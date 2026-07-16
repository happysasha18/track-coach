#!/usr/bin/env python3
"""test_atomic_io.py — crash-consistent index/marker writes + loud load (root class 1
of the 2026-07-16 command audit).

The data-loss root: index.json / aliases.json were written in place (plain write_text),
and a corrupt-but-present file was silently coerced to an EMPTY library — so a kill
mid-write erased the catalog and the next save persisted the loss (and gc then reclaimed
"unreferenced" run dirs). The fix, pinned here:

  * every index/marker write goes through library._atomic_write_text (tmp + fsync +
    os.replace), so a kill at any instant leaves the OLD file or the NEW file, never a
    truncated one, and no `.tmp` litter survives a clean write (G-INV-11: no half state).
  * load_index FAILS LOUDLY (SystemExit) on a present-but-unparseable index rather than
    returning {"entries": []} — a corrupt read never overwrites the real catalog with empty.
  * load_aliases stays additive but WARNS on a corrupt-present file (lost merges are
    visible, not silent) instead of an indistinguishable "no aliases set".

Pure stdlib unittest; no heavy deps.
"""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import library  # noqa: E402


class AtomicWriteHelper(unittest.TestCase):
    def test_helper_exists_and_round_trips(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "sub" / "x.json"  # parent does not exist yet
            library._atomic_write_text(p, '{"k": 1}')
            self.assertEqual(json.loads(p.read_text()), {"k": 1})

    def test_no_tmp_litter_after_clean_write(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            library._atomic_write_text(p, "hello")
            leftovers = [q.name for q in Path(d).iterdir() if q.name != "x.json"]
            self.assertEqual(leftovers, [], f"atomic write left litter: {leftovers}")


class SaveIndexAtomic(unittest.TestCase):
    def test_save_index_uses_atomic_write_no_tmp_left(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            library.save_index(root, {"entries": [{"track": "t", "widget": "w.html"}]})
            names = sorted(q.name for q in root.iterdir())
            self.assertIn("index.json", names)
            self.assertNotIn("index.json.tmp", names)
            self.assertEqual(library.load_index(root)["entries"][0]["track"], "t")


class LoudLoadIndex(unittest.TestCase):
    def test_corrupt_present_index_fails_loud(self):
        """A present-but-unparseable index.json must NOT read back as empty — it exits loud."""
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "index.json").write_text('{"entries": [{"track": "t"')  # truncated
            with self.assertRaises(SystemExit):
                library.load_index(root)

    def test_absent_index_is_empty(self):
        with TemporaryDirectory() as d:
            self.assertEqual(library.load_index(Path(d))["entries"], [])

    def test_blank_index_is_treated_as_fresh_empty(self):
        """A zero-byte / whitespace-only index is the fresh-root case, not corruption."""
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "index.json").write_text("   \n")
            self.assertEqual(library.load_index(root)["entries"], [])

    def test_valid_index_still_normalizes_str_entries(self):
        """The legacy string-entry normalization survives the loud-load change."""
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "index.json").write_text(json.dumps({"entries": ["legacy-slug"]}))
            entries = library.load_index(root)["entries"]
            self.assertEqual(entries, [{"widget": "legacy-slug"}])


class AliasesAtomicAndVisible(unittest.TestCase):
    def test_save_aliases_atomic_no_tmp_left(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            library.save_aliases(root, {"a": "b"})
            names = sorted(q.name for q in root.iterdir())
            self.assertIn("aliases.json", names)
            self.assertNotIn("aliases.json.tmp", names)
            self.assertEqual(library.load_aliases(root), {"a": "b"})

    def test_absent_aliases_silent_empty(self):
        with TemporaryDirectory() as d:
            buf = io.StringIO()
            with redirect_stderr(buf):
                self.assertEqual(library.load_aliases(Path(d)), {})
            self.assertEqual(buf.getvalue(), "", "absent aliases must be silent")

    def test_corrupt_present_aliases_warns_but_additive(self):
        """A corrupt aliases.json must surface a stderr warning (lost merges visible),
        yet stay additive (return {}) so it never blocks a read the way the index does."""
        with TemporaryDirectory() as d:
            root = Path(d)
            (root / "aliases.json").write_text('{"aliases": {"a":')  # truncated
            buf = io.StringIO()
            with redirect_stderr(buf):
                self.assertEqual(library.load_aliases(root), {})
            self.assertIn("aliases.json", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
