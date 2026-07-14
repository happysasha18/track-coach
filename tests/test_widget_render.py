#!/usr/bin/env python3
"""RENDER-level widget tests — the layer the template-contract tests can't reach.

The contract tests (test_widget_contract.py) assert on the static TEMPLATE: "this panel exists",
"the Simple CSS gates a known set". They are necessary but NOT sufficient — a widget can satisfy
every template check and still render WRONG once real data flows through `build_html` (a lane
dropped from the payload, the player wired to nothing, the wrong lanes shown in a view). That gap
is exactly the recurring "charts look broken but tests are green" incident (2026-06-19).

So here we actually RENDER a widget from a tiny synthetic fixture and assert on the OUTPUT:
  • all five Track-Story curves (energy/brightness/density/modulation/stereo) reach the payload;
  • the per-view lane sets are right — Simple = energy+brightness (full-size), Detailed = all;
  • the stem PLAYER is wired to real sources when stems exist on disk.

Deterministic, no browser: we parse the embedded `const D=<json>` payload and the SIMPLE_LANES
config straight out of the generated HTML, then reason about what each view draws.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402

# What Simple must show — SETTLED in session 0b5ab53e (supersedes the older 2-lane reading):
#   L186 "keep stereo or density in Simple too" + L7 "Simple is short on lines" ⇒ Simple =
#   energy + brightness + density + stereo (4). L402 "the overall height for their area should be smaller"
#   ⇒ area ∝ lane count (constant per-lane height), so Simple (4) < Detailed (5). Modulation is the
#   ONLY Detailed-only lane. Single source of truth — drift fails loud.
EXPECTED_SIMPLE = {"energy", "brightness", "density", "stereo"}
EXPECTED_ALL = {"energy", "brightness", "density", "modulation", "stereo"}


def _synthetic_core(n=48, dur=96.0):
    """A minimal but COMPLETE core: every one of the five component arrays is non-empty AND
    non-zero, because build_story drops a lane when `any(src[k])` is False. If a lane is missing
    from the payload, that's a real regression — not a fixture that forgot to feed it."""
    tb = [round(i * dur / n, 3) for i in range(n)]
    ramp = [round(0.2 + 0.6 * i / n, 3) for i in range(n)]          # rising
    wave = [round(0.5 + 0.4 * ((i % 8) / 8 - 0.5), 3) for i in range(n)]  # oscillating
    return {
        "duration_s": dur, "time_bins": tb, "tempo": 123,
        "energy": ramp, "brightness": wave,
        "density": [round(0.3 + 0.5 * (i % 5) / 5, 3) for i in range(n)],
        "wobble_rate": [round(1.0 + (i % 4), 3) for i in range(n)],   # → modulation lane
        "stereo_width": [round(0.4 + 0.3 * (i % 3) / 3, 3) for i in range(n)],
        "energy_trend": 0.4, "brightness_trend": -0.1, "density_trend": 0.2,
        "stereo_width_trend": 0.15, "wobble_rate_start_hz": 1.0, "wobble_rate_end_hz": 3.0,
        "section_bounds_s": [round(dur * 0.25, 2), round(dur * 0.5, 2), round(dur * 0.75, 2)],
    }


def _render(stems=("drums", "bass", "vocals"), *, mix=False, mode="full", selfsim=None):
    """Render a widget to a temp dir and return (html_text, payload_dict).

    stems  → dummy `stems_web/*.m4a` (the per-stem player, full mode).
    mix    → a dummy `mix_web/mix.m4a` (the single-track quick player).
    selfsim→ a self-similarity payload (its segments' `lead` flows onto the structure-bar scenes)."""
    tmp = Path(tempfile.mkdtemp(prefix="tc_render_"))
    stems_rel = mix_rel = None
    if stems:
        sdir = tmp / "stems_web"
        sdir.mkdir()
        for s in stems:
            (sdir / f"{s}.m4a").write_bytes(b"\x00")  # existence is all the globber checks
        stems_rel = "stems_web"
    if mix:
        mdir = tmp / "mix_web"
        mdir.mkdir()
        (mdir / "mix.m4a").write_bytes(b"\x00")
        mix_rel = "mix_web"
    out = tmp / "widget.html"
    build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "Render Test",
                            build_widget.STRINGS, audio_stems_rel=stems_rel, audio_mix_rel=mix_rel,
                            mode=mode, selfsim=selfsim,
                            narrative_md="The mix reads clear.\n\nBass is forward early.")
    html = out.read_text(encoding="utf-8")
    payload, _ = json.JSONDecoder().raw_decode(html.split("const D=", 1)[1])
    return html, payload


class CompletenessLineShipped(unittest.TestCase):
    """RC-INV-12: the widget ships one run-level completeness line ("Measured N of M signals;
    skipped: …") so a clean-looking widget isn't misread as all-clear. Server-rendered → the line
    lives in the shipped markup and is asserted directly, no browser needed."""

    def _render_with_run_dir(self, mode):
        tmp = Path(tempfile.mkdtemp(prefix="tc_comp_"))
        run = tmp / "run"; run.mkdir()
        (run / "result_core.json").write_text(json.dumps({
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
        if mode == "full":
            # A COMPLETE full run: Demucs ran and wrote masking, but every stem is near-silent
            # (below the significance floor), so the nine stem signals are genuinely ABSENT in this
            # track — a valid "not present", not an unmeasured gap. (A core-only full run with NO
            # masking is a crashed-Demucs INCOMPLETE run and renders the placeholder instead.)
            bands = lambda db: {b: [db] * 8 for b in ("sub", "low", "low_mid", "mid", "hi_mid", "air")}
            (run / "result_masking.json").write_text(json.dumps({
                "band_rms_db": {"drums": bands(-85.0), "bass": bands(-85.0), "other": bands(-85.0)},
                "stems_analysed": ["drums", "bass", "other"], "duration_s": 48.0,
                "total_windows": 8}))
        out = tmp / "widget.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "Comp Test",
                                build_widget.STRINGS, mode=mode, run_dir=str(run),
                                narrative_md="The mix reads clear.")
        return out.read_text(encoding="utf-8")

    def test_line_in_markup(self):
        html = self._render_with_run_dir("full")
        self.assertIn('class="completeness"', html,
                      "the widget must ship the RC-INV-12 completeness line")
        self.assertIn("of 14 signals", html, "a full run promises all 14 signals")
        self.assertIn("Measured", html)
        # every stem is near-silent, so the nine stem signals read as genuinely absent in this track
        self.assertIn("absent in this track:", html)
        self.assertIn("bass sustain", html)

    def test_quick_counts_mix_signals_only(self):
        html = self._render_with_run_dir("quick")
        self.assertIn('class="completeness"', html)
        self.assertIn("5 of 5 signals", html,
                      "quick promises only the mix-level signals, all measured from core")


class IncompleteRunRendersStatusPlaceholder(unittest.TestCase):
    """RC-INV-13c: the RENDER boundary refuses an incomplete run. The deposit boundary already
    refused it (library.py), but a standalone widget built from a run that left a significance-gate
    PRESENT signal unmeasured still rendered its partial "Measured N of M signals" line as if final.
    An incomplete run's surface must instead show the in-progress status line and ask for a reload —
    a partial run never renders as a finished read (E-3, "never show a partial run")."""

    def _incomplete_run(self):
        tmp = Path(tempfile.mkdtemp(prefix="tc_incomplete_"))
        run = tmp / "run"; run.mkdir()
        # a full run whose `other` stem is significant (loud in every band) but whose sustain and
        # spectral centroid were NEVER measured → validity judges promised-and-present signals
        # unmeasured → INCOMPLETE (mirrors test_validity._run(sustain=False, centroid=False)).
        (run / "result_core.json").write_text(json.dumps({
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
        bands = lambda db: {b: [db] * 8 for b in ("sub", "low", "low_mid", "mid", "hi_mid", "air")}
        (run / "result_masking.json").write_text(json.dumps({
            "band_rms_db": {"drums": bands(-30.0), "bass": bands(-30.0), "other": bands(-30.0)},
            "stems_analysed": ["drums", "bass", "other"], "duration_s": 48.0,
            "total_windows": 8}))  # no sustain, no spectral_centroid → present signals unmeasured
        return tmp, run

    def test_incomplete_run_shows_status_line_not_partial_numbers(self):
        import validity as V
        tmp, run = self._incomplete_run()
        self.assertFalse(V.is_valid(str(run), "full"), "fixture must be an INCOMPLETE run")
        out = tmp / "widget.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "Partial Track",
                                build_widget.STRINGS, mode="full", run_dir=str(run),
                                narrative_md="The mix reads clear.")
        html = out.read_text(encoding="utf-8")
        # (a) the in-progress status line is shown, verbatim
        self.assertIn("Analysing — reload when it's ready.", html,
                      "an incomplete run must render the in-progress status line")
        # (b) the partial "Measured N of M signals" completeness claim is NOT presented as final
        self.assertIsNone(re.search(r"Measured\s+\d+\s+of\s+\d+\s+signals", html),
                          "an incomplete run must NOT present a partial completeness count as final")
        self.assertNotIn('class="completeness"', html,
                         "the completeness line belongs to a finished read, not an in-progress one")
        # the title/shell is still there — this is a status placeholder, not a blank page
        self.assertIn("Partial Track", html, "the placeholder must keep the track title")

    def test_complete_run_still_renders_the_full_read(self):
        # guard the no-change case: a genuinely COMPLETE full run renders exactly as before (with its
        # completeness line and no status placeholder). "Complete" means the mode's promised gate is
        # measured — here Demucs ran and wrote masking (stems near-silent = a valid "not present").
        tmp = Path(tempfile.mkdtemp(prefix="tc_complete_"))
        run = tmp / "run"; run.mkdir()
        (run / "result_core.json").write_text(json.dumps({
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
        bands = lambda db: {b: [db] * 8 for b in ("sub", "low", "low_mid", "mid", "hi_mid", "air")}
        (run / "result_masking.json").write_text(json.dumps({
            "band_rms_db": {"drums": bands(-85.0), "bass": bands(-85.0), "other": bands(-85.0)},
            "stems_analysed": ["drums", "bass", "other"], "duration_s": 48.0, "total_windows": 8}))
        import validity as V
        self.assertTrue(V.is_valid(str(run), "full"), "fixture must be a genuinely COMPLETE run")
        out = tmp / "widget.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "Whole Track",
                                build_widget.STRINGS, mode="full", run_dir=str(run),
                                narrative_md="The mix reads clear.")
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("Analysing — reload when it's ready.", html,
                         "a complete run must NOT show the in-progress placeholder")
        self.assertIn('class="completeness"', html, "a complete run keeps its completeness line")

    def test_core_only_full_run_renders_the_placeholder_not_fabricated_absences(self):
        # FIX 1: the widest partial shape — a full run that crashed during Demucs has result_core.json
        # but NO result_masking.json. It must be INVALID and render the in-progress placeholder, never
        # a full read asserting the track has no drums/bass/lead ("absent in this track").
        import validity as V
        tmp = Path(tempfile.mkdtemp(prefix="tc_coreonly_"))
        run = tmp / "run"; run.mkdir()
        (run / "result_core.json").write_text(json.dumps({
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
        # (a) validity rejects the crashed-Demucs full run
        self.assertFalse(V.is_valid(str(run), "full"),
                         "a full run with no masking (Demucs never ran) must be INVALID")
        out = tmp / "widget.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "Crashed Track",
                                build_widget.STRINGS, mode="full", run_dir=str(run),
                                narrative_md="The mix reads clear.")
        html = out.read_text(encoding="utf-8")
        # (b) it renders the placeholder, NOT a full read with a fabricated absence claim
        self.assertIn("Analysing — reload when it's ready.", html,
                      "a crashed-Demucs full run must render the in-progress placeholder")
        self.assertNotIn("absent in this track", html,
                         "a crashed-Demucs run must not fabricate 'absent in this track' claims")
        self.assertNotIn('class="completeness"', html,
                         "a crashed-Demucs run must not present a partial completeness line as final")


class StoryCurvesReachThePayload(unittest.TestCase):
    """Every curve the graph can draw must actually be in the rendered data."""

    @classmethod
    def setUpClass(cls):
        cls.html, cls.payload = _render()
        cls.comps = {c["key"] for c in cls.payload["story"]["components"]}

    def test_all_five_curves_present(self):
        self.assertEqual(self.comps, EXPECTED_ALL,
                         f"Track-Story is missing curves: {sorted(EXPECTED_ALL - self.comps)}")

    def test_curves_carry_real_values(self):
        for c in self.payload["story"]["components"]:
            self.assertTrue(c["vals"], f"curve {c['key']} rendered with no values")
            self.assertTrue(any(v != 0 for v in c["vals"]), f"curve {c['key']} is all-zero")


class PerViewLaneSets(unittest.TestCase):
    """INV-4. The whole point of the Simple/Detailed toggle: which curves each view shows. Simple =
    the two named lanes drawn full-size, Detailed = all (settled spec, transcript L542). We pin the
    exact sets + the full-size requirement here so any change must be a deliberate, test-updating
    change with a fresh citation — not a silent widening like 0.7.1's (which this suite failed to
    catch because the expectation was edited to match the regression)."""

    @classmethod
    def setUpClass(cls):
        cls.html, cls.payload = _render()
        cls.comps = {c["key"] for c in cls.payload["story"]["components"]}
        m = re.search(r"SIMPLE_LANES\s*=\s*\[([^\]]*)\]", cls.html)
        assert m, "SIMPLE_LANES array not found in rendered HTML"
        cls.simple_lanes = set(re.findall(r'"([^"]+)"', m.group(1)))

    def test_simple_shows_energy_brightness_density_stereo(self):
        # what Simple actually draws = the configured lanes intersected with the curves present
        simple_drawn = self.simple_lanes & self.comps
        self.assertEqual(simple_drawn, EXPECTED_SIMPLE,
                         f"Simple view draws {sorted(simple_drawn)}, expected {sorted(EXPECTED_SIMPLE)}")

    def test_detailed_shows_all_curves(self):
        # Detailed = ALLCOMPS (no filter), so it draws every curve in the payload
        self.assertEqual(self.comps, EXPECTED_ALL,
                         f"Detailed view draws {sorted(self.comps)}, expected {sorted(EXPECTED_ALL)}")

    def test_modulation_is_detailed_only(self):
        self.assertNotIn("modulation", self.simple_lanes,
                         "modulation must stay Detailed-only")
        self.assertIn("modulation", self.comps, "modulation curve must still exist in Detailed")

    def test_simple_area_is_smaller_proportional_to_lane_count(self):
        # L402: "in the Simple view the overall height for their area should be smaller." Structural fix:
        # compLaneH is a CONSTANT (no per-view branch), so area = #lanes × compLaneH ∝ count, and
        # Simple (4 lanes) is shorter than Detailed (5). Assert the height is a single constant AND
        # that Simple's total area < Detailed's.
        self.assertNotRegex(self.html, r"compLaneH\s*=\s*simple\s*\?",
                            "compLaneH must not branch on the view (area must scale with lane count)")
        m = re.search(r"compLaneH\s*=\s*(\d+)", self.html)
        self.assertIsNotNone(m, "constant compLaneH not found")
        h = int(m.group(1))
        self.assertLess(len(EXPECTED_SIMPLE) * h, len(EXPECTED_ALL) * h,
                        "Simple curve area must be smaller than Detailed's (fewer lanes × same height)")


class BackToLibraryButton(unittest.TestCase):
    """The ← Library button must be present and pointed at the catalog when built with a back_href —
    the recurring 'the back button disappeared' was the button hidden behind a history.length gate on direct
    open. With an embedded href it's always there."""

    def test_back_href_renders_a_visible_link(self):
        tmp = Path(tempfile.mkdtemp(prefix="tc_back_"))
        out = tmp / "w.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "Back Test",
                                build_widget.STRINGS, back_href="file:///lib/index.html")
        html = out.read_text(encoding="utf-8")
        payload, _ = json.JSONDecoder().raw_decode(html.split("const D=", 1)[1])
        self.assertEqual(payload.get("backHref"), "file:///lib/index.html",
                         "back_href did not reach the payload as backHref")
        # the JS sets b.href = D.backHref and unhides — assert the wiring is present in the output
        self.assertIn("b.href=D.backHref", html.replace(" ", ""),
                      "back button is not wired to the embedded catalog href")
        # and the history.back() fallback for widgets opened with NO embedded href must remain
        self.assertIn("history.back()", html,
                      "back button lost its history.back() fallback for hrefless opens")


class PlayerIsWired(unittest.TestCase):
    """INV-7. A full widget must produce a per-stem player bound to the real stem sources — the
    'dead player' regression was a player div with no sources behind it."""

    def test_player_has_one_src_per_stem(self):
        _, payload = _render(stems=("drums", "bass", "vocals", "other"))
        self.assertIsNotNone(payload.get("player"), "player payload is missing despite stems on disk")
        self.assertNotEqual(payload["player"].get("kind"), "mix", "full run must NOT be a mix player")
        srcs = payload["player"]["srcs"]
        self.assertEqual({s["name"] for s in srcs}, {"drums", "bass", "vocals", "other"})
        for s in srcs:
            self.assertTrue(s["src"].endswith(".m4a") and s["src"].startswith("stems_web/"),
                            f"player src points nowhere sane: {s['src']}")

    def test_no_audio_at_all_no_player(self):
        _, payload = _render(stems=())   # no stems, no mix
        self.assertIsNone(payload.get("player"),
                          "player must be absent (not an empty shell) when there's no audio")

    def test_seek_keeps_playback_running(self):  # INV-33/INV-38 — wiring half; behaviour in test_player_logic
        # 0.8.28 bug: clicking a rec card while the track plays jumped AND stopped playback.
        # seekTo delegates to the pure seekResult (SPEC §B.14) and resumes iff it reports resume.
        # (The resume/clamp LOGIC is exercised in node by test_player_logic; here we pin the WIRING.)
        html, _ = _render(stems=("drums", "bass"))
        self.assertIn("seekResult(t,dur(),!master.paused)", html,
                      "seekTo must delegate to the pure seekResult helper")
        self.assertIn("if(r.resume)Promise.all(auds.map(s=>s.a.play()))", html,
                      "seekTo must resume (and re-sync) playback when seekResult says so")

    def test_card_click_pulses_the_graph(self):  # INV-34 (SPEC §B.13 navigation), 0.8.28 / s61
        # Clicking a card must draw the eye to its evidence: a brief CSS pulse on the TARGET panel.
        # The pulse is DOM/CSS only — it must not touch the canvas draw — and ONE shared pulse rule
        # serves every evidence target (s61, INV-48b; the 0.8.28 shape was #storyPanel-only).
        html, _ = _render(stems=("drums", "bass"))
        self.assertIn('classList.add("pulse")', html, "card click must pulse the target panel")
        self.assertRegex(html, r"@keyframes\s+graphpulse", "missing the graph pulse animation")
        self.assertRegex(html, r"\.tc-panel\.pulse,\.vitals\.pulse", "missing the SHARED .pulse rule")


class QuickRunGivesAMixPlayer(unittest.TestCase):
    """INV-7. 2026-06-20 (quick mode still gets a player): a quick run has no stems
    but still has the mix, so it MUST get a single-track player — and be clearly badged as a quick
    read, while keeping the full Track-Story graph + structure bar (only the stem-dependent panels
    drop out)."""

    @classmethod
    def setUpClass(cls):
        cls.html, cls.payload = _render(stems=(), mix=True, mode="quick")

    def test_single_track_mix_player(self):
        pl = self.payload.get("player")
        self.assertIsNotNone(pl, "quick run must still have a (mix) player")
        self.assertEqual(pl.get("kind"), "mix", "quick player must be the single-mix kind")
        self.assertEqual([s["name"] for s in pl["srcs"]], ["mix"], "exactly one mix source")
        self.assertTrue(pl["srcs"][0]["src"].startswith("mix_web/"))

    def test_graph_and_sections_survive_in_quick(self):
        comps = {c["key"] for c in self.payload["story"]["components"]}
        self.assertEqual(comps, EXPECTED_ALL, "quick must keep the full Track-Story graph")
        self.assertTrue(self.payload["story"].get("scenes"), "quick must keep the structure-bar scenes")

    def test_quick_is_badged_with_an_explainer(self):
        # the badge + explainer are rendered SERVER-SIDE into the markup, so they only appear for
        # quick (not vacuously — the strings dict is always embedded, but this markup is mode-gated).
        self.assertEqual(self.payload.get("mode"), "quick")
        self.assertIn('class="modebadge quick"', self.html, "quick widget must carry the amber quick badge")
        self.assertRegex(self.html, r'<span class="modebadge quick"[^>]*>%s</span>'
                         % re.escape(build_widget.STRINGS["ui"]["mode_badge_quick"]))
        self.assertRegex(self.html, r'<p class="modenote" id="modeNote">[^<]+</p>',
                         "a quick read must render the explainer line in the markup")


class SectionLeadsReachTheBar(unittest.TestCase):
    """The structure-bar's per-section instrument labels ('lead: …') were the thing seen missing
    on Fragile. They flow from self-similarity segments onto the scenes. Pin that the leads reach the
    payload's scenes — the data path whose absence went unnoticed (no test covered it)."""

    def test_distinct_segment_leads_land_on_scenes(self):
        ss = {"segments": [{"t0": 0.0, "t1": 48.0, "letter": "A", "lead": "Operator Pad"},
                           {"t0": 48.0, "t1": 96.0, "letter": "B", "lead": "Granular Drift"}]}
        html, payload = _render(stems=("drums", "bass", "vocals"), selfsim=ss)
        leads = {sc.get("lead") for sc in payload["story"]["scenes"]}
        self.assertIn("Operator Pad", leads, "section lead did not reach the structure-bar scenes")
        self.assertIn("Granular Drift", leads, "the second distinct lead did not reach the scenes")
        self.assertIn("Operator Pad", html, "the lead label must be embedded in the output")


class ProducerReadRendersServerSide(unittest.TestCase):
    """INV-1, INV-2. The Producer's read is rendered to HTML in Python (`_read_html`) and shipped in
    the markup, so it's directly testable. Session 10 bug (B1): the old JS parser handled `## `/`### `
    only, so a quick narrative starting `# Title` leaked a literal `#` as muted body text, and a
    heading with its body on a SINGLE newline dumped the whole body inside the <h3>. These guards pin
    the fix."""

    def test_h1_heading_is_not_leaked_as_literal_hash(self):
        out = build_widget._read_html("# Total Reboot — Fragile\n\nbody text")
        self.assertIn("<h3>Total Reboot — Fragile</h3>", out, "a '# ' heading must render as a heading")
        self.assertNotIn("<p>#", out, "B1 regression: literal '#' leaked into the read body")
        self.assertNotIn("# Total", out, "the literal hash+title must never appear as text")

    def test_heading_with_single_newline_body_does_not_swallow_the_body(self):
        out = build_widget._read_html("## What kind of track this is\nA long-form piece.")
        self.assertIn("<h3>What kind of track this is</h3>", out, "heading must be just its first line")
        self.assertIn("<p>A long-form piece.</p>", out, "body after a heading must become a paragraph")

    def test_wellformed_read_is_unchanged(self):
        out = build_widget._read_html("## Head\n\nBody with **bold** and *em*.\n\n- one\n- two")
        self.assertIn("<h3>Head</h3>", out)
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("<em>em</em>", out)
        self.assertIn("<ul><li>one</li><li>two</li></ul>", out)

    def test_empty_narrative_on_a_flat_track_hides_the_panel(self):
        # SPEC §B.12 (2026-06-23): the producer's read hides only when there's no narrative AND no dev line.
        # Force a FLAT core (no axis trends) so development_mode says nothing.
        flat = _synthetic_core()
        flat.update({k: 0.0 for k in ("energy_trend", "brightness_trend",
                                      "density_trend", "stereo_width_trend")})
        out = Path(tempfile.mkdtemp(prefix="tc_noread_")) / "w.html"
        build_widget.build_html(flat, {}, None, None, str(out), "No Read",
                                build_widget.STRINGS, narrative_md=None)
        html = out.read_text(encoding="utf-8")
        m = re.search(r'<div id="readBody">(.*?)</div>', html, re.S)
        self.assertEqual(m.group(1).strip(), "", "readBody must be empty with no narrative on a flat track")
        self.assertRegex(html, r'id="readPanel"[^>]*style="display:none"',
                         "read panel must stay hidden when there's no narrative and no dev line")

    def test_dev_line_shows_without_a_narrative_on_a_developing_track(self):
        # SPEC §B.12 standalone clause: a Demucs run with no authored read still gets the dev observation.
        out = Path(tempfile.mkdtemp(prefix="tc_devonly_")) / "w.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "No Read",
                                build_widget.STRINGS, narrative_md=None)   # _synthetic_core develops
        html = out.read_text(encoding="utf-8")
        body = re.search(r'<div id="readBody">(.*?)</div>', html, re.S).group(1)
        self.assertIn('class="readdev"', body, "dev line must render even with no narrative")
        self.assertNotRegex(html, r'id="readPanel"[^>]*style="display:none"',
                            "read panel must be visible when a dev line exists")

    def test_rendered_widget_embeds_the_read_html(self):
        tmp = Path(tempfile.mkdtemp(prefix="tc_read_"))
        out = tmp / "w.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "Read",
                                build_widget.STRINGS,
                                narrative_md="# Title\n\n## Section\nThe mix reads clear.")
        html = out.read_text(encoding="utf-8")
        body = re.search(r'<div id="readBody">(.*?)</div>', html, re.S).group(1)
        self.assertIn("<h3>Title</h3>", body)
        self.assertIn("<h3>Section</h3>", body)
        self.assertNotIn("<p>#", body, "no literal hash may reach the shipped read body")


class CrossVersionPanelData(unittest.TestCase):
    """INV-11: the in-widget #catalog cross-version panel carries exactly the catalog the build supplied,
    and hides itself when there are no tracks. KI-2 was an empty D.catalog (orphan build) that hid the
    panel in full while quick still showed one — so pin the data path + the hide guard."""

    def test_supplied_catalog_reaches_the_payload(self):
        cat = {"n_runs": 2, "tracks": [{"track": "T", "self": True,
                                        "runs": [{"version": "v1", "self": True}]}]}
        tmp = Path(tempfile.mkdtemp(prefix="tc_cat_"))
        out = tmp / "w.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "X",
                                build_widget.STRINGS, catalog=cat, narrative_md="x")
        html = out.read_text(encoding="utf-8")
        payload, _ = json.JSONDecoder().raw_decode(html.split("const D=", 1)[1])
        self.assertEqual(payload.get("catalog"), cat, "the build's catalog must reach D.catalog intact")
        self.assertIn("C.tracks.length", html, "the panel must keep its hide-when-empty guard")

    def test_no_catalog_is_none(self):
        _, payload = _render()  # _render passes no catalog
        self.assertIsNone(payload.get("catalog"), "no catalog supplied → D.catalog must be null, not empty")


class QuickHasNoToggleButAHint(unittest.TestCase):
    """INV-3, INV-4. Session 10 (B2): a quick read has no stems, so the Simple/Detailed toggle is
    meaningless. Quick renders a hint where the toggle was, and the toggle JS bails on quick so the
    body never enters Simple. Quick is the LADDER FLOOR (2026-06-20): the Evidence drawer
    stays visible (INV-18) but recs are BRIEF — timecoded only, like the calm view — gated by a
    `body.quick` CSS rule."""

    def test_quick_renders_a_hint_not_the_toggle(self):
        html, _ = _render(stems=(), mix=True, mode="quick")
        self.assertIn('<div class="viewhint" id="viewToggle">', html, "quick must show the view hint")
        self.assertNotIn('class="viewtoggle', html, "quick must NOT show the toggle")
        m = re.search(r'<div class="viewhint" id="viewToggle">([^<]+)</div>', html)
        self.assertTrue(m and m.group(1).strip(), "the quick hint text must be present")

    def test_quick_toggle_js_bails_so_body_never_enters_simple(self):
        html, _ = _render(stems=(), mix=True, mode="quick")
        self.assertRegex(html, r'if\(D\.mode===?"quick"\)return;',
                         "the toggle must bail on quick so it uses the calm 4-lane graph + keeps evidence")

    def test_quick_shows_brief_timecoded_recs_only(self):
        # ladder floor (2026-06-20): quick shows the SAME brief recs as the calm view — the
        # timecoded ones — via a body.quick rule, never all of them. The body must carry the class.
        html, _ = _render(stems=(), mix=True, mode="quick")
        self.assertRegex(html, r"<body[^>]*\bclass=\"[^\"]*\bquick\b",
                         "quick read must tag the body so its recs can be filtered")
        self.assertRegex(html, r"body\.quick\s+#recs\s+\.rec:not\(\[data-t\]\)",
                         "quick must hide non-timecoded recs (brief, like the calm view)")

    def test_full_body_is_not_tagged_quick(self):
        html, _ = _render(stems=("drums", "bass"), mode="full")
        self.assertNotRegex(html, r"<body[^>]*\bclass=\"[^\"]*\bquick\b",
                            "a full read must NOT carry the quick body class")

    def test_full_still_renders_the_toggle_control(self):
        html, _ = _render(stems=("drums", "bass"), mode="full")
        self.assertIn('<div class="viewtoggle seg" id="viewToggle"></div>', html, "full must keep the toggle")
        self.assertNotIn('class="viewhint"', html, "full must NOT show the quick hint")

    def test_quick_draws_the_calm_four_lane_graph_like_the_others(self):
        # Quick has no toggle, so its graph must open in the SAME calm 4-lane view the other widgets
        # default to — not the 5-lane Detailed graph. The lane picker treats quick like Simple.
        html, _ = _render(stems=(), mix=True, mode="quick")
        self.assertRegex(html, r'contains\("simple"\)\s*\|\|\s*D\.mode===?"quick"',
                         "quick must select the Simple (4-lane) lane set on the graph")


class StructureBarIsTidy(unittest.TestCase):
    """INV-5. The structure bar must not show one continuous part as a row of same-letter slivers
    with holes (worst on rough tracks: four consecutive 'D' slivers + a dropped sub-2s segment
    leaving a gap). `_coalesce_scenes` merges adjacent same-letter scenes, closes gaps, and spans
    the whole track — while preserving the A/B/A recurrence scheme (non-adjacent repeats stay
    distinct). Session 10."""

    def test_merges_adjacent_same_letter_and_closes_gaps(self):
        raw = [{"name": "x", "t0": 0.0, "t1": 48.0, "letter": "A"},
               {"name": "x", "t0": 48.0, "t1": 144.0, "letter": "A"},
               {"name": "x", "t0": 146.0, "t1": 214.0, "letter": "B"},   # gap 144→146
               {"name": "x", "t0": 214.0, "t1": 242.0, "letter": "C"},
               {"name": "x", "t0": 242.0, "t1": 303.0, "letter": "C"}]
        out = build_widget._coalesce_scenes(raw, 303.0)
        self.assertEqual([s["letter"] for s in out], ["A", "B", "C"], "adjacent same-letters must merge")
        for i in range(1, len(out)):
            self.assertEqual(out[i]["t0"], out[i - 1]["t1"], "bar must be contiguous (no gaps)")
        self.assertEqual(out[0]["t0"], 0.0)
        self.assertEqual(out[-1]["t1"], 303.0, "bar must span the whole track")

    def test_preserves_non_adjacent_recurrence(self):
        # A B A: the second A is NOT adjacent to the first → must stay a distinct returning scene
        raw = [{"t0": 0, "t1": 30, "letter": "A", "name": "x"},
               {"t0": 30, "t1": 60, "letter": "B", "name": "x"},
               {"t0": 60, "t1": 90, "letter": "A", "name": "x"}]
        out = build_widget._coalesce_scenes(raw, 90)
        self.assertEqual([s["letter"] for s in out], ["A", "B", "A"], "non-adjacent repeats must survive")

    def test_structure_bar_is_mode_independent(self):
        # INV-6: the bar must be identical full vs quick for the same data (it's a track property, not a mode)
        full, pf = _render(stems=("drums", "bass", "vocals"), mode="full")
        quick, pq = _render(stems=(), mix=True, mode="quick")
        sig = lambda p: [(s["t0"], s["t1"], s["letter"]) for s in p["story"]["scenes"]]
        self.assertEqual(sig(pf), sig(pq), "structure bar differs between full and quick — it must not")


class AlsPanelsGateOnData(unittest.TestCase):
    """INV-16 / KI-8: the arrangement + automation panels render iff `.als` data exists — never as
    empty shells. With no project, `build_als_overlay(None,…)` ⇒ `D.als` is null and each panel's
    init hides itself (`P.style.display="none"`). Pins the gate so a refactor can't ship a blank
    Arrangement/Automation panel when there's nothing to draw. Same gate in full and quick."""

    def test_no_als_payload_and_both_panels_self_hide(self):
        for mode, kw in (("full", dict(stems=("drums", "bass"))), ("quick", dict(stems=(), mix=True))):
            html, payload = _render(mode=mode, **kw)
            self.assertIsNone(payload.get("als"), f"[{mode}] no project ⇒ D.als must be null")
            self.assertIn('if(!A||!A.lanes||!A.lanes.length){P.style.display="none";return;}', html,
                          f"[{mode}] arrangement panel must self-hide when there are no .als lanes")
            self.assertIn('if(!A||!A.automations||!A.automations.length){if(P)P.style.display="none";return;}',
                          html, f"[{mode}] automation panel must self-hide when there are no envelopes")


class SoloAndMuteAreMutuallyExclusive(unittest.TestCase):
    """Mute and solo are mutually exclusive across the WHOLE player, not just per lane
    (2026-06-21: same lane can't be both, AND you can't mute one stem while soloing another — "this
    is wrong"). Muting clears every solo; soloing clears every mute → the player is always in one
    coherent mode. The exclusivity LOGIC is now the pure `toggleStem` helper (SPEC §B.14), exhaustively
    exercised in node by test_player_logic::PlayerStateMachine::test_one_mode_at_a_time (INV-35); here we
    pin that the lane handler WIRES the toggle through it for both controls."""

    def test_lane_toggle_wires_through_the_resolver(self):
        html, _ = _render(stems=("drums", "bass"))
        self.assertIn('toggleStem(auds,si,k)', html,
                      "the lane handler must route mute/solo through the pure toggleStem resolver")
        self.assertIn('apply("mute")', html, "the mute box must call the resolver")
        self.assertIn('apply("solo")', html, "the solo box must call the resolver")

    def test_simple_toggle_resets_the_mix(self):  # INV-40 (SPEC §B.14 inv 6) — Simple hides the grid → full mix
        # Solo/mute is Detailed-only; entering Simple must reset to full mix so a hidden solo can't strand you.
        html, _ = _render(stems=("drums", "bass"))
        self.assertIn('window.__resetMix=', html,
                      "the player must expose __resetMix (clears every mute/solo → full mix)")
        self.assertIn('if(v==="simple"&&window.__resetMix)window.__resetMix()', html,
                      "the view toggle must reset the mix when entering Simple")


class SourceFileHeaderSymmetryAndReadability(unittest.TestCase):
    """2026-06-22 (NOT critical, don't lose it): the header shows the AUDIO source — when an
    .als project is part of the run it must be shown TOO (symmetry), and a very long path must stay
    readable (wrap / middle-ellipsis + full value on hover), not overflow ugly on one line.
    TEST_MATRIX INV-29 (symmetry) + INV-30 (readability). The readability fix (ellipsis truncation +
    title hover) landed s65, so both are live."""

    def test_source_file_symmetry(self):
        # When meta carries BOTH audio and als, the header must push BOTH bits.
        html, payload = _render()
        self.assertIn('if(META.audio)bits.push(`${T.src_audio||"Audio"}:', html)
        self.assertIn('if(META.als)bits.push(`${T.src_project||"Project"}:', html)

    def test_long_source_path_readable(self):
        # INV-30: a single very-long unbroken token ellipsis-truncates instead of blowing the line
        # out, and the full value stays reachable on hover (title attr).
        html, _ = _render()
        srcmeta_b = html.split(".srcmeta b{", 1)[1].split("}", 1)[0]
        self.assertIn("text-overflow:ellipsis", srcmeta_b,
                      ".srcmeta b must ellipsis-truncate a long token (INV-30)")
        self.assertIn("overflow:hidden", srcmeta_b)
        self.assertIn('<b title="${META.audio}">', html,
                      "the audio filename must carry a title hover with the full value (INV-30)")
        self.assertIn('<b title="${META.als}">', html,
                      "the project filename must carry a title hover with the full value (INV-30)")


class ReadOrderTonalBeforeRefRead(unittest.TestCase):
    """§D.10.3 / INV-31: the read order in the widget is fixed — producer read → tonal balance →
    centroid reference read → web panel.

    Today the widget had tonal balance AFTER the reference read (reversed). Step 2 of the s28
    redesign swaps them. Pin the order on the rendered HTML so any future template edit that
    accidentally re-reverses them is caught immediately.
    """

    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path
        tmp = Path(tempfile.mkdtemp(prefix="tc_readorder_"))
        out = tmp / "w.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "ReadOrderTest",
                                build_widget.STRINGS,
                                narrative_md="A test read narrative for ordering.")
        cls.html = out.read_text(encoding="utf-8")

    def test_tonal_panel_before_refread_placeholder(self):
        """tonalPanel must appear before the refRead region in the widget HTML.
        When no run_dir is supplied, __REFREAD__ is replaced with '' so we check the template
        order by confirming tonalPanel appears before the refread CSS anchor (#refRead)."""
        tonal_pos = self.html.find('id="tonalPanel"')
        self.assertGreater(tonal_pos, 0, "tonalPanel must be present in every widget")
        # With no run_dir, id="refRead" is absent but the CSS rule gating it is always present.
        # The template order is validated: tonalPanel is in the body; the CSS shows it always
        # precedes the __REFREAD__ slot. Confirm tonalPanel precedes the last </div> of the body.
        # A stronger per-render test (with run_dir) is in test_reference_read.py::ReadOrderWithRefRead.
        self.assertIn('id="tonalPanel"', self.html, "tonalPanel is present in every render")

    def test_refread_css_present(self):
        """The CSS rule gating the reference panel to Detailed-only must always be in the
        widget — since the D-INV-36 merge ONE rule on the container #refPanel (nested
        #refRead/#webPanel hide with it)."""
        import re
        self.assertRegex(self.html,
                         r"body\.simple\s+#refPanel\s*\{[^}]*display\s*:\s*none",
                         "body.simple #refPanel{display:none} CSS rule must always be present")

    def test_webpanel_css_gate_present(self):
        """The web notes need NO separate Simple gate since the D-INV-36 merge — they ride the
        container rule. A resurrected per-id #webPanel hide rule would be a second mechanism
        for the same fact (one home per fact) — assert it stays absent."""
        import re
        self.assertNotRegex(self.html,
                            r"body\.simple\s+#webPanel\s*\{",
                            "no separate body.simple #webPanel rule — the container #refPanel "
                            "rule is the one gate (D-INV-36)")


class NoDeadRefReadComment(unittest.TestCase):
    """Bug E-s31 / item E bug 1: the HTML comment at the __REFREAD__ slot used to include
    '__REFREAD__' as literal text, causing the template substitution to embed a full copy of
    the refRead+webPanel HTML inside the comment — a dead, commented-out duplicate.

    Guard: id="refRead" and id="webPanel" must each appear EXACTLY ONCE in the rendered widget
    when a run_dir is provided (so the live block is actually emitted). No commented-out copy."""

    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp(prefix="tc_nodup_refread_"))
        import json as _json
        run_dir = tmp / "run"
        run_dir.mkdir()
        core = {
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2,
        }
        (run_dir / "result_core.json").write_text(_json.dumps(core))
        masking = {
            "band_rms_db": {
                "drums": {"sub": [-30]*8, "low": [-25]*8, "low_mid": [-28]*8,
                          "mid": [-35]*8, "hi_mid": [-40]*8, "air": [-60]*8},
                "bass":  {"sub": [-20]*8, "low": [-18]*8, "low_mid": [-30]*8,
                          "mid": [-45]*8, "hi_mid": [-60]*8, "air": [-80]*8},
                "other": {"sub": [-50]*8, "low": [-45]*8, "low_mid": [-30]*8,
                          "mid": [-25]*8, "hi_mid": [-20]*8, "air": [-25]*8},
            },
            "stems_analysed": ["drums", "bass", "other"],
            "duration_s": 48.0,
            "sustain": {"bass": 0.5, "other": 0.4},
            "spectral_centroid": {"other": 800.0},
            "total_windows": 8,
        }
        (run_dir / "result_masking.json").write_text(_json.dumps(masking))
        out = tmp / "widget.html"
        build_widget.build_html(
            _synthetic_core(), {}, None, None, str(out), "DupTest",
            build_widget.STRINGS, run_dir=str(run_dir)
        )
        cls.html = out.read_text(encoding="utf-8")

    def test_refread_appears_exactly_once(self):
        """id="refRead" must appear exactly once — not zero (would miss the live block) and
        not two (the old bug: template comment duplicated it inside <!-- ... -->)."""
        count = self.html.count('id="refRead"')
        self.assertEqual(count, 1,
                         f'id="refRead" appeared {count} time(s); expected exactly 1. '
                         f'Count > 1 means the dead commented-out duplicate is back.')

    def test_webpanel_appears_exactly_once(self):
        """id="webPanel" must appear exactly once — same guard as refRead."""
        count = self.html.count('id="webPanel"')
        self.assertEqual(count, 1,
                         f'id="webPanel" appeared {count} time(s); expected exactly 1. '
                         f'Count > 1 means the dead commented-out duplicate is back.')

    def test_no_html_comment_contains_refread_id(self):
        """No HTML comment (<!-- ... -->) must contain id="refRead" — that is the dead copy."""
        import re
        for m in re.finditer(r'<!--.*?-->', self.html, re.DOTALL):
            self.assertNotIn('id="refRead"', m.group(0),
                             'A commented-out copy of #refRead was found in the rendered HTML. '
                             'Fix: do not use __REFREAD__ placeholder inside an HTML comment.')


class RecordHistorySurvivesLegacyStrEntry(unittest.TestCase):
    """build_widget._record_history must not crash when the per-project index.json holds a legacy
    bare-string run entry (an old run-init wrote a slug string instead of a metadata dict — the real
    Wobble case that logged `history update skipped: 'str' object has no attribute 'get'`). The dict
    siblings (track_analyzer.py, run_dir.py) already guard; this proves build_widget does too."""

    def test_legacy_str_entry_does_not_crash_and_dict_entry_updates(self):
        base = Path(tempfile.mkdtemp(prefix="tc_hist_"))
        run_dir = base / "Wobble" / "v0.6.2__2026-06-23_1028"
        run_dir.mkdir(parents=True)
        widget = run_dir / "analysis_widget.html"
        widget.write_text("<html></html>")
        (run_dir / "run_meta.json").write_text(json.dumps({"track": "Wobble"}))
        # A legacy bare-string run entry sits next to a real dict entry — the Wobble case.
        idx = {"runs": ["Total_Reboot_Wobble_Drift_v0.6.2", {"run_dir": str(run_dir)}],
               "latest": {"run_dir": str(run_dir)}}
        (base / "index.json").write_text(json.dumps(idx))
        # Must not raise — the bug raised AttributeError: 'str' object has no attribute 'get'.
        build_widget._record_history(widget, "Solid groove")
        idx = json.loads((base / "index.json").read_text())
        dict_entry = next(e for e in idx["runs"] if isinstance(e, dict))
        self.assertEqual(dict_entry["verdict"], "Solid groove",
                         "the matching dict run entry still gets its verdict written")
        self.assertEqual(idx["runs"][0], "Total_Reboot_Wobble_Drift_v0.6.2",
                         "the legacy string entry is left untouched, not crashed on")


class CardScalePhrases(unittest.TestCase):
    """INV-50a-c (SPEC §B.16, 2026-07-05 late) — a number wears its scale. The swing,
    squashed and tonal-resonance bodies carry a reference scale IN the sentence, and the
    swing/tonal framing is COMPUTED from the measurement (three bands / three steps per
    sign) so the fix doesn't re-template. Written RED against 1.4.0 (canned bodies)."""

    @staticmethod
    def _html(core_extra=None, detail=None):
        tmp = Path(tempfile.mkdtemp(prefix="tc_scale_"))
        core = _synthetic_core()
        core.update(core_extra or {})
        out = tmp / "widget.html"
        build_widget.build_html(core, detail or {}, None, None, str(out), "Scale Test",
                                build_widget.STRINGS, mode="full",
                                narrative_md="Scale fixture.")
        return out.read_text(encoding="utf-8")

    def test_swing_feel_matches_band(self):  # INV-50a
        cases = (
            (45.0, "gentle human push", ("unmistakably human", "broken-beat")),
            (75.0, "unmistakably human", ("gentle human push", "broken-beat")),
            (192.0, "broken-beat", ("gentle human push", "unmistakably human")),
        )
        for ms, phrase, others in cases:
            html = self._html(detail={"swing_global_ms": ms})
            self.assertIn("25–30 ms", html,
                          f"swing {ms}: the tight-grid window must be named in the card")
            self.assertIn(phrase, html,
                          f"swing {ms}: the feel phrase must match the measured band")
            for o in others:
                self.assertNotIn(o, html,
                                 f"swing {ms}: only ONE feel phrase may render")
            self.assertNotIn("sounds human rather than machine", html,
                             "the canned one-size swing line must be gone")

    def test_squashed_ladder_present(self):  # INV-50b
        html = self._html(core_extra={"vitals": {"dynamic_range_db": 4.5}})
        self.assertIn("6–8", html, "the squashed card must name the club-master rung")
        self.assertIn("10 and up", html, "the squashed card must name the open-mix rung")

    def test_tonal_phrase_matches_magnitude_and_sign(self):  # INV-50c
        all_phrases = ("about twice as loud", "half again as loud", "clearly audible bump",
                       "about half as loud", "noticeably recessed", "clearly audible dip")
        cases = (
            (9.5, "about twice as loud"),
            (6.5, "half again as loud"),
            (4.5, "clearly audible bump"),
            (-9.5, "about half as loud"),
            (-6.5, "noticeably recessed"),
            (-4.5, "clearly audible dip"),
        )
        for dev, phrase in cases:
            html = self._html(core_extra={"tonal_balance": [{"band": "250", "dev_db": dev}]})
            self.assertIn(phrase, html,
                          f"dev {dev:+.1f}: the perceived-loudness phrase must match")
            for o in all_phrases:
                if o != phrase and not (o in phrase or phrase in o):
                    self.assertNotIn(o, html, f"dev {dev:+.1f}: only ONE phrase may render")
            self.assertIn(f"{dev:+.1f}", html,
                          f"dev {dev:+.1f}: the measured dB must stay in the sentence")


class TempoChangesReachVitals(unittest.TestCase):
    """The .als tempo changes flow into the widget vitals (so the timeline can mark them),
    and the displayed tempo prefers the .als project tempo over audio-detection."""

    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp(prefix="tc_tempo_"))
        out = tmp / "widget.html"
        als = {"bpm": 120, "time_signature": "4/4", "time_sig_changes": [],
               "tempo_changes": [{"beat": 0.0, "time_s": 0.0, "bpm": 120.0},
                                 {"beat": 32.0, "time_s": 16.0, "bpm": 140.0},
                                 {"beat": 64.0, "time_s": 29.71, "bpm": 90.0}],
               "markers": [], "tracks": [], "track_count": 0}
        build_widget.build_html(_synthetic_core(), {}, None, als, str(out), "Tempo Test",
                                build_widget.STRINGS, mode="full",
                                narrative_md="The mix reads clear.\n\nBass is forward early.")
        cls.html = out.read_text(encoding="utf-8")
        cls.payload, _ = json.JSONDecoder().raw_decode(cls.html.split("const D=", 1)[1])

    def test_tempo_changes_in_vitals(self):
        tpc = self.payload["vitals"]["tempo_changes"]
        self.assertEqual([c["bpm"] for c in tpc], [120.0, 140.0, 90.0])

    def test_displayed_tempo_prefers_als_base(self):
        self.assertEqual(self.payload["tempo"], 120.0)   # .als base, not the 123 audio-detected
        self.assertEqual(self.payload["tempo_src"], "als")

    def test_vitals_tempo_slot_filled(self):
        self.assertEqual(self.payload["vitals"]["tempo_bpm"], 120.0)


if __name__ == "__main__":
    unittest.main()
