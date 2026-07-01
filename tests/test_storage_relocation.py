#!/usr/bin/env python3
"""Tests for §G storage relocation invariants (G-INV-1…17).

All tests use tmp_path / temp dirs. They NEVER touch ~/.track-coach/ (the real library/projects).
Tests assert against the REAL shipped artifact — actual functions from run_dir.py, catalog.py,
library.py, track_analyzer.py — never a source-string match.
"""
import json
import sys
import types
import unittest
from pathlib import Path
import tempfile

import pytest

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_dir      # noqa: E402
import catalog      # noqa: E402
import library      # noqa: E402


def _fake_args(**kw):
    """Create a minimal argparse-like namespace."""
    ns = types.SimpleNamespace(base=None, als=None, track_version=None, mode="full")
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _touch(path: Path) -> Path:
    """Create a file (and parent dirs) — just needs to exist, not real audio."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"FAKE")
    return path


# ─── Item 1: Relocation default (G-INV-1 / G-INV-3) ──────────────────────────

class RelocationDefault(unittest.TestCase):
    """G-INV-1/3: default base is ~/.track-coach/projects; --base overrides it."""

    def test_default_base_is_home_projects(self, tmp_path=None):
        """With no --base, base_dir() returns ~/.track-coach/projects — NOT next to the audio."""
        # Use a temp file path that doesn't need to exist (base_dir is pure)
        audio = Path("/some/ableton/project/My_Track.wav")
        args = _fake_args(base=None)
        result = run_dir.base_dir(args, audio)
        expected = Path.home() / ".track-coach" / "projects"
        self.assertEqual(result, expected)
        # Crucially: NOT under the audio's folder
        self.assertFalse(str(result).startswith(str(audio.parent)))

    def test_base_flag_still_overrides(self):
        """--base overrides the default; path shape base/slug/stamp is preserved."""
        with tempfile.TemporaryDirectory() as td:
            audio = Path(td) / "project" / "My_Track.wav"
            args = _fake_args(base=str(Path(td) / "custom_base"))
            result = run_dir.base_dir(args, audio)
            self.assertEqual(result, (Path(td) / "custom_base").resolve())
            # Ensure it's NOT the new default
            self.assertNotEqual(result, Path.home() / ".track-coach" / "projects")

    def test_run_dir_is_under_home_projects_when_no_base(self):
        """cmd_init with no --base creates the run dir under ~/.track-coach/projects/<slug>/."""
        with tempfile.TemporaryDirectory() as td:
            audio = _touch(Path(td) / "project" / "Beat_v1.wav")
            args = _fake_args(audio=str(audio), base=None)
            # Redirect stdout to capture run_dir path without writing to real home
            # Instead, test via base_dir + track_root
            base = run_dir.base_dir(args, audio)
            self.assertTrue(str(base).startswith(str(Path.home() / ".track-coach" / "projects")))


# ─── Item 2: Collision disambiguation (G-INV-2 / G-INV-2b) ───────────────────

class CollisionDisambiguation(unittest.TestCase):
    """G-INV-2/2b: same source → same slug; different source → slug-2."""

    def test_same_source_reuses_slug(self):
        """Running the same audio twice reuses the same slug dir (no slug-2)."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            audio = _touch(Path(td) / "als" / "My_Track.wav")
            args1 = _fake_args(audio=str(audio), base=str(base))
            args2 = _fake_args(audio=str(audio), base=str(base))
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(args1)
                run_dir.cmd_init(args2)
            # Both runs land under the same slug dir
            slug = run_dir.slugify(audio.name)
            slug_dir = base / slug
            self.assertTrue(slug_dir.exists())
            # No slug-2 should be created
            slug2_dir = base / f"{slug}-2"
            self.assertFalse(slug2_dir.exists(), f"Unexpected slug-2 dir: {slug2_dir}")
            # Two run subdirs (both stamps) in the slug dir
            run_dirs = [p for p in slug_dir.iterdir() if p.is_dir() and p.name != "latest"]
            self.assertGreaterEqual(len(run_dirs), 2)

    def test_different_source_gets_slug_2(self):
        """Two different audio files with the same name → second gets slug-2."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            # Same filename, different directories → same slug → collision
            audio1 = _touch(Path(td) / "project_a" / "My_Track.wav")
            audio2 = _touch(Path(td) / "project_b" / "My_Track.wav")
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio1), base=str(base)))
                run_dir.cmd_init(_fake_args(audio=str(audio2), base=str(base)))
            slug = run_dir.slugify("My_Track.wav")
            slug_dir = base / slug
            slug2_dir = base / f"{slug}-2"
            self.assertTrue(slug_dir.exists(), f"Primary slug dir missing: {slug_dir}")
            self.assertTrue(slug2_dir.exists(), f"slug-2 dir not created for different source: {slug2_dir}")

    def test_run_meta_carries_source_identity(self):
        """Each run's run_meta.json has a source_identity field."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            audio = _touch(Path(td) / "project" / "My_Track.wav")
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio), base=str(base)))
            slug = run_dir.slugify(audio.name)
            slug_dir = base / slug
            run_dirs = [p for p in slug_dir.iterdir() if p.is_dir() and p.name != "latest"]
            self.assertTrue(run_dirs, "No run dirs created")
            meta = json.loads((run_dirs[0] / "run_meta.json").read_text())
            self.assertIn("source_identity", meta, "source_identity not in run_meta.json")
            # Should be the audio path (no als provided); compare resolved paths
            # because cmd_init calls .expanduser().resolve() which may add /private on macOS
            self.assertEqual(meta["source_identity"], str(audio.resolve()))


# ─── Item 3: Seed on first post-move run (G-INV-12) ──────────────────────────

class SeedFromOldIndex(unittest.TestCase):
    """G-INV-12: first post-move run merges old per-folder index into new shared index."""

    def test_old_index_entries_appear_in_new_index(self):
        """Old-style index beside audio is seeded into the new shared index on first run."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            new_base = td / "new_projects"
            audio = _touch(td / "als_project" / "Beat.wav")
            slug = run_dir.slugify(audio.name)

            # Create old-style index at <audio_parent>/track-coach-output/index.json
            old_index_dir = audio.parent / "track-coach-output"
            old_index_dir.mkdir(parents=True, exist_ok=True)
            old_run_meta = {
                "track": slug, "version": "", "run_dir": str(old_index_dir / slug / "2026-01-01_1000"),
                "analyzed_at": "2026-01-01 10:00", "mode": "full",
                "audio": audio.name, "als": None,
            }
            (old_index_dir / "index.json").write_text(json.dumps({"runs": [old_run_meta]}))

            # First run with the new base
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio), base=str(new_base)))

            # The new shared index should contain the old entry PLUS the new run
            new_idx_path = new_base / "index.json"
            self.assertTrue(new_idx_path.exists(), "New shared index.json not created")
            new_idx = json.loads(new_idx_path.read_text())
            all_runs = new_idx.get("runs", [])
            old_run_dirs = [r.get("run_dir") for r in all_runs]
            self.assertIn(old_run_meta["run_dir"], old_run_dirs,
                         "Old index entry not seeded into new shared index")
            # New run should also be there
            self.assertGreater(len(all_runs), 1, "New run not added")

    def test_no_old_index_proceeds_normally(self):
        """When no old index exists, the tool just creates the new index without seeding."""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            new_base = td / "new_projects"
            audio = _touch(td / "fresh_project" / "NewTrack.wav")
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio), base=str(new_base)))
            new_idx_path = new_base / "index.json"
            self.assertTrue(new_idx_path.exists())
            new_idx = json.loads(new_idx_path.read_text())
            self.assertEqual(len(new_idx.get("runs", [])), 1)


# ─── Item 4: Catalog open-link fallback (G-INV-14) ───────────────────────────

class CatalogFallback(unittest.TestCase):
    """G-INV-14: open href falls back to library HTML copy when src_run_dir is gone."""

    def _make_library(self, tmp: Path, src_run_dir_exists: bool = False):
        """Create a temp library with one entry; src_run_dir may or may not exist."""
        lib_root = tmp / "library"
        widgets_dir = lib_root / "widgets"
        widgets_dir.mkdir(parents=True)
        widget_name = "My_Track__v1__2026-01-01_1000.html"
        (widgets_dir / widget_name).write_text("<html>widget</html>")

        # The src_run_dir: either real (sub-path in tmp) or nonexistent
        if src_run_dir_exists:
            src_dir = tmp / "projects" / "My_Track" / "v1__2026-01-01_1000"
            src_dir.mkdir(parents=True)
            (src_dir / "analysis_widget.html").write_text("<html>original</html>")
        else:
            src_dir = tmp / "ableton" / "project_a" / "track-coach-output" / "My_Track" / "v1__2026-01-01_1000"
            # NOT created on disk

        entry = {
            "track": "My_Track", "version": "v1", "stamp": "2026-01-01_1000",
            "widget": widget_name, "mode": "full",
            "src_run_dir": str(src_dir), "src_widget": "analysis_widget.html",
            "deposited_at": "2026-01-01T10:00:00+00:00",
        }
        idx = {"entries": [entry]}
        (lib_root / "index.json").write_text(json.dumps(idx))
        return lib_root, src_dir, widgets_dir / widget_name

    def test_open_href_falls_back_to_library_copy(self):
        """When src_run_dir doesn't exist on disk, open href → library's HTML copy (file://)."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root, src_dir, lib_copy = self._make_library(tmp, src_run_dir_exists=False)
            # Confirm src_dir does NOT exist
            self.assertFalse(src_dir.exists())
            self.assertTrue(lib_copy.exists())

            # build_catalog probes src_run_dir and injects _lib_href
            out = catalog.build_catalog(root=lib_root)
            html_text = out.read_text()

            # The open href must point at the library copy — NOT at the dead src_run_dir
            lib_uri = lib_copy.as_uri()
            self.assertIn(lib_uri, html_text,
                         "Library copy URI not found in catalog HTML when src_run_dir is missing")
            # The src_run_dir URI (nonexistent) should NOT appear as an open link
            dead_uri = (src_dir / "analysis_widget.html").as_uri()
            self.assertNotIn(dead_uri, html_text,
                            "Dead src_run_dir URI should not appear when dir is missing")

    def test_render_does_not_crash_when_src_run_dir_missing(self):
        """Rendering a catalog whose src_run_dir is gone doesn't raise."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root, src_dir, lib_copy = self._make_library(tmp, src_run_dir_exists=False)
            # Should not raise
            try:
                catalog.build_catalog(root=lib_root)
            except Exception as e:
                self.fail(f"build_catalog raised unexpectedly with missing src_run_dir: {e}")

    def test_existing_src_run_dir_is_preferred(self):
        """When src_run_dir exists, the original widget URI is used (not the library copy)."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root, src_dir, lib_copy = self._make_library(tmp, src_run_dir_exists=True)
            out = catalog.build_catalog(root=lib_root)
            html_text = out.read_text()
            orig_uri = (src_dir / "analysis_widget.html").as_uri()
            self.assertIn(orig_uri, html_text,
                         "Original widget URI should be used when src_run_dir exists")


# ─── Item 5: Catalog passive migrate-warning (G-INV-16 support) ──────────────

class MigrateWarning(unittest.TestCase):
    """G-INV-16 support: catalog shows a banner for entries with src_run_dir outside the output root."""

    def test_banner_counts_outside_root_members(self):
        """Banner appears with N=1 when one member's src_run_dir is outside the output root."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root = tmp / "library"
            widgets_dir = lib_root / "widgets"
            widgets_dir.mkdir(parents=True)

            # Two entries: one inside the output root (tmp/), one outside (tmp/ableton/)
            inside_dir = tmp / "projects" / "TrackA" / "v1__2026-01-01_1000"
            inside_dir.mkdir(parents=True)
            outside_dir = tmp / "ableton_project" / "track-coach-output" / "TrackB" / "v1__2026-01-01_1000"
            # outside_dir intentionally NOT under lib_root.parent (which is tmp/)
            # Actually tmp/ contains everything... let me use a truly outside path

        # Use an explicit non-temp path that's clearly outside
        with tempfile.TemporaryDirectory() as td_lib, tempfile.TemporaryDirectory() as td_ableton:
            lib_root = Path(td_lib) / "library"
            widgets_dir = lib_root / "widgets"
            widgets_dir.mkdir(parents=True)

            inside_dir = Path(td_lib) / "projects" / "TrackA" / "v1__2026-01-01_1000"
            inside_dir.mkdir(parents=True)

            outside_dir = Path(td_ableton) / "track-coach-output" / "TrackB" / "v1__2026-01-01_1000"
            # Not created on disk (doesn't matter for the banner check)

            w1 = "TrackA__v1__2026-01-01_1000.html"
            w2 = "TrackB__v1__2026-01-01_1000.html"
            (widgets_dir / w1).write_text("<html>a</html>")
            (widgets_dir / w2).write_text("<html>b</html>")

            entries = [
                {"track": "TrackA", "version": "v1", "stamp": "2026-01-01_1000",
                 "widget": w1, "mode": "full", "src_run_dir": str(inside_dir),
                 "deposited_at": "2026-01-01T10:00:00+00:00"},
                {"track": "TrackB", "version": "v1", "stamp": "2026-01-01_1000",
                 "widget": w2, "mode": "full", "src_run_dir": str(outside_dir),
                 "deposited_at": "2026-01-01T10:00:00+00:00"},
            ]
            (lib_root / "index.json").write_text(json.dumps({"entries": entries}))

            out = catalog.build_catalog(root=lib_root)
            html_text = out.read_text()

            # Banner div should be present and mention exactly 1 track
            self.assertIn('<div class="migrate-banner">', html_text,
                         "No migrate banner div in catalog when members have outside src_run_dir")
            self.assertIn("1 track", html_text,
                         "Banner should mention N=1 track outside root")

    def test_no_banner_when_all_inside_root(self):
        """No banner when all members' src_run_dir are inside the output root."""
        with tempfile.TemporaryDirectory() as td:
            lib_root = Path(td) / "library"
            widgets_dir = lib_root / "widgets"
            widgets_dir.mkdir(parents=True)
            inside_dir = Path(td) / "projects" / "TrackA" / "v1__2026-01-01_1000"
            inside_dir.mkdir(parents=True)
            w = "TrackA__v1__2026-01-01_1000.html"
            (widgets_dir / w).write_text("<html>a</html>")
            entries = [
                {"track": "TrackA", "version": "v1", "stamp": "2026-01-01_1000",
                 "widget": w, "mode": "full", "src_run_dir": str(inside_dir),
                 "deposited_at": "2026-01-01T10:00:00+00:00"},
            ]
            (lib_root / "index.json").write_text(json.dumps({"entries": entries}))
            out = catalog.build_catalog(root=lib_root)
            html_text = out.read_text()
            # No migrate banner div when all dirs are inside the root
            # (the CSS class .migrate-banner is always emitted; only the banner DIV is conditional)
            self.assertNotIn('<div class="migrate-banner">', html_text,
                            "Banner div should NOT appear when all src_run_dirs are inside root")


# ─── Item 6: RC-INV-9 disk-presence check (G-INV-11) ────────────────────────

class DiskPresenceCheck(unittest.TestCase):
    """G-INV-11: index-based run selector skips entries whose run dir is missing on disk."""

    def test_missing_run_dir_is_skipped(self):
        """existing_runs() returns only entries whose run_dir exists on disk."""
        with tempfile.TemporaryDirectory() as td:
            real_dir = Path(td) / "real_run"
            real_dir.mkdir()
            gone_dir = Path(td) / "deleted_run"
            # gone_dir NOT created

            runs = [
                {"track": "MyTrack", "run_dir": str(real_dir), "version": "v1"},
                {"track": "MyTrack", "run_dir": str(gone_dir), "version": "v2"},
            ]
            result = run_dir.existing_runs(runs)
            run_dirs_returned = [r["run_dir"] for r in result]
            self.assertIn(str(real_dir), run_dirs_returned)
            self.assertNotIn(str(gone_dir), run_dirs_returned)

    def test_all_missing_returns_empty(self):
        """existing_runs() returns empty list when all entries point at missing dirs."""
        runs = [
            {"track": "MyTrack", "run_dir": "/nonexistent/path/run1", "version": "v1"},
            {"track": "MyTrack", "run_dir": "/nonexistent/path/run2", "version": "v2"},
        ]
        result = run_dir.existing_runs(runs)
        self.assertEqual(result, [])

    def test_non_dict_entries_are_skipped(self):
        """existing_runs() silently skips non-dict entries (legacy strings)."""
        with tempfile.TemporaryDirectory() as td:
            real_dir = Path(td) / "real"
            real_dir.mkdir()
            runs = [
                "legacy_string_entry",
                {"track": "MyTrack", "run_dir": str(real_dir)},
            ]
            result = run_dir.existing_runs(runs)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["run_dir"], str(real_dir))

    def test_library_index_entries_use_src_run_dir_key(self):
        """existing_runs() also works with library index entries (src_run_dir key)."""
        with tempfile.TemporaryDirectory() as td:
            real_dir = Path(td) / "real_run"
            real_dir.mkdir()
            gone_dir = Path(td) / "gone_run"

            # Library index uses src_run_dir, not run_dir
            entries = [
                {"track": "MyTrack", "src_run_dir": str(real_dir), "widget": "x.html"},
                {"track": "MyTrack", "src_run_dir": str(gone_dir), "widget": "y.html"},
            ]
            result = run_dir.existing_runs(entries)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["src_run_dir"], str(real_dir))


class CmdCatalogHidesAbsentRows(unittest.TestCase):
    """G-INV-11 / RC-INV-9 applied to the in-widget plaque (catalog.json built by cmd_catalog).

    Absent non-self rows must be DROPPED entirely from catalog.json so the plaque
    never renders a dead '(file not found)' entry.  The self/current row is always
    kept even when its widget file does not exist yet at catalog-build time.
    A track whose only runs are all absent is dropped from the catalog.
    Counts (n_runs / n_tracks) reflect only the visible rows.
    """

    def _make_index(self, base: Path, entries: list) -> Path:
        idx = base / "index.json"
        idx.write_text(json.dumps({"runs": entries}))
        return idx

    def test_absent_non_self_entry_is_hidden(self):
        """One present + one absent run for the same track: absent must not appear in catalog.json."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self_run = base / "TrackA" / "v1__2026-07-01_1200"
            self_run.mkdir(parents=True)
            widget = self_run / "analysis_widget.html"
            widget.write_text("<html>self</html>")

            gone_run = base / "TrackA" / "v0__2026-06-30_1000"
            # gone_run NOT created — widget file will not exist

            self._make_index(base, [
                {"track": "TrackA", "run_dir": str(self_run), "version": "v1",
                 "analyzed_at": "2026-07-01", "verdict": "good", "mode": "full"},
                {"track": "TrackA", "run_dir": str(gone_run), "version": "v0",
                 "analyzed_at": "2026-06-30", "verdict": "old", "mode": "full"},
            ])

            import types
            args = types.SimpleNamespace(self=str(self_run), base=str(base))
            run_dir.cmd_catalog(args)

            cat = json.loads((self_run / "catalog.json").read_text())
            all_versions = [r["version"] for t in cat["tracks"] for r in t["runs"]]
            self.assertIn("v1", all_versions, "self row must be present")
            self.assertNotIn("v0", all_versions, "absent non-self row must be hidden")

    def test_counts_reflect_only_visible_rows(self):
        """n_runs and n_tracks count only surviving (non-absent, non-dropped) rows."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # Track A: self run (present) + one absent run
            self_run = base / "TrackA" / "v1__2026-07-01_1200"
            self_run.mkdir(parents=True)
            (self_run / "analysis_widget.html").write_text("<html/>")
            gone_run = base / "TrackA" / "v0__2026-06-20_0800"
            # Track B: one present run
            b_run = base / "TrackB" / "v1__2026-07-01_1000"
            b_run.mkdir(parents=True)
            (b_run / "analysis_widget.html").write_text("<html/>")

            self._make_index(base, [
                {"track": "TrackA", "run_dir": str(self_run), "version": "v1",
                 "analyzed_at": "2026-07-01", "mode": "full"},
                {"track": "TrackA", "run_dir": str(gone_run), "version": "v0",
                 "analyzed_at": "2026-06-20", "mode": "full"},
                {"track": "TrackB", "run_dir": str(b_run), "version": "v1",
                 "analyzed_at": "2026-07-01", "mode": "full"},
            ])

            import types
            args = types.SimpleNamespace(self=str(self_run), base=str(base))
            run_dir.cmd_catalog(args)

            cat = json.loads((self_run / "catalog.json").read_text())
            # 2 tracks survive (TrackA + TrackB); 2 visible runs (one per track)
            self.assertEqual(cat["n_tracks"], 2)
            self.assertEqual(cat["n_runs"], 2)

    def test_track_with_only_absent_runs_is_dropped(self):
        """A track whose every run dir is absent must be dropped from the catalog entirely."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self_run = base / "TrackA" / "v1__2026-07-01_1200"
            self_run.mkdir(parents=True)
            (self_run / "analysis_widget.html").write_text("<html/>")

            # TrackB exists only as stale index entries — no run dir on disk
            ghost_run1 = base / "TrackB" / "v1__2026-06-01_1000"
            ghost_run2 = base / "TrackB" / "v2__2026-06-15_1200"

            self._make_index(base, [
                {"track": "TrackA", "run_dir": str(self_run), "version": "v1",
                 "analyzed_at": "2026-07-01", "mode": "full"},
                {"track": "TrackB", "run_dir": str(ghost_run1), "version": "v1",
                 "analyzed_at": "2026-06-01", "mode": "full"},
                {"track": "TrackB", "run_dir": str(ghost_run2), "version": "v2",
                 "analyzed_at": "2026-06-15", "mode": "full"},
            ])

            import types
            args = types.SimpleNamespace(self=str(self_run), base=str(base))
            run_dir.cmd_catalog(args)

            cat = json.loads((self_run / "catalog.json").read_text())
            track_names = [t["track"] for t in cat["tracks"]]
            self.assertNotIn("TrackB", track_names, "all-absent track must be dropped")
            self.assertEqual(cat["n_tracks"], 1)

    def test_self_entry_kept_even_without_widget_file(self):
        """The self row must always appear in catalog.json even when its widget file is missing.

        This covers the build-time window: catalog.json is written BEFORE build_widget runs,
        so analysis_widget.html may not exist yet for the current run.
        """
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self_run = base / "TrackA" / "v1__2026-07-01_1200"
            self_run.mkdir(parents=True)
            # Deliberately do NOT create analysis_widget.html for the self run

            self._make_index(base, [
                {"track": "TrackA", "run_dir": str(self_run), "version": "v1",
                 "analyzed_at": "2026-07-01", "mode": "full"},
            ])

            import types
            args = types.SimpleNamespace(self=str(self_run), base=str(base))
            run_dir.cmd_catalog(args)

            cat = json.loads((self_run / "catalog.json").read_text())
            all_versions = [r["version"] for t in cat["tracks"] for r in t["runs"]]
            self.assertIn("v1", all_versions, "self row must survive even without a widget file")


# ─── Item 7: migrate command (G-INV-16) ───────────────────────────────────────

class MigrateCommand(unittest.TestCase):
    """G-INV-16: migrate dry-run reports the plan + changes nothing; --apply moves + rewrites index."""

    def _setup_migrate_scenario(self, tmp: Path):
        """Create a fake library with one member whose src_run_dir is in an 'ableton' folder."""
        lib_root = tmp / "output_root" / "library"
        widgets_dir = lib_root / "widgets"
        widgets_dir.mkdir(parents=True)

        # The "old" run dir — outside the output root
        ableton_run = tmp / "ableton_project" / "track-coach-output" / "My_Track" / "v1__2026-01-01_1000"
        ableton_run.mkdir(parents=True)
        (ableton_run / "analysis_widget.html").write_text("<html>widget</html>")
        (ableton_run / "run_meta.json").write_text(json.dumps({
            "track": "My_Track", "track_version": "v1", "mode": "full",
            "analyzed_at": "2026-01-01 10:00", "audio": "My_Track.wav",
        }))

        widget_name = "My_Track__v1__2026-01-01_1000.html"
        (widgets_dir / widget_name).write_text("<html>copy</html>")

        entries = [{
            "track": "My_Track", "version": "v1", "stamp": "2026-01-01_1000",
            "widget": widget_name, "mode": "full",
            "src_run_dir": str(ableton_run),
            "src_widget": "analysis_widget.html",
            "deposited_at": "2026-01-01T10:00:00+00:00",
        }]
        (lib_root / "index.json").write_text(json.dumps({"entries": entries}))

        output_root = tmp / "output_root"
        return lib_root, ableton_run, output_root

    def test_dry_run_changes_nothing(self):
        """migrate dry-run: plan is computed but nothing is moved, index unchanged."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root, ableton_run, output_root = self._setup_migrate_scenario(tmp)

            plan = library.migrate_plan(lib_root, output_root)
            self.assertEqual(len(plan), 1, "Expected exactly 1 member to migrate")
            self.assertEqual(plan[0]["src"], ableton_run)

            # Dry-run: nothing is moved
            self.assertTrue(ableton_run.exists(), "Source run dir should still exist after dry-run")

            # Index unchanged
            idx = library.load_index(lib_root)
            self.assertEqual(idx["entries"][0]["src_run_dir"], str(ableton_run))

    def test_migrate_apply_moves_and_rewrites(self):
        """migrate --apply: moves the run dir into the output root and rewrites src_run_dir."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root, ableton_run, output_root = self._setup_migrate_scenario(tmp)

            plan = library.migrate_plan(lib_root, output_root)
            self.assertEqual(len(plan), 1)

            moved = library.migrate_apply(lib_root, output_root)
            self.assertEqual(len(moved), 1)

            # Original dir is gone
            self.assertFalse(ableton_run.exists(),
                            "Source run dir should be moved, not remain in ableton folder")

            # New location exists
            new_dir = plan[0]["dst"]
            self.assertTrue(new_dir.exists(), f"New run dir not found at expected location: {new_dir}")

            # Index is rewritten
            idx = library.load_index(lib_root)
            updated_src = idx["entries"][0]["src_run_dir"]
            self.assertEqual(updated_src, str(new_dir),
                            f"src_run_dir not updated in index: {updated_src!r}")

    def test_migrate_apply_no_op_when_already_inside(self):
        """migrate_apply does nothing when all members are already inside the output root."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root = tmp / "output_root" / "library"
            (lib_root / "widgets").mkdir(parents=True)
            output_root = tmp / "output_root"

            # Put a run dir INSIDE the output root
            inside_run = output_root / "projects" / "MyTrack" / "v1__2026-01-01_1000"
            inside_run.mkdir(parents=True)
            (inside_run / "run_meta.json").write_text("{}")
            w = "MyTrack__v1__2026-01-01_1000.html"
            (lib_root / "widgets" / w).write_text("<html/>")

            entries = [{"track": "MyTrack", "version": "v1", "stamp": "2026-01-01_1000",
                       "widget": w, "mode": "full", "src_run_dir": str(inside_run),
                       "deposited_at": "2026-01-01T10:00:00+00:00"}]
            (lib_root / "index.json").write_text(json.dumps({"entries": entries}))

            plan = library.migrate_plan(lib_root, output_root)
            self.assertEqual(plan, [], "No migration needed when all inside root")
            moved = library.migrate_apply(lib_root, output_root)
            self.assertEqual(moved, [])
            # Source still exists
            self.assertTrue(inside_run.exists())


if __name__ == "__main__":
    unittest.main()
