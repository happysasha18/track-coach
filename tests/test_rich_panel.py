#!/usr/bin/env python3
"""§D.10.2 rich web panel — tests for B3/B4 (render_reference_notes wired into widget + side page).

Asserts on REAL produced HTML — no mocks, no source-scraping.

Coverage:
  - render_reference_notes (pure function): blurb, note callout, is-direct pill + label,
    is-indirect pill + label, is-webonly pill + label, is-na pill + label, trait titles, sources.
  - _web_panel_html rich mode: wrapper has id="webPanel" + class="tc-panel"; body is from
    the shared renderer (tc-rn-blurb, tc-rn-pill is-direct, sources); empty when no content.
  - Widget structure: every user-facing content section is a <details class="tc-panel">;
    the vitals strip is NOT a details element.
  - Side-page generator (build_reference_notes.py): all artists present; blurb text matches
    JSON; tc-rn-* markup present; light-theme CSS present.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import build_widget            # noqa: E402
import build_reference_notes   # noqa: E402

NOTES_PATH = SKILL_DIR / "data" / "reference_web_notes.json"


# ── shared fixture helpers ─────────────────────────────────────────────────────────────────

def _load_notes():
    return json.loads(NOTES_PATH.read_text(encoding="utf-8"))


def _core(n=24, dur=48.0):
    """Minimal but complete core — all lanes non-empty."""
    tb = [round(i * dur / n, 3) for i in range(n)]
    return {
        "duration_s": dur, "time_bins": tb, "tempo": 123,
        "energy":     [round(0.2 + 0.6 * i / n, 3) for i in range(n)],
        "brightness": [round(0.5 + 0.4 * ((i % 8) / 8 - 0.5), 3) for i in range(n)],
        "density":    [round(0.3 + 0.5 * (i % 5) / 5, 3) for i in range(n)],
        "wobble_rate": [round(1.0 + (i % 4), 3) for i in range(n)],
        "stereo_width": [round(0.4 + 0.3 * (i % 3) / 3, 3) for i in range(n)],
        "energy_trend": 0.4, "brightness_trend": -0.1, "density_trend": 0.2,
        "stereo_width_trend": 0.15, "wobble_rate_start_hz": 1.0, "wobble_rate_end_hz": 3.0,
        "section_bounds_s": [round(dur * 0.5, 2)],
    }


# ── §D.10.2 — render_reference_notes (pure function) ──────────────────────────────────────

class RenderReferenceNotesUnit(unittest.TestCase):
    """The shared renderer emits correct semantic markup for each artist entry."""

    @classmethod
    def setUpClass(cls):
        notes = _load_notes()
        cls.dc = notes["DeepChord"]           # has direct traits, no note
        cls.vs = notes["Venetian Snares"]     # has note, is-na trait
        cls.dc_html = build_widget.render_reference_notes(cls.dc)
        cls.vs_html  = build_widget.render_reference_notes(cls.vs)

    # -- blurb -------------------------------------------------------------------
    def test_blurb_class_and_text_present(self):
        """DeepChord blurb renders with tc-rn-blurb class and real text."""
        self.assertIn('class="tc-rn-blurb"', self.dc_html)
        # "lava-lamp stasis" is a phrase in the DeepChord blurb
        self.assertIn("lava-lamp stasis", self.dc_html)

    # -- note callout ------------------------------------------------------------
    def test_note_absent_for_deepchord(self):
        """DeepChord has note=null → tc-rn-note must not appear."""
        self.assertNotIn('class="tc-rn-note"', self.dc_html)

    def test_note_present_for_venetian_snares(self):
        """Venetian Snares has a non-null note → note callout must be rendered."""
        self.assertIn('class="tc-rn-note"', self.vs_html)
        self.assertIn("varies sharply", self.vs_html)

    # -- pill labels for every tier ----------------------------------------------
    def test_direct_pill_class_and_label(self):
        """is-direct pill must exist for DeepChord (≥3 direct traits) and carry its label."""
        self.assertIn('tc-rn-pill is-direct', self.dc_html)
        self.assertIn("measurement confirms", self.dc_html)

    def test_indirect_pill_class_and_label(self):
        """is-indirect pill and label — at least one entry must use tier=indirect.
        Venetian Snares has no indirect traits; build a synthetic entry."""
        entry = {"artist": "SynTest", "blurb": "test",
                 "traits": [{"phrase": "x", "title": "X title", "tier": "indirect"}]}
        html = build_widget.render_reference_notes(entry)
        self.assertIn('tc-rn-pill is-indirect', html)
        self.assertIn("measurement confirms (indirect)", html)

    def test_webonly_pill_class_and_label(self):
        """is-webonly pill and label — DeepChord has many web-only traits."""
        self.assertIn('tc-rn-pill is-webonly', self.dc_html)
        self.assertIn("web says", self.dc_html)

    def test_na_pill_class_and_label(self):
        """is-na pill and label — Venetian Snares has odd-time-sig (not-measurable)."""
        self.assertIn('tc-rn-pill is-na', self.vs_html)
        self.assertIn("not measurable", self.vs_html)

    # -- trait titles ------------------------------------------------------------
    def test_trait_title_span_present(self):
        """Trait titles must appear inside tc-rn-trait-title spans."""
        self.assertIn('class="tc-rn-trait-title"', self.dc_html)
        # "Devastatingly deep" is the opening of the bass-anchor trait title
        self.assertIn("Devastatingly deep", self.dc_html)

    # -- sources -----------------------------------------------------------------
    def test_sources_present_with_links(self):
        """Sources must render as a list of links."""
        self.assertIn('class="tc-rn-sources"', self.dc_html)
        self.assertIn("Wikipedia", self.dc_html)
        self.assertIn('<a href=', self.dc_html)

    def test_sources_open_in_new_tab(self):
        """Source links must have target="_blank"."""
        self.assertIn('target="_blank"', self.dc_html)


# ── §D.10.2 — _web_panel_html rich mode ───────────────────────────────────────────────────

class WebPanelHtmlRichMode(unittest.TestCase):
    """_web_panel_html in rich mode uses render_reference_notes as the body builder."""

    @classmethod
    def setUpClass(cls):
        dc = _load_notes()["DeepChord"]
        # centroid_z can be a neutral dict — tier is read from JSON, not from centroid
        cls.html = build_widget._web_panel_html(
            "DeepChord", [], {ax: 0.0 for ax in ("tempo", "bass_share", "brightness")},
            web_data=dc,
        )

    def test_has_webpanel_id(self):
        self.assertIn('id="webPanel"', self.html)

    def test_is_details_with_tc_panel_class(self):
        """The outer element must be <details class="tc-panel">."""
        self.assertRegex(
            self.html,
            r'<details[^>]*class="tc-panel[^"]*"[^>]*id="webPanel"'
            r'|<details[^>]*id="webPanel"[^>]*class="tc-panel[^"]*"',
        )

    def test_has_rich_blurb_markup(self):
        """Body must come from render_reference_notes: tc-rn-blurb must be present."""
        self.assertIn('class="tc-rn-blurb"', self.html)

    def test_has_direct_pill_and_label(self):
        """Rich body must contain at least one is-direct pill."""
        self.assertIn("tc-rn-pill is-direct", self.html)
        self.assertIn("measurement confirms", self.html)

    def test_has_sources(self):
        """Sources must appear (shared renderer path)."""
        self.assertIn("tc-rn-sources", self.html)

    def test_returns_empty_when_no_blurb_no_traits(self):
        """Panel absent (§D.10.2 liveness) when both blurb and traits are empty."""
        result = build_widget._web_panel_html(
            "Empty", [], {},
            web_data={"artist": "Empty", "blurb": "", "traits": []},
        )
        self.assertEqual(result, "")

    def test_simple_mode_empty_when_no_conf_entries(self):
        """Simple (fallback) mode with no conf_entries and no centroid → empty string."""
        result = build_widget._web_panel_html("X", [], {})
        self.assertEqual(result, "")


# ── Widget structure: all panels are <details class="tc-panel"> ───────────────────────────

class PanelStructureIsDetails(unittest.TestCase):
    """Every user-facing content section must be a <details class="tc-panel"> (Phase A)."""

    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp(prefix="tc_rp_struct_"))
        sdir = tmp / "stems_web"
        sdir.mkdir()
        for s in ("drums", "bass", "vocals"):
            (sdir / f"{s}.m4a").write_bytes(b"\x00")
        out = tmp / "w.html"
        build_widget.build_html(_core(), {}, None, None, str(out), "StructTest",
                                build_widget.STRINGS, audio_stems_rel="stems_web",
                                narrative_md="The mix reads clear.")
        cls.html = out.read_text(encoding="utf-8")

    def test_story_panel_is_details(self):
        self.assertRegex(
            self.html,
            r'<details[^>]*class="tc-panel[^"]*"[^>]*id="storyPanel"'
            r'|<details[^>]*id="storyPanel"[^>]*class="tc-panel[^"]*"',
            "storyPanel must be a <details class='tc-panel'>",
        )

    def test_read_panel_is_details(self):
        self.assertRegex(
            self.html,
            r'<details[^>]*class="tc-panel[^"]*"[^>]*id="readPanel"'
            r'|<details[^>]*id="readPanel"[^>]*class="tc-panel[^"]*"',
            "readPanel must be a <details class='tc-panel'>",
        )

    def test_recs_panel_is_details(self):
        self.assertRegex(
            self.html,
            r'<details[^>]*class="tc-panel[^"]*"[^>]*id="recsPanel"'
            r'|<details[^>]*id="recsPanel"[^>]*class="tc-panel[^"]*"',
            "recsPanel must be a <details class='tc-panel'>",
        )

    def test_evidence_is_details(self):
        self.assertRegex(
            self.html,
            r'<details[^>]*class="tc-panel[^"]*"[^>]*id="evidence"'
            r'|<details[^>]*id="evidence"[^>]*class="tc-panel[^"]*"',
            "evidence must be a <details class='tc-panel'>",
        )

    def test_tonal_panel_is_details(self):
        self.assertRegex(
            self.html,
            r'<details[^>]*class="tc-panel[^"]*"[^>]*id="tonalPanel"'
            r'|<details[^>]*id="tonalPanel"[^>]*class="tc-panel[^"]*"',
            "tonalPanel must be a <details class='tc-panel'>",
        )

    def test_vitals_strip_is_not_a_details(self):
        """The vitals metrics strip must NOT be wrapped in a <details> element."""
        m = re.search(r'class="vitals"', self.html)
        self.assertIsNotNone(m, "vitals strip must exist in the rendered widget")
        self.assertNotRegex(
            self.html, r'<details[^>]*class="[^"]*vitals[^"]*"',
            "vitals strip must not be a <details> element",
        )

    def test_webpanel_is_hidden_in_simple_view(self):
        """Confirm the existing Simple-view gate on webPanel survives the B3 refactor."""
        self.assertRegex(
            self.html,
            r"body\.simple\s+#webPanel\s*\{[^}]*display\s*:\s*none",
            "body.simple #webPanel { display:none } rule must be present",
        )


# ── Side-page parity (build_reference_notes.py) ───────────────────────────────────────────

class SidePageParity(unittest.TestCase):
    """The side-page generator and the in-widget panel share one source and one renderer."""

    @classmethod
    def setUpClass(cls):
        cls.notes = _load_notes()
        tmp = Path(tempfile.mkdtemp(prefix="tc_sp_"))
        cls.out = tmp / "reference_notes.html"
        build_reference_notes.build(cls.out)
        cls.html = cls.out.read_text(encoding="utf-8")

    def test_all_artists_present(self):
        for artist in ("DeepChord", "Venetian Snares", "SCSI-9"):
            self.assertIn(artist, self.html, f"{artist} missing from generated side page")

    def test_deepchord_blurb_in_side_page(self):
        """Blurb text from JSON must appear in the side page (shared renderer path)."""
        blurb_fragment = "lava-lamp stasis"   # in DeepChord blurb
        self.assertIn(blurb_fragment, self.html)

    def test_venetian_snares_note_in_side_page(self):
        """Note callout from JSON must appear for Venetian Snares."""
        self.assertIn("varies sharply", self.html)

    def test_tc_rn_pill_present(self):
        """Side page must use tc-rn-pill (shared renderer, not a hand-rolled copy)."""
        self.assertIn("tc-rn-pill", self.html)

    def test_sources_links_present(self):
        """Sources section must appear (shared renderer path)."""
        self.assertIn("tc-rn-sources", self.html)

    def test_light_theme_css_present(self):
        """Light-theme CSS for tc-rn-* classes must be in the side page."""
        self.assertIn(".tc-rn-pill.is-direct", self.html)
        self.assertIn(".tc-rn-pill.is-webonly", self.html)

    def test_page_has_doctype(self):
        """Generated page must be a well-formed HTML document."""
        self.assertTrue(self.html.strip().startswith("<!DOCTYPE"),
                        "side page must start with <!DOCTYPE html>")


if __name__ == "__main__":
    unittest.main()
