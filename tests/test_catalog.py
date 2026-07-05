#!/usr/bin/env python3
"""Catalog data + render tests (scripts/library.py pure helpers + scripts/catalog.py).

Covers the new 0.7 catalog: arc downsampling, metric extraction, version grouping by audio hash
(collapse re-analyses, number v1..vN, deltas), and a render smoke test that the page actually emits
rows / search / sort / relative links / mini-arc SVG. Pure, no filesystem, no deps.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import library  # noqa: E402
import catalog  # noqa: E402
import build_widget  # noqa: E402  (cross-page tests render the widget surface too)


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
        self.assertIn(">guess<", self.html)  # heuristic source marked (plain-language label)

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


class NewestOnlyPerTrack(unittest.TestCase):
    """D-INV-32: the catalog shows ONE row per track — its NEWEST version. Older versions get no
    catalog row (they live only in the per-track plaque, INV-11). Every rendered cell reads the
    newest version; the subtitle counts TRACKS (rows shown), never a larger version total."""

    def _two_versions(self):
        # Same track slug, two different bounces (distinct sha) → two VERSIONS; v2 is newest by mtime.
        return [
            _e("Shared", "h1", "2026-01-01_0900", 1000, bpm=120, lufs=-12,
               length_s=300, key="A minor", title="Shared", arc=[0.1, 0.5]),
            _e("Shared", "h2", "2026-06-01_0900", 2000, bpm=124, lufs=-9,
               length_s=310, key="A minor", title="Shared", arc=[0.2, 0.7]),
        ]

    def test_two_versions_render_one_row(self):
        page = catalog.render_catalog_html(self._two_versions())
        self.assertEqual(page.count('<tr data-track='), 1)  # ONE row, not two

    def test_the_row_is_the_newest_version(self):
        page = catalog.render_catalog_html(self._two_versions())
        self.assertIn('data-version="v2"', page)       # newest version's label
        self.assertNotIn('data-version="v1"', page)    # the older version has NO catalog row
        self.assertIn('data-bpm="124"', page)          # newest metrics, not the older 120
        self.assertNotIn('data-bpm="120"', page)

    def test_subtitle_counts_tracks_not_versions(self):
        page = catalog.render_catalog_html(self._two_versions())
        self.assertIn("1 track", page)                 # one track = one row
        self.assertNotIn("2 versions", page)           # never claim more rows than are shown

    def test_single_version_track_unchanged(self):
        page = catalog.render_catalog_html(
            [_e("Solo", "h1", "2026-01-01_0900", 1000, bpm=100, title="Solo", arc=[0.3, 0.4])])
        self.assertEqual(page.count('<tr data-track='), 1)
        self.assertIn("1 track", page)

    def test_two_distinct_tracks_still_two_rows(self):
        page = catalog.render_catalog_html([
            _e("A", "h1", "2026-01-01_0900", 1000, title="A"),
            _e("B", "h2", "2026-01-02_0900", 2000, title="B")])
        self.assertEqual(page.count('<tr data-track='), 2)
        self.assertIn("2 tracks", page)

    def test_sibling_fingerprint_is_newest(self):
        # library.newest_reps picks the NEWEST version's rep entry per track, so the lean/sibling
        # cell (read from that entry's run dir) reflects the newest version, never an older one.
        entries = [
            _e("T", "h1", "2026-01-01_0900", 1000, src_run_dir="/old/run"),
            _e("T", "h2", "2026-06-01_0900", 2000, src_run_dir="/new/run")]
        reps = library.newest_reps(entries)
        self.assertEqual(reps["T"]["src_run_dir"], "/new/run")  # newest version's run dir


class LeanCellEmptyCopy(unittest.TestCase):
    """D-INV-22: the 'leans toward' (reference) column empty state is MODE-AWARE and uses the
    reference column's own domain phrases — a quick-only row reads 'full analysis only'
    (D-INV-20/22), a full row with no close direction reads 'no close direction yet' (SPEC §D) —
    and NEVER the siblings column's phrase 'no similar tracks' (Fable audit, 2026-07-03: the
    shipped `_lean_cell` wrongly emitted 'no similar tracks' for every empty lean, incl. quick)."""

    def test_quick_row_reads_full_analysis_only(self):
        page = catalog.render_catalog_html(
            [_e("Q", "h1", "2026-01-01_0900", 1000, mode="quick", title="Q", bpm=120)])
        self.assertIn("full analysis only", page)          # D-INV-22 quick-cell copy
        self.assertNotIn("no similar tracks", page)         # never the siblings-column phrase

    def test_full_row_no_lean_reads_no_close_direction(self):
        page = catalog.render_catalog_html(
            [_e("F", "h1", "2026-01-01_0900", 1000, mode="full", title="F", bpm=120)])
        self.assertIn("no close direction yet", page)       # full run, no direction stands apart
        self.assertNotIn("no similar tracks", page)

    def test_no_similar_tracks_phrase_never_in_lean_column(self):
        # the phrase belongs to the §F "Similar in library" column's own empty state ("—"),
        # never the reference/leans column — a whole-catalog guard against the collision.
        for m in ("quick", "full"):
            page = catalog.render_catalog_html(
                [_e("T", "h1", "2026-01-01_0900", 1000, mode=m, title="T")])
            self.assertNotIn("no similar tracks", page)


class LinkPointsAtOriginal(unittest.TestCase):
    """Where a row links to: the ORIGINAL widget in its run dir — its stems sit next to it, so the
    player plays. The deposited library copy is stem-less, so opening THAT leaves a dead player
    (the recurring 'плеер убился' regression). `_open_href` is the shared resolver. PURE."""

    def test_prefers_original_widget_in_run_dir(self):
        e = {"src_run_dir": "/runs/Shared Memories/2026-06-18_0748",
             "src_widget": "analysis_widget_v0.7.1.html",
             "widget": "Shared_Memories__v0__2026-06-18_0748.html"}
        href = catalog._open_href(e, "widgets")
        self.assertTrue(href.startswith("file://"), f"expected an absolute file URI, got {href}")
        self.assertTrue(href.endswith("analysis_widget_v0.7.1.html"),
                        "must point at the ORIGINAL widget (stems live beside it)")
        self.assertNotIn("widgets/", href, "must NOT point at the stem-less library copy")
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


class CatalogIsLocalIndex(unittest.TestCase):
    """INV-17 / KI-4: the catalog is a LOCAL index — BOTH the title link (`_open_href`) and the play
    button (`_mix_uri_for`) resolve to an absolute `file://` rooted in the ORIGINAL run dir (where the
    widget + its stems/mix live). Portability scope = local filesystem, NOT GitHub Pages. This guards
    against a refactor silently making one absolute and the other relative (the false premise behind
    KI-4: open→ was already absolute since 0.7.3, not relative)."""

    def test_open_and_play_are_both_absolute_file_in_the_same_run_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "Shared Memories" / "2026-06-18_0748"
            (run / "mix_web").mkdir(parents=True)
            (run / "mix_web" / "mix.m4a").write_bytes(b"\x00")
            (run / "analysis_widget_v0.7.1.html").write_text("<html></html>")
            e = {"src_run_dir": str(run), "src_widget": "analysis_widget_v0.7.1.html",
                 "widget": "SM__v0__2026-06-18_0748.html"}
            open_href = catalog._open_href(e, "widgets")
            mix_uri = catalog._mix_uri_for(e)
            run_uri = run.as_uri()
            self.assertTrue(open_href.startswith("file://"), f"open href not absolute: {open_href}")
            self.assertTrue(mix_uri.startswith("file://"), f"mix uri not absolute: {mix_uri}")
            self.assertTrue(open_href.startswith(run_uri), "open href must live under the run dir")
            self.assertTrue(mix_uri.startswith(run_uri), "play mix must live under the SAME run dir")


class ClickableTitleNoOpenColumn(unittest.TestCase):
    """Sasha 2026-06-20: 'кнопка опен не нужна если сделать само название кликабл'. The track TITLE is
    the link into the widget; the separate 'open' column is gone; the whole row tints on hover so it
    reads as clickable. PURE — assert on the rendered output."""

    def setUp(self):
        e = _e("Shared_Memories", "h2", "2026-06-18_0748", 2000, bpm=123, arc=[0.1, 1.0],
               title="Shared Memories", src_run_dir="/runs/SM/x", src_widget="w.html")
        self.html = catalog.render_catalog_html([e])

    def test_title_is_the_link(self):
        # the title text sits inside an <a class="ttl" href="…the widget…">
        self.assertRegex(self.html, r'<a class="ttl" href="[^"]*w\.html">Shared Memories</a>',
                         "the track title must be the clickable link into the widget")

    def test_no_open_column_remains(self):
        self.assertNotIn('class="open"', self.html, "the standalone open control must be gone")
        self.assertNotIn("c-open", self.html, "the open column cell/class must be gone")
        self.assertNotIn("open ↗", self.html, "the old 'open ↗' label must be gone")

    def test_row_tints_on_hover(self):
        # Sasha 'по наводке мышкой чуть фон меняется' — the hover must actually CHANGE the row
        # background, not just exist as an empty selector. Pin that a background is set.
        self.assertRegex(self.html, r"tbody tr:hover\{background:[^}]+\}",
                         "rows must visibly change background on hover (clickable affordance)")

    def test_plain_span_when_no_widget(self):
        # no resolvable widget → the title is a non-link span, never a dangling empty href
        html = catalog.render_catalog_html([{"track": "T", "stamp": "s", "arc": [0.1]}])
        self.assertIn('<span class="ttl">T</span>', html)
        self.assertNotRegex(html, r'<a class="ttl" href="">')


class ResponsiveTable(unittest.TestCase):
    """INV-10. Sasha 2026-06-20: 'если не на полный экран таблица странно показывается'. On a narrow
    window the 11-column table must shed its least-important columns (media queries) rather than clip,
    with an overflow-scroll fallback below the smallest breakpoint. We guard the BEHAVIOUR (several
    columns are actually hidden, the last/widest one first) not the exact px breakpoints — those are
    free to tune. nth-child is used in the catalog CSS only for this column-shedding, so counting it
    is meaningful."""

    def setUp(self):
        self.html = catalog.render_catalog_html([_e("T", "h", "s", 1, bpm=120, arc=[0.1, 1.0])])

    def test_columns_are_shed_progressively_on_narrow_windows(self):
        shed = {int(n) for n in re.findall(r"nth-child\((\d+)\)", self.html)}
        self.assertGreaterEqual(len(shed), 3,
                                f"responsive table sheds too few columns ({sorted(shed)}); a lone "
                                "padding @media would pass a weaker check — this must hide real columns")
        self.assertIn(catalog._NCOLS, shed,
                      f"the last column (#{catalog._NCOLS}, mode) must be among the first shed on narrow")

    def test_overflow_scroll_is_the_last_resort_fallback(self):
        self.assertRegex(self.html, r"\.tablewrap\{[^}]*overflow-x:auto",
                         "below the smallest breakpoint the table must scroll, not clip")


class StaleWidgetFlag(unittest.TestCase):
    """INV-12 (KI-1): a catalog row whose linked widget was built on an OLDER TC_VERSION than the current
    one is flagged with a self-explaining 'older analysis · vX.Y.Z → re-analyse' chip — so an out-of-date
    deposit is visible without hovering (Glossary 'stale', UI clarity fix 2026-06-30).
    The chip carries class='stale' and the version number in its text; the title tooltip is also kept."""

    def test_current_version_is_not_flagged(self):
        cur = catalog.build_widget.TC_VERSION
        e = _e("T", "h", "2026-01-01_0900", 1, bpm=120, arc=[0.1, 1.0],
               src_run_dir="/r", src_widget=f"analysis_widget_v{cur}.html")
        self.assertNotIn('class="stale"', catalog.render_catalog_html([e]))

    def test_older_version_is_flagged(self):
        e = _e("T", "h", "2026-01-01_0900", 1, bpm=120, arc=[0.1, 1.0],
               src_run_dir="/r", src_widget="analysis_widget_v0.0.1.html")
        html = catalog.render_catalog_html([e])
        self.assertIn('class="stale"', html, "an out-of-date deposit must carry the stale chip element")
        self.assertIn("older analysis", html, "chip text must say 'older analysis' (Glossary wording, not the bare word 'stale')")
        self.assertIn("v0.0.1", html, "chip text must include the specific old version number, visible not just hovered")
        self.assertIn("re-analyse to refresh", html, "the tooltip must explain what to do")

    def test_unparseable_widget_name_is_not_flagged(self):
        e = _e("T", "h", "2026-01-01_0900", 1, bpm=120, arc=[0.1, 1.0],
               src_widget="analysis_widget.html")  # no _vX.Y.Z, no stored version → unknown, don't cry wolf
        self.assertNotIn('class="stale"', catalog.render_catalog_html([e]))

    def test_stored_tc_version_flags_stale_even_with_unparseable_filename(self):
        # KI-7 / INV-12 option-b: the hole — a versionless filename used to slip through. A version
        # stored at deposit time closes it: the row is flagged stale regardless of the filename.
        e = _e("T", "h", "2026-01-01_0900", 1, bpm=120, arc=[0.1, 1.0],
               src_run_dir="/r", src_widget="analysis_widget.html", tc_version="0.0.1")
        html = catalog.render_catalog_html([e])
        self.assertIn('class="stale"', html, "a stored older version must be flagged even with no version in the name")
        self.assertIn("older analysis", html, "chip text must say 'older analysis'")

    def test_stored_tc_version_is_preferred_over_the_filename(self):
        # the deposit-time version is authoritative: a current-looking filename can't mask an older build
        cur = catalog.build_widget.TC_VERSION
        e = _e("T", "h", "2026-01-01_0900", 1, bpm=120, arc=[0.1, 1.0], src_run_dir="/r",
               src_widget=f"analysis_widget_v{cur}.html", tc_version="0.0.1")
        self.assertIn('class="stale"', catalog.render_catalog_html([e]))


class FmtDate(unittest.TestCase):
    """INV-13. `_fmt_date` must format a normal `YYYY-MM-DD_HHMM` stamp AND never crash on a stamp
    that carries extra underscores (a malformed deposit once did → 'too many values to unpack', broke
    the catalog)."""

    def test_normal_stamp(self):
        self.assertEqual(catalog._fmt_date("2026-06-18_0748"), "2026-06-18 07:48")

    def test_extra_underscores_do_not_crash(self):
        # last token isn't a 4-digit time → passes through unchanged, no exception
        self.assertEqual(catalog._fmt_date("Shared_Memories_2026x"), "Shared_Memories_2026x")
        self.assertEqual(catalog._fmt_date("a_b_c_0748"), "a_b_c 07:48")  # robust rsplit, no crash

    def test_no_underscore_passthrough(self):
        self.assertEqual(catalog._fmt_date("whatever"), "whatever")


class CatalogNoDevSlugOnSurface(unittest.TestCase):
    """INV-43 (turnkey — no dev-internal label on the user surface). The catalog page must never
    show a raw track/stamp folder-slug as VISIBLE text: the title link shows the human title, the
    `.trk` raw-slug subtitle is gone, and a run dir that broke the `<track>/<stamp>` convention
    (its stamp is a folder-slug like `Total_Reboot_Wobble_Drift_v0.6.2`) shows `—` in Date, not the
    slug. `_fmt_date`'s pure passthrough (INV-13) is untouched — the guard is caller-side."""

    def test_is_date_shaped(self):
        self.assertTrue(catalog._is_date_shaped("2026-06-18_0748"))
        self.assertTrue(catalog._is_date_shaped("2026-06-18"))
        self.assertFalse(catalog._is_date_shaped("Total_Reboot_Wobble_Drift_v0.6.2"))
        self.assertFalse(catalog._is_date_shaped(""))

    def test_display_date_slug_stamp_falls_back(self):
        # slug stamp, no analyzed_at → em dash, never the slug
        self.assertEqual(catalog._display_date(
            {"stamp": "Total_Reboot_Wobble_Drift_v0.6.2"}), "—")
        # slug stamp but a real analyzed_at → that date
        self.assertEqual(catalog._display_date(
            {"stamp": "slug_x", "analyzed_at": "2026-06-25 10:01"}), "2026-06-25 10:01")
        # date-shaped stamp still formats via _fmt_date
        self.assertEqual(catalog._display_date({"stamp": "2026-06-18_0748"}),
                         "2026-06-18 07:48")

    def test_render_shows_title_not_raw_slug(self):
        e = _e("Total_Reboot_-_Wobble_Drift", "h", "Total_Reboot_Wobble_Drift_v0.6.2", 1,
               bpm=120, arc=[0.1, 1.0], title="Total Reboot — Wobble Drift")
        html_out = catalog.render_catalog_html([e])
        # strip attribute values (data-*, href, class…) → only tag-enclosed VISIBLE text remains
        visible = re.sub(r'\w+="[^"]*"', "", html_out)
        self.assertNotIn("Total_Reboot", visible,
                         "raw folder-slug must not appear as visible catalog text")
        self.assertIn("Total Reboot — Wobble Drift", html_out,
                      "the clean human title must be the row label")


class CatalogRowPlayer(unittest.TestCase):
    """INV-8, INV-9. Session 10: each row with a playable web mix gets a one-button preview player +
    a scrubber that rides the TIME-axis ribbon (not the frequency strip). Rows without a mix render
    no control at all (graceful). The audio source = the ORIGINAL run's mix (file:// in data-mix).
    PURE on the render."""

    SIG = {"energy": [0.1, 0.5, 1.0], "brightness": [0.2, 0.6, 0.9], "density": [0.3, 0.5, 0.7],
           "tonal_balance": [{"band": f"b{i}", "rel_db": -i, "dev_db": 0} for i in range(9)]}

    def _row_html(self, mix_uri):
        e = _e("Deep", "h7", "2026-06-19_1000", 3000, bpm=128, title="Deep",
               src_run_dir="/runs/Deep/x", src_widget="w.html", mix_uri=mix_uri, **self.SIG)
        return catalog.render_catalog_html([e])

    def test_play_button_and_scrubber_when_a_mix_exists(self):
        html = self._row_html("file:///runs/Deep/x/mix_web/mix.m4a")
        self.assertIn('class="cplay"', html, "a playable row must show the one-button player")
        self.assertIn('data-mix="file:///runs/Deep/x/mix_web/mix.m4a"', html,
                      "the row must carry the original run's web-mix URI")
        self.assertIn('class="sig play"', html, "the signature must become a scrubber when playable")
        self.assertIn('class="ph"', html, "the playhead line must be present on a playable row")
        self.assertIn('y2="30"', html, "the playhead must ride the ribbon (RIB_H=30, time axis), not the strip")

    def test_no_control_when_no_mix(self):
        html = self._row_html(None)
        self.assertNotIn('class="cplay"', html, "a row with no mix must NOT show a play button")
        self.assertNotIn("data-mix=", html, "a row with no mix must NOT carry a data-mix")
        self.assertNotIn('class="sig play"', html, "the signature must stay non-interactive without a mix")

    def test_player_js_is_wired(self):
        html = self._row_html("file:///runs/Deep/x/mix_web/mix.m4a")
        self.assertIn("tr.dataset.mix", html, "player JS must read the row's mix source")
        self.assertIn("new Audio(src)", html, "player JS must create the audio from the mix source")
        self.assertIn("getBoundingClientRect", html, "ribbon click-to-seek must be wired")

    def test_exclusive_playback_one_row_at_a_time(self):
        """INV-14 / KI-5: at most ONE preview plays at a time. Guaranteed by (1) a SINGLE shared
        `cur` across all rows and (2) an unconditional `stop()` before `a.play()` in the click
        handler (it silences whatever else is playing). A refactor to per-row state, or a dropped
        stop(), would regress to all-play-at-once while the suite stayed green — this guards it."""
        html = self._row_html("file:///runs/Deep/x/mix_web/mix.m4a")
        self.assertEqual(html.count("let cur=null"), 1,
                         "exactly ONE shared player-state var (per-row state ⇒ all-play-at-once)")
        self.assertIn("function stop()", html, "a shared stop() must exist to silence the active row")
        js = re.sub(r"\s+", " ", html)
        self.assertIn("if(cur&&cur.audio===a){ stop(); return; } stop(); a.play(", js,
                      "before playing a row, the handler must stop() whatever is currently playing")

    def test_dead_play_button_gives_feedback(self):
        """Ops (prover F4): the mix can exist at build time but be gone/moved at view time. Instead of
        a silently dead button, the player must disable it + tooltip 'preview unavailable' on a play
        failure OR an audio `error` event — never a control that does nothing with no explanation."""
        html = self._row_html("file:///runs/Deep/x/mix_web/mix.m4a")
        js = re.sub(r"\s+", " ", html)
        self.assertIn('btn.disabled=true', js, "a failed preview must disable the button")
        self.assertIn('btn.title="preview unavailable"', js, "and explain why via a tooltip")
        self.assertIn('addEventListener("error",dead)', js, "an audio load error must trigger the feedback")
        self.assertIn('.catch(dead)', js, "a failed play() must trigger the feedback (not be swallowed)")
        self.assertIn(".cplay.dead", html, "a disabled/dead play button must be styled as such")

    def test_mix_uri_for_probes_the_run_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(catalog._mix_uri_for({}), "no src_run_dir → no mix")
            self.assertIsNone(catalog._mix_uri_for({"src_run_dir": d}), "no mix file → None (graceful)")
            mix = Path(d) / "mix_web" / "mix.m4a"
            mix.parent.mkdir()
            mix.write_bytes(b"\x00")
            self.assertEqual(catalog._mix_uri_for({"src_run_dir": d}), mix.as_uri(),
                             "an existing web mix → its file:// URI")


class NoResidualPlaceholder(unittest.TestCase):
    """INV-21 — the catalog page must also ship zero unsubstituted __PLACEHOLDER__ tokens."""

    def test_catalog_html_has_no_uppercase_placeholder(self):
        html = catalog.render_catalog_html([_e("T", "h", "2026-06-18_0748", 1, arc=[0.1, 0.5, 1.0])])
        leftovers = sorted(set(re.findall(r"__[A-Z][A-Z0-9_]*__", html)))
        self.assertEqual(leftovers, [], f"INV-21: catalog shipped placeholder(s): {leftovers}")


def _mini_core(n=24, dur=48.0):
    tb = [round(i * dur / n, 3) for i in range(n)]
    return {"duration_s": dur, "time_bins": tb, "tempo": 123,
            "energy": [round(0.2 + 0.6 * i / n, 3) for i in range(n)],
            "brightness": [round(0.5 + 0.2 * (i % 4), 3) for i in range(n)],
            "density": [round(0.3 + 0.1 * (i % 5), 3) for i in range(n)],
            "wobble_rate": [round(1.0 + (i % 4), 3) for i in range(n)],
            "stereo_width": [round(0.4 + 0.1 * (i % 3), 3) for i in range(n)],
            "energy_trend": 0.4, "brightness_trend": -0.1, "density_trend": 0.2,
            "stereo_width_trend": 0.1, "wobble_rate_start_hz": 1.0, "wobble_rate_end_hz": 3.0,
            "section_bounds_s": [round(dur * 0.5, 2)]}


class CrossPageModeAgreement(unittest.TestCase):
    """INV-20 (§7 X1) — the S2 catalog mode pill (.mode.{m}) and the S1 widget mode badge
    (.modebadge.{m}) use the SAME word and SAME colour token per mode, so a run shown 'Quick' in the
    catalog never opens a 'Full' widget. Asserted on BOTH rendered surfaces."""

    @staticmethod
    def _widget_html(mode):
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="tc_xpage_"))
        if mode == "quick":
            (tmp / "mix_web").mkdir(); (tmp / "mix_web" / "mix.m4a").write_bytes(b"\x00")
            kw = dict(audio_mix_rel="mix_web", mode="quick")
        else:
            (tmp / "stems_web").mkdir()
            for s in ("drums", "bass"):
                (tmp / "stems_web" / f"{s}.m4a").write_bytes(b"\x00")
            kw = dict(audio_stems_rel="stems_web", mode="full")
        out = tmp / "w.html"
        build_widget.build_html(_mini_core(), {}, None, None, str(out), "X", build_widget.STRINGS, **kw)
        return out.read_text(encoding="utf-8")

    @staticmethod
    def _colour(css, selector):
        # the colour var declared for a `selector{...color:var(--x)...}` rule
        m = re.search(re.escape(selector) + r"\s*\{[^}]*color:var\((--[a-z]+)\)", css)
        return m.group(1) if m else None

    def test_word_matches_across_pages(self):
        for mode in ("full", "quick"):
            cat = catalog.render_catalog_html([_e("T", "h", "2026-06-18_0748", 1, mode=mode, arc=[0.1, 1.0])])
            self.assertIn(f'class="mode {mode}"', cat, f"catalog pill missing for mode={mode}")
            self.assertIn(f'class="modebadge {mode}"', self._widget_html(mode),
                          f"widget badge word disagrees with catalog for mode={mode}")

    def test_colour_token_matches_across_pages(self):
        cat = catalog.render_catalog_html([_e("T", "h", "2026-06-18_0748", 1, arc=[0.1, 1.0])])
        wid_full = self._widget_html("full")
        wid_quick = self._widget_html("quick")
        for mode, wid in (("full", wid_full), ("quick", wid_quick)):
            cat_col = self._colour(cat, f".mode.{mode}")
            wid_col = self._colour(wid, f".modebadge.{mode}")
            self.assertIsNotNone(cat_col, f"catalog .mode.{mode} colour not found")
            self.assertIsNotNone(wid_col, f"widget .modebadge.{mode} colour not found")
            self.assertEqual(cat_col, wid_col,
                             f"INV-20: mode={mode} colour differs — catalog {cat_col} vs widget {wid_col}")


class DirectionLinksCarryEntryPair(unittest.TestCase):
    """D-INV-37 (writer side, N20) — catalog direction links carry the ONE-SHOT ENTRY PAIR:
    the row's own widget URL + `?direction=⟨URL-encoded direction name⟩#detailed`, so the
    widget opens in Detailed (the panel is Simple-hidden, INV-18/22) focused on that
    direction (the reader side is the widget's D-INV-37 entry reader, test_headless_render
    ::EntryFocus). Supersedes the 0.9 `#refRead` placeholder anchor (which pointed INTO a
    CSS-hidden panel for Simple-remembered users — the class this wiring kills).
    Kept from bug E-s31: hrefs must never be bare '#' (a dead link)."""

    def _entry_with_lean(self, widget_href=None):
        """A catalog entry pre-injected with a synthetic Lean so _lean_cell is exercised."""
        import similarity_columns as SC
        e = _e("test_track", "h1", "2026-01-01_0900", 1000,
               arc=[0.1, 0.5, 1.0], mode="full",
               title="Test Track")
        # Inject a synthetic lean (as build_catalog does at runtime)
        e["_leans"] = [SC.Lean(direction="Venetian Snares", level="close", runner=None, n_shared=10)]
        if widget_href:
            e["src_run_dir"] = widget_href.replace("/widget.html", "")
            e["src_widget"] = "widget.html"
        return e

    def test_direction_link_href_is_not_dead(self):
        """When leans are present, the sim-dir links must NOT use bare '#' as the href
        (bug E-s31: href="#" scrolls nowhere)."""
        e = self._entry_with_lean()
        # Call _lean_cell directly with a widget href (mirrors what _row does)
        import similarity_columns as SC
        leans = e["_leans"]
        cell = catalog._lean_cell(leans, widget_href="file:///test/widget.html")
        hrefs = re.findall(r'href="([^"]*)"', cell)
        self.assertTrue(hrefs, "direction cell must contain at least one href")
        for href in hrefs:
            self.assertNotEqual(href, "#",
                                f"direction link href must not be bare '#' (dead link); got {href!r}. "
                                f"Fix: wire the D-INV-37 entry pair.")

    def test_direction_link_carries_entry_pair(self):
        """Each direction link = own widget URL + `?direction=⟨enc name⟩#detailed` — the
        spaced name URL-encoded (EF-8), the pair in query-then-hash order (D-INV-37)."""
        import similarity_columns as SC
        leans = [SC.Lean(direction="Venetian Snares", level="close", runner=None, n_shared=8)]
        cell = catalog._lean_cell(leans, widget_href="file:///some/path/widget.html")
        hrefs = re.findall(r'<a class="sim-dir" href="([^"]*)"', cell)
        self.assertEqual(len(hrefs), 1, "one lean ⇒ one direction link")
        self.assertEqual(
            hrefs[0], "file:///some/path/widget.html?direction=Venetian%20Snares#detailed",
            "the direction link must carry the one-shot entry pair — the URL-encoded "
            "direction name as `?direction=` plus the `#detailed` view override "
            "(D-INV-37: the panel is Simple-hidden, entry rides the §B.15 override)")

    def test_rendered_catalog_direction_link_carries_entry_pair(self):
        """Render the full catalog HTML: every sim-dir href carries the entry pair and
        none is bare '#'."""
        e = self._entry_with_lean(widget_href="file:///test/widget.html")
        # Build a proper entry with the src fields so _open_href resolves
        e["src_run_dir"] = "/test"
        e["src_widget"] = "widget.html"
        html = catalog.render_catalog_html([e])
        sim_dir_hrefs = re.findall(r'<a class="sim-dir" href="([^"]*)"', html)
        self.assertTrue(sim_dir_hrefs, "the injected lean must render a sim-dir link")
        for href in sim_dir_hrefs:
            self.assertNotEqual(href, "#",
                                f"sim-dir href in rendered catalog must not be bare '#'; "
                                f"got {href!r}. The direction link must navigate, not scroll to top.")
            self.assertIn("?direction=", href,
                          f"rendered direction link must carry `?direction=`; got {href!r}")
            self.assertTrue(href.endswith("#detailed"),
                            f"rendered direction link must end with the `#detailed` "
                            f"one-shot view override; got {href!r}")


if __name__ == "__main__":
    unittest.main()
