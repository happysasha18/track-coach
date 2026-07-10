"""The /tc and /tc-quick commands must SHIP with the repo and be installed by setup.sh.

Guards the packaging gap found 2026-07-10 (s63): the commands existed only in the
author's global ~/.claude/commands/, so a fresh clone + setup.sh never delivered them —
the README promised a command surface a new user would not have. This test keeps the
three surfaces (repo files, installer, README) in lockstep so the gap cannot silently
return.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CommandsShipWithRepo(unittest.TestCase):
    def test_command_files_present_in_repo(self):
        for c in ("tc", "tc-quick"):
            p = os.path.join(ROOT, "commands", f"{c}.md")
            self.assertTrue(os.path.isfile(p), f"missing shipped command: commands/{c}.md")

    def test_command_files_invoke_the_skill(self):
        for c in ("tc", "tc-quick"):
            txt = open(os.path.join(ROOT, "commands", f"{c}.md")).read()
            self.assertIn("description:", txt, f"commands/{c}.md has no frontmatter description")
            self.assertIn("track-coach", txt, f"commands/{c}.md does not invoke the track-coach skill")

    def test_setup_installs_the_commands(self):
        setup = open(os.path.join(ROOT, "setup.sh")).read()
        self.assertIn(".claude/commands", setup, "setup.sh does not target the Claude commands folder")
        self.assertIn("commands/$c.md", setup, "setup.sh does not copy the shipped command files")

    def test_readme_and_repo_agree_on_the_commands(self):
        readme = open(os.path.join(ROOT, "README.md")).read()
        self.assertIn("/tc", readme)
        self.assertIn("/tc-quick", readme)


if __name__ == "__main__":
    unittest.main()
