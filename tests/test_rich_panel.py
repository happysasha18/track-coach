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

    # -- glyph-led layout (variant A, Alexander 2026-07-04) ---------------------
    def test_direct_glyph_and_confirmed_section(self):
        """direct traits render with ★ glyph inside .rn-trait-glyph span (variant A layout).
        No trailing per-row pill — confirmed rows use glyph-led format."""
        self.assertIn('class="rn-trait-glyph"', self.dc_html)
        self.assertIn('★', self.dc_html)   # ★
        # Old pill must NOT appear (D-INV-29: no per-row long labels)
        self.assertNotIn('tc-rn-pill is-direct', self.dc_html)

    def test_indirect_glyph_in_confirmed_section(self):
        """indirect traits render with ☆ glyph inside .rn-trait-glyph.rn-trait-glyph-indirect.
        Builds a synthetic entry with an indirect trait."""
        entry = {"artist": "SynTest", "blurb": "test",
                 "traits": [{"phrase": "x", "title": "X title", "tier": "indirect"}]}
        html = build_widget.render_reference_notes(entry)
        self.assertIn('rn-trait-glyph-indirect', html)
        self.assertIn('☆', html)   # ☆
        # Old indirect pill must NOT appear
        self.assertNotIn('tc-rn-pill is-indirect', html)

    def test_webonly_traits_in_muted_group_not_pills(self):
        """web-only traits collapse into ONE muted group (rn-webonly-group), not N pills.
        D-INV-29: the repeated grey pills are exactly what the spec forbids.
        Variant A heading: 'Web describes these' (not 'web says' pill text)."""
        self.assertIn('class="rn-webonly-group"', self.dc_html)
        # Heading contains "describes these" (case-insensitive — the heading may be lower/upper)
        self.assertIn("describes these", self.dc_html.lower())
        # Old per-row pills must NOT appear
        self.assertNotIn('tc-rn-pill is-webonly', self.dc_html)

    def test_na_traits_in_muted_group_not_pills(self):
        """not-measurable traits also go into the muted web-only group, not is-na pills.
        Venetian Snares has an odd-time-sig (not-measurable) trait."""
        self.assertNotIn('tc-rn-pill is-na', self.vs_html)
        # The trait text itself must still appear (content is preserved — case-insensitive)
        self.assertIn("Odd time", self.vs_html)

    # -- trait text in new layout ------------------------------------------------
    def test_trait_text_span_present(self):
        """Confirmed trait text must appear inside rn-trait-text spans (variant A)."""
        self.assertIn('class="rn-trait-text"', self.dc_html)
        # "Devastatingly deep" is the opening of a direct (bass-anchor) trait title in DeepChord
        self.assertIn("Devastatingly deep", self.dc_html)

    # -- footnote legend ---------------------------------------------------------
    def test_footnote_legend_present(self):
        """One .rn-footnote legend must appear explaining ★/☆/· (variant A)."""
        self.assertIn('class="rn-footnote"', self.dc_html)
        self.assertIn('★', self.dc_html)   # ★ must appear in footnote text

    # -- sources -----------------------------------------------------------------
    def test_sources_present_with_links(self):
        """Sources must render as a list of links."""
        self.assertIn('class="tc-rn-sources"', self.dc_html)
        self.assertIn("Wikipedia", self.dc_html)
        self.assertIn('<a href=', self.dc_html)

    def test_sources_open_in_new_tab(self):
        """Source links must have target="_blank"."""
        self.assertIn('target="_blank"', self.dc_html)


# ── §D.10.2 — _web_body_html rich mode (per-direction body since the D-INV-36 merge) ───────

class WebPanelHtmlRichMode(unittest.TestCase):
    """_web_body_html in rich mode uses render_reference_notes as the body builder. Since the
    D-INV-36 merge (s58) the <details id="webPanel"> wrapper is built once by
    render_reference_read (nested in #refPanel, one body per shown direction) — the wrapper
    facts live in test_reference_read::WebPanelRendering + the MergedReferencePanel browser
    tests; this class covers the per-direction BODY."""

    @classmethod
    def setUpClass(cls):
        dc = _load_notes()["DeepChord"]
        # centroid_z can be a neutral dict — tier is read from JSON, not from centroid
        cls.html = build_widget._web_body_html(
            "DeepChord", [], {ax: 0.0 for ax in ("tempo", "bass_share", "brightness")},
            web_data=dc,
        )

    def test_body_has_no_wrapper(self):
        """The body builder returns CONTENT only — the webPanel details wrapper is the merged
        panel's job (render_reference_read), never duplicated here (E-BUG-1: the id must
        appear exactly once in a widget)."""
        self.assertNotIn('id="webPanel"', self.html)
        self.assertNotIn("<details", self.html)

    def test_has_rich_blurb_markup(self):
        """Body must come from render_reference_notes: tc-rn-blurb must be present."""
        self.assertIn('class="tc-rn-blurb"', self.html)

    def test_has_direct_glyph_in_confirmed_section(self):
        """Rich body must contain ★ glyph in the confirmed section (variant A layout)."""
        self.assertIn('rn-trait-glyph', self.html)
        self.assertIn('★', self.html)   # ★ glyph
        # No old per-row pill
        self.assertNotIn('tc-rn-pill is-direct', self.html)

    def test_has_sources(self):
        """Sources must appear (shared renderer path)."""
        self.assertIn("tc-rn-sources", self.html)

    def test_returns_empty_when_no_blurb_no_traits(self):
        """Body absent (§D.10.2 liveness) when both blurb and traits are empty — the merged
        panel then hides the web disclosure for this direction (D-INV-36d)."""
        result = build_widget._web_body_html(
            "Empty", [], {},
            web_data={"artist": "Empty", "blurb": "", "traits": []},
        )
        self.assertEqual(result, "")

    def test_simple_mode_empty_when_no_conf_entries(self):
        """Simple (fallback) mode with no conf_entries and no centroid → empty string."""
        result = build_widget._web_body_html("X", [], {})
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
        """The Simple-view gate on the web notes — since the D-INV-36 merge it rides the ONE
        container rule: body.simple #refPanel hides the nested #webPanel with it."""
        self.assertRegex(
            self.html,
            r"body\.simple\s+#refPanel\s*\{[^}]*display\s*:\s*none",
            "body.simple #refPanel { display:none } rule must be present (hides nested #webPanel)",
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


# ── §D.10.2 — trait sort order and glyph mapping (0.9.4) ─────────────────────────────────

class TraitSortOrder(unittest.TestCase):
    """Traits must be sorted by evidence strength: direct first (★ glyph), then indirect
    (☆ glyph), then web-only and not-measurable (collapsed into ONE muted group).
    Variant A layout (Alexander 2026-07-04): no per-row pills."""

    @classmethod
    def setUpClass(cls):
        notes = _load_notes()
        # DeepChord: has direct AND web-only traits (in mixed JSON order)
        cls.dc_html = build_widget.render_reference_notes(notes["DeepChord"])
        # Venetian Snares: has direct AND not-measurable traits
        cls.vs_html = build_widget.render_reference_notes(notes["Venetian Snares"])

    # -- sort: confirmed section before web-only group -------------------------
    def test_direct_before_webonly_in_render(self):
        """The confirmed section (rn-confirmed-list) must appear before the web-only group
        (rn-webonly-group) — direct=0 comes before web-only=2 in the sorted layout."""
        confirmed_pos = self.dc_html.find("rn-confirmed-list")
        webonly_pos   = self.dc_html.find("rn-webonly-group")
        self.assertGreater(confirmed_pos, -1, "rn-confirmed-list must be present (DeepChord has direct traits)")
        self.assertGreater(webonly_pos,   -1, "rn-webonly-group must be present (DeepChord has web-only traits)")
        self.assertLess(
            confirmed_pos, webonly_pos,
            "confirmed section must appear before the web-only group (sort: direct=0 < web-only=2)",
        )

    # -- sort: confirmed section before web-only group (not-measurable) --------
    def test_direct_before_na_in_render(self):
        """The confirmed section must appear before any web-only/not-measurable group.
        Venetian Snares has both direct and not-measurable traits."""
        confirmed_pos = self.vs_html.find("rn-confirmed-list")
        webonly_pos   = self.vs_html.find("rn-webonly-group")
        self.assertGreater(confirmed_pos, -1, "rn-confirmed-list must be present (Venetian Snares has direct traits)")
        self.assertGreater(webonly_pos,   -1, "rn-webonly-group must be present (not-measurable goes to muted group)")
        self.assertLess(
            confirmed_pos, webonly_pos,
            "confirmed section must appear before is-na group (sort: direct=0 < not-measurable=3)",
        )

    # -- glyph mapping ---------------------------------------------------------
    def test_glyph_in_confirmed_rows(self):
        """★ must appear in .rn-trait-glyph for direct; ☆ for indirect (variant A layout)."""
        import re
        # ★ glyph in confirmed rows (DeepChord has direct traits)
        glyph_els = re.findall(r'<span class="rn-trait-glyph"[^>]*>([^<]*)</span>', self.dc_html)
        self.assertTrue(glyph_els, "at least one rn-trait-glyph element must be present for direct traits")
        # At least one must be ★
        star_glyphs = [g for g in glyph_els if "★" in g]
        self.assertTrue(star_glyphs, "★ glyph must appear in .rn-trait-glyph for direct traits")

        # ☆ glyph for indirect trait (build a synthetic entry)
        entry = {"artist": "SynGlyph", "blurb": "test",
                 "traits": [{"title": "Indirect trait", "tier": "indirect"},
                             {"title": "Direct trait",  "tier": "direct"}]}
        html = build_widget.render_reference_notes(entry)
        indirect_glyphs = re.findall(
            r'<span class="rn-trait-glyph rn-trait-glyph-indirect">([^<]*)</span>', html)
        self.assertTrue(indirect_glyphs, "at least one rn-trait-glyph-indirect element must be present")
        self.assertIn("☆", indirect_glyphs[0],
                      "☆ glyph must appear in .rn-trait-glyph-indirect for indirect traits")


if __name__ == "__main__":
    unittest.main()
