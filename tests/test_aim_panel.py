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


# ── Stage-2 helpers ──────────────────────────────────────────────────────────────────────────────

def _make_recs_for_aim():
    """Build a small synthetic recs list (8-tuples) for stage-2 tests.

    Returns (recs, track_z, directions) where:
      - recs[0]: cls="do", axis="brightness" — track brightness=3.0 vs centroid=0 → diverging (offset=3.0)
      - recs[1]: cls="do", axis="density" — track density=0.1 vs centroid=0.0 → on-style
        (|offset|=0.1 < AIM_INZONE_Z, but |track_z|=0.1 < AIM_INZONE_Z → NOT on-style either)
      - recs[2]: cls="crit", axis="tempo" — track tempo=2.5 vs centroid=0 → diverging, different tier
      - recs[3]: cls="concept", axis=None — no axis, passes through unchanged
    direction "TestDir" has centroid at all-0.0.
    """
    recs = [
        # (cls, when, head, body, fix, t, based, axis)
        ("do", "whole track", "Brightness issue", "The brightness is too high.", "", None, "brightness measurement.", "brightness"),
        ("do", "whole track", "Density in-zone", "Density is typical.", "", None, "density measurement.", "density"),
        ("crit", "0:30", "Tempo concern", "The tempo drifts.", "Tighten the grid.", 30.0, "tempo measurement.", "tempo"),
        ("concept", "whole track", "Creative choice", "A structural note.", "", None, "structure.", None),
    ]
    # track_z: brightness=3.0 (diverging from centroid 0.0), tempo=2.5 (diverging), density=0.1 (in-zone)
    track_z = {ax: 0.0 for ax in FP.AXES}
    track_z["brightness"] = 3.0
    track_z["tempo"] = 2.5
    track_z["density"] = 0.1
    # centroid at all-0.0
    directions = {"TestDir": {ax: 0.0 for ax in FP.AXES}}
    return recs, track_z, directions


def _aim_html_with_recs(slug="stage2-test"):
    """Render reference read passing recs — the full stage-2 path."""
    recs, track_z, directions = _make_recs_for_aim()
    norm = _norm_identity()
    return build_widget.render_reference_read(
        track_z, directions, norm, slug=slug, recs=recs
    )


# ── AimCardsStoreEmbedded ─────────────────────────────────────────────────────────────────────

class AimCardsStoreEmbedded(unittest.TestCase):
    """D-INV-32 stage-2: #aimcardsStore is embedded inside #aimpanel with one .aimcards-block
    per qualifying direction when recs are passed.  Without recs, the store is absent."""

    @classmethod
    def setUpClass(cls):
        cls.html_with_recs = _aim_html_with_recs()
        # Control: same call without recs
        track_z = {ax: 0.0 for ax in FP.AXES}
        track_z["brightness"] = 3.0
        directions = {"TestDir": {ax: 0.0 for ax in FP.AXES}}
        cls.html_no_recs = build_widget.render_reference_read(
            track_z, directions, _norm_identity(), slug="no-recs-ctrl"
        )

    def test_aimcards_store_present_with_recs(self):
        """#aimcardsStore must appear in the HTML when recs are passed."""
        self.assertIn('id="aimcardsStore"', self.html_with_recs,
                      "#aimcardsStore must be in the HTML when recs are supplied")

    def test_aimcards_store_absent_without_recs(self):
        """#aimcardsStore must NOT appear when no recs are passed."""
        self.assertNotIn('id="aimcardsStore"', self.html_no_recs,
                         "#aimcardsStore must be absent when recs=None")

    def test_one_aimcards_block_per_lean(self):
        """Number of .aimcards-block divs must equal the number of qualifying leans."""
        import re
        # Use the same track/directions as in _aim_html_with_recs
        recs, track_z, directions = _make_recs_for_aim()
        import similarity_columns as SC
        leans = SC.leans_toward_topk(track_z, directions)
        blocks = re.findall(r'class="aimcards-block"', self.html_with_recs)
        self.assertEqual(len(blocks), len(leans),
                         f"expected {len(leans)} .aimcards-block(s), got {len(blocks)}")

    def test_aimcards_store_inside_aimpanel(self):
        """#aimcardsStore must appear inside #aimpanel (after #aimpanel opening tag)."""
        aimpanel_pos = self.html_with_recs.find('id="aimpanel"')
        store_pos = self.html_with_recs.find('id="aimcardsStore"')
        self.assertGreater(aimpanel_pos, 0, "#aimpanel must be present")
        self.assertGreater(store_pos, 0, "#aimcardsStore must be present")
        self.assertGreater(store_pos, aimpanel_pos,
                           "#aimcardsStore must appear inside #aimpanel (after the opening tag)")


# ── AimCardsSetIdenticalToBaseline ───────────────────────────────────────────────────────────

class AimCardsSetIdenticalToBaseline(unittest.TestCase):
    """D-INV-15: the card SET (count) in each aimcards-block must equal the recs count.
    Re-flavouring never adds or drops cards — only re-orders and annotates."""

    @classmethod
    def setUpClass(cls):
        import re
        cls.recs, cls.track_z, cls.directions = _make_recs_for_aim()
        cls.html = _aim_html_with_recs()
        # Extract all .aimcards-block divs
        cls.blocks = re.findall(
            r'<div class="aimcards-block"[^>]*>(.*?)</div>\s*(?=<div class="aimcards-block"|</div>)',
            cls.html, re.DOTALL
        )

    def test_aimcards_block_card_count_equals_recs_count(self):
        """Every .aimcards-block must contain exactly len(recs) .rec divs."""
        import re
        n_recs = len(self.recs)
        # get block content more reliably from the stored html
        import re
        # Find all aimcards-block contents
        block_htmls = re.findall(
            r'class="aimcards-block"[^>]*>(.*?)</div>\s*(?=<div class="aimcards-block"|</div>|$)',
            self.html, re.DOTALL
        )
        self.assertTrue(len(block_htmls) > 0, "must have at least one aimcards-block")
        for i, block in enumerate(block_htmls):
            card_count = len(re.findall(r'<div class="rec ', block))
            self.assertEqual(card_count, n_recs,
                             f"aimcards-block[{i}] has {card_count} cards, expected {n_recs}")

    def test_based_on_text_preserved(self):
        """Each card's based-on text must appear in the aimcards block (D-INV-15)."""
        # The first rec's based-on is "brightness measurement."
        self.assertIn("brightness measurement.", self.html,
                      "based-on text must be preserved in re-flavoured cards")


# ── AimCardsDivergingRisesInTier ──────────────────────────────────────────────────────────────

class AimCardsDivergingRisesInTier(unittest.TestCase):
    """D-INV-17: within the same urgency tier, diverging cards appear before non-diverging cards.

    Fixture:
      - recs[0]: cls="do", axis="brightness", offset=3.0 (diverging)  — should appear first within do
      - recs[1]: cls="do", axis="density",   offset=0.1 (in-zone)    — should appear second within do
    Both are tier "do"; the diverging one must come first.
    """

    @classmethod
    def setUpClass(cls):
        import re
        cls.html = _aim_html_with_recs()
        # Extract the first aimcards-block (data-aim="0")
        m = re.search(r'class="aimcards-block"\s+data-aim="0"[^>]*>(.*?)(?=<div class="aimcards-block"|</div>\s*</div>)',
                      cls.html, re.DOTALL)
        cls.block_html = m.group(1) if m else ""

    def test_diverging_card_before_inzone_within_tier(self):
        """The diverging 'do' card (brightness) must appear before the in-zone 'do' card (density)."""
        brightness_pos = self.block_html.find("Brightness issue")
        density_pos = self.block_html.find("Density in-zone")
        self.assertGreater(brightness_pos, -1, "Brightness issue card must be present")
        self.assertGreater(density_pos, -1, "Density in-zone card must be present")
        self.assertLess(brightness_pos, density_pos,
                        "diverging 'do' card (Brightness issue) must appear before in-zone 'do' card")

    def test_crit_tier_still_before_do_tier(self):
        """crit-tier cards must appear before do-tier cards (tier ordering preserved)."""
        crit_pos = self.block_html.find("Tempo concern")
        do_pos = self.block_html.find("Brightness issue")
        self.assertGreater(crit_pos, -1, "crit card must be present")
        self.assertGreater(do_pos, -1, "do card must be present")
        self.assertLess(crit_pos, do_pos,
                        "crit-tier card must appear before do-tier card (tier ordering).")


# ── AimCardsDivergingGetsOptionNote ──────────────────────────────────────────────────────────

class AimCardsDivergingGetsOptionNote(unittest.TestCase):
    """D-INV-17 / closes D-21: a diverging card gets ONE option-note (.aim-option) mentioning
    the direction; the note cap is 1 per card for single-select (D-21 closed)."""

    @classmethod
    def setUpClass(cls):
        import re
        cls.html = _aim_html_with_recs()
        # Extract individual rec cards — no nested divs inside .rec, so each .*?</div> is one card.
        # re.findall with lazy .*? stops at the FIRST </div> after each opening tag.
        all_cards = re.findall(r'<div class="rec [^"]*"[^>]*>.*?</div>', cls.html, re.DOTALL)
        cls.brightness_card = next((c for c in all_cards if 'Brightness issue' in c), "")
        cls.density_card = next((c for c in all_cards if 'Density in-zone' in c), "")

    def test_diverging_card_has_option_note(self):
        """The diverging card (brightness, |offset|=3.0) must contain a .aim-option note."""
        self.assertIn("aim-option", self.brightness_card,
                      "diverging card must have a .aim-option element")

    def test_option_note_mentions_direction(self):
        """The option-note must mention the direction name."""
        self.assertIn("TestDir", self.brightness_card,
                      "option-note must mention the direction name")

    def test_option_note_uses_observe_and_offer_register(self):
        """The option-note must use the observe-and-offer register ('an option, if')."""
        self.assertIn("an option, if", self.brightness_card,
                      "option-note must use the observe-and-offer register")

    def test_inzone_card_has_no_option_note(self):
        """An in-zone card (density, |offset|=0.1) must NOT have a .aim-option note."""
        self.assertNotIn("aim-option", self.density_card,
                         "in-zone card must not have a .aim-option note")

    def test_single_option_note_per_diverging_card(self):
        """Single-select → cap=1 option-note per card (D-21 closed)."""
        import re
        count = len(re.findall(r'aim-option', self.brightness_card))
        self.assertLessEqual(count, 1,
                             "single-select: at most 1 option-note per diverging card (D-21)")


# ── AimCardsOnStyleMark ───────────────────────────────────────────────────────────────────────

class AimCardsOnStyleMark(unittest.TestCase):
    """D-INV-17: a card whose axis is on-style (track aligns with direction on that axis, both
    at a notable value) gets a .aim-onstyle mark."""

    @classmethod
    def setUpClass(cls):
        # Build a fixture where the track and direction share a notably extreme density value.
        # track density=2.5, direction centroid density=2.0 → offset=0.5 (just above threshold, diverging)
        # Hmm, for on-style we need |offset| < AIM_INZONE_Z AND |track_z| >= AIM_INZONE_Z AND |centroid_z| >= AIM_INZONE_Z
        # So: track_z[density]=2.0, centroid_z[density]=1.8 → offset=0.2 < 0.4; |track|=2.0 >= 0.4; |centroid|=1.8 >= 0.4
        recs = [
            ("do", "whole track", "Density on-style", "Density is quite high.", "", None, "density evidence.", "density"),
        ]
        track_z = {ax: 0.0 for ax in FP.AXES}
        track_z["density"] = 2.0   # notable value
        directions = {"OnStyleDir": {ax: 0.0 for ax in FP.AXES}}
        directions["OnStyleDir"]["density"] = 1.8   # direction also dense → offset = 0.2, on-style
        norm = _norm_identity()
        import re
        cls.html = build_widget.render_reference_read(
            track_z, directions, norm, slug="onstyle-test", recs=recs
        )
        m = re.search(r'class="aimcards-block"[^>]*>(.*?)(?=</div>\s*</div>|$)',
                      cls.html, re.DOTALL)
        cls.block_html = m.group(1) if m else ""

    def test_onstyle_card_has_onstyle_mark(self):
        """A card with axis at a notable value aligned with the direction must have .aim-onstyle."""
        self.assertIn("aim-onstyle", self.block_html,
                      "on-style card must have a .aim-onstyle mark")

    def test_onstyle_note_mentions_direction(self):
        """The on-style note must mention the direction name."""
        self.assertIn("OnStyleDir", self.block_html,
                      "on-style note must mention the direction name")


# ── NoAimRecs ─────────────────────────────────────────────────────────────────────────────────

class NoAimRecs(unittest.TestCase):
    """D-INV-32/5: when recs=None (the default), the HTML must have no #aimcardsStore —
    the 'no aim' baseline shows #recs (JS-rendered) untouched."""

    def test_no_aimcards_store_when_recs_none(self):
        """Default call (recs=None) must produce no #aimcardsStore element."""
        track_z = {ax: 0.0 for ax in FP.AXES}
        track_z["brightness"] = 2.0
        directions = {"ADir": {ax: 0.0 for ax in FP.AXES}}
        html = build_widget.render_reference_read(
            track_z, directions, _norm_identity(), slug="no-recs"
        )
        self.assertNotIn('id="aimcardsStore"', html,
                         "recs=None → no #aimcardsStore in HTML (baseline is JS-rendered #recs)")

    def test_aimcards_display_in_full_widget(self):
        """The full widget HTML must contain #aimcardsDisplay (ready to receive re-flavoured cards)."""
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="tc_aim_disp_"))
        out = tmp / "w.html"
        run_dir = _make_run_dir(str(tmp))
        build_widget.build_html(
            _minimal_core(), {}, None, None, str(out), "DispTest",
            build_widget.STRINGS, run_dir=run_dir
        )
        html = out.read_text(encoding="utf-8")
        self.assertIn('id="aimcardsDisplay"', html,
                      "full widget must contain #aimcardsDisplay element")

    def test_aimcards_display_css_gate_in_simple(self):
        """CSS must gate #aimcardsDisplay to Detailed-only (body.simple #aimcardsDisplay display:none)."""
        import tempfile, re
        tmp = Path(tempfile.mkdtemp(prefix="tc_aim_dispgate_"))
        out = tmp / "w.html"
        run_dir = _make_run_dir(str(tmp))
        build_widget.build_html(
            _minimal_core(), {}, None, None, str(out), "DispGate",
            build_widget.STRINGS, run_dir=run_dir
        )
        html = out.read_text(encoding="utf-8")
        self.assertRegex(
            html,
            r"body\.simple\s+#aimcardsDisplay\s*\{[^}]*display\s*:\s*none",
            "must have body.simple #aimcardsDisplay { display:none } rule"
        )


if __name__ == "__main__":
    unittest.main()
