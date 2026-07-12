#!/usr/bin/env python3
"""CREDIBILITY guardrail tests — G1…G7, derived from docs/SPEC.md (the credibility layer) via
product-prover (docs/prover_runs/spec_credibility_2026-06-20.md). Phase 3 of NEXT_STEPS #4.

These are LAYER-1 necessary-condition tests: they do NOT pin the musical verdict (that needs the producer's
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


def _masking(stems, n=24, dur=120.0, flatness=None, sustain=None, centroid=None):
    """stems: {name: dB-scalar | {band: dB}}. Builds a masking payload with flat per-band dB over time.
    flatness: optional {stem: 0..1} energy-weighted spectral flatness (G13 noise/pitch split).
    sustain: optional {stem: 0..1} envelope continuity (G13 pad-vs-chord).
    centroid: optional {stem: Hz} per-stem spectral centroid (G18 freq-role from the frequency analyzer)."""
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
        "spectral_flatness": dict(flatness or {}),
        "sustain": dict(sustain or {}),
        "spectral_centroid": dict(centroid or {}),
        "viz": {"win_s": dur / n, "bins": tb, "bb": {}, "band": {}},
    }


def _notes(events):
    """events: list of (start, dur) → a result_notes-style payload for one stem (pitch irrelevant here)."""
    return {"notes": [{"t": float(s), "dur": float(d), "pitch": 60, "name": "C4", "amp": 0.5}
                      for s, d in events]}


def _selfsim(edges, letters):
    """edges: boundary times incl 0 and dur → segments; letters: per-segment recurrence letter."""
    segs = [{"t0": round(edges[i], 2), "t1": round(edges[i + 1], 2),
             "label": ord(letters[i]) - 65, "letter": letters[i]} for i in range(len(letters))]
    return {"segments": segs, "n_labels": len(set(letters)), "k": len(set(letters)),
            "labels_per_beat": [], "beat_times": []}


def _rhythm(leakage=(), onsets=None):
    """A minimal rhythm payload: pairwise stem leakage (for CR-4) + per-stem onset_rate (for (g)).
    leakage: list of (a, b, r); onsets: {stem: onsets_per_sec}."""
    return {"separation": {"leakage": [{"a": a, "b": b, "r": r} for a, b, r in leakage]},
            "rhythm": {st: {"onset_rate": rate} for st, rate in (onsets or {}).items()}}


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
# required dip/build), and not more than ~⅓ of scenes are Drops (catches "all drops").
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
        # the "all drops" case: this fixture is loud throughout with NO dips. Old code (≥0.8 of peak
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
# G8 — KNOW WHAT YOU'RE LOOKING AT (2026-06-21). A credibility tool must announce its SOURCE:
# you cannot trust a number if you don't know which track it came from. The producer opened a widget and
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
# would be exactly the wrong-label problem [[track-coach-stem-labels]] — the producer makes electronic, so a
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


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G12 — (g) stem CHARACTER labels (2026-06-21). Raw Demucs labels (vocals/guitar/…) are wrong
# for electronic music, so we describe what the SOUND is from MEASURED features: frequency role (which
# third of the spectrum carries the energy, EXCLUDING bled bands) × percussive-vs-sustained (onset rate).
# Hard requirements: DETERMINISTIC (same track → same label every run) and gated to significant stems.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G12_StemCharacterLabels(unittest.TestCase):
    def _setup(self):
        # drums: low + many onsets → kick/drums. bass: low + few onsets → bass. lead: mid + few → melodic.
        # gtr: looks low ONLY because of drum bleed (its real energy is mid) → must read melodic, not bass.
        # piano: silent → excluded.
        mask = _masking({
            "drums": {"sub": -16, "low": -18, "low_mid": -34, "mid": -36, "hi_mid": -40, "air": -48},
            "bass":  {"sub": -20, "low": -24, "low_mid": -40, "mid": -50, "hi_mid": -70, "air": -90},
            "lead":  {"sub": -80, "low": -70, "low_mid": -30, "mid": -28, "hi_mid": -44, "air": -70},
            "gtr":   {"sub": -75, "low": -30, "low_mid": -38, "mid": -34, "hi_mid": -58, "air": -85},
            "piano": -95,
        })
        rh = _rhythm(leakage=[("drums", "gtr", 0.4), ("drums", "bass", 0.6)],
                     onsets={"drums": 5.3, "bass": 1.3, "lead": 1.1, "gtr": 1.6})
        return mask, rh

    def setUp(self):
        self.mask, self.rh = self._setup()
        self.ch = bw.stem_character(self.mask, self.rh, bw.leakage_caveats(self.mask, self.rh))

    def test_drums_stem_is_drums_not_kick(self):
        # s14 (§B.7): the whole `drums` stem is TRUSTED by identity → "drums", not reduced to "kick"
        # (kick lives in the drum breakdown). Reducing it to "kick instead of the whole kit" was wrong.
        self.assertEqual(self.ch["drums"]["label"], "drums")
        self.assertEqual(self.ch["drums"]["confidence"], "clear")

    def test_low_sustained_is_bass(self):
        self.assertEqual(self.ch["bass"]["label"], "bass")
        self.assertEqual(self.ch["bass"]["confidence"], "clear")

    def test_mid_sustained_no_notes_shows_base_role_not_tonal(self):
        # s14 (§B.7): the uncertain mid umbrella shows the BASE ROLE ("mid"), never the jargon "tonal".
        self.assertEqual(self.ch["lead"]["role"], "mid")
        self.assertEqual(self.ch["lead"]["label"], "mid")
        self.assertEqual(self.ch["lead"]["confidence"], "approx")

    def test_bled_low_excluded_so_guitar_is_not_bass(self):
        # gtr's loudest raw band is low (−22), but that's drum bleed. As of G14 the role no longer EXCLUDES
        # the bled band — instead the high-pass drop is small (its real mid survives) so it's not 'bass'.
        self.assertEqual(self.ch["gtr"]["role"], "mid", "guitar with bled low should read mid, not bass")
        self.assertNotEqual(self.ch["gtr"]["label"], "bass")

    def test_insignificant_stem_excluded(self):
        self.assertNotIn("piano", self.ch, "a silent stem must not get a character label")

    def test_deterministic_same_input_same_label(self):
        # a hard requirement: the same track must never be relabelled on a re-run.
        a = bw.stem_character(self.mask, self.rh, bw.leakage_caveats(self.mask, self.rh))
        m2, r2 = self._setup()
        b = bw.stem_character(m2, r2, bw.leakage_caveats(m2, r2))
        self.assertEqual(a, b, "stem_character is not deterministic — labels would drift between runs")

    def test_reaches_payload(self):
        _, D = _render(_core(), masking=self.mask, rhythm=self.rh)
        self.assertEqual((D.get("stem_character") or {}).get("bass", {}).get("label"), "bass")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G13 — split the honest mid·sustained "tonal" umbrella (2026-06-21: "a chord or a melody — I
# thought that was simple", and it IS: polyphony). MEASURED buckets only, no vocabulary: monophonic → lead
# (loudest) / melody (quieter); polyphonic → pad (held) / chord (stabs); high spectral flatness → noise.
# Every G13 label is `approx`; with NO transcribed notes we keep the honest "tonal" (CR-1). SPEC §B.4.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G13_TonalSplit(unittest.TestCase):
    MID = {"sub": -80, "low": -70, "low_mid": -22, "mid": -20, "hi_mid": -44, "air": -70}  # mid·sustained, loud

    def _mid(self, shift=0.0):  # same shape, quieter in its carrying bands
        return {b: (v + shift if b in ("low_mid", "mid") else v) for b, v in self.MID.items()}

    def test_polyphony_helper(self):
        self.assertEqual(bw.polyphony([{"t": 0, "dur": 1}, {"t": 1, "dur": 1}, {"t": 2, "dur": 1}]), 0.0)
        self.assertEqual(bw.polyphony([{"t": 0, "dur": 2}, {"t": 0, "dur": 2}]), 1.0)
        self.assertIsNone(bw.polyphony([]))   # nothing to measure → caller keeps the honest umbrella

    def test_mono_loudest_is_lead_quieter_is_melody(self):
        mask = _masking({"lead": self.MID, "mel": self._mid(-12)})
        rh = _rhythm(onsets={"lead": 1.0, "mel": 1.0})
        seq = _notes([(0, 0.5), (1, 0.5), (2, 0.5), (3, 0.5)])  # non-overlapping → monophonic
        ch = bw.stem_character(mask, rh, [], {"lead": seq, "mel": seq})
        self.assertEqual(ch["lead"]["label"], "lead")
        self.assertEqual(ch["mel"]["label"], "melody")

    def test_poly_held_is_pad(self):
        # polyphonic AND a continuously-sounding envelope (sustain ≥ PAD_SUSTAIN_MIN) → a held pad
        mask = _masking({"pad": self.MID}, sustain={"pad": 0.9})
        ch = bw.stem_character(mask, _rhythm(onsets={"pad": 1.0}), [],
                               {"pad": _notes([(0, 2.0), (0, 2.0), (2, 2.0), (2, 2.0)])})  # stacked
        self.assertEqual(ch["pad"]["label"], "pad")

    def test_poly_gappy_is_chord(self):
        # polyphonic but a gappy envelope (low sustain) → rhythmic chord stabs, not a held pad
        mask = _masking({"chd": self.MID}, sustain={"chd": 0.45})
        ch = bw.stem_character(mask, _rhythm(onsets={"chd": 1.0}), [],
                               {"chd": _notes([(0, 0.3), (0, 0.3), (1, 0.3), (1, 0.3)])})  # stacked
        self.assertEqual(ch["chd"]["label"], "chord")

    def test_poly_no_sustain_data_defaults_to_chord(self):
        # missing sustain (older masking) → never invent "pad"; fall back to the honest "chord" umbrella
        mask = _masking({"x": self.MID})
        ch = bw.stem_character(mask, _rhythm(onsets={"x": 1.0}), [],
                               {"x": _notes([(0, 0.5), (0, 0.5), (1, 0.5), (1, 0.5)])})
        self.assertEqual(ch["x"]["label"], "chord")

    def test_high_flatness_is_noise(self):
        # broadband/noisy stem: flatness wins even over pitched-looking notes — there's no pitch to call.
        mask = _masking({"nz": self.MID}, flatness={"nz": 0.5})
        ch = bw.stem_character(mask, _rhythm(onsets={"nz": 1.0}), [], {"nz": _notes([(0, 0.5), (1, 0.5)])})
        self.assertEqual(ch["nz"]["label"], "noise")

    def test_no_notes_shows_base_role_not_tonal(self):
        # s14 (§B.7): without transcribed notes we can't name the musical role → show the base role
        # ("mid"), never the jargon "tonal". (CR-1 honesty is kept; the WORD changed.)
        mask = _masking({"x": self.MID})
        ch = bw.stem_character(mask, _rhythm(onsets={"x": 1.0}), [], None)  # no per-stem notes
        self.assertEqual(ch["x"]["label"], "mid")

    def test_only_mid_sustained_is_refined(self):
        # G13 refines ONLY mid·sustained — a low·sustained bass must stay "bass" even with notes present.
        mask = _masking({"bass": {"sub": -20, "low": -22, "low_mid": -50, "mid": -60, "hi_mid": -80, "air": -90}})
        ch = bw.stem_character(mask, _rhythm(onsets={"bass": 1.0}), [], {"bass": _notes([(0, 0.5), (1, 0.5)])})
        self.assertEqual(ch["bass"]["label"], "bass")

    def test_g13_labels_are_approx(self):
        mask = _masking({"lead": self.MID})
        ch = bw.stem_character(mask, _rhythm(onsets={"lead": 1.0}), [], {"lead": _notes([(0, 0.5), (1, 0.5)])})
        self.assertEqual(ch["lead"]["confidence"], "approx")

    def test_deterministic(self):
        mask = _masking({"lead": self.MID, "mel": self._mid(-12)})
        rh = _rhythm(onsets={"lead": 1.0, "mel": 1.0})
        notes = {"lead": _notes([(0, 0.5), (1, 0.5)]), "mel": _notes([(0, 0.5), (1, 0.5)])}
        self.assertEqual(bw.stem_character(mask, rh, [], notes), bw.stem_character(mask, rh, [], notes))


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G14 — robust freq-ROLE via a HIGH-PASS drop (2026-06-21). Decide "is this a low/bass
# stem?" by how much loudness it LOSES when high-passed (sub+low dropped), not by which band is loudest.
# Fixes two real-data failures found by deed: an intermittent bass read as ~silence at the median →
# mislabeled mid; and a guitar's bled-in (loud) low → mislabeled bass. Relative drop, leakage-free.
# ──────────────────────────────────────────────────────────────────────────────────────────────
def _intermittent(loud_db, n=24, hits=5):
    """A band series silent at the median but loud in its top `hits` bins — an intermittent stem."""
    return [-120.0] * (n - hits) + [float(loud_db)] * hits


class G14_RoleHighPassDrop(unittest.TestCase):
    def test_trusted_bass_stem_stays_bass_even_when_highpass_does_not_collapse(self):
        # s14 (§B.7): the Lazy_Sparks fix. A synth `bass` stem with strong mid harmonics does NOT lose
        # ≥HP_DROP_DB under the high-pass (it would have fallen to "mid"/"tonal"). Because the `bass`
        # family is TRUSTED by identity, we skip the high-pass entirely and keep it "bass".
        mask = _masking({"bass": {"sub": -22, "low": -24, "low_mid": -26, "mid": -28, "hi_mid": -40, "air": -60}})
        ch = bw.stem_character(mask, _rhythm(onsets={"bass": 1.0}), [], None)
        self.assertEqual(ch["bass"]["label"], "bass")
        self.assertEqual(ch["bass"]["role"], "low")

    def test_untrusted_low_stem_collapses_under_highpass(self):
        # the high-pass mechanism still classifies an UNTRUSTED stem name: a low-dominant stem that
        # collapses under the high-pass reads as low → "bass".
        mask = _masking({"sub": {"sub": -20, "low": -22, "low_mid": -55, "mid": -60, "hi_mid": -80, "air": -90}})
        ch = bw.stem_character(mask, _rhythm(onsets={"sub": 1.0}), [], None)
        self.assertEqual(ch["sub"]["role"], "low")
        self.assertEqual(ch["sub"]["label"], "bass")

    def test_bled_low_stem_is_not_bass(self):
        # loudest single band is low (−24, drum bleed) but real mid content survives the high-pass → NOT bass
        mask = _masking({"gtr": {"sub": -70, "low": -24, "low_mid": -30, "mid": -34, "hi_mid": -58, "air": -85}})
        ch = bw.stem_character(mask, _rhythm(onsets={"gtr": 1.0}), [], None)
        self.assertEqual(ch["gtr"]["role"], "mid")
        self.assertNotEqual(ch["gtr"]["label"], "bass")

    def test_intermittent_bass_typed_by_loud_content_not_median(self):
        # bass plays only a few beats: median is silence in every band, but its loud low hits keep it 'bass'.
        band = {"sub": _intermittent(-18), "low": _intermittent(-20)}
        for b in ("low_mid", "mid", "hi_mid", "air"):
            band[b] = [-120.0] * 24
        mask = {"duration_s": 120.0, "total_windows": 24, "masking_threshold_db": -6.0,
                "time_bins": [i * 5.0 for i in range(24)], "stems_analysed": ["bass"],
                "band_rms_db": {"bass": band}, "masking_flags": {}, "masking_summary": {},
                "spectral_flatness": {}, "viz": {"win_s": 5.0, "bins": [], "bb": {}, "band": {}}}
        ch = bw.stem_character(mask, _rhythm(onsets={"bass": 1.0}), [], None)
        self.assertEqual(ch.get("bass", {}).get("label"), "bass")

    def test_role_is_leakage_free(self):
        # G14 made the role independent of CR-4 leakage — passing caveats must not change it.
        mask = _masking({"gtr": {"sub": -70, "low": -24, "low_mid": -30, "mid": -34, "hi_mid": -58, "air": -85}})
        rh = _rhythm(onsets={"gtr": 1.0})
        self.assertEqual(bw.stem_character(mask, rh, [], None)["gtr"]["role"],
                         bw.stem_character(mask, rh, [{"stem": "gtr", "band": "low"}], None)["gtr"]["role"])


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G15 — percussive-vs-tonal by CONTENT, not onset alone (found by deed on track 2 "Simon Fava"). The G12
# onset gate (>=3.0) short-circuited two PITCHED mid stems (a stabby pad, a choppy vocal) to "perc" before
# the tonal split ran. Same family as G14: a stem with transcribed notes is tonal even when rhythmic;
# "perc" is reserved for transient stems with NO pitched content (drums, which aren't transcribed).
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G15_PercussiveByContent(unittest.TestCase):
    MID = {"sub": -80, "low": -70, "low_mid": -22, "mid": -20, "hi_mid": -44, "air": -70}
    LOW = {"sub": -16, "low": -18, "low_mid": -34, "mid": -36, "hi_mid": -40, "air": -48}

    def test_pitched_rhythmic_stem_is_tonal_not_perc(self):
        # onset 3.5 (> ONSET_PERCUSSIVE) BUT it has notes → pitched → routed to the tonal split, not "perc"
        mask = _masking({"rp": self.MID}, sustain={"rp": 0.9})
        ch = bw.stem_character(mask, _rhythm(onsets={"rp": 3.5}), [],
                               {"rp": _notes([(0, 2.0), (0, 2.0), (2, 2.0), (2, 2.0)])})  # polyphonic + held
        self.assertFalse(ch["rp"]["percussive"])
        self.assertEqual(ch["rp"]["label"], "pad")

    def test_pitched_rhythmic_mono_is_melody_not_perc(self):
        mask = _masking({"vox": self.MID})
        ch = bw.stem_character(mask, _rhythm(onsets={"vox": 3.7}), [],
                               {"vox": _notes([(0, 0.4), (1, 0.4), (2, 0.4)])})  # monophonic, rhythmic
        self.assertFalse(ch["vox"]["percussive"])
        self.assertEqual(ch["vox"]["label"], "lead")   # single mono → loudest → lead

    def test_transient_without_notes_stays_kick(self):
        # no transcribed notes → not pitched → onset alone governs → still percussion
        mask = _masking({"dr": self.LOW})
        ch = bw.stem_character(mask, _rhythm(onsets={"dr": 5.0}), [], None)
        self.assertTrue(ch["dr"]["percussive"])
        self.assertEqual(ch["dr"]["label"], "kick")

    def test_mid_transient_without_notes_is_perc(self):
        mask = _masking({"pc": self.MID})
        ch = bw.stem_character(mask, _rhythm(onsets={"pc": 5.0}), [], None)  # no notes
        self.assertEqual(ch["pc"]["label"], "perc")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G18 — freq-role from the per-stem FREQUENCY ANALYZER's spectral CENTROID (s14). When the masking
# carries spectral_centroid, a sustained stem's role follows where its energy sits (low/mid/high) — a
# robust signal that replaces the crude 6-band high-pass. Falls back to the high-pass when no centroid.
# An UNTRUSTED stem name is used (bass/drums are trusted by identity and never reach this path).
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G18_CentroidFreqRole(unittest.TestCase):
    def _ch(self, hz):
        m = _masking({"syn": -25.0}, centroid=({"syn": hz} if hz is not None else None))
        return bw.stem_character(m, _rhythm(onsets={"syn": 1.0}), [], None)["syn"]  # sustained, no notes

    def test_low_centroid_is_low_role_bass_label(self):
        c = self._ch(120.0)                     # like a bass (deed: Lazy_Sparks bass 117 Hz)
        self.assertEqual(c["role"], "low")
        self.assertEqual(c["label"], "bass")

    def test_mid_centroid_is_mid(self):
        self.assertEqual(self._ch(1000.0)["role"], "mid")   # like a guitar/lead (deed: 1007 Hz)

    def test_high_centroid_is_high(self):
        self.assertEqual(self._ch(6000.0)["role"], "high")  # airy/cymbal-bright

    def test_no_centroid_falls_back_to_highpass(self):
        # pre-0.8.14 masking (no spectral_centroid) must still produce a role via the high-pass path.
        c = self._ch(None)
        self.assertIn(c["role"], ("low", "mid", "high"))
        self.assertIsNotNone(c["label"])


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G16 — INDIVIDUAL masking recs (request #2): name the masked part by its measured character + band +
# worst time, not a generic template line with the raw Demucs name. Gated to significant stems.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G16_IndividualMaskingRecs(unittest.TestCase):
    def setUp(self):
        m = _masking({"bass":  {"sub": -18, "low": -20, "low_mid": -22, "mid": -30, "hi_mid": -50, "air": -70},
                      "lead":  {"sub": -80, "low": -70, "low_mid": -30, "mid": -28, "hi_mid": -44, "air": -70},
                      "piano": -95})
        m["masking_summary"] = {
            "low_mid__lead":  {"pct_masked": 18.0, "flagged_windows": 4, "total_windows": 24, "mean_diff_db": 10.0},
            "low_mid__piano": {"pct_masked": 20.0, "flagged_windows": 5, "total_windows": 24, "mean_diff_db": 9.0}}
        m["masking_flags"] = {
            "low_mid__lead":  [{"low_stem": "bass", "mid_stem": "lead", "time_s": 78.0,
                                "low_db": -22.0, "mid_db": -34.0, "diff_db": 12.0, "window_idx": 15}],
            "low_mid__piano": [{"low_stem": "bass", "mid_stem": "piano", "time_s": 80.0,
                                "low_db": -22.0, "mid_db": -40.0, "diff_db": 18.0, "window_idx": 16}]}
        self.m = m
        ch = {"bass": {"label": "bass", "confidence": "clear"}, "lead": {"label": "lead", "confidence": "approx"}}
        self.recs = bw.build_recommendations(_core(), {}, m, bw.STRINGS, character=ch)
        self.blob = " || ".join(r[1] + " " + r[2] + " " + r[3] for r in self.recs)  # header+title+body

    def test_names_both_parts_by_character_and_band(self):
        self.assertIn("lead", self.blob)
        self.assertIn("bass", self.blob)
        self.assertIn("250–600 Hz", self.blob)

    def test_empty_stem_is_not_named(self):
        self.assertNotIn("piano", self.blob)   # piano is below the floor → never surfaced as a clash

    def test_not_the_generic_raw_name_line(self):
        self.assertNotIn("of spots", self.blob)   # the old generic template must not fire when characters exist

    def test_pinned_to_worst_moment(self):
        self.assertTrue([r for r in self.recs if r[5] == 78.0],
                        "the named masking rec should be anchored to the worst flag's time")

    def test_falls_back_to_generic_without_characters(self):
        recs = bw.build_recommendations(_core(), {}, self.m, bw.STRINGS, character=None)
        blob = " || ".join(r[1] + " " + r[2] + " " + r[3] for r in recs)
        self.assertIn("of spots", blob)   # no characters → old generic line, never a wrong named claim


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G17 — the late_entry rec names the PART, never the raw Demucs name (SPEC §B.6, request #2 cont.).
# late_entry is by definition about a near-silent stem, so a G16 character label is usually ABSENT —
# the honest naming hierarchy is: character label → stemmap real-track name (only verdict 'clear') →
# neutral "a new element". The raw Demucs family name ('vocals'/'guitar') must NEVER reach the card.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G17_LateEntryNamesThePart(unittest.TestCase):
    def _late_masking(self, spike_db=LOUD):
        """A 'vocals' stem silent everywhere but one spike near the end (tb=110 > 0.8*120), plus a
        constant-loud 'drums' baseline so nothing else fires. spike_db controls the entering peak:
        LOUD (−20, real content) → fires; a sub-floor value (−61) → an empty artifact, must NOT fire."""
        m = _masking({"drums": LOUD, "vocals": SILENT})
        spike = 22                                   # tb_m[22] = 110.0 (> 96.0)
        for b in BAND_ORDER:
            m["band_rms_db"]["vocals"][b] = [SILENT] * 24
            m["band_rms_db"]["vocals"][b][spike] = spike_db
        return m

    def _late_rec(self, recs):
        return next((r for r in recs if "enters right at the end" in r[2] or "appears at" in r[3]), None)

    def _all_text(self, r):
        return r[1] + " " + r[2] + " " + r[3] + " " + r[4]   # header+title+body+fix

    def test_fires_and_never_uses_raw_demucs_name(self):
        m = self._late_masking()
        recs = bw.build_recommendations(_core(), {}, m, bw.STRINGS)   # no character, no stemmap
        r = self._late_rec(recs)
        self.assertIsNotNone(r, "late_entry should fire for a stem that only spikes near the end")
        self.assertNotIn("vocals", self._all_text(r))        # raw Demucs name must never leak
        self.assertIn("A new element is silent", r[3])       # body uses the neutral phrase, not the stem

    def test_prefers_character_label(self):
        m = self._late_masking()
        ch = {"vocals": {"label": "lead", "confidence": "approx"}}
        r = self._late_rec(bw.build_recommendations(_core(), {}, m, bw.STRINGS, character=ch))
        self.assertIn("lead", r[3])                           # the measured character names the part
        self.assertNotIn("vocals", self._all_text(r))

    def test_uses_stemmap_real_name_only_when_clear(self):
        m = self._late_masking()
        good = {"stems": {"vocals": {"verdict": "clear",
                                     "track_matches": [{"track": "Lead Synth", "r": 0.6}]}}}
        r = self._late_rec(bw.build_recommendations(_core(), {}, m, bw.STRINGS, stemmap=good))
        self.assertIn("Lead Synth", r[3])                    # the clearly-mapped real track name
        self.assertNotIn("vocals", self._all_text(r))

    def test_ignores_stemmap_when_not_clear(self):
        m = self._late_masking()
        for v in ("mixed", "nomatch", "empty"):
            sm = {"stems": {"vocals": {"verdict": v,
                                       "track_matches": [{"track": "Lead Synth", "r": 0.31}]}}}
            r = self._late_rec(bw.build_recommendations(_core(), {}, m, bw.STRINGS, stemmap=sm))
            self.assertNotIn("Lead Synth", self._all_text(r), f"verdict {v} can't be trusted to name a part")
            self.assertIn("A new element is silent", r[3])    # falls through to neutral

    def test_does_not_cry_wolf_on_an_empty_artifact(self):
        # CR-1 "don't paint silence": a late spike that never clears the −55 dB real-content floor is a
        # separation artifact (Lazy_Sparks vocals: peak −61 dB, verdict 'empty'), not a musical event.
        # Per-band −69 → broadband peak ≈ −61 (< STEM_EMPTY_FLOOR_DB) → the card must NOT fire at all.
        m = self._late_masking(spike_db=-69.0)
        recs = bw.build_recommendations(_core(), {}, m, bw.STRINGS)
        self.assertIsNone(self._late_rec(recs),
                          "late_entry must not fire on a near-silent artifact stem (entering peak below floor)")


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G19 — PRECISE masking frequency (s14, idea a): the coarse band only says THAT the bass buries a
# part; the per-stem spectra say WHERE inside the band they fight, so the rec names a cut frequency
# ("≈380 Hz") instead of the whole "250–600 Hz". Defensible: the spot = worst spectral OVERLAP, and we
# only name it when the buried part actually has energy there; otherwise None → keep the band range.
# ──────────────────────────────────────────────────────────────────────────────────────────────
# A small synthetic log-freq spectrum grid (numpy-free), like masking's SPEC_CENTERS but local to the
# test so it doesn't pull the numpy-dependent masking module. 8 bins spanning the low_mid band + edges.
SPEC_FREQS = [60.0, 120.0, 200.0, 300.0, 380.0, 480.0, 700.0, 1200.0]
LOW_MID = (250, 600)


def _flat_spec(db=-40.0):
    return [float(db)] * len(SPEC_FREQS)


def _in_band_idx(band, freqs=SPEC_FREQS):
    lo, hi = band
    return [i for i, f in enumerate(freqs) if lo <= f < hi]


class G19_PreciseMaskingFreq(unittest.TestCase):
    def test_picks_the_worst_overlap_bin_in_band(self):
        idxs = _in_band_idx(LOW_MID)
        target = idxs[len(idxs) // 2]                         # some bin inside 250–600 Hz
        masker, maskee = _flat_spec(), _flat_spec()
        masker[target], maskee[target] = 0.0, -5.0           # both loud here → max min-overlap
        hz = bw.mask_collision_freq(masker, maskee, LOW_MID, SPEC_FREQS)
        self.assertEqual(hz, SPEC_FREQS[target])

    def test_freq_lands_inside_the_band(self):
        idxs = _in_band_idx(LOW_MID)
        masker, maskee = _flat_spec(-50.0), _flat_spec(-50.0)
        for i in idxs:                                        # plenty of in-band energy
            masker[i], maskee[i] = -3.0, -3.0
        hz = bw.mask_collision_freq(masker, maskee, LOW_MID, SPEC_FREQS)
        self.assertIsNotNone(hz)
        self.assertTrue(LOW_MID[0] <= hz < LOW_MID[1])

    def test_ignores_out_of_band_overlap(self):
        # a loud overlap OUTSIDE the band must not be chosen — only in-band bins count.
        masker, maskee = _flat_spec(-50.0), _flat_spec(-50.0)
        masker[0], maskee[0] = 0.0, 0.0                      # 60 Hz — below the band
        masker[4], maskee[4] = -2.0, -2.0                    # 380 Hz — in band, the only legit pick
        hz = bw.mask_collision_freq(masker, maskee, LOW_MID, SPEC_FREQS)
        self.assertEqual(hz, 380.0)

    def test_none_when_a_spectrum_is_silent(self):
        self.assertIsNone(bw.mask_collision_freq(None, _flat_spec(), LOW_MID, SPEC_FREQS))
        self.assertIsNone(bw.mask_collision_freq([None] * len(SPEC_FREQS), _flat_spec(), LOW_MID, SPEC_FREQS))

    def test_none_when_buried_part_is_barely_present(self):
        # the best in-band overlap bin still has the maskee well below its own peak → don't over-claim.
        target = _in_band_idx(LOW_MID)[0]
        masker, maskee = _flat_spec(-60.0), _flat_spec(-60.0)
        masker[target], maskee[target] = 0.0, bw.MASK_FREQ_MIN_LEVEL_DB - 6.0   # below the floor
        self.assertIsNone(bw.mask_collision_freq(masker, maskee, LOW_MID, SPEC_FREQS))

    def _rec_blob(self, with_spectrum):
        m = _masking({"bass": {"sub": -18, "low": -20, "low_mid": -22, "mid": -30, "hi_mid": -50, "air": -70},
                      "lead": {"sub": -80, "low": -70, "low_mid": -30, "mid": -28, "hi_mid": -44, "air": -70}})
        m["masking_summary"] = {"low_mid__lead": {"pct_masked": 18.0, "flagged_windows": 4,
                                                  "total_windows": 24, "mean_diff_db": 10.0}}
        m["masking_flags"] = {"low_mid__lead": [{"low_stem": "bass", "mid_stem": "lead", "time_s": 78.0,
                                                 "low_db": -22.0, "mid_db": -34.0, "diff_db": 12.0,
                                                 "window_idx": 15}]}
        if with_spectrum:
            bass, lead = _flat_spec(-50.0), _flat_spec(-50.0)
            bass[4], lead[4] = 0.0, -3.0                      # overlap peak at 380 Hz (index 4)
            m["spectrum"] = {"bass": bass, "lead": lead}
            m["spectrum_freqs"] = SPEC_FREQS
        ch = {"bass": {"label": "bass", "confidence": "clear"},
              "lead": {"label": "lead", "confidence": "approx"}}
        recs = bw.build_recommendations(_core(), {}, m, bw.STRINGS, character=ch)
        return " || ".join(r[1] + " " + r[2] + " " + r[3] + " " + r[4] for r in recs)

    def test_rec_names_precise_freq_when_spectra_pinpoint_it(self):
        blob = self._rec_blob(with_spectrum=True)
        self.assertIn("≈380 Hz", blob)

    def test_rec_falls_back_to_band_without_spectra(self):
        blob = self._rec_blob(with_spectrum=False)
        self.assertIn("250–600 Hz", blob)
        self.assertNotIn("≈", blob)


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G20 — per-stem repetition SURFACED as words (CR-6, credibility item (e), 0.8.18). The recurrence number
# was computed + carried but never spoken. Now one card contrasts the part that EVOLVES (low recurrence,
# carrying the development) with the ones that LOOP — named by character, never the raw Demucs name, and
# only when there's a real spread (someone clearly evolves AND someone clearly loops).
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G20_RepetitionSurfacing(unittest.TestCase):
    def setUp(self):
        self.m = _masking({"bass": -20, "drums": -22, "guitar": -24})
        self.ch = {"bass": {"label": "bass", "confidence": "clear"},
                   "drums": {"label": "drums", "confidence": "clear"},
                   "guitar": {"label": "guitar", "confidence": "approx"}}

    def _blob(self, repetition, character="default"):
        ch = self.ch if character == "default" else character
        recs = bw.build_recommendations(_core(), {}, self.m, bw.STRINGS,
                                        character=ch, repetition=repetition)
        return " || ".join(r[1] + " " + r[2] + " " + r[3] + " " + r[4] for r in recs)

    def test_recurrence_computed_from_each_stems_own_selfsim(self):
        pss = {"bass": _selfsim([0, 20, 40, 60, 80, 100], "ABCDE"),     # all distinct → evolves
               "drums": _selfsim([0, 20, 40, 60, 80, 100], "ABABA")}    # 2 labels / 5 segs → loops
        rep = {r["stem"]: r["recurrence"] for r in bw.stem_repetition(pss, self.m)}
        self.assertEqual(rep["bass"], 0.0)
        self.assertGreater(rep["drums"], 0.5)

    def test_card_fires_on_a_real_spread_and_names_parts(self):
        rep = [{"stem": "bass", "recurrence": 0.14}, {"stem": "drums", "recurrence": 0.55},
               {"stem": "guitar", "recurrence": 0.60}]
        blob = self._blob(rep)
        self.assertIn("carrying the development", blob)
        self.assertIn("bass", blob)        # the evolver
        self.assertIn("drums", blob)       # a looper
        self.assertIn("guitar", blob)      # a looper
        # C12: raw recurrence numbers are no longer shown in the card body (they were "(recurrence 0.14)")
        self.assertNotIn("0.14", blob, "raw recurrence numbers must not appear in card body (C12 fix)")

    def test_no_card_when_everything_loops(self):
        rep = [{"stem": "bass", "recurrence": 0.52}, {"stem": "drums", "recurrence": 0.55},
               {"stem": "guitar", "recurrence": 0.60}]
        self.assertNotIn("carrying the development", self._blob(rep))

    def test_no_card_when_nothing_loops(self):
        rep = [{"stem": "bass", "recurrence": 0.05}, {"stem": "drums", "recurrence": 0.10}]
        self.assertNotIn("carrying the development", self._blob(rep))

    def test_never_names_a_stem_without_a_character_label(self):
        # the would-be evolver has no character label → must be skipped, not named by its raw stem key.
        rep = [{"stem": "bass", "recurrence": 0.10}, {"stem": "drums", "recurrence": 0.55},
               {"stem": "guitar", "recurrence": 0.60}]
        ch = {"drums": {"label": "drums"}, "guitar": {"label": "guitar"}}   # no 'bass' label
        self.assertNotIn("carrying the development", self._blob(rep, character=ch))

    def test_no_card_without_character(self):
        rep = [{"stem": "bass", "recurrence": 0.14}, {"stem": "drums", "recurrence": 0.55}]
        self.assertNotIn("carrying the development", self._blob(rep, character=None))

    def test_dedupes_shared_loop_labels_no_salad(self):
        # two loopers share the 'mid' label (real on Lazy_Sparks: other+guitar) → "the mid, the mid" is the
        # salad we killed; must collapse to one "the mid".
        m = _masking({"bass": -20, "other": -22, "guitar": -24, "drums": -23})
        ch = {"bass": {"label": "bass"}, "other": {"label": "mid"},
              "guitar": {"label": "mid"}, "drums": {"label": "drums"}}
        rep = [{"stem": "bass", "recurrence": 0.14}, {"stem": "other", "recurrence": 0.50},
               {"stem": "guitar", "recurrence": 0.60}, {"stem": "drums", "recurrence": 0.54}]
        blob = bw.build_recommendations(_core(), {}, m, bw.STRINGS, character=ch, repetition=rep)
        text = " ".join(r[2] + " " + r[3] + " " + r[4] for r in blob)
        self.assertIn("carrying the development", text)
        self.assertNotIn("the mid, the mid", text)
        self.assertNotIn("the mid the mid", text)


# ──────────────────────────────────────────────────────────────────────────────────────────────
# G21 — "Where does it get boring?" (2026-06-22). For an EVOLVING track, the onset after which no
# NEW section is introduced (everything after only recombines earlier material). Measured from the self-sim
# segment letters; gated so it never fires on a track that doesn't develop, nor when new ideas keep arriving.
# ──────────────────────────────────────────────────────────────────────────────────────────────
class G21_DevelopmentPlateau(unittest.TestCase):
    def _plat(self, letters, dur=None):
        n = len(letters)
        dur = dur if dur is not None else n * 10.0
        edges = [round(i * dur / n, 2) for i in range(n + 1)]
        return bw.development_plateau(_selfsim(edges, letters), dur)

    def test_fires_when_it_develops_then_plateaus(self):
        # A B C D C D C : last NEW = D (4th of 7 segs) → tail 3/7 ≈ 0.43; 4 distinct sections.
        p = self._plat("ABCDCDC")
        self.assertIsNotNone(p)
        self.assertEqual(p["n_sections"], 4)
        self.assertGreaterEqual(p["tail_frac"], 0.30)
        self.assertAlmostEqual(p["onset_s"], 4 / 7 * 70.0, places=1)   # end of the 4th segment

    def test_none_when_new_material_keeps_arriving(self):
        self.assertIsNone(self._plat("ABCDE"))        # every section new → last-new at the very end
        self.assertIsNone(self._plat("ABCDEC"))       # a new E lands near the end → not a plateau

    def test_none_when_it_does_not_develop_enough(self):
        self.assertIsNone(self._plat("ABAB"))         # only 2 distinct sections
        self.assertIsNone(self._plat("AAAA"))         # 1 section

    def test_surfaced_as_a_timed_card(self):
        ss = _selfsim([0, 20, 40, 60, 80, 100, 120], "ABCDCD")
        core = {"duration_s": 120.0, "time_bins": [], "section_bounds_s": [], "energy": [], "energy_trend": None}
        recs = bw.build_recommendations(core, {}, None, bw.STRINGS, selfsim=ss)
        plat = [r for r in recs if "new ideas stop" in r[1]]
        self.assertEqual(len(plat), 1)
        self.assertIsNotNone(plat[0][5])              # anchored to the onset time on the timeline

    def test_no_card_without_selfsim(self):
        core = {"duration_s": 120.0, "time_bins": [], "section_bounds_s": [], "energy": [], "energy_trend": None}
        recs = bw.build_recommendations(core, {}, None, bw.STRINGS, selfsim=None)
        self.assertFalse([r for r in recs if "new ideas stop" in r[1]])


class EvalRecSpecificityMetrics(unittest.TestCase):
    """Guards the measuring stick used by scripts/eval_rec_specificity.py (NEXT_STEPS #2 eval), so the
    'per-stem is more specific' claim rests on a counting rule that means what it says."""
    def setUp(self):
        import eval_rec_specificity as ev
        self.ev = ev

    def _rec(self, text, t=None):
        return ("do", "H", text, "", "", t)   # (cls, header, title, body, fix, time)

    def test_counts_named_timed_freq(self):
        recs = [self._rec("the bass buries the mid around ≈270 Hz", t=78.0),  # named+timed+freq
                self._rec("energy is flat", t=None),                          # none of the three
                self._rec("the drums loop", t=12.0)]                          # named+timed
        m = self.ev._metrics(recs)
        self.assertEqual(m["total"], 3)
        self.assertEqual(m["named"], 2)
        self.assertEqual(m["timed"], 2)
        self.assertEqual(m["freq"], 1)

    def test_freq_regex_matches_hz_and_khz(self):
        self.assertTrue(self.ev.FREQ_RE.search("cut at ≈380 Hz"))
        self.assertTrue(self.ev.FREQ_RE.search("around ≈1.2 kHz here"))
        self.assertIsNone(self.ev.FREQ_RE.search("the 250–600 Hz band"))   # a plain band range, not a spot


class RecTargetCompleteness(unittest.TestCase):
    """INV-48a (SPEC §B.13, prover CN-3) — the evidence-target map is COMPLETE: every rec key
    with a based-on entry has an evidence target, and every target is a real panel id from the
    §B.13 map. Same completeness rule as the based-on line itself (INV-31)."""

    def test_every_based_key_has_a_target(self):
        missing = set(bw.REC_BASED) - set(bw.REC_TARGET)
        self.assertFalse(missing,
                         f"rec keys with a based-on line but NO evidence target: {sorted(missing)}")

    def test_targets_are_known_panels(self):
        bad = {k: v for k, v in bw.REC_TARGET.items() if v not in bw.EVIDENCE_TARGETS}
        self.assertFalse(bad, f"evidence targets outside the §B.13 map: {bad}")


if __name__ == "__main__":
    unittest.main()
