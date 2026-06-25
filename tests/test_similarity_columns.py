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


if __name__ == "__main__":
    unittest.main()
