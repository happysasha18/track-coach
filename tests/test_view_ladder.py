#!/usr/bin/env python3
"""View-ladder monotonicity (INV-19) + the CSS gating contract that realises it (INV-22).

Why this file exists (Sasha, session 12, 2026-06-20): the recurring Simple/Detailed regression
(memory track-coach-graph-regression) was fixed element-by-element (INV-3 recs, INV-4 lanes, INV-18
evidence), but the LADDER ITSELF — `quick ⊆ full-Simple ⊆ full-Detailed`, each tier adds — was never
pinned as one property. So a NEW element added to Simple but forgotten in Detailed, or shown in quick
but hidden in Simple, could re-create the inversion and no existing test would catch it. This file
asserts the property over the whole element set, on the RENDERED artifact, not the template.

Asserted on shipped HTML (one full render + one quick render), no browser, instant.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402


def _core(n=48, dur=96.0):
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


def _render(*, mode="full", stems=("drums", "bass", "vocals"), mix=False):
    tmp = Path(tempfile.mkdtemp(prefix="tc_ladder_"))
    stems_rel = mix_rel = None
    if stems:
        sdir = tmp / "stems_web"; sdir.mkdir()
        for s in stems:
            (sdir / f"{s}.m4a").write_bytes(b"\x00")
        stems_rel = "stems_web"
    if mix:
        mdir = tmp / "mix_web"; mdir.mkdir()
        (mdir / "mix.m4a").write_bytes(b"\x00")
        mix_rel = "mix_web"
    out = tmp / "w.html"
    build_widget.build_html(_core(), {}, None, None, str(out), "Ladder Test",
                            build_widget.STRINGS, audio_stems_rel=stems_rel, audio_mix_rel=mix_rel,
                            mode=mode, narrative_md="The mix reads clear.\n\nBass is forward early.")
    return out.read_text(encoding="utf-8")


def _hide_set(html, cls):
    """The set of #ids that `body.<cls>` hides via display:none in the SHIPPED css."""
    blocks = re.findall(rf"body\.{cls}([^{{]*)\{{[^}}]*display\s*:\s*none[^}}]*\}}", html)
    return set(re.findall(r"#([A-Za-z][\w-]*)", " ".join(blocks)))


FULL = _render(mode="full")
QUICK = _render(mode="quick", stems=(), mix=True)

HIDE_SIMPLE = _hide_set(FULL, "simple")
HIDE_QUICK = _hide_set(QUICK, "quick")
HIDE_DETAILED = _hide_set(FULL, "detailed")

# Elements Simple hides that quick does NOT CSS-hide are allowed ONLY if they are data-absent in quick
# (the stem viz: quick has stems=none ⇒ #stemlanes/#seqKey are not produced — §5 data gate). A NEW
# element hidden in Simple but visible in quick that is NOT in this set is a ladder inversion.
DATA_ABSENT_IN_QUICK = {"stemlanes", "seqKey"}


class CssGatingContract(unittest.TestCase):
    """INV-22 — the mechanism: one positive body class `simple` (+ `quick`); NO `body.detailed`."""

    def test_no_body_detailed_class_exists(self):
        # INV-22: Detailed is the ABSENCE of `.simple`, never a positive class. A `body.detailed`
        # hide rule would be a new tier mechanism — update the spec first.
        self.assertEqual(HIDE_DETAILED, set(), "INV-22: a body.detailed hide rule appeared — Detailed "
                         "must be the absence of .simple, not a positive class")
        self.assertNotRegex(FULL, r"\.detailed\b[^{]*\{[^}]*display\s*:\s*none",
                            "INV-22: no .detailed display:none rule may exist")

    def test_simple_hide_set_is_exactly_the_known_three(self):
        # INV-22 + INV-18: Simple hides ONLY the deep stem viz and the non-timecoded recs.
        self.assertEqual(HIDE_SIMPLE, {"stemlanes", "seqKey", "recs"},
                         f"INV-22: Simple hide-set drifted: {sorted(HIDE_SIMPLE)}")

    def test_quick_hide_set_is_only_recs(self):
        # INV-22: quick CSS-hides only the non-timecoded recs; stem viz is withheld by DATA absence.
        self.assertEqual(HIDE_QUICK, {"recs"},
                         f"INV-22: quick hide-set drifted: {sorted(HIDE_QUICK)}")

    def test_quick_body_class_set_server_side(self):
        # INV-22: quick run carries body class "quick" from L-py (__BODYCLASS__), full does not.
        self.assertRegex(QUICK, r'<body[^>]*class="[^"]*\bquick\b', "quick run must ship body.quick")
        self.assertNotRegex(FULL, r'<body[^>]*class="[^"]*\bquick\b', "full run must NOT ship body.quick")


class LadderIsMonotonic(unittest.TestCase):
    """INV-19 — quick ⊆ full-Simple ⊆ full-Detailed, as a property over the whole element set."""

    def test_detailed_shows_at_least_what_simple_shows(self):
        # visible(Simple) ⊆ visible(Detailed)  ⟺  hide(Detailed) ⊆ hide(Simple).
        self.assertTrue(HIDE_DETAILED <= HIDE_SIMPLE,
                        f"INV-19: Detailed hides {sorted(HIDE_DETAILED - HIDE_SIMPLE)} that Simple shows "
                        "— Detailed must add to Simple, never remove")

    def test_quick_is_the_floor_no_css_inversion(self):
        # Everything quick CSS-hides, Simple must also hide (quick can't show something Simple hides).
        self.assertTrue(HIDE_QUICK <= HIDE_SIMPLE,
                        f"INV-19: quick shows {sorted(HIDE_QUICK - HIDE_SIMPLE)} that Simple hides "
                        "— quick is the floor, it cannot show MORE than Simple")

    def test_simple_only_hides_extra_that_quick_lacks_by_data(self):
        # The elements Simple hides beyond quick's CSS hide-set must be exactly the stem viz that quick
        # lacks by DATA absence. Anything else = an element hidden in Simple but live in quick = inversion.
        simple_extra = HIDE_SIMPLE - HIDE_QUICK
        offenders = simple_extra - DATA_ABSENT_IN_QUICK
        self.assertEqual(offenders, set(),
                         f"INV-19 inversion: {sorted(offenders)} hidden in Simple but not withheld in "
                         "quick (neither CSS-hidden nor data-absent) — fix the ladder or update §5")
        # and prove the stem viz really IS absent/withheld in the quick render (not just uneclared)
        for el in DATA_ABSENT_IN_QUICK:
            self.assertNotRegex(QUICK, rf'id="{el}"[^>]*>\s*<canvas',
                                f"INV-19: quick unexpectedly produced live #{el} stem viz")

    def test_grid_visibility_is_monotonic(self):
        # §5 projected: visibility per element per tier (Q, F-S, F-D). The SPEC's own monotonicity —
        # vis(Q) ⟹ vis(S) ⟹ vis(D) for every element. Mirrors §5; update both together (change protocol).
        # 1 = visible, 0 = hidden/absent at that tier.
        GRID = {  # element:            Q  F-S  F-D
            "modeBadge":               (1, 1, 1),
            "viewToggle/hint":         (1, 1, 1),
            "vitals/verdict":          (1, 1, 1),
            "story":                   (1, 1, 1),
            "structureBar":            (1, 1, 1),
            "playerTransport":         (1, 1, 1),
            "stemlanes":               (0, 0, 1),   # floor & Simple hide/absent; Detailed adds
            "recs(non-timecoded)":     (0, 0, 1),   # quick+Simple show timecoded only; Detailed adds
            "recs(timecoded)":         (1, 1, 1),
            "readPanel":               (1, 1, 1),
            "tonalPanel":              (1, 1, 1),
            "evidence":                (1, 1, 1),   # INV-18 — every view
            "catalogPanel":            (1, 1, 1),
        }
        for el, (q, s, d) in GRID.items():
            self.assertLessEqual(q, s, f"INV-19: {el} visible in quick but not Simple")
            self.assertLessEqual(s, d, f"INV-19: {el} visible in Simple but not Detailed")


if __name__ == "__main__":
    unittest.main()
