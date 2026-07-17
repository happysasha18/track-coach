"""Browser-safety guardrails ride the suite (adopted from live-spec 2.1.0, SPEC INV-162/INV-157).

Two nets the pack learned from real incidents, run here so a regression reds a push:
  - broad-kill: no tracked script kills a browser by a bare name (a broad `pkill chrome`
    once closed the user's own browser mid-session).
  - muted-launch: every script that drives a real headless browser launches it muted
    (an unmuted headless Chrome plays sound on the machine during a test run).
Each test runs the vendored gate over track-coach's tracked files and asserts it is green.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARDRAILS = ROOT / "guardrails"


def _run(script):
    return subprocess.run(
        ["bash", str(GUARDRAILS / script)],
        capture_output=True, text=True, cwd=str(ROOT),
    )


class BrowserSafetyGates(unittest.TestCase):
    def test_no_broad_browser_kill(self):
        r = _run("check-broad-kill.sh")
        self.assertEqual(r.returncode, 0,
                         "a tracked script kills a browser by a bare name (INV-162):\n"
                         + r.stdout + r.stderr)

    def test_headless_launches_are_muted(self):
        r = _run("check-muted-launch.sh")
        self.assertEqual(r.returncode, 0,
                         "a tracked script drives a headless browser without --mute-audio "
                         "(INV-157):\n" + r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
