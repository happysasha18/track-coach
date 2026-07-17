"""The shipped set stays free of Cyrillic and owner-name leaks (adopted from live-spec, SPEC INV-120).

track-coach ships as a skill others install, so a personal name or a Russian process note in a
tracked file would travel to every user. This gate refuses a shipped file that carries Cyrillic
outside a deliberate user-language string, or an owner/personal name, unless the file is a known
detector or an authorship line listed in scripts/shipped-language-allowlist.json. A NEW leak reds.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ShippedLanguage(unittest.TestCase):
    def test_no_cyrillic_or_owner_name_in_shipped_set(self):
        r = subprocess.run(
            ["python3", str(ROOT / "scripts" / "check-shipped-language.py"), "--root", str(ROOT)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(r.returncode, 0,
                         "a shipped file carries Cyrillic or an owner name outside the allowlist "
                         "(SPEC INV-120):\n" + r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
