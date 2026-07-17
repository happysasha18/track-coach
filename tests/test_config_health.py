"""The installed git hook matches its source (adopted from live-spec 2.1.0, SPEC INV-175).

A gate lives twice: guardrails/pre-push travels with the repo; .git/hooks/pre-push actually
runs. They drift the moment an install is skipped — exactly what happened here on 2026-07-17
(the scoped gate b was edited in guardrails/pre-push but the installed hook stayed stale until
a reinstall). This test reds when the installed hook is missing or differs, naming the fix
(guardrails/install.sh). A CI checkout with no installed hooks skips by name.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ConfigHealth(unittest.TestCase):
    def test_installed_hooks_match_source(self):
        r = subprocess.run(
            ["bash", str(ROOT / "guardrails" / "check-config-health.sh")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(r.returncode, 0,
                         "installed git hook drifted from its guardrails/ source "
                         "(run guardrails/install.sh):\n" + r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
