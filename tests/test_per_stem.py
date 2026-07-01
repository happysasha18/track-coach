#!/usr/bin/env python3
"""Per-stem measurements core (SPEC §B.11 / CR-11, matrix INV-23..27). Pure functions, numpy-free.

The credibility design Sasha insisted on: a stem only speaks when it DIVERGES from the REST of the
track (not the full mix, which contains it), and cards earn their slot by an OBJECTIVE importance
score — no per-track human approval. These tests pin those rules before the UI wires them.
"""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget as bw  # noqa: E402


class RestCurve(unittest.TestCase):
    """The comparison baseline is the mix MINUS this stem (prover F1) — built from the OTHER stems."""
    def test_excludes_the_target_stem(self):
        curves = {"bass": [1, 1, 1], "drums": [2, 2, 2], "lead": [4, 4, 4]}
        self.assertEqual(bw.rest_curve(curves, "bass"), [3.0, 3.0, 3.0])  # mean of drums+lead

    def test_single_stem_has_no_rest(self):
        self.assertIsNone(bw.rest_curve({"bass": [1, 2, 3]}, "bass"))  # nothing to compare to

    def test_unknown_target_uses_all(self):
        # defensive: target not present → average of everything (still a valid baseline)
        self.assertEqual(bw.rest_curve({"a": [2, 2], "b": [4, 4]}, "zzz"), [3.0, 3.0])


class Divergence(unittest.TestCase):
    """Shape comparison, scale-invariant (a stem sits far below the mix in absolute level)."""
    def test_identical_shape_is_zero(self):
        self.assertAlmostEqual(bw.divergence([1, 2, 3, 4], [1, 2, 3, 4]), 0.0)

    def test_scaled_shape_is_still_zero(self):  # same shape, different level → not a divergence
        self.assertAlmostEqual(bw.divergence([1, 2, 3, 4], [10, 20, 30, 40]), 0.0)

    def test_opposite_shape_is_one(self):
        self.assertAlmostEqual(bw.divergence([1, 2, 3, 4], [4, 3, 2, 1]), 1.0)

    def test_flat_baseline_gives_no_signal(self):  # can't measure shape vs a flat line → don't cry wolf
        self.assertEqual(bw.divergence([1, 2, 3, 4], [5, 5, 5, 5]), 0.0)

    def test_too_short_gives_no_signal(self):
        self.assertEqual(bw.divergence([1], [2]), 0.0)


class CandidateScore(unittest.TestCase):
    """Objective usefulness: big · persistent · specific · non-redundant. No human approval (Sasha)."""
    def test_fully_redundant_scores_zero(self):  # restates the mix → ~0
        self.assertEqual(bw.candidate_score(divergence=0.9, persistence=0.9,
                                            specificity=0.9, redundancy=1.0), 0.0)

    def test_strong_unique_card_scores_high(self):
        s = bw.candidate_score(divergence=1.0, persistence=1.0, specificity=1.0, redundancy=0.0)
        self.assertGreaterEqual(s, 0.95)

    def test_more_divergence_scores_higher(self):
        lo = bw.candidate_score(divergence=0.2, persistence=0.5, specificity=0.5, redundancy=0.0)
        hi = bw.candidate_score(divergence=0.8, persistence=0.5, specificity=0.5, redundancy=0.0)
        self.assertGreater(hi, lo)

    def test_score_is_bounded_0_1(self):
        for d in (0.0, 0.5, 1.0):
            s = bw.candidate_score(divergence=d, persistence=d, specificity=d, redundancy=0.0)
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)


class Persistence(unittest.TestCase):
    """How much of the track the divergence holds — opposite sides of their own means."""
    def test_fully_opposite_is_one(self):
        self.assertAlmostEqual(bw._persistence([1, 2, 3, 4], [4, 3, 2, 1]), 1.0)

    def test_identical_is_zero(self):
        self.assertAlmostEqual(bw._persistence([1, 2, 3, 4], [1, 2, 3, 4]), 0.0)


class DivergenceCandidates(unittest.TestCase):
    """Integrate the core: per stem × measure, compare to the REST and emit a scored candidate."""
    def test_one_stem_diverges_others_flat_baseline(self):
        cores = {"bass":  {"energy": [1, 2, 3, 4]},
                 "drums": {"energy": [4, 3, 2, 1]},
                 "lead":  {"energy": [4, 3, 2, 1]}}
        cands = bw.stem_divergence_candidates(cores, measures=("energy",))
        # bass runs opposite the rest (drums+lead) → one candidate; the others' baseline is flat → none
        self.assertEqual([c["stem"] for c in cands], ["bass"])
        self.assertEqual(cands[0]["measure"], "energy")
        self.assertGreaterEqual(cands[0]["divergence"], 0.99)

    def test_all_moving_together_yields_nothing(self):
        cores = {"a": {"energy": [1, 2, 3]}, "b": {"energy": [1, 2, 3]}, "c": {"energy": [1, 2, 3]}}
        self.assertEqual(bw.stem_divergence_candidates(cores, measures=("energy",)), [])

    def test_sorted_by_score_desc(self):
        cores = {"bass":  {"energy": [1, 2, 3, 4], "density": [1, 1.1, 1.2, 1.0]},
                 "drums": {"energy": [4, 3, 2, 1], "density": [4, 3, 2, 1]},
                 "lead":  {"energy": [4, 3, 2, 1], "density": [4, 3, 2, 1]}}
        cands = bw.stem_divergence_candidates(cores, measures=("energy", "density"))
        scores = [c["score"] for c in cands]
        self.assertEqual(scores, sorted(scores, reverse=True))


class BudgetAndDiversity(unittest.TestCase):
    """Top by score up to a TOTAL budget, with a diversity rule so one stem can't hog the list."""
    def _c(self, stem, score):
        return {"stem": stem, "measure": "energy", "divergence": score, "score": score}

    def test_budget_limits_total(self):
        cands = [self._c("bass", 0.9), self._c("lead", 0.8), self._c("drums", 0.7)]
        self.assertEqual(len(bw.select_cards(cands, budget=2)), 2)

    def test_diversity_lets_a_weaker_other_stem_in(self):
        cands = [self._c("bass", 0.9), self._c("bass", 0.85), self._c("bass", 0.8),
                 self._c("lead", 0.4)]
        out = bw.select_cards(cands, budget=3, per_stem_cap=2)
        stems = sorted(c["stem"] for c in out)
        self.assertEqual(stems, ["bass", "bass", "lead"])  # 2 bass capped, lead promoted over 3rd bass

    def test_fills_budget_when_one_stem_dominates(self):
        cands = [self._c("bass", 0.9), self._c("bass", 0.85), self._c("bass", 0.8)]
        # only bass exists → the cap must not starve the budget
        self.assertEqual(len(bw.select_cards(cands, budget=3, per_stem_cap=2)), 3)

    def test_zero_budget_is_empty(self):
        self.assertEqual(bw.select_cards([self._c("bass", 0.9)], budget=0), [])


class Trend(unittest.TestCase):
    def test_rising_is_positive_flat_is_zero(self):
        self.assertGreater(bw._trend([1, 2, 3, 4, 5, 6]), 0.3)
        self.assertEqual(bw._trend([3, 3, 3, 3]), 0.0)
        self.assertLess(bw._trend([6, 5, 4, 3, 2, 1]), -0.3)


class CompositeCandidates(unittest.TestCase):
    """Cross-signal cards: a stem moving against the whole track (Sasha's composite idea)."""
    def test_stem_thins_as_track_builds(self):
        mix = {"energy": [1, 2, 3, 4, 5, 6]}
        stems = {"drums": {"density": [6, 5, 4, 3, 2, 1]}}
        out = bw.composite_candidates(mix, stems)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["relation"], "thins_as_track_builds")
        self.assertEqual(out[0]["stem"], "drums")

    def test_moving_together_yields_nothing(self):
        mix = {"energy": [1, 2, 3, 4, 5, 6]}
        stems = {"drums": {"density": [1, 2, 3, 4, 5, 6]}}
        self.assertEqual(bw.composite_candidates(mix, stems), [])


class StereoWidthMeasure(unittest.TestCase):
    """E2 (2026-06-23): widen the funnel — stereo width joins energy/density as a PRESCRIPTIVE per-part
    measure ("this part is wider/narrower than the rest"). Two guards: (1) a near-MONO part has no real
    stereo image to read, so its stereo card is suppressed (per-measure validity, A1 discipline);
    (2) stereo is a SEPARATE axis from the correlated activity pair (energy+density) — it must get its OWN
    card, never be merged into the "louder but sparser" activity card. SPEC §B.11."""

    def test_stereo_in_prescriptive_measures(self):
        self.assertIn("stereo_width", bw.PER_STEM_MEASURES)
        self.assertEqual(bw.CORRELATED_MEASURES, ("energy", "density"))

    def test_stereo_wording(self):
        self.assertEqual(bw._MEASURE_WORDS["stereo_width"], ("wider", "narrower"))

    def _cores(self, lead_mean):
        # lead's width runs OPPOSITE the two neighbours' shape → a real shape divergence (rest is shaped,
        # not flat — divergence is undefined vs a constant, so the baseline must move)
        return {"lead": {"stereo_width": [1, 0, 1, 0, 1, 0], "stereo_width_mean": lead_mean},
                "a":    {"stereo_width": [0, 1, 0, 1, 0, 1], "stereo_width_mean": 0.3},
                "b":    {"stereo_width": [0, 1, 0, 1, 0, 1], "stereo_width_mean": 0.3}}

    def test_wide_stem_emits_stereo_candidate(self):
        cands = bw.stem_divergence_candidates(self._cores(0.4), measures=("stereo_width",))
        self.assertTrue(any(c["stem"] == "lead" and c["measure"] == "stereo_width" for c in cands))

    def test_near_mono_stem_suppressed(self):
        # same diverging shape, but the part is essentially mono → no stereo card (nothing to widen)
        cands = bw.stem_divergence_candidates(self._cores(0.01), measures=("stereo_width",))
        self.assertEqual([c for c in cands if c["measure"] == "stereo_width"], [])

    def test_stereo_is_its_own_card_not_merged_into_activity(self):
        cands = [{"stem": "lead", "measure": "energy",       "dir": "up",   "score": 0.5},
                 {"stem": "lead", "measure": "density",      "dir": "down", "score": 0.4},
                 {"stem": "lead", "measure": "stereo_width", "dir": "up",   "score": 0.45}]
        out = bw.collapse_correlated(cands)
        lead = [c for c in out if c.get("stem") == "lead"]
        self.assertEqual(len(lead), 2)                                  # activity card + stereo card
        merged = [c for c in lead if "measures" in c]
        stereo = [c for c in lead if c.get("measure") == "stereo_width"]
        self.assertEqual(len(merged), 1)                               # energy+density merged into one
        self.assertEqual({m for m, _ in merged[0]["measures"]}, {"energy", "density"})
        self.assertEqual(len(stereo), 1)                               # stereo stands alone


class DynamicsMeasure(unittest.TestCase):
    """E2 (2026-06-23): per-part DYNAMIC RANGE as an axis ("this part is more dynamic / more compressed
    than the rest"). Unlike energy/density/stereo this is a SCALAR (`vitals.dynamic_range_db`, already in
    the core — no re-run), compared to the MEAN of the rest; |dev| past a dB threshold → a card. It's an
    independent axis (passes through collapse as its own card). SPEC §B.11."""

    def _cores(self, drums_dr):
        return {"drums": {"vitals": {"dynamic_range_db": drums_dr}},
                "bass":  {"vitals": {"dynamic_range_db": 25.0}},
                "lead":  {"vitals": {"dynamic_range_db": 26.0}}}

    def test_compressed_outlier_fires_down(self):
        cands = bw.stem_dynamics_candidates(self._cores(13.0))
        drums = [c for c in cands if c["stem"] == "drums"]
        self.assertEqual(len(drums), 1)
        self.assertEqual(drums[0]["measure"], "dynamics")
        self.assertEqual(drums[0]["dir"], "down")          # lower DR = more compressed

    def test_within_threshold_no_card(self):
        cores = {"a": {"vitals": {"dynamic_range_db": 20.0}},
                 "b": {"vitals": {"dynamic_range_db": 21.0}},
                 "c": {"vitals": {"dynamic_range_db": 22.0}}}
        self.assertEqual(bw.stem_dynamics_candidates(cores), [])

    def test_dynamics_wording(self):
        self.assertEqual(bw._MEASURE_WORDS["dynamics"], ("more dynamic", "more compressed"))

    def test_dynamics_is_independent_card_through_collapse(self):
        cands = [{"stem": "drums", "measure": "energy",   "dir": "up",   "score": 0.5},
                 {"stem": "drums", "measure": "dynamics", "dir": "down", "score": 0.6}]
        out = bw.collapse_correlated(cands)
        drums = [c for c in out if c.get("stem") == "drums"]
        self.assertEqual(len(drums), 2)                    # energy card + dynamics card, not merged
        self.assertTrue(any(c.get("measure") == "dynamics" for c in drums))

    def test_per_stem_cards_surfaces_dynamics(self):
        cores = self._cores(13.0)
        heads = " | ".join(c[2] for c in bw.per_stem_cards(cores))
        self.assertIn("more compressed than the rest", heads)


class CompositeTrendCalibration(unittest.TestCase):
    """Phase B (2026-06-23): COMPOSITE_TREND_MIN is FROZEN at a principled 0.3 — a composite ("a part
    moves against the whole track") only fires when the MIX has a genuine directional build/breakdown.
    None of the 3 library tracks does (mix energy _trend: Lazy 0.195, Shared -0.002, Wobble -0.034), so
    composites are correctly SILENT on all 3 — the threshold is validated as not-crying-wolf, not lowered
    to fire on noise. This guards both ends: a weak-arc track stays silent at the frozen tau; a real build
    still fires. JOURNAL 2026-06-23 s18 Phase B."""

    def test_frozen_threshold_value(self):
        self.assertEqual(bw.COMPOSITE_TREND_MIN, 0.3)

    def test_weak_arc_track_stays_silent_at_frozen_tau(self):
        # mix energy _trend ≈ 0.15 (< 0.3), like the flat library tracks, even with a strongly-thinning
        # stem → no composite. Forcing a fire here would mean lowering tau onto noise.
        mix = {"energy": [1, 3, 2, 2, 2, 2.6]}
        self.assertLess(bw._trend(mix["energy"]), bw.COMPOSITE_TREND_MIN)
        stems = {"drums": {"density": [6, 5, 4, 3, 2, 1]}}
        self.assertEqual(bw.composite_candidates(mix, stems), [])

    def test_genuine_build_still_fires_at_frozen_tau(self):
        mix = {"energy": [1, 2, 3, 4, 5, 6]}            # _trend = 1.0, a real build
        stems = {"drums": {"density": [6, 5, 4, 3, 2, 1]}}
        self.assertEqual(len(bw.composite_candidates(mix, stems)), 1)


class BrightnessIsNotPrescriptive(unittest.TestCase):
    """SPEC §B.11.1 (Sasha 2026-06-22): a part being brighter/darker than the rest is NOT a defect —
    the coach can't know intent (a drum fill / synth stab may be wanted), so brightness must not produce
    a prescriptive 'worth a second listen' per-stem card. It's dropped from the default prescriptive
    measures; relative brightness is descriptive / a future viz, not a per-part nudge."""

    def test_default_measures_exclude_brightness(self):
        self.assertNotIn("brightness", bw.PER_STEM_MEASURES)
        self.assertIn("energy", bw.PER_STEM_MEASURES)
        self.assertIn("density", bw.PER_STEM_MEASURES)

    def test_a_brightness_diverging_stem_yields_no_default_card(self):
        # bass brightness runs opposite the rest, but with default measures it must NOT card.
        cores = {"bass":  {"energy": [1, 2, 3, 4], "brightness": [4, 3, 2, 1]},
                 "drums": {"energy": [1, 2, 3, 4], "brightness": [1, 2, 3, 4]},
                 "lead":  {"energy": [1, 2, 3, 4], "brightness": [1, 2, 3, 4]}}
        cands = bw.stem_divergence_candidates(cores)  # default PER_STEM_MEASURES
        self.assertEqual([c for c in cands if c["measure"] == "brightness"], [])


def _fake_masking(levels_db):
    """A minimal masking dict with one controllable level per stem: all energy in one band, constant
    across windows, so loud_level(stem_broadband_db(...)) == the given dB. Lets us drive the
    significance gate + prominence weight without real audio."""
    n = 4
    return {"stems_analysed": list(levels_db),
            "total_windows": n,
            "band_rms_db": {st: {"low": [db] * n} for st, db in levels_db.items()}}


class Prominence(unittest.TestCase):
    """Near-silent stems rank BELOW louder ones (Sasha 2026-06-22): a quiet part's card earns less budget,
    so it sorts lower — a soft down-rank, never a drop."""
    def test_lower_prominence_scores_lower(self):
        loud = bw.candidate_score(divergence=0.8, persistence=0.8, specificity=0.5,
                                  redundancy=0.0, prominence=1.0)
        quiet = bw.candidate_score(divergence=0.8, persistence=0.8, specificity=0.5,
                                   redundancy=0.0, prominence=0.4)
        self.assertGreater(loud, quiet)

    def test_default_prominence_is_neutral(self):  # back-compat: omitting it changes nothing
        a = bw.candidate_score(divergence=0.6, persistence=0.6, specificity=0.6, redundancy=0.0)
        b = bw.candidate_score(divergence=0.6, persistence=0.6, specificity=0.6,
                               redundancy=0.0, prominence=1.0)
        self.assertEqual(a, b)

    def test_quiet_stem_ranks_below_loud_stem_at_equal_divergence(self):
        # `loud` and `quiet` diverge from the rest IDENTICALLY; only loudness differs → loud sorts first
        cores = {"loud":  {"energy": [1, 2, 3, 4]},
                 "quiet": {"energy": [1, 2, 3, 4]},
                 "restA": {"energy": [4, 3, 2, 1]},
                 "restB": {"energy": [4, 3, 2, 1]}}
        levels = {"loud": 1.0, "quiet": 0.4}
        cands = bw.stem_divergence_candidates(cores, measures=("energy",), levels=levels)
        order = [c["stem"] for c in cands]
        self.assertLess(order.index("loud"), order.index("quiet"))

    def test_stem_prominence_relative_to_loudest(self):
        prom = bw.stem_prominence(_fake_masking({"kick": -8.0, "pad": -20.0}))
        self.assertEqual(prom["kick"], 1.0)            # loudest stem → full weight
        self.assertLess(prom["pad"], prom["kick"])     # quieter stem → down-weighted
        self.assertGreaterEqual(prom["pad"], bw.PROMINENCE_FLOOR)

    def test_empty_masking_yields_no_weights(self):    # → every stem defaults to full weight downstream
        self.assertEqual(bw.stem_prominence(None), {})


class CompositeCardWording(unittest.TestCase):
    """Composite candidates (stem vs whole track) are now WORDED into the pool, named by character (0.8.23)."""
    def test_composite_card_worded_and_named_by_character(self):
        cores = {"drums": {"density": [6, 5, 4, 3, 2, 1]}}     # one stem → no divergence pair; composite fires
        mix = {"energy": [1, 2, 3, 4, 5, 6]}
        cards = bw.per_stem_cards(cores, mix_core=mix, character={"drums": {"label": "the beat"}})
        self.assertTrue(cards)
        heads = " ".join(c[2] for c in cards)
        self.assertIn("the beat", heads)              # named by character label
        self.assertNotIn("drums", heads)              # never the raw Demucs stem
        self.assertTrue(all(c[5] is None for c in cards))  # Detailed-only: no timecode


class PerStemCards(unittest.TestCase):
    """Candidates → worded rec tuples; Detailed-only (no timecode) and named by character, not raw stem."""
    def test_empty_input_no_cards(self):
        self.assertEqual(bw.per_stem_cards({}), [])

    def test_words_the_part_by_character_label_not_raw_stem(self):
        # density (a prescriptive measure) — brightness no longer cards (SPEC §B.11.1); this test's
        # intent is the character-label wording, which is measure-independent.
        cores = {"other": {"density": [1, 2, 3, 4]},
                 "drums": {"density": [4, 3, 2, 1]},
                 "bass":  {"density": [4, 3, 2, 1]}}
        cards = bw.per_stem_cards(cores, character={"other": {"label": "lead"}})
        self.assertTrue(cards)
        cls, when, head, body, fix, t, based = cards[0][:7]
        self.assertEqual(cls, "concept")
        self.assertIsNone(t)                      # no timecode → hidden in Simple, shown in Detailed
        self.assertIn("lead", head)               # named by character label
        self.assertNotIn("other", head)           # never the raw Demucs stem name
        self.assertTrue(based.strip())            # INV-31 — carries a based-on line
        self.assertIn("lead", based)              # …names the part by its character label there too


class CollapseCorrelated(unittest.TestCase):
    """Per PART, correlated divergence candidates collapse to ONE card (SPEC §B.11 "Correlated measures
    collapse — SMART"): same direction → strongest only; opposite directions → MERGE into one richer card."""

    def test_same_direction_keeps_strongest_only(self):
        cands = [{"stem": "mid", "measure": "energy", "dir": "down", "score": 0.6},
                 {"stem": "mid", "measure": "density", "dir": "down", "score": 0.4}]
        out = bw.collapse_correlated(cands)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["measure"], "energy")   # the stronger one survives, unmerged
        self.assertNotIn("measures", out[0])

    def test_opposite_directions_merge_carrying_both(self):
        cands = [{"stem": "lead", "measure": "energy", "dir": "up", "score": 0.6},
                 {"stem": "lead", "measure": "density", "dir": "down", "score": 0.4}]
        out = bw.collapse_correlated(cands)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["measures"], [("energy", "up"), ("density", "down")])  # ordered, both kept
        self.assertEqual(out[0]["score"], 0.6)          # carries the strongest score

    def test_composite_candidates_pass_through_untouched(self):
        comp = {"kind": "composite", "stem": "drums", "relation": "thins_as_track_builds", "score": 0.5}
        out = bw.collapse_correlated([comp,
                                      {"stem": "lead", "measure": "energy", "dir": "up", "score": 0.6},
                                      {"stem": "lead", "measure": "density", "dir": "down", "score": 0.4}])
        comps = [c for c in out if c.get("kind") == "composite"]
        self.assertEqual(comps, [comp])

    def test_integration_merged_card_reads_louder_but_sparser(self):
        # lead's energy RISES vs the rest while its density FALLS → opposite dirs → one merged card.
        # The rest must carry a shape (divergence is measured against shape, not a flat line), so drums/bass
        # run OPPOSITE to the lead on each axis.
        cores = {"other": {"energy": [1, 2, 3, 4, 5, 6], "density": [6, 5, 4, 3, 2, 1]},
                 "drums": {"energy": [6, 5, 4, 3, 2, 1], "density": [1, 2, 3, 4, 5, 6]},
                 "bass":  {"energy": [6, 5, 4, 3, 2, 1], "density": [1, 2, 3, 4, 5, 6]}}
        cards = bw.per_stem_cards(cores, character={"other": {"label": "lead"}})
        heads = " ".join(c[2] for c in cards)
        self.assertIn("louder but sparser", heads)
        self.assertNotIn("other", heads)               # never the raw Demucs stem


if __name__ == "__main__":
    unittest.main()
