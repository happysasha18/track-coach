#!/usr/bin/env python3
"""§D.10 / §F — catalog-tail similarity columns rendered in the REAL catalog page.

Tests assert:
  1. The two column headers ("Leans toward", "Similar in library") appear in the output.
  2. A close/mid lean renders the direction name in the correct colour (green / amber).
  3. A far lean (or None) shows the 'no close direction yet' message — no red in the direction cell.
  4. A sibling chip carries the sibling's track label and colour (far IS allowed per F-INV-1).
  5. The coloured link (`sim-dir` / `sib-chip`) is an anchor element.

Sim data is injected into entry dicts (the same pattern as `mix_uri` in build_catalog) so this
file is PURE — no filesystem, no run dirs required. Verifies render_catalog_html output only.
Methodology: spec → prove → matrix → test → code. NEVER loosen a test to make code pass.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import catalog  # noqa: E402
import similarity_columns as S  # noqa: E402


def _e(track, sha="sha1", stamp="2026-06-20_2100", mtime=1000, **kw):
    e = {"track": track, "audio_sha": sha, "stamp": stamp, "audio_mtime": mtime,
         "widget": f"{track}-{stamp}.html", "mode": "full",
         "bpm": 123, "arc": [0.1, 0.5, 1.0],
         "title": track.replace("_", " "),
         "_leans": [], "_siblings": []}
    e.update(kw)
    return e


class ColumnHeaders(unittest.TestCase):
    """The two new header cells must be present in every rendered catalog page."""

    def test_both_headers_present(self):
        html = catalog.render_catalog_html([_e("T")])
        self.assertIn("Leans toward", html)
        self.assertIn("Similar in library", html)


class LeanCellRendering(unittest.TestCase):
    """Direction name(s) coloured by level; no red for the reference column (owner rule 2026-06-29).
    Cell now accepts a list of up to 3 Lean objects (§D.10.1)."""

    def _render(self, leans):
        return catalog.render_catalog_html([_e("T", _leans=leans)])

    def test_close_lean_shows_green_direction_name(self):
        lean = S.Lean(direction="DeepChord", level=S.CLOSE, runner=None, n_shared=12)
        html = self._render([lean])
        self.assertIn("#2e9e5b", html, "close lean must use green #2e9e5b")
        self.assertIn("DeepChord", html, "direction name must appear")
        self.assertIn("sim-dir", html, "direction must be rendered as .sim-dir link")

    def test_mid_lean_shows_amber_direction_name(self):
        lean = S.Lean(direction="SCSI-9", level=S.MID, runner=None, n_shared=11)
        html = self._render([lean])
        self.assertIn("#d8932a", html, "mid lean must use amber #d8932a")
        self.assertIn("SCSI-9", html)

    def test_far_lean_not_in_list_shows_no_close_message(self):
        # leans_toward_topk never passes FAR to the renderer; empty list → grey message.
        html = self._render([])
        self.assertIn("no close direction yet", html, "full row, empty list → the reference column's own "
                      "'no close direction yet' (D-INV-22), never the siblings phrase 'no similar tracks'")
        self.assertNotIn("no similar tracks", html, "the siblings-column phrase must never leak into the lean cell")
        self.assertNotIn("#c2503d", html, "red must NOT appear in the direction cell (owner rule 2026-06-29)")

    def test_none_lean_list_shows_no_close_message(self):
        html = self._render([])
        self.assertIn("no close direction yet", html, "full row, empty list → 'no close direction yet' (D-INV-22)")
        self.assertNotIn("no similar tracks", html, "the siblings-column phrase must never leak into the lean cell")

    def test_direction_link_is_an_anchor(self):
        lean = S.Lean(direction="Venetian Snares", level=S.CLOSE, runner=None, n_shared=14)
        html = self._render([lean])
        # The direction must be a clickable <a> element
        self.assertIn("<a", html)
        self.assertIn("Venetian Snares", html)

    def test_up_to_three_directions_all_shown(self):
        """§D.10.1: all qualifying directions shown, each coloured by its own level."""
        leans = [
            S.Lean(direction="Venetian Snares", level=S.CLOSE, runner=None, n_shared=14),
            S.Lean(direction="DeepChord",       level=S.MID,   runner=None, n_shared=12),
            S.Lean(direction="SCSI-9",          level=S.MID,   runner=None, n_shared=11),
        ]
        html = self._render(leans)
        self.assertIn("Venetian Snares", html)
        self.assertIn("DeepChord", html)
        self.assertIn("SCSI-9", html)
        # Nearest (CLOSE) must use green; others (MID) must use amber
        self.assertIn("#2e9e5b", html, "closest direction must be green")
        self.assertIn("#d8932a", html, "mid direction must be amber")

    def test_two_directions_both_shown(self):
        leans = [
            S.Lean(direction="DeepChord", level=S.CLOSE, runner=None, n_shared=12),
            S.Lean(direction="SCSI-9",    level=S.MID,   runner=None, n_shared=11),
        ]
        html = self._render(leans)
        self.assertIn("DeepChord", html)
        self.assertIn("SCSI-9", html)
        self.assertEqual(html.count('<a class="sim-dir"'), 2, "two direction links expected")


class SiblingCellRendering(unittest.TestCase):
    """Sibling chips with correct colours; FAR sibling is allowed (last resort, F-INV-1)."""

    def _render(self, *entries):
        return catalog.render_catalog_html(list(entries))

    def test_close_sibling_green(self):
        sib = S.Sibling(track="B_Track", level=S.CLOSE, n_shared=12)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn("#2e9e5b", html, "close sibling must use green #2e9e5b")
        self.assertIn("sib-chip", html, "sibling must render as .sib-chip")

    def test_mid_sibling_amber(self):
        sib = S.Sibling(track="B_Track", level=S.MID, n_shared=11)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn("#d8932a", html, "mid sibling must use amber #d8932a")

    def test_far_sibling_red_is_allowed(self):
        """F-INV-1: a far sibling appears in red as a last resort — never silenced."""
        sib = S.Sibling(track="B_Track", level=S.FAR, n_shared=10)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        # Red IS present here (unlike the direction column)
        self.assertIn("#c2503d", html, "far sibling must use red #c2503d (last resort, F-INV-1)")
        self.assertIn("sib-chip", html)

    def test_sibling_label_from_title(self):
        sib = S.Sibling(track="B_Track", level=S.CLOSE, n_shared=12)
        html = self._render(
            _e("A_Track", _siblings=[sib]),
            _e("B_Track", title="My Track B"),
        )
        self.assertIn("My Track B", html, "sibling should show the track title as label")

    def test_sibling_is_anchor(self):
        sib = S.Sibling(track="B_Track", level=S.CLOSE, n_shared=12)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn('<a class="sib-chip"', html, "sibling must be an anchor element")

    def test_no_siblings_shows_no_comparison_yet(self):
        # F-INV-7 (defect #3): a single-track full-run library has one placeable version but no OTHER
        # placeable track, so the own-library cell reads 'no comparison yet' — NEVER a bare '—'
        # (the old bug rendered a dash for all three distinct empty reasons).
        html = catalog.render_catalog_html([_e("T", _siblings=[])])
        self.assertIn("sim-none", html, "empty siblings cell must render the grey empty-state span")
        self.assertIn("no comparison yet", html, "single-track full library → 'no comparison yet' (F-INV-7)")
        self.assertNotIn('<span class="sim-none">—</span>', html,
                         "the empty own-library cell must not be a bare dash")

    def test_up_to_three_siblings_shown(self):
        sibs = [S.Sibling(track=f"T{i}", level=S.CLOSE, n_shared=12) for i in range(3)]
        entries = [_e("A_Track", _siblings=sibs)] + [_e(f"T{i}") for i in range(3)]
        html = catalog.render_catalog_html(entries)
        # Count <a class="sib-chip" occurrences (not CSS class definitions)
        self.assertEqual(html.count('<a class="sib-chip"'), 3, "up to 3 siblings, no more")


class ClosenessGlyphTier(unittest.TestCase):
    """D-INV-26 / F-INV-3: BOTH similarity columns carry the 3-tier greyscale-safe closeness
    glyph beside each name (●●● close / ●●○ mid / ●○○ far). One shared scheme, so the cue reads
    the same in the reference column and the own-library column and survives greyscale, print,
    and colour-blind reading — the SHAPE (filled vs hollow) carries it, not the colour."""

    def _render(self, *entries):
        return catalog.render_catalog_html(list(entries))

    # ── §F own-library column (the fix's primary target) ──
    def test_close_sibling_carries_three_filled_dots(self):
        sib = S.Sibling(track="B_Track", level=S.CLOSE, n_shared=12)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn("●●●", html, "close sibling must carry the ●●● glyph (D-INV-26)")
        self.assertIn("dot-tier", html, "sibling chip must carry the .dot-tier glyph span")

    def test_mid_sibling_carries_two_filled_one_hollow(self):
        sib = S.Sibling(track="B_Track", level=S.MID, n_shared=11)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn("●●○", html, "mid sibling must carry the ●●○ glyph (D-INV-26)")

    def test_far_sibling_carries_one_filled_two_hollow(self):
        sib = S.Sibling(track="B_Track", level=S.FAR, n_shared=10)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn("●○○", html, "far sibling must carry the ●○○ glyph (D-INV-26)")

    def test_every_sibling_entry_carries_a_dot_tier(self):
        """Each own-library column entry — not just the first — carries the glyph."""
        sibs = [S.Sibling(track="T0", level=S.CLOSE, n_shared=12),
                S.Sibling(track="T1", level=S.MID, n_shared=11),
                S.Sibling(track="T2", level=S.MID, n_shared=10)]
        entries = [_e("A_Track", _siblings=sibs), _e("T0"), _e("T1"), _e("T2")]
        html = self._render(*entries)
        self.assertEqual(html.count('<a class="sib-chip"'), 3, "three sibling chips expected")
        # one dot-tier glyph per chip (three chips → at least three dot-tier spans on this row)
        self.assertGreaterEqual(html.count("dot-tier"), 3,
                                "every own-library entry must carry its own dot-tier glyph")

    # ── §D reference column (uniform: same shared scheme) ──
    def test_close_lean_carries_three_filled_dots(self):
        lean = S.Lean(direction="DeepChord", level=S.CLOSE, runner=None, n_shared=12)
        html = self._render(_e("T", _leans=[lean]))
        self.assertIn("●●●", html, "close lean must carry the ●●● glyph, uniform with §F (D-INV-26)")

    def test_mid_lean_carries_two_filled_one_hollow(self):
        lean = S.Lean(direction="SCSI-9", level=S.MID, runner=None, n_shared=11)
        html = self._render(_e("T", _leans=[lean]))
        self.assertIn("●●○", html, "mid lean must carry the ●●○ glyph, uniform with §F (D-INV-26)")


class ClosenessCarriesAccessibleWord(unittest.TestCase):
    """D-INV-26 / I.10a: each closeness mark names its level in WORDS as a non-colour, non-shape cue,
    so assistive tech and colour-blind readers get the closeness without the tint or the dot shape.
    The word rides a `title` (hover) AND screen-reader-only text on BOTH the reference (Leans toward)
    and own-library (Similar) columns; the dots stay aria-hidden as the visual redundancy."""

    def _render(self, *entries):
        return catalog.render_catalog_html(list(entries))

    def test_close_sibling_names_close_in_words(self):
        sib = S.Sibling(track="B_Track", level=S.CLOSE, n_shared=12)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn("closeness: close", html, "sibling chip must carry a title naming the closeness word")
        self.assertIn("close closeness", html, "sibling chip must carry screen-reader text naming the level")
        self.assertIn("sr-only", html, "the closeness word must ride a screen-reader-only span")

    def test_far_sibling_names_far_in_words(self):
        sib = S.Sibling(track="B_Track", level=S.FAR, n_shared=10)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn("far closeness", html, "a far sibling must state 'far' in words, not lean on the red")
        self.assertIn("closeness: far", html)

    def test_lean_names_closeness_in_words(self):
        lean = S.Lean(direction="DeepChord", level=S.MID, runner=None, n_shared=12)
        html = self._render(_e("T", _leans=[lean]))
        self.assertIn("mild closeness", html, "reference chip must name its closeness word too (uniform)")
        self.assertIn("closeness: mild", html)

    def test_dots_stay_aria_hidden(self):
        sib = S.Sibling(track="B_Track", level=S.CLOSE, n_shared=12)
        html = self._render(_e("A_Track", _siblings=[sib]), _e("B_Track"))
        self.assertIn('class="dot-tier" aria-hidden="true"', html,
                      "the dot glyph must stay aria-hidden — the word is the accessible carrier")


class Ncols(unittest.TestCase):
    """_NCOLS is the SUPERSET column count; the RENDERED count is dynamic — the two similarity
    columns drop when no version carries their data (D-INV-22 / F-INV-7), so the header count,
    empty-state colspan and responsive shed all follow the actual rendered columns."""

    def test_ncols_equals_header_count(self):
        self.assertEqual(catalog._NCOLS, len(catalog._HEADERS))

    def test_ncols_is_the_full_superset(self):
        # 10 base columns + 2 similarity columns = the full superset _NCOLS
        self.assertEqual(catalog._NCOLS, 12, "expected 12-column superset (10 base + 2 similarity)")

    def test_full_library_renders_all_twelve_columns(self):
        import re
        # a full-run library carries both similarity columns → 12 header cells (<th ...> / <th>,
        # never counting the <thead> wrapper)
        html = catalog.render_catalog_html([_e("T")])
        self.assertEqual(len(re.findall(r"<th[ >]", html)), 12, "a full-run row renders all 12 columns")

    def test_all_quick_library_renders_only_ten_columns(self):
        import re
        # an all-quick library has no reference/sibling computation → both similarity columns drop
        html = catalog.render_catalog_html([_e("Q1", mode="quick"), _e("Q2", mode="quick")])
        self.assertEqual(len(re.findall(r"<th[ >]", html)), 10, "all-quick library sheds both similarity columns")

    def test_last_column_shed_on_narrow(self):
        import re
        html = catalog.render_catalog_html([_e("T")])
        shed = {int(n) for n in re.findall(r"nth-child\((\d+)\)", html)}
        self.assertIn(catalog._NCOLS, shed,
                      f"the last rendered column (#{catalog._NCOLS}) must be shed on narrow screens")


class ColumnPresenceGate(unittest.TestCase):
    """Defect #7 — D-INV-22 / F-INV-7: a similarity column is ABSENT when NO shown version produced
    a computed result. An all-quick library (no fingerprints, no directions) carries neither an
    all-empty 'Leans toward' nor an all-empty 'Similar in library' column — so a brand-new column
    never reads as a missing feature and an all-quick library doesn't carry a dead column. A MIXED
    library keeps both columns (data for even one track, D-INV-22 2026-06-25)."""

    def test_all_quick_library_drops_both_similarity_columns(self):
        html = catalog.render_catalog_html([_e("Q1", mode="quick"), _e("Q2", mode="quick")])
        self.assertNotIn("Leans toward", html,
                         "an all-quick library has no reference computation → the column is absent (D-INV-22)")
        self.assertNotIn("Similar in library", html,
                         "an all-quick library has no sibling computation → the column is absent (F-INV-7)")

    def test_mixed_library_keeps_both_columns(self):
        # one full row produces a computed result → both columns render; the quick row reads its
        # missing-by-mode phrase inside the present column.
        html = catalog.render_catalog_html([_e("F", mode="full"), _e("Q", mode="quick")])
        self.assertIn("Leans toward", html)
        self.assertIn("Similar in library", html)
        self.assertIn("full analysis only", html, "the quick row reads 'full analysis only' inside the present column")


if __name__ == "__main__":
    unittest.main()
