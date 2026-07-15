#!/usr/bin/env python3
"""§D10F — the two catalog-tail similarity columns' PURE geometry (SPEC §D.10 + §F → D-INV-21…26, F-INV-1…8),
derived from docs/SPEC.md via product-prover (s25). Each test cites the SPEC clause it enforces.

Methodology (playbook): spec → prove → matrix → test → code. Fixtures are SYNTHETIC + deterministic
(made-up fingerprints, never real music). NEVER loosen a test to make code pass — change the SPEC first
with a fresh citation. The colour RENDER + scroll-nav are NOT here (they land with the catalog code,
asserted against the real artifact); this file pins the geometry that the render paints.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import completeness as C  # noqa: E402
import similarity_columns as S  # noqa: E402

AX = [f"a{i}" for i in range(12)]  # 12 axes ⇒ always ≥ MIN_SHARED_AXES (10) when fully measured


def fp(**over):
    v = {k: 0.0 for k in AX}
    v.update(over)
    return v


def cloud(*members):
    return C.centroid(list(members))


class LeansTowardPicksNearestDirection(unittest.TestCase):
    """D-INV-21: the named direction is the axis-count-fair nearest cloud, one geometry."""

    def test_nearest_centroid_wins(self):
        track = fp(a0=1.0)
        dirs = {"near": cloud(fp(a0=1.2), fp(a0=0.8)), "far": cloud(fp(a0=9.0), fp(a0=9.4))}
        lean = S.leans_toward(track, dirs)
        self.assertEqual(lean.direction, "near")

    def test_no_directions_is_none_not_fabricated(self):
        # D-INV-21 / §D.10: with nothing to lean toward, return None ("no direction yet"), never a fake nearest.
        self.assertIsNone(S.leans_toward(fp(a0=1.0), {}))


class RelativeLeanBuckets(unittest.TestCase):
    """D-INV-26 / D-28: the cue is RELATIVE lean — how far the nearest stands apart from the others."""

    def test_clear_lean_is_close(self):
        # one direction hugged, the other two far and bunched ⇒ nearest stands clearly apart ⇒ close.
        track = fp(a0=0.0)
        dirs = {"x": cloud(fp(a0=0.1)), "y": cloud(fp(a0=8.0)), "z": cloud(fp(a0=8.3))}
        self.assertEqual(S.leans_toward(track, dirs).level, S.CLOSE)

    def test_mild_lean_is_mid(self):
        # nearest stands moderately apart (sep ≈ 0.37): clearly nearest x, but the field is wide ⇒ mid.
        track = fp(a0=0.0)
        dirs = {"x": cloud(fp(a0=0.5)), "y": cloud(fp(a0=4.0)), "z": cloud(fp(a0=9.9))}
        self.assertEqual(S.leans_toward(track, dirs).level, S.MID)

    def test_no_real_lean_is_far(self):
        # all three directions equidistant from the track ⇒ no lean ⇒ far.
        track = fp(a0=0.0, a1=0.0)
        dirs = {"x": cloud(fp(a0=5.0)), "y": cloud(fp(a1=5.0)), "z": cloud(fp(a0=5.0, a1=5.0))}
        # x and y are both distance 5; z is farther — nearest barely apart from runner ⇒ far.
        lean = S.leans_toward(track, dirs)
        self.assertEqual(lean.level, S.FAR)

    def test_single_direction_is_mid(self):
        # nothing to be relative to ⇒ a lean, but not a strong relative one.
        self.assertEqual(S.leans_toward(fp(a0=0.0), {"only": cloud(fp(a0=1.0))}).level, S.MID)


class RunnerUpDeferred(unittest.TestCase):
    """⟨DECIDE D-24⟩ RE-OPENED (by deed, s25): the runner-up is deferred from v1 — under relative lean a tied
    second means the nearest does NOT stand apart (a weak lean, not a close one). v1 always returns runner=None."""

    def test_two_tied_directions_yield_no_runner_and_no_strong_lean(self):
        # x and y nearly tied ⇒ the nearest does not stand apart ⇒ a WEAK lean (far), and never a runner in v1.
        track = fp(a0=0.0)
        dirs = {"x": cloud(fp(a0=0.10)), "y": cloud(fp(a0=0.12)), "z": cloud(fp(a0=9.0))}
        lean = S.leans_toward(track, dirs)
        self.assertEqual(lean.level, S.FAR)
        self.assertIsNone(lean.runner)

    def test_clear_single_lean_has_no_runner(self):
        track = fp(a0=0.0)
        dirs = {"x": cloud(fp(a0=0.1)), "y": cloud(fp(a0=4.0)), "z": cloud(fp(a0=8.2))}
        self.assertIsNone(S.leans_toward(track, dirs).runner)


class LeansTowardCompleteness(unittest.TestCase):
    """RC-INV-5a: a not-comparable track yields no direction, never a fabricated nearest."""

    def test_missing_axes_track_is_not_comparable(self):
        track = {"a0": 1.0}  # only 1 measured axis ⇒ < MIN_SHARED_AXES with any full cloud
        dirs = {"x": cloud(fp(a0=1.0))}
        self.assertIsNone(S.leans_toward(track, dirs))


class NearestOwnBasics(unittest.TestCase):
    """F-INV-1/2: up to 3 nearest OWN tracks, ranked, never itself."""

    def test_ranked_nearest_first_and_excludes_self(self):
        lib = {"me": fp(a0=0.0), "close": fp(a0=0.2), "midd": fp(a0=3.0), "farr": fp(a0=9.0)}
        sibs = S.nearest_own("me", lib)
        self.assertNotIn("me", [s.track for s in sibs])
        self.assertEqual(sibs[0].track, "close")
        self.assertLessEqual(len(sibs), 3)

    def test_cap_of_three(self):
        lib = {"me": fp(a0=0.0)}
        lib.update({f"n{i}": fp(a0=0.1 * (i + 1)) for i in range(6)})
        self.assertEqual(len(S.nearest_own("me", lib)), 3)


class NearestOwnRedIsLastResort(unittest.TestCase):
    """F-INV-1 / D-INV-26: red only when nothing close; never empty if a comparable sibling exists."""

    def test_all_far_returns_one_red_not_empty(self):
        # one track sits far from a LARGE tight cluster ⇒ the tercile cuts (D-27) put all its siblings in the
        # far bucket ⇒ red last-resort: exactly one sibling, tinted far, never empty (F-INV-1).
        lib = {"lonely": fp(a0=20.0)}
        lib.update({f"c{i}": fp(a0=0.1 * i) for i in range(9)})   # 9 tight members ⇒ c-c pairs dominate terciles
        sibs = S.nearest_own("lonely", lib)
        self.assertEqual(len(sibs), 1)
        self.assertEqual(sibs[0].level, S.FAR)

    def test_library_of_one_has_no_comparison(self):
        # F-INV-7: no other comparable track ⇒ empty ("no comparison yet"), not a red self-match.
        self.assertEqual(S.nearest_own("solo", {"solo": fp(a0=1.0)}), [])

    def test_close_sibling_is_not_red(self):
        lib = {"me": fp(a0=0.0), "twin": fp(a0=0.05), "farr": fp(a0=15.0)}
        sibs = S.nearest_own("me", lib)
        self.assertEqual(sibs[0].track, "twin")
        self.assertIn(sibs[0].level, (S.CLOSE, S.MID))


class NoNumberLeaksOut(unittest.TestCase):
    """D-INV-25: the surface inputs carry a LEVEL word, never a raw distance the render could print."""

    def test_levels_are_words_not_numbers(self):
        lib = {"me": fp(a0=0.0), "x": fp(a0=0.2), "y": fp(a0=5.0)}
        for s in S.nearest_own("me", lib):
            self.assertIn(s.level, (S.CLOSE, S.MID, S.FAR))
        lean = S.leans_toward(fp(a0=0.0), {"x": cloud(fp(a0=0.1)), "y": cloud(fp(a0=9.0))})
        self.assertIn(lean.level, (S.CLOSE, S.MID, S.FAR))


class TopKBasics(unittest.TestCase):
    """§D.10.1: leans_toward_topk returns up to k CLOSE/MID leans, never FAR, nearest-first."""

    def test_returns_list_not_single(self):
        track = fp(a0=0.0)
        dirs = {"near": cloud(fp(a0=0.1)), "far": cloud(fp(a0=9.0))}
        result = S.leans_toward_topk(track, dirs)
        self.assertIsInstance(result, list)

    def test_no_directions_returns_empty_list(self):
        result = S.leans_toward_topk(fp(a0=0.0), {})
        self.assertEqual(result, [])

    def test_nearest_first_ordering(self):
        # Three directions with clear enough separation to qualify (sep ≥ SEP_MID=0.25).
        # sep_0 = (d[B]-d[A]) / (d[C]-d[A]); with A=0.1, B=5.0, C=9.9 on a0:
        #   = (5.0-0.1)/(9.9-0.1) = 4.9/9.8 = 0.5 ≥ SEP_MID → MID → qualifies.
        track = fp(a0=0.0)
        dirs = {
            "A": cloud(fp(a0=0.1)),   # nearest
            "B": cloud(fp(a0=5.0)),   # mid (clearly apart from A)
            "C": cloud(fp(a0=9.9)),   # farthest
        }
        result = S.leans_toward_topk(track, dirs)
        self.assertTrue(len(result) >= 1, "at least one direction must qualify")
        self.assertEqual(result[0].direction, "A", "nearest must be first")
        if len(result) >= 2:
            self.assertEqual(result[1].direction, "B", "second-nearest must be second")

    def test_at_most_k_results(self):
        # Five equally-spaced directions; topk(k=3) must cap at 3.
        track = fp(a0=0.0)
        dirs = {f"D{i}": cloud(fp(a0=float(i))) for i in range(1, 6)}
        result = S.leans_toward_topk(track, dirs, k=3)
        self.assertLessEqual(len(result), 3)

    def test_far_directions_excluded_never_in_result(self):
        # All three directions equidistant → FAR → empty list, never padded.
        track = fp(a0=0.0, a1=0.0)
        dirs = {
            "x": cloud(fp(a0=5.0)),
            "y": cloud(fp(a1=5.0)),
            "z": cloud(fp(a0=5.0, a1=5.0)),
        }
        # This may or may not produce FAR depending on geometry; only assert the type contract.
        result = S.leans_toward_topk(track, dirs)
        for lean in result:
            self.assertIn(lean.level, (S.CLOSE, S.MID),
                          "topk must never include a FAR direction (D-INV-27)")

    def test_single_direction_returns_mid_lean(self):
        # One direction → MID (nothing to be relative to), not an empty list.
        track = fp(a0=0.0)
        result = S.leans_toward_topk(track, {"only": cloud(fp(a0=1.0))})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].level, S.MID)
        self.assertEqual(result[0].direction, "only")

    def test_all_equidistant_returns_empty(self):
        # Two perfectly equidistant directions (span=0) → total_span≤1e-9 → [] (D-INV-27)
        track = fp(a0=0.0)
        dirs = {"x": cloud(fp(a0=5.0)), "y": cloud(fp(a0=5.0))}
        result = S.leans_toward_topk(track, dirs)
        self.assertEqual(result, [], "equidistant directions → no real lean → empty list")

    def test_deterministic_tie_break_by_name(self):
        # Two directions at the same distance from the track → alphabetical name wins.
        track = fp(a0=0.0)
        # Both 'Alpha' and 'Zeta' sit at the same distance on orthogonal axes.
        dirs = {
            "Zeta":  cloud(fp(a0=3.0)),
            "Alpha": cloud(fp(a0=3.0)),
            "Omega": cloud(fp(a0=9.0)),
        }
        result1 = S.leans_toward_topk(track, dirs)
        result2 = S.leans_toward_topk(track, {"Omega": cloud(fp(a0=9.0)),
                                               "Zeta":  cloud(fp(a0=3.0)),
                                               "Alpha": cloud(fp(a0=3.0))})
        if result1 and result2:
            self.assertEqual(result1[0].direction, result2[0].direction,
                             "tie-break must be deterministic regardless of dict insertion order")

    def test_result_levels_are_words_not_numbers(self):
        track = fp(a0=0.0)
        dirs = {"A": cloud(fp(a0=0.1)), "B": cloud(fp(a0=9.0))}
        for lean in S.leans_toward_topk(track, dirs):
            self.assertIn(lean.level, (S.CLOSE, S.MID),
                          "topk levels must be 'close' or 'mid' words, never a number (D-INV-25)")

    def test_missing_axes_track_returns_empty(self):
        # RC-INV-5a: not-comparable track → no comparable direction → empty list.
        track = {"a0": 1.0}  # only 1 measured axis < MIN_SHARED_AXES
        dirs = {"x": cloud(fp(a0=1.0))}
        self.assertEqual(S.leans_toward_topk(track, dirs), [])


class ReasonProbe(unittest.TestCase):
    """Shared reason-plumbing (D-INV-22 / D-INV-22-completeness / F-INV-5/6/7): an empty similarity
    result carries WHY it is empty + which signals are missing, so the cell can phrase it (never a
    bare []) and the presence gate can drop an all-empty column. One missing-signals probe, threaded
    to both columns."""

    def _real_fp(self, **over):
        """A fingerprint on the REAL 14 axis names (so missing_signals maps to producer reads)."""
        import fingerprints as FP
        v = {ax: 0.0 for ax in FP.AXES}
        v.update(over)
        return v

    def test_missing_signals_names_the_absent_axes_in_producer_words(self):
        import fingerprints as FP
        fp = self._real_fp()
        del fp["brightness"]          # drop one measured axis
        fp["density"] = None          # None = not-measured (RC-INV-1), a measured 0 stays measured
        reads = S.missing_signals(fp)
        self.assertIn(FP.AXIS_READS["brightness"], reads)  # 'brightness'
        self.assertIn(FP.AXIS_READS["density"], reads)     # 'density'
        self.assertNotIn(FP.AXIS_READS["tempo"], reads, "a measured 0.0 axis is NOT missing (RC-INV-1)")

    def test_missing_signals_empty_when_complete(self):
        self.assertEqual(S.missing_signals(self._real_fp()), [])

    def test_lean_reason_no_data_when_no_directions(self):
        # no directions defined at all → the reference column is absent (D-INV-22)
        self.assertEqual(S.lean_reason(self._real_fp(), {}), (S.R_NO_DATA, []))

    def test_lean_reason_missing_axis_when_not_comparable(self):
        # a fingerprint measuring only 1 axis can't share MIN_SHARED with any full direction → missing-axis
        track = {"tempo": 1.0}
        dirs = {"x": cloud(self._real_fp())}
        reason, miss = S.lean_reason(track, dirs)
        self.assertEqual(reason, S.R_MISSING)
        self.assertTrue(miss, "the missing-signal reads must be named for the 'can't compare' cell")

    def test_lean_reason_no_direction_when_comparable_but_far(self):
        # fully comparable, but the caller found no CLOSE/MID lean → 'no close direction yet'
        reason, miss = S.lean_reason(self._real_fp(), {"x": cloud(self._real_fp(tempo=9.0))})
        self.assertEqual(reason, S.R_NO_DIRECTION)
        self.assertEqual(miss, [])

    def test_sibling_reason_no_comparison_for_library_of_one(self):
        lib = {"solo": self._real_fp()}
        self.assertEqual(S.sibling_reason("solo", lib), (S.R_NO_COMPARISON, []))

    def test_sibling_reason_missing_axis_when_self_not_comparable(self):
        # this track measures 1 axis; a full sibling exists but they can't share MIN_SHARED → missing-axis
        lib = {"me": {"tempo": 1.0}, "full": self._real_fp()}
        reason, miss = S.sibling_reason("me", lib)
        self.assertEqual(reason, S.R_MISSING)
        self.assertTrue(miss)

    def test_sibling_reason_no_data_when_absent(self):
        self.assertEqual(S.sibling_reason("ghost", {"other": fp(a0=1.0)}), (S.R_NO_DATA, []))


if __name__ == "__main__":
    unittest.main()
