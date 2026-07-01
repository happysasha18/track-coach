#!/usr/bin/env python3
"""Widget STRUCTURE / CSS-gating contract — asserted on the RENDERED OUTPUT, not the template.

Why this file exists, and why it changed (Sasha, 2026-06-20): we kept breaking the suite because
these checks used to scrape the module-level `build_widget.TEMPLATE` string and pin exact CSS/JS
tokens (`a.open{…border…}`, `compLaneH=\\d+`, the `SIMPLE_LANES` array). That made cosmetic edits
fail tests even when the rendered widget was perfect ("проверил в темплейте, но не в HTML"). The fix:
assert on the HTML this skill actually SHIPS — render one widget and inspect its output.

Division of labour (no more duplication):
  • DATA / BEHAVIOUR — which curves reach the payload, the per-view lane sets, compLaneH being a
    constant, the player + back-button wiring — lives ONCE in test_widget_render.py (it parses the
    rendered payload). Don't re-pin those tokens here.
  • STRUCTURE / CSS VISIBILITY — the panels a user must see, and what the Simple view hides via CSS —
    lives HERE, because CSS visibility isn't visible in the JSON payload. We still read it off the
    RENDERED HTML so a template that fails to emit its CSS would fail too.

No browser, no audio, instant: one render + string/CSS assertions on the result.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402


def _core(n=48, dur=96.0):
    """Minimal but complete core — every lane non-empty so nothing is dropped for being absent."""
    tb = [round(i * dur / n, 3) for i in range(n)]
    return {
        "duration_s": dur, "time_bins": tb, "tempo": 123,
        "energy": [round(0.2 + 0.6 * i / n, 3) for i in range(n)],
        "brightness": [round(0.5 + 0.4 * ((i % 8) / 8 - 0.5), 3) for i in range(n)],
        "density": [round(0.3 + 0.5 * (i % 5) / 5, 3) for i in range(n)],
        "wobble_rate": [round(1.0 + (i % 4), 3) for i in range(n)],
        "stereo_width": [round(0.4 + 0.3 * (i % 3) / 3, 3) for i in range(n)],
        "energy_trend": 0.4, "brightness_trend": -0.1, "density_trend": 0.2,
        "stereo_width_trend": 0.15, "wobble_rate_start_hz": 1.0, "wobble_rate_end_hz": 3.0,
        "section_bounds_s": [round(dur * 0.25, 2), round(dur * 0.5, 2), round(dur * 0.75, 2)],
    }


def _render_widget():
    """Render one full widget (stems + narrative so player and read panels are live) → output HTML."""
    tmp = Path(tempfile.mkdtemp(prefix="tc_contract_"))
    sdir = tmp / "stems_web"
    sdir.mkdir()
    for s in ("drums", "bass", "vocals"):
        (sdir / f"{s}.m4a").write_bytes(b"\x00")
    out = tmp / "w.html"
    build_widget.build_html(_core(), {}, None, None, str(out), "Contract Test",
                            build_widget.STRINGS, audio_stems_rel="stems_web",
                            narrative_md="The mix reads clear.\n\nBass is forward early.",
                            back_href="file:///lib/index.html")
    return out.read_text(encoding="utf-8")


HTML = _render_widget()
# every `body.simple … {display:none…}` selector list in the SHIPPED css
SIMPLE_HIDE = " ".join(re.findall(r"body\.simple([^{]*)\{[^}]*display\s*:\s*none[^}]*\}", HTML))


class PanelsExist(unittest.TestCase):
    """The panels a user must always be able to reach must be in the rendered widget."""

    def test_core_panels_render(self):
        for el in ('id="playerControls"', 'id="readPanel"', 'id="recs"', 'id="storyPanel"',
                   'id="story"', 'id="evidence"', 'id="autoPanel"', 'id="backLink"'):
            self.assertIn(el, HTML, f"rendered widget is missing the panel: {el}")

    def test_producer_read_is_rendered_server_side_when_a_narrative_exists(self):
        # INV-2: The read is now rendered SERVER-SIDE (session 10): #readBody ships filled in the
        # markup and the panel is visible — not built by JS. We rendered WITH a narrative, so assert
        # the body is non-empty real HTML and the panel isn't hidden.
        m = re.search(r'<div id="readBody">(.*?)</div>', HTML, re.S)
        self.assertIsNotNone(m, "rendered widget has no #readBody")
        self.assertTrue(m.group(1).strip(), "producer's read was not rendered into #readBody server-side")
        self.assertNotRegex(HTML, r'id="readPanel"[^>]*style="display:none"',
                            "read panel must be visible when a narrative exists")

    def test_back_link_carries_its_label(self):
        # the ← Library link must reference its translatable label (the wiring/href is render-tested)
        self.assertTrue(build_widget.STRINGS["ui"].get("back_to_library"),
                        "missing the back_to_library string")
        self.assertIn("back_to_library", HTML, "output doesn't reference the back_to_library label")

    def test_automation_is_wired_to_its_data(self):
        self.assertIn("A.automations", HTML, "automation chart has no data binding in the output")
        for s in ("auto_title", "auto_hint"):
            self.assertTrue(build_widget.STRINGS["ui"].get(s), f"missing the {s} string")
            self.assertIn(s, HTML, f"output doesn't reference the {s} string")

    def test_automation_sits_inside_the_evidence_drawer(self):
        # structural: the automation panel lives inside the Evidence drawer, so it appears/collapses
        # with it (and its data gate INV-16 hides it when there are no envelopes)
        self.assertLess(HTML.index('id="evidence"'), HTML.index('id="autoPanel"'),
                        "automation panel must sit inside the Evidence drawer")


class SimpleViewGating(unittest.TestCase):
    """What the Simple view hides via CSS — the one thing the JSON payload can't tell us. The recurring
    incident was panels (player, read) silently CSS-hidden in Simple while their data still shipped."""

    def test_gated_set_is_exactly_the_known_five(self):
        # INV-18 (Sasha, 2026-06-20): the Evidence drawer is ALWAYS visible — Simple no longer hides it.
        # Simple hides ONLY: the demux stem viz (#stemlanes + #seqKey), the recs panel filtered to
        # non-timecoded cards (#recs), the reference read (#refRead — §D.10.3 Detailed-only), the
        # web-info plaque (#webPanel — §D.10.2 Detailed-only, shipped 0.9.1), and the aim picker
        # panel (#aimpanel — §D.6.1 Detailed-only, shipped 0.9.10).
        hidden = set(re.findall(r"#([A-Za-z][\w-]*)", SIMPLE_HIDE))
        self.assertEqual(hidden, {"stemlanes", "seqKey", "recs", "refRead", "webPanel", "aimpanel"},
                         f"Simple view gates an unexpected set: {sorted(hidden)}")

    def test_evidence_drawer_is_always_visible(self):
        # INV-18: the Evidence drawer must NOT be among the Simple-hidden selectors (it used to be).
        self.assertNotIn("#evidence", SIMPLE_HIDE, "regression: Simple hides the Evidence drawer")

    def test_player_and_read_stay_visible_in_simple(self):
        for keep in ("#playerControls", "#playBtn", "#readPanel"):
            self.assertNotIn(keep, SIMPLE_HIDE, f"regression: Simple hides {keep}")

    def test_recs_filtered_not_capped_or_blanket_hidden(self):
        # Simple shows ONLY the timecoded recs (the cards a timeline triangle points to); it targets
        # the non-timecoded cards, never a blanket #recs hide or an nth-of-type cap.
        self.assertRegex(HTML, r"body\.simple\s+#recs\s+\.rec:not\(\[data-t\]\)",
                         "Simple must hide ONLY the non-timecoded recs")
        self.assertNotRegex(HTML, r"body\.simple\s+#recs[^{]*nth-of-type",
                            "regression: recommendation cards are capped in Simple")
        self.assertNotIn("storyCues", HTML, "the separate callout list under the graph should be gone")

    def test_demux_stem_viz_is_detailed_only(self):
        # the per-stem canvas + its key are Detailed-only; the transport stays in both views
        self.assertRegex(HTML, r"body\.simple\s+#stemlanes", "demux stem viz must be hidden in Simple")
        self.assertRegex(HTML, r"body\.simple\s+#seqKey", "demux sequencer key must be hidden in Simple")


class NoResidualPlaceholder(unittest.TestCase):
    """INV-21 — every `__PLACEHOLDER__` the L-py template declares must be substituted before the
    widget reaches the producer. A new template slot wired into the HTML but not into the Python emits
    a literal `__NEWTHING__` — visible garbage, caught by nothing else. One regex over the real output."""

    def test_no_uppercase_double_underscore_token_survives(self):
        leftovers = sorted(set(re.findall(r"__[A-Z][A-Z0-9_]*__", HTML)))
        self.assertEqual(leftovers, [], f"INV-21: unsubstituted template placeholder(s) shipped: {leftovers}")


class ModeLabel(unittest.TestCase):
    """Quick runs were once mislabelled 'deep mode' — the header subtitle must follow D.mode."""

    def test_subtitle_branches_on_mode(self):
        self.assertRegex(HTML, r'D\.mode\s*===?\s*["\']quick["\']',
                         "header subtitle does not branch on D.mode (quick runs mislabelled)")
        for s in ("subtitle", "subtitle_quick"):
            self.assertTrue(build_widget.STRINGS["ui"].get(s), f"missing the {s} string")


class ModeBadge(unittest.TestCase):
    """Sasha 2026-06-20: the run mode must be unmistakable ON THE PAGE — a badge near the brand, and
    on a quick read a one-line explainer of what a full run adds. (The catalog carries it too, via the
    MODE column.) HTML above is a FULL render; render a quick one here for the quick case."""

    def test_full_render_shows_the_full_badge_and_no_quick_note(self):
        # HTML is a full render: green "full" badge, and NO quick explainer line (that's mode-gated).
        self.assertIn('class="modebadge full"', HTML, "full widget must carry the full badge")
        self.assertNotIn('class="modenote"', HTML, "full widget must NOT show the quick explainer")

    def test_quick_render_shows_quick_badge_and_explainer(self):
        tmp = Path(tempfile.mkdtemp(prefix="tc_qbadge_"))
        mdir = tmp / "mix_web"
        mdir.mkdir()
        (mdir / "mix.m4a").write_bytes(b"\x00")
        out = tmp / "w.html"
        build_widget.build_html(_core(), {}, None, None, str(out), "Quick", build_widget.STRINGS,
                                audio_mix_rel="mix_web", mode="quick")
        h = out.read_text(encoding="utf-8")
        self.assertIn('class="modebadge quick"', h, "quick badge (amber) missing")
        self.assertIn(build_widget.STRINGS["ui"]["mode_badge_quick"], h, "quick badge label missing")
        self.assertRegex(h, r'<p class="modenote" id="modeNote">[^<]+</p>', "quick explainer line missing")


if __name__ == "__main__":
    unittest.main()
