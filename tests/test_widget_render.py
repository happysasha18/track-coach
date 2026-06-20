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


if __name__ == "__main__":
    unittest.main()
