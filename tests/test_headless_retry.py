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


if __name__ == "__main__":
    unittest.main()
