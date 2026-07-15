"""Unit tests for headless browser-liveness recovery (scripts/headless_check.py).

WHY this file exists: the render harness drives ONE persistent headless Chrome over its
DevTools pipe (the 2026-07-15 rework that replaced 60+ per-probe `--dump-dom` subprocess
launches, which truncated under load and failed a random test every full run). The one
remaining infrastructure failure mode is the persistent browser DYING mid-suite (a crash,
an OOM kill). When that happens the transport raises `_BrowserDead`; `probe` then drops the
dead browser and relaunches a fresh one ONCE for the current read — browser-liveness
recovery, never an assertion retry.

These tests mock `_one_probe` (the single live read), so they need no real Chrome and are
fast + deterministic. They pin three behaviours:
  1. a TRANSIENT browser death (die once, then a live read) → probe RECOVERS, does not raise.
  2. a PERSISTENT death (every attempt dies) → still raises after exhausting the relaunches.
  3. a REAL read failure (the browser is alive, the read itself fails) → raises IMMEDIATELY
     without relaunching — recovery can never mask a genuine test failure.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import headless_check as hc  # noqa: E402


class HeadlessBrowserLivenessRecovery(unittest.TestCase):
    def test_transient_death_recovers(self):
        """The first read dies (browser transport broke); the relaunch reads cleanly. probe
        must RECOVER — return the parsed result — not raise — and must relaunch exactly once."""
        seq = [hc._BrowserDead("Chrome pipe closed"), {"ok": True, "n": 3}]
        with mock.patch.object(hc, "_one_probe", side_effect=seq) as m, \
                mock.patch.object(hc, "_shutdown") as sd, \
                mock.patch.object(hc.time, "sleep"):
            result = hc.probe("/tmp/w.html", "({ok:true})")
        self.assertEqual(result, {"ok": True, "n": 3},
                         "probe must return the result after recovering from a browser death")
        self.assertEqual(m.call_count, 2, "probe must relaunch exactly once (die, then success)")
        self.assertEqual(sd.call_count, 1, "the dead browser must be dropped before relaunch")

    def test_persistent_death_still_raises(self):
        """Every attempt dies — probe must still raise after exhausting the relaunches, and
        must have tried _RENDER_ATTEMPTS times."""
        seq = [hc._BrowserDead("Chrome process exited") for _ in range(hc._RENDER_ATTEMPTS)]
        with mock.patch.object(hc, "_one_probe", side_effect=seq) as m, \
                mock.patch.object(hc, "_shutdown"), \
                mock.patch.object(hc.time, "sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                hc.probe("/tmp/w.html", "({ok:true})")
        self.assertIn("did not stay alive", str(ctx.exception))
        self.assertEqual(m.call_count, hc._RENDER_ATTEMPTS,
                         f"a persistent death must exhaust all {hc._RENDER_ATTEMPTS} attempts")

    def test_real_read_failure_raises_without_relaunch(self):
        """The browser is alive but the read itself fails (a malformed js expression, a page
        that never rendered). probe must raise on the FIRST attempt and must NOT relaunch, so
        recovery can never mask a real test failure."""
        seq = [RuntimeError("probe returned no value (page may not have rendered)"),
               {"ok": True}]  # a 2nd success is offered but must never be reached
        with mock.patch.object(hc, "_one_probe", side_effect=seq) as m, \
                mock.patch.object(hc, "_shutdown") as sd, \
                mock.patch.object(hc.time, "sleep") as sleep_mock:
            with self.assertRaises(RuntimeError) as ctx:
                hc.probe("/tmp/w.html", "(this is not valid)")
        self.assertIn("probe returned no value", str(ctx.exception))
        self.assertEqual(m.call_count, 1,
                         "a real read failure must fail immediately — no relaunch")
        sd.assert_not_called()
        sleep_mock.assert_not_called()


@unittest.skipUnless(Path(hc.CHROME).exists(), "real Chrome not installed on this host")
class HeadlessBrowserProcessGroupIsolation(unittest.TestCase):
    """The persistent browser runs in its OWN process group, and shutdown reaps that whole
    group. This is what keeps a forced/hung teardown from leaking orphan browsers AND keeps a
    reap scoped to THIS run — never a name/path pattern that could match another window's Chrome
    or the human's real browser. Drives a real Chrome, so it is skipped where none is installed."""

    def tearDown(self):
        # never leak the module-global browser into a sibling test
        try:
            hc._shutdown()
        except Exception:
            pass
        hc._BROWSER = None

    def test_browser_runs_in_own_group_and_shutdown_reaps_it(self):
        b = hc._browser()
        pid = b._proc.pid
        pgid = os.getpgid(pid)
        # start_new_session makes the browser its own group leader (pgid == pid), distinct from
        # this test runner's group — so a group reap can never hit the runner.
        self.assertEqual(pgid, pid, "browser must lead its own process group (start_new_session)")
        self.assertNotEqual(pgid, os.getpgid(0), "browser group must differ from the test runner's")
        # a live CDP round-trip confirms the browser is really up before we tear it down
        self.assertTrue(b.call("Browser.getVersion", timeout=20), "browser must be live")
        hc._shutdown()
        # the whole group must be gone — killpg with signal 0 is an existence probe
        with self.assertRaises(ProcessLookupError,
                               msg="shutdown must reap the browser's entire process group"):
            os.killpg(pgid, 0)


if __name__ == "__main__":
    unittest.main()
