#!/usr/bin/env python3
"""Global-library tests — naming, the clean policy, and a deposit round-trip.

`clean_plan` deletes files, so its policy is a PURE function tested exhaustively here (no FS).
`deposit` is exercised against a temp library root via $TRACK_COACH_LIBRARY.
"""
import json, os, sys, tempfile, types, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import library  # noqa: E402

NOW = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)


def E(track, stamp, days_old=0, widget=None):
    return {"track": track, "stamp": stamp,
            "deposited_at": (NOW - timedelta(days=days_old)).isoformat(),
            "widget": widget or f"{track}__v0__{stamp}.html"}


class Naming(unittest.TestCase):
    def test_canonical_name_shape(self):
        self.assertEqual(library.canonical_widget_name("Foo", "v1", "2026-06-18_0748"),
                         "Foo__v1__2026-06-18_0748.html")

    def test_sanitize_spaces_and_brackets(self):
        n = library.canonical_widget_name("Total Reboot [2026]", "", "a b")
        self.assertNotIn(" ", n)
        self.assertNotIn("[", n)
        self.assertTrue(n.endswith(".html"))

    def test_upsert_replaces_same_widget(self):
        es = [{"widget": "a.html", "verdict": "old"}]
        es = library.upsert(es, {"widget": "a.html", "verdict": "new"})
        self.assertEqual(len(es), 1)
        self.assertEqual(es[0]["verdict"], "new")


class CleanPolicy(unittest.TestCase):
    def test_all_within_track_scope_only(self):
        es = [E("A", "s1"), E("B", "s2")]
        keep, rm = library.clean_plan(es, all_=True, track="A", now=NOW)
        self.assertEqual([e["track"] for e in rm], ["A"])
        self.assertEqual([e["track"] for e in keep], ["B"])

    def test_older_than(self):
        es = [E("A", "old", days_old=40), E("A", "new", days_old=2)]
        keep, rm = library.clean_plan(es, older_than_days=30, now=NOW)
        self.assertEqual([e["stamp"] for e in rm], ["old"])
        self.assertEqual([e["stamp"] for e in keep], ["new"])

    def test_keep_per_track_keeps_newest_n(self):
        es = [E("A", "2026-01"), E("A", "2026-03"), E("A", "2026-02"), E("B", "x")]
        keep, rm = library.clean_plan(es, keep_per_track=2, now=NOW)
        kept = sorted(e["stamp"] for e in keep if e["track"] == "A")
        self.assertEqual(kept, ["2026-02", "2026-03"])      # newest two
        self.assertEqual([e["stamp"] for e in rm], ["2026-01"])

    def test_missing_uses_exists_predicate(self):
        es = [E("A", "here"), E("A", "gone")]
        present = {"A__v0__here.html"}
        keep, rm = library.clean_plan(es, missing=True, exists=lambda e: e["widget"] in present, now=NOW)
        self.assertEqual([e["stamp"] for e in rm], ["gone"])

    def test_no_filter_removes_nothing(self):
        es = [E("A", "s1"), E("B", "s2")]
        keep, rm = library.clean_plan(es, now=NOW)
        self.assertEqual(rm, [])
        self.assertEqual(len(keep), 2)


class DepositRoundTrip(unittest.TestCase):
    def test_deposit_copies_widget_and_indexes_it(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget_v0.6.4.html"; w.write_text("<html>widget</html>")
                meta = {"track": "Total_Reboot_X", "track_version": "", "mode": "full",
                        "verdict": "v"}
                entry = library.deposit_from_run(run, w, meta)
                root = library.library_root()
                self.assertTrue((root / "widgets" / entry["widget"]).exists())
                idx = json.loads((root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 1)
                self.assertEqual(idx["entries"][0]["track"], "Total_Reboot_X")
                # re-deposit same run → upsert, not duplicate
                library.deposit_from_run(run, w, meta)
                idx = json.loads((root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 1)
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class StoresBuildVersion(unittest.TestCase):
    """INV-12 option-b / KI-7: the build's TC_VERSION is recorded in the index entry at deposit time
    (read from the widget's embedded payload), so the stale check no longer depends on the filename —
    closing the hole where a versionless/musical-versioned filename slipped through unflagged."""

    def test_version_from_widget_reads_the_embedded_payload(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d) / "analysis_widget.html"  # NB: no version in the name
            w.write_text('<script>const D={"mode":"full","version":"0.4.2","meta":{}};</script>')
            self.assertEqual(library.version_from_widget(w), "0.4.2")
            w.write_text("<html>no payload</html>")
            self.assertIsNone(library.version_from_widget(w))

    def test_deposit_records_tc_version_even_with_a_versionless_filename(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget.html"  # versionless name → must come from the payload
                w.write_text('<script>const D={"version":"0.7.6","meta":{}};</script>')
                entry = library.deposit_from_run(run, w, {"track": "T", "mode": "full"})
                self.assertEqual(entry.get("tc_version"), "0.7.6")
                idx = json.loads((library.library_root() / "index.json").read_text())
                self.assertEqual(idx["entries"][0].get("tc_version"), "0.7.6")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_analysis_version_from_widget_reads_the_embedded_payload(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d) / "analysis_widget.html"
            w.write_text('<script>const D={"version":"1.4.1","analysis_version":3,"meta":{}};</script>')
            self.assertEqual(library.analysis_version_from_widget(w), 3)
            w.write_text('<script>const D={"version":"1.4.1","meta":{}};</script>')  # pre-stamping widget
            self.assertIsNone(library.analysis_version_from_widget(w))

    def test_deposit_records_the_analysis_version(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget.html"
                w.write_text('<script>const D={"version":"1.4.1","analysis_version":1,"meta":{}};</script>')
                entry = library.deposit_from_run(run, w, {"track": "T", "mode": "full"})
                self.assertEqual(entry.get("tc_analysis_version"), 1)
                idx = json.loads((library.library_root() / "index.json").read_text())
                self.assertEqual(idx["entries"][0].get("tc_analysis_version"), 1)
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class DepositAtomicity(unittest.TestCase):
    """INV-15 / KI-6: a deposit either targets the run's real track slug or ABORTS without writing a
    partial/junk entry. The KI-1 saga: a build off a run dir one level too shallow resolved the track
    to `track-coach-output` and left a junk row + a half-failed catalog regen. Guard it BEFORE any
    write so a malformed run dir leaves the library untouched."""

    def test_slug_sentinel_is_pure_and_catches_the_junk_shapes(self):
        for bad in ("", "track-coach-output", "Total_Reboot-output", "2026-06-18_0748"):
            self.assertTrue(library.looks_like_output_sentinel(bad), f"{bad!r} should be rejected")
        for ok in ("Total_Reboot_Fragile", "Shared Memories", "run"):
            self.assertFalse(library.looks_like_output_sentinel(ok), f"{ok!r} is a real track")

    def test_malformed_run_dir_aborts_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                # run dir one level too shallow: parent is the output root, no meta.track → junk slug
                base = Path(d) / "track-coach-output"; base.mkdir()
                run = base / "2026-06-18_0748"; run.mkdir()
                w = run / "analysis_widget_v0.7.6.html"; w.write_text("<html>w</html>")
                with self.assertRaises(library.DepositError):
                    library.deposit_from_run(run, w, {"mode": "full"})  # no track → parent.name="track-coach-output"
                root = library.library_root()
                self.assertFalse((root / "index.json").exists(), "no index written on a refused deposit")
                self.assertFalse((root / "widgets").exists(), "no widget copied on a refused deposit")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class LegacyStrInLibraryEntries(unittest.TestCase):
    """Regression: 'str' object has no attribute 'get' when a library index.json entry is a bare
    string (a legacy slug written by old run-init code before the full-metadata format).
    upsert() and load_index() must both tolerate stray string entries — normalize, don't crash.
    Bug surface: library.py:upsert (same unguarded .get() pattern as build_widget._record_history
    that triggered the Wobble history-update-skipped log)."""

    def test_upsert_with_legacy_str_entry_does_not_crash(self):
        """upsert() must not raise when entries contains a stray string slug (pre-metadata format).
        This is the RED-on-bug test: before the isinstance guard it raised
        AttributeError: 'str' object has no attribute 'get'."""
        entries = ["Total_Reboot_Wobble_Drift_v0.6.2",        # stray legacy string
                   {"widget": "real.html", "track": "WD"}]
        result = library.upsert(entries, {"widget": "new.html", "track": "WD"})
        widgets = [e.get("widget") for e in result if isinstance(e, dict)]
        self.assertIn("real.html", widgets)    # existing real entry kept
        self.assertIn("new.html", widgets)     # new entry appended

    def test_load_index_normalizes_str_entries_to_dicts(self):
        """load_index() must coerce any stray string in 'entries' to a minimal dict so
        every downstream caller (upsert, clean_plan, group_versions) sees a uniform type."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            raw = {"entries": ["stray_slug",
                               {"widget": "real.html", "track": "T", "stamp": "s1"}]}
            (root / "index.json").write_text(json.dumps(raw))
            idx = library.load_index(root)
            # All items must be dicts after normalization
            self.assertTrue(all(isinstance(e, dict) for e in idx["entries"]),
                            "load_index must normalize every entry to a dict")
            self.assertEqual(len(idx["entries"]), 2)
            # The normalized stray string is preserved as {"widget": "stray_slug"}
            self.assertEqual(idx["entries"][0].get("widget"), "stray_slug")
            # The real entry is unchanged
            self.assertEqual(idx["entries"][1]["track"], "T")

    def test_deposit_into_index_with_legacy_str_entry_succeeds(self):
        """Full deposit round-trip: even when the library index.json already holds a stray string
        entry, deposit() must succeed and produce a clean index (all dicts)."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                root = library.library_root()
                root.mkdir(parents=True)
                # Seed the index with a stray string entry (simulates the legacy format)
                (root / "index.json").write_text(
                    json.dumps({"entries": ["Total_Reboot_Wobble_Drift_v0.6.2"]}))
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget.html"; w.write_text("<html>widget</html>")
                # Before fix: deposit → upsert → 'str'.get() → AttributeError
                entry = library.deposit_from_run(run, w, {"track": "WD", "mode": "full"})
                idx = json.loads((root / "index.json").read_text())
                self.assertTrue(all(isinstance(e, dict) for e in idx["entries"]),
                                "all index entries must be dicts after deposit")
                self.assertEqual(entry["track"], "WD")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class CleanCommandConvention(unittest.TestCase):
    """Integration tests for the `clean` command H-INV-12 confirmation convention.

    Dry-run is the default; --apply (or back-compat --yes) is required to act.
    Bare `clean --all` must preview (not error). All asserted against real FS state.
    """

    def _make_lib(self, tmp, entries):
        """Create a minimal library under tmp with the given entries + widget files."""
        import types
        lib_root = Path(tmp) / "library"
        wdir = lib_root / "widgets"
        wdir.mkdir(parents=True)
        for e in entries:
            (wdir / e["widget"]).write_text("<html>widget</html>")
        library.save_index(lib_root, {"entries": entries})
        return lib_root

    def _args(self, **kwargs):
        import types
        defaults = dict(all=False, older_than=None, keep_per_track=None,
                        track=None, missing=False, apply=False, yes=False, dry_run=False)
        defaults.update(kwargs)
        # argparse stores --older-than as older_than (underscored)
        ns = types.SimpleNamespace(**defaults)
        return ns

    def test_dry_run_by_default_older_than(self):
        """bare clean --older-than N (no act flag) previews only; index unchanged. H-INV-12."""
        with tempfile.TemporaryDirectory() as d:
            entries = [E("A", "old", days_old=40), E("A", "new", days_old=2)]
            lib_root = self._make_lib(d, entries)
            os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
            try:
                args = self._args(older_than=30)
                library._cmd_clean(args)
                # index must still have both entries (dry-run changed nothing)
                idx = json.loads((lib_root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 2, "dry-run must not remove index entries")
                # both widget files must still exist
                self.assertTrue((lib_root / "widgets" / entries[0]["widget"]).exists())
                self.assertTrue((lib_root / "widgets" / entries[1]["widget"]).exists())
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_apply_flag_actually_removes(self):
        """clean --older-than N --apply removes the old entry and its widget. H-INV-12."""
        with tempfile.TemporaryDirectory() as d:
            entries = [E("A", "old", days_old=40), E("A", "new", days_old=2)]
            lib_root = self._make_lib(d, entries)
            os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
            try:
                args = self._args(older_than=30, apply=True)
                library._cmd_clean(args)
                idx = json.loads((lib_root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 1, "--apply must reduce index to 1 entry")
                stamps = [e.get("stamp") for e in idx["entries"]]
                self.assertIn("new", stamps, "the newer entry must survive")
                self.assertNotIn("old", stamps, "the old entry must be removed")
                # widget file for the removed entry must be gone
                self.assertFalse((lib_root / "widgets" / entries[0]["widget"]).exists(),
                                 "--apply must delete the widget file")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_yes_flag_back_compat_still_removes(self):
        """clean --older-than N --yes (legacy alias) removes, same as --apply. H-INV-12."""
        with tempfile.TemporaryDirectory() as d:
            entries = [E("A", "old", days_old=40), E("A", "new", days_old=2)]
            lib_root = self._make_lib(d, entries)
            os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
            try:
                args = self._args(older_than=30, yes=True)
                library._cmd_clean(args)
                idx = json.loads((lib_root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 1, "--yes alias must remove like --apply")
                stamps = [e.get("stamp") for e in idx["entries"]]
                self.assertIn("new", stamps)
                self.assertNotIn("old", stamps)
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_bare_all_previews_not_errors(self):
        """bare clean --all (no act flag) must preview without raising SystemExit. H-INV-12."""
        with tempfile.TemporaryDirectory() as d:
            entries = [E("A", "s1"), E("B", "s2")]
            lib_root = self._make_lib(d, entries)
            os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
            try:
                args = self._args(all=True)
                # must not raise SystemExit (the old code did sys.exit without --yes)
                library._cmd_clean(args)
                # dry-run: index still has both entries
                idx = json.loads((lib_root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 2,
                                 "bare --all must preview, not remove entries")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class ReferenceNotDeposited(unittest.TestCase):
    """G-INV-18: a run with reference:true in run_meta is refused by deposit_from_run."""

    def test_reference_run_refused(self):
        """deposit_from_run raises DepositError for a reference run; index unchanged. G-INV-18."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget.html"; w.write_text("<html>widget</html>")
                meta = {"reference": True, "track": "SomeRef", "mode": "full"}
                with self.assertRaises(library.DepositError):
                    library.deposit_from_run(run, w, meta)
                root = library.library_root()
                self.assertFalse((root / "index.json").exists(),
                                 "no index written on a reference deposit refusal (G-INV-18)")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_own_run_still_deposits(self):
        """A run without reference:true deposits normally. G-INV-18."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget.html"; w.write_text("<html>widget</html>")
                meta = {"track": "OwnTrack", "mode": "full"}
                entry = library.deposit_from_run(run, w, meta)
                self.assertEqual(entry["track"], "OwnTrack")
                root = library.library_root()
                idx = json.loads((root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 1)
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_banner_count_excludes_references(self):
        """A reference run is refused, so library member count stays own-only. G-INV-18."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                # Deposit one own run
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget.html"; w.write_text("<html>widget</html>")
                library.deposit_from_run(run, w, {"track": "OwnTrack", "mode": "full"})
                # Attempt to deposit a reference run — must raise before writing
                refrun = Path(d) / "refrun"; refrun.mkdir()
                rw = refrun / "analysis_widget.html"; rw.write_text("<html>ref</html>")
                with self.assertRaises(library.DepositError):
                    library.deposit_from_run(refrun, rw,
                                             {"reference": True, "track": "ArtistRef", "mode": "full"})
                # Index must still have exactly 1 entry (the own track — banner input is own-only)
                root = library.library_root()
                idx = json.loads((root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 1,
                                 "library member count must exclude references (banner input stays own-only)")
                self.assertEqual(idx["entries"][0]["track"], "OwnTrack")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class SyntheticNotDeposited(unittest.TestCase):
    """G-INV-21: a run with synthetic:true in run_meta is refused by deposit_from_run — a
    fixture/smoke run never enters the library, exactly as a reference is refused (G-INV-18)."""

    def test_synthetic_run_refused(self):
        """deposit_from_run raises DepositError for a synthetic run; index unchanged. G-INV-21."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget.html"; w.write_text("<html>widget</html>")
                meta = {"synthetic": True, "track": "sine_220hz_1s", "mode": "quick"}
                with self.assertRaises(library.DepositError):
                    library.deposit_from_run(run, w, meta)
                root = library.library_root()
                self.assertFalse((root / "index.json").exists(),
                                 "no index written on a synthetic deposit refusal (G-INV-21)")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_own_run_still_deposits(self):
        """A run without synthetic:true deposits normally. G-INV-21."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = Path(d) / "run"; run.mkdir()
                w = run / "analysis_widget.html"; w.write_text("<html>widget</html>")
                entry = library.deposit_from_run(run, w, {"track": "OwnTrack", "mode": "full"})
                self.assertEqual(entry["track"], "OwnTrack")
                root = library.library_root()
                idx = json.loads((root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 1)
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class IncompleteRunNotDeposited(unittest.TestCase):
    """RC-INV-13: a run with analysis data but a broken measurement (a present stem whose sustain
    was never computed) is refused at deposit; a complete run deposits normally."""

    def _bands(self, db):
        return {b: [db] * 8 for b in ("sub", "low", "low_mid", "mid", "hi_mid", "air")}

    def _run(self, d, *, sustain):
        run = Path(d) / "run"; run.mkdir()
        (run / "analysis_widget.html").write_text("<html>w</html>")
        (run / "result_core.json").write_text(json.dumps({
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
        mk = {"band_rms_db": {"drums": self._bands(-30.0), "bass": self._bands(-30.0),
                              "other": self._bands(-30.0)},
              "stems_analysed": ["drums", "bass", "other"], "duration_s": 48.0,
              "total_windows": 8, "spectral_centroid": {"other": 800.0}}
        if sustain:
            mk["sustain"] = {"bass": 0.5, "other": 0.4}
        (run / "result_masking.json").write_text(json.dumps(mk))
        (run / "result_notes_other.json").write_text(json.dumps({"n_notes": 42}))
        return run

    def test_incomplete_run_refused(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = self._run(d, sustain=False)  # other significant, sustain never computed → invalid
                w = run / "analysis_widget.html"
                with self.assertRaises(library.DepositError):
                    library.deposit_from_run(run, w, {"track": "Partial", "mode": "full"})
                self.assertFalse((library.library_root() / "index.json").exists(),
                                 "no index written on an incomplete deposit refusal (RC-INV-13)")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_complete_run_deposits(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = self._run(d, sustain=True)  # all present signals measured → valid
                w = run / "analysis_widget.html"
                entry = library.deposit_from_run(run, w, {"track": "Whole", "mode": "full"})
                self.assertEqual(entry["track"], "Whole")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_forget_run_supersedes_old_deposit(self):
        """When a run is redone, its old deposit must cease to exist — forget_run drops the entry
        (and its widget file) by src_run_dir, matching even a slug that drifted. RC-INV-13."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                run = self._run(d, sustain=True)
                w = run / "analysis_widget.html"
                entry = library.deposit_from_run(run, w, {"track": "Wobble", "mode": "full"})
                root = library.library_root()
                self.assertTrue((root / "widgets" / entry["widget"]).exists())
                gone = library.forget_run(root, run)
                self.assertEqual(gone, 1, "the deposit for this run dir is forgotten")
                self.assertEqual(library.load_index(root)["entries"], [],
                                 "no lingering incomplete entry after a redo")
                self.assertFalse((root / "widgets" / entry["widget"]).exists(),
                                 "the old widget file is removed too")
                self.assertEqual(library.forget_run(root, run), 0,
                                 "forgetting an already-gone run is a no-op")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class ReferenceCleanup(unittest.TestCase):
    """G-INV-20: dereference command drops reference entries by album-path substring."""

    def _make_lib_with_refs(self, tmp):
        """Create a library with 1 own entry + 2 reference entries under SomeAlbum path."""
        lib_root = Path(tmp) / "lib"
        wdir = lib_root / "widgets"
        wdir.mkdir(parents=True)
        (wdir / "own_track.html").write_text("<html>own</html>")
        (wdir / "ref_1.html").write_text("<html>ref1</html>")
        (wdir / "ref_2.html").write_text("<html>ref2</html>")
        entries = [
            {"track": "OwnTrack", "stamp": "s1", "widget": "own_track.html",
             "src_run_dir": f"{tmp}/projects/OwnTrack/s1"},
            {"track": "RefArtist1", "stamp": "r1", "widget": "ref_1.html",
             "src_run_dir": f"{tmp}/SomeAlbum/track-coach-output/2026-01-01_1000"},
            {"track": "RefArtist2", "stamp": "r2", "widget": "ref_2.html",
             "src_run_dir": f"{tmp}/SomeAlbum/track-coach-output/2026-01-02_1000"},
        ]
        library.save_index(lib_root, {"entries": entries})
        return lib_root

    def test_dry_run_writes_nothing(self):
        """dereference without --apply leaves index unchanged and creates no .bak. G-INV-20."""
        with tempfile.TemporaryDirectory() as d:
            lib_root = self._make_lib_with_refs(d)
            os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
            try:
                idx_before = (lib_root / "index.json").read_text()
                args = types.SimpleNamespace(album_path=["SomeAlbum"], apply=False)
                library._cmd_dereference(args)
                self.assertEqual((lib_root / "index.json").read_text(), idx_before,
                                 "dry-run must not modify index.json (G-INV-20)")
                baks = list(lib_root.glob("index.json.bak-*"))
                self.assertEqual(baks, [], "dry-run must not create .bak file (G-INV-20)")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_apply_backs_up_and_drops_only_references(self):
        """dereference --apply creates a .bak and drops only reference entries. G-INV-20."""
        with tempfile.TemporaryDirectory() as d:
            lib_root = self._make_lib_with_refs(d)
            os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
            try:
                args = types.SimpleNamespace(album_path=["SomeAlbum"], apply=True)
                library._cmd_dereference(args)
                baks = list(lib_root.glob("index.json.bak-*"))
                self.assertEqual(len(baks), 1,
                                 "exactly one .bak must be created on --apply (G-INV-20)")
                idx = library.load_index(lib_root)
                self.assertEqual(len(idx["entries"]), 1,
                                 "only own entry must remain after dereference --apply (G-INV-20)")
                self.assertEqual(idx["entries"][0]["track"], "OwnTrack")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_own_entries_and_run_dirs_untouched(self):
        """dereference --apply keeps own entry; run dirs on disk are never deleted. G-INV-20."""
        with tempfile.TemporaryDirectory() as d:
            lib_root = self._make_lib_with_refs(d)
            # Create a real run dir on disk (the reference album path)
            run_dir = Path(d) / "SomeAlbum" / "track-coach-output" / "2026-01-01_1000"
            run_dir.mkdir(parents=True)
            (run_dir / "result_core.json").write_text("{}")
            os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)
            try:
                args = types.SimpleNamespace(album_path=["SomeAlbum"], apply=True)
                library._cmd_dereference(args)
                # own entry still in index
                idx = library.load_index(lib_root)
                own = [e for e in idx["entries"] if isinstance(e, dict) and e.get("track") == "OwnTrack"]
                self.assertEqual(len(own), 1, "own entry must survive dereference (G-INV-20)")
                # run dir on disk untouched
                self.assertTrue(run_dir.exists(),
                                "dereference must NOT delete run dirs on disk (G-INV-20)")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


if __name__ == "__main__":
    unittest.main()
