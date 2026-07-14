"""Unit tests for the headless-Chrome crash retry (scripts/headless_check.py).

WHY this file exists: the headless render harness crashes INTERMITTENTLY under system
load. A different random subset of the browser-level tests fails on each full-suite run,
always with the same signature — the probe node is absent from the dumped DOM and Chrome's
stderr shows a headless crash (NOTREACHED hit / browser_context_impl.cc /
ProcessHeadlessCommands / crashpad … mach_vm_read … invalid address). Each failing test
passes cleanly on a re-run in isolation, which proves the render is correct and only the
infrastructure flaked. That flake blocks the pre-push gate (which runs the full suite), so
`_probe_render` now retries the crash — up to _RENDER_ATTEMPTS total — while leaving every
GENUINE failure to fail immediately.

These tests mock `_run_chrome`, so they need no real Chrome and are fast + deterministic.
They pin three behaviours:
  1. a TRANSIENT crash (crash once, then a good DOM) → probe RECOVERS, does not raise.
  2. a PERSISTENT crash (every attempt crashes) → still raises after exhausting the retries.
  3. a NON-crash miss (probe node absent, NO crash markers) → raises WITHOUT retrying
     (call count is 1) — the retry never masks a real failure.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import headless_check as hc  # noqa: E402


# A dumped DOM that CONTAINS the injected probe node with a valid JSON payload.
_GOOD_DOM = (
    "<html><body>widget…"
    '<script id="__tc_probe" type="application/json">{"ok": true, "n": 3}</script>'
    "</body></html>")

# stderr carrying the real headless-crash signature (every marker the flake shows).
_CRASH_STDERR = (
    "[1234:5678:0101/000000.000000:FATAL:browser_context_impl.cc(42)] "
    "Check failed: NOTREACHED hit. \n"
    "ProcessHeadlessCommands\n"
    "crashpad_handler: mach_vm_read failed: (os/kern) invalid address\n")

# A dumped DOM with NO probe node, and stderr WITHOUT any crash marker — a genuine miss
# (e.g. a malformed `js` expression whose injected script never appended the node).
_EMPTY_DOM = "<html><body>page loaded but the probe never ran</body></html>"
_BENIGN_STDERR = "[INFO:headless_shell.cc(100)] rendered ok, no probe expression matched\n"


def _cp(stdout: str, stderr: str) -> CompletedProcess:
    return CompletedProcess(args=["chrome"], returncode=0, stdout=stdout, stderr=stderr)


def _tiny_widget() -> str:
    """A minimal on-disk HTML file so probe() can read + rewrite it. Its content is
    irrelevant because _run_chrome is mocked — only a real path is needed."""
    tmp = Path(tempfile.mkdtemp(prefix="tc_retry_"))
    out = tmp / "w.html"
    out.write_text("<head></head><body>hi</body>", encoding="utf-8")
    return str(out)


class HeadlessCrashRetry(unittest.TestCase):
    def setUp(self):
        self.widget = _tiny_widget()

    def test_transient_crash_recovers(self):
        """First render crashes (crash-signature stderr, no probe node); the retry renders a
        good DOM. probe must RECOVER — return the parsed result — not raise."""
        seq = [_cp("", _CRASH_STDERR), _cp(_GOOD_DOM, "")]
        with mock.patch.object(hc, "_run_chrome", side_effect=seq) as m, \
                mock.patch.object(hc.time, "sleep"):  # no real backoff wait
            result = hc.probe(self.widget, "({ok:true})")
        self.assertEqual(result, {"ok": True, "n": 3},
                         "probe must return the parsed result after recovering from a crash")
        self.assertEqual(m.call_count, 2,
                         "probe must have retried exactly once (crash, then success)")

    def test_persistent_crash_still_raises(self):
        """Every attempt crashes with the signature — probe must still raise after
        exhausting the retries, and must have tried _RENDER_ATTEMPTS times."""
        seq = [_cp("", _CRASH_STDERR) for _ in range(hc._RENDER_ATTEMPTS)]
        with mock.patch.object(hc, "_run_chrome", side_effect=seq) as m, \
                mock.patch.object(hc.time, "sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                hc.probe(self.widget, "({ok:true})")
        self.assertIn("probe result not found", str(ctx.exception))
        self.assertEqual(m.call_count, hc._RENDER_ATTEMPTS,
                         f"a persistent crash must exhaust all {hc._RENDER_ATTEMPTS} attempts")

    def test_noncrash_miss_fails_without_retrying(self):
        """The probe node is absent but stderr shows NO crash marker — a genuine failure
        (e.g. a malformed js expression). probe must raise on the FIRST attempt and must
        NOT retry, so the retry can never mask a real test failure."""
        seq = [_cp(_EMPTY_DOM, _BENIGN_STDERR),
               _cp(_GOOD_DOM, "")]  # a 2nd success is offered but must never be reached
        with mock.patch.object(hc, "_run_chrome", side_effect=seq) as m, \
                mock.patch.object(hc.time, "sleep") as sleep_mock:
            with self.assertRaises(RuntimeError) as ctx:
                hc.probe(self.widget, "(this is not valid)")
        self.assertIn("probe result not found", str(ctx.exception))
        self.assertEqual(m.call_count, 1,
                         "a non-crash miss must fail immediately — the retry must NOT fire")
        sleep_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
