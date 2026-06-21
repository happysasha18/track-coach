#!/usr/bin/env python3
"""CREDIBILITY guardrail tests — G1…G7, derived from docs/SPEC.md (the credibility layer) via
product-prover (docs/prover_runs/spec_credibility_2026-06-20.md). Phase 3 of NEXT_STEPS #4.

These are LAYER-1 necessary-condition tests: they do NOT pin the musical verdict (that needs Sasha's
golden labels — layer 2, blocked). They only assert what can NEVER be true if the credibility invariant
CR-1 holds: "track-coach never presents, as fact, a number derived from invalid or insufficient input."
"Don't cry wolf, and don't paint silence."

Methodology (NEXT_STEPS 🪜, playbook): bug → SPEC → test → code. The SPEC (docs/SPEC.md) was written and
prover-stressed FIRST; each test below cites the SPEC clause + the prover finding it enforces, so a
failure points at a spec violation, not a guessed threshold. NEVER loosen one of these to make code pass
— if behaviour must change, change the SPEC first with a fresh citation (memory track-coach-graph-regression).

Fixtures are SYNTHETIC + deterministic (the data-sourcing rule: demos/screenshots = REAL, tests = made-up
deterministic data, so the suite never depends on real music). Evidence that these bugs exist on REAL data
(Lazy_Sparks, by deed 2026-06-20) is recorded in docs/SPEC.md §B.
"""
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget as bw  # noqa: E402
from build_widget import BAND_ORDER  # noqa: E402

# dB anchors for the synthetic stems. A "loud" stem reads as real content; a "silent" stem is a Demucs
# layer the separation barely filled (Lazy_Sparks vocals −92 dB / piano −88 dB). Broadband sums the six
# bands, so all-bands −95 → ~−87 dB broadband → below the −55 "empty" floor (build_widget.py loud_level).
LOUD = -20.0
SILENT = -95.0


# ──────────────────────────────────────────────────────────────────────────────────────────────
# fixture builders
# ──────────────────────────────────────────────────────────────────────────────────────────────
def _core(n=24, dur=120.0, energy=None, density=None, brightness=None, bounds=None):
    """A complete mix-level core. energy/density/brightness drive the Track-Story intensity curve;
    every component array is non-zero so build_story keeps all five lanes (any(src[k]) gate)."""
    tb = [round(i * dur / n, 3) for i in range(n)]
    flat = [0.5] * n
    return {
        "duration_s": dur, "time_bins": tb, "tempo": 120,
        "energy": energy if energy is not None else flat,
        "brightness": brightness if brightness is not None else [round(0.4 + 0.2 * (i % 4) / 4, 3) for i in range(n)],
        "density": density if density is not None else [round(0.3 + 0.3 * (i % 5) / 5, 3) for i in range(n)],
        "wobble_rate": [round(1.0 + (i % 4), 3) for i in range(n)],
        "stereo_width": [round(0.4 + 0.2 * (i % 3) / 3, 3) for i in range(n)],
        "energy_trend": 0.0, "brightness_trend": 0.0, "density_trend": 0.0,
        "stereo_width_trend": 0.0, "wobble_rate_start_hz": 1.0, "wobble_rate_end_hz": 2.0,
        "section_bounds_s": bounds if bounds is not None else [],
    }


def _masking(stems, n=24, dur=120.0):
    """stems: {name: dB-scalar | {band: dB}}. Builds a masking payload with flat per-band dB over time."""
    tb = [round(i * dur / n, 1) for i in range(n)]
    band = {}
    for st, spec in stems.items():
        if isinstance(spec, dict):
            band[st] = {b: [float(spec.get(b, spec.get("_all", SILENT)))] * n for b in BAND_ORDER}
        else:
            band[st] = {b: [float(spec)] * n for b in BAND_ORDER}
    return {
        "duration_s": dur, "total_windows": n, "masking_threshold_db": -6.0,
        "time_bins": tb, "stems_analysed": list(stems), "band_rms_db": band,
        "masking_flags": {}, "masking_summary": {},
        "viz": {"win_s": dur / n, "bins": tb, "bb": {}, "band": {}},
    }


def _selfsim(edges, letters):
    """edges: boundary times incl 0 and dur → segments; letters: per-segment recurrence letter."""
    segs = [{"t0": round(edges[i], 2), "t1": round(edges[i + 1], 2),
             "label": ord(letters[i]) - 65, "letter": letters[i]} for i in range(len(letters))]
    return {"segments": segs, "n_labels": len(set(letters)), "k": len(set(letters)),
            "labels_per_beat": [], "beat_times": []}


def _rhythm(leakage):
    """A minimal rhythm payload carrying only the pairwise stem leakage CR-4 needs.
    leakage: list of (a, b, r)."""
    return {"separation": {"leakage": [{"a": a, "b": b, "r": r} for a, b, r in leakage]}}


def _render(core, masking=None, selfsim=None, meta=None, title="Cred Test", rhythm=None,
            per_stem_selfsim=None):
    tmp = Path(tempfile.mkdtemp(prefix="tc_cred_"))
    out = tmp / "widget.html"
    bw.build_html(core, {}, masking, None, str(out), title, bw.STRINGS,
                  selfsim=selfsim, meta=meta, rhythm=rhythm, per_stem_selfsim=per_stem_selfsim,
                  mode="full")
    html = out.read_text(encoding="utf-8")
    payload, _ = json.JSONDecoder().raw_decode(html.split("const D=", 1)[1])
    return html, payload


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G1 — CR-2/CR-7 + prover P7: an insignificant stem produces NO per-stem output, and the widget
# carries an "omitted: <names> — too little material" note that NAMES them.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G1_InsignificantStemsOmittedAndNamed(unittest.TestCase):
    def setUp(self):
        self.html, self.D = _render(
            _core(),
            _masking({"drums": LOUD, "bass": LOUD, "vocals": SILENT, "piano": SILENT}))
        self.stem = self.D.get("stem") or {}

    def test_silent_stems_not_in_per_stem_viz(self):
        # CR-2: dropped from analysis — no per-stem viz computed for it (saves compute, doesn't paint silence).
        drawn = set(self.stem.get("stems", []))
        for st in ("vocals", "piano"):
            self.assertNotIn(st, drawn, f"silent stem '{st}' is still drawn in the per-stem viz (CR-2)")

    def test_silent_stems_not_in_heat(self):
        # the colour grid must carry no data for an omitted stem (CR-2/CR-3).
        heat = set((self.stem.get("heat") or {}).keys())
        self.assertFalse(heat & {"vocals", "piano"}, "omitted stems still have heat data")

    def test_kept_stems_survive(self):
        drawn = set(self.stem.get("stems", []))
        self.assertEqual({"drums", "bass"} & drawn, {"drums", "bass"}, "significant stems were dropped")

    def test_omission_note_names_the_stems(self):
        # P7: a panel that just disappears confuses the producer — the note must NAME them + the reason.
        for st in ("vocals", "piano"):
            self.assertRegex(
                self.html, rf"{st}[^<]{{0,80}}(omit|too little|near-silent|empty)|"
                           rf"(omit|too little)[^<]{{0,80}}{st}",
                f"no rendered note names the omitted stem '{st}'")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G2 — CR-1a (prover P2): the mix-level arc survives even when ALL stems are insignificant. The
# stem layer is omitted; energy/brightness/density/vitals are independent of stem significance.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G2_MixArcSurvivesAllInsignificantStems(unittest.TestCase):
    def setUp(self):
        self.html, self.D = _render(
            _core(),
            _masking({"drums": SILENT, "bass": SILENT, "vocals": SILENT, "piano": SILENT}))

    def test_story_components_present(self):
        comps = {c["key"] for c in (self.D.get("story") or {}).get("components", [])}
        for k in ("energy", "brightness", "density", "stereo"):
            self.assertIn(k, comps, f"mix-level lane '{k}' vanished when all stems were insignificant (CR-1a)")

    def test_intensity_curve_present(self):
        self.assertTrue((self.D.get("story") or {}).get("intensity"),
                        "the intensity/power curve must not depend on stems (CR-1a)")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G3 — CR-3: per-stem colour is gated on ABSOLUTE level, not per-stem normalization. A silent stem
# renders empty, never full-colour. (Layer-1 observable: a wholly-below-floor stem contributes no
# coloured heat; the colour function must reference an absolute floor, not only a per-stem max.)
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G3_SilentStemRendersEmptyNotFullColour(unittest.TestCase):
    def setUp(self):
        self.html, self.D = _render(
            _core(),
            _masking({"drums": LOUD, "bass": LOUD, "vocals": SILENT}))

    def test_silent_stem_has_no_colour_data(self):
        # vocals at −95 dB must not appear as a coloured row (subsumes into G1's omission).
        heat = (self.D.get("stem") or {}).get("heat") or {}
        self.assertNotIn("vocals", heat, "a silent stem still carries heat → would paint full-colour")

    def test_band_colour_uses_an_absolute_floor(self):
        # the per-stem strip's colour scale must be anchored to an ABSOLUTE dB floor in the payload,
        # so a quiet stem cannot normalize its loudest band up to full colour.
        floor = (self.D.get("stem") or {}).get("colour_floor_db")
        self.assertIsNotNone(floor, "stem payload exposes no absolute colour floor (CR-3)")
        self.assertLess(floor, -40.0, "absolute colour floor should be well below content level")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G4 — CR-5a (prover P4): scene boundaries derive from the self-similarity segmentation, not the
# coarse section_bounds_s. On a track whose section_bounds collapse the middle into one blob but
# whose self-sim correctly splits it, the scenes must follow self-sim.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G4_ScenesFollowSelfSimNotCoarseBounds(unittest.TestCase):
    def setUp(self):
        dur = 120.0
        # section_bounds gives ONE big middle blob; self-sim splits the track into A B C A C.
        ss = _selfsim([0, 20, 50, 75, 100, dur], "ABCAC")
        self.ss_edges = sorted({s["t0"] for s in ss["segments"]} | {s["t1"] for s in ss["segments"]})
        self.html, self.D = _render(_core(dur=dur, bounds=[60.0]), masking=None, selfsim=ss)
        self.scenes = (self.D.get("story") or {}).get("scenes", [])

    def test_scene_count_not_collapsed(self):
        # 5 self-sim segments → the structure bar must not flatten the middle to one or two blobs.
        self.assertGreaterEqual(len(self.scenes), 4,
                                f"scenes collapsed to {len(self.scenes)} — middle not split per self-sim (CR-5a)")

    def test_scene_edges_align_to_selfsim(self):
        scene_edges = sorted({s["t0"] for s in self.scenes} | {s["t1"] for s in self.scenes})
        for e in self.ss_edges:
            self.assertTrue(any(abs(e - se) <= 2.0 for se in scene_edges),
                            f"self-sim boundary {e}s has no matching scene edge (CR-5a); got {scene_edges}")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G5 — CR-5: every scene named "Drop" is immediately preceded by a LOWER-intensity scene (the
# required яма/build), and not more than ~⅓ of scenes are Drops (catches "весь из дропов").
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G5_DropRequiresPrecedingDipAndIsCapped(unittest.TestCase):
    def setUp(self):
        n, dur = 36, 180.0
        # a continuously-LOUD track: high energy with small ripple (NOT flat — _mm would zero a flat
        # curve and hide the bug). Every segment lands ≥0.8 of peak → today reads "Drop" everywhere.
        # The credible reading: without a preceding dip there is no drop.
        hi = [0.86, 0.92, 0.97, 1.0, 0.9, 0.94] * (n // 6)
        ss = _selfsim([0, 30, 60, 90, 120, 150, dur], "ABCDEF")
        self.html, self.D = _render(
            _core(n=n, dur=dur, energy=hi, density=hi, brightness=hi, bounds=[30, 60, 90, 120, 150]),
            masking=None, selfsim=ss)
        self.scenes = (self.D.get("story") or {}).get("scenes", [])

    def _is_drop(self, name):
        return bool(re.match(r"^Drop\b", name or ""))

    def test_no_drop_without_a_lower_predecessor(self):
        for i, sc in enumerate(self.scenes):
            if self._is_drop(sc["name"]):
                self.assertGreater(i, 0, "the first scene cannot be a Drop (nothing lower precedes it)")
                self.assertLess(self.scenes[i - 1].get("tier", 1.0), sc.get("tier", 0.0),
                                f"scene {i} '{sc['name']}' is a Drop but its predecessor is not lower (CR-5)")

    def test_continuously_loud_track_is_not_all_drops(self):
        # the "весь из дропов" case: this fixture is loud throughout with NO dips. Old code (≥0.8 of peak
        # ⇒ Drop) labelled all 6 segments Drop; the credible reading is zero drops (no lift), at most a
        # few. The structural cap: every Drop needs a strictly-lower non-Drop predecessor ⇒ Drops can
        # never be more than ~half the scenes. A continuously-loud track must fall well under that.
        if not self.scenes:
            self.skipTest("no scenes")
        drops = sum(1 for sc in self.scenes if self._is_drop(sc["name"]))
        self.assertLessEqual(drops / len(self.scenes), 0.5,
                             f"{drops}/{len(self.scenes)} scenes are Drops — a continuously-loud track read as (nearly) all drops (CR-5)")


class G5b_RealDropsAreStillDetected(unittest.TestCase):
    """The contrast rule must not over-correct into 'nothing is ever a Drop'. A genuinely alternating
    dip→high track (build/breakdown then a release) must still surface Drops, each with a lower
    predecessor. Guards the positive direction of CR-5."""

    def setUp(self):
        n, dur = 48, 240.0
        # alternating: low section, then a high release, repeated — the textbook build→drop shape.
        alt = [(0.25 if (i // 6) % 2 == 0 else 0.95) for i in range(n)]
        ss = _selfsim([0, 30, 60, 90, 120, 150, 180, 210, dur], "ABCDEFGH")
        self.html, self.D = _render(
            _core(n=n, dur=dur, energy=alt, density=alt, brightness=alt,
                  bounds=[30, 60, 90, 120, 150, 180, 210]),
            masking=None, selfsim=ss)
        self.scenes = (self.D.get("story") or {}).get("scenes", [])

    def test_drops_are_detected(self):
        drops = [sc for sc in self.scenes if re.match(r"^Drop\b", sc["name"] or "")]
        self.assertGreaterEqual(len(drops), 2, "an alternating build→drop track surfaced no Drops (over-corrected, CR-5)")

    def test_each_drop_has_a_lower_predecessor(self):
        for i, sc in enumerate(self.scenes):
            if re.match(r"^Drop\b", sc["name"] or ""):
                self.assertLess(self.scenes[i - 1].get("tier", 1.0), sc.get("tier", 0.0),
                                f"Drop at scene {i} lacks a lower predecessor (CR-5)")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G6 — CR-5: scene names ∈ the allowed vocabulary, and Drop numbering is contiguous (no "Drop, Drop 3"
# gap). The gap arose because numbers were assigned in build_story BEFORE _coalesce_scenes merged; the
# fix numbers Drops AFTER coalescing. Several real Drops here exercise the numbering non-vacuously.
# ──────────────────────────────────────────────────────────────────────────────────────────────
ALLOWED_SCENE_WORDS = {"Intro", "Build", "Drop", "Breakdown", "Outro", "Section", "Main", "Peak"}


class G6_SceneNameVocabularyAndContiguousNumbering(unittest.TestCase):
    def setUp(self):
        n, dur = 48, 240.0
        # alternating dip→high → four genuine Drops (Drop, Drop 2, Drop 3, Drop 4). Numbering is applied
        # after coalescing, so it must come out gap-free regardless of any letter merge.
        alt = [(0.25 if (i // 6) % 2 == 0 else 0.95) for i in range(n)]
        ss = _selfsim([0, 30, 60, 90, 120, 150, 180, 210, dur], "ABCDEFGH")
        self.html, self.D = _render(
            _core(n=n, dur=dur, energy=alt, density=alt, brightness=alt,
                  bounds=[30, 60, 90, 120, 150, 180, 210]),
            masking=None, selfsim=ss)
        self.scenes = (self.D.get("story") or {}).get("scenes", [])

    def test_names_in_vocabulary(self):
        for sc in self.scenes:
            base = re.sub(r"\s*\d+$", "", sc["name"] or "")
            self.assertIn(base, ALLOWED_SCENE_WORDS, f"scene name '{sc['name']}' is outside the vocabulary (CR-5)")

    def test_drop_numbering_contiguous(self):
        nums = []
        for sc in self.scenes:
            m = re.match(r"^Drop(?:\s+(\d+))?$", sc["name"] or "")
            if m:
                nums.append(int(m.group(1)) if m.group(1) else 1)
        if len(nums) > 1:
            self.assertEqual(sorted(nums), list(range(1, len(nums) + 1)),
                             f"Drop numbering has gaps: {nums} (numbered before _coalesce_scenes merged — CR-5)")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G7 — CR-6: per-stem repetition / self-similarity is computed only on SIGNIFICANT stems (an
# insignificant stem must never be used as a source of "this part returns"). Layer-1 contract: the
# significance gate exists and excludes below-floor stems, so whoever computes per-stem self-sim
# (CR-6, not yet built) is forced through it.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G7_PerStemRepetitionOnlyOnSignificantStems(unittest.TestCase):
    def setUp(self):
        self.masking = _masking({"drums": LOUD, "bass": LOUD, "vocals": SILENT, "piano": SILENT})

    def test_significance_gate_exists_and_excludes_silent(self):
        self.assertTrue(hasattr(bw, "significant_stems"),
                        "no significant_stems() gate — per-stem analysis can't be restricted (CR-6)")
        sig = set(bw.significant_stems(self.masking))
        self.assertEqual(sig, {"drums", "bass"},
                         f"significance gate let silent stems through: {sorted(sig)} (CR-6)")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G8 — KNOW WHAT YOU'RE LOOKING AT (Sasha, 2026-06-21). A credibility tool must announce its SOURCE:
# you cannot trust a number if you don't know which track it came from. Sasha opened a widget and
# couldn't tell what it was — because it was hand-rendered WITHOUT --src-audio, so the header showed
# only a free-text title. Guard: when the source filename is provided, the rendered header carries it.
# (The complementary defence is process — always build via the orchestrator, which always passes
# --src-audio/--src-als; SKILL.md already mandates it. This guards the wiring so identity can't silently
# drop out of a correctly-built widget.)
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G8_WidgetAnnouncesItsSource(unittest.TestCase):
    def setUp(self):
        self.html, self.D = _render(
            _core(),
            meta={"audio": "My_Track_v0.6.2.wav", "als": "My_Track.als",
                  "track_version": "v0.6.2", "analyzed_at": "2026-06-21 10:00"},
            title="My Track v0.6.2")

    def test_source_filename_in_payload(self):
        self.assertEqual((self.D.get("meta") or {}).get("audio"), "My_Track_v0.6.2.wav",
                         "the analysed audio filename must reach the widget payload")

    def test_source_filename_rendered_in_header(self):
        # the #srcmeta line is built from META.audio at runtime; the value must be present in the HTML
        # (inside the embedded payload) so the header can announce it. A widget that shows numbers but
        # not its source is exactly the "what am I even looking at?" failure.
        self.assertIn("My_Track_v0.6.2.wav", self.html,
                      "the source filename is not in the rendered widget — header can't announce the track")

    def test_srcmeta_element_exists(self):
        self.assertIn('id="srcmeta"', self.html, "the header source-line element is missing")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G9 — CR-4: bled energy is not attributed to the wrong stem. A stem whose DOMINANT band is really a
# louder, correlated neighbour bleeding in must be CAVEATED (named), not presented as that stem's own.
# Conservative + identity-agnostic: only the stem's single loudest band, only when the carrier is
# ≥10 dB louder AND correlated. The real Lazy_Sparks case: guitar's loudest band is low, but drums
# carries low 19 dB louder and they correlate — guitar's "low" is drum bleed.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G9_BledEnergyIsCaveatedNotAttributed(unittest.TestCase):
    def _mask(self):
        # drums: loud broadband → carries low. bass: owns sub. guitar: loudest band = low (−40) but
        # that's drum bleed. piano: silent (insignificant → must never get a caveat).
        return _masking({
            "drums":  {"sub": -18, "low": -20, "low_mid": -22, "mid": -22, "hi_mid": -24, "air": -30},
            "bass":   {"sub": -22, "low": -28, "low_mid": -34, "mid": -44, "hi_mid": -60, "air": -80},
            "guitar": {"sub": -75, "low": -40, "low_mid": -50, "mid": -48, "hi_mid": -58, "air": -90},
            "piano":  -95,
        })

    def test_dominant_bled_band_is_flagged_and_names_the_source(self):
        rh = _rhythm([("drums", "guitar", 0.35), ("drums", "bass", 0.6)])
        _, D = _render(_core(), masking=self._mask(), rhythm=rh)
        cav = D.get("leakage_caveats") or []
        gtr = [c for c in cav if c["stem"] == "guitar"]
        self.assertTrue(gtr, "guitar's dominant 'low' (drum bleed) was not caveated (CR-4)")
        self.assertEqual(gtr[0]["band"], "low")
        self.assertEqual(gtr[0]["source"], "drums", "the bleed source must be named")

    def test_caveat_is_rendered_with_the_names(self):
        rh = _rhythm([("drums", "guitar", 0.35)])
        html, _ = _render(_core(), masking=self._mask(), rhythm=rh)
        self.assertIn("guitar", html)
        self.assertRegex(html, r"guitar[^<]{0,160}(bleed|drums)", "the bleed caveat isn't rendered for the producer")

    def test_carrier_owning_its_band_is_not_flagged(self):
        # bass's loudest band is sub and nothing is ≥10 dB louder there → bass must NOT be flagged.
        rh = _rhythm([("drums", "bass", 0.6)])
        _, D = _render(_core(), masking=self._mask(), rhythm=rh)
        self.assertFalse([c for c in (D.get("leakage_caveats") or []) if c["stem"] == "bass"],
                         "bass owns its sub — flagging it as bleed is a false attribution (CR-4)")

    def test_insignificant_stem_never_caveated(self):
        rh = _rhythm([("drums", "piano", 0.9)])  # even with high correlation
        _, D = _render(_core(), masking=self._mask(), rhythm=rh)
        self.assertFalse([c for c in (D.get("leakage_caveats") or []) if c["stem"] == "piano"],
                         "a silent/omitted stem must not get a bleed caveat (CR-2 + CR-4)")

    def test_no_rhythm_means_no_caveats(self):
        _, D = _render(_core(), masking=self._mask(), rhythm=None)
        self.assertEqual(D.get("leakage_caveats"), [], "without leakage data there is nothing to attribute")

    def test_low_correlation_is_not_flagged(self):
        # same levels but the neighbour does NOT rise/fall with guitar (r below threshold) → no claim.
        rh = _rhythm([("drums", "guitar", 0.05)])
        _, D = _render(_core(), masking=self._mask(), rhythm=rh)
        self.assertFalse([c for c in (D.get("leakage_caveats") or []) if c["stem"] == "guitar"],
                         "uncorrelated stems shouldn't be called bleed (CR-4)")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G10 — CR-7: a stem↔project correspondence is stated only where DEFENSIBLE. The map panel asserts a
# project family (“matches X”) ONLY for a "clear" verdict; "mixed"/"nomatch"/"empty"/"weak" must not
# name a family at all. This is structurally guaranteed: only the map_clear string carries the {fam}
# slot. Locking it here so a future edit can't start asserting a family for an uncertain match (which
# would be exactly the wrong-label problem [[track-coach-stem-labels]] — Sasha makes electronic, so a
# Demucs "vocals"/"guitar" label is an approximation, never an identity).
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G10_StemProjectMatchStatedOnlyWhenClear(unittest.TestCase):
    def test_only_clear_verdict_can_name_a_family(self):
        S = bw.STRINGS["ui"]
        self.assertIn("{fam}", S["map_clear"], "a clear match must name the family")
        for k in ("map_mixed", "map_nomatch", "map_empty", "map_weak"):
            self.assertNotIn("{fam}", S[k], f"'{k}' must not assert a project family — the match isn't clear (CR-7)")

    def test_head_builder_feeds_family_only_to_clear(self):
        # source invariant: in the map-panel HEAD map, best_family is interpolated ONLY in the clear arm.
        _, _ = None, None
        src = (Path(__file__).resolve().parent.parent / "scripts" / "build_widget.py").read_text()
        m = re.search(r"const HEAD=\{(.*?)\};", src, re.S)
        self.assertTrue(m, "map-panel HEAD builder not found")
        head = m.group(1)
        # the clear arm runs from "clear:" up to the next verdict key (",mixed:")
        clear_arm = re.search(r"clear:.*?(?=,\s*mixed:)", head, re.S).group(0)
        self.assertIn("best_family", clear_arm, "clear arm should name the family")
        self.assertEqual(head.count("best_family"), 1,
                         "best_family is interpolated outside the clear arm — a non-clear verdict could "
                         "assert a project family it can't defend (CR-7)")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G11 — CR-6: per-stem repetition is read from each stem's OWN self-similarity, and ONLY for
# significant stems. "This part returns" must be grounded in the stem's real recurring material, and a
# near-silent stem must never be read for repetition (the G7 gate, made live). recurrence ∈ 0..1.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G11_PerStemRepetitionGatedToSignificant(unittest.TestCase):
    def setUp(self):
        # drums+bass significant, piano silent (insignificant). Per-stem self-sim: bass evolves
        # (all-distinct → recurrence 0), drums repeats (ABCABC → recurrence 0.5), piano has data too
        # but must be IGNORED because it's insignificant.
        self.masking = _masking({"drums": LOUD, "bass": LOUD, "piano": SILENT})
        self.pss = {
            "drums": _selfsim([0, 20, 40, 60, 80, 100, 120], "ABCABC"),
            "bass":  _selfsim([0, 20, 40, 60, 80, 100, 120], "ABCDEF"),
            "piano": _selfsim([0, 60, 120], "AA"),
        }
        _, self.D = _render(_core(), masking=self.masking, per_stem_selfsim=self.pss)
        self.rep = {r["stem"]: r for r in (self.D.get("stem_repetition") or [])}

    def test_insignificant_stem_excluded(self):
        self.assertNotIn("piano", self.rep, "a silent stem must not be read for repetition (CR-6/G7)")

    def test_significant_stems_present(self):
        self.assertIn("drums", self.rep)
        self.assertIn("bass", self.rep)

    def test_recurrence_metric(self):
        self.assertEqual(self.rep["bass"]["recurrence"], 0.0, "an all-distinct part should read as evolving (0)")
        self.assertEqual(self.rep["drums"]["recurrence"], 0.5, "ABCABC = 3 labels / 6 segs → recurrence 0.5")
        self.assertEqual(self.rep["drums"]["top_count"], 2, "each of A/B/C recurs twice in ABCABC")

    def test_no_data_means_empty(self):
        _, D = _render(_core(), masking=self.masking, per_stem_selfsim=None)
        self.assertEqual(D.get("stem_repetition"), [], "no per-stem self-sim → nothing to claim")


if __name__ == "__main__":
    unittest.main()
