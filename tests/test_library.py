#!/usr/bin/env python3
"""Global-library tests — naming, the clean policy, and a deposit round-trip.

`clean_plan` deletes files, so its policy is a PURE function tested exhaustively here (no FS).
`deposit` is exercised against a temp library root via $TRACK_COACH_LIBRARY.
"""
import json, os, sys, tempfile, unittest
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


if __name__ == "__main__":
    unittest.main()
