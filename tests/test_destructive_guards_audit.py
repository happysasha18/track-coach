#!/usr/bin/env python3
"""test_destructive_guards_audit.py — destructive-command guards (audit root class 4).

Each is its own quick fix in the same family: a preview/guard that did not hold.
  * clean --apply --dry-run deleted anyway (the --dry-run flag was parsed, never read).
  * clean crashed KeyError('track') on a legacy string index entry.
  * backup with zero sources silently created an empty .backup_ok snapshot ("all backed up").
  * reset --no-backup accepted ANY .backup_ok snapshot, including an empty one, so a populated
    library could be wiped unrecoverably without --i-understand.
  * restore joined the stamp onto backups/ with no validation — a stamp with path separators
    escaped the root.
  * dereference --album-path "" matched every entry and emptied the index.
  * a symlink child of the output root crashed hard-reset/reset (stat/rmtree follow symlinks).

Pure stdlib unittest.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import library  # noqa: E402


class CleanGuards(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.lib = Path(self._tmp) / "library"
        (self.lib / "widgets").mkdir(parents=True)
        os.environ["TRACK_COACH_LIBRARY"] = str(self.lib)

    def tearDown(self):
        os.environ.pop("TRACK_COACH_LIBRARY", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _seed(self, entries):
        for e in entries:
            w = e.get("widget")
            if w:
                (self.lib / "widgets" / w).write_text("<html>w</html>")
        library.save_index(self.lib, {"entries": entries})

    def test_dry_run_beats_apply(self):
        """clean --apply --dry-run must PREVIEW, never delete (explicit --dry-run wins)."""
        self._seed([{"track": "T", "stamp": "s1", "widget": "w.html", "deposited_at": ""}])
        args = types.SimpleNamespace(all=True, older_than=None, keep_per_track=None,
                                     track=None, missing=False, apply=True, yes=False,
                                     dry_run=True)
        library._cmd_clean(args)
        self.assertTrue((self.lib / "widgets" / "w.html").exists(),
                        "--dry-run must win over --apply and delete nothing")
        self.assertEqual(len(library.load_index(self.lib)["entries"]), 1,
                         "the index must be untouched under --dry-run")

    def test_clean_legacy_string_entry_no_keyerror(self):
        """clean --missing must not KeyError on a legacy string entry (coerced to {'widget':...})."""
        library.save_index(self.lib, {"entries": ["legacy-slug",
                                                   {"track": "T", "stamp": "s1",
                                                    "widget": "w.html", "deposited_at": ""}]})
        (self.lib / "widgets" / "w.html").write_text("<html>w</html>")
        args = types.SimpleNamespace(all=False, older_than=None, keep_per_track=None,
                                     track=None, missing=True, apply=False, yes=False,
                                     dry_run=False)
        library._cmd_clean(args)  # must not raise


class BackupAndResetGuards(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.base = Path(self._tmp) / "output"
        self.base.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _curate(self):
        lib = self.base / "library" / "widgets"
        lib.mkdir(parents=True)
        (lib / "a.html").write_text("<html>w</html>")
        library.save_index(self.base / "library", {"entries": []})

    def test_backup_zero_sources_refuses(self):
        """A user backup with nothing curated must fail loud, not create an empty snapshot."""
        args = types.SimpleNamespace(base=str(self.base), full=False, list=False)
        with self.assertRaises(SystemExit):
            library._cmd_backup(args)
        self.assertFalse((self.base / "backups").exists()
                         and any((self.base / "backups").iterdir()),
                         "no snapshot may be created when there is nothing to back up")

    def test_empty_snapshot_is_not_a_valid_backup_when_curated_present(self):
        """An empty .backup_ok snapshot must not count as protecting real curated work."""
        self._curate()
        empty = self.base / "backups" / "2020-01-01_0000"
        empty.mkdir(parents=True)
        (empty / ".backup_ok").write_text("ok")
        self.assertFalse(library._has_valid_backup(self.base),
                         "an empty snapshot must not satisfy the --no-backup guard")

    def test_reset_no_backup_empty_snapshot_demands_i_understand(self):
        """reset --no-backup with only an empty snapshot must refuse without --i-understand
        and wipe nothing."""
        self._curate()
        empty = self.base / "backups" / "2020-01-01_0000"
        empty.mkdir(parents=True)
        (empty / ".backup_ok").write_text("ok")
        args = types.SimpleNamespace(base=str(self.base), yes_wipe_everything=True,
                                     no_backup=True, i_understand=False)
        with self.assertRaises(SystemExit):
            library._cmd_reset(args)
        self.assertTrue((self.base / "library").exists(),
                        "the curated library must survive a refused wipe")

    def test_do_backup_marker_written_into_final_dir_no_tmp_left(self):
        self._curate()
        dest = library._do_backup(self.base)
        self.assertTrue((dest / ".backup_ok").exists(),
                        "the trust marker must live in the final snapshot dir")
        leftover = list((self.base / "backups").glob("_tmp_*"))
        self.assertEqual(leftover, [], f"no _tmp_ litter may survive: {leftover}")


class RestoreAndDereferenceGuards(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.base = Path(self._tmp) / "output"
        (self.base / "backups").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_restore_rejects_path_escape_stamp(self):
        """A stamp with path separators must not resolve to a dir OUTSIDE backups/, even
        when that dir exists and carries a .backup_ok (the real escape vector)."""
        evil = self.base / "evil"          # sibling of backups/, reachable via '../evil'
        (evil / "library").mkdir(parents=True)
        (evil / ".backup_ok").write_text("ok")
        args = types.SimpleNamespace(base=str(self.base),
                                     stamp="../evil", apply=True, force=True)
        with self.assertRaises(SystemExit):
            library._cmd_restore(args)

    def test_dereference_rejects_empty_album_path(self):
        os.environ["TRACK_COACH_LIBRARY"] = str(self.base / "library")
        try:
            (self.base / "library").mkdir(parents=True, exist_ok=True)
            library.save_index(self.base / "library",
                               {"entries": [{"track": "T", "widget": "w.html",
                                             "src_run_dir": "/some/path"}]})
            args = types.SimpleNamespace(album_path=[""], apply=True)
            with self.assertRaises(SystemExit):
                library._cmd_dereference(args)
        finally:
            os.environ.pop("TRACK_COACH_LIBRARY", None)


class SymlinkSafeWipe(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.base = Path(self._tmp) / "output"
        self.base.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_hard_reset_dry_run_survives_dangling_symlink(self):
        """A dangling symlink child must not crash the always-safe hard-reset preview."""
        (self.base / "projects").mkdir()
        (self.base / "link").symlink_to(self.base / "does-not-exist")  # dangling
        args = types.SimpleNamespace(base=str(self.base), yes_wipe_everything=False,
                                     including_backups=False)
        library._cmd_hard_reset(args)  # must not raise


if __name__ == "__main__":
    unittest.main()
