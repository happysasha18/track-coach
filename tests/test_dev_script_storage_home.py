#!/usr/bin/env python3
"""Guard: dev/eval scripts must not root analysis-data paths inside the user's
working folders (Ableton projects under ~/Desktop, albums under ~/Downloads).

The 21 GB scatter cleaned up on 2026-07-12 came from analysis output landing
next to the source audio inside those working folders. Storage now lives under
~/.track-coach/ (G-INV-1). This guard keeps the two dev/eval scripts from ever
again anchoring a DATA ROOT back at a working folder. It scans source text (no
import side effects), like the traceability guards.
"""
import re
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
GUARDED = ["gen_reference_directions.py", "eval_rec_specificity.py"]

# A data root anchored at one of these first components sits inside the user's
# working folders. A "Downloads" segment UNDER ~/.track-coach is allowed — that
# is the migration dump's provenance mirror, not a working-folder root.
FORBIDDEN_ROOTS = [
    r'H\(\s*["\']~/Downloads',
    r'H\(\s*["\']~/Desktop',
    r'Path\.home\(\)\s*/\s*["\']Desktop["\']',
    r'Path\.home\(\)\s*/\s*["\']Downloads["\']',
    r'migrated-\d{4}-\d{2}-\d{2}',  # a dated migration dump is a personal-machine path, never a data root
]


class DevScriptStorageHome(unittest.TestCase):
    def test_no_working_folder_data_root(self):
        offenders = []
        for name in GUARDED:
            src = (SCRIPTS / name).read_text()
            for pat in FORBIDDEN_ROOTS:
                if re.search(pat, src):
                    offenders.append(f"{name}: matches forbidden working-folder root /{pat}/")
        self.assertEqual(
            offenders, [],
            "dev/eval scripts must root analysis data under ~/.track-coach, not "
            "inside the user's working folders:\n" + "\n".join(offenders))

    def test_scripts_reference_the_tool_home(self):
        for name in GUARDED:
            src = (SCRIPTS / name).read_text()
            self.assertIn(
                ".track-coach", src,
                f"{name} should root its analysis data under ~/.track-coach")


if __name__ == "__main__":
    unittest.main()
