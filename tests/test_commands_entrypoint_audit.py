"""The /tc and /tc-quick command files must drive the SANCTIONED one-command entrypoint
(track_analyzer.py analyze/build), not the deprecated hand-driven pipeline (audit root
class 3).

SKILL.md forbids hand-driving run_dir.py init + build_widget.py; on that path the commands'
"every build auto-deposits + rebuilds the catalog" promise was a silent no-op (deposit lives
only in track_analyzer.py cmd_build). These checks pin the fix so the drift cannot return.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cmd(c):
    return open(os.path.join(ROOT, "commands", f"{c}.md")).read()


class CommandsUseEntrypoint(unittest.TestCase):
    def test_both_route_through_track_analyzer_entrypoint(self):
        for c in ("tc", "tc-quick"):
            txt = _cmd(c)
            # the quoted invocation is  ...track_analyzer.py" analyze  /  ..." build
            self.assertRegex(txt, r'track_analyzer\.py"?\s+analyze',
                             f"commands/{c}.md must drive the analyze entrypoint")
            self.assertRegex(txt, r'track_analyzer\.py"?\s+build',
                             f"commands/{c}.md must drive the build entrypoint")

    def test_neither_hand_drives_the_forbidden_internals(self):
        for c in ("tc", "tc-quick"):
            txt = _cmd(c)
            self.assertNotIn("run_dir.py init", txt,
                             f"commands/{c}.md still hand-drives run_dir.py init (forbidden)")
            self.assertNotIn("build_widget.py", txt,
                             f"commands/{c}.md still hand-drives build_widget.py (forbidden)")

    def test_both_pass_title(self):
        for c in ("tc", "tc-quick"):
            self.assertIn("--title", _cmd(c),
                          f"commands/{c}.md must pass --title (SKILL.md: always required)")

    def test_quick_does_not_deny_the_mix_player(self):
        """tc-quick must not tell the agent to drop the player — quick still ships a
        single-track mix player, encoded automatically by the entrypoint (§B.14)."""
        txt = _cmd("tc-quick")
        self.assertNotIn("no player", txt.lower())
        self.assertNotIn("/ player", txt.lower())


if __name__ == "__main__":
    unittest.main()
