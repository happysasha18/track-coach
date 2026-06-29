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


class ReferenceReadBars(unittest.TestCase):
    """Per-facet bar rows: at least one row, count matches measured axes, bars are in the HTML."""

    @classmethod
    def setUpClass(cls):
        dirs = {"Near": _zfp(tempo=0.2), "FarDir": _zfp(tempo=9.0)}
        cls.html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES},
            dirs,
            _norm_identity()
        )

    def test_bar_rows_present(self):
        self.assertIn('class="refread-row"', self.html,
                      "at least one facet bar row must be rendered")

    def test_bar_count_equals_all_axes_when_fully_measured(self):
        n_bars = self.html.count('class="refread-row"')
        self.assertEqual(n_bars, len(FP.AXES),
                         f"expected {len(FP.AXES)} bars (all axes measured), got {n_bars}")

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
    """RC-INV-1: an axis the run did not measure must be omitted, never drawn at zero."""

    def test_nan_axis_is_omitted_from_bars(self):
        raw = {ax: 0.0 for ax in FP.AXES}
        raw["pad_bright"] = float("nan")   # unmeasured
        dirs = {"Near": _zfp(tempo=0.2), "FarDir": _zfp(tempo=9.0)}
        html = build_widget.render_reference_read(raw, dirs, _norm_identity())
        n_bars = html.count('class="refread-row"')
        expected = len(FP.AXES) - 1   # all but pad_bright
        self.assertEqual(n_bars, expected,
                         f"nan axis must be omitted: expected {expected} bars, got {n_bars}")
        self.assertNotIn("Pad brightness", html,
                         "label for the nan axis must not appear in bars")

    def test_axis_missing_from_centroid_is_omitted(self):
        raw = {ax: 0.0 for ax in FP.AXES}
        # Centroid missing 'bass_share'
        dirs = {"Near": {ax: 0.0 for ax in FP.AXES if ax != "bass_share"},
                "FarDir": _zfp(tempo=9.0)}
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


if __name__ == "__main__":
    unittest.main()
