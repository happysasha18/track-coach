#!/usr/bin/env python3
"""§F.2 — own-library sibling NAVIGATION in the catalog (F-INV-4 / D-INV-28).

Defect #4: clicking a listed neighbour must scroll the catalog to that track's ROW and highlight it
— pure navigation that changes no analysis state — NOT open the sibling's widget (which is what the
title link and the OLD sibling chip did, making the chip a duplicate of the title link).

Red-first is string-level (cheap, no browser): the sibling chip href is the in-page `#row-<slug>`
anchor, never the sibling's widget path, and every catalog row carries a stable `id`. A browser-level
check (row scrolled + highlight class added on a real click) runs when headless Chrome is available.

Methodology: spec → prove → matrix → test → code. NEVER loosen a test to make code pass.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import catalog  # noqa: E402
import similarity_columns as S  # noqa: E402


def _e(track, **kw):
    e = {"track": track, "audio_sha": f"h_{track}", "stamp": "2026-01-01_0900",
         "audio_mtime": 1000, "widget": f"{track}.html", "mode": "full",
         "bpm": 120, "arc": [0.1, 0.5, 1.0], "title": track.replace("_", " "),
         "_leans": [], "_siblings": []}
    e.update(kw)
    return e


class SiblingChipIsInPageNavigation(unittest.TestCase):
    """F-INV-4 / D-INV-28: the sibling chip scrolls to the sibling's row (#row-<slug>), it does not
    open the widget. The title link opens the widget; a reference DIRECTION opens the widget; an own
    sibling SCROLLS — so the chip href must be the in-page anchor, never the widget path."""

    def _render(self):
        sib = S.Sibling(track="B_Track", level=S.CLOSE, n_shared=12)
        # B carries a resolvable widget path so href_map WOULD produce a file:// widget URL — the old
        # bug used exactly that for the chip href. The new chip must ignore it in favour of #row-.
        return catalog.render_catalog_html([
            _e("A_Track", _siblings=[sib]),
            _e("B_Track", src_run_dir="/runs/B", src_widget="widget_B.html"),
        ])

    def test_sibling_chip_href_is_the_row_anchor(self):
        import re
        html = self._render()
        hrefs = re.findall(r'<a class="sib-chip" href="([^"]*)"', html)
        self.assertTrue(hrefs, "the injected sibling must render a chip")
        self.assertEqual(hrefs[0], "#row-B_Track",
                         "F-INV-4: the sibling chip must be the in-page #row-<slug> anchor")

    def test_sibling_chip_href_is_not_the_widget_path(self):
        import re
        html = self._render()
        hrefs = re.findall(r'<a class="sib-chip" href="([^"]*)"', html)
        for h in hrefs:
            self.assertFalse(h.startswith("file://"), f"chip must not open the widget; got {h!r}")
            self.assertNotIn("widget_B.html", h, "chip must NOT point at the sibling's widget (D-INV-28)")
            self.assertTrue(h.startswith("#row-"), f"chip must be an in-page anchor; got {h!r}")

    def test_every_row_has_a_stable_id(self):
        html = self._render()
        self.assertIn('id="row-A_Track"', html, "each catalog row needs a stable id to scroll to")
        self.assertIn('id="row-B_Track"', html)

    def test_chip_carries_scroll_target_dataattr(self):
        html = self._render()
        self.assertIn('data-scroll-row="row-B_Track"', html,
                      "the chip must name its scroll target for the nav handler")


@unittest.skipUnless(Path(getattr(__import__("headless_check"), "CHROME", "/nonexistent")).exists(),
                     "headless Chrome not available")
class SiblingClickScrollsAndHighlights(unittest.TestCase):
    """Browser-level (L3): a real click on the sibling chip highlights the target row (the pulse
    class is added synchronously in the handler) instead of navigating away — the string test can
    see the href but not the click behaviour. One probe only (Chrome-saturation discipline)."""

    @classmethod
    def setUpClass(cls):
        import headless_check as hc
        cls.hc = hc
        sib = S.Sibling(track="B_Track", level=S.CLOSE, n_shared=12)
        html = catalog.render_catalog_html([
            _e("A_Track", _siblings=[sib]),
            _e("B_Track"),
        ])
        tmp = Path(tempfile.mkdtemp(prefix="tc_nav_"))
        out = tmp / "index.html"
        out.write_text(html)
        cls.widget = str(out)

    def test_click_highlights_target_row(self):
        js = ("(function(){"
              "var chip=document.querySelector('a.sib-chip[data-scroll-row]');"
              "if(!chip)return {found:false};"
              "var id=chip.getAttribute('data-scroll-row');"
              "var row=document.getElementById(id);"
              "if(!row)return {found:true,row:false};"
              "chip.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));"
              "return {found:true,row:true,id:id,pulsed:row.classList.contains('row-pulse')};"
              "})()")
        res = self.hc.probe(self.widget, js, width=1200, height=900)
        self.assertTrue(res.get("found"), "the sibling chip must exist in the rendered DOM")
        self.assertTrue(res.get("row"), "the chip's target row id must resolve to a real row")
        self.assertEqual(res.get("id"), "row-B_Track")
        self.assertTrue(res.get("pulsed"),
                        "clicking the sibling chip must add the highlight-pulse class to the target row")


if __name__ == "__main__":
    unittest.main()
