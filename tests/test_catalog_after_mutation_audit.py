#!/usr/bin/env python3
"""test_catalog_after_mutation_audit.py — catalog left stale after a mutation (audit root class 6).

clean, dereference, and restore mutated the index but never regenerated the catalog (unlike their
siblings remove/prune-versions), so the visible Catalog page kept showing removed tracks with dead
links. dereference also dropped index entries but never unlinked the deposited widget HTML copies,
orphaning other people's music in library/widgets/ with no verb left to reclaim them. And
`list --track T` with no match on a populated library said "(library empty)" — factually wrong.

Pure stdlib unittest.
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import library  # noqa: E402


class RegenAfterMutation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.base = Path(self._tmp) / "root"
        self.lib = self.base / "library"
        (self.lib / "widgets").mkdir(parents=True)
        os.environ["TRACK_COACH_LIBRARY"] = str(self.lib)
        os.environ["TRACK_COACH_ROOT"] = str(self.base)
        self._calls = []
        self._orig = library._regen_catalog
        library._regen_catalog = lambda: self._calls.append(True)

    def tearDown(self):
        library._regen_catalog = self._orig
        os.environ.pop("TRACK_COACH_LIBRARY", None)
        os.environ.pop("TRACK_COACH_ROOT", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _seed(self, entries):
        for e in entries:
            w = e.get("widget")
            if w:
                (self.lib / "widgets" / w).write_text("<html>w</html>")
        library.save_index(self.lib, {"entries": entries})

    def test_clean_apply_regenerates_catalog(self):
        self._seed([{"track": "T", "stamp": "s1", "widget": "w.html", "deposited_at": ""}])
        args = types.SimpleNamespace(all=True, older_than=None, keep_per_track=None, track=None,
                                     missing=False, apply=True, yes=False, dry_run=False)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_clean(args)
        self.assertEqual(self._calls, [True], "clean --apply must regenerate the catalog (G-INV-11)")

    def test_dereference_apply_regenerates_and_unlinks_widget(self):
        self._seed([{"track": "Ref", "stamp": "s1", "widget": "ref.html",
                     "src_run_dir": "/music/DeepChord/track-coach-output/s1"}])
        args = types.SimpleNamespace(album_path=["/music/DeepChord"], apply=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_dereference(args)
        self.assertEqual(self._calls, [True], "dereference --apply must regenerate the catalog")
        self.assertFalse((self.lib / "widgets" / "ref.html").exists(),
                         "dereference must unlink the dropped widget HTML (no orphan)")

    def test_restore_apply_regenerates_catalog(self):
        snap = self.base / "backups" / "2026-07-16_120000"
        (snap / "library").mkdir(parents=True)
        (snap / "library" / "index.json").write_text('{"entries": []}')
        (snap / ".backup_ok").write_text("ok")
        args = types.SimpleNamespace(base=str(self.base), stamp="2026-07-16_120000",
                                     apply=True, force=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_restore(args)
        self.assertEqual(self._calls, [True], "restore --apply must regenerate the catalog (H-INV-9)")


class ListNoMatch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.lib = Path(self._tmp) / "library"
        (self.lib / "widgets").mkdir(parents=True)
        os.environ["TRACK_COACH_LIBRARY"] = str(self.lib)

    def tearDown(self):
        os.environ.pop("TRACK_COACH_LIBRARY", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_no_match_is_not_library_empty(self):
        (self.lib / "widgets" / "w.html").write_text("<html>w</html>")
        library.save_index(self.lib, {"entries": [
            {"track": "RealTrack", "stamp": "s1", "widget": "w.html"}]})
        args = types.SimpleNamespace(track="nosuchtrack", json=False)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            library._cmd_list(args)
        text = out.getvalue()
        self.assertNotIn("(library empty)", text,
                         "a populated library with no filter match must NOT say '(library empty)'")
        self.assertIn("nosuchtrack", text, "the message should name the track that matched nothing")


if __name__ == "__main__":
    unittest.main()
