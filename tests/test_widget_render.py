#!/usr/bin/env python3
"""RENDER-level widget tests — the layer the template-contract tests can't reach.

The contract tests (test_widget_contract.py) assert on the static TEMPLATE: "this panel exists",
"the Simple CSS gates a known set". They are necessary but NOT sufficient — a widget can satisfy
every template check and still render WRONG once real data flows through `build_html` (a lane
dropped from the payload, the player wired to nothing, the wrong lanes shown in a view). That gap
is exactly the recurring "charts look broken but tests are green" incident (Sasha, 2026-06-19).

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
#   L186 "стерео или плотность тоже оставить в симпл" + L7 "в симпл недостаёт линий" ⇒ Simple =
#   energy + brightness + density + stereo (4). L402 "общая высота для их площади должна быть меньше"
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
    """The whole point of the Simple/Detailed toggle: which curves each view shows. Simple = the two
    named lanes drawn full-size, Detailed = all (settled spec, transcript L542). We pin the exact
    sets + the full-size requirement here so any change must be a deliberate, test-updating change
    with a fresh citation — not a silent widening like 0.7.1's (which this suite failed to catch
    because the expectation was edited to match the regression)."""

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
        # Sasha L402: "в симпле вью общая высота для их площади должна быть меньше." Structural fix:
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
    the recurring 'пропала кнопка бэк' was the button hidden behind a history.length gate on direct
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
    """A full widget must produce a per-stem player bound to the real stem sources — the 'dead
    player' regression was a player div with no sources behind it."""

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


class QuickRunGivesAMixPlayer(unittest.TestCase):
    """Sasha 2026-06-20 ("плеер какая разница быстрый прогон?"): a quick run has no stems but still
    has the mix, so it MUST get a single-track player — and be clearly badged as a quick read, while
    keeping the full Track-Story graph + structure bar (only the stem-dependent panels drop out)."""

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
    """The structure-bar's per-section instrument labels ('lead: …') were the thing Sasha saw missing
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
    """The Producer's read is rendered to HTML in Python (`_read_html`) and shipped in the markup, so
    it's directly testable. Session 10 bug (B1): the old JS parser handled `## `/`### ` only, so a
    quick narrative starting `# Title` leaked a literal `#` as muted body text, and a heading with its
    body on a SINGLE newline dumped the whole body inside the <h3>. These guards pin the fix."""

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

    def test_empty_narrative_renders_nothing_and_hides_the_panel(self):
        tmp = Path(tempfile.mkdtemp(prefix="tc_noread_"))
        out = tmp / "w.html"
        build_widget.build_html(_synthetic_core(), {}, None, None, str(out), "No Read",
                                build_widget.STRINGS, narrative_md=None)
        html = out.read_text(encoding="utf-8")
        m = re.search(r'<div id="readBody">(.*?)</div>', html, re.S)
        self.assertEqual(m.group(1).strip(), "", "readBody must be empty with no narrative")
        self.assertRegex(html, r'id="readPanel"[^>]*style="display:none"',
                         "read panel must stay hidden when there's no narrative")

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
    """Session 10 (B2): a quick read has no stems, so the Simple/Detailed toggle is meaningless. Quick
    renders a hint where the toggle was, and the toggle JS bails on quick so the body never enters
    Simple. Quick is the LADDER FLOOR (Sasha, 2026-06-20): the Evidence drawer stays visible (INV-18)
    but recs are BRIEF — timecoded only, like the calm view — gated by a `body.quick` CSS rule."""

    def test_quick_renders_a_hint_not_the_toggle(self):
        html, _ = _render(stems=(), mix=True, mode="quick")
        self.assertIn('<div class="viewhint" id="viewToggle">', html, "quick must show the view hint")
        self.assertNotIn('<div class="viewtoggle" id="viewToggle">', html, "quick must NOT show the toggle")
        m = re.search(r'<div class="viewhint" id="viewToggle">([^<]+)</div>', html)
        self.assertTrue(m and m.group(1).strip(), "the quick hint text must be present")

    def test_quick_toggle_js_bails_so_body_never_enters_simple(self):
        html, _ = _render(stems=(), mix=True, mode="quick")
        self.assertRegex(html, r'if\(D\.mode===?"quick"\)return;',
                         "the toggle must bail on quick so it uses the calm 4-lane graph + keeps evidence")

    def test_quick_shows_brief_timecoded_recs_only(self):
        # ladder floor (Sasha 2026-06-20): quick shows the SAME brief recs as the calm view — the
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
        self.assertIn('<div class="viewtoggle" id="viewToggle"></div>', html, "full must keep the toggle")
        self.assertNotIn('class="viewhint"', html, "full must NOT show the quick hint")

    def test_quick_draws_the_calm_four_lane_graph_like_the_others(self):
        # Quick has no toggle, so its graph must open in the SAME calm 4-lane view the other widgets
        # default to — not the 5-lane Detailed graph. The lane picker treats quick like Simple.
        html, _ = _render(stems=(), mix=True, mode="quick")
        self.assertRegex(html, r'contains\("simple"\)\s*\|\|\s*D\.mode===?"quick"',
                         "quick must select the Simple (4-lane) lane set on the graph")


class StructureBarIsTidy(unittest.TestCase):
    """The structure bar must not show one continuous part as a row of same-letter slivers with holes
    (worst on rough tracks: four consecutive 'D' slivers + a dropped sub-2s segment leaving a gap).
    `_coalesce_scenes` merges adjacent same-letter scenes, closes gaps, and spans the whole track —
    while preserving the A/B/A recurrence scheme (non-adjacent repeats stay distinct). Session 10."""

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
        # the bar must be identical full vs quick for the same data (it's a track property, not a mode)
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


if __name__ == "__main__":
    unittest.main()
