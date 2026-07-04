"""Whole-artifact completeness gate — browser-level (INV-GATE / INV-45 / INV-46).

WHY this exists: the suite had ~660+ tests that asserted specific strings or DOM stubs
with no real browser rendering. Two classes of failure kept slipping through:
  (a) a panel silently empties (no data wired → self-hides → Alexander notices by eye),
  (b) a catalog backpointer is dead or missing.
The suite stayed green because no test checked whether every user-facing panel was
POPULATED in a full-widget render.

This gate renders a SYNTHETIC FULL widget (labelled as such) exercising every panel —
core, masking, als, stemmap, rhythm, notes, narrative, catalog, back_href, stems_web —
and asserts 20+ surface-level completeness criteria in headless Chrome.

FIXTURE: SYNTHETIC — built in this test, not from a real run dir.
Reason: the most complete real run dir (Wobble Drift, 2026-07-03) has large real .m4a
audio files (impractical to copy/load in a test) and no controlled back_href. A synthetic
fixture gives full panel coverage with precise, minimal data and no disk dependency.

Red-on-partial check: assertions about missing panels are also run on a PARTIAL fixture
(no als, no notes, no narrative) to prove the gate CATCHES emptiness.

CONVERGENCE MECHANISM (INV-46): USER_SURFACES is the single source of truth.
  (a) USER_SURFACES maps every surface id → its render condition + owning gate test.
  (b) A DOM-scan test scans every <details class="tc-panel" id="..."> in the rendered
      widget. Any id NOT in USER_SURFACES fails the scan — a new panel is red until
      registered. PROOF: test_CONV_probe_scan_detects_unregistered uses a widget with
      an injected __probe_unregistered panel and verifies the scan catches it.
  (c) test_CONV_every_registry_entry_has_gate_test verifies every non-DEFERRED
      USER_SURFACES entry has a gate test method on this class (registry ⊆ gated).

Net invariant: suite green ⟺ every rendered surface is registered AND gated.

INV-GATE: every user-facing panel is POPULATED in a full widget render (browser level).
INV-45: near-silent stems auto-start muted (CR-2 APPROVED behavior, Alexander 2026-07-03).
INV-46: surface registry + DOM-scan convergence mechanism.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402
import headless_check as hc  # noqa: E402

_HAVE_CHROME = Path(hc.CHROME).exists()

N = 16  # time bins
DUR = 120.0

# ── Surface Registry (INV-46) ─────────────────────────────────────────────────
# Central registry of every user-facing surface rendered by the full widget.
#
# Maps DOM element id → {
#   "condition": when this element is present
#     "always"        – present in every full render
#     "when-als"      – present when .als data was loaded
#     "when-stemmap"  – present when stemmap data was loaded
#     "when-rhythm"   – present when rhythm data was loaded
#     "when-notes"    – present when notes data was loaded
#     "DEFERRED"      – §D feature, not in 1.0 standard render
#   "gated_by": the gate test method name that asserts this surface is populated
# }
#
# DOM-SCAN INVARIANT: every <details class="tc-panel" id="..."> in a rendered full widget
# MUST have its id here. A new panel without a registry entry makes
# test_CONV_all_rendered_panels_are_registered fail (red). A registry entry without a
# gate method makes test_CONV_every_registry_entry_has_gate_test fail (red).
USER_SURFACES = {
    # ── Main details panels (scanned by DOM-scan) ────────────────────────────
    "storyPanel":  {"condition": "always",       "gated_by": "test_3_arc_canvas_rendered"},
    "recsPanel":   {"condition": "always",       "gated_by": "test_5_recs_cards_have_title_and_body"},
    "readPanel":   {"condition": "always",       "gated_by": "test_6_producers_read_nonempty"},
    "tonalPanel":  {"condition": "always",       "gated_by": "test_7_tonal_balance_bars_present"},
    "evidence":    {"condition": "always",       "gated_by": "test_8_evidence_container_visible"},
    "arrPanel":    {"condition": "when-als",     "gated_by": "test_8_arrangement_panel_nonempty"},
    "autoPanel":   {"condition": "when-als",     "gated_by": "test_8_automation_panel_nonempty"},
    "mapPanel":    {"condition": "when-stemmap", "gated_by": "test_8_stemmap_panel_nonempty"},
    "rhyPanel":    {"condition": "when-rhythm",  "gated_by": "test_8_rhythm_panel_nonempty"},
    "notePanel":   {"condition": "when-notes",   "gated_by": "test_8_notes_panel_nonempty"},
    "catalog":     {"condition": "always",       "gated_by": "test_19_catalog_rows_and_hrefs"},
    # ── §D deferred — no reference direction in the standard 1.0 render ─────
    # These appear ONLY when a reference aim is set; not required in standard render.
    "refRead":     {"condition": "DEFERRED",     "gated_by": None},
    "webPanel":    {"condition": "DEFERRED",     "gated_by": None},
}


# ── Synthetic full-fixture data ───────────────────────────────────────────────

def _core() -> dict:
    tb = [round(i * DUR / N, 3) for i in range(N)]
    return {
        "duration_s": DUR, "time_bins": tb, "tempo": 123,
        "energy":       [round(0.2 + 0.6 * i / N, 3) for i in range(N)],
        "brightness":   [round(0.1 + 0.7 * i / N, 3) for i in range(N)],
        "density":      [round(0.3 + 0.4 * (i % 5) / 5, 3) for i in range(N)],
        "wobble_rate":  [round(1.0 + (i % 4), 3) for i in range(N)],
        "stereo_width": [round(0.4 + 0.3 * (i % 3) / 3, 3) for i in range(N)],
        "energy_trend": 0.5, "brightness_trend": 0.6, "density_trend": 0.05,
        "stereo_width_trend": 0.1,
        "wobble_rate_start_hz": 3.0, "wobble_rate_end_hz": 3.2,
        "section_bounds_s": [30.0, 60.0, 90.0],
        "endpoint_cosine": 0.97,
        "vitals": {
            "tempo_bpm": 123,
            "key": "G minor",
            "key_conf": 0.85,
            "duration_s": DUR,
            "lufs": -14.0,
            "true_peak_db": -0.5,
            "dynamic_range_db": 9,
            "stereo_width": 0.55,
            "phase_corr": 0.42,   # L/R correlation → the 9th vitals slot "Phase" (real widgets carry it;
                                  # the gate must scan it too — Fable audit 2026-07-03, INV-47 hygiene)
        },
        "tonal_balance": [
            {"band": "60",   "rel_db": 0.0,   "dev_db": 0.0},
            {"band": "120",  "rel_db": -2.0,  "dev_db": 1.0},
            {"band": "250",  "rel_db": -4.0,  "dev_db": 6.0},
            {"band": "500",  "rel_db": -6.0,  "dev_db": -2.0},
            {"band": "2k",   "rel_db": -9.0,  "dev_db": 0.0},
            {"band": "8k",   "rel_db": -14.0, "dev_db": -5.0},
        ],
    }


def _masking() -> dict:
    """Three significant stems: drums, bass, other."""
    BANDS = ["sub", "low", "low_mid", "mid", "hi_mid", "air"]
    BIG = -20.0
    def _band(v):
        return {b: [float(v)] * N for b in BANDS}
    return {
        "stems_analysed": ["drums", "bass", "other"],
        "total_windows": N,
        "time_bins": [round(i * DUR / N, 3) for i in range(N)],
        "duration_s": DUR,
        "band_rms_db": {"drums": _band(BIG), "bass": _band(BIG), "other": _band(BIG)},
        "masking_summary": {},
        "masking_flags": {},
        "sustain": {"bass": 0.8, "other": 0.4},
        "spectral_centroid": {"drums": 300.0, "bass": 120.0, "other": 800.0},
        "spectral_flatness": {},
        "spectrum": {},
        "spectrum_freqs": None,
    }


def _masking_with_silent_other() -> dict:
    """Masking data where 'other' is near-silent (below STEM_EMPTY_FLOOR_DB = -55 dB).
    Broadband for -80 dB per-band is ~-72 dB, well below the -55 dB floor.
    Used to test CR-2 auto-mute behavior (INV-45).
    """
    BANDS = ["sub", "low", "low_mid", "mid", "hi_mid", "air"]
    BIG    = -20.0
    SILENT = -80.0  # broadband ~-72 dB → below STEM_EMPTY_FLOOR_DB (-55 dB)
    def _band(v):
        return {b: [float(v)] * N for b in BANDS}
    return {
        "stems_analysed": ["drums", "bass", "other"],
        "total_windows": N,
        "time_bins": [round(i * DUR / N, 3) for i in range(N)],
        "duration_s": DUR,
        "band_rms_db": {"drums": _band(BIG), "bass": _band(BIG), "other": _band(SILENT)},
        "masking_summary": {},
        "masking_flags": {},
        "sustain": {"bass": 0.8},  # "other" is silent, excluded
        "spectral_centroid": {"drums": 300.0, "bass": 120.0, "other": 800.0},
        "spectral_flatness": {},
        "spectrum": {},
        "spectrum_freqs": None,
    }


def _als() -> dict:
    """Minimal als with one MIDI track (arrangement lane) and one automation (automation panel)."""
    return {
        "bpm": 123,
        "time_signature": "4/4",
        "time_sig_changes": [{"time_s": 0.0, "sig": "4/4"}],
        "markers": [
            {"time_s": 0.0,  "name": "Intro"},
            {"time_s": 60.0, "name": "Drop"},
        ],
        "tracks": [
            {
                "name": "Bass MIDI",
                "midi_clips": [{"start_s": 0.0, "end_s": 120.0, "note_count": 48}],
                "audio_clips": [],
                "automations": [
                    {
                        "param": "cutoff",
                        "device": "filter",
                        "varies": True,
                        "events": [
                            {"time_s": 0.0,   "value": 0.2},
                            {"time_s": 40.0,  "value": 0.6},
                            {"time_s": 80.0,  "value": 0.9},
                            {"time_s": 120.0, "value": 0.5},
                        ],
                    }
                ],
            }
        ],
        "track_count": 1,
        "total_midi_notes": 48,
        "total_audio_clips": 0,
    }


def _stemmap() -> dict:
    return {
        "stems": {
            "drums": {
                "verdict": "clear", "best_family": "drums",
                "verdict_text": "Tracks the drums family closely.",
                "family_matches": [{"family": "drums", "r": 0.85},
                                   {"family": "other", "r": 0.1}],
            },
            "bass": {
                "verdict": "clear", "best_family": "bass",
                "verdict_text": "Tracks the bass family closely.",
                "family_matches": [{"family": "bass", "r": 0.90},
                                   {"family": "other", "r": 0.05}],
            },
            "other": {
                "verdict": "mixed", "best_family": None,
                "verdict_text": "Has signal, but timing follows several parts.",
                "family_matches": [{"family": "other", "r": 0.30},
                                   {"family": "lead",  "r": 0.20}],
            },
        },
        "model_recommendation": "a 6-stem model",
        "model_why": "The project has melodic parts.",
        "export_suggestion": None,
    }


def _rhythm() -> dict:
    return {
        "rhythm": {
            "drums": {"onset_rate": 4.0, "offgrid_ms": 5.0, "syncopation_pct": 10.0,
                      "onset_density": [1.0] * N},
            "bass":  {"onset_rate": 0.5, "offgrid_ms": 8.0, "syncopation_pct": 5.0,
                      "onset_density": [1.0] * N},
        },
        "separation": {
            "reconstruction_error_db": -28.0,
            "reconstruction_text": "The parts add back up cleanly.",
            "leakage": [],
        },
    }


def _notes() -> dict:
    return {
        "label": "other",
        "notes": [{"t": 0.0, "dur": 0.5, "pitch": 60, "amp": 0.8},
                  {"t": 1.0, "dur": 0.5, "pitch": 64, "amp": 0.7}],
        "pitch_min": 60,
        "pitch_max": 64,
        "n_notes": 2,
    }


def _catalog(widget_path: str) -> dict:
    return {
        "self_track": "Gate Test Track",
        "tracks": [{
            "track": "Gate Test Track",
            "self": True,
            "runs": [{
                "version": "v1",
                "date": "2026-07-03 10:00",
                "verdict": "A synthetic track for testing.",
                "mode": "full",
                "rel": Path(widget_path).name,
                "self": True,
                "exists": True,
            }],
        }],
        "n_tracks": 1,
        "n_runs": 1,
    }


def _build_full_widget(tmp: Path) -> str:
    """Build a SYNTHETIC FULL widget (every panel populated) in the given tmp dir.

    SYNTHETIC — not a real analysis; all data constructed inline to give precise
    control over every panel and avoid large audio file dependencies.
    Returns the path to the widget HTML.
    """
    # Stems web: dummy .m4a files (existence is all the player checks for src)
    sw = tmp / "stems_web"
    sw.mkdir()
    for stem in ("drums", "bass", "other"):
        (sw / f"{stem}.m4a").write_bytes(b"\x00" * 16)

    # Real catalog target (back_href) — a minimal HTML file so the href resolves
    lib_index = tmp / "library_index.html"
    lib_index.write_text("<html><body>Library</body></html>")

    out = tmp / "widget_full.html"
    core = _core()

    from datetime import datetime
    build_widget.build_html(
        core, {}, _masking(), _als(), str(out),
        "Gate Test Track",
        build_widget.STRINGS,
        als_offset_s=0.0,
        stemmap=_stemmap(),
        rhythm=_rhythm(),
        notes=_notes(),
        audio_stems_rel="stems_web",
        narrative_md=(
            "## What I hear\n\nThe track opens with a clean kick and bassline. "
            "The energy builds steadily into the drop.\n\n"
            "## What needs attention\n\nThe high end accumulates past bar 32."
        ),
        catalog=_catalog(str(out)),
        back_href=lib_index.as_uri(),
        meta={
            "audio": "gate_test.wav",
            "als":   "gate_test.als",   # INV-GATE §4: srcmeta shows BOTH audio AND .als filename
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "built_at":    datetime.now().strftime("%Y-%m-%d"),
        },
        mode="full",
    )
    return str(out)


def _build_partial_widget(tmp: Path) -> str:
    """Build a PARTIAL widget (no als, no notes, no narrative) — used to prove the
    gate CATCHES emptiness: assertions about those missing panels must fail."""
    out = tmp / "widget_partial.html"
    build_widget.build_html(
        _core(), {}, None, None, str(out),
        "Partial Gate Test",
        build_widget.STRINGS,
        mode="full",
    )
    return str(out)


def _build_probe_widget(full_html_path: str, tmp: Path) -> str:
    """Build a probe widget by injecting an unregistered panel into the full widget HTML.

    CONVERGENCE PROOF (INV-46): this widget contains a <details class="tc-panel"
    id="__probe_unregistered"> element that is NOT in USER_SURFACES. The DOM-scan
    test (test_CONV_probe_scan_detects_unregistered) must find it and report it as
    unregistered — proving the scan catches new panels added without registration.

    After the proof, the injection is NOT in any normal render, so the production
    test (test_CONV_all_rendered_panels_are_registered) stays green.
    """
    src = Path(full_html_path).read_text(encoding="utf-8")
    # Inject immediately after the foot div (inside the .wrap container)
    injection = (
        '<details class="tc-panel" id="__probe_unregistered">'
        '<summary>Probe (unregistered — for convergence test only)</summary>'
        '<p>probe content</p></details>'
    )
    foot_marker = '<div class="foot" id="foot"></div>'
    assert foot_marker in src, "probe injection: foot marker not found in widget HTML"
    src = src.replace(foot_marker, foot_marker + "\n" + injection, 1)
    out = tmp / "widget_probe.html"
    out.write_text(src, encoding="utf-8")
    return str(out)


def _build_muted_stem_widget(tmp: Path) -> str:
    """Build a widget with 'other' stem near-silent to test CR-2 auto-mute (INV-45).

    SYNTHETIC — 'other' stem is at -80 dB per band, broadband ~-72 dB,
    well below STEM_EMPTY_FLOOR_DB (-55 dB). It therefore lands in D.stem.omitted
    and the player JS starts it MUTED (CR-2 approved behavior).
    """
    sw = tmp / "stems_web_muted"
    sw.mkdir(exist_ok=True)
    for stem in ("drums", "bass", "other"):
        (sw / f"{stem}.m4a").write_bytes(b"\x00" * 16)

    out = tmp / "widget_muted_stem.html"
    from datetime import datetime
    build_widget.build_html(
        _core(), {}, _masking_with_silent_other(), None, str(out),
        "Muted Stem Test",
        build_widget.STRINGS,
        audio_stems_rel="stems_web_muted",
        meta={
            "audio": "muted_test.wav",
            "als": None,
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "built_at":    datetime.now().strftime("%Y-%m-%d"),
        },
        mode="full",
    )
    return str(out)


def _build_quick_widget(tmp: Path) -> str:
    """Build a SYNTHETIC QUICK widget: mix-only — NO stems, NO .als, NO stemmap/rhythm/notes.
    A quick run has no evidence data, so every #evidence sub-panel self-hides — the config that
    exposed the empty-#evidence-opens-to-nothing bug (Fable audit 2026-07-03). The always-panels
    (arc, tonal, read, recs, catalog) stay populated so the empty-collapsible scan flags ONLY the
    genuinely empty container, not a false positive."""
    lib_index = tmp / "library_index_quick.html"
    lib_index.write_text("<html><body>Library</body></html>")
    out = tmp / "widget_quick.html"
    from datetime import datetime
    build_widget.build_html(
        _core(), {}, {}, None, str(out),
        "Quick Gate Track",
        build_widget.STRINGS,
        narrative_md=(
            "## What I hear\n\nA mix-only quick read: clean kick, a steady build into the drop.\n\n"
            "## What needs attention\n\nThe high end accumulates past bar 32."
        ),
        catalog=_catalog(str(out)),
        back_href=lib_index.as_uri(),
        meta={
            "audio": "quick_test.wav",
            "als": None,   # quick = no Ableton project
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "built_at":    datetime.now().strftime("%Y-%m-%d"),
        },
        mode="quick",
    )
    return str(out)


# ── Shared probe helpers ──────────────────────────────────────────────────────

def _probe(widget: str, js: str, width: int = 1200, height: int = 3200) -> object:
    return hc.probe(widget, js, width=width, height=height)


def _open_details(body_class: str = "detailed") -> str:
    """JS preamble that opens all <details> and optionally sets body class."""
    return (
        f"(function(){{document.body.className='{body_class}';"
        "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
    )


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class NoEmptyVisibleCollapsibleAcrossConfigs(unittest.TestCase):
    """A0 / INV-GATE axis extension (Fable audit 2026-07-03). NO visible, open ``<details>`` may
    render with ONLY its summary — an empty expandable reads as broken. Checked across the
    render-config axis {quick, full-Simple, full-Detailed}: the standard completeness gate builds
    only ``mode="full"`` fixtures, so the LIVE empty-#evidence-in-quick bug (its 5 sub-panels all
    self-hide, but the outer #evidence container stayed visible) passed the suite green. A visible
    collapsible must have body content beyond its summary, or not be visible at all."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="tc_axisgate_"))
        cls.quick = _build_quick_widget(cls._tmp)
        cls.full = _build_full_widget(cls._tmp)

    def _empty_open_details(self, widget: str, body_class: str) -> list:
        """ids of every VISIBLE, open ``<details id>`` that has NO visible child besides its summary.

        Height alone lies — a tc-panel's padding keeps a content-less container ~34px tall (Fable's
        "71px" #evidence). The real test is structural: does the opened panel show any content element
        at all? A panel whose only children are the summary + display:none sub-panels is empty-open."""
        js = (
            "(function(){document.body.className='%s';"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var ev=document.getElementById('evidence');"
            "if(ev){ev.dispatchEvent(new Event('toggle'));}"      # force the on-open sub-panel draws
            "var bad=[];"
            "document.querySelectorAll('details[id]').forEach(function(d){"
            "  if(d.offsetParent===null) return;"                 # the <details> itself is hidden → fine
            "  var kids=Array.prototype.filter.call(d.children,function(c){"
            "    if(c.tagName==='SUMMARY') return false;"
            "    var st=getComputedStyle(c);"
            "    if(st.display==='none'||st.visibility==='hidden') return false;"
            "    var r=c.getBoundingClientRect();"
            "    return r.width>1 && r.height>1;"                 # a real, visible content element
            "  });"
            "  if(kids.length===0){bad.push(d.id);}"             # nothing but the summary shows → empty open
            "});return bad;})()" % body_class
        )
        res = _probe(widget, js)
        return res if isinstance(res, list) else []

    def test_quick_has_no_empty_open_collapsible(self):
        bad = self._empty_open_details(self.quick, "")
        self.assertEqual(bad, [], f"EMPTY OPEN COLLAPSIBLE in the QUICK widget: {bad}")

    def test_full_simple_has_no_empty_open_collapsible(self):
        bad = self._empty_open_details(self.full, "simple")
        self.assertEqual(bad, [], f"EMPTY OPEN COLLAPSIBLE in the full-SIMPLE widget: {bad}")

    def test_full_detailed_has_no_empty_open_collapsible(self):
        bad = self._empty_open_details(self.full, "detailed")
        self.assertEqual(bad, [], f"EMPTY OPEN COLLAPSIBLE in the full-DETAILED widget: {bad}")

    def test_quick_panels_all_registered(self):
        """INV-46 composed across the MODE axis: every panel rendered in the QUICK config is in
        USER_SURFACES. The self-closing DOM-scan otherwise ran on the full widget only, so a
        quick-only panel could ship unregistered + un-gated (Fable audit 2026-07-03)."""
        ids = _probe(self.quick,
            "(function(){var p=document.querySelectorAll('details.tc-panel[id]');"
            "return Array.prototype.map.call(p,function(e){return e.id;});})()")
        ids = ids if isinstance(ids, list) else []
        unregistered = [i for i in ids if i not in USER_SURFACES]
        self.assertEqual(unregistered, [],
                         f"unregistered panel(s) rendered in the QUICK widget: {unregistered}")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class WholeArtifactCompletenessGate(unittest.TestCase):
    """INV-GATE / INV-45 / INV-46: every user-facing panel is POPULATED in a full render.

    Fails loudly naming the empty surface. Proves the gate catches emptiness on a
    partial render before asserting it passes on the full fixture.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="tc_gate_"))
        cls.full         = _build_full_widget(cls._tmp)
        cls.partial      = _build_partial_widget(cls._tmp)
        cls.probe        = _build_probe_widget(cls.full, cls._tmp)
        cls.muted_stem   = _build_muted_stem_widget(cls._tmp)

    # ── Convergence helpers ─────────────────────────────────────────────────

    def _run_panel_scan(self, widget: str) -> list[str]:
        """Return ids of all <details class="tc-panel" id="..."> elements in widget."""
        ids = _probe(widget,
            "(function(){"
            "var panels=document.querySelectorAll('details.tc-panel[id]');"
            "return Array.prototype.map.call(panels,function(p){return p.id;});})()")
        return ids if isinstance(ids, list) else []

    # ── 1. Header title ─────────────────────────────────────────────────────

    def test_1_header_title_nonempty(self):
        """Header title must equal the track title and be non-empty."""
        t = _probe(self.full, "(function(){var e=document.getElementById('title');return e?e.textContent.trim():null;})()")
        self.assertIsNotNone(t, "EMPTY SURFACE: #title element not found in full widget")
        self.assertGreater(len(t), 0, "EMPTY SURFACE: #title is empty in full widget")
        self.assertIn("Gate Test Track", t,
                      f"EMPTY SURFACE: #title does not contain the track title; got: {repr(t)}")

    # ── 2. Vitals row ────────────────────────────────────────────────────────

    def test_2_vitals_all_slots_populated(self):
        """Vitals row: Tempo, Key, Length, Loudness, True peak, Dynamics, Stereo, Phase must
        all render with non-empty, non-placeholder text. Metre appears when .als is loaded.
        (Phase = L/R correlation, the 9th slot — real widgets carry phase_corr; gated here too.)"""
        r = _probe(self.full,
            "(function(){"
            "var vits={};"
            "document.querySelectorAll('#vitals .vit').forEach(function(e){"
            "var lbl=e.querySelector('.vlabel');var val=e.querySelector('.vval');"
            "if(lbl&&val)vits[lbl.textContent.trim()]=val.textContent.trim();});"
            "return vits;})()")
        required = {"Tempo", "Key", "Length", "Loudness", "True peak", "Dynamics", "Stereo", "Phase", "Metre"}
        for slot in required:
            self.assertIn(slot, r,
                          f"EMPTY SURFACE: vitals slot '{slot}' absent from full widget; got: {list(r.keys())}")
            v = r[slot]
            self.assertGreater(len(v), 0,
                               f"EMPTY SURFACE: vitals slot '{slot}' is empty in full widget")
            # Stronger: reject placeholder "—" and whitespace-only values
            self.assertNotEqual(v, "—",
                                f"EMPTY SURFACE: vitals slot '{slot}' is placeholder '—' (data not wired)")
            self.assertTrue(v.strip(),
                            f"EMPTY SURFACE: vitals slot '{slot}' is whitespace-only in full widget")

    def test_2_vitals_absent_on_partial(self):
        """Proves gate detects: partial widget (no als) must lack the Metre slot."""
        r = _probe(self.partial,
            "(function(){var v={};document.querySelectorAll('#vitals .vit').forEach(function(e){"
            "var l=e.querySelector('.vlabel');if(l)v[l.textContent.trim()]=1;});return v;})()")
        # The Metre vital only appears when als is present; partial has no als
        self.assertNotIn("Metre", r,
                         "gate-self-check: partial widget must not have Metre vital (no als); "
                         "if this fails the gate can't distinguish full from partial for this slot")

    # ── 3. Track-story arc chart ──────────────────────────────────────────────

    def test_3_arc_canvas_rendered(self):
        """Track-story arc chart canvas must have non-zero dimensions AND drawn pixels."""
        r = _probe(self.full,
            "(function(){"
            "var c=document.getElementById('story');"
            "if(!c)return null;"
            "var dims={h:c.offsetHeight,w:c.offsetWidth};"
            "try{"
            "var ctx=c.getContext('2d');"
            "var W=c.width,H=c.height;"
            "var data=ctx.getImageData(0,0,Math.max(1,W),Math.max(1,H)).data;"
            "var drawn=0;"
            "for(var i=3;i<data.length;i+=4)if(data[i]>5)drawn++;"
            "dims.drawn=drawn;dims.total=W*H;"
            "}catch(e){dims.drawn=-1;dims.err=String(e);}"
            "return dims;})()")
        self.assertIsNotNone(r, "EMPTY SURFACE: #story canvas not found in full widget")
        self.assertGreater(r["h"], 0,
                           f"EMPTY SURFACE: #story canvas has zero height; got: {r}")
        self.assertGreater(r["w"], 0,
                           f"EMPTY SURFACE: #story canvas has zero width; got: {r}")
        # Pixel-drawn check (stronger than element-present)
        drawn = r.get("drawn", -1)
        if drawn >= 0:  # -1 means getImageData threw (CORS or other — don't block)
            self.assertGreater(drawn, 0,
                               f"EMPTY SURFACE: #story canvas has no drawn pixels "
                               f"(all transparent) — arc draw ops may have failed; "
                               f"total={r.get('total')}")

    # ── 4. Player lanes ──────────────────────────────────────────────────────

    def test_4_player_stem_lanes_all_named(self):
        """Player must have player lanes for every stem; window.__ns_state must list them all.
        #stemlanes is Detailed-only; switch to Detailed before measuring canvas height."""
        r = _probe(self.full,
            "(function(){"
            # Switch to Detailed view so #stemlanes becomes visible
            "document.body.classList.remove('simple');"
            "var ns=window.__ns_state||null;"
            "var c=document.getElementById('stemlanes');"
            "return {ns_state:ns, canvas_h:c?c.offsetHeight:0};})()")
        ns = r.get("ns_state")
        self.assertIsNotNone(ns,
                             "EMPTY SURFACE: window.__ns_state not set — player lane grid not rendered")
        names = [e["name"] for e in ns]
        for stem in ("drums", "bass", "other"):
            self.assertIn(stem, names,
                          f"EMPTY SURFACE: stem '{stem}' missing from player lane grid; __ns_state={ns}")
        self.assertGreater(r.get("canvas_h", 0), 0,
                           "EMPTY SURFACE: #stemlanes canvas has zero height — player lanes not drawn")

    def test_4_player_absent_on_partial(self):
        """Proves gate detects: partial widget (no stems_web) must have no __ns_state."""
        r = _probe(self.partial, "(function(){return window.__ns_state||null;})()")
        self.assertIsNone(r,
                          "gate-self-check: partial widget must not have __ns_state (no stems_web)")

    # ── 5. Recommendations ───────────────────────────────────────────────────

    def test_5_recs_cards_have_title_and_body(self):
        """At least 1 rec card must be visible; each card must have a non-empty title AND body."""
        r = _probe(self.full,
            "(function(){"
            "document.body.className='';"  # Detailed view
            "var cards=Array.prototype.filter.call("
            "document.querySelectorAll('#recs > .rec'),"
            "function(e){return e.getBoundingClientRect().height>0;});"
            "var ok=cards.map(function(c){"
            "var h=c.querySelector('h3');var p=c.querySelector('p');"
            "return {h:h?(h.textContent.trim()||'').length:0,"
            "p:p?(p.textContent.trim()||'').length:0};});"
            "return {count:cards.length,cards:ok};})()")
        self.assertGreater(r.get("count", 0), 0,
                           "EMPTY SURFACE: no rec cards visible in Detailed view of full widget")
        for i, card in enumerate(r.get("cards", [])):
            self.assertGreater(card.get("h", 0), 0,
                               f"EMPTY SURFACE: rec card #{i} has empty title in full widget")
            self.assertGreater(card.get("p", 0), 0,
                               f"EMPTY SURFACE: rec card #{i} has empty body in full widget")

    # ── 6. Producer's read ────────────────────────────────────────────────────

    _READ_FLOOR = 40  # minimum visible characters

    def test_6_producers_read_nonempty(self):
        """#readBody innerText must be non-empty and not whitespace-only."""
        t = _probe(self.full,
            "(function(){"
            "var e=document.getElementById('readBody');"
            "return e?e.innerText.trim():null;})()")
        self.assertIsNotNone(t, "EMPTY SURFACE: #readBody element not found in full widget")
        self.assertTrue(t.strip(), "EMPTY SURFACE: #readBody is whitespace-only in full widget")
        self.assertGreater(len(t), self._READ_FLOOR,
                           f"EMPTY SURFACE: #readBody is too short ({len(t)} chars < {self._READ_FLOOR}); "
                           f"got: {repr(t[:120])}")

    def test_6_read_has_authored_sections_in_full(self):
        """Full widget must have AUTHORED narrative sections (h3 headings) inside #readBody."""
        r = _probe(self.full,
            "(function(){"
            "var e=document.getElementById('readBody');"
            "if(!e)return {h3s:0};"
            "return {h3s:e.querySelectorAll('h3').length,"
            "text:e.innerText.trim().substring(0,60)};})()")
        self.assertGreater(r.get("h3s", 0), 0,
                           "EMPTY SURFACE: #readBody has no authored headings (h3) in full widget; "
                           f"got: {repr(r.get('text'))}")

    def test_6_no_authored_sections_on_partial(self):
        """Proves gate detects: partial widget (no narrative) must have NO authored h3 headings."""
        r = _probe(self.partial,
            "(function(){"
            "var e=document.getElementById('readBody');"
            "if(!e)return {h3s:0};"
            "return {h3s:e.querySelectorAll('h3').length};})()")
        self.assertEqual(r.get("h3s", 0), 0,
                         f"gate-self-check: partial widget has {r.get('h3s')} authored h3 heading(s) — "
                         "narrative may have been wired accidentally")

    # ── 7. Tonal balance ─────────────────────────────────────────────────────

    def test_7_tonal_balance_bars_present(self):
        """Tonal balance panel visible + canvas has drawn pixels (not just element-present)."""
        r = _probe(self.full,
            "(function(){"
            "var p=document.getElementById('tonalPanel');"
            "var c=document.getElementById('tonal');"
            "if(!p||!c)return {panel:false};"
            "var pv=getComputedStyle(p).display!=='none'&&p.offsetHeight>0;"
            "var res={panel:pv,ch:c.offsetHeight,cw:c.offsetWidth};"
            "try{"
            "var ctx=c.getContext('2d');"
            "var W=c.width,H=c.height;"
            "var data=ctx.getImageData(0,0,Math.max(1,W),Math.max(1,H)).data;"
            "var drawn=0;"
            "for(var i=3;i<data.length;i+=4)if(data[i]>5)drawn++;"
            "res.drawn=drawn;"
            "}catch(e){res.drawn=-1;res.err=String(e);}"
            "return res;})()")
        self.assertTrue(r.get("panel"),
                        "EMPTY SURFACE: #tonalPanel not visible in full widget")
        self.assertGreater(r.get("ch", 0), 0,
                           "EMPTY SURFACE: #tonal canvas height is 0 in full widget")
        drawn = r.get("drawn", -1)
        if drawn >= 0:
            self.assertGreater(drawn, 0,
                               "EMPTY SURFACE: #tonal canvas has no drawn pixels — "
                               "tonal bar draw ops may have failed")

    # ── 8. Evidence & detail panels ──────────────────────────────────────────

    def test_8_evidence_container_visible(self):
        """Evidence container (#evidence) must exist and be present in the full widget.
        Gating surface: 'evidence' in USER_SURFACES (condition: always)."""
        r = _probe(self.full,
            "(function(){"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var e=document.getElementById('evidence');"
            "if(!e)return {present:false};"
            "return {present:true,h:e.offsetHeight};})()")
        self.assertTrue(r.get("present"),
                        "EMPTY SURFACE: #evidence container not found in full widget — "
                        "Evidence & detail section is missing from the HTML")

    def test_8_arrangement_panel_nonempty(self):
        """Arrangement panel (#arrPanel) must be visible and have rendered canvas content."""
        r = _probe(self.full,
            "(function(){"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var p=document.getElementById('arrPanel');"
            "var c=document.getElementById('arr');"
            "if(!p||!c)return {panel:false};"
            "var pv=getComputedStyle(p).display!=='none'&&p.offsetHeight>0;"
            "return {panel:pv,ch:c.offsetHeight,cw:c.offsetWidth};})()")
        self.assertTrue(r.get("panel"),
                        "EMPTY SURFACE: #arrPanel not visible in full widget — "
                        "als data may not have been wired or has no lanes")
        self.assertGreater(r.get("ch", 0), 0,
                           "EMPTY SURFACE: arrangement canvas has zero height in full widget")

    def test_8_automation_panel_nonempty(self):
        """Automation panel (#autoPanel) must be visible and have non-empty text content."""
        r = _probe(self.full,
            "(function(){"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var p=document.getElementById('autoPanel');"
            "if(!p)return {panel:false};"
            "var pv=getComputedStyle(p).display!=='none'&&p.offsetHeight>0;"
            "return {panel:pv,text:(p.textContent||'').trim().length};})()")
        self.assertTrue(r.get("panel"),
                        "EMPTY SURFACE: #autoPanel not visible in full widget — "
                        "als automation data may not have been wired or has no varying envelopes")
        self.assertGreater(r.get("text", 0), 5,
                           "EMPTY SURFACE: #autoPanel appears empty in full widget")

    def test_8_als_panels_absent_on_partial(self):
        """Proves gate detects: partial widget (no als) must have hidden/absent arr + auto panels."""
        for pid in ("arrPanel", "autoPanel"):
            r = _probe(self.partial,
                f"(function(){{var e=document.getElementById('{pid}');"
                f"if(!e)return {{present:false}};var d=getComputedStyle(e).display;"
                f"return {{present:true,display:d,h:e.offsetHeight}};}})() ")
            present = r.get("present", False)
            if present:
                hidden = r.get("display") == "none" or r.get("h", 0) == 0
                self.assertTrue(hidden,
                                f"gate-self-check: #{pid} is visible on partial widget (no als)")

    def test_8_stemmap_panel_nonempty(self):
        """Stem ↔ project map panel (#mapPanel) must be visible and non-empty."""
        r = _probe(self.full,
            "(function(){"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var p=document.getElementById('mapPanel');"
            "if(!p)return {panel:false};"
            "var pv=getComputedStyle(p).display!=='none'&&p.offsetHeight>0;"
            "return {panel:pv,text:(p.innerText||'').trim().length};})()")
        self.assertTrue(r.get("panel"),
                        "EMPTY SURFACE: #mapPanel not visible in full widget — "
                        "stemmap may not have been wired")
        self.assertGreater(r.get("text", 0), 5,
                           "EMPTY SURFACE: #mapPanel appears empty in full widget")

    def test_8_rhythm_panel_nonempty(self):
        """Rhythm & separation panel (#rhyRows) must have rendered cards."""
        r = _probe(self.full,
            "(function(){"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var el=document.getElementById('rhyRows');"
            "if(!el)return {present:false};"
            "var cards=el.querySelectorAll('.mcard');"
            "return {present:true,cards:cards.length,"
            "text:(el.textContent||'').trim().length};})()")
        self.assertTrue(r.get("present"),
                        "EMPTY SURFACE: #rhyRows not found in full widget")
        self.assertGreater(r.get("cards", 0), 0,
                           "EMPTY SURFACE: rhythm panel has no stem cards in full widget")

    def test_8_notes_panel_nonempty(self):
        """Transcribed notes panel (#notePanel) must be visible with a populated title."""
        r = _probe(self.full,
            "(function(){"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var p=document.getElementById('notePanel');"
            "if(!p)return {panel:false};"
            "var pv=getComputedStyle(p).display!=='none'&&p.offsetHeight>0;"
            "var t=document.getElementById('noteTitle');"
            "return {panel:pv,title:t?(t.textContent.trim()):null};})()")
        self.assertTrue(r.get("panel"),
                        "EMPTY SURFACE: #notePanel not visible in full widget")
        title = r.get("title") or ""
        self.assertGreater(len(title), 0,
                           "EMPTY SURFACE: #noteTitle is empty in full widget")

    def test_8_notes_panel_absent_on_partial(self):
        """Proves gate detects: partial widget (no notes) must have hidden #notePanel."""
        r = _probe(self.partial,
            "(function(){var p=document.getElementById('notePanel');"
            "if(!p)return {present:false};"
            "return {present:true,display:getComputedStyle(p).display,h:p.offsetHeight};})()")
        if r.get("present"):
            hidden = r.get("display") == "none" or r.get("h", 0) == 0
            self.assertTrue(hidden,
                            "gate-self-check: #notePanel is visible on partial widget (no notes)")

    # ── 9. Catalog backpointer ────────────────────────────────────────────────

    def test_9_catalog_backlink_present_and_live(self):
        """#backLink must be present, visible, and its href must point to a real file (not '#')."""
        r = _probe(self.full,
            "(function(){"
            "var b=document.getElementById('backLink');"
            "if(!b)return {present:false};"
            "return {present:true,hidden:b.hidden,"
            "href:b.getAttribute('href')||'',"
            "text:(b.textContent||'').trim()};})()")
        self.assertTrue(r.get("present"),
                        "EMPTY SURFACE: #backLink element not found in full widget")
        self.assertFalse(r.get("hidden"),
                         "EMPTY SURFACE: #backLink is hidden in full widget")
        href = r.get("href", "")
        self.assertTrue(href and href != "#",
                        f"EMPTY SURFACE: #backLink href is dead ('{href}') in full widget")
        self.assertTrue(href.startswith("file://"),
                        f"EMPTY SURFACE: #backLink href is not a file:// URI; got: {repr(href)}")

    def test_9_backlink_has_dead_href_on_partial(self):
        """Proves gate detects: partial widget (no back_href) must have href='#' (not file://)."""
        r = _probe(self.partial,
            "(function(){"
            "var b=document.getElementById('backLink');"
            "if(!b)return {present:false};"
            "return {present:true,href:b.getAttribute('href')||''};})()")
        if r.get("present"):
            href = r.get("href", "")
            self.assertFalse(href.startswith("file://"),
                             f"gate-self-check: partial widget backLink has a file:// href — "
                             f"gate can't distinguish full from partial; href={repr(href)}")

    # ── 10. Footer version + analyzed date ────────────────────────────────────

    def test_10_footer_has_version_and_date(self):
        """Footer (#foot) must contain TC_VERSION; #srcmeta must have a date."""
        r = _probe(self.full,
            "(function(){"
            "var f=document.getElementById('foot');"
            "var s=document.getElementById('srcmeta');"
            "return {foot:f?(f.textContent||'').trim():null,"
            "srcmeta:s?(s.textContent||'').trim():null};})()")
        foot = r.get("foot") or ""
        self.assertGreater(len(foot), 0,
                           "EMPTY SURFACE: footer (#foot) is empty in full widget")
        self.assertIn(build_widget.TC_VERSION, foot,
                      f"EMPTY SURFACE: TC_VERSION '{build_widget.TC_VERSION}' not in footer; "
                      f"got: {repr(foot)}")
        srcmeta = r.get("srcmeta") or ""
        self.assertGreater(len(srcmeta), 0,
                           "EMPTY SURFACE: source/date line (#srcmeta) is empty in full widget")
        self.assertTrue(re.search(r"\d{4}-\d{2}-\d{2}", srcmeta),
                        f"EMPTY SURFACE: no date in #srcmeta; got: {repr(srcmeta)}")

    # ── 11. (removed 2026-07-03, s49) — the #verdict "In short" headline panel was
    #        removed at Alexander's call (repeated the cards, weight on the calm-first
    #        screen). The verdict TEXT still lives in the catalog/library listing, which
    #        is gated elsewhere. No widget panel to assert here anymore. ──────────────

    # ── 12. Subtitle + source meta ────────────────────────────────────────────

    def test_12_subtitle_and_srcmeta(self):
        """#sub must show the duration+BPM line; #srcmeta must name BOTH the audio file
        AND the .als project file (INV-GATE §4 — both sources visible in the header)."""
        r = _probe(self.full,
            "(function(){"
            "var sub=document.getElementById('sub');"
            "var sm=document.getElementById('srcmeta');"
            "return {"
            "sub:sub?(sub.textContent||'').trim():null,"
            "srcmeta:sm?(sm.textContent||'').trim():null,"
            "srcmetaHtml:sm?sm.innerHTML:null};})()")
        # Subtitle: length + BPM
        sub = r.get("sub") or ""
        self.assertGreater(len(sub), 0,
                           "EMPTY SURFACE: #sub is empty — duration/BPM line not rendered")
        self.assertIn("BPM", sub,
                      f"EMPTY SURFACE: #sub missing BPM; got: {repr(sub)}")
        # srcmeta: must name audio file
        srcmeta = r.get("srcmeta") or ""
        self.assertIn("gate_test.wav", srcmeta,
                      f"EMPTY SURFACE: #srcmeta does not name the audio file 'gate_test.wav'; "
                      f"got: {repr(srcmeta)}")
        # srcmeta: must ALSO name the .als project file (INV-GATE §4)
        self.assertIn("gate_test.als", srcmeta,
                      f"EMPTY SURFACE: #srcmeta does not name the .als project file 'gate_test.als' "
                      f"(both sources must appear in the header — INV-GATE §4); "
                      f"got: {repr(srcmeta)}")

    # ── 13. Mode badge ────────────────────────────────────────────────────────

    def test_13_mode_badge_matches_mode(self):
        """#modeBadge must be present with non-empty text matching the run mode.
        Full mode → 'Full analysis'; quick mode → 'Quick read'."""
        r = _probe(self.full,
            "(function(){"
            "var e=document.getElementById('modeBadge');"
            "return e?{text:(e.textContent||'').trim(),cls:e.className}:null;})()")
        self.assertIsNotNone(r, "EMPTY SURFACE: #modeBadge element not found in full widget")
        text = r.get("text", "")
        self.assertGreater(len(text), 0,
                           "EMPTY SURFACE: #modeBadge is empty in full widget")
        # In full mode the badge should not say "Quick read"
        self.assertNotIn("Quick", text,
                         f"EMPTY SURFACE: #modeBadge says 'Quick' in a full render; got: {repr(text)}")
        # Should contain "Full" or similar full-mode indicator
        self.assertIn("Full", text,
                      f"EMPTY SURFACE: #modeBadge does not confirm full mode; got: {repr(text)}")

    # ── 14. View selector ─────────────────────────────────────────────────────

    def test_14_view_toggle_has_buttons(self):
        """Full render: #viewToggle must have exactly 2 buttons (Simple + Detailed);
        exactly one must have the 'on' class (active view indicator)."""
        r = _probe(self.full,
            "(function(){"
            "var tg=document.getElementById('viewToggle');"
            "if(!tg)return {present:false};"
            "var btns=tg.querySelectorAll('button');"
            "var onCount=Array.prototype.filter.call(btns,function(b){"
            "return b.classList.contains('on');}).length;"
            "var labels=Array.prototype.map.call(btns,function(b){return b.textContent.trim();});"
            "return {present:true,count:btns.length,onCount:onCount,labels:labels};})()")
        self.assertTrue(r.get("present"),
                        "EMPTY SURFACE: #viewToggle not found in full widget")
        self.assertEqual(r.get("count"), 2,
                         f"EMPTY SURFACE: #viewToggle must have exactly 2 buttons (Simple + Detailed); "
                         f"got {r.get('count')}: {r.get('labels')}")
        self.assertEqual(r.get("onCount"), 1,
                         f"EMPTY SURFACE: exactly one #viewToggle button must be active ('on'); "
                         f"got onCount={r.get('onCount')}, labels={r.get('labels')}")

    # ── 15. Player audio count == lanes ──────────────────────────────────────

    def test_15_player_audio_count_equals_lanes(self):
        """#playAudios must have exactly one <audio> per stem lane; every src is non-empty."""
        r = _probe(self.full,
            "(function(){"
            "var wrap=document.getElementById('playAudios');"
            "if(!wrap)return {present:false};"
            "var audios=wrap.querySelectorAll('audio');"
            "var ns=window.__ns_state||[];"
            "var srcs=Array.prototype.map.call(audios,function(a){"
            "return a.getAttribute('src')||a.src||'';});"
            "return {present:true,audioCount:audios.length,"
            "laneCount:ns.length,srcs:srcs};})()")
        self.assertTrue(r.get("present"),
                        "EMPTY SURFACE: #playAudios wrapper not found in full widget")
        lanes = r.get("laneCount", 0)
        audios = r.get("audioCount", 0)
        self.assertGreater(audios, 0,
                           "EMPTY SURFACE: #playAudios has no <audio> elements — "
                           "stems_web audio files may not have been wired")
        self.assertEqual(audios, lanes,
                         f"EMPTY SURFACE: audio count ({audios}) != lane count ({lanes}) — "
                         "dead play button: some lanes have no audio backing")
        for i, src in enumerate(r.get("srcs", [])):
            self.assertTrue(src,
                            f"EMPTY SURFACE: audio element #{i} has empty src in full widget — "
                            "the stem audio file path was not resolved")

    # ── 16. Play controls + legend ────────────────────────────────────────────

    def test_16_play_controls_nonempty(self):
        """Play controls filled by JS: #playBtn, #playTime, #seqKey, #playNote must all be
        non-empty after page load. An empty control = a typo in a strings key or wiring miss."""
        r = _probe(self.full,
            "(function(){"
            "document.body.classList.remove('simple');"
            "return {"
            "playBtn:(document.getElementById('playBtn')||{}).textContent||'',"
            "playTime:(document.getElementById('playTime')||{}).textContent||'',"
            "seqKey:(document.getElementById('seqKey')||{}).innerHTML||'',"
            "playNote:(document.getElementById('playNote')||{}).textContent||''};})()")
        for ctrl, label in [
            ("playBtn",  "#playBtn (play/pause button)"),
            ("playTime", "#playTime (time display)"),
            ("seqKey",   "#seqKey (lane legend)"),
            ("playNote", "#playNote (player instruction hint)"),
        ]:
            v = r.get(ctrl, "").strip()
            self.assertGreater(len(v), 0,
                               f"EMPTY SURFACE: {label} is empty after page load — "
                               "JS strings key may be missing or the control not wired")

    # ── 17. Timeline cue letters ──────────────────────────────────────────────

    def test_17_timeline_cue_letters(self):
        """Timecoded rec cards must carry a data-let attribute with a single letter (a/b/c…).
        The letter badge links the card to the triangle cue on the timeline (INV-34)."""
        r = _probe(self.full,
            "(function(){"
            "document.body.className='';"
            "var cards=document.querySelectorAll('#recs .rec[data-let]');"
            "var letters=Array.prototype.map.call(cards,function(c){return c.dataset.let||'';});"
            "return {cueCount:cards.length,letters:letters};})()")
        self.assertGreater(r.get("cueCount", 0), 0,
                           "EMPTY SURFACE: no rec cards have a data-let cue letter in full widget — "
                           "timecoded recs must receive a/b/c letters from the CUES array "
                           "(check that the fixture generates at least one timecoded rec)")
        for let in r.get("letters", []):
            self.assertEqual(len(let), 1,
                             f"EMPTY SURFACE: cue letter has wrong length; expected single char, got: {repr(let)}")
            self.assertTrue(let.islower() or let == "•",
                            f"EMPTY SURFACE: cue letter is not a lowercase letter or fallback •; got: {repr(let)}")

    # ── 18. Rec sub-parts: based-on + → Try + legend ─────────────────────────

    def test_18_rec_subparts_present(self):
        """At least one rec card must carry a 'Based on' evidence line AND a '→ Try' fix.
        #recLegend must be non-empty (colour key for crit/do/concept cards)."""
        r = _probe(self.full,
            "(function(){"
            "document.body.className='';"
            "var recs=document.getElementById('recs');"
            "var fixCards=recs?recs.querySelectorAll('.rec p.fix'):[];"
            "var basedCards=recs?recs.querySelectorAll('.rec p.based'):[];"
            "var fixTexts=Array.prototype.map.call(fixCards,"
            "function(p){return (p.textContent||'').trim().length;});"
            "var basedTexts=Array.prototype.map.call(basedCards,"
            "function(p){return (p.textContent||'').trim().length;});"
            "var legend=document.getElementById('recLegend');"
            "return {"
            "fixCount:fixCards.length,fixLens:fixTexts,"
            "basedCount:basedCards.length,basedLens:basedTexts,"
            "legendLen:(legend?(legend.innerHTML||'').trim().length:0)};})()")
        # → Try fix lines
        self.assertGreater(r.get("fixCount", 0), 0,
                           "EMPTY SURFACE: no rec card has a '→ Try' fix line in full widget — "
                           "rec objects may not have a 'fix' field set")
        for i, length in enumerate(r.get("fixLens", [])):
            self.assertGreater(length, 0,
                               f"EMPTY SURFACE: '→ Try' fix on rec #{i} is empty in full widget")
        # Based-on evidence lines
        self.assertGreater(r.get("basedCount", 0), 0,
                           "EMPTY SURFACE: no rec card has a 'Based on' evidence line in full widget — "
                           "REC_BASED map may not have entries for the generated rec keys")
        for i, length in enumerate(r.get("basedLens", [])):
            self.assertGreater(length, 0,
                               f"EMPTY SURFACE: 'Based on' line on rec #{i} is empty in full widget")
        # Legend
        self.assertGreater(r.get("legendLen", 0), 0,
                           "EMPTY SURFACE: #recLegend is empty in full widget — "
                           "the colour key (crit/do/concept) was not rendered")

    # ── 19. Embedded catalog panel rows + hrefs ───────────────────────────────

    def test_19_catalog_rows_and_hrefs(self):
        """#catBody must have at least 1 track row; the self row (current track) must exist.
        Gating surface: 'catalog' in USER_SURFACES."""
        r = _probe(self.full,
            "(function(){"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var body=document.getElementById('catBody');"
            "if(!body)return {present:false};"
            "var rows=body.querySelectorAll('.catrun');"
            "var selfRow=body.querySelector('.catrun.self');"
            "var links=body.querySelectorAll('a.copen');"
            "return {present:true,"
            "rows:rows.length,"
            "hasSelf:!!selfRow,"
            "links:Array.prototype.map.call(links,function(a){return a.getAttribute('href')||'';}),"
            "catVisible:getComputedStyle(document.getElementById('catalog')||{}).display!=='none'};})()")
        self.assertTrue(r.get("present"),
                        "EMPTY SURFACE: #catBody not found in full widget")
        self.assertGreater(r.get("rows", 0), 0,
                           "EMPTY SURFACE: #catBody has no track rows — catalog not rendered")
        self.assertTrue(r.get("hasSelf"),
                        "EMPTY SURFACE: #catBody has no self row (.catrun.self) — "
                        "the current track's version is missing from the catalog")
        self.assertTrue(r.get("catVisible"),
                        "EMPTY SURFACE: #catalog panel is still hidden after JS ran — "
                        "catalog data may not have been wired")

    # ── 20. Evidence readouts ──────────────────────────────────────────────────

    def test_20_evidence_readouts_nonempty(self):
        """Evidence panel readouts filled by JS must be non-empty:
        #arrReadout, #autoReadout, #noteReadout (hover hints),
        #mapNotes (stemmap model recommendation),
        #rhySep (separation verdict),
        #mapRows ≥1 child, #rhyRows ≥1 .mcard."""
        r = _probe(self.full,
            "(function(){"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "function txt(id){var e=document.getElementById(id);"
            "return e?(e.textContent||'').trim():null;}"
            "function childCount(id,sel){"
            "var e=document.getElementById(id);"
            "return e?e.querySelectorAll(sel||'*').length:0;}"
            "return {"
            "arrReadout:txt('arrReadout'),"
            "autoReadout:txt('autoReadout'),"
            "noteReadout:txt('noteReadout'),"
            "mapNotes:txt('mapNotes'),"
            "rhySep:txt('rhySep'),"
            "mapRowsCount:childCount('mapRows','.mcard,.z'),"
            "rhyRowsCount:childCount('rhyRows','.mcard')};})()")
        for readout_id, label in [
            ("arrReadout",  "#arrReadout (arrangement hover text)"),
            ("autoReadout", "#autoReadout (automation hover text)"),
            ("noteReadout", "#noteReadout (notes hover text)"),
            ("mapNotes",    "#mapNotes (stemmap model recommendation)"),
            ("rhySep",      "#rhySep (separation quality verdict)"),
        ]:
            v = r.get(readout_id)
            self.assertIsNotNone(v, f"EMPTY SURFACE: {label} element not found in full widget")
            self.assertGreater(len(v), 0,
                               f"EMPTY SURFACE: {label} is empty in full widget — "
                               "JS may not have wired the readout")
        self.assertGreater(r.get("mapRowsCount", 0), 0,
                           "EMPTY SURFACE: #mapRows has no rows in full widget — "
                           "stemmap data may not have been wired")
        self.assertGreater(r.get("rhyRowsCount", 0), 0,
                           "EMPTY SURFACE: #rhyRows has no .mcard rows in full widget — "
                           "rhythm data may not have been wired")

    # ── 21. Auto-mute approved behavior (INV-45) ─────────────────────────────

    def test_21_auto_mute_approved_behavior(self):
        """CR-2 / INV-45 — APPROVED BEHAVIOR (Alexander 2026-07-03): a near-silent stem's
        lane starts MUTED on first load (avoids surprise silence on play; M/S buttons still work).

        Uses a variant fixture where 'other' stem has levels at -80 dB per band (broadband
        ~-72 dB, well below STEM_EMPTY_FLOOR_DB = -55 dB), causing it to appear in
        D.stem.omitted. The player JS then starts that lane muted (build_widget.py:3868).

        Verifies:
          - 'other' appears in __ns_state with mute=true (approved auto-mute)
          - 'drums' and 'bass' appear with mute=false (significant stems un-muted)
        """
        r = _probe(self.muted_stem, "(function(){return window.__ns_state||null;})()")
        self.assertIsNotNone(r,
                             "INV-45: __ns_state not set in muted-stem widget — player not initialized")
        by_name = {e["name"]: e for e in r}
        # Near-silent stem must appear and be auto-muted (CR-2)
        self.assertIn("other", by_name,
                      "INV-45: 'other' (near-silent) stem missing from __ns_state — "
                      "near-silent stems must still appear as muted lanes (CR-2 visibility)")
        self.assertTrue(by_name["other"].get("mute"),
                        f"INV-45: 'other' (near-silent) not auto-started muted — "
                        f"CR-2 approved behavior requires near-silent stems to start muted; "
                        f"got: {by_name['other']}")
        # Significant stems must be un-muted
        for stem in ("drums", "bass"):
            if stem in by_name:
                self.assertFalse(by_name[stem].get("mute"),
                                 f"INV-45: '{stem}' (significant stem) incorrectly starts muted; "
                                 f"only near-silent stems auto-mute (CR-2); got: {by_name[stem]}")

    # ── CONVERGENCE MECHANISM (INV-46) ───────────────────────────────────────
    #
    # Three interlocking tests that make the gate self-closing:
    #   (b) DOM-scan — rendered ⊆ registry
    #   (c) Registry-gated — registry ⊆ gated
    #   proof — the scan CAN catch an unregistered panel
    #
    # Together: rendered ⊆ registry ⊆ gated ⟹ rendered ⊆ gated (100% by construction).
    # ─────────────────────────────────────────────────────────────────────────

    def test_CONV_probe_scan_detects_unregistered(self):
        """CONVERGENCE PROOF: the DOM-scan catches a panel injected without registration.

        Runs the panel scan on the probe widget (full widget + injected
        <details id="__probe_unregistered" class="tc-panel">). Asserts the scan FINDS
        __probe_unregistered AND it is NOT in USER_SURFACES.

        This test PASSES when the mechanism is working correctly — proving that adding a
        new tc-panel without registering it would make
        test_CONV_all_rendered_panels_are_registered fail (go RED).
        """
        scanned = self._run_panel_scan(self.probe)
        self.assertIn("__probe_unregistered", scanned,
                      "CONVERGENCE PROOF FAILED: __probe_unregistered not found by DOM-scan — "
                      "the scan does not detect new <details class='tc-panel' id='...'> elements "
                      "(mechanism broken; check the querySelectorAll selector)")
        self.assertNotIn("__probe_unregistered", USER_SURFACES,
                         "CONVERGENCE SETUP ERROR: __probe_unregistered must NOT be in USER_SURFACES "
                         "(it is the injected test element that proves the scan catches unknowns)")

    def test_CONV_all_rendered_panels_are_registered(self):
        """CONVERGENCE: every <details class="tc-panel" id="..."> in the full render is in USER_SURFACES.

        If a new panel is added to the widget without a USER_SURFACES entry, this test fails
        naming the unregistered id. The developer must then:
          1. Add it to USER_SURFACES with a condition and gated_by method name.
          2. Add the gate test method.
          3. Re-run until green.

        This is the self-closing property: adding a panel cannot silently escape the gate.
        """
        scanned = self._run_panel_scan(self.full)
        unregistered = [pid for pid in scanned if pid not in USER_SURFACES]
        self.assertEqual(unregistered, [],
                         f"CONVERGENCE FAILED: {len(unregistered)} rendered panel(s) not in "
                         f"USER_SURFACES: {unregistered}. "
                         "Add each to USER_SURFACES and add a gate test method.")

    def test_CONV_every_registry_entry_has_gate_test(self):
        """CONVERGENCE: every non-DEFERRED USER_SURFACES entry has a gate test method (registry ⊆ gated).

        Verifies that each surface in the registry is covered by a real gate assertion.
        A surface without a gate method means it was registered but the completeness
        assertion was never written — it would slip through the suite green.
        """
        missing = []
        for surface_id, info in sorted(USER_SURFACES.items()):
            if info["condition"] == "DEFERRED":
                continue  # §D deferred surfaces — no gate yet (no reference in 1.0)
            gated_by = info.get("gated_by")
            if not gated_by:
                missing.append(f"  {surface_id}: gated_by is None (must name a test method)")
                continue
            if not hasattr(WholeArtifactCompletenessGate, gated_by):
                missing.append(
                    f"  {surface_id}: gated_by='{gated_by}' not found as a method on "
                    f"WholeArtifactCompletenessGate")
        if missing:
            self.fail(
                f"CONVERGENCE FAILED: {len(missing)} registry entry/entries lack a gate method:\n"
                + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
