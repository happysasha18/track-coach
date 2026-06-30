#!/usr/bin/env python3
"""Tests for §H cleanup commands: reset, gc, gc --ableton-tails, remove, prune-versions.

All tests use tmp dirs. NEVER touches ~/.track-coach/ (the real library/projects).
Tests assert against the REAL shipped artifact — actual functions from library.py —
not source-string matches.

Test order mirrors the build checklist:
  1. ResetCommand          (H-INV-6)
  2. GcPlan / GcCommand    (H-INV-3)
  3. AbletonTailSweep      (H-INV-5)
  4. RemovePlan / RemoveCommand        (H-INV-2)
  5. PruneVersionsPlan / PruneVersionsCommand  (H-INV-4)
"""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import library  # noqa: E402


# ─── helpers ──────────────────────────────────────────────────────────────────

def _touch(path: Path, content: bytes = b"FAKE") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _make_run(slug_dir: Path, name: str, n_results: int = 0) -> Path:
    """Create a run dir with n_results result_*.json files."""
    rd = slug_dir / name
    rd.mkdir(parents=True, exist_ok=True)
    for i in range(n_results):
        (rd / f"result_stage{i}.json").write_text("{}")
    return rd


def _make_library(tmp: Path, entries: list) -> tuple:
    """Set up a minimal library under tmp with given entries + widget files."""
    lib_root = tmp / "library"
    wdir = lib_root / "widgets"
    wdir.mkdir(parents=True)
    for e in entries:
        (wdir / e["widget"]).write_text("<html>widget</html>")
    library.save_index(lib_root, {"entries": entries})
    return lib_root, wdir


# ─── 1. reset (H-INV-6) ───────────────────────────────────────────────────────

class ResetDryRun(unittest.TestCase):
    """Bare reset prints a plan and removes nothing. H-INV-6."""

    def test_dry_run_removes_nothing(self):
        """A bare reset (no --yes-wipe-everything) must not delete any directory."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "output"
            projects = base / "projects" / "slug1" / "run1"
            projects.mkdir(parents=True)
            (projects / "result.json").write_text("{}")
            lib = base / "library"
            lib.mkdir(parents=True)
            (lib / "index.json").write_text('{"entries":[]}')

            os.environ["TRACK_COACH_ROOT"] = str(base)
            try:
                args = types.SimpleNamespace(base=None, yes_wipe_everything=False)
                library._cmd_reset(args)
                # dry-run: nothing removed
                self.assertTrue((base / "projects").exists(),
                                "reset dry-run must NOT delete projects/")
                self.assertTrue((base / "library").exists(),
                                "reset dry-run must NOT delete library/")
            finally:
                os.environ.pop("TRACK_COACH_ROOT", None)

    def test_dry_run_prints_plan(self, capsys=None):
        """Bare reset must print what it WOULD remove (smoke-test: no crash)."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "output"
            (base / "projects").mkdir(parents=True)
            (base / "library").mkdir(parents=True)
            os.environ["TRACK_COACH_ROOT"] = str(base)
            try:
                args = types.SimpleNamespace(base=None, yes_wipe_everything=False)
                # Should not raise; output goes to stdout
                library._cmd_reset(args)
            finally:
                os.environ.pop("TRACK_COACH_ROOT", None)


class ResetApply(unittest.TestCase):
    """reset --yes-wipe-everything removes projects/ + library/ and leaves siblings. H-INV-6."""

    def test_wipe_removes_projects_and_library(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "output"
            projects = base / "projects" / "slug1" / "run1"
            projects.mkdir(parents=True)
            lib = base / "library" / "widgets"
            lib.mkdir(parents=True)

            os.environ["TRACK_COACH_ROOT"] = str(base)
            try:
                args = types.SimpleNamespace(base=None, yes_wipe_everything=True)
                library._cmd_reset(args)
                self.assertFalse((base / "projects").exists(),
                                 "reset --yes-wipe-everything must remove projects/")
                self.assertFalse((base / "library").exists(),
                                 "reset --yes-wipe-everything must remove library/")
            finally:
                os.environ.pop("TRACK_COACH_ROOT", None)

    def test_wipe_leaves_sibling_dir_untouched(self):
        """reset must not touch directories outside the output root (G-INV-7)."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "output"
            sibling_audio = Path(d) / "audio" / "track.wav"
            _touch(sibling_audio)
            (base / "projects").mkdir(parents=True)
            (base / "library").mkdir(parents=True)

            os.environ["TRACK_COACH_ROOT"] = str(base)
            try:
                args = types.SimpleNamespace(base=None, yes_wipe_everything=True)
                library._cmd_reset(args)
                self.assertTrue(sibling_audio.exists(),
                                "reset must NOT delete files outside the output root (G-INV-7)")
            finally:
                os.environ.pop("TRACK_COACH_ROOT", None)

    def test_base_flag_overrides_root(self):
        """--base lets the user specify a custom output root for reset."""
        with tempfile.TemporaryDirectory() as d:
            custom_base = Path(d) / "custom"
            (custom_base / "projects").mkdir(parents=True)
            (custom_base / "library").mkdir(parents=True)

            args = types.SimpleNamespace(base=str(custom_base), yes_wipe_everything=True)
            library._cmd_reset(args)
            self.assertFalse((custom_base / "projects").exists())
            self.assertFalse((custom_base / "library").exists())


# ─── 2. gc — orphan prune (H-INV-3) ──────────────────────────────────────────

class GcPlan(unittest.TestCase):
    """gc_plan: pure classification logic. H-INV-3 / G-INV-10 / G-INV-15."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.base = Path(self._tmp) / "output"
        self.projects = self.base / "projects"
        self.lib_root = self.base / "library"
        self.lib_root.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _setup(self):
        slug_dir = self.projects / "track_a"
        # referenced run (1 result file, will be in library index)
        run_ref = _make_run(slug_dir, "2026-01-01_1000", n_results=1)
        # best undeposited run (2 result files, not in library)
        run_best = _make_run(slug_dir, "2026-01-02_1000", n_results=2)
        # orphan run (0 result files, not in library, not best)
        run_orphan = _make_run(slug_dir, "2026-01-03_1000", n_results=0)
        # Library index references only run_ref
        idx = {"entries": [{"track": "track_a", "stamp": "s1",
                            "widget": "w.html", "src_run_dir": str(run_ref)}]}
        library.save_index(self.lib_root, idx)
        return run_ref, run_best, run_orphan

    def test_orphan_classified_correctly(self):
        """gc_plan puts the orphan run in 'orphan', the referenced in keep_referenced,
        and the best undeposited in keep_best. H-INV-3."""
        run_ref, run_best, run_orphan = self._setup()
        plan = library.gc_plan(self.projects, self.lib_root)

        # Resolve paths for reliable comparison on macOS (/var vs /private/var)
        orphan_res = {str(p.resolve()) for p in plan["orphan"]}
        ref_res = {str(p.resolve()) for p in plan["keep_referenced"]}
        best_res = {str(p.resolve()) for p in plan["keep_best"]}

        self.assertIn(str(run_orphan.resolve()), orphan_res,
                      "orphan run must appear in plan['orphan']")
        self.assertIn(str(run_ref.resolve()), ref_res,
                      "referenced run must appear in plan['keep_referenced']")
        self.assertIn(str(run_best.resolve()), best_res,
                      "best undeposited run must appear in plan['keep_best']")
        self.assertEqual(len(plan["orphan"]), 1,
                         "exactly one orphan run expected")

    def test_empty_projects_dir_returns_empty_plan(self):
        """gc_plan on a missing projects dir returns empty lists."""
        plan = library.gc_plan(self.projects, self.lib_root)
        self.assertEqual(plan["orphan"], [])
        self.assertEqual(plan["keep_referenced"], [])
        self.assertEqual(plan["keep_best"], [])


class GcCommand(unittest.TestCase):
    """_cmd_gc: dry-run lists orphan; --apply deletes only orphan. H-INV-3."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.base = Path(self._tmp) / "output"
        self.projects = self.base / "projects"
        self.lib_root = self.base / "library"
        self.lib_root.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("TRACK_COACH_ROOT", None)
        os.environ.pop("TRACK_COACH_LIBRARY", None)

    def _setup(self):
        slug_dir = self.projects / "track_a"
        run_ref = _make_run(slug_dir, "2026-01-01_1000", n_results=1)
        run_best = _make_run(slug_dir, "2026-01-02_1000", n_results=2)
        run_orphan = _make_run(slug_dir, "2026-01-03_1000", n_results=0)
        idx = {"entries": [{"track": "track_a", "stamp": "s1",
                            "widget": "w.html", "src_run_dir": str(run_ref)}]}
        library.save_index(self.lib_root, idx)
        os.environ["TRACK_COACH_ROOT"] = str(self.base)
        os.environ["TRACK_COACH_LIBRARY"] = str(self.lib_root)
        return run_ref, run_best, run_orphan

    def test_dry_run_removes_nothing(self):
        """gc without --apply must not delete any files. H-INV-3."""
        run_ref, run_best, run_orphan = self._setup()
        args = types.SimpleNamespace(base=None, apply=False,
                                     ableton_tails=False, scan_dir=None)
        library._cmd_gc(args)
        self.assertTrue(run_orphan.exists(), "dry-run must not delete orphan")
        self.assertTrue(run_ref.exists(), "dry-run must not delete referenced run")
        self.assertTrue(run_best.exists(), "dry-run must not delete best run")

    def test_apply_deletes_only_orphan(self):
        """gc --apply must delete orphaned runs and keep referenced + best. H-INV-3."""
        run_ref, run_best, run_orphan = self._setup()
        args = types.SimpleNamespace(base=None, apply=True,
                                     ableton_tails=False, scan_dir=None)
        library._cmd_gc(args)
        self.assertFalse(run_orphan.exists(),
                         "gc --apply must remove orphaned run dir")
        self.assertTrue(run_ref.exists(),
                        "gc --apply must keep referenced run (G-INV-10)")
        self.assertTrue(run_best.exists(),
                        "gc --apply must keep best-undeposited run (G-INV-15)")


# ─── 3. Ableton-tail sweep (H-INV-5) ──────────────────────────────────────────

class AbletonTailScan(unittest.TestCase):
    """ableton_tail_scan: classifies slug dirs within tco/ folders. H-INV-5."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _make_tco(self) -> tuple:
        """Build a fake track-coach-output/ with one safe and one unsafe slug dir."""
        d = Path(self._tmp)
        tco = d / "ableton" / "track-coach-output"

        # (a) safe slug: only dangling `latest` symlink + index.json
        slug_a = tco / "slug_a"
        slug_a.mkdir(parents=True)
        (slug_a / "index.json").write_text("{}")
        (slug_a / "latest").symlink_to("2026-01-01_1000")  # dangling — target absent

        # (b) unsafe slug: contains a real run subdir with result files
        slug_b = tco / "slug_b"
        run_b = slug_b / "2026-01-01_1000"
        run_b.mkdir(parents=True)
        (run_b / "result_masking.json").write_text("{}")

        return tco, slug_a, slug_b, run_b

    def test_dry_run_reports_safe_and_real_correctly(self):
        """ableton_tail_scan must classify (a) safe and (b) has-real-runs. H-INV-5."""
        tco, slug_a, slug_b, run_b = self._make_tco()
        scan = library.ableton_tail_scan([tco])

        safe_slugs = {str(s.resolve()) for _, s in scan["safe"]}
        real_slugs = {str(s.resolve()) for _, s in scan["real_runs"]}

        self.assertIn(str(slug_a.resolve()), safe_slugs,
                      "dangling-only slug_a must be classified 'safe'")
        self.assertIn(str(slug_b.resolve()), real_slugs,
                      "slug_b with real run must be classified 'real_runs'")
        self.assertEqual(scan["missing"], [],
                         "no missing tco dirs expected")

    def test_apply_removes_only_safe_leaves_real_runs(self):
        """Removing safe slug dirs must leave the 'real_runs' slug dirs intact. H-INV-5."""
        tco, slug_a, slug_b, run_b = self._make_tco()
        scan = library.ableton_tail_scan([tco])

        # Simulate --apply: remove only safe dirs
        for _, slug in scan["safe"]:
            shutil.rmtree(slug)

        self.assertFalse(slug_a.exists(),
                         "safe slug_a must be removed by --apply")
        self.assertTrue(slug_b.exists(),
                        "slug_b with real runs must NOT be removed (H-INV-5)")
        self.assertTrue(run_b.exists(),
                        "real run dir inside slug_b must survive")

    def test_missing_tco_dir_reported_as_missing(self):
        """A non-existent tco_dir must appear in scan['missing'], not crash. H-INV-5."""
        ghost = Path(self._tmp) / "no_such_tco"
        scan = library.ableton_tail_scan([ghost])
        self.assertIn(ghost, scan["missing"])
        self.assertEqual(scan["safe"], [])
        self.assertEqual(scan["real_runs"], [])

    def test_slug_dir_has_real_runs_positive(self):
        """_slug_dir_has_real_runs returns True when a non-symlink subdir exists."""
        d = Path(self._tmp)
        slug = d / "slug"
        run = slug / "2026-01-01_1000"
        run.mkdir(parents=True)
        self.assertTrue(library._slug_dir_has_real_runs(slug))

    def test_slug_dir_has_real_runs_negative_dangling_symlink(self):
        """_slug_dir_has_real_runs returns False for dangling-symlink-only slug dir."""
        d = Path(self._tmp)
        slug = d / "slug"
        slug.mkdir(parents=True)
        (slug / "index.json").write_text("{}")
        (slug / "latest").symlink_to("nonexistent")  # dangling
        self.assertFalse(library._slug_dir_has_real_runs(slug))


class GcAbletonTailsCommand(unittest.TestCase):
    """_cmd_gc --ableton-tails: dry-run reports; --apply removes only safe dirs. H-INV-5."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("TRACK_COACH_ROOT", None)
        os.environ.pop("TRACK_COACH_LIBRARY", None)

    def test_dry_run_does_not_remove(self):
        d = Path(self._tmp)
        tco = d / "ableton" / "track-coach-output"
        slug_a = tco / "slug_a"
        slug_a.mkdir(parents=True)
        (slug_a / "latest").symlink_to("nonexistent")

        args = types.SimpleNamespace(base=None, apply=False,
                                     ableton_tails=True, scan_dir=str(tco))
        library._cmd_gc(args)
        self.assertTrue(slug_a.exists(), "dry-run must not remove slug dir")

    def test_apply_removes_safe_dirs(self):
        d = Path(self._tmp)
        tco = d / "ableton" / "track-coach-output"
        # safe slug
        slug_a = tco / "slug_a"
        slug_a.mkdir(parents=True)
        (slug_a / "latest").symlink_to("nonexistent")
        # unsafe slug
        slug_b = tco / "slug_b"
        run_b = slug_b / "2026-01-01_1000"
        run_b.mkdir(parents=True)
        (run_b / "result_masking.json").write_text("{}")

        args = types.SimpleNamespace(base=None, apply=True,
                                     ableton_tails=True, scan_dir=str(tco))
        library._cmd_gc(args)

        self.assertFalse(slug_a.exists(), "safe slug must be removed by --apply")
        self.assertTrue(slug_b.exists(), "unsafe slug must NOT be removed (H-INV-5)")
        self.assertTrue(run_b.exists(), "real run inside slug_b must survive")


# ─── 4. remove — prune track/version from library (H-INV-2) ──────────────────

class RemovePlan(unittest.TestCase):
    """Pure tests for remove_plan. H-INV-2."""

    def _entries(self):
        return [
            {"track": "A", "stamp": "s1", "version": "v1", "widget": "A__v1__s1.html"},
            {"track": "A", "stamp": "s2", "version": "v2", "widget": "A__v2__s2.html"},
            {"track": "B", "stamp": "s3", "version": "v1", "widget": "B__v1__s3.html"},
        ]

    def test_remove_whole_track(self):
        """remove_plan with version=None removes all entries for that track. H-INV-2."""
        keep, rm = library.remove_plan(self._entries(), "A")
        self.assertEqual([e["track"] for e in keep], ["B"],
                         "only B should remain after removing A")
        self.assertEqual(len(rm), 2, "both A entries must be in to_remove")
        self.assertTrue(all(e["track"] == "A" for e in rm))

    def test_remove_one_version_by_stamp(self):
        """remove_plan by stamp removes exactly one entry, leaves other A + B. H-INV-2."""
        keep, rm = library.remove_plan(self._entries(), "A", version="s1")
        self.assertEqual(len(rm), 1)
        self.assertEqual(rm[0]["stamp"], "s1")
        keep_tracks = {e["track"] for e in keep}
        self.assertIn("A", keep_tracks, "A's other version must remain")
        self.assertIn("B", keep_tracks, "B must remain untouched")

    def test_remove_one_version_by_version_label(self):
        """remove_plan matches the 'version' field as well as 'stamp'. H-INV-2."""
        keep, rm = library.remove_plan(self._entries(), "A", version="v2")
        self.assertEqual(len(rm), 1)
        self.assertEqual(rm[0]["stamp"], "s2")

    def test_other_tracks_untouched(self):
        """Removing A must leave B's entries completely intact. H-INV-2."""
        keep, rm = library.remove_plan(self._entries(), "A")
        b_entries = [e for e in keep if e["track"] == "B"]
        self.assertEqual(len(b_entries), 1)

    def test_no_match_returns_empty_remove(self):
        """remove_plan returns empty to_remove when track doesn't exist."""
        keep, rm = library.remove_plan(self._entries(), "NoSuchTrack")
        self.assertEqual(rm, [])
        self.assertEqual(len(keep), len(self._entries()))


class RemoveCommand(unittest.TestCase):
    """_cmd_remove: assert against real FS + index. H-INV-2."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("TRACK_COACH_LIBRARY", None)

    def _make_lib(self):
        entries = [
            {"track": "TrackA", "stamp": "s1", "version": "v1",
             "widget": "TrackA__v1__s1.html", "mode": "full"},
            {"track": "TrackA", "stamp": "s2", "version": "v2",
             "widget": "TrackA__v2__s2.html", "mode": "full"},
            {"track": "TrackB", "stamp": "s3", "version": "v1",
             "widget": "TrackB__v1__s3.html", "mode": "full"},
        ]
        lib_root, wdir = _make_library(Path(self._tmp), entries)
        os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
        return lib_root, wdir

    def test_dry_run_removes_nothing(self):
        """remove without --apply must not delete any widget or index entry. H-INV-2."""
        lib_root, wdir = self._make_lib()
        args = types.SimpleNamespace(track="TrackA", version=None, apply=False)
        library._cmd_remove(args)
        # widgets unchanged
        self.assertTrue((wdir / "TrackA__v1__s1.html").exists())
        self.assertTrue((wdir / "TrackA__v2__s2.html").exists())
        # index unchanged
        idx = library.load_index(lib_root)
        self.assertEqual(len(idx["entries"]), 3,
                         "dry-run must not modify the index")

    def test_remove_one_version_leaves_others_and_updates_index(self):
        """remove one version → correct widget deleted, other versions + TrackB intact. H-INV-2."""
        lib_root, wdir = self._make_lib()
        args = types.SimpleNamespace(track="TrackA", version="s1", apply=True)
        library._cmd_remove(args)
        # Removed widget gone
        self.assertFalse((wdir / "TrackA__v1__s1.html").exists(),
                         "widget for removed version must be deleted")
        # Other versions intact
        self.assertTrue((wdir / "TrackA__v2__s2.html").exists(),
                        "TrackA v2 widget must remain")
        self.assertTrue((wdir / "TrackB__v1__s3.html").exists(),
                        "TrackB widget must remain untouched")
        # Index updated atomically (G-INV-11)
        idx = library.load_index(lib_root)
        self.assertEqual(len(idx["entries"]), 2)
        remaining = {(e["track"], e.get("stamp")) for e in idx["entries"]}
        self.assertIn(("TrackA", "s2"), remaining)
        self.assertIn(("TrackB", "s3"), remaining)

    def test_remove_whole_track(self):
        """remove all versions of TrackA → both widgets gone, TrackB intact. H-INV-2."""
        lib_root, wdir = self._make_lib()
        args = types.SimpleNamespace(track="TrackA", version=None, apply=True)
        library._cmd_remove(args)
        self.assertFalse((wdir / "TrackA__v1__s1.html").exists())
        self.assertFalse((wdir / "TrackA__v2__s2.html").exists())
        self.assertTrue((wdir / "TrackB__v1__s3.html").exists())
        idx = library.load_index(lib_root)
        self.assertEqual(len(idx["entries"]), 1)
        self.assertEqual(idx["entries"][0]["track"], "TrackB")

    def test_remove_does_not_delete_run_dir(self):
        """remove only deletes the library widget copy, NOT the src_run_dir. H-INV-2 / ⟨H-2⟩."""
        lib_root, wdir = self._make_lib()
        # Give one entry a fake src_run_dir
        run_dir = Path(self._tmp) / "projects" / "TrackA" / "s1"
        run_dir.mkdir(parents=True)
        (run_dir / "result_core.json").write_text("{}")
        # Update index to reference it
        idx = library.load_index(lib_root)
        for e in idx["entries"]:
            if e.get("stamp") == "s1":
                e["src_run_dir"] = str(run_dir)
        library.save_index(lib_root, idx)

        args = types.SimpleNamespace(track="TrackA", version="s1", apply=True)
        library._cmd_remove(args)

        self.assertTrue(run_dir.exists(),
                        "remove must NOT delete the backing run dir (H-INV-2 / ⟨H-2⟩)")


# ─── 5. prune-versions (H-INV-4) ──────────────────────────────────────────────

class PruneVersionsPlan(unittest.TestCase):
    """Pure tests for prune_versions_plan. H-INV-4."""

    def _entries(self):
        """3 distinct versions (different audio_sha) of track T, oldest to newest."""
        return [
            {"track": "T", "stamp": "2026-01-01", "widget": "T__v1.html",
             "audio_sha": "sha_v1", "deposited_at": "2026-01-01T00:00:00+00:00"},
            {"track": "T", "stamp": "2026-02-01", "widget": "T__v2.html",
             "audio_sha": "sha_v2", "deposited_at": "2026-02-01T00:00:00+00:00"},
            {"track": "T", "stamp": "2026-03-01", "widget": "T__v3.html",
             "audio_sha": "sha_v3", "deposited_at": "2026-03-01T00:00:00+00:00"},
        ]

    def test_keep_1_drops_two_oldest(self):
        """keep_n=1 → newest version kept, two older dropped. H-INV-4."""
        keep, drop = library.prune_versions_plan(self._entries(), 1)
        self.assertEqual(len(keep), 1, "keep_n=1 must leave exactly 1 entry")
        self.assertEqual(len(drop), 2, "keep_n=1 must drop 2 entries")
        self.assertEqual(keep[0]["audio_sha"], "sha_v3",
                         "newest version (sha_v3) must be kept")
        dropped_shas = {e["audio_sha"] for e in drop}
        self.assertIn("sha_v1", dropped_shas, "sha_v1 must be dropped")
        self.assertIn("sha_v2", dropped_shas, "sha_v2 must be dropped")

    def test_keep_2_drops_oldest_only(self):
        """keep_n=2 → two newest kept, only oldest dropped. H-INV-4."""
        keep, drop = library.prune_versions_plan(self._entries(), 2)
        self.assertEqual(len(keep), 2)
        self.assertEqual(len(drop), 1)
        self.assertEqual(drop[0]["audio_sha"], "sha_v1",
                         "only oldest version (sha_v1) must be dropped")

    def test_keep_n_ge_count_drops_nothing(self):
        """keep_n >= number of versions → nothing dropped. H-INV-4."""
        keep, drop = library.prune_versions_plan(self._entries(), 3)
        self.assertEqual(drop, [], "keep_n=3 with 3 versions must drop nothing")
        keep, drop = library.prune_versions_plan(self._entries(), 10)
        self.assertEqual(drop, [], "keep_n=10 with 3 versions must drop nothing")

    def test_negative_keep_raises(self):
        """prune_versions_plan must raise ValueError for negative keep_n. H-INV-4."""
        with self.assertRaises(ValueError):
            library.prune_versions_plan(self._entries(), -1)

    def test_other_tracks_handled_independently(self):
        """Each track's versions are pruned independently. H-INV-4."""
        entries = self._entries() + [
            {"track": "Other", "stamp": "2026-01-01", "widget": "O__v1.html",
             "audio_sha": "sha_o1", "deposited_at": "2026-01-01T00:00:00+00:00"},
            {"track": "Other", "stamp": "2026-04-01", "widget": "O__v2.html",
             "audio_sha": "sha_o2", "deposited_at": "2026-04-01T00:00:00+00:00"},
        ]
        keep, drop = library.prune_versions_plan(entries, 1)
        kept_by_track: dict = {}
        for e in keep:
            kept_by_track.setdefault(e["track"], []).append(e["audio_sha"])
        # T: only newest sha_v3 kept
        self.assertEqual(kept_by_track.get("T"), ["sha_v3"])
        # Other: only newest sha_o2 kept
        self.assertEqual(kept_by_track.get("Other"), ["sha_o2"])

    def test_same_sha_entries_are_dropped_together(self):
        """All entries sharing the same audio_sha are treated as one version. H-INV-4."""
        # Two entries with same sha (two runs of same audio)
        entries = [
            {"track": "T", "stamp": "2026-01-01", "widget": "T__r1.html",
             "audio_sha": "sha_v1", "deposited_at": "2026-01-01T00:00:00+00:00"},
            {"track": "T", "stamp": "2026-01-02", "widget": "T__r2.html",
             "audio_sha": "sha_v1", "deposited_at": "2026-01-02T00:00:00+00:00"},  # same sha
            {"track": "T", "stamp": "2026-03-01", "widget": "T__v3.html",
             "audio_sha": "sha_v3", "deposited_at": "2026-03-01T00:00:00+00:00"},
        ]
        keep, drop = library.prune_versions_plan(entries, 1)
        # sha_v1 group has 2 entries — both dropped together
        dropped_shas = {e["audio_sha"] for e in drop}
        self.assertIn("sha_v1", dropped_shas, "sha_v1 group must be dropped together")
        self.assertEqual(len(drop), 2, "both sha_v1 entries must be dropped")


class PruneVersionsCommand(unittest.TestCase):
    """_cmd_prune_versions: assert against real FS + index. H-INV-4."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("TRACK_COACH_LIBRARY", None)

    def _make_lib(self):
        entries = [
            {"track": "T", "stamp": "2026-01-01", "widget": "T__v1.html",
             "audio_sha": "sha_v1", "deposited_at": "2026-01-01T00:00:00+00:00"},
            {"track": "T", "stamp": "2026-02-01", "widget": "T__v2.html",
             "audio_sha": "sha_v2", "deposited_at": "2026-02-01T00:00:00+00:00"},
            {"track": "T", "stamp": "2026-03-01", "widget": "T__v3.html",
             "audio_sha": "sha_v3", "deposited_at": "2026-03-01T00:00:00+00:00"},
        ]
        lib_root, wdir = _make_library(Path(self._tmp), entries)
        os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
        return lib_root, wdir

    def test_dry_run_removes_nothing(self):
        """prune-versions without --apply must not delete any widget or index entry. H-INV-4."""
        lib_root, wdir = self._make_lib()
        args = types.SimpleNamespace(keep=1, apply=False)
        library._cmd_prune_versions(args)
        # All widgets still present
        for fname in ("T__v1.html", "T__v2.html", "T__v3.html"):
            self.assertTrue((wdir / fname).exists(),
                            f"dry-run must not delete {fname}")
        idx = library.load_index(lib_root)
        self.assertEqual(len(idx["entries"]), 3,
                         "dry-run must not modify the index")

    def test_apply_keeps_only_newest(self):
        """prune-versions --keep 1 --apply → only newest widget + index entry remain. H-INV-4."""
        lib_root, wdir = self._make_lib()
        args = types.SimpleNamespace(keep=1, apply=True)
        library._cmd_prune_versions(args)
        # Newest version widget survives
        self.assertTrue((wdir / "T__v3.html").exists(),
                        "newest widget must survive")
        # Older widgets deleted
        self.assertFalse((wdir / "T__v1.html").exists(),
                         "v1 widget must be deleted")
        self.assertFalse((wdir / "T__v2.html").exists(),
                         "v2 widget must be deleted")
        # Index has exactly 1 entry
        idx = library.load_index(lib_root)
        self.assertEqual(len(idx["entries"]), 1,
                         "index must have exactly 1 entry after prune --keep 1")
        self.assertEqual(idx["entries"][0]["audio_sha"], "sha_v3",
                         "remaining entry must be newest version (sha_v3)")

    def test_no_keep_flag_does_nothing(self):
        """With no --keep arg, prune-versions shows versions and makes no changes. H-INV-4."""
        lib_root, wdir = self._make_lib()
        args = types.SimpleNamespace(keep=None, apply=False)
        library._cmd_prune_versions(args)
        idx = library.load_index(lib_root)
        self.assertEqual(len(idx["entries"]), 3,
                         "omitting --keep must leave the library untouched (H-INV-4 no silent default)")

    def test_apply_does_not_delete_run_dirs(self):
        """prune-versions only removes library entries + widgets; run dirs stay. H-INV-4."""
        lib_root, wdir = self._make_lib()
        # Give oldest entry a fake run dir
        run_dir = Path(self._tmp) / "projects" / "T" / "run_v1"
        run_dir.mkdir(parents=True)
        (run_dir / "result_core.json").write_text("{}")
        idx = library.load_index(lib_root)
        for e in idx["entries"]:
            if e.get("audio_sha") == "sha_v1":
                e["src_run_dir"] = str(run_dir)
        library.save_index(lib_root, idx)

        args = types.SimpleNamespace(keep=1, apply=True)
        library._cmd_prune_versions(args)

        self.assertTrue(run_dir.exists(),
                        "prune-versions must NOT delete backing run dirs (H-INV-4)")


if __name__ == "__main__":
    unittest.main()
