#!/usr/bin/env python3
"""test_straggler_audit.py — the remaining correctness tails of the 2026-07-16 command audit.

  * alias --merge silently overwrote an existing mapping (a→b became a→c with no mention that the
    old merge was dropped), so a typo'd second merge lost the first without a trace.
  * remove/prune-versions/clean unlinked widget files BEFORE the (now atomic) index rewrite, so a
    kill in that window left the index pointing at deleted widgets — the harmful half-state. The
    index must be rewritten first (a leftover widget file is harmless; a dangling entry is not).

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


class AliasReMergeNote(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.lib = Path(self._tmp) / "library"
        (self.lib / "widgets").mkdir(parents=True)
        os.environ["TRACK_COACH_LIBRARY"] = str(self.lib)
        library.save_index(self.lib, {"entries": [
            {"track": "a", "stamp": "s1", "widget": "a.html"},
            {"track": "b", "stamp": "s2", "widget": "b.html"},
            {"track": "c", "stamp": "s3", "widget": "c.html"}]})

    def tearDown(self):
        os.environ.pop("TRACK_COACH_LIBRARY", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_remerge_discloses_replaced_mapping(self):
        library.save_aliases(self.lib, {"a": "b"})
        # catalog.build_catalog is heavy; stub it — we only assert the disclosure.
        import catalog
        orig = catalog.build_catalog
        catalog.build_catalog = lambda *a, **k: ""
        self.addCleanup(setattr, catalog, "build_catalog", orig)
        args = types.SimpleNamespace(list=False, remove=None, merge="a", into="c")
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            library._cmd_alias(args)
        out = err.getvalue()
        self.assertIn("b", out, "re-merging a already-aliased slug must disclose the replaced target")
        self.assertEqual(library.load_aliases(self.lib).get("a"), "c")


class RemoveSavesIndexBeforeUnlink(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.lib = Path(self._tmp) / "library"
        self.wdir = self.lib / "widgets"
        self.wdir.mkdir(parents=True)
        os.environ["TRACK_COACH_LIBRARY"] = str(self.lib)
        (self.wdir / "w.html").write_text("<html>w</html>")
        library.save_index(self.lib, {"entries": [
            {"track": "T", "stamp": "s1", "widget": "w.html"}]})
        self._orig_save = library.save_index
        self._present = {}

        def spy(root, idx):
            # crash-consistency: the widget file must still be on disk when the index is rewritten
            # (index-first), so a kill between save and unlink leaves a harmless orphan, not a
            # dangling index entry.
            self._present["at_save"] = (self.wdir / "w.html").exists()
            return self._orig_save(root, idx)

        library.save_index = spy

    def tearDown(self):
        library.save_index = self._orig_save
        os.environ.pop("TRACK_COACH_LIBRARY", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _stub_regen(self):
        orig = library._regen_catalog
        library._regen_catalog = lambda: None
        self.addCleanup(setattr, library, "_regen_catalog", orig)

    def test_remove_rewrites_index_before_unlink(self):
        self._stub_regen()
        args = types.SimpleNamespace(track="T", version=None, apply=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_remove(args)
        self.assertTrue(self._present.get("at_save"),
                        "remove must save the index BEFORE unlinking widgets (index-first)")

    def test_prune_rewrites_index_before_unlink(self):
        self._stub_regen()
        library.save_index(self.lib, {"entries": [
            {"track": "T", "stamp": "s1", "widget": "w.html", "audio_sha": "OLD", "audio_mtime": 1},
            {"track": "T", "stamp": "s2", "widget": "w2.html", "audio_sha": "NEW", "audio_mtime": 2}]})
        (self.wdir / "w2.html").write_text("<html>w2</html>")
        self._present.clear()
        args = types.SimpleNamespace(keep=1, apply=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_prune_versions(args)
        self.assertTrue(self._present.get("at_save"),
                        "prune-versions must save the index BEFORE unlinking widgets")

    def test_clean_rewrites_index_before_unlink(self):
        args = types.SimpleNamespace(all=True, older_than=None, keep_per_track=None, track=None,
                                     missing=False, apply=True, yes=False, dry_run=False)
        self._stub_regen()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_clean(args)
        self.assertTrue(self._present.get("at_save"),
                        "clean must save the index BEFORE unlinking widgets")


if __name__ == "__main__":
    unittest.main()
