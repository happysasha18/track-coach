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

    def test_no_siblings_shows_dash(self):
        html = catalog.render_catalog_html([_e("T", _siblings=[])])
        self.assertIn("sim-none", html, "empty siblings cell must show the grey dash")

    def test_up_to_three_siblings_shown(self):
        sibs = [S.Sibling(track=f"T{i}", level=S.CLOSE, n_shared=12) for i in range(3)]
        entries = [_e("A_Track", _siblings=sibs)] + [_e(f"T{i}") for i in range(3)]
        html = catalog.render_catalog_html(entries)
        # Count <a class="sib-chip" occurrences (not CSS class definitions)
        self.assertEqual(html.count('<a class="sib-chip"'), 3, "up to 3 siblings, no more")


class Ncols(unittest.TestCase):
    """_NCOLS stays in sync with _HEADERS and is used in responsive shedding."""

    def test_ncols_equals_header_count(self):
        self.assertEqual(catalog._NCOLS, len(catalog._HEADERS))

    def test_ncols_is_12(self):
        # 10 original + 2 new sim columns
        self.assertEqual(catalog._NCOLS, 12, "expected 12 columns (10 original + 2 sim)")

    def test_last_column_shed_on_narrow(self):
        import re
        html = catalog.render_catalog_html([_e("T")])
        shed = {int(n) for n in re.findall(r"nth-child\((\d+)\)", html)}
        self.assertIn(catalog._NCOLS, shed,
                      f"column #{catalog._NCOLS} (last) must be shed on narrow screens")


if __name__ == "__main__":
    unittest.main()
