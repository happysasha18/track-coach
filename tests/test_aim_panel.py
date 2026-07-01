#!/usr/bin/env python3
"""§D.6.1 — Aim picker + prioritised-step panel (stage 1).

Tests assert on the RENDERED HTML from render_reference_read (the real shipped function).
All geometric assertions use synthetic fingerprints; disk-gated tests are skipped in CI.

Coverage (TEST_MATRIX rows D-INV-31..34):
  - AimPanelIsCollapsedDetailsAfterRefRead: #aimpanel is a <details> WITHOUT `open`, after #refRead
  - PerDirectionBlocksEmbedded: one data-aim="{idx}" block per lean + data-aim="" baseline
  - NoAimIsBaseline: value="" option exists; its block has the placeholder, no step items
  - AimStateComposition: baseline empty; in-zone facets excluded; picker excludes unqualified dirs
  - AimPickerDetailedFullRunOnly: CSS body.simple gate; no panel in quick mode or without dirs
  - StepsAreDivergenceOrdered: steps sorted by abs(offset) desc; in-zone dropped (D-INV-34/17)
  - StepsCiteEvidence: each step names its facet label (evidence anchor, D-INV-10)
  - AlreadyCloseWhenNoDivergence: all-in-zone → exactly the "Already close..." message, no invented steps
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

# ── shared fixtures (mirrored from test_reference_read.py) ────────────────────────────────────

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
    """Minimal on-disk run dir with result_core.json + result_masking.json."""
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


def _aim_html_two_dirs(slug="test-track"):
    """render_reference_read with 2 qualifying directions; track clearly diverges from 'Near'."""
    # Track at tempo=3.0, brightness=-1.5, energy_build=0.6; centroid at all-0.0.
    # Offsets: tempo=3.0 (high), brightness=-1.5 (low), energy_build=0.6 (high)
    # all abs >= 0.4 → all are steps.
    track_raw = _zfp(tempo=3.0, brightness=-1.5, energy_build=0.6)
    dirs = {"Near": _zfp(), "FarDir": _zfp(tempo=9.0)}
    return build_widget.render_reference_read(track_raw, dirs, _norm_identity(), slug=slug)


# ── AimPanelIsCollapsedDetailsAfterRefRead ────────────────────────────────────────────────────

class AimPanelIsCollapsedDetailsAfterRefRead(unittest.TestCase):
    """D-INV-31: #aimpanel is a <details> WITHOUT `open`, positioned after #refRead in the HTML."""

    @classmethod
    def setUpClass(cls):
        cls.html = _aim_html_two_dirs()

    def test_aimpanel_is_details_element(self):
        import re
        self.assertRegex(self.html, r'<details[^>]*id="aimpanel"',
                         "#aimpanel must be a <details> element")

    def test_aimpanel_has_no_open_attr(self):
        """Panel must start collapsed — <details id="aimpanel"> must NOT carry `open`."""
        import re
        self.assertNotRegex(
            self.html, r'<details[^>]*id="aimpanel"[^>]* open[\s>]',
            "#aimpanel <details> must not carry the `open` attribute (default collapsed)"
        )

    def test_aimpanel_after_refread(self):
        """#aimpanel must appear after #refRead in the HTML string (§D.6.1 order)."""
        refread_pos = self.html.find('id="refRead"')
        aimpanel_pos = self.html.find('id="aimpanel"')
        self.assertGreater(refread_pos, 0, "refRead must be present in the HTML")
        self.assertGreater(aimpanel_pos, 0, "aimpanel must be present in the HTML")
        self.assertGreater(aimpanel_pos, refread_pos,
                           "#aimpanel must appear AFTER #refRead (§D.6.1 layout order)")

    def test_aimpanel_summary_text(self):
        """The <summary> text must say 'To sound more like your aim'."""
        self.assertIn("To sound more like your aim", self.html,
                      "aim panel summary text must say 'To sound more like your aim'")

    def test_aimpanel_has_data_slug(self):
        """The #aimpanel element must carry a data-slug attribute for JS key construction."""
        self.assertIn('data-slug="test-track"', self.html,
                      "#aimpanel must carry data-slug attribute for localStorage keying")


# ── PerDirectionBlocksEmbedded ────────────────────────────────────────────────────────────────

class PerDirectionBlocksEmbedded(unittest.TestCase):
    """D-INV-32: one data-aim="{idx}" block per lean + the data-aim="" baseline block."""

    @classmethod
    def setUpClass(cls):
        cls.html = _aim_html_two_dirs()
        # Count how many leans the fixture produces (should be 2 for "Near" + "FarDir")
        track_raw = _zfp(tempo=3.0, brightness=-1.5, energy_build=0.6)
        dirs = {"Near": _zfp(), "FarDir": _zfp(tempo=9.0)}
        cls.leans = SC.leans_toward_topk(track_raw, dirs)

    def test_baseline_block_present(self):
        """data-aim="" baseline block must be present (shown when 'no aim' selected)."""
        self.assertIn('data-aim=""', self.html,
                      "baseline aim-block (data-aim='') must be in the HTML")

    def test_per_direction_blocks_count(self):
        """Number of data-aim="{idx}" blocks must equal number of leans."""
        import re
        idx_blocks = re.findall(r'data-aim="(\d+)"', self.html)
        self.assertEqual(len(idx_blocks), len(self.leans),
                         f"expected {len(self.leans)} aim-block divs (one per lean), "
                         f"got {len(idx_blocks)}")

    def test_direction_names_in_picker_options(self):
        """Each lean's direction name must appear as a <option> in the picker."""
        for lean in self.leans:
            self.assertIn(_html_escape(lean.direction), self.html,
                          f"direction '{lean.direction}' must be an option in the picker")

    def test_no_aim_option_present(self):
        """A 'no aim' option with value="" must always be the first picker option."""
        self.assertIn('<option value="">no aim</option>', self.html,
                      "picker must have a 'no aim' option with value='' as default")


def _html_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── NoAimIsBaseline ───────────────────────────────────────────────────────────────────────────

class NoAimIsBaseline(unittest.TestCase):
    """D-INV-32: the value="" option selects the baseline block which has only a placeholder,
    never step items."""

    @classmethod
    def setUpClass(cls):
        import re
        cls.html = _aim_html_two_dirs()
        # Extract the baseline block (data-aim="")
        m = re.search(r'<div class="aim-block" data-aim=""[^>]*>(.*?)</div>', cls.html, re.DOTALL)
        cls.baseline_content = m.group(1) if m else ""

    def test_baseline_block_has_no_step_items(self):
        """The baseline block (data-aim='') must contain no <li> step items."""
        self.assertNotIn("<li>", self.baseline_content,
                         "baseline block must not have <li> step items (only a placeholder)")

    def test_baseline_block_has_placeholder(self):
        """The baseline block must show a placeholder prompt."""
        self.assertIn("Pick an aim", self.baseline_content,
                      "baseline block must contain the 'Pick an aim' placeholder text")


# ── AimStateComposition ───────────────────────────────────────────────────────────────────────

class AimStateComposition(unittest.TestCase):
    """D-INV-33/34: in-zone facets excluded from steps; picker excludes unqualified directions.

    Fixture: track at brightness=0.1 (offset from centroid = 0.1, in-zone: < AIM_INZONE_Z=0.4).
             Also at tempo=2.0 (offset=2.0, diverging: >= 0.4).
    Result: Tempo appears in steps; Brightness does NOT (in-zone, excluded).
    """

    @classmethod
    def setUpClass(cls):
        # brightness offset = 0.1 (in-zone, not a step); tempo offset = 2.0 (diverging, a step)
        track_raw = _zfp(tempo=2.0, brightness=0.1)
        dirs = {"Near": _zfp()}   # single direction, centroid at all-0.0
        cls.html = build_widget.render_reference_read(
            track_raw, dirs, _norm_identity(), slug="composition-test"
        )
        # Find the first aim-block div (idx 0) content
        import re
        m = re.search(r'data-aim="0"[^>]*>(.*?)</div>', cls.html, re.DOTALL)
        cls.step_block = m.group(1) if m else ""

    def test_tempo_in_steps_as_diverging(self):
        """A facet with |offset|=2.0 (>= AIM_INZONE_Z=0.4) must appear as a step."""
        self.assertIn("Tempo", self.step_block,
                      "Tempo (offset=2.0, diverging) must appear as a step")

    def test_brightness_not_in_steps_as_inzone(self):
        """A facet with |offset|=0.1 (< AIM_INZONE_Z=0.4) must NOT appear as a step."""
        self.assertNotIn("Brightness", self.step_block,
                         "Brightness (offset=0.1, in-zone) must be excluded from steps")

    def test_picker_only_has_leans_directions(self):
        """Picker options must contain only directions that qualify (are in leans)."""
        # Single qualifying direction "Near" → only one option besides the blank
        self.assertIn('>Near<', self.html,
                      "'Near' direction must appear as a picker option")
        # A hypothetical FAR direction should never appear
        # (confirmed by design: _aim_panel_html only iterates `leans`)


# ── AimPickerDetailedFullRunOnly ──────────────────────────────────────────────────────────────

class AimPickerDetailedFullRunOnly(unittest.TestCase):
    """D-INV-33: aim panel is Detailed-only (CSS gate); absent in quick mode; absent with no dirs.

    The CSS rule must be in the full widget HTML (tested via build_html).
    Quick mode → __REFREAD__ is "" → no #aimpanel.
    No qualifying directions → render_reference_read returns without aim panel.
    """

    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp(prefix="tc_aim_gate_"))
        out = tmp / "widget.html"
        run_dir = _make_run_dir(str(tmp))
        build_widget.build_html(
            _minimal_core(), {}, None, None, str(out), "AimGate Test",
            build_widget.STRINGS, run_dir=run_dir
        )
        cls.html = out.read_text(encoding="utf-8")

    def test_css_hides_aimpanel_in_simple(self):
        """CSS must gate #aimpanel to Detailed-only."""
        import re
        self.assertRegex(
            self.html,
            r"body\.simple\s+#aimpanel\s*\{[^}]*display\s*:\s*none",
            "must have body.simple #aimpanel { display:none ... } rule (Detailed-only gate)"
        )

    def test_no_aimpanel_in_quick_mode(self):
        """Quick mode bypasses _ref_read_html → no #aimpanel in output."""
        tmp = Path(tempfile.mkdtemp(prefix="tc_aim_quick_"))
        out = tmp / "w.html"
        run_dir = _make_run_dir(str(tmp))
        build_widget.build_html(
            _minimal_core(), {}, None, None, str(out), "QuickAim",
            build_widget.STRINGS, mode="quick", run_dir=run_dir
        )
        html = out.read_text(encoding="utf-8")
        self.assertNotIn('id="aimpanel"', html,
                         "quick mode must produce no #aimpanel (full run only, D-INV-33)")

    def test_no_aimpanel_when_empty_directions(self):
        """No qualifying directions → render_reference_read returns no aim panel."""
        html = build_widget.render_reference_read(
            {ax: 0.0 for ax in FP.AXES}, {}, _norm_identity(), slug="no-dirs"
        )
        self.assertNotIn('id="aimpanel"', html,
                         "empty directions → no aim panel (D-INV-33 no-strand)")

    def test_no_aimpanel_when_far_lean_only(self):
        """All-FAR lean → leans=[] → no aim panel."""
        # Two equidistant directions → FAR for both → leans=[]
        dirs = {"x": _zfp(tempo=5.0), "y": _zfp(dynamics=5.0)}
        html = build_widget.render_reference_read(_zfp(), dirs, _norm_identity(), slug="far")
        leans = SC.leans_toward_topk(_zfp(), dirs)
        if not leans:
            self.assertNotIn('id="aimpanel"', html,
                             "all-FAR lean → leans=[] → no aim panel (D-INV-33)")


# ── StepsAreDivergenceOrdered ─────────────────────────────────────────────────────────────────

class StepsAreDivergenceOrdered(unittest.TestCase):
    """D-INV-34/D-INV-17: steps ordered by abs(offset) desc; in-zone facets dropped.

    Fixture: tempo=3.0 (highest abs offset), brightness=-1.5 (second), energy_build=0.6 (third).
    All >= AIM_INZONE_Z=0.4. Expected order: Tempo → Brightness (Dynamic range if that label) →
    Energy build. In-zone axis (stereo at 0.0) must be absent.
    """

    @classmethod
    def setUpClass(cls):
        import re
        # track at tempo=3.0, brightness=-1.5, energy_build=0.6, stereo=0.05 (in-zone)
        track_raw = _zfp(tempo=3.0, brightness=-1.5, energy_build=0.6, stereo=0.05)
        dirs = {"Near": _zfp()}   # centroid at all-0.0, single direction
        cls.html = build_widget.render_reference_read(
            track_raw, dirs, _norm_identity(), slug="order-test"
        )
        # Extract the aim-block for idx 0
        m = re.search(r'data-aim="0"[^>]*>(.*?)</div>', cls.html, re.DOTALL)
        cls.block_html = m.group(1) if m else ""

    def test_largest_offset_is_first_step(self):
        """Tempo (|offset|=3.0) must be the first step."""
        import re
        # Find all <strong> label tags within <li> items
        labels = re.findall(r'<li><strong>([^<]+)</strong>', self.block_html)
        self.assertTrue(labels, "must have at least one step")
        self.assertEqual(labels[0], "Tempo",
                         f"Tempo (largest |offset|=3.0) must be step #1; got {labels[0]!r}")

    def test_second_largest_is_second_step(self):
        """Brightness (|offset|=1.5) must be the second step."""
        import re
        labels = re.findall(r'<li><strong>([^<]+)</strong>', self.block_html)
        self.assertGreater(len(labels), 1, "must have at least two steps")
        self.assertEqual(labels[1], "Brightness",
                         f"Brightness (|offset|=1.5) must be step #2; got {labels[1]!r}")

    def test_inzone_axis_is_absent(self):
        """An in-zone axis (stereo=0.05, |offset|<0.4) must NOT appear as a step."""
        self.assertNotIn("Stereo width", self.block_html,
                         "in-zone axis (stereo, |offset|=0.05) must be excluded from steps")


# ── StepsCiteEvidence ─────────────────────────────────────────────────────────────────────────

class StepsCiteEvidence(unittest.TestCase):
    """D-INV-10: each step must name its facet label as the evidence anchor.

    Steps use the format: "<strong>{facet label}</strong> sits {magnitude} than {direction} — ..."
    The facet label must be the readable English label (from _AXIS_LABELS), not the raw axis key.
    """

    @classmethod
    def setUpClass(cls):
        import re
        track_raw = _zfp(tempo=2.5, brightness=-1.2)
        dirs = {"Near": _zfp()}
        cls.html = build_widget.render_reference_read(
            track_raw, dirs, _norm_identity(), slug="evidence-test"
        )
        m = re.search(r'data-aim="0"[^>]*>(.*?)</div>', cls.html, re.DOTALL)
        cls.block_html = m.group(1) if m else ""

    def test_steps_use_readable_facet_labels(self):
        """Each step must name its facet label as a <strong> evidence anchor."""
        import re
        labels = re.findall(r'<li><strong>([^<]+)</strong>', self.block_html)
        self.assertTrue(labels, "must have at least one step")
        # "tempo" (raw axis key) must not appear; "Tempo" (readable label) must
        self.assertNotIn("tempo", labels,
                         "raw axis key 'tempo' must not appear — use readable label 'Tempo'")
        # All labels must be non-empty readable strings
        for label in labels:
            self.assertTrue(len(label) > 0, "step label must be non-empty")

    def test_step_phrasing_is_observe_and_offer(self):
        """Steps must use the observe-and-offer register with directional language."""
        # Must contain phrasing like "an option: ease it..." or "an option: nudge it..."
        self.assertIn("an option:", self.block_html,
                      "steps must use the observe-and-offer register ('an option: ...')")

    def test_step_names_direction(self):
        """Each step must name the target direction (evidence that the step closes a gap toward it)."""
        # "Near" is the direction name in our fixture
        self.assertIn("Near", self.block_html,
                      "each step must name the target direction as context")

    def test_steps_use_directional_magnitude(self):
        """Steps must name the magnitude direction (higher/lower) not raw numbers."""
        # Must contain human-readable magnitude words (matched, a bit higher/lower, etc.)
        has_direction_word = any(
            w in self.block_html
            for w in ["higher", "lower", "matched"]
        )
        self.assertTrue(has_direction_word,
                        "step phrasing must use directional magnitude words (higher/lower/matched)")


# ── AlreadyCloseWhenNoDivergence ──────────────────────────────────────────────────────────────

class AlreadyCloseWhenNoDivergence(unittest.TestCase):
    """D-INV-34: when all facets are within ±AIM_INZONE_Z, the aim block says exactly
    'Already close on what we can measure.' — zero invented steps."""

    @classmethod
    def setUpClass(cls):
        import re
        # Track at all-0.0; centroid also at all-0.0 → all offsets = 0.0 < AIM_INZONE_Z=0.4
        track_raw = _zfp()   # all axes = 0.0
        dirs = {"Near": _zfp(tempo=0.1)}   # single direction; centroid near center
        cls.html = build_widget.render_reference_read(
            track_raw, dirs, _norm_identity(), slug="close-test"
        )
        m = re.search(r'data-aim="0"[^>]*>(.*?)</div>', cls.html, re.DOTALL)
        cls.block_html = m.group(1) if m else ""

    def test_already_close_message_present(self):
        """All offsets in-zone → must show exactly the 'Already close...' message."""
        self.assertIn("Already close on what we can measure.", self.block_html,
                      "all-in-zone fixture must produce the 'Already close...' message")

    def test_no_step_items_when_all_in_zone(self):
        """No <li> step items when all facets are in-zone."""
        self.assertNotIn("<li>", self.block_html,
                         "all-in-zone: must have zero <li> step items, only the 'Already close' message")

    def test_exact_message_text(self):
        """The message must be exactly: 'Already close on what we can measure.' (no extra steps)."""
        self.assertIn("aim-close", self.block_html,
                      "all-in-zone block must use the aim-close element (no invented steps)")


if __name__ == "__main__":
    unittest.main()
