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


if __name__ == "__main__":
    unittest.main()
