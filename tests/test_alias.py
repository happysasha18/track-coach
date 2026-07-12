#!/usr/bin/env python3
"""Same-song alias merge (G-INV-23): two tracks under different filenames show as ONE catalog row.

A user records that slug A is the same song as slug B (a rename, a different bounce named differently).
The alias map folds A onto B BEFORE the catalog groups by track, so the two collapse to one row and
their distinct bounces stay as versions. The map is pure metadata, additive, and reversible.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import library  # noqa: E402
import catalog  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "library.py"


def _entry(track, sha, stamp):
    return {"track": track, "widget": f"{track}.html", "stamp": stamp, "audio_sha": sha,
            "mode": "full", "src_run_dir": f"/runs/{track}"}


class AliasMap(unittest.TestCase):
    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            library.save_aliases(root, {"b": "a"})
            self.assertEqual(library.load_aliases(root), {"b": "a"})

    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(library.load_aliases(Path(d)), {})

    def test_self_alias_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / library.ALIASES_FILE).write_text(json.dumps({"aliases": {"a": "a"}}))
            self.assertEqual(library.load_aliases(root), {})

    def test_resolve_follows_chain(self):
        self.assertEqual(library.resolve_alias("c", {"c": "b", "b": "a"}), "a")

    def test_resolve_is_cycle_safe(self):
        # a→b→a must not spin; returns the last slug reached, never hangs.
        self.assertIn(library.resolve_alias("a", {"a": "b", "b": "a"}), {"a", "b"})

    def test_canonicalize_is_pure(self):
        e = _entry("b", "sha_b", "s1")
        original = dict(e)
        out = library.canonicalize_entries([e], {"b": "a"})
        self.assertEqual(out[0]["track"], "a", "the copy is rewritten to canonical")
        self.assertEqual(e, original, "the input entry is never mutated")

    def test_empty_map_is_a_copy(self):
        es = [_entry("a", "s", "s1")]
        self.assertEqual(library.canonicalize_entries(es, {}), es)


class AliasMergesGrouping(unittest.TestCase):
    """The whole point: after canonicalisation the two filename identities are ONE track."""

    def test_two_filenames_collapse_to_one_track_two_versions(self):
        a = _entry("fragile_rearrange", "sha1", "2026-01-02_1000")
        b = _entry("total_reboot_fragile", "sha2", "2026-01-01_1000")
        # before: two separate tracks
        self.assertEqual(len(library.group_versions([a, b])), 2)
        # after aliasing b → a: one track, two versions
        merged = library.canonicalize_entries([a, b], {"total_reboot_fragile": "fragile_rearrange"})
        groups = library.group_versions(merged)
        self.assertEqual(list(groups), ["fragile_rearrange"], "one row, canonical slug")
        self.assertEqual(len(groups["fragile_rearrange"]), 2, "both bounces kept as versions")

    def test_catalog_renders_one_row(self):
        a = _entry("fragile_rearrange", "sha1", "2026-01-02_1000")
        b = _entry("total_reboot_fragile", "sha2", "2026-01-01_1000")
        merged = library.canonicalize_entries([a, b], {"total_reboot_fragile": "fragile_rearrange"})
        html = catalog.render_catalog_html(merged)
        self.assertIn("1 track", html, "the merged catalog counts ONE track")


class AliasCli(unittest.TestCase):
    def _run(self, root, *args):
        env = dict(os.environ, TRACK_COACH_LIBRARY=str(root))
        return subprocess.run([sys.executable, str(SCRIPT), "alias", *args],
                              text=True, capture_output=True, env=env)

    def _seed(self, root):
        (root / "widgets").mkdir(parents=True, exist_ok=True)
        idx = {"entries": [_entry("fragile_rearrange", "s1", "2026-01-02_1000"),
                           _entry("total_reboot_fragile", "s2", "2026-01-01_1000")]}
        (root / "index.json").write_text(json.dumps(idx))

    def test_merge_list_remove(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lib"
            self._seed(root)
            m = self._run(root, "--merge", "total_reboot_fragile", "--into", "fragile_rearrange")
            self.assertEqual(m.returncode, 0, m.stderr)
            self.assertEqual(library.load_aliases(root),
                             {"total_reboot_fragile": "fragile_rearrange"})
            ls = self._run(root, "--list")
            self.assertIn("total_reboot_fragile", ls.stdout)
            rm = self._run(root, "--remove", "total_reboot_fragile")
            self.assertEqual(rm.returncode, 0, rm.stderr)
            self.assertEqual(library.load_aliases(root), {})

    def test_self_merge_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lib"
            self._seed(root)
            r = self._run(root, "--merge", "fragile_rearrange", "--into", "fragile_rearrange")
            self.assertNotEqual(r.returncode, 0, "merging a track into itself is refused")

    def test_cycle_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "lib"
            self._seed(root)
            self._run(root, "--merge", "total_reboot_fragile", "--into", "fragile_rearrange")
            r = self._run(root, "--merge", "fragile_rearrange", "--into", "total_reboot_fragile")
            self.assertNotEqual(r.returncode, 0, "a merge that forms a cycle is refused")


if __name__ == "__main__":
    unittest.main(verbosity=2)
