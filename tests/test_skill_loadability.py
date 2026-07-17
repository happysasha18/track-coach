"""The shipped SKILL.md loads and scopes itself (adopted from live-spec, the Trail-of-Bits lesson).

track-coach ships as a skill others install. A skill that ships with broken frontmatter, a name that
does not match its folder, no description, no metadata version, or no "when NOT to use" section is a
broken artifact however good its prose — the harness can't index it or a reader can't scope it. This
gate runs guardrails/check-skill-loadability.sh over the root SKILL.md; a NEW break reds.

FIT DECISION (2026-07-17): the pack gate globs skills/*/SKILL.md for a repo-of-skills; track-coach is
one tool-skill whose SKILL.md sits at the repo root, so the checker was adapted to that root file.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "guardrails" / "check-skill-loadability.sh"


class SkillLoadability(unittest.TestCase):
    def test_root_skill_loads_named_versioned_and_negative_scoped(self):
        r = subprocess.run(
            [str(CHECKER), str(ROOT)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(
            r.returncode, 0,
            "the shipped SKILL.md does not load/scope cleanly (frontmatter, name, "
            "description, metadata version, or 'when NOT to use' section):\n" + r.stdout + r.stderr,
        )

    def test_checker_catches_a_missing_section(self):
        """Negative (INV-6): the checker must RED a skill that drops a required piece —
        a green-only assertion could pass with a broken checker."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            broken = Path(d)
            # a well-formed frontmatter but NO 'when NOT to use' section and NO version
            (broken / "SKILL.md").write_text(
                "---\nname: " + broken.name + "\ndescription: x\n---\n\nbody only\n"
            )
            r = subprocess.run(
                [str(CHECKER), str(broken)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(r.returncode, 0,
                                "checker passed a SKILL.md missing version + 'when NOT to use'")


if __name__ == "__main__":
    unittest.main()
