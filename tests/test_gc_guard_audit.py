#!/usr/bin/env python3
"""test_gc_guard_audit.py — the gc user-file guard (H-INV-5), audit root class 2.

The destructive-classifier holes the 2026-07-16 command audit found:
  * `_slug_dir_has_real_runs` only looked for child *directories*, so a slug dir
    holding a loose regular file (a bounce, notes.txt) plus a dangling symlink was
    classified 'safe' and rmtree'd — deleting the user's own file (H-INV-5 says the
    sweep never touches non-track-coach files).
  * neither `ableton_tail_scan` nor `--scan-dir` checked its scan target is actually a
    `track-coach-output/` dir, so the KI-1 shallow-deposit shape (parent.parent lands
    on the Ableton project folder itself) pointed the destructive classifier at an
    arbitrary user folder.

Pure stdlib unittest.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import library  # noqa: E402


class LooseFileIsProtected(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_slug_dir_with_loose_file_is_not_safe(self):
        """A slug dir holding a loose regular file must NOT be classified 'safe'."""
        slug = Path(self._tmp) / "track-coach-output" / "myslug"
        slug.mkdir(parents=True)
        (slug / "index.json").write_text("{}")
        (slug / "latest").symlink_to("2026-01-01_1000")  # dangling
        (slug / "mytrack-final.wav").write_text("PCM")   # the user's own file
        self.assertTrue(
            library._slug_dir_has_real_runs(slug),
            "a loose user file must disqualify a slug dir from the 'safe' (deletable) set")

    def test_scan_leaves_loose_file_slug_out_of_safe(self):
        tco = Path(self._tmp) / "track-coach-output"
        slug = tco / "myslug"
        slug.mkdir(parents=True)
        (slug / "latest").symlink_to("gone")            # dangling
        (slug / "notes.txt").write_text("my notes")     # user file
        scan = library.ableton_tail_scan([tco])
        safe = {str(s.resolve()) for _, s in scan["safe"]}
        self.assertNotIn(str(slug.resolve()), safe,
                         "a slug dir with a loose user file must never be 'safe'")


class ScanTargetShapeGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_non_output_dir_basename_is_skipped_not_scanned(self):
        """A scan target whose basename is not track-coach-output (the KI-1 shallow shape
        pointing at the Ableton project folder itself) must be skipped, never scanned —
        so its child folders are not classified deletable."""
        proj = Path(self._tmp) / "MyAbletonProject"  # NOT a track-coach-output dir
        child = proj / "Samples"                      # a real user folder
        child.mkdir(parents=True)
        (child / "kick.wav").write_text("PCM")
        scan = library.ableton_tail_scan([proj])
        safe = {str(s.resolve()) for _, s in scan["safe"]}
        self.assertNotIn(str(child.resolve()), safe,
                         "a non-output-dir target must not have its children marked safe")
        self.assertIn(proj, scan.get("skipped", []),
                      "a non-conforming scan target must be reported as skipped")


if __name__ == "__main__":
    unittest.main()
