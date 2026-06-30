#!/usr/bin/env python3
"""§D.10.3 — Reference read block: per-facet bar chart vs nearest direction centroid.

Tests assert on the RENDERED HTML (the real shipped artifact) and the pure render_reference_read
function.  All geometric assertions use synthetic fingerprints; the Lazy Sparks assertion
reads from disk and is skipped when that run dir is absent (CI-safe).

Coverage:
  - header line rendered for close/mid lean
  - "no close direction" shown for far lean
  - at least one facet bar row present for a measured lean
  - bar count equals number of shared measured axes (nan axes omitted, RC-INV-1)
  - summary line contains "Closest on:" and "Furthest on:"
  - CSS gates the block to Detailed-only (body.simple #refRead{display:none!important})
  - block absent from widget rendered without run_dir (empty string for __REFREAD__)
  - quick-mode widget has no refRead block
  - nearest direction for Lazy Sparks matches catalog column (Venetian Snares) [disk-gated]
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402
import fingerprints as FP  # noqa: E402
import similarity_columns as SC  # noqa: E402

# ── helpers ───────────────────────────────────────────────────────────────────────────────

def _zfp(**over):
    """14-axis z-fingerprint with all axes at 0.0, with given overrides."""
    d = {ax: 0.0 for ax in FP.AXES}
    d.update(over)
    return d


def _norm_identity():
    """A z-norm that leaves raw values unchanged (mu=0, sd=1 for every axis)."""
    return {"mu": {ax: 0.0 for ax in FP.AXES}, "sd": {ax: 1.0 for ax in FP.AXES}}


def _minimal_core():
    n, dur = 24, 48.0
    tb = [round(i * dur / n, 3) for i in range(n)]
    ramp = [round(0.2 + 0.6 * i / n, 3) for i in range(n)]
    return {
        "duration_s": dur, "time_bins": tb, "tempo": 120,
        "energy": ramp, "brightness": ramp,
        "density": [0.4] * n, "wobble_rate": [1.0] * n,
        "stereo_width": [0.5] * n,
        "energy_trend": 0.3, "brightness_trend": 0.1, "density_trend": 0.0,
        "stereo_width_trend": 0.0,
        "section_bounds_s": [dur * 0.5],
    }


def _make_run_dir(tmp_root):
    """Create a minimal on-disk run dir with result_core.json + result_masking.json so
    fingerprint_from_run_dir returns a non-None fingerprint."""
    run_dir = Path(tmp_root) / "run"
    run_dir.mkdir(exist_ok=True)
    core = {
        "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
        "stereo_width_mean": 0.5,
        "density_lv": 0.6,
        "energy_trend": 0.2,
    }
    (run_dir / "result_core.json").write_text(json.dumps(core))
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
    (run_dir / "result_masking.json").write_text(json.dumps(masking))
    return str(run_dir)


# ── §D.10.3 pure-function tests ───────────────────────────────────────────────────────────

class ReferenceReadHeader(unittest.TestCase):
    """The header line must name the nearest direction for a close or mid lean."""

    def _dirs_with_clear_lean(self):
        # Closest direction is 'Near' (at z=0.2), Far is at z=9.0 → clear relative lean → close
        return {"Near": _zfp(tempo=0.2), "FarDir": _zfp(tempo=9.0)}

    def test_header_names_direction_for_close_lean(self):
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            self._dirs_with_clear_lean(),
            _norm_identity()
        )
        self.assertIn("Leans toward", html, "header must say 'Leans toward'")
        self.assertIn("Near", html, "header must name the nearest direction")

    def test_header_colour_is_green_for_close(self):
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            self._dirs_with_clear_lean(),
            _norm_identity()
        )
        self.assertIn("#2e9e5b", html, "close lean must use green #2e9e5b")

    def test_header_colour_is_amber_for_mid(self):
        # Mid lean: nearest is moderately apart (sep ≈ 0.37)
        dirs = {"Near": _zfp(tempo=0.5), "Mid": _zfp(tempo=4.0), "Far": _zfp(tempo=9.9)}
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            dirs,
            _norm_identity()
        )
        lean = SC.leans_toward(_zfp(), dirs)
        if lean and lean.level == SC.MID:
            self.assertIn("#d8932a", html, "mid lean must use amber #d8932a")

    def test_far_lean_shows_no_close_direction_yet(self):
        # Two equidistant directions → FAR
        dirs = {"x": _zfp(tempo=5.0), "y": _zfp(dynamics=5.0)}
        lean = SC.leans_toward(_zfp(), dirs)
        if lean and lean.level == SC.FAR:
            html = build_widget.render_reference_read(
                {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity()
            )
            self.assertNotIn("Leans toward", html, "far lean must not name a direction")
            self.assertIn("No close direction", html, "far lean must show 'No close direction yet'")

    def test_empty_directions_returns_empty_string(self):
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, {}, _norm_identity()
        )
        self.assertEqual(html, "", "no directions → empty string")

    def test_none_fingerprint_returns_empty_string(self):
        html = build_widget.render_reference_read(
            None, {"x": _zfp()}, _norm_identity()
        )
        self.assertEqual(html, "", "None fingerprint → empty string")


# D-INV-30 — per-facet reference read vs centroid
class ReferenceReadBars(unittest.TestCase):
    """Per-facet bar rows: at least one row, count matches measured axes per panel, bars are in HTML.

    Uses a SINGLE-direction fixture so the bar count is unambiguous (one panel = len(FP.AXES) bars).
    Multi-direction tab tests live in ReferenceReadTabSelector."""

    @classmethod
    def setUpClass(cls):
        # Single direction → 1 panel → bar count is exactly len(FP.AXES) for a fully-measured track.
        dirs = {"Near": _zfp(tempo=0.2)}
        cls.html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            dirs,
            _norm_identity()
        )

    def test_bar_rows_present(self):
        self.assertIn('class="refread-row"', self.html,
                      "at least one facet bar row must be rendered")

    def test_bar_count_equals_all_axes_when_fully_measured(self):
        # Single direction → 1 panel → exactly len(FP.AXES) bars.
        n_bars = self.html.count('class="refread-row"')
        self.assertEqual(n_bars, len(FP.AXES),
                         f"expected {len(FP.AXES)} bars (all axes measured, 1 panel), got {n_bars}")

    def test_bars_use_bar_html_structure(self):
        self.assertIn('class="refread-barwrap"', self.html,
                      "each bar must have a .refread-barwrap wrapper")
        self.assertIn('class="refread-center"', self.html,
                      "each bar must have a .refread-center marker for zero")
        self.assertIn('class="refread-bar"', self.html,
                      "each bar must have a .refread-bar offset element")

    def test_no_raw_numbers_on_surface(self):
        # D-INV-25: no raw distance/score/percentage text. Bar widths are CSS %; direction is in
        # the label. The offset numbers must only appear as CSS style values, not as text content.
        # We check that no lone float or int is emitted as visible text between tags.
        import re
        # Remove all tag attributes (style="...", etc.) then check there are no stray floats
        stripped = re.sub(r'<[^>]+>', ' ', self.html)
        # Only "No close direction yet" or direction names and labels should remain
        self.assertNotRegex(stripped, r'\b\d+\.\d{3,}\b',
                            "raw numeric values must not appear as visible text (D-INV-25)")


class ReferenceReadOmitsMissingAxes(unittest.TestCase):
    """RC-INV-1: an axis the run did not measure must be omitted, never drawn at zero.

    Both tests use a SINGLE-direction fixture so bar counts are unambiguous (1 panel)."""

    def test_nan_axis_is_omitted_from_bars(self):
        raw = {ax: 0.0 for ax in FP.AXES}
        raw["pad_bright"] = float("nan")   # unmeasured
        dirs = {"Near": _zfp(tempo=0.2)}    # single direction → 1 panel
        html = build_widget.render_reference_read(raw, dirs, _norm_identity())
        n_bars = html.count('class="refread-row"')
        expected = len(FP.AXES) - 1   # all but pad_bright
        self.assertEqual(n_bars, expected,
                         f"nan axis must be omitted: expected {expected} bars, got {n_bars}")
        self.assertNotIn("Pad brightness", html,
                         "label for the nan axis must not appear in bars")

    def test_axis_missing_from_centroid_is_omitted(self):
        raw = {ax: 0.0 for ax in FP.AXES}
        # Centroid missing 'bass_share' — single direction → 1 panel → unambiguous count
        dirs = {"Near": {ax: 0.0 for ax in FP.AXES if ax != "bass_share"}}
        html = build_widget.render_reference_read(raw, dirs, _norm_identity())
        n_bars = html.count('class="refread-row"')
        self.assertEqual(n_bars, len(FP.AXES) - 1,
                         "axis absent from centroid must be omitted from bars")
        self.assertNotIn("Bass share", html,
                         "label for axis missing from centroid must not appear")


class ReferenceReadSummaryLine(unittest.TestCase):
    """A summary line naming closest and furthest facets must be present."""

    def test_summary_line_present(self):
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            {"Near": _zfp(tempo=0.2), "FarDir": _zfp(tempo=9.0)},
            _norm_identity()
        )
        self.assertIn("Closest on:", html, "summary must name closest facets")
        self.assertIn("Furthest on:", html, "summary must name furthest facets")

    def test_summary_names_axis_labels_not_keys(self):
        # The summary must use readable English labels, not internal axis key names
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            {"Near": _zfp(energy_build=2.0), "FarDir": _zfp(tempo=9.0)},
            _norm_identity()
        )
        # "energy_build" (key) must not appear; "Energy build" (label) may appear
        import re
        summary_section = re.search(r'class="refread-summary"[^>]*>([^<]+)<', html)
        if summary_section:
            self.assertNotIn("energy_build", summary_section.group(1),
                             "raw axis key must not appear in summary (use readable label)")


class ReferenceReadMostDivergentFirst(unittest.TestCase):
    """Rows must be ordered most-divergent first."""

    def test_largest_offset_axis_is_first_row(self):
        # Make 'brightness' the most divergent axis by setting a big offset
        raw = {ax: 0.0 for ax in FP.AXES}
        raw["brightness"] = 0.0  # track at 0
        centroid = _zfp(brightness=2.5, tempo=0.1)   # brightness is most divergent
        dirs = {"Near": centroid, "FarDir": _zfp(tempo=9.0)}
        html = build_widget.render_reference_read(raw, dirs, _norm_identity())
        import re
        labels = re.findall(r'class="refread-label">([^<]+)<', html)
        self.assertTrue(labels, "must have at least one label")
        self.assertEqual(labels[0], "Brightness",
                         f"most-divergent axis (Brightness) must be first; got {labels[0]}")


class ReferenceReadTabSelector(unittest.TestCase):
    """§D.10.1 tab selector: up to 3 direction tabs, nearest first, coloured by own level.
    1 direction → no tab bar; 2–3 → tab buttons present; JS switches panels client-side."""

    def _two_dir_html(self):
        """2 qualifying directions: Near (CLOSE) and FarDir (MID as last)."""
        dirs = {"Near": _zfp(tempo=0.2), "FarDir": _zfp(tempo=9.0)}
        return build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity()
        )

    def test_single_direction_no_tab_bar(self):
        """1 qualifying direction → no .reftabs element (monotonic ladder: 1 tab = no tab bar)."""
        dirs = {"Near": _zfp(tempo=0.2)}
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity()
        )
        self.assertNotIn('class="reftabs"', html,
                         "single direction must produce no tab bar")
        self.assertIn('class="refpanel"', html,
                      "single direction must still produce a refpanel content block")

    def test_two_directions_produce_tab_buttons(self):
        html = self._two_dir_html()
        self.assertIn('class="reftabs"', html,
                      "two qualifying directions must produce a .reftabs tab bar")
        self.assertIn('class="reftab active"', html,
                      "first (nearest) tab must be active by default")
        self.assertIn('class="reftab"', html,
                      "at least one non-active tab must be present")

    def test_two_directions_produce_two_panels(self):
        html = self._two_dir_html()
        self.assertEqual(html.count('class="refpanel"'), 2,
                         "two qualifying directions must produce exactly two .refpanel elements")

    def test_first_panel_visible_by_default(self):
        """Nearest direction panel has no display:none (default active)."""
        html = self._two_dir_html()
        # The first panel has no style="display:none"; subsequent ones do.
        import re
        panels = re.findall(r'<div class="refpanel"([^>]*)>', html)
        self.assertTrue(panels, "must have at least one refpanel")
        self.assertNotIn('display:none', panels[0],
                         "first (active) panel must not be hidden")
        if len(panels) > 1:
            self.assertIn('display:none', panels[1],
                          "second panel must be hidden until tab is clicked")

    def test_nearest_tab_coloured_by_close_level(self):
        """The nearest direction tab is coloured green (#2e9e5b) when level is CLOSE."""
        dirs = {"Near": _zfp(tempo=0.1), "FarDir": _zfp(tempo=9.0)}
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity()
        )
        import re
        lean = SC.leans_toward(_zfp(), dirs)
        if lean and lean.level == SC.CLOSE:
            self.assertIn("#2e9e5b", html, "CLOSE nearest tab must use green")

    def test_tab_js_present_for_multi_direction(self):
        """Client-side JS for tab switching must be present when ≥2 tabs exist."""
        html = self._two_dir_html()
        self.assertIn('querySelectorAll(".reftab")', html,
                      "tab-switching JS must be embedded for multi-direction selector")
        self.assertIn('querySelectorAll(".refpanel")', html,
                      "panel-switching JS must be embedded")

    def test_no_tab_js_for_single_direction(self):
        """No tab-switching JS when only 1 direction qualifies."""
        dirs = {"Near": _zfp(tempo=0.2)}
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity()
        )
        self.assertNotIn('querySelectorAll(".reftab")', html,
                         "no tab JS for single-direction (no tabs to switch)")

    def test_bar_count_per_panel_equals_axes_count(self):
        """Each panel must contain bars for all fully-measured axes (len(FP.AXES) per panel)."""
        html = self._two_dir_html()
        n_bars = html.count('class="refread-row"')
        n_panels = html.count('class="refpanel"')
        self.assertGreater(n_panels, 0, "must have at least one panel")
        self.assertEqual(n_bars, n_panels * len(FP.AXES),
                         f"expected {n_panels}×{len(FP.AXES)}={n_panels*len(FP.AXES)} bars, got {n_bars}")


class ReferenceReadDetailedOnly(unittest.TestCase):
    """Detailed-only gate: CSS rule hides the block in Simple; block absent when run_dir=None."""

    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp(prefix="tc_rr_"))
        out = tmp / "widget.html"
        run_dir = _make_run_dir(str(tmp))
        build_widget.build_html(_minimal_core(), {}, None, None, str(out), "RefReadTest",
                                build_widget.STRINGS, run_dir=run_dir)
        cls.html = out.read_text(encoding="utf-8")

    def test_refread_block_in_html(self):
        """Block present in the full-mode widget."""
        self.assertIn('id="refRead"', self.html,
                      "refRead block must be in the widget HTML when run_dir is supplied")

    def test_css_hides_refread_in_simple(self):
        """CSS must gate refRead to Detailed-only."""
        import re
        self.assertRegex(self.html,
                         r"body\.simple\s+#refRead\s*\{[^}]*display\s*:\s*none",
                         "must have body.simple #refRead { display:none ... } rule")

    def test_refread_absent_without_run_dir(self):
        """No run_dir supplied → __REFREAD__ replaced with '' → no block in output."""
        tmp = Path(tempfile.mkdtemp(prefix="tc_rr_norun_"))
        out = tmp / "w.html"
        build_widget.build_html(_minimal_core(), {}, None, None, str(out), "NoRef",
                                build_widget.STRINGS)
        html = out.read_text(encoding="utf-8")
        self.assertNotIn('id="refRead"', html,
                         "widget without run_dir must have no refRead block")

    def test_quick_mode_has_no_refread_block(self):
        """Quick mode → _ref_read_html skipped → no refRead in output."""
        tmp = Path(tempfile.mkdtemp(prefix="tc_rr_quick_"))
        out = tmp / "w.html"
        run_dir = _make_run_dir(str(tmp))
        build_widget.build_html(_minimal_core(), {}, None, None, str(out), "Quick",
                                build_widget.STRINGS, mode="quick", run_dir=run_dir)
        html = out.read_text(encoding="utf-8")
        self.assertNotIn('id="refRead"', html,
                         "quick mode must produce no refRead block (quick ⊆ Simple ⊆ Detailed)")


class LazySparksNearestDirection(unittest.TestCase):
    """Lazy Sparks must lean toward Venetian Snares — matches what the catalog column shows.
    Skipped when the run dir is not present (CI-safe)."""

    LAZY_RUN_DIR = ("/Users/sashaabramovich/Desktop/Projects/Lazy_Sparks/"
                    "Lazy_Sparks Project/track-coach-output/"
                    "Total_Reboot_Lazy_Sparks_edit2026/2026-06-20_2100")

    @unittest.skipUnless(Path(LAZY_RUN_DIR).exists(),
                         "Lazy Sparks run dir not on this machine")
    def test_lean_is_venetian_snares(self):
        ref_path = Path(__file__).resolve().parent.parent / "data" / "reference_directions.json"
        ref_data = json.loads(ref_path.read_text(encoding="utf-8"))
        norm = ref_data.get("_norm", {})
        directions = {k: v for k, v in ref_data.items() if k != "_norm"}
        raw_fp = FP.fingerprint_from_run_dir(self.LAZY_RUN_DIR)
        self.assertIsNotNone(raw_fp, "Lazy Sparks run dir must yield a fingerprint")
        track_z = FP.normalize_fingerprint(raw_fp, norm)
        lean = SC.leans_toward(track_z, directions)
        self.assertIsNotNone(lean, "Lazy Sparks must lean toward some direction")
        self.assertEqual(lean.direction, "Venetian Snares",
                         f"expected Venetian Snares lean, got {lean.direction}")

    @unittest.skipUnless(Path(LAZY_RUN_DIR).exists(),
                         "Lazy Sparks run dir not on this machine")
    def test_refread_block_renders_venetian_snares_for_lazy(self):
        """render_reference_read for Lazy Sparks must name Venetian Snares in the HTML."""
        ref_path = Path(__file__).resolve().parent.parent / "data" / "reference_directions.json"
        ref_data = json.loads(ref_path.read_text(encoding="utf-8"))
        norm = ref_data.get("_norm", {})
        directions = {k: v for k, v in ref_data.items() if k != "_norm"}
        raw_fp = FP.fingerprint_from_run_dir(self.LAZY_RUN_DIR)
        html = build_widget.render_reference_read(raw_fp, directions, norm)
        self.assertIn("Venetian Snares", html,
                      "reference read for Lazy Sparks must name Venetian Snares")
        self.assertIn("Leans toward", html,
                      "reference read for Lazy Sparks must show 'Leans toward'")


# D-INV-29 — web-style ★/☆ plaque (facets tied to measurement)
class ReferenceReadRichLook(unittest.TestCase):
    """Category chips, plain-words column, ★/☆ marks — the rich look ported from the explorer.
    Tests covering D-INV-25 (no raw numbers) and the confirmation map logic (D-INV-24).
    """

    # ── fixtures ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def _html_no_conf(cls):
        """Single direction, NO confirmation data → chips + words but NO star marks."""
        return build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            {"Near": _zfp(tempo=0.2)},
            _norm_identity(),
        )

    @classmethod
    def _html_direct_agrees(cls):
        """Centroid z=-0.8 on tempo (expect=low) → agrees with direct → ★"""
        centroid = _zfp(tempo=-0.8)
        conf = {"TestDir": [{"axis": "tempo", "expect": "low", "tier": "direct"}]}
        return build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            {"TestDir": centroid},
            _norm_identity(),
            confirmation=conf,
            confirm_z=0.4,
        )

    @classmethod
    def _html_indirect_agrees(cls):
        """Centroid z=-0.8 on tempo (expect=low) + tier=indirect → ☆"""
        centroid = _zfp(tempo=-0.8)
        conf = {"TestDir": [{"axis": "tempo", "expect": "low", "tier": "indirect"}]}
        return build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            {"TestDir": centroid},
            _norm_identity(),
            confirmation=conf,
            confirm_z=0.4,
        )

    @classmethod
    def _html_contradicted(cls):
        """Centroid z=+0.8 on tempo but expect=low → contradicted → no star."""
        centroid = _zfp(tempo=0.8)
        conf = {"TestDir": [{"axis": "tempo", "expect": "low", "tier": "direct"}]}
        return build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            {"TestDir": centroid},
            _norm_identity(),
            confirmation=conf,
            confirm_z=0.4,
        )

    @classmethod
    def _html_near_mean(cls):
        """Centroid z=-0.1 on tempo (|z|<0.4) → near mean → no star even if expect=low."""
        centroid = _zfp(tempo=-0.1)
        conf = {"TestDir": [{"axis": "tempo", "expect": "low", "tier": "direct"}]}
        return build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            {"TestDir": centroid},
            _norm_identity(),
            confirmation=conf,
            confirm_z=0.4,
        )

    # ── category chips ────────────────────────────────────────────────────────────────────

    def test_category_chips_present(self):
        """Every row must have a category chip (Mix / Balance / Character)."""
        html = self._html_no_conf()
        self.assertIn('class="refread-cat"', html,
                      "refread rows must carry category chips")

    def test_mix_chip_appears(self):
        html = self._html_no_conf()
        self.assertIn(">Mix<", html, "Mix category chip text must appear")

    def test_balance_chip_appears(self):
        html = self._html_no_conf()
        self.assertIn(">Balance<", html, "Balance category chip text must appear")

    def test_character_chip_appears(self):
        html = self._html_no_conf()
        self.assertIn(">Character<", html, "Character category chip text must appear")

    # ── plain-words column ────────────────────────────────────────────────────────────────

    def test_words_column_present(self):
        """refread-words span must appear in every rendered block."""
        html = self._html_no_conf()
        self.assertIn('class="refread-words"', html,
                      "plain-words column must be present in every row")

    def test_words_column_contains_human_text(self):
        """Words column must contain one of the five agreed terms."""
        html = self._html_no_conf()
        self.assertTrue(
            any(w in html for w in ["matched", "higher", "lower"]),
            "words column must contain 'matched', 'higher', or 'lower'",
        )

    def test_char_chip_on_character_axes(self):
        """'char' chip must appear for Character axes (pad_sustain, bass_sustain, etc.)."""
        html = self._html_no_conf()
        self.assertIn('refread-chip"', html,
                      "'char' chip must appear for Character axes")

    # ── no raw numbers ────────────────────────────────────────────────────────────────────

    def test_no_raw_decimal_numbers_in_visible_text(self):
        """D-INV-25: no bare decimals in visible text of the reference-read block.
        Bar widths live in CSS style attributes (stripped before check)."""
        import re
        html = self._html_no_conf()
        m = re.search(r'id="refRead"', html)
        self.assertIsNotNone(m, "refRead block must be present")
        # Strip all HTML tags (removes style="...", attr="...") so only visible text remains
        stripped = re.sub(r"<[^>]+>", " ", html)
        self.assertNotRegex(
            stripped,
            r"\b\d+\.\d+\b",
            "raw decimal numbers must not appear as visible text in refRead (D-INV-25)",
        )

    # ── ★ marks (tier=direct, centroid agrees) ────────────────────────────────────────────
    # NOTE: literal ★/☆ chars also appear in the legend, so we detect row-level stars via the
    # CSS class (refread-star / refread-halfstar) and the data-confirmed attribute instead.

    def test_star_appears_when_direct_centroid_agrees(self):
        """Direct, agreed centroid → row marked with data-confirmed + non-halfstar star span."""
        html = self._html_direct_agrees()
        # data-confirmed marks a ★/☆ row (not the legend)
        self.assertIn('data-confirmed="1"', html,
                      "data-confirmed must be present when tier=direct and centroid agrees")
        # The direct star is a refread-star span WITHOUT the halfstar class
        self.assertIn(
            'title="Web-described trait, confirmed directly by measurement">★',
            html,
            "★ span with 'confirmed directly' title must be present",
        )

    def test_confirmed_row_has_data_confirmed_attr(self):
        """A confirmed row must carry data-confirmed=1 (used for CSS tinting)."""
        html = self._html_direct_agrees()
        self.assertIn('data-confirmed="1"', html,
                      "confirmed rows must have data-confirmed attribute for CSS tinting")

    # ── ☆ marks (tier=indirect, centroid agrees) ─────────────────────────────────────────

    def test_halfstar_appears_when_indirect_centroid_agrees(self):
        """Indirect, agreed centroid → data-confirmed + refread-halfstar span."""
        html = self._html_indirect_agrees()
        self.assertIn('data-confirmed="1"', html,
                      "data-confirmed must be present for indirect confirmation")
        # The indirect star uses the refread-halfstar class
        self.assertIn("refread-halfstar", html,
                      "refread-halfstar class must be present for indirect tier")
        # The row must NOT have a plain (direct) star title
        self.assertNotIn(
            "confirmed directly",
            html,
            "indirect confirmation must not emit a direct-star title",
        )

    # ── no mark when contradicted or near mean ────────────────────────────────────────────

    def test_no_star_when_centroid_contradicts(self):
        """data-confirmed must be absent when the centroid contradicts the expect."""
        html = self._html_contradicted()
        self.assertNotIn('data-confirmed', html,
                         "data-confirmed must not appear when centroid contradicts expect")

    def test_no_star_when_centroid_near_mean(self):
        """data-confirmed must be absent when |centroid z| < confirm_z."""
        html = self._html_near_mean()
        self.assertNotIn('data-confirmed', html,
                         "data-confirmed must not appear when centroid is near the mean")

    # ── legend ───────────────────────────────────────────────────────────────────────────

    def test_legend_present(self):
        """A refread-legend div explaining ★/☆ and the char chip must be in the block."""
        html = self._html_no_conf()
        self.assertIn('class="refread-legend"', html,
                      "refread-legend must be present in the reference-read block")


class ViewURLHash(unittest.TestCase):
    """JOB-2: URL hash encodes the view state — #detailed opens Detailed on load;
    toggling calls history.replaceState to keep the hash in sync."""

    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp(prefix="tc_urlhash_"))
        out = tmp / "widget.html"
        run_dir = _make_run_dir(str(tmp))
        build_widget.build_html(_minimal_core(), {}, None, None, str(out), "URLHashTest",
                                build_widget.STRINGS, run_dir=run_dir)
        cls.html = out.read_text(encoding="utf-8")

    def test_url_hash_detailed_read_on_load(self):
        """The JS must detect #detailed / #full in location.hash to open Detailed view."""
        self.assertIn("detail", self.html,
                      "JS must check 'detail' keyword in location.hash")

    def test_apply_calls_replace_state(self):
        """The apply() function must call history.replaceState to update the URL hash on toggle."""
        self.assertIn("replaceState", self.html,
                      "apply() must call history.replaceState to update the URL hash")

    def test_view_inited_flag_present(self):
        """A guard flag must prevent replaceState from firing on the initial apply() call."""
        self.assertIn("_viewInited", self.html,
                      "a _viewInited guard must prevent URL write on initial load")

    def test_simple_hash_written_on_toggle(self):
        """The 'simple' hash string must be referenced in the toggle JS."""
        self.assertIn("'#simple'", self.html,
                      "replaceState must write '#simple' when toggling to Simple view")

    def test_detailed_hash_written_on_toggle(self):
        """The 'detailed' hash string must be referenced in the toggle JS."""
        self.assertIn("'#detailed'", self.html,
                      "replaceState must write '#detailed' when toggling to Detailed view")


# §D.10.2 / §D.10.3 — read order + web-info plaque (s28 redesign)

class ReadOrderWithRefRead(unittest.TestCase):
    """§D.10.3 read order: #tonalPanel must precede #refRead, which must precede #webPanel.
    Asserts on the REAL rendered widget HTML (with run_dir so refRead is present).
    """

    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp(prefix="tc_rr_order_"))
        out = tmp / "widget.html"
        run_dir = _make_run_dir(str(tmp))
        build_widget.build_html(_minimal_core(), {}, None, None, str(out), "ReadOrderTest",
                                build_widget.STRINGS, run_dir=run_dir)
        cls.html = out.read_text(encoding="utf-8")

    def test_tonal_before_refread(self):
        """tonalPanel must appear in the HTML BEFORE refRead (§D.10.3 order)."""
        tonal_pos = self.html.find('id="tonalPanel"')
        refread_pos = self.html.find('id="refRead"')
        self.assertGreater(tonal_pos, 0, "tonalPanel must be in the HTML")
        self.assertGreater(refread_pos, 0, "refRead must be in the HTML when run_dir is supplied")
        self.assertLess(tonal_pos, refread_pos,
                        "tonalPanel must come BEFORE refRead (§D.10.3 read order)")

    def test_refread_before_web_panel_summary(self):
        """If the web panel element is present, refRead must precede it in the HTML."""
        refread_pos = self.html.find('id="refRead"')
        # Search for the webPanel element id, not the CSS comment that also says "What the web says"
        web_pos = self.html.find('id="webPanel"')
        if web_pos > 0:
            self.assertLess(refread_pos, web_pos,
                            "refRead must come BEFORE the #webPanel element in the HTML")


class WebPanelRendering(unittest.TestCase):
    """§D.10.2 web-info plaque — collapsed, summary, artist header, ★/☆ facet lines with phrases.
    Asserts on the OUTPUT of render_reference_read (the real shipped function), not source.
    """

    @classmethod
    def _html_with_web_data(cls):
        """render_reference_read with synthetic data that guarantees ★ for one direct facet."""
        dirs = {"TestArtist": _zfp(tempo=-0.8)}   # centroid z=-0.8 on tempo, expect=low → agrees
        conf = {"TestArtist": [
            {"axis": "tempo",  "expect": "low", "tier": "direct",   "phrase": "slow meditative tempo"},
            {"axis": "stereo", "expect": "low", "tier": "indirect", "phrase": "narrow stereo"},
        ]}
        return build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            dirs,
            _norm_identity(),
            confirmation=conf,
            confirm_z=0.4,
        )

    def test_web_panel_present_when_facet_earns_mark(self):
        html = self._html_with_web_data()
        self.assertIn('id="webPanel"', html,
                      "web panel must be present when ≥1 facet earns ★ or ☆")

    def test_web_panel_collapsed_no_open_attr(self):
        """Panel must be collapsed — <details> must NOT carry the `open` attribute."""
        html = self._html_with_web_data()
        import re
        # `<details id="webPanel"` must NOT be followed immediately by ` open`
        self.assertNotRegex(html, r'<details\s+id="webPanel"\s+open',
                            "web panel <details> must not carry the `open` attribute (stays collapsed)")

    def test_web_panel_summary_names_artist(self):
        html = self._html_with_web_data()
        self.assertIn("What the web says about TestArtist", html,
                      "web panel summary must name the focused artist")

    def test_web_panel_has_artist_sub_header(self):
        html = self._html_with_web_data()
        self.assertIn('class="web-artist-hdr"', html,
                      "web panel must carry an artist sub-header element")

    def test_web_panel_has_phrase_and_glyph(self):
        """At least one facet line must carry the phrase text and a ★ or ☆ glyph."""
        html = self._html_with_web_data()
        self.assertIn("slow meditative tempo", html,
                      "the phrase from confirmation data must appear in the web panel")
        self.assertIn("★", html,
                      "★ glyph must appear for a confirmed direct facet")

    def test_web_panel_in_refread_region(self):
        """The web panel must appear in the HTML after the #refRead block (within the REFREAD slot)."""
        html = self._html_with_web_data()
        refread_pos = html.find('id="refRead"')
        webpanel_pos = html.find('id="webPanel"')
        self.assertGreater(refread_pos, 0, "refRead block must be present")
        self.assertGreater(webpanel_pos, refread_pos,
                           "webPanel must appear after (within the same __REFREAD__ slot as) refRead")

    def test_web_panel_absent_when_no_marks(self):
        """No ★/☆ possible — contradicted facet → panel absent."""
        dirs = {"TestArtist": _zfp(tempo=0.8)}   # centroid z=+0.8, expect=low → CONTRADICTED
        conf = {"TestArtist": [
            {"axis": "tempo", "expect": "low", "tier": "direct", "phrase": "slow tempo"},
        ]}
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity(),
            confirmation=conf, confirm_z=0.4,
        )
        self.assertNotIn('id="webPanel"', html,
                         "web panel must be absent when no facet earns ★ or ☆")


# §D.10.2 rich panel — blurb, genre_era, sorted tiers, bar ★/☆ regression (s28 / 0.9.2)

class WebPanelRichRendering(unittest.TestCase):
    """§D.10.2 rich panel via web_notes: blurb + genre_era + full sorted trait list.
    Tests assert on the rendered HTML from render_reference_read (the real shipped function).

    Coverage:
    - blurb and genre_era appear in the panel body
    - a ★ tier row (direct+confirmed) appears
    - a 'web says · our tracks don't show it' row (none-tier) appears
    - ★ row appears BEFORE the 'web says' row in the HTML (sorted correctly)
    - panel absent when direction has no blurb and no traits (liveness rule §D.10.2)
    - bar ★/☆ (inline in centroid bars) still renders when web_notes is the sole source
      — one-source principle: confirmation auto-derived from web_notes (§D.10.2)
    - contradicted direct trait lands in 'web says' tier, not shown as ★
    """

    @classmethod
    def _rich_html(cls):
        """render_reference_read with web_notes that yields ★ (confirmed), ☆ (indirect confirmed),
        and a 'web says' row (none-tier) — for the focused direction 'TestArtist'."""
        # tempo centroid z=-0.8 → confirms expect=low (★ for direct).
        # energy_build centroid z=-0.8 → confirms expect=low (☆ for indirect).
        # brightness centroid z=0.0 → does NOT confirm expect=high (→ 'web says' for direct).
        # odd_trait: tier=none, axis=null → always 'web says'.
        dirs = {"TestArtist": _zfp(tempo=-0.8, energy_build=-0.8)}
        web_notes = {"TestArtist": {
            "artist": "TestArtist",
            "genre_era": "Test genre / era",
            "blurb": "A short test blurb about this artist.",
            "traits": [
                {"phrase": "slow tempo",         "axis": "tempo",        "expect": "low",  "tier": "direct"},
                {"phrase": "constant intensity",  "axis": "energy_build", "expect": "low",  "tier": "indirect"},
                {"phrase": "bright highs",        "axis": "brightness",   "expect": "high", "tier": "direct"},
                {"phrase": "odd time signatures", "axis": None,           "expect": None,   "tier": "none"},
            ]
        }}
        return build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            dirs,
            _norm_identity(),
            web_notes=web_notes,
            confirm_z=0.4,
        )

    def test_blurb_in_panel(self):
        """Blurb text must appear in the rich panel body."""
        html = self._rich_html()
        self.assertIn("A short test blurb about this artist.", html,
                      "blurb must appear in the rich web panel")

    def test_genre_era_in_panel(self):
        """Genre/era line must appear in the rich panel body."""
        html = self._rich_html()
        self.assertIn("Test genre / era", html,
                      "genre_era must appear in the rich web panel")

    def test_star_row_appears_for_confirmed_direct(self):
        """A directly confirmed trait (centroid agrees) must appear with ★ glyph."""
        html = self._rich_html()
        self.assertIn("slow tempo", html, "confirmed direct phrase must be in the panel")
        self.assertIn("★", html, "★ glyph must appear for confirmed direct trait")

    def test_halfstar_row_appears_for_confirmed_indirect(self):
        """An indirectly confirmed trait (centroid agrees) must appear with ☆ glyph."""
        html = self._rich_html()
        self.assertIn("constant intensity", html, "confirmed indirect phrase must be in the panel")
        self.assertIn("☆", html, "☆ glyph must appear for confirmed indirect trait")

    def test_nosay_row_appears_for_none_tier(self):
        """A none-tier trait must appear with 'web says' badge — never silently dropped (⟨D-30⟩)."""
        html = self._rich_html()
        self.assertIn("odd time signatures", html,
                      "none-tier phrase must appear in the panel (show-labeled, not silent-drop)")
        self.assertIn("web says", html,
                      "'web says' pill must appear for none-tier traits")

    def test_nosay_row_appears_for_contradicted_direct(self):
        """B3 design change (s29): the rich panel now uses render_reference_notes, which reads
        the static `tier` field from the JSON entry — no centroid-Z dynamic re-sorting.
        A trait with tier='direct' always renders as is-direct (★ pill), regardless of whether
        the current track's centroid agrees. The phrase must still appear; now under the
        static-tier class, not a centroid-dependent web-facet-nosay element."""
        html = self._rich_html()
        self.assertIn("bright highs", html,
                      "contradicted direct phrase must still appear in the panel")
        # Static tier: tier='direct' → is-direct pill, regardless of centroid agreement.
        # (Centroid-Z re-sorting was removed from the web panel in B3/s29.)
        self.assertIn("tc-rn-pill is-direct", html,
                      "static tier=direct → is-direct pill (no centroid re-sort in B3)")

    def test_star_row_before_nosay_row(self):
        """★ tier row must appear BEFORE 'web says' row (sorted by status, strongest first)."""
        html = self._rich_html()
        star_pos  = html.find("slow tempo")
        nosay_pos = html.find("odd time signatures")
        self.assertGreater(star_pos, 0, "★-tier phrase must be in the HTML")
        self.assertGreater(nosay_pos, 0, "'web says' phrase must be in the HTML")
        self.assertLess(star_pos, nosay_pos,
                        "★ row must appear BEFORE 'web says' row in the HTML (sorted by tier)")

    def test_panel_absent_when_no_web_content(self):
        """A direction with empty blurb and empty traits → panel absent (§D.10.2 liveness rule)."""
        dirs = {"EmptyDir": _zfp(tempo=-0.8)}
        web_notes = {"EmptyDir": {
            "artist": "EmptyDir",
            "genre_era": "",
            "blurb": "",
            "traits": []
        }}
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity(),
            web_notes=web_notes, confirm_z=0.4,
        )
        self.assertNotIn('id="webPanel"', html,
                         "panel must be absent when direction has no blurb and no traits")

    def test_bar_star_derived_from_web_notes(self):
        """Bar ★/☆ (in centroid bars) must still render when web_notes is the sole source —
        confirmation is auto-derived from web_notes' direct/indirect traits (one-source principle)."""
        dirs = {"TestArtist": _zfp(tempo=-0.8)}
        web_notes = {"TestArtist": {
            "artist": "TestArtist",
            "genre_era": "test",
            "blurb": "test blurb",
            "traits": [
                {"phrase": "slow tempo", "axis": "tempo", "expect": "low", "tier": "direct"},
            ]
        }}
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity(),
            web_notes=web_notes, confirm_z=0.4,
        )
        self.assertIn('data-confirmed="1"', html,
                      "bar ★ must appear when web_notes drives both the panel and the bar marks")

    def test_panel_present_when_only_nosay_traits(self):
        """Panel must show even when all traits are in the 'web says' tier (panel absent only with
        no content at all — §D.10.2 liveness rule after ⟨D-30⟩ resolution)."""
        dirs = {"TestArtist": _zfp(tempo=0.8)}     # centroid agrees with NOTHING (all contradicted)
        web_notes = {"TestArtist": {
            "artist": "TestArtist",
            "genre_era": "genre",
            "blurb": "blurb text",
            "traits": [
                {"phrase": "slow tempo", "axis": "tempo", "expect": "low", "tier": "direct"},
            ]
        }}
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, dirs, _norm_identity(),
            web_notes=web_notes, confirm_z=0.4,
        )
        self.assertIn('id="webPanel"', html,
                      "panel must be present even when all traits land in the 'web says' tier "
                      "(panel absent only when there is no web content whatsoever)")


if __name__ == "__main__":
    unittest.main()
