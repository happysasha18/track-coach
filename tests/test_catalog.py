#!/usr/bin/env python3
"""Catalog data + render tests (scripts/library.py pure helpers + scripts/catalog.py).

Covers the new 0.7 catalog: arc downsampling, metric extraction, version grouping by audio hash
(collapse re-analyses, number v1..vN, deltas), and a render smoke test that the page actually emits
rows / search / sort / relative links / mini-arc SVG. Pure, no filesystem, no deps.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import library  # noqa: E402
import catalog  # noqa: E402


class Downsample(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(library.downsample_curve([]), [])

    def test_short_passthrough(self):
        self.assertEqual(library.downsample_curve([0.1, 0.2, 0.3], 40), [0.1, 0.2, 0.3])

    def test_long_reduces_to_n(self):
        out = library.downsample_curve(list(range(100)), 40)
        self.assertEqual(len(out), 40)
        self.assertLess(out[0], out[-1])  # monotone input stays monotone


class RunMetrics(unittest.TestCase):
    def test_pulls_vitals_and_arc_and_tags(self):
        core = {"vitals": {"tempo_bpm": 123, "key": "E minor", "lufs": -12.9,
                           "dynamic_range_db": 14.5, "duration_s": 338.4},
                "energy": [0.0, 0.5, 1.0]}
        meta = {"mood_tags": ["dark"], "style_tags": ["house/club"], "energy_level": 7,
                "tags_source": "heuristic", "title": "T", "audio_sha256": "abc"}
        m = library.run_metrics(core, meta)
        self.assertEqual(m["bpm"], 123)
        self.assertEqual(m["key"], "E minor")
        self.assertEqual(m["lufs"], -12.9)
        self.assertEqual(m["length_s"], 338.4)
        self.assertEqual(m["arc"], [0.0, 0.5, 1.0])
        self.assertEqual(m["mood_tags"], ["dark"])
        self.assertEqual(m["audio_sha"], "abc")

    def test_falls_back_to_top_level(self):
        m = library.run_metrics({"tempo": 100, "duration_s": 60, "energy": []}, {})
        self.assertEqual(m["bpm"], 100)
        self.assertEqual(m["length_s"], 60)
        self.assertEqual(m["mood_tags"], [])

    def test_stores_row_signature_curves_and_tonal(self):
        core = {"energy": list(range(100)), "brightness": list(range(100)),
                "density": list(range(100)),
                "tonal_balance": [{"band": "60–120", "rel_db": 0.0, "dev_db": 2.7},
                                  {"band": "8–16k", "rel_db": -26.9, "dev_db": -3.0}]}
        m = library.run_metrics(core, {})
        # three curves, all downsampled to the SAME length so they align in the ribbon
        self.assertEqual(len(m["energy"]), 48)
        self.assertEqual(len(m["brightness"]), 48)
        self.assertEqual(len(m["density"]), 48)
        # tonal balance is carried band-for-band (only the three fields the strip needs)
        self.assertEqual(len(m["tonal_balance"]), 2)
        self.assertEqual(m["tonal_balance"][0],
                         {"band": "60–120", "rel_db": 0.0, "dev_db": 2.7})

    def test_signature_absent_when_no_curves(self):
        m = library.run_metrics({"vitals": {"tempo_bpm": 120}}, {})
        self.assertEqual(m["energy"], [])
        self.assertEqual(m["tonal_balance"], [])


def _e(track, sha, stamp, mtime, **kw):
    e = {"track": track, "audio_sha": sha, "stamp": stamp, "audio_mtime": mtime,
         "widget": f"{track}-{stamp}.html", "mode": "full"}
    e.update(kw)
    return e


class GroupVersions(unittest.TestCase):
    def test_same_hash_collapses_to_newest_run(self):
        entries = [_e("T", "h1", "2026-01-01_0900", 1000, lufs=-9),
                   _e("T", "h1", "2026-01-02_0900", 1000, lufs=-8)]  # re-analysis, same bounce
        groups = library.group_versions(entries)
        self.assertEqual(len(groups["T"]), 1)
        ver = groups["T"][0]
        self.assertEqual(ver["n_runs"], 2)
        self.assertEqual(ver["rep"]["stamp"], "2026-01-02_0900")  # newest run is the rep

    def test_numbers_v1_to_vn_by_mtime_newest_first(self):
        entries = [_e("T", "h2", "2026-02-01_0900", 2000),
                   _e("T", "h1", "2026-01-01_0900", 1000)]
        vers = library.group_versions(entries)["T"]
        self.assertEqual([v["label"] for v in vers], ["v2", "v1"])  # display newest first
        self.assertEqual(vers[0]["sha"], "h2")

    def test_explicit_version_label_wins(self):
        vers = library.group_versions([_e("T", "h1", "2026-01-01_0900", 1000, version="2026 mix")])["T"]
        self.assertEqual(vers[0]["label"], "2026 mix")

    def test_delta_vs_previous_version(self):
        entries = [_e("T", "h1", "2026-01-01_0900", 1000, lufs=-12, length_s=300),
                   _e("T", "h2", "2026-02-01_0900", 2000, lufs=-8, length_s=310)]
        newest = library.group_versions(entries)["T"][0]  # v2
        self.assertEqual(newest["delta"]["lufs"], 4.0)
        self.assertEqual(newest["delta"]["length_s"], 10.0)

    def test_missing_hash_each_stands_alone(self):
        entries = [{"track": "T", "stamp": "a", "widget": "a.html"},
                   {"track": "T", "stamp": "b", "widget": "b.html"}]
        self.assertEqual(len(library.group_versions(entries)["T"]), 2)


class SignatureSvg(unittest.TestCase):
    """The catalog ROW SIGNATURE: spectral ribbon (time) over a 9-band tonal strip (frequency),
    fully visible by TAP — no hover. Must degrade gracefully on partial / old data. PURE."""
    FULL = {
        "energy": [0.1, 0.5, 1.0, 0.4], "brightness": [0.0, 0.3, 0.7, 1.0],
        "density": [0.2, 0.4, 0.6, 0.8],
        "tonal_balance": [{"band": f"b{i}", "rel_db": -i * 3.0,
                           "dev_db": (5.0 if i == 1 else 0.0)} for i in range(9)],
    }

    def test_full_emits_ribbon_gradient_and_nine_bars(self):
        s = catalog.signature_svg(self.FULL, uid=7)
        self.assertIn('class="sig"', s)
        self.assertIn('linearGradient id="r7"', s)        # brightness-coloured ribbon stroke
        self.assertIn('stroke="url(#r7)"', s)
        self.assertEqual(s.count("<rect"), 9)             # nine tonal bands
        self.assertIn('opacity="0.95"', s)                # the |dev|≥4 band is brightened

    def test_degrades_to_ribbon_only_without_tonal(self):
        e = {k: v for k, v in self.FULL.items() if k != "tonal_balance"}
        s = catalog.signature_svg(e, uid=1)
        self.assertIn('stroke="url(#r1)"', s)             # ribbon still drawn
        self.assertEqual(s.count("<rect"), 0)             # no tonal strip

    def test_falls_back_to_legacy_arc_without_curves(self):
        s = catalog.signature_svg({"arc": [0.2, 0.8, 0.5]}, uid=2)
        self.assertIn('class="arc"', s)                   # legacy sparkline path
        self.assertNotIn('class="sig"', s)

    def test_dash_when_nothing(self):
        self.assertIn("—", catalog.signature_svg({}, uid=3))


class RenderSmoke(unittest.TestCase):
    def setUp(self):
        self.entries = [
            _e("Shared_Memories", "h2", "2026-06-18_0748", 2000, lufs=-12.9, bpm=123,
               key="E minor", length_s=338, mood_tags=["dark", "driving"], style_tags=["house/club"],
               tags_source="heuristic", arc=[0.1, 0.6, 1.0, 0.4], title="Shared Memories",
               verdict="Dense club build"),
            _e("Fragile", "h9", "2026-06-18_0819", 2100, lufs=-23, bpm=89, key="C# minor",
               length_s=420, mode="quick", mood_tags=["melancholic"], arc=[0.2, 0.3], title="Fragile"),
        ]
        self.html = catalog.render_catalog_html(self.entries)

    def test_has_rows_for_each_track(self):
        self.assertIn("Shared Memories", self.html)
        self.assertIn("Fragile", self.html)
        self.assertEqual(self.html.count('<tr data-track='), 2)

    def test_controls_and_sort_headers_present(self):
        self.assertIn('id="q"', self.html)               # search box
        self.assertIn('th class="sortable"', self.html)   # sortable headers
        self.assertIn('data-key="lufs"', self.html)

    def test_relative_widget_links(self):
        self.assertIn('href="widgets/Shared_Memories-2026-06-18_0748.html"', self.html)

    def test_miniarc_svg_and_tags(self):
        self.assertIn("<svg class=\"arc\"", self.html)
        self.assertIn('polyline', self.html)
        self.assertIn(">dark<", self.html)
        self.assertIn("draft", self.html)  # heuristic source marked

    def test_empty_library_message(self):
        self.assertIn("Library is empty", catalog.render_catalog_html([]))

    def test_has_favicon(self):
        self.assertIn('rel="icon"', self.html)

    def test_full_signature_row_renders_ribbon_and_strip(self):
        e = _e("Deep", "h7", "2026-06-19_1000", 3000, bpm=128,
               energy=[0.1, 0.5, 1.0], brightness=[0.2, 0.6, 0.9], density=[0.3, 0.5, 0.7],
               tonal_balance=[{"band": f"b{i}", "rel_db": -i, "dev_db": 0} for i in range(9)])
        page = catalog.render_catalog_html([e])
        self.assertIn('class="sig"', page)
        self.assertIn('stroke="url(#r0)"', page)  # the row's ribbon (uid 0); exact bar count is unit-tested


class OpenLinkPointsAtOriginal(unittest.TestCase):
    """The 'open →' fix (2026-06-19): the catalog must open the ORIGINAL widget in its run dir —
    its stems sit next to it, so the player plays. The deposited library copy is stem-less, so
    opening THAT leaves a dead player (the recurring 'плеер убился' regression). PURE."""

    def test_prefers_original_widget_in_run_dir(self):
        e = {"src_run_dir": "/runs/Shared Memories/2026-06-18_0748",
             "src_widget": "analysis_widget_v0.7.1.html",
             "widget": "Shared_Memories__v0__2026-06-18_0748.html"}
        href = catalog._open_href(e, "widgets")
        self.assertTrue(href.startswith("file://"), f"expected an absolute file URI, got {href}")
        self.assertTrue(href.endswith("analysis_widget_v0.7.1.html"),
                        "open must point at the ORIGINAL widget (stems live beside it)")
        self.assertNotIn("widgets/", href, "open must NOT point at the stem-less library copy")
        self.assertIn("Shared%20Memories", href, "spaces in the path must be URL-encoded")

    def test_falls_back_to_copy_for_old_entries(self):
        # entries deposited before src_widget existed: keep working via the relative copy
        e = {"widget": "T__v0__2026-01-01_0900.html"}
        self.assertEqual(catalog._open_href(e, "widgets"), "widgets/T__v0__2026-01-01_0900.html")

    def test_render_emits_original_file_link(self):
        e = _e("Shared_Memories", "h2", "2026-06-18_0748", 2000, bpm=123, arc=[0.1, 1.0],
               src_run_dir="/runs/SM/2026-06-18_0748", src_widget="analysis_widget_v0.7.1.html")
        html = catalog.render_catalog_html([e])
        self.assertIn("file://", html)
        self.assertIn("analysis_widget_v0.7.1.html", html)

    def test_open_is_a_styled_pill_button(self):
        # Sasha 2026-06-19 "вижу опен но он поменялся": the open control must be a BORDERED PILL with
        # the diagonal ↗ arrow (matching the in-widget "Open ↗" button), not a bare text link. Pins
        # both the markup (↗) and that the CSS gives a.open a border + radius, so the styling can't
        # silently regress to a plain link again.
        e = _e("SM", "h2", "2026-06-18_0748", 2000, bpm=123, arc=[0.1, 1.0],
               src_run_dir="/runs/SM", src_widget="w.html")
        html = catalog.render_catalog_html([e])
        self.assertIn("open ↗", html, "open control lost its ↗ pill label")
        self.assertRegex(html, r"a\.open\{[^}]*border[^}]*\}", "a.open must be a bordered pill")
        self.assertRegex(html, r"a\.open\{[^}]*border-radius[^}]*\}", "a.open pill needs a border-radius")


if __name__ == "__main__":
    unittest.main()
