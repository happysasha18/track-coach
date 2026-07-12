#!/usr/bin/env python3
"""§E — run-completeness / missing-measurement tests (RC-INV-1…12), derived from docs/SPEC.md §E via
product-prover (the §E review, s24). Each test cites the SPEC clause it enforces.

Methodology (playbook): bug → SPEC → test → code. The motivating bug (by deed, 2026-06-25): a partial run
transcribed only the `other` stem, so bass/lead note-density came back 0 — read as a music claim ("no bass
notes") when it meant "not measured". §E makes 'missing' a first-class state; these tests pin that the
shared logic (scripts/completeness.py) never lets a missing value masquerade as a real zero.

Fixtures are SYNTHETIC + deterministic (tests = made-up data, never real music). NEVER loosen one of these
to make code pass — change the SPEC first with a fresh citation.
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import completeness as C  # noqa: E402
import fingerprints as FP  # noqa: E402


class MissingIsNotZero(unittest.TestCase):
    """RC-INV-1: missing (None/NaN) is distinct from a measured zero."""

    def test_none_and_nan_are_missing(self):
        self.assertTrue(C.is_missing(None))
        self.assertTrue(C.is_missing(float("nan")))

    def test_measured_zero_is_not_missing(self):
        self.assertFalse(C.is_missing(0.0))
        self.assertFalse(C.is_missing(0))
        self.assertFalse(C.is_missing(-55.0))

    def test_manifest_lists_only_measured_axes(self):
        fp = {"tempo": 123.0, "pad_notes": 0.0, "bass_notes": None, "sustain": float("nan")}
        # RC-INV-2: measured-zero pad_notes is IN; missing bass_notes / NaN sustain are OUT
        self.assertEqual(C.manifest(fp), {"tempo", "pad_notes"})


class CompareOverSharedAxesOnly(unittest.TestCase):
    """RC-INV-3/5: a pairwise comparison drops a missing axis — never a 0-gap, never a max-gap."""

    def test_missing_axis_dropped_not_zeroed(self):
        # bass_notes missing on A, present (large) on B. If it were imputed to 0 it would add a huge gap;
        # if treated as "identical" it would add 0. RC-INV-5: it is simply not in the comparison.
        a = {"tempo": 0.0, "bass_notes": None}
        b = {"tempo": 0.0, "bass_notes": 9.0}
        d, n = C.per_axis_distance(a, b)
        self.assertEqual(n, 1)          # only tempo is shared
        self.assertEqual(d, 0.0)        # identical on the one shared axis — bass_notes excluded entirely

    def test_shared_axes_intersection(self):
        a = {"x": 1.0, "y": 2.0, "z": None}
        b = {"x": 1.0, "y": None, "z": 3.0}
        self.assertEqual(C.shared_axes(a, b), {"x"})


class TooFewSharedIsNotComparable(unittest.TestCase):
    """RC-INV-5a: below the floor of shared axes the pair is 'not comparable', never a fake 0 distance."""

    def test_no_shared_axes_returns_none(self):
        a = {"x": 1.0, "y": 2.0}
        b = {"p": 1.0, "q": 2.0}
        d, n = C.per_axis_distance(a, b, min_shared=1)
        self.assertIsNone(d)            # NOT 0.0 (which would read as "identical")
        self.assertEqual(n, 0)

    def test_below_min_shared_returns_none(self):
        a = {"x": 1.0, "y": 2.0, "z": 3.0}
        b = {"x": 1.0, "w": 9.0}
        d, n = C.per_axis_distance(a, b, min_shared=2)
        self.assertIsNone(d)
        self.assertEqual(n, 1)


class RankingIsAxisCountFair(unittest.TestCase):
    """RC-INV-5b: ranking directions uses per-axis distance, so a direction sharing more axes is not
    unfairly pushed away by a larger raw sum."""

    def test_per_axis_distance_not_raw_sum(self):
        track = {"a": 0.0, "b": 0.0, "c": 0.0}
        # DirP shares 3 axes, each off by 1.0 -> raw sum dist = sqrt(3)=1.73, per-axis = 1.0
        dirP = {"a": 1.0, "b": 1.0, "c": 1.0}
        # DirQ shares 1 axis, off by 1.2 -> raw sum dist = 1.2 (LOOKS closer by raw sum), per-axis = 1.2
        dirQ = {"a": 1.2, "x": 5.0, "y": 5.0}
        rank = C.nearest(track, {"P": dirP, "Q": dirQ}, min_shared=1)
        # by raw Euclidean sum Q (1.2) would beat P (1.73) — WRONG. Per-axis: P 1.0 < Q 1.2 -> P nearest.
        self.assertEqual(rank[0][1], "P")
        self.assertAlmostEqual(rank[0][0], 1.0, places=6)

    def test_not_comparable_direction_skipped_not_zero(self):
        track = {"a": 0.0}
        dirs = {"shareable": {"a": 1.0}, "disjoint": {"z": 9.0}}
        rank = C.nearest(track, dirs, min_shared=1)
        names = [r[1] for r in rank]
        self.assertIn("shareable", names)
        self.assertNotIn("disjoint", names)   # disjoint never enters the ranking as a fake 0


class CentroidSkipsMissingMembers(unittest.TestCase):
    """RC-INV-6: a member missing an axis does not drag the cloud's centroid toward 0; an axis no member
    has is absent (MISSING), not 0."""

    def test_missing_member_does_not_pull_to_zero(self):
        members = [
            {"sustain": 0.9, "tempo": 120.0},
            {"sustain": None, "tempo": 120.0},   # this member never measured sustain
            {"sustain": 0.9, "tempo": 120.0},
        ]
        cen = C.centroid(members)
        # sustain averaged over the TWO members that have it -> 0.9, NOT (0.9+0+0.9)/3 = 0.6
        self.assertAlmostEqual(cen["sustain"], 0.9, places=6)
        self.assertAlmostEqual(cen["tempo"], 120.0, places=6)

    def test_axis_no_member_has_is_missing_not_zero(self):
        members = [{"tempo": 120.0}, {"tempo": 124.0}]
        cen = C.centroid(members)
        self.assertNotIn("sustain", cen)          # absent axis is absent, not 0
        self.assertAlmostEqual(cen["tempo"], 122.0, places=6)


class SharedAxisFloor(unittest.TestCase):
    """RC-INV-5a / ⟨E-2 settled⟩: MIN_SHARED_AXES = 10 — below it, not comparable (too little DATA)."""

    def test_floor_is_ten(self):
        self.assertEqual(C.MIN_SHARED_AXES, 10)

    def test_comparable_at_floor_not_below(self):
        ten = {f"a{i}": 0.0 for i in range(10)}
        nine = {f"a{i}": 0.0 for i in range(9)}
        self.assertTrue(C.comparable(ten, dict(ten)))            # 10 shared -> comparable
        self.assertFalse(C.comparable(ten, nine))               # 9 shared -> not comparable

    def test_quick_vs_full_not_comparable(self):
        # a quick mix-only run (~6 axes) against a full fingerprint shares too few — an apples-to-oranges comparison
        quick = {f"mix{i}": 0.0 for i in range(6)}
        full = {**{f"mix{i}": 0.0 for i in range(6)}, **{f"stem{i}": 0.0 for i in range(8)}}
        self.assertFalse(C.comparable(quick, full))
        rank = C.nearest(quick, {"full": full})                 # default floor -> excluded, never a fake 0
        self.assertEqual(rank, [])

    def test_dissimilar_but_fully_measured_IS_comparable(self):
        # the floor is about missing DATA, not dissimilar music: two fully-measured tracks compare fine
        a = {f"x{i}": 0.0 for i in range(14)}
        b = {f"x{i}": 9.0 for i in range(14)}                    # very different, but all axes present
        self.assertTrue(C.comparable(a, b))
        d, n = C.per_axis_distance(a, b, min_shared=C.MIN_SHARED_AXES)
        self.assertIsNotNone(d)
        self.assertEqual(n, 14)


class PartialRunIsAnError(unittest.TestCase):
    """RC-INV-10 / ⟨E-1 settled⟩: should-have-measured-but-didn't = technical error; mode-never-promised = not."""

    def test_missing_promised_axis_is_failure(self):
        present = {"tempo", "bass_notes"}            # bass present
        expected = {"tempo", "bass_notes", "pad_notes"}
        self.assertEqual(C.incomplete_axes(present, expected), {"pad_notes"})
        self.assertTrue(C.is_partial_failure(present, expected))

    def test_complete_run_is_not_a_failure(self):
        present = {"tempo", "bass_notes", "pad_notes"}
        expected = {"tempo", "bass_notes", "pad_notes"}
        self.assertEqual(C.incomplete_axes(present, expected), set())
        self.assertFalse(C.is_partial_failure(present, expected))

    def test_mode_never_promised_is_not_a_failure(self):
        # quick mode promises only mix axes; absent stem axes are NOT an error
        present = {"tempo", "stereo"}
        expected_quick = {"tempo", "stereo"}
        self.assertFalse(C.is_partial_failure(present, expected_quick))


class RunCompleteness(unittest.TestCase):
    """RC-INV-12: "measured N of M signals; skipped: ⟨reads⟩" over the axes the run's rung promises
    (fingerprints.PROMISED_BY_MODE, split from the one AXES list). Missing-by-mode axes (per-stem on
    quick) are not promised, so they never count as skipped (RC-INV-7)."""

    def _core_only(self, tmp):
        """A run with only result_core.json — the five mix-level signals, no stems (no masking)."""
        run = Path(tmp) / "run"; run.mkdir()
        (run / "result_core.json").write_text(json.dumps({
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
        return str(run)

    def _full(self, tmp):
        """A run with core + masking so fingerprint_from_run_dir places all 14 axes."""
        run = Path(tmp) / "run"; run.mkdir()
        (run / "result_core.json").write_text(json.dumps({
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
        (run / "result_masking.json").write_text(json.dumps({
            "band_rms_db": {
                "drums": {"sub": [-30]*8, "low": [-25]*8, "low_mid": [-28]*8,
                          "mid": [-35]*8, "hi_mid": [-40]*8, "air": [-60]*8},
                "bass":  {"sub": [-20]*8, "low": [-18]*8, "low_mid": [-30]*8,
                          "mid": [-45]*8, "hi_mid": [-60]*8, "air": [-80]*8},
                "other": {"sub": [-50]*8, "low": [-45]*8, "low_mid": [-30]*8,
                          "mid": [-25]*8, "hi_mid": [-20]*8, "air": [-25]*8}},
            "stems_analysed": ["drums", "bass", "other"], "duration_s": 48.0,
            "sustain": {"bass": 0.5, "other": 0.4},
            "spectral_centroid": {"other": 800.0}, "total_windows": 8}))
        return str(run)

    def test_full_complete_measures_all(self):
        """A full run with core + masking measures all 14 promised signals, nothing skipped."""
        with tempfile.TemporaryDirectory() as td:
            n, m, skipped = FP.run_completeness(self._full(td), "full")
            self.assertEqual((n, m), (14, 14))
            self.assertEqual(skipped, [])

    def test_full_partial_lists_skipped_reads(self):
        """A full run that only measured the mix (no stems) discloses the 9 stem reads as skipped."""
        with tempfile.TemporaryDirectory() as td:
            n, m, skipped = FP.run_completeness(self._core_only(td), "full")
            self.assertEqual((n, m), (5, 14))
            self.assertEqual(len(skipped), 9)
            self.assertIn("bass sustain", skipped)   # a promised stem read, disclosed by plain name

    def test_quick_promises_only_mix_axes(self):
        """Quick promises only the five mix-level signals — its stemless per-stem axes are
        missing-by-mode, never counted as skipped (RC-INV-7)."""
        with tempfile.TemporaryDirectory() as td:
            n, m, skipped = FP.run_completeness(self._core_only(td), "quick")
            self.assertEqual((n, m), (5, 5))
            self.assertEqual(skipped, [])


class SignificanceHasUnknown(unittest.TestCase):
    """RC-INV-11: a stem whose gate inputs weren't measured is UNKNOWN, not INSIGNIFICANT."""

    def test_missing_gate_input_is_unknown(self):
        self.assertEqual(C.significance(None), C.UNKNOWN)
        self.assertEqual(C.significance(float("nan")), C.UNKNOWN)

    def test_measured_quiet_is_insignificant(self):
        self.assertEqual(C.significance(-58.0), C.INSIGNIFICANT)   # measured + below floor

    def test_measured_loud_is_significant(self):
        self.assertEqual(C.significance(-20.0), C.SIGNIFICANT)

    def test_unknown_is_distinct_from_insignificant(self):
        # the whole point of RC-INV-11 / RC-INV-1: not-measured must not read as measured-empty
        self.assertNotEqual(C.significance(None), C.significance(-58.0))


if __name__ == "__main__":
    unittest.main()
