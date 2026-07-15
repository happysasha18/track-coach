"""Browser-level regression tests — assert the REAL shipped artifact RENDERED.

WHY this file exists (s34, emphatic): the other ~660 tests assert on the
HTML *string* or a node-DOM stub with NO stylesheet. Two visible bugs still shipped
to the user's eyes twice in one day — the recs grid collapsed to one crooked column,
and card `<b>` leaked as `&lt;b&gt;` — because `style.display=""` "passed" with no
CSS and card TEXT was never read, only counted. A string test cannot see layout,
computed visibility, or escaping. These tests render the widget in headless Chrome
(scripts/headless_check.py) and read back what the EYE sees: real column geometry
and real visible text. See NEXT_STEPS.md "#1 PRIORITY — test-suite overhaul".
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402
import headless_check as hc  # noqa: E402

_HAVE_CHROME = Path(hc.CHROME).exists()


def _rich_core(n=48, dur=120.0):
    """A core wired to spawn SEVERAL recommendation cards (long_section, brightness,
    climax, endpoint, wobble, true-peak, squashed, tonal) so the grid has enough
    cards to actually lay out multiple columns — a 1-card grid can't reveal a
    column-collapse bug."""
    tb = [round(i * dur / n, 3) for i in range(n)]
    ramp = [round(0.15 + 0.8 * i / n, 3) for i in range(n)]          # rises → late climax
    bright = [round(0.1 + 0.85 * i / n, 3) for i in range(n)]        # strong upward → brightness rec
    return {
        "duration_s": dur, "time_bins": tb, "tempo": 123,
        "energy": ramp, "brightness": bright,
        "density": [round(0.3 + 0.5 * (i % 5) / 5, 3) for i in range(n)],
        "wobble_rate": [round(1.0 + (i % 4), 3) for i in range(n)],
        "stereo_width": [round(0.4 + 0.3 * (i % 3) / 3, 3) for i in range(n)],
        "energy_trend": 0.5, "brightness_trend": 0.6, "density_trend": 0.05,
        "stereo_width_trend": 0.1, "wobble_rate_start_hz": 3.0, "wobble_rate_end_hz": 3.2,
        "section_bounds_s": [round(dur * 0.1, 2), round(dur * 0.15, 2)],  # one long tail section
        "endpoint_cosine": 0.97,                                          # → endpoint rec
        "vitals": {"true_peak_db": 0.6, "dynamic_range_db": 4.5},         # → truepeak + squashed
        "tonal_balance": [{"band": "250", "dev_db": 6.0}],                # → tonal_resonance
    }


def _build_rich_widget(with_stems=False):
    tmp = Path(tempfile.mkdtemp(prefix="tc_hl_"))
    stems_rel = None
    if with_stems:
        sdir = tmp / "stems_web"
        sdir.mkdir()
        for s in ("drums", "bass", "vocals"):
            (sdir / f"{s}.m4a").write_bytes(b"\x00")  # existence is all the globber checks
        stems_rel = "stems_web"
    out = tmp / "widget.html"
    build_widget.build_html(_rich_core(), {}, None, None, str(out), "Headless Test",
                            build_widget.STRINGS, mode="full", audio_stems_rel=stems_rel,
                            narrative_md="The mix reads clear.\n\nBass is forward early.")
    return str(out)


# Read the computed visibility ("shown" = display!=none AND non-zero height) of each
# selector, in a chosen view, by toggling the REAL body.simple class the toggle uses.
def _vis_in_view(widget, view, selectors):
    body = "true" if view == "simple" else "false"
    lst = ",".join(f'"{s}"' for s in selectors)
    js = ("(function(){document.body.classList.toggle('simple'," + body + ");"
          "var o={};[" + lst + "].forEach(function(s){var e=document.querySelector(s);"
          "o[s]=e?(getComputedStyle(e).display!=='none' && e.offsetHeight>0):null;});"
          "return o;})()")
    return hc.probe(widget, js, width=1100, height=3200)


# Detailed view (all cards shown) + read the X-left of every visible card, snapped to
# a 12px grid — the count of DISTINCT columns is what the eye sees, robust to auto-fit
# collapsing empty tracks.
_COLS_JS = ("(function(){document.body.classList.remove('simple');"
            "var xs={};Array.prototype.forEach.call(document.querySelectorAll('#recs > .rec'),"
            "function(e){var r=e.getBoundingClientRect();if(r.height>0)xs[Math.round(r.left/12)]=1;});"
            "return {cols:Object.keys(xs).length,"
            "cards:document.querySelectorAll('#recs > .rec').length};})()")


def _make_ref_run_dir(tmp_root):
    """Minimal on-disk run dir (result_core + result_masking) so fingerprint_from_run_dir
    returns a placeable fingerprint — the reference read/web panel then load their
    directions + web notes from the bundled data/ files. Mirrors test_reference_read's
    _make_run_dir (the fixture that already renders refRead for Venetian Snares)."""
    import json
    run_dir = Path(tmp_root) / "run"
    run_dir.mkdir(exist_ok=True)
    (run_dir / "result_core.json").write_text(json.dumps({
        "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
        "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
    (run_dir / "result_masking.json").write_text(json.dumps({
        "band_rms_db": {
            "drums": {"sub": [-30]*8, "low": [-25]*8, "low_mid": [-28]*8,
                      "mid": [-35]*8, "hi_mid": [-40]*8, "air": [-60]*8},
            "bass":  {"sub": [-20]*8, "low": [-18]*8, "low_mid": [-30]*8,
                      "mid": [-45]*8, "hi_mid": [-60]*8, "air": [-80]*8},
            "other": {"sub": [-50]*8, "low": [-45]*8, "low_mid": [-30]*8,
                      "mid": [-25]*8, "hi_mid": [-20]*8, "air": [-25]*8}},
        "stems_analysed": ["drums", "bass", "other"], "duration_s": 48.0,
        "sustain": {"bass": 0.5, "other": 0.4},
        "spectral_centroid": {"other": 800.0}, "total_windows": 8}))
    return str(run_dir)


def _build_ref_widget():
    """A FULL widget that renders the §D reference read (needs a run_dir for the
    fingerprint) AND the tonal-balance panel (needs core.tonal_balance) — the surfaces
    whose Detailed-only gate + read-order were only ever asserted as CSS text."""
    tmp = Path(tempfile.mkdtemp(prefix="tc_ref_"))
    out = tmp / "widget.html"
    core = _rich_core()
    # The tonal panel self-hides below 3 bands and draws by rel_db (0 dB = loudest band).
    core["tonal_balance"] = [
        {"band": "60",  "rel_db": 0.0,  "dev_db": 0.0},
        {"band": "120", "rel_db": -2.0, "dev_db": 1.0},
        {"band": "250", "rel_db": -4.0, "dev_db": 6.0},
        {"band": "500", "rel_db": -6.0, "dev_db": -2.0},
        {"band": "2k",  "rel_db": -9.0, "dev_db": 0.0},
        {"band": "8k",  "rel_db": -14.0, "dev_db": -5.0},
    ]
    build_widget.build_html(core, {}, None, None, str(out), "Reference Test",
                            build_widget.STRINGS, mode="full",
                            run_dir=_make_ref_run_dir(str(tmp)),
                            narrative_md="The mix reads clear.\n\nBass is forward early.")
    return str(out)


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class RefReadSurfacesRendered(unittest.TestCase):
    """The reference read (#refRead), the web panel (#webPanel) and the tonal-balance
    panel (#tonalPanel) had their visibility + Detailed-only gate + read-order verified
    ONLY as CSS text / DOM-string order (inventory Tier-2 holes 12/14/15/16). A browser
    specificity conflict or load-time JS override would pass those and still ship a
    Detailed panel leaking into Simple. These assert the RENDERED visibility + geometry."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_ref_widget()

    def test_reference_surfaces_present_in_detailed(self):
        # Guard the fixture itself: if the bundled directions/web-notes stop producing a
        # reference read, the gate tests below would pass vacuously. Fail loudly instead.
        v = _vis_in_view(self.widget, "detailed", ["#refRead", "#webPanel", "#tonalPanel"])
        for sel in ("#refRead", "#webPanel", "#tonalPanel"):
            self.assertIs(v[sel], True, f"{sel} must render+show in Detailed (fixture guard)")

    def test_refread_detailed_only(self):
        simple = _vis_in_view(self.widget, "simple", ["#refRead"])["#refRead"]
        detail = _vis_in_view(self.widget, "detailed", ["#refRead"])["#refRead"]
        self.assertIs(simple, False, "#refRead must be hidden in Simple (rendered, not CSS text)")
        self.assertIs(detail, True, "#refRead must be visible in Detailed (rendered)")

    def test_webpanel_detailed_only(self):
        simple = _vis_in_view(self.widget, "simple", ["#webPanel"])["#webPanel"]
        detail = _vis_in_view(self.widget, "detailed", ["#webPanel"])["#webPanel"]
        self.assertIs(simple, False, "#webPanel must be hidden in Simple (rendered)")
        self.assertIs(detail, True, "#webPanel must be visible in Detailed (rendered)")

    def test_tonal_panel_visible_in_both_views(self):
        # The tonal-balance panel is the always-on head of the read — NOT Detailed-only.
        for view in ("simple", "detailed"):
            v = _vis_in_view(self.widget, view, ["#tonalPanel"])["#tonalPanel"]
            self.assertIs(v, True, f"#tonalPanel must stay visible in {view} (rendered)")

    def test_read_order_tonal_above_refread_above_webpanel(self):
        # §D.10.3 fixed read order — asserted by RENDERED vertical position, not DOM string
        # order (which cannot see a CSS reorder / flex / grid moving a block visually).
        r = hc.probe(
            self.widget,
            "(function(){document.body.classList.remove('simple');"
            "return {tonal:TC.top('#tonalPanel'),ref:TC.top('#refRead'),web:TC.top('#webPanel')};})()",
            width=1100, height=3600)
        self.assertIsNotNone(r["tonal"]); self.assertIsNotNone(r["ref"]); self.assertIsNotNone(r["web"])
        self.assertLess(r["tonal"], r["ref"], "tonal panel must sit above the reference read")
        self.assertLess(r["ref"], r["web"], "reference read must sit above the web panel")

    def test_ref_panels_stay_within_viewport_when_narrow(self):
        # §I.10 × viewport, for the §D reference surfaces (pass-3 composition, s56). The ×viewport
        # clause named only the recs grid + segmented control + cards; #refRead/#webPanel and the
        # up-to-3-tab selector (.reftab) were only ever probed at width=1100. On a narrow screen a
        # panel or the tab row could overflow horizontally (right edge past the viewport, or an
        # internal h-scroll) and the string/wide tests would never see it. Assert the read stays
        # within its width envelope. Width is the supported narrow floor (560px): a real producer
        # window is ~720px (test_two_columns_at_alexanders_window) and up; the reference read's
        # facet bars hold a ~375px minimum, so below ~535px one panel h-scrolls by design — phone
        # widths are out of this desktop tool's range. (Reads window.innerWidth, so it stays correct
        # whatever the harness reports as the effective viewport.)
        r = hc.probe(
            self.widget,
            "(function(){document.body.classList.remove('simple');"
            "document.querySelectorAll('details.tc-panel').forEach(function(d){d.open=true;});"
            "var vw=window.innerWidth;"
            "function box(sel){var e=document.querySelector(sel);if(!e)return null;"
            "var r=e.getBoundingClientRect();"
            "return {right:Math.round(r.right),scrollW:e.scrollWidth,clientW:e.clientWidth};}"
            "var tabs=document.querySelectorAll('#refRead .reftab');var tmax=0;"
            "tabs.forEach(function(t){var rr=t.getBoundingClientRect();if(rr.right>tmax)tmax=rr.right;});"
            "return {vw:vw,refRead:box('#refRead'),webPanel:box('#webPanel'),"
            "tab_count:tabs.length,tab_maxright:Math.round(tmax)};})()",
            width=560, height=4000)
        vw = r["vw"]
        for name in ("refRead", "webPanel"):
            b = r[name]
            self.assertIsNotNone(b, f"#{name} must render in Detailed (fixture guard)")
            self.assertLessEqual(b["right"], vw + 1,
                                 f"#{name} right edge ({b['right']}) must stay within the viewport "
                                 f"({vw}) — no horizontal overflow on a narrow screen (§I.10 ×viewport)")
            self.assertLessEqual(b["scrollW"], b["clientW"] + 1,
                                 f"#{name} must not scroll horizontally inside itself "
                                 f"(scrollW {b['scrollW']} > clientW {b['clientW']})")
        # When the read renders a multi-direction selector, the tab row must ALSO fit within the
        # viewport (a 3-tab row is the overflow risk). This fixture is single-direction (0 tabs), so
        # the fit is asserted conditionally — the up-to-3-tab case is exercised whenever a fixture
        # yields tabs; the panel-containment above is the always-on guard.
        if r["tab_count"] > 0:
            self.assertLessEqual(r["tab_maxright"], vw + 1,
                                 f"the reference tab selector ({r['tab_count']} tabs, right {r['tab_maxright']}) "
                                 f"must fit within the viewport ({vw}) — no tab-row overflow when narrow")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class RecsGridReflow(unittest.TestCase):
    """The s29 panels + a sub-760px window used to stack every rec in one crooked
    column (viewport `@media` breakpoint). The grid must now reflow by its OWN width."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_rich_widget()

    def test_enough_cards_to_test_layout(self):
        r = hc.probe(self.widget, _COLS_JS, width=1200, height=2800)
        self.assertGreaterEqual(r["cards"], 4,
                                f"fixture must render >=4 cards to test columns, got {r['cards']}")

    def test_two_columns_at_alexanders_window(self):
        # 720px is THE regression width: the old `@media(max-width:760px)` rule fired
        # here and stacked every card in one column at the user's ~2/3-screen window.
        # The container query must now give two columns. A test at a wide (>760px)
        # window would NOT have caught the shipped bug.
        r = hc.probe(self.widget, _COLS_JS, width=720, height=3600)
        self.assertEqual(
            r["cols"], 2,
            f"recs grid must show 2 columns at a 720px window; saw {r['cols']} "
            "(the crooked single-column regression the user saw)")

    def test_capped_at_two_columns_when_wide(self):
        # 2026-07-02: at a wide window the recs must stay at 2 columns, never 3 —
        # a rec card wants a readable line length. The grid caps at two (was ">=3" before).
        r = hc.probe(self.widget, _COLS_JS, width=1100, height=2800)
        self.assertEqual(
            r["cols"], 2,
            f"recs grid must stay capped at 2 columns on a wide window; saw {r['cols']}")

    def test_single_column_when_cramped(self):
        r = hc.probe(self.widget, _COLS_JS, width=460, height=4000)
        self.assertEqual(
            r["cols"], 1,
            f"recs grid must reflow to 1 column when narrow; saw {r['cols']}")

    def test_cards_have_vertical_breathing_room(self):
        # the plates felt glued together. Assert a real gap between
        # stacked cards (single-column view) — never 0.
        r = hc.probe(
            self.widget,
            "(function(){document.body.classList.remove('simple');"
            "var C=Array.prototype.filter.call(document.querySelectorAll('#recs > .rec'),"
            "function(e){return e.getBoundingClientRect().height>0;})"
            ".map(function(e){return e.getBoundingClientRect();})"
            ".sort(function(a,b){return a.top-b.top;});"
            "for(var i=1;i<C.length;i++){if(Math.abs(C[i].left-C[i-1].left)<4)"
            "return {gap:Math.round(C[i].top-C[i-1].bottom)};}return {gap:null};})()",
            width=460, height=4000)
        self.assertIsNotNone(r["gap"], "need >=2 stacked cards to measure the gap")
        self.assertGreaterEqual(r["gap"], 12,
                                f"stacked cards must have a visible vertical gap; saw {r['gap']}px")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class RecsEscaping(unittest.TestCase):
    """Card copy carries trusted <b> emphasis; it must render as bold, NOT leak as
    literal `&lt;b&gt;` text (the s33 double-escape bug)."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_rich_widget()

    def test_no_escaped_tag_leak_in_cards(self):
        r = hc.probe(
            self.widget,
            "(function(){document.body.classList.remove('simple');"
            "return {leak:TC.escLeak('#recs'),"
            "vis:Array.prototype.filter.call(document.querySelectorAll('#recs > .rec'),"
            "function(e){return e.getBoundingClientRect().height>0;}).length};})()",
            width=1100, height=2800)
        self.assertEqual(r["leak"], 0,
                         "no card may show a literal &lt;tag&gt; — trusted HTML must render")

    def test_recs_non_empty_in_default_view(self):
        # Default (simple) view: at least one card must be visible — a blank recs
        # panel is exactly the kind of broken render a human catches first.
        r = hc.probe(
            self.widget,
            "(function(){return {vis:Array.prototype.filter.call("
            "document.querySelectorAll('#recs > .rec'),function(e){"
            "return e.getBoundingClientRect().height>0;}).length};})()",
            width=1100, height=2800)
        self.assertGreaterEqual(r["vis"], 1,
                                "default view must show at least one visible rec card")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class ViewLadderRendered(unittest.TestCase):
    """The recurring Simple/Detailed regression ([[track-coach-graph-regression]]) and
    INV-19 were only ever asserted on the CSS *text* (test_view_ladder.py extracts
    selector sets by regex). A specificity conflict or a stylesheet the browser
    resolves differently passes those and still ships a broken view — the exact
    class of miss the s34 overhaul targets. These check the RENDERED visibility."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_rich_widget(with_stems=True)

    def test_stemlanes_hidden_in_simple_shown_in_detailed(self):
        # THE recurring inversion, now pinned at render level: the deep stem viz is
        # Detailed-only. Simple must compute display:none; Detailed must show it.
        simple = _vis_in_view(self.widget, "simple", ["#stemlanes"])["#stemlanes"]
        detail = _vis_in_view(self.widget, "detailed", ["#stemlanes"])["#stemlanes"]
        self.assertIs(simple, False, "#stemlanes must be hidden in Simple (rendered)")
        self.assertIs(detail, True, "#stemlanes must be visible in Detailed (rendered)")

    def test_core_surfaces_visible_in_both_views(self):
        # Story / read / evidence are every-view surfaces — a blank one in either view
        # is a broken render the string tests can't see.
        core = ["#story", "#evidence", "#readBody"]
        for view in ("simple", "detailed"):
            v = _vis_in_view(self.widget, view, core)
            for sel in core:
                self.assertIs(v[sel], True, f"{sel} must be visible in {view} (rendered)")

    def test_nontimecoded_recs_hidden_in_simple_shown_in_detailed(self):
        # Simple shows only timecoded recs; Detailed adds the global ones. Assert on the
        # computed display of a real non-timecoded card, not a CSS substring.
        js = ("(function(v){document.body.classList.toggle('simple',v);"
              "var g=document.querySelectorAll('#recs > .rec:not([data-t])');"
              "var shown=0;g.forEach(function(e){if(getComputedStyle(e).display!=='none'"
              "&&e.offsetHeight>0)shown++;});return {total:g.length,shown:shown};})")
        simple = hc.probe(self.widget, js + "(true)", width=1100, height=3200)
        detail = hc.probe(self.widget, js + "(false)", width=1100, height=3200)
        self.assertGreater(simple["total"], 0, "fixture needs a non-timecoded card to test the gate")
        self.assertEqual(simple["shown"], 0, "Simple must hide non-timecoded recs (rendered)")
        self.assertEqual(detail["shown"], detail["total"],
                         "Detailed must show every non-timecoded rec (rendered)")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class SimpleViewGatingBrowser(unittest.TestCase):
    """Browser-level companion to test_widget_contract::SimpleViewGating and
    test_view_ladder::CssGatingContract (INV-18 / INV-22).

    Those tests assert the CSS hide-set by parsing `body.simple ... {display:none}`
    from the HTML text — they cannot verify that the browser actually computes those
    elements hidden.  A specificity conflict or a JS override at load time passes
    the string test and still ships a broken Simple view.

    These tests render full widgets in headless Chrome and read back REAL computed
    visibility by toggling the `body.simple` class the toggle uses, via
    `_vis_in_view`.  The hide-set is tested as a contract (all elements together)
    rather than one element at a time, which is the direct browser proof for INV-18
    and INV-22.  Two fixtures cover two disjoint halves of the hide-set:
      - stems widget (`_build_rich_widget(with_stems=True)`) has `#stemlanes`/`#seqKey`
      - ref widget (`_build_ref_widget()`) has `#refRead`/`#webPanel`
    """

    @classmethod
    def setUpClass(cls):
        cls.stems_widget = _build_rich_widget(with_stems=True)
        cls.ref_widget = _build_ref_widget()

    def test_stem_viz_hidden_in_simple_visible_in_detailed(self):
        """#stemlanes and #seqKey must be HIDDEN in Simple and VISIBLE in Detailed.
        INV-18 / INV-22 browser proof for the stem-viz half of the Simple hide-set
        (the recurring inversion the s34 overhaul targets — previously only checked
        as a CSS text substring, not as real computed display)."""
        sels = ["#stemlanes", "#seqKey"]
        simple = _vis_in_view(self.stems_widget, "simple", sels)
        detail = _vis_in_view(self.stems_widget, "detailed", sels)
        for sel in sels:
            self.assertIs(simple[sel], False,
                          f"{sel} must be HIDDEN in Simple view (real computed visibility, INV-22)")
            self.assertIs(detail[sel], True,
                          f"{sel} must be VISIBLE in Detailed view (real computed visibility, INV-22)")

    def test_ref_panels_hidden_in_simple_visible_in_detailed(self):
        """#refRead and #webPanel must be HIDDEN in Simple and VISIBLE in Detailed.
        INV-18 / INV-22 browser proof for the reference-panel half of the Simple
        hide-set (§D.10.2 / §D.10.3 Detailed-only gates — previously only checked
        as a CSS text substring, not as real computed display)."""
        sels = ["#refRead", "#webPanel"]
        simple = _vis_in_view(self.ref_widget, "simple", sels)
        detail = _vis_in_view(self.ref_widget, "detailed", sels)
        for sel in sels:
            self.assertIs(simple[sel], False,
                          f"{sel} must be HIDDEN in Simple view (real computed visibility, INV-18)")
            self.assertIs(detail[sel], True,
                          f"{sel} must be VISIBLE in Detailed view (real computed visibility, INV-18)")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class PreRenderSmoke(unittest.TestCase):
    """The standing ship gate (scripts/prerender_smoke.py) must pass on a real render:
    no JS console error, no escaped-tag leak, recs non-empty, every core surface visible
    in both views. This runs the exact function the ship-checklist CLI runs, so the gate
    can never silently rot away from the checklist."""

    def test_smoke_clean_on_a_full_widget(self):
        import prerender_smoke  # noqa: E402  (scripts is already on sys.path)
        fails = prerender_smoke.run_smoke(_build_rich_widget(with_stems=True))
        self.assertEqual(fails, [], "pre-render smoke found render defects:\n" + "\n".join(fails))


def _build_omitted_widget():
    """A FULL widget whose separation returned SIX stems, two of which are near-silent
    (vocals/piano ≈ −90 dB, below STEM_EMPTY_FLOOR_DB). The player still ships all six;
    the per-stem viz keeps the 4 loud ones. SPEC CR-2 (docs/SPEC.md:75) requires the
    widget to NAME the omitted two ("stems X, Y omitted — too little material to read")
    — the regression this fixture guards is that they vanish with no acknowledgment.
    Spectral centroids are distinct for the two silent stems so they get different band words
    (INV-STEMNAME-NEARSILENT-ID): piano=600 Hz → 'mid (near-silent)', vocals=1200 Hz → 'mid (near-silent)'
    ... wait: both centroid ≥600 and < 2000 → both 'mid'. But they're sorted: piano < vocals, so
    piano → 'mid 1 (near-silent)', vocals → 'mid 2 (near-silent)'.  Deliberately uses one with
    centroid <600 Hz and one ≥600 Hz: piano=400 Hz → 'low-mid', vocals=1200 Hz → 'mid' (distinct)."""
    tmp = Path(tempfile.mkdtemp(prefix="tc_omit_"))
    sdir = tmp / "stems_web"
    sdir.mkdir()
    for s in ("drums", "bass", "other", "guitar", "vocals", "piano"):
        (sdir / f"{s}.m4a").write_bytes(b"\x00")
    W = 8
    def _band(v):
        return {b: [float(v)] * W for b in build_widget.BAND_ORDER}
    loud, silent = _band(-20.0), _band(-90.0)
    masking = {
        "stems_analysed": ["drums", "bass", "other", "guitar", "vocals", "piano"],
        "band_rms_db": {"drums": loud, "bass": loud, "other": loud, "guitar": loud,
                        "vocals": silent, "piano": silent},
        # Distinct centroids for the silent stems: piano=400 Hz → "low-mid", vocals=1200 Hz → "mid"
        "spectral_centroid": {"drums": 250.0, "bass": 120.0, "other": 800.0,
                              "guitar": 1000.0, "piano": 400.0, "vocals": 1200.0},
        "total_windows": W, "duration_s": 120.0,
        "time_bins": [round(i * 120.0 / W, 3) for i in range(W)],
        "masking_summary": {},
    }
    out = tmp / "widget.html"
    build_widget.build_html(_rich_core(), {}, masking, None, str(out), "Omitted Test",
                            build_widget.STRINGS, mode="full", audio_stems_rel="stems_web",
                            narrative_md="The mix reads clear.\n\nBass is forward early.")
    return str(out)


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class OmittedStemsAcknowledged(unittest.TestCase):
    """SPEC CR-2 (docs/SPEC.md:75) + INV-42: when separation returns near-silent stems,
    the stem panel must ACKNOWLEDGE them by name, not silently drop them. Regression
    guard (2026-07-02): they used to render; 0.8.1 stripped them from the draw
    grid and no caption replaced them, so vocals/piano vanished and every string test
    (and Fable) missed it — because the tests checked the disappearance, never the
    acknowledgment. This reads the REAL rendered stem-panel text in headless Chrome."""

    def test_payload_marks_the_near_silent_stems_omitted(self):
        # Precondition (backend already correct): the data names the omitted stems.
        widget = _build_omitted_widget()
        got = hc.probe(widget,
                       "(function(){return (D.stem&&D.stem.omitted)||[];})()",
                       width=1100, height=3200)
        self.assertEqual(sorted(got), ["piano", "vocals"],
                         "backend must mark the near-silent stems omitted")

    def test_stem_panel_names_the_omitted_stems_visibly(self):
        # The regression itself: the RENDERED stem panel must name the omitted stems.
        widget = _build_omitted_widget()
        res = hc.probe(widget, "(function(){"
                       "document.body.classList.remove('simple');"  # stem viz is Detailed-only
                       "var e=document.getElementById('seqKey');"
                       "if(!e)return{present:false};"
                       "return{present:true,"
                       "vis:getComputedStyle(e).display!=='none'&&e.offsetHeight>0,"
                       "text:(e.textContent||'').toLowerCase()};})()",
                       width=1100, height=3200)
        self.assertTrue(res.get("present"), "stem-panel legend (#seqKey) must exist on a full run")
        self.assertTrue(res.get("vis"), "the omitted-stems acknowledgment must be VISIBLE in Detailed")
        text = res.get("text", "")
        # Part 1, item 3 (s45): the omitted note now shows a COUNT sentence rather than each stem's
        # display name ("near-silent, near-silent" was a meaningless listing). The note reads
        # "N parts were too quiet to read and are left out". Check: count-sentence words are present
        # and raw stem names are absent.
        self.assertTrue("too quiet" in text or "left out" in text or "omit" in text,
                        "the omitted-stems note must explain WHY they are absent; got: " + repr(text[:200]))
        self.assertNotIn("vocals", text,
                         "raw 'vocals' must not appear in the omitted-stems note")
        self.assertNotIn("piano", text,
                         "raw 'piano' must not appear in the omitted-stems note")

    def test_omitted_stems_sink_below_the_significant_ones(self):
        # Layout (s37): an empty lane in the MIDDLE reads as a gap; the near-silent stems
        # must be grouped at the BOTTOM, below every stem that carries real content.
        widget = _build_omitted_widget()
        res = hc.probe(widget, "(function(){"
                       "var s=(D.player&&D.player.srcs||[]).map(function(x){return x.name;});"
                       "var om=(D.stem&&D.stem.omitted)||[];"
                       "return {order:s,omitted:om};})()",
                       width=1100, height=3200)
        order, omitted = res["order"], set(res["omitted"])
        last_significant = max((i for i, n in enumerate(order) if n not in omitted), default=-1)
        first_omitted = min((i for i, n in enumerate(order) if n in omitted), default=len(order))
        self.assertGreater(first_omitted, last_significant,
                           f"omitted stems must sit below every significant one; order={order}, omitted={sorted(omitted)}")


class CatalogPageResponsive(unittest.TestCase):
    """Browser-level gate on the catalog page (index.html): responsive column shedding is
    REAL geometry a string test can't see. PRIORITY (Fable pre-1.0 V1): the two reference
    columns (11 Leans toward, 12 Similar — the newest work) must stay visible longest, so the
    less-important mood/style (9) + Analysis (10) drop first at `@media(max-width:1440px)`; the
    reference columns themselves drop only at `@media(max-width:1100px)`; `@media(max-width:880px)`
    also hides col 3 (date). Same bug class as the crooked recs grid — a computed `display:none`
    under a viewport width, invisible to a string/DOM-stub test. INV-10 / responsive-table."""

    @classmethod
    def setUpClass(cls):
        if not _HAVE_CHROME:
            raise unittest.SkipTest("headless Chrome not available")
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import catalog  # noqa: E402
        entries = [
            {"track": "Alpha", "audio_sha": "h1", "stamp": "2026-01-01_0900",
             "audio_mtime": 1000, "widget": "a.html", "mode": "full", "bpm": 120,
             "key": "A minor", "lufs": -9.0, "dr": 10.0, "length_s": 300,
             "mood_tags": ["dark"], "style_tags": ["techno"], "arc": [0.1, 0.5, 1.0]},
            {"track": "Beta", "audio_sha": "h2", "stamp": "2026-02-01_0900",
             "audio_mtime": 2000, "widget": "b.html", "mode": "full", "bpm": 128,
             "key": "C major", "lufs": -8.0, "dr": 8.0, "length_s": 320,
             "mood_tags": ["bright"], "style_tags": ["house"], "arc": [0.2, 0.6, 0.9]},
        ]
        tmp = Path(tempfile.mkdtemp(prefix="tc_cat_"))
        out = tmp / "index.html"
        out.write_text(catalog.render_catalog_html(entries))
        cls.widget = str(out)

    def _col_shown(self, width, nth):
        js = ("(function(){var th=document.querySelector('thead th:nth-child(" + str(nth) + ")');"
              "return th?getComputedStyle(th).display!=='none':null;})()")
        return hc.probe(self.widget, js, width=width, height=900)

    def test_1400_keeps_reference_cols_drops_moodstyle_and_mode(self):
        # Fable pre-1.0 V1: at a full 1400px window the reference columns (11 Leans toward,
        # 12 Similar) used to clip off-screen. New priority — drop mood/style (9) + Analysis (10)
        # first at ≤1440 so the reference work stays visible on a normal full window.
        self.assertFalse(self._col_shown(1400, 9), "col 9 (mood/style) drops first at ≤1440px")
        self.assertFalse(self._col_shown(1400, 10), "col 10 (Analysis) drops first at ≤1440px")
        self.assertTrue(self._col_shown(1400, 11), "col 11 (Leans toward) must stay visible at 1400px")
        self.assertTrue(self._col_shown(1400, 12), "col 12 (Similar in library) must stay visible at 1400px")
        self.assertTrue(self._col_shown(1400, 3), "col 3 (date) must show at 1400px")

    def test_wide_1500_shows_all_columns(self):
        for nth in (9, 10, 11, 12):
            self.assertTrue(self._col_shown(1500, nth),
                            f"col {nth} shows on a wide (>1440px) window")

    def test_narrow_1000_sheds_cols_9_to_12(self):
        for nth in (9, 10, 11, 12):
            self.assertFalse(self._col_shown(1000, nth),
                             f"col {nth} must be hidden below 1100px; got shown")
        self.assertTrue(self._col_shown(1000, 3),
                        "col 3 (date) still shows at 1000px (above the 880 breakpoint)")

    def test_very_narrow_820_also_sheds_date(self):
        self.assertFalse(self._col_shown(820, 3), "col 3 (date) must be hidden below 880px")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class QuickModeRefReadAbsent(unittest.TestCase):
    """D-INV-5 / D-INV-20: quick mode must produce NO #refRead block in the rendered DOM
    even when a run_dir is supplied. The string test
    (test_reference_read::ReferenceReadDetailedOnly::test_quick_mode_has_no_refread_block)
    checks HTML source only — it cannot catch a JS loader injecting the block later.
    This verifies the RENDERED DOM in headless Chrome."""

    @classmethod
    def setUpClass(cls):
        tmp = Path(tempfile.mkdtemp(prefix="tc_qm_"))
        out = tmp / "widget.html"
        build_widget.build_html(_rich_core(), {}, None, None, str(out), "Quick Mode Test",
                                build_widget.STRINGS, mode="quick",
                                run_dir=_make_ref_run_dir(str(tmp)),
                                narrative_md="Quick run.")
        cls.widget = str(out)

    def test_refread_absent_in_quick_mode_rendered_dom(self):
        """#refRead must not exist in the rendered DOM in quick mode (D-INV-5 / D-INV-20)."""
        r = hc.probe(
            self.widget,
            "(function(){var e=document.getElementById('refRead');"
            "return {present:!!e,visible:e?(getComputedStyle(e).display!=='none'"
            "&&e.offsetHeight>0):false};})()",
            width=1100, height=3200)
        self.assertFalse(r["present"],
                         "#refRead must be absent from the rendered DOM in quick mode "
                         "(quick run ⊆ Simple view — no reference layer; D-INV-5 / D-INV-20)")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class RefReadEvidenceMarksRendered(unittest.TestCase):
    """D-INV-10: ★/☆ evidence marks must RENDER visibly in the reference bars panel in Detailed
    view; missing-axis rows must not produce phantom zero-height rows. The string tests
    (test_reference_read::ReferenceReadRichLook, ::ReferenceReadOmitsMissingAxes) check
    HTML source; they cannot verify that the browser actually displays these marks or that
    CSS doesn't render hidden phantom rows for omitted axes."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_ref_widget()

    def test_star_marks_visible_in_detailed(self):
        """At least one data-confirmed row (★/☆ mark) must be VISIBLE in Detailed view (D-INV-10)."""
        r = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "var rows=document.querySelectorAll('#refRead [data-confirmed=\"1\"]');"
            "var vis=0;"
            "rows.forEach(function(e){"
            "if(e.offsetHeight>0&&getComputedStyle(e).display!=='none')vis++;});"
            "return {total:rows.length,visible:vis};})()",
            width=1100, height=3600)
        self.assertGreater(r["total"], 0,
                           "fixture must produce at least one data-confirmed (★/☆) row — "
                           "check _build_ref_widget or the bundled reference_web_notes.json")
        self.assertGreater(r["visible"], 0,
                           "at least one ★/☆ evidence mark must be VISIBLE in Detailed view "
                           "(D-INV-10: each trait carries its real evidence)")

    def test_all_rendered_rows_have_nonzero_height(self):
        """Every rendered .refread-row must have non-zero height — no phantom hidden rows for
        missing axes (D-INV-10: omitted axes must not appear, even invisibly)."""
        r = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "var rows=document.querySelectorAll('#refRead .refread-row');"
            "var hidden=0,total=rows.length;"
            "rows.forEach(function(e){"
            "if(e.offsetHeight<=0||getComputedStyle(e).display==='none')hidden++;});"
            "return {total:total,hidden:hidden};})()",
            width=1100, height=3600)
        self.assertGreater(r["total"], 0,
                           "fixture must produce refread rows to test the omission gate")
        self.assertEqual(r["hidden"], 0,
                         f"every refread-row must have non-zero height — {r['hidden']} "
                         "phantom/hidden row(s) detected (D-INV-10: missing axes omitted, never hidden)")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class RefReadBarsRendered(unittest.TestCase):
    """D-INV-19: the per-facet signed bars (fir-tree decomposition) must physically RENDER
    with non-zero pixel widths in a real browser. The string tests
    (test_reference_read::ReferenceReadBars, ::ReferenceReadMostSimilarFirst) verify HTML
    structure and sort order from source — they cannot confirm that CSS percentage widths
    resolve to actual rendered pixels."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_ref_widget()

    def test_refread_bars_render_with_nonzero_width(self):
        """At least one .refread-bar element must have non-zero rendered pixel width (D-INV-19)."""
        r = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "var bars=Array.prototype.slice.call("
            "document.querySelectorAll('#refRead .refread-bar'));"
            "var any_nonzero=bars.some(function(e){"
            "return e.getBoundingClientRect().width>0;});"
            "return {count:bars.length,any_nonzero_width:any_nonzero};})()",
            width=1100, height=3600)
        self.assertGreater(r["count"], 0,
                           "fixture must produce .refread-bar elements — check _build_ref_widget")
        self.assertTrue(r["any_nonzero_width"],
                        "at least one .refread-bar must render with non-zero pixel width "
                        "(D-INV-19: full-dim fingerprint bars rendered, not just present in source HTML)")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class NoRawStemNameOnAnySurface(unittest.TestCase):
    """INV-STEMNAME-ALL (0.9.22, s45): the same stem must show ONE producer name on every
    surface, and no raw splitter/model/tool name may appear in rendered text.
    Exercises all 8 leaking surfaces from data/stem_naming_inventory_s45.md:
      Surface C — omitted stems note (vocals/piano → 'near-silent')
      Surface E — rhythm panel tile headings ('other' → character label)
      Surface F — leakage pairs and bleed caveats ('other'/'bass' raw names)
      Surface G — mapPanel stem card titles and family bars ('other' family)
      Surface D — notes panel title ('vocals' label → display name)
      plus static STRINGS: note_hint 'basic-pitch', map_hint 'Demucs', note_hint_other 'Demucs'
    The NO-.als path is used (the leaking path where the arc fallback emits raw names)."""

    @classmethod
    def setUpClass(cls):
        if not _HAVE_CHROME:
            raise unittest.SkipTest("headless Chrome not available")
        tmp = Path(tempfile.mkdtemp(prefix="tc_rawstem_"))
        N = 8
        BIG = -20.0    # well above STEM_EMPTY_FLOOR_DB (-55 dB) → significant
        SMALL = -80.0  # well below floor → near-silent / omitted
        BANDS = ["sub", "low", "low_mid", "mid", "hi_mid", "air"]

        # Masking: drums/bass/other significant; vocals/piano near-silent.
        # bass dominates "sub" at -10 dB; "other" also sits in sub at -25 dB
        # (gap = 15 dB ≥ 10 = LEAK_LOUDER_DB) → triggers a bleed caveat for "other".
        masking = {
            "stems_analysed": ["drums", "bass", "other", "vocals", "piano"],
            "total_windows": N,
            "time_bins": [float(i) for i in range(N)],
            "duration_s": float(N),
            "band_rms_db": {
                "drums": {b: ([BIG] if b in ("low_mid", "mid") else [SMALL]) * N for b in BANDS},
                "bass":  {b: ([-10.0] if b == "sub" else [SMALL]) * N for b in BANDS},
                "other": {b: ([-25.0] if b == "sub" else [SMALL]) * N for b in BANDS},
                "vocals": {b: [SMALL] * N for b in BANDS},
                "piano":  {b: [SMALL] * N for b in BANDS},
            },
            "masking_summary": {},
            "masking_flags": {},
            "sustain": {"bass": 0.9, "other": 0.3},
            "spectral_centroid": {"drums": 300.0, "bass": 120.0, "other": 800.0},
            "spectral_flatness": {},
            "spectrum": {},
            "spectrum_freqs": None,
        }

        # Rhythm: leakage pair (bass ↔ other, r=0.65 ≥ 0.2) drives the bleed caveat.
        rhythm = {
            "rhythm": {
                "drums": {"onset_rate": 4.0, "offgrid_ms": 5.0, "syncopation_pct": 10.0,
                          "onset_density": [1.0] * N},
                "bass":  {"onset_rate": 0.5, "offgrid_ms": 8.0, "syncopation_pct": 5.0,
                          "onset_density": [1.0] * N},
                "other": {"onset_rate": 0.5, "offgrid_ms": 15.0, "syncopation_pct": 20.0,
                          "onset_density": [1.0] * N},
            },
            "separation": {
                "reconstruction_error_db": -20.0,
                "reconstruction_text": "The parts add back up cleanly.",
                "leakage": [{"a": "bass", "b": "other", "r": 0.65}],
            },
        }

        # Stemmap: has a family_matches entry with family "other" (should become "the rest")
        # and a verdict_text that has been cleaned (already fixed in map_stems.py).
        stemmap = {
            "stems": {
                "drums": {"verdict": "clear", "best_family": "drums",
                          "verdict_text": "Tracks the drums family closely.",
                          "family_matches": [{"family": "drums", "r": 0.85},
                                             {"family": "other", "r": 0.1},
                                             {"family": "kick",  "r": 0.05}]},
                "bass":  {"verdict": "clear", "best_family": "bass",
                          "verdict_text": "Tracks the bass family closely.",
                          "family_matches": [{"family": "bass",  "r": 0.90},
                                             {"family": "other", "r": 0.05},
                                             {"family": "kick",  "r": 0.02}]},
                "other": {"verdict": "mixed", "best_family": None,
                          "verdict_text": "Has signal, but timing follows several parts.",
                          "family_matches": [{"family": "other", "r": 0.30},
                                             {"family": "chord", "r": 0.20},
                                             {"family": "lead",  "r": 0.10}]},
            },
            "model_recommendation": "a 6-stem model",
            "model_why": "The project has melodic/harmonic parts. A 6-stem model adds stems.",
            "export_suggestion": None,
        }

        # Notes: label = "vocals" (raw stem name — must be routed through disp()).
        notes = {
            "label": "vocals",
            "notes": [{"t": 0.0, "dur": 0.5, "pitch": 60, "amp": 0.8}],
            "pitch_min": 60,
            "pitch_max": 72,
            "n_notes": 1,
        }

        out = tmp / "widget.html"
        build_widget.build_html(
            _rich_core(), {}, masking, None, str(out), "Raw Stem Test",
            build_widget.STRINGS, mode="full",
            stemmap=stemmap, rhythm=rhythm, notes=notes,
        )
        cls.widget = str(out)

    def _full_text(self):
        """Rendered innerText with all panels open and Detailed view."""
        return hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "return document.body.innerText;})()",
            width=1100, height=3400,
        )

    def test_no_raw_tool_names_in_any_text(self):
        """Demucs, htdemucs, htdemucs_6s, basic-pitch must not appear anywhere in the
        rendered widget text (static strings + map_stems.py prose)."""
        import re
        text = self._full_text()
        self.assertNotRegex(text, r"(?i)\bDemucs\b",
                            "Demucs tool name must not appear in rendered text")
        self.assertNotRegex(text, r"(?i)\bhtdemucs\b",
                            "htdemucs model name must not appear in rendered text")
        self.assertNotIn("htdemucs_6s", text,
                         "htdemucs_6s must not appear in rendered text")
        self.assertNotIn("basic-pitch", text,
                         "basic-pitch tool name must not appear in rendered text")

    def test_no_raw_stem_in_omitted_note(self):
        """Omitted stems (vocals, piano) must not show raw names; note names them identified."""
        text = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "var e=document.getElementById('omittedNote');"
            "return e?e.textContent.toLowerCase():'';})()",
            width=1100, height=3200,
        )
        self.assertNotIn("vocals", text,
                         "raw 'vocals' must not appear in the omitted note")
        self.assertNotIn("piano", text,
                         "raw 'piano' must not appear in the omitted note")
        # s46: the note now names stems by identified label (INV-STEMNAME-NEARSILENT-ID):
        # "stems low 1 (near-silent), low 2 (near-silent) omitted — too little material to read"
        # Check that: (a) "(near-silent)" appears (identified labels), (b) reason is given.
        self.assertIn("(near-silent)", text,
                      "omitted note must show identified near-silent labels; got: " + repr(text))
        self.assertTrue("omitted" in text or "too little" in text or "material" in text,
                        "omitted note must explain WHY they are absent; got: " + repr(text))

    def test_no_raw_stem_as_rhythm_tile_heading(self):
        """Rhythm panel tile headings must use display names, not raw 'other'."""
        text = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var el=document.getElementById('rhyRows');"
            "return el?el.textContent.toLowerCase():'';})()",
            width=1100, height=3400,
        )
        # textContent concatenates child text without structural newlines.
        # 'drums' and 'bass' are valid display names (trusted by identity).
        # 'other' as a tile heading must be gone (mapped to character label).
        self.assertNotIn("other", text,
                         "'other' must not appear as a rhythm tile heading (use the character label)")

    def test_no_raw_stem_in_leakage_pairs(self):
        """Leakage pairs must show display names, not 'other ↔ bass'."""
        text = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var el=document.getElementById('rhySep');"
            "return el?el.textContent.toLowerCase():'';})()",
            width=1100, height=3400,
        )
        # The leakage pair was 'bass ↔ other' — after fix it uses display names.
        # 'other' should not appear in the '↔' context (it may appear in other prose,
        # so we check the specific leaking phrase pattern).
        self.assertNotIn("other ↔", text,
                         "raw 'other ↔' must not appear in leakage pairs")
        self.assertNotIn("↔ other", text,
                         "raw '↔ other' must not appear in leakage pairs")

    def test_no_raw_stem_in_notes_title(self):
        """Notes panel title must not show raw 'vocals' — must use display name."""
        text = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var e=document.getElementById('noteTitle');"
            "return e?e.textContent.toLowerCase():'';})()",
            width=1100, height=3400,
        )
        self.assertNotIn("vocals", text,
                         "raw 'vocals' must not appear in the notes panel title")

    def test_everything_else_not_the_rest_in_fam_display(self):
        """fam_display['other'] must read 'everything else', not 'the rest' in the stem↔project panel."""
        # INV-44 wording: the family bars in #mapPanel must use producer language.
        # (Other uses of "the rest" — recs_hint, tonal resonance card — are fine prose.)
        text = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var mp=document.getElementById('mapPanel');"
            "return mp?mp.innerText:'';})()",
            width=1100, height=3400,
        )
        self.assertNotIn("the rest", text,
                         "'the rest' (dev label) must not appear in #mapPanel; got: " + repr(text[:300]))
        self.assertIn("everything else", text,
                      "'everything else' must appear in #mapPanel for the fam_display 'other' family; got: " + repr(text[:300]))


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class NearSilentStemIdentified(unittest.TestCase):
    """INV-STEMNAME-NEARSILENT-ID (s46): near-silent stems carry an IDENTIFIED label
    (frequency-band word + '(near-silent)'), never the bare word 'near-silent'.
    CR-2 visibility: they appear as MUTED, LABELLED rows in the player lanes.
    No rhythm-tile entry for near-silent stems.
    These tests render a full widget with two near-silent stems."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_omitted_widget()

    def test_stem_display_has_identified_nearsilent_labels(self):
        """stem_display for omitted stems must carry '(near-silent)' qualifier, not bare 'near-silent'."""
        res = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "var disp=D.stem_display||{};"
            "var om=(D.stem&&D.stem.omitted)||[];"
            "return om.map(function(s){return {stem:s,label:disp[s]||null};});})()",
            width=1100, height=3200,
        )
        self.assertTrue(len(res) >= 2,
                        "fixture must have at least 2 omitted stems; got: " + repr(res))
        for entry in res:
            lbl = (entry.get("label") or "").lower()
            self.assertIn("(near-silent)", lbl,
                          f"stem '{entry['stem']}' label must contain '(near-silent)'; got: {repr(lbl)}")
            self.assertNotEqual(lbl, "near-silent",
                                f"bare 'near-silent' must not be the label for '{entry['stem']}'")

    def test_nearsilent_labels_are_distinct(self):
        """No two near-silent stems in the same widget may have the same display label."""
        res = hc.probe(
            self.widget,
            "(function(){"
            "var disp=D.stem_display||{};"
            "var om=(D.stem&&D.stem.omitted)||[];"
            "return om.map(function(s){return disp[s]||'';});})()",
            width=1100, height=3200,
        )
        self.assertEqual(len(res), len(set(res)),
                         "near-silent labels must be distinct; got: " + repr(res))

    def test_nearsilent_stems_appear_as_muted_lanes(self):
        """Near-silent stems must be VISIBLE (not filtered out) in the player lane grid, rendered muted.

        Checks canvas height: with 6 stems (4 significant + 2 near-silent, laneH=30px, gap=5px)
        the #stemlanes canvas is taller than with 4 significant stems only. Minimum with 6 stems
        and LPT=4, LPB=18: 4 + 6*35 - 5 + 18 = 227 px. With 4 only: 4 + 4*35 - 5 + 18 = 157 px.
        Also checks via window.__ns_state that near-silent stems start muted (exposed by the code)."""
        res = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "var om=(D.stem&&D.stem.omitted)||[];"
            "var lcv=document.getElementById('stemlanes');"
            "var lh=lcv?lcv.offsetHeight:0;"
            # window.__ns_state exposed by build_widget.py after the fix: {name, mute} per stem
            "var ns=window.__ns_state||null;"
            "return {canvas_h:lh,omitted:om,ns_state:ns};})()",
            width=1100, height=3200,
        )
        self.assertGreater(res.get("canvas_h", 0), 200,
                           "#stemlanes canvas must be tall enough for 6 lanes (≥200 px with near-silent visible); "
                           f"got {res.get('canvas_h')} — near-silent stems may still be filtered out")
        ns_state = res.get("ns_state")
        if ns_state:  # exposed by the fixed code; absent in old code (test passes canvas check instead)
            om = set(res.get("omitted", []))
            for entry in ns_state:
                if entry["name"] in om:
                    self.assertTrue(entry.get("mute"),
                                    f"near-silent stem '{entry['name']}' must start muted; ns_state={ns_state}")

    def test_nearsilent_stems_not_in_rhythm_tiles(self):
        """Near-silent stems must NOT appear in rhythm tiles (no pulse in silence)."""
        res = hc.probe(
            self.widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var om=(D.stem&&D.stem.omitted)||[];"
            "var rhy=document.querySelectorAll('.rhy-tile .z');"
            "var rhyNames=Array.prototype.map.call(rhy,function(e){return e.textContent.toLowerCase();});"
            "var disp=D.stem_display||{};"
            "var omDisp=om.map(function(s){return (disp[s]||'').toLowerCase()});"
            "return {rhy_names:rhyNames,omitted_labels:omDisp};})()",
            width=1100, height=3400,
        )
        rhy_names = set(res.get("rhy_names", []))
        for lbl in res.get("omitted_labels", []):
            if lbl:
                self.assertNotIn(lbl, rhy_names,
                                 f"near-silent stem label '{lbl}' must not appear in rhythm tiles")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class WordingInvariants(unittest.TestCase):
    """INV-44 wording: play_note no nested parens; reference bars carry 'lower · them · higher'."""

    @classmethod
    def setUpClass(cls):
        cls.stem_widget = _build_rich_widget(with_stems=True)  # needs audio for the player to render
        cls.ref_widget = _build_ref_widget()

    def test_play_note_no_nested_parens(self):
        """play_note intro must not have nested parentheses: '))'  signals a closing double-close."""
        text = hc.probe(
            self.stem_widget,
            "(function(){"
            "var e=document.getElementById('playNote');"
            "return e?e.textContent:'';})()",
            width=1100, height=2400,
        )
        self.assertTrue(len(text) > 10,
                        "play_note must render with a stem widget (fixture check); got: " + repr(text))
        self.assertNotIn("))", text,
                         "play_note must not have nested parentheses — '))'  found; got: " + repr(text[:300]))

    def test_reference_bars_have_axis_labels(self):
        """Reference bars must carry a '.refread-axis' element with 'lower' and 'higher'."""
        res = hc.probe(
            self.ref_widget,
            "(function(){"
            "document.body.classList.remove('simple');"
            "document.querySelectorAll('details').forEach(function(d){d.open=true;});"
            "var el=document.querySelector('.refread-axis');"
            "return el?el.textContent:null;})()",
            width=1100, height=3600,
        )
        self.assertIsNotNone(res,
                             "reference bars must have a .refread-axis element (axis orientation label)")
        self.assertIn("lower", (res or "").lower(),
                      "refread-axis must contain 'lower'; got: " + repr(res))
        self.assertIn("higher", (res or "").lower(),
                      "refread-axis must contain 'higher'; got: " + repr(res))


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class WebPanelReadableLayout(unittest.TestCase):
    """D-INV-29 approved layout (2026-07-04, variant A + visible sources).

    The shipped #webPanel must:
    (a) render glyph-led confirmed rows (★/☆ as leading glyph, not a trailing pill) — asserted
        by checking the glyph appears BEFORE the trait text in the rendered HTML of a confirmed row;
    (b) NOT render per-row 'WEB SAYS' pills — the old repeated grey pills that D-INV-29 forbids;
        all web-only traits collapse into ONE muted group, not N pills;
    (c) show the sources block with ≥1 <a href> link (2026-07-04 amendment: keep visible);
    (d) show one footnote legend line explaining ★/☆/·.

    Uses _build_ref_widget() which loads bundled reference_web_notes.json (DeepChord as nearest
    direction — has both direct and web-only traits, and 4 source links).
    """

    @classmethod
    def setUpClass(cls):
        if not _HAVE_CHROME:
            raise unittest.SkipTest("headless Chrome not available")
        cls.widget = _build_ref_widget()

    def _open_webpanel_js(self, body_js):
        """Wrap JS to open #webPanel and remove simple class before running body_js."""
        return (
            "(function(){"
            "document.body.classList.remove('simple');"
            "var wp=document.querySelector('#webPanel');"
            "if(wp)wp.open=true;"
            + body_js +
            "})()"
        )

    def test_confirmed_trait_rows_lead_with_glyph(self):
        """Confirmed-trait rows must use a leading glyph (★/☆), not a trailing pill.
        We assert: a .rn-trait-glyph element exists with ★ or ☆ text (new layout),
        AND the old trailing pill class 'tc-rn-pill is-direct' does NOT appear
        (the pill-per-row pattern that D-INV-29 forbids)."""
        r = hc.probe(
            self.widget,
            self._open_webpanel_js(
                "var wp=document.querySelector('#webPanel');"
                "var glyphEls=wp?wp.querySelectorAll('.rn-trait-glyph'):[];"
                "var glyphCount=0;"
                "glyphEls.forEach(function(e){var t=e.textContent.trim();"
                "if(t==='★'||t==='☆')glyphCount++;});"
                "var html=wp?wp.innerHTML:'';"
                "var hasPill=html.indexOf('tc-rn-pill is-direct')>=0||"
                "html.indexOf('tc-rn-pill is-indirect')>=0;"
                "return {glyph_count:glyphCount,has_old_pill:hasPill};"
            ),
            width=1100, height=3600,
        )
        self.assertGreater(r["glyph_count"], 0,
                           "#webPanel must have .rn-trait-glyph elements with ★/☆ "
                           "(confirmed trait rows must lead with a glyph — variant A layout)")
        self.assertFalse(r["has_old_pill"],
                         "#webPanel must NOT contain the old 'tc-rn-pill is-direct/is-indirect' "
                         "trailing pills — D-INV-29 forbids per-row pill labels")

    def test_no_per_row_webonly_pill(self):
        """Web-only traits must NOT render as individual per-row pills.
        The old layout had N 'WEB SAYS' pills (one per web-only trait) — D-INV-29 forbids this.
        The new layout collapses all web-only traits into ONE muted group with dot-separated text."""
        r = hc.probe(
            self.widget,
            self._open_webpanel_js(
                "var wp=document.querySelector('#webPanel');"
                "var html=wp?wp.innerHTML:'';"
                "var hasWebonlyPill=html.indexOf('tc-rn-pill is-webonly')>=0||"
                "html.indexOf('tc-rn-pill is-na')>=0;"
                "return {has_webonly_pill:hasWebonlyPill};"
            ),
            width=1100, height=3600,
        )
        self.assertFalse(r["has_webonly_pill"],
                         "#webPanel must NOT contain per-row 'tc-rn-pill is-webonly/is-na' pills "
                         "— D-INV-29: web-only traits collapse into ONE muted group, not N pills")

    def test_sources_block_has_links(self):
        """Sources block must be VISIBLE at the panel bottom with ≥1 <a href> link.
        2026-07-04 amendment: the v2 mockup dropped the sources block; the call: keep it."""
        r = hc.probe(
            self.widget,
            self._open_webpanel_js(
                "var wp=document.querySelector('#webPanel');"
                "var links=wp?wp.querySelectorAll('a[href]'):[];"
                "var count=0;"
                "links.forEach(function(e){"
                "if(e.offsetHeight>0&&getComputedStyle(e).display!=='none')count++;});"
                "return {visible_link_count:count};"
            ),
            width=1100, height=3600,
        )
        self.assertGreater(r["visible_link_count"], 0,
                           "#webPanel must have ≥1 visible <a href> source link "
                           "(2026-07-04 amendment: sources block stays visible)")

    def test_footnote_legend_present(self):
        """One footnote legend must appear in #webPanel explaining ★/☆/·.
        Assert a .rn-footnote element exists with visible text containing ★."""
        r = hc.probe(
            self.widget,
            self._open_webpanel_js(
                "var wp=document.querySelector('#webPanel');"
                "var fn=wp?wp.querySelector('.rn-footnote'):null;"
                "var text=fn?fn.textContent:'';"
                "var visible=fn?(fn.offsetHeight>0&&getComputedStyle(fn).display!=='none'):false;"
                "return {text:text,visible:visible};"
            ),
            width=1100, height=3600,
        )
        self.assertTrue(r["visible"],
                        "#webPanel must contain a visible .rn-footnote element "
                        "(one footnote legend explaining ★/☆/·)")
        self.assertIn("★", r["text"],
                      ".rn-footnote must contain '★' in its text; got: " + repr(r["text"][:200]))

    def test_s57_section_headings_not_dimmer_than_body_and_sources_are_links(self):
        """s57 (2026-07-05): (a) a section heading is NEVER dimmer than the body it
        heads — the `.rn-section-label` / `.tc-rn-sources-label` computed luminance must be ≥ the
        body (`.tc-rn-blurb` / `.rn-trait-row`) luminance (was `--muted` under `--ink` body — a
        brightness inversion). (b) Each source reads as a LINK: `.tc-rn-sources a` carries an
        underline AND a leading chain-link icon (inline svg.tc-rn-link-ico, the conventional
        link glyph — replaced the ↗ arrow per 2026-07-05)."""
        r = hc.probe(
            self.widget,
            self._open_webpanel_js(
                "function lum(c){var m=(c||'').match(/(\\d+),\\s*(\\d+),\\s*(\\d+)/);"
                "if(!m)return -1;return 0.2126*+m[1]+0.7152*+m[2]+0.0722*+m[3];}"
                "var wp=document.querySelector('#webPanel');"
                "var lbl=wp?wp.querySelector('.rn-section-label'):null;"
                "var slbl=wp?wp.querySelector('.tc-rn-sources-label'):null;"
                "var body=wp?(wp.querySelector('.tc-rn-blurb')||wp.querySelector('.rn-trait-row')):null;"
                "var a=wp?wp.querySelector('.tc-rn-sources a'):null;"
                "return {"
                "label_lum: lbl?lum(getComputedStyle(lbl).color):null,"
                "sources_label_lum: slbl?lum(getComputedStyle(slbl).color):null,"
                "body_lum: body?lum(getComputedStyle(body).color):null,"
                "src_underline: a?getComputedStyle(a).textDecorationLine:null,"
                "src_icon: a?(a.querySelector('svg.tc-rn-link-ico')?'chain':null):null};"
            ),
            width=1100, height=3600,
        )
        self.assertIsNotNone(r["label_lum"], "fixture must render a .rn-section-label")
        self.assertIsNotNone(r["body_lum"], "fixture must render web-panel body text")
        self.assertGreaterEqual(
            r["label_lum"], r["body_lum"] - 1,
            f"a section heading must not be dimmer than its body (label lum {r['label_lum']} "
            f"< body lum {r['body_lum']}) — s57 brightness-hierarchy fix")
        if r["sources_label_lum"] is not None:
            self.assertGreaterEqual(
                r["sources_label_lum"], r["body_lum"] - 1,
                "the Sources heading must not be dimmer than the body either")
        self.assertIsNotNone(r["src_underline"], "fixture must render a .tc-rn-sources link")
        self.assertIn("underline", r["src_underline"],
                      f"source links must be underlined (read as links); got {r['src_underline']}")
        self.assertEqual(r["src_icon"], "chain",
                         "each source link must carry a leading chain-link icon "
                         f"(inline svg.tc-rn-link-ico); got {r['src_icon']!r}")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class PanelGapHierarchy(unittest.TestCase):
    """DS-INV-9 panel-rhythm slice (2026-07-05 review): the gap BETWEEN top-level
    panels (--rhythm) must be strictly LARGER than the gap between the sub-panels nested inside
    #evidence (--gap). This fixes the earlier INVERSION (measured 24px inter < 30px intra — the
    reverse of correct hierarchy). Measured with real getBoundingClientRect, invisible to string
    tests. Robust to WHICH panels render: it takes the first two top-level `.wrap > details.tc-panel`
    and the first two `#evidence > details.tc-panel` sub-panels."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_rich_widget(with_stems=True)

    def test_inter_panel_gap_exceeds_intra_panel_gap(self):
        r = hc.probe(
            self.widget,
            "(function(){document.body.classList.remove('simple');"
            # open #evidence so its nested sub-panels have layout to measure
            "var ev=document.querySelector('#evidence');if(ev)ev.open=true;"
            "function gap(list){if(list.length<2)return null;"
            "return list[1].getBoundingClientRect().top-list[0].getBoundingClientRect().bottom;}"
            "var wrap=document.querySelector('.wrap')||document.body;"
            "var tops=Array.prototype.filter.call(wrap.children,"
            "function(e){return e.matches&&e.matches('details.tc-panel');});"
            "var subs=document.querySelectorAll('#evidence > details.tc-panel');"
            "return {inter:gap(tops),intra:gap(Array.prototype.slice.call(subs))};})()",
            width=1100, height=4200,
        )
        self.assertIsNotNone(r["inter"], "fixture must render ≥2 top-level .tc-panel sections")
        self.assertIsNotNone(r["intra"], "fixture must render ≥2 sub-panels inside #evidence")
        self.assertGreater(
            r["inter"], r["intra"] + 4,
            f"inter-panel gap (--rhythm, {r['inter']}px) must be clearly larger than the intra-panel "
            f"gap (--gap, {r['intra']}px) — DS-INV-9 hierarchy; was inverted (24<30) before the s57 fix")



@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class DesignTokenColourRendered(unittest.TestCase):
    """Browser-level proof of the SEMANTIC COLOUR tokens (SPEC §I, DS-INV-2/3).

    The 9 tests in test_design_tokens.py assert the tokens are DEFINED and that their
    values match the catalog palette — but only as text in build_widget.TEMPLATE.
    Nothing verified that a real browser RESOLVES --good/--warn/--bad at :root and
    delivers them through the cascade to the elements that wear them. A malformed
    :root, a specificity conflict, or a token indirection would pass every string
    test and still ship a colourless (or wrong-coloured) MEANING to the eye — the
    exact class the s34 overhaul targets, extended from visibility to COLOUR. Node
    N16 (design tokens) was the weakest in the s52 coverage inventory: 9 tests, ALL
    STRING, no computed-colour proof anywhere (data/test_coverage_inventory_s52.md).

    Level: L3-BROWSER (the level a colour fact requires). The rgb values below are the
    computed render of the §I :root hexes (--good #46d39a / --warn #ffb454 / --bad
    #ff6b6b), verified by probe s52.
    """

    _GOOD_HEX, _GOOD_RGB = "#46d39a", "rgb(70, 211, 154)"
    _WARN_HEX = "#ffb454"
    _BAD_HEX = "#ff6b6b"

    @classmethod
    def setUpClass(cls):
        cls.full_widget = _build_rich_widget(with_stems=True)  # carries .modebadge.full
        cls.ref_widget = _build_ref_widget()                   # carries #webPanel + a ★ glyph

    def test_semantic_tokens_resolve_at_root_in_browser(self):
        """--good/--warn/--bad must RESOLVE at :root AT RUNTIME, not merely exist in the
        CSS text. Negative side (INV-6): a dropped token resolves to '' — that is the
        failure a string test cannot see."""
        js = ('({good:getComputedStyle(document.documentElement).getPropertyValue("--good").trim(),'
              'warn:getComputedStyle(document.documentElement).getPropertyValue("--warn").trim(),'
              'bad:getComputedStyle(document.documentElement).getPropertyValue("--bad").trim()})')
        r = hc.probe(self.full_widget, js, width=1200, height=3000)
        self.assertEqual(r["good"], self._GOOD_HEX, "--good must resolve at :root in the browser (not '')")
        self.assertEqual(r["warn"], self._WARN_HEX, "--warn must resolve at :root in the browser (not '')")
        self.assertEqual(r["bad"], self._BAD_HEX, "--bad must resolve at :root in the browser (not '')")

    def test_full_mode_badge_computes_good_green(self):
        """The 'full analysis' badge (.modebadge.full) wears color:var(--good). Assert the
        browser COMPUTES that green through the cascade — not that a hex sits in the text.
        Negative side (INV-6): it must NOT fall back to default black, the failure mode when
        the token drops and the label silently loses its meaning-colour."""
        js = ('(function(){var e=document.querySelector(".modebadge.full");'
              'return {present:!!e,color:e?getComputedStyle(e).color:null};})()')
        r = hc.probe(self.full_widget, js, width=1200, height=3000)
        self.assertTrue(r["present"], "the full widget must render a .modebadge.full to test the token")
        self.assertEqual(r["color"], self._GOOD_RGB,
                         "the full-mode badge must render in --good green (real computed colour)")
        self.assertNotEqual(r["color"], "rgb(0, 0, 0)",
                            "the badge colour must not fall back to default black (token dropped)")

    def test_confirmed_web_panel_glyph_computes_good_green(self):
        """The ★ confirmed-trait glyph in the web panel (#webPanel .rn-trait-glyph — the
        surface reworked in 0.9.32) wears color:var(--good). Browser proof the readable
        layout the eye just approved stays green under the real cascade."""
        js = ('(function(){var e=document.querySelector("#webPanel .rn-trait-glyph");'
              'return {present:!!e,color:e?getComputedStyle(e).color:null};})()')
        r = hc.probe(self.ref_widget, js, width=1200, height=3000)
        self.assertTrue(r["present"], "the ref fixture must render a confirmed-trait ★ glyph to test")
        self.assertEqual(r["color"], self._GOOD_RGB,
                         "the confirmed ★ glyph must render in --good green (real computed colour)")


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class CatalogSemanticColourRendered(unittest.TestCase):
    """Browser-level proof of the CATALOG semantic-colour cells (§D.10 / §F, D-INV-22 /
    F-INV-1). The 6 hex-in-HTML tests in test_catalog_columns.py assert the direction /
    sibling colour appears as TEXT in render_catalog_html output — but nothing verified a
    real browser RESOLVES those inline `style="color:#…"` values and delivers them through
    the cascade to the anchor the eye reads. The colour IS the meaning here: a close match
    reads green, a mid match amber, a far sibling red. A malformed style attr, an anchor
    default-colour override, or a link-colour reset would pass every hex string test and
    still ship a colourless (or blue-link) meaning to the eye — the exact s34 class,
    extended from visibility to the catalog's colour. This is the B2-remainder gap left
    open after N16 closed the widget tokens (data/test_rework_s52.md, close-order item 2).

    Level: L3-BROWSER (a colour fact's required level). The rgb values are the computed
    render of the §D palette hexes (close #2e9e5b / mid #d8932a / far #c2503d).
    """

    _CLOSE_HEX, _CLOSE_RGB = "#2e9e5b", "rgb(46, 158, 91)"
    _MID_HEX, _MID_RGB = "#d8932a", "rgb(216, 147, 42)"
    _FAR_HEX, _FAR_RGB = "#c2503d", "rgb(194, 80, 61)"

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import catalog  # noqa: E402
        import similarity_columns as S  # noqa: E402

        def _e(track, **kw):
            e = {"track": track, "audio_sha": f"sha_{track}", "stamp": "2026-06-20_2100",
                 "audio_mtime": 1000, "widget": f"{track}.html", "mode": "full",
                 "bpm": 123, "arc": [0.1, 0.5, 1.0], "title": track,
                 "_leans": [], "_siblings": []}
            e.update(kw)
            return e

        # Track A carries a CLOSE lean (green) + a MID lean (amber) and a FAR sibling to B (red,
        # allowed per F-INV-1). Track B exists so the sibling chip resolves a title/href.
        leans = [S.Lean(direction="DeepChord", level=S.CLOSE, runner=None, n_shared=13),
                 S.Lean(direction="SCSI-9",    level=S.MID,   runner=None, n_shared=11)]
        sibs = [S.Sibling(track="Bravo", level=S.FAR, n_shared=6)]
        entries = [_e("Alpha", _leans=leans, _siblings=sibs), _e("Bravo")]
        tmp = Path(tempfile.mkdtemp(prefix="tc_catcol_"))
        out = tmp / "index.html"
        out.write_text(catalog.render_catalog_html(entries))
        cls.widget = str(out)

    def _colours(self, selector):
        """Computed color of every element matching selector, in document order."""
        js = ("(function(){return Array.prototype.map.call("
              "document.querySelectorAll('" + selector + "'),"
              "function(e){return getComputedStyle(e).color;});})()")
        return hc.probe(self.widget, js, width=1500, height=1200)

    def test_close_lean_computes_green(self):
        """The nearest direction (.sim-dir, CLOSE) must COMPUTE green through the cascade —
        not merely carry the hex in the style text. Negative side: it must not fall back to
        the default anchor blue (rgb(0,0,238)) — the failure a hex string test cannot see."""
        cols = self._colours(".sim-dir")
        self.assertGreaterEqual(len(cols), 1, "the catalog must render at least one .sim-dir direction")
        self.assertEqual(cols[0], self._CLOSE_RGB,
                         "the closest direction must render in close-green (real computed colour)")
        self.assertNotEqual(cols[0], "rgb(0, 0, 238)",
                            "the direction colour must not fall back to default anchor blue")

    def test_mid_lean_computes_amber(self):
        """The second direction (MID) must compute amber — proves the per-level colour map
        survives the cascade for more than the first cell."""
        cols = self._colours(".sim-dir")
        self.assertGreaterEqual(len(cols), 2, "track Alpha must render both its leans (close + mid)")
        self.assertEqual(cols[1], self._MID_RGB,
                         "the second (mid) direction must render in amber (real computed colour)")

    def test_far_sibling_computes_red(self):
        """A FAR sibling chip (.sib-chip) is allowed (F-INV-1) and reads red. Assert the
        browser computes that red — the colour that tells the eye 'last-resort match'."""
        cols = self._colours(".sib-chip")
        self.assertGreaterEqual(len(cols), 1, "the catalog must render the sibling chip")
        self.assertEqual(cols[0], self._FAR_RGB,
                         "the far sibling chip must render in far-red (real computed colour)")
        self.assertNotEqual(cols[0], "rgb(0, 0, 238)",
                            "the sibling colour must not fall back to default anchor blue")


# ── D-INV-36 — the merged reference panel (Q5, 2026-07-05) ──────────────────────

def _merged_ref_page(directions, web_notes, tmp_prefix="tc_merged_", lead_px=0):
    """Render render_reference_read() output into a standalone page for the harness.

    Pure-function fixture: synthetic directions/web_notes, identity norm, track at the
    origin — no run_dir, no real data files, so each test controls exactly which
    directions qualify and which carry web content.

    lead_px: height of a filler block ABOVE the panel — gives the page scroll room so
    the D-INV-37 entry-focus scroll ('panel into view') is measurable, mirroring the
    real widget where #refPanel sits far down the page."""
    import fingerprints as FP
    track = {ax: 0.0 for ax in FP.AXES}
    norm = {"mu": {ax: 0.0 for ax in FP.AXES}, "sd": {ax: 1.0 for ax in FP.AXES}}
    html = build_widget.render_reference_read(track, directions, norm, web_notes=web_notes)
    lead = f"<div style='height:{lead_px}px'></div>" if lead_px else ""
    tmp = Path(tempfile.mkdtemp(prefix=tmp_prefix))
    out = tmp / "page.html"
    out.write_text(
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        f"<body>{lead}{html}</body></html>", encoding="utf-8")
    return str(out)


def _three_close_dirs():
    """Three directions that all qualify as leans for a track at the origin (small,
    distinct offsets on different axes), nearest-first = Alpha, Beta, Gamma."""
    import fingerprints as FP
    def z(**over):
        d = {ax: 0.0 for ax in FP.AXES}
        d.update(over)
        return d
    return {"Alpha": z(tempo=0.2), "Beta": z(dynamics=0.35), "Gamma": z(brightness=0.5)}


def _web_note(artist):
    return {
        "artist": artist,
        "genre_era": f"{artist} — test genre, test era",
        "blurb": f"What the web says about {artist}: a distinctive test sound.",
        "traits": [
            {"phrase": f"{artist} wide pads", "axis": "stereo_width", "tier": "direct",
             "expect": "high"},
            {"phrase": f"{artist} dubby depths", "axis": None, "tier": "none"},
        ],
        "sources": [{"label": f"{artist} source", "url": "https://example.com"}],
    }


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class MergedReferencePanel(unittest.TestCase):
    """D-INV-36 — ONE reference panel: shared selector, two nested open disclosures,
    web notes follow the selector and exist for every shown direction (SPEC §D.10.1/.2,
    the Q5 merge, 2026-07-05). Written RED against the pre-merge render
    (two top-level panels; web stuck on the top match; the forbidden empty-state copy)."""

    @classmethod
    def setUpClass(cls):
        dirs = _three_close_dirs()
        notes = {n: _web_note(n) for n in dirs}
        cls.page = _merged_ref_page(dirs, notes)
        # Fixture guard: all three directions must actually qualify, else the selector
        # tests pass vacuously.
        import fingerprints as FP
        import similarity_columns as SC
        track = {ax: 0.0 for ax in FP.AXES}
        leans = SC.leans_toward_topk(track, dirs)
        assert len(leans) == 3, f"fixture must yield 3 qualifying directions, got {len(leans)}"

    def test_one_container_selector_and_two_nested_open_disclosures(self):
        """(a) #refPanel is the ONE container: selector at the top, then the centroid
        disclosure (#refRead), then the web disclosure (#webPanel) — both nested, both open."""
        r = hc.probe(self.page,
            "(function(){"
            "var c=document.getElementById('refPanel');"
            "if(!c)return {container:false};"
            "var rr=document.getElementById('refRead'),wp=document.getElementById('webPanel');"
            "return {container:true,cOpen:c.open===true,"
            "cTitle:(c.querySelector('summary')||{}).textContent||'',"
            "rrNested:!!rr&&c.contains(rr),wpNested:!!wp&&c.contains(wp),"
            "rrOpen:!!rr&&rr.open===true,wpOpen:!!wp&&wp.open===true,"
            "rrBeforeWp:!!(rr&&wp)&&!!(rr.compareDocumentPosition(wp)&Node.DOCUMENT_POSITION_FOLLOWING),"
            "tabsInContainer:c.querySelectorAll('.reftab').length,"
            "tabsBeforeRr:(function(){var t=c.querySelector('.reftabs');"
            "return !!(t&&rr)&&!!(t.compareDocumentPosition(rr)&Node.DOCUMENT_POSITION_FOLLOWING);})()"
            "};})()", width=1100, height=2400)
        self.assertTrue(r.get("container"),
                        "MERGE: #refPanel container not found — the two reference panels must "
                        "merge into ONE (D-INV-36a)")
        self.assertTrue(r.get("cOpen"), "#refPanel must be open by default")
        self.assertIn("You vs your closest match", r.get("cTitle", ""),
                      "the container keeps the established title")
        self.assertTrue(r.get("rrNested"), "#refRead must be NESTED inside #refPanel")
        self.assertTrue(r.get("wpNested"), "#webPanel must be NESTED inside #refPanel")
        self.assertTrue(r.get("rrOpen"), "the centroid disclosure must be open by default")
        self.assertTrue(r.get("wpOpen"), "the web disclosure must be open by default (nested-open, "
                                         "supersedes the standalone-collapsed panel)")
        self.assertTrue(r.get("rrBeforeWp"), "centroid read must precede web notes (D-INV-30)")
        self.assertEqual(r.get("tabsInContainer"), 3,
                         "the shared selector (3 qualifying directions = 3 tabs) must sit in the "
                         "container, above both disclosures")
        self.assertTrue(r.get("tabsBeforeRr"), "the selector must precede the first disclosure")

    def test_tab_switch_retargets_both_bars_and_web(self):
        """(b) Clicking a tab re-targets BOTH disclosures — bars AND web body + summary.
        The pre-merge defect: bars switch, web notes stay on the top match."""
        r = hc.probe(self.page,
            "(function(){"
            "var tabs=document.querySelectorAll('.reftab');"
            "if(tabs.length<2)return {tabs:tabs.length};"
            "tabs[1].click();"
            "function visIdx(sel){var v=[];document.querySelectorAll(sel).forEach(function(p){"
            "if(getComputedStyle(p).display!=='none')v.push(p.dataset.didx);});return v;}"
            "var wp=document.getElementById('webPanel');"
            "return {tabs:tabs.length,"
            "barsVisible:visIdx('.refpanel'),"
            "webVisible:visIdx('.webdir'),"
            "webSummary:wp?(wp.querySelector('summary')||{}).textContent||'':''"
            "};})()", width=1100, height=2400)
        self.assertGreaterEqual(r.get("tabs", 0), 2, "fixture must render ≥2 tabs")
        self.assertEqual(r.get("barsVisible"), ["1"],
                         "after clicking tab 2, ONLY that direction's bars are visible")
        self.assertEqual(r.get("webVisible"), ["1"],
                         "after clicking tab 2, the web disclosure must show THAT direction's "
                         "body — not stay on the top match (the Q5 defect, D-INV-36b)")
        self.assertIn("Beta", r.get("webSummary", ""),
                      "the web disclosure summary must follow the selector (artist name)")

    def test_all_shown_directions_have_embedded_web_bodies(self):
        """(c) The build embeds a web body for EVERY shown direction, not only the nearest."""
        r = hc.probe(self.page,
            "(function(){var v=[];document.querySelectorAll('.webdir').forEach(function(p){"
            "v.push(p.dataset.didx);});"
            "return {bodies:v,tabs:document.querySelectorAll('.reftab').length};})()",
            width=1100, height=2400)
        self.assertEqual(r.get("bodies"), ["0", "1", "2"],
                         "all 3 shown directions must carry an embedded web body "
                         "(pre-merge: only the top match, D-INV-36c)")

    def test_direction_without_web_content_hides_web_disclosure(self):
        """(d) A focused direction with NO web content hides the web disclosure entirely
        (never an empty-open box, INV-47 composed); switching back restores it."""
        dirs = _three_close_dirs()
        notes = {"Alpha": _web_note("Alpha"), "Gamma": _web_note("Gamma")}   # Beta: none
        page = _merged_ref_page(dirs, notes, tmp_prefix="tc_merged_gap_")
        js = (
            "(function(){"
            "var tabs=document.querySelectorAll('.reftab');"
            "var wp=document.getElementById('webPanel');"
            "function wpVisible(){return !!wp&&wp.offsetParent!==null&&wp.offsetHeight>0;}"
            "var out={tabs:tabs.length,initial:wpVisible()};"
            "if(tabs.length>=2){tabs[1].click();out.onGap=wpVisible();"
            "tabs[0].click();out.back=wpVisible();}"
            "return out;})()"
        )
        r = hc.probe(page, js, width=1100, height=2400)
        self.assertGreaterEqual(r.get("tabs", 0), 2, "fixture must render ≥2 tabs")
        self.assertTrue(r.get("initial"), "web disclosure visible for a direction WITH content")
        self.assertFalse(r.get("onGap"),
                         "focusing a direction with NO web content must HIDE the web disclosure "
                         "(absent, never empty-open — D-INV-36d)")
        self.assertTrue(r.get("back"), "switching back must restore the web disclosure")

    def test_empty_state_says_no_close_direction_yet(self):
        """(e) Directions defined but none close ⇒ the NON-expandable stub plaque with the
        one-line 'no close direction yet' prose — never the §F siblings phrase 'No similar
        tracks' (pre-merge bug), and never anything to open (2026-07-05)."""
        import fingerprints as FP
        def z(**over):
            d = {ax: 0.0 for ax in FP.AXES}
            d.update(over)
            return d
        far = {"x": z(tempo=9.0), "y": z(dynamics=9.0)}
        page = _merged_ref_page(far, {}, tmp_prefix="tc_merged_far_")
        r = hc.probe(page,
            "(function(){var c=document.getElementById('refPanel');"
            "return {container:!!c,text:c?(c.innerText||''):'',"
            "tag:c?c.tagName:'',"
            "summaries:c?c.querySelectorAll('summary').length:0,"
            "tabs:document.querySelectorAll('.reftab').length,"
            "nested:c?c.querySelectorAll('details').length:0};})()",
            width=1100, height=1200)
        self.assertTrue(r.get("container"), "the empty state still renders #refPanel")
        self.assertIn("no close direction yet", r.get("text", "").lower(),
                      "the empty state must read 'no close direction yet' (SPEC §D.10.1)")
        self.assertNotIn("no similar tracks", r.get("text", "").lower(),
                         "the §F siblings phrase must NEVER appear on this surface (D-INV-22 "
                         "vocabulary — the pre-merge bug)")
        self.assertEqual(r.get("tag"), "DIV",
                         "the empty state is a NON-expandable stub — a plain div, never a "
                         "<details> (D-INV-36e, 2026-07-05)")
        self.assertEqual(r.get("summaries"), 0, "the stub has no summary — nothing to click open")
        self.assertEqual(r.get("tabs"), 0, "the empty state renders no tabs")
        self.assertEqual(r.get("nested"), 0, "the empty state renders no nested disclosures")

    def test_missing_fingerprint_renders_no_comparison_data_stub(self):
        """(e) Directions defined but the run carries NO fingerprint (an old or partial full
        run) ⇒ the same NON-expandable stub with the 'no comparison data in this run' note —
        never a silently absent panel (D-INV-36e, 2026-07-05: the vanished panel
        read as a hole in the page)."""
        data_dir = Path(build_widget.__file__).resolve().parent.parent / "data"
        if not (data_dir / "reference_directions.json").exists():
            self.skipTest("reference_directions.json absent — reference feature not set up")
        with tempfile.TemporaryDirectory(prefix="tc_nofp_run_") as td:
            stub = build_widget._ref_read_html(td)   # empty run dir → fingerprint is None
        tmp = Path(tempfile.mkdtemp(prefix="tc_nofp_page_"))
        page = tmp / "page.html"
        page.write_text("<!doctype html><html><head><meta charset='utf-8'></head>"
                        f"<body>{stub}</body></html>", encoding="utf-8")
        r = hc.probe(str(page),
            "(function(){var c=document.getElementById('refPanel');"
            "return {container:!!c,text:c?(c.innerText||''):'',"
            "tag:c?c.tagName:'',"
            "summaries:c?c.querySelectorAll('summary').length:0,"
            "nested:c?c.querySelectorAll('details').length:0};})()",
            width=1100, height=800)
        self.assertTrue(r.get("container"),
                        "no-fingerprint run must still render #refPanel (the stub)")
        self.assertIn("no comparison data in this run", r.get("text", "").lower(),
                      "the stub must say the run has no comparison data (D-INV-36e)")
        self.assertNotIn("no similar tracks", r.get("text", "").lower(),
                         "the §F siblings phrase must NEVER appear on this surface (D-INV-22)")
        self.assertEqual(r.get("tag"), "DIV", "the stub is a plain div — nothing to open")
        self.assertEqual(r.get("summaries"), 0, "the stub has no summary")
        self.assertEqual(r.get("nested"), 0, "the stub has no nested disclosures")


# ── D-INV-37 — URL entry-focus: catalog direction-link → widget opens on that tab ─────────

# Shared entry-state readback: active tab labels, visible bars/web indices, scroll
# geometry, the web summary, the view store, and the live URL search — everything the
# D-INV-37 reader row asserts.
_ENTRY_STATE_JS = (
    "(function(){var rp=document.getElementById('refPanel');"
    "var act=[];document.querySelectorAll('.reftab.active').forEach("
    "function(b){act.push(b.textContent.trim());});"
    "function visIdx(sel){var v=[];document.querySelectorAll(sel).forEach(function(p){"
    "if(getComputedStyle(p).display!=='none')v.push(p.dataset.didx);});return v;}"
    "var wp=document.getElementById('webPanel');"
    "return {active:act,bars:visIdx('.refpanel'),"
    "scrollY:Math.round(window.scrollY),"
    "rpTop:rp?Math.round(rp.getBoundingClientRect().top):null,"
    "vh:window.innerHeight,"
    "bodySimple:document.body.classList.contains('simple'),"
    "webSummary:wp?(wp.querySelector('summary')||{}).textContent||'':'',"
    "store:(function(){try{return localStorage.getItem('tc_view');}catch(e){return 'ERR';}})(),"
    "search:location.search,errors:TC.errors()};})()"
)


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class EntryFocus(unittest.TestCase):
    """D-INV-37 — the one-shot `?direction` entry reader (SPEC §D.10.1, wired s59).
    A catalog direction-link opens the widget with THAT direction's tab active and the
    reference panel scrolled into view; unknown names fall back to nearest (still
    scrolled); no param means the default state with NO scroll; entry never writes the
    view store, and tab clicks never touch the URL. Written RED against 1.1.0 (no
    reader: the param was inert, the page stayed at the top)."""

    LEAD = 1600  # px of filler above the panel — real widgets bury #refPanel this deep

    @classmethod
    def setUpClass(cls):
        # "Beta Prime" carries the URL-encoding case (a spaced name, EF-8).
        import fingerprints as FP
        def z(**over):
            d = {ax: 0.0 for ax in FP.AXES}
            d.update(over)
            return d
        cls.dirs = {"Alpha": z(tempo=0.2), "Beta Prime": z(dynamics=0.35),
                    "Gamma": z(brightness=0.5)}
        notes = {n: _web_note(n) for n in cls.dirs}
        cls.page = _merged_ref_page(cls.dirs, notes, tmp_prefix="tc_entry_",
                                    lead_px=cls.LEAD)

    def _probe(self, suffix):
        return hc.probe(self.page, _ENTRY_STATE_JS, width=1100, height=900,
                        url_suffix=suffix)

    def test_entry_param_focuses_named_tab_and_scrolls(self):
        """(a) `?direction=⟨2nd direction, URL-encoded⟩` ⇒ that tab active, bars + web
        body + web summary follow (the click path, D-INV-36b), panel scrolled into view."""
        r = self._probe("?direction=Beta%20Prime")
        self.assertEqual(r.get("active"), ["Beta Prime"],
                         "the named direction's tab must be ACTIVE on entry (D-INV-37)")
        self.assertEqual(r.get("bars"), ["1"],
                         "the named direction's bars must be the visible panel")
        self.assertIn("Beta Prime", r.get("webSummary", ""),
                      "the web summary must follow the entry focus (D-INV-36b path)")
        self.assertGreater(r.get("scrollY", 0), 0,
                           "entry must SCROLL the panel into view — the 1.1.0 defect: "
                           "the page stayed at the top and the focus was invisible")
        self.assertTrue(0 <= r.get("rpTop", -1) < r.get("vh", 0),
                        f"#refPanel top must sit inside the viewport, got top="
                        f"{r.get('rpTop')} vh={r.get('vh')}")
        self.assertEqual(r.get("errors"), [], "entry must be JS-clean")

    def test_unknown_direction_falls_back_to_nearest_still_scrolls(self):
        """(b) A stale/foreign name ⇒ nearest (default) stays focused, panel STILL
        opens and scrolls — the link never strands."""
        r = self._probe("?direction=Nonexistent%20Direction")
        self.assertEqual(r.get("active"), ["Alpha"],
                         "unknown name must FALL BACK to the nearest direction")
        self.assertEqual(r.get("bars"), ["0"], "nearest bars stay the visible panel")
        self.assertGreater(r.get("scrollY", 0), 0,
                           "even on fallback the panel must scroll into view")
        self.assertEqual(r.get("errors"), [], "fallback must be JS-clean")

    def test_no_param_default_state_no_scroll(self):
        """(c) Regression fence: a NORMAL open (no param) keeps the default state and
        does NOT scroll — the reader must be one-shot and param-gated."""
        r = self._probe("")
        self.assertEqual(r.get("active"), ["Alpha"], "default focus stays the nearest")
        self.assertEqual(r.get("scrollY"), 0,
                         "no param ⇒ NO scroll — a normal open must not jump the page")

    def test_entry_writes_no_store_and_tab_click_keeps_url(self):
        """(d) Fences: entry never writes the view store (§B.15), and a tab click after
        entry leaves the URL search untouched (the tab stays ephemeral, D-INV-28)."""
        js = ("(function(){var tabs=document.querySelectorAll('.reftab');"
              "if(tabs.length>2)tabs[2].click();"
              "var act=[];document.querySelectorAll('.reftab.active').forEach("
              "function(b){act.push(b.textContent.trim());});"
              "return {active:act,search:location.search,"
              "store:(function(){try{return localStorage.getItem('tc_view');}"
              "catch(e){return 'ERR';}})()};})()")
        r = hc.probe(self.page, js, width=1100, height=900,
                     url_suffix="?direction=Beta%20Prime")
        self.assertEqual(r.get("active"), ["Gamma"],
                         "the click path must still work after entry")
        self.assertEqual(r.get("search"), "?direction=Beta%20Prime",
                         "a tab click must NOT write the URL — the entry param is "
                         "one-shot, the tab ephemeral (D-INV-28)")
        self.assertIsNone(r.get("store"),
                          "entry must never write the view store (§B.15 fence)")

    def test_empty_state_ignores_param(self):
        """(e) The 'no close direction yet' empty state ignores the parameter entirely —
        no scroll, no focus, no error."""
        import fingerprints as FP
        def z(**over):
            d = {ax: 0.0 for ax in FP.AXES}
            d.update(over)
            return d
        far = {"x": z(tempo=9.0), "y": z(dynamics=9.0)}
        page = _merged_ref_page(far, {}, tmp_prefix="tc_entry_far_", lead_px=self.LEAD)
        r = hc.probe(page, _ENTRY_STATE_JS, width=1100, height=900,
                     url_suffix="?direction=x")
        self.assertEqual(r.get("scrollY"), 0,
                         "the empty state must IGNORE the param — no scroll")
        self.assertEqual(r.get("active"), [], "no tabs exist to focus")
        self.assertEqual(r.get("errors"), [], "ignoring must be JS-clean")

    def test_full_widget_entry_opens_detailed_and_scrolls(self):
        """(f) Composition on the REAL full widget: the catalog link's entry pair
        `?direction=⟨name⟩#detailed` opens the widget NOT in Simple (the panel is
        Simple-hidden, INV-18/22 — entry rides the shipped §B.15 hash override) with
        #refPanel inside the viewport."""
        page = _build_ref_widget()
        r0 = hc.probe(page,
                      "(function(){var v=[];document.querySelectorAll('.reftab').forEach("
                      "function(b){v.push(b.textContent.trim());});"
                      "return {labels:v,bars:TC.count('.refpanel')};})()",
                      width=1100, height=900)
        self.assertGreaterEqual(r0.get("bars", 0), 1,
                                "fixture guard: the full widget must render the reference read")
        labels = r0.get("labels") or []
        target = labels[1] if len(labels) >= 2 else None
        import urllib.parse
        suffix = ("?direction=" + urllib.parse.quote(target) if target
                  else "?direction=whatever") + "#detailed"
        r = hc.probe(page, _ENTRY_STATE_JS, width=1100, height=900, url_suffix=suffix)
        self.assertFalse(r.get("bodySimple"),
                         "the entry pair must land in Detailed — #refPanel is Simple-hidden")
        self.assertGreater(r.get("scrollY", 0), 0,
                           "the real widget must scroll the reference panel into view")
        self.assertTrue(0 <= r.get("rpTop", -1) < r.get("vh", 0),
                        f"#refPanel must sit inside the viewport, got top="
                        f"{r.get('rpTop')} vh={r.get('vh')}")
        if target:
            self.assertEqual(r.get("active"), [target],
                             "the named tab must be active on the real widget")
        self.assertIsNone(r.get("store"), "entry must not write tc_view (§B.15)")
        self.assertEqual(r.get("errors"), [], "the composed entry must be JS-clean")


def _build_nav_widget():
    """SYNTHETIC full widget for card→evidence navigation (INV-48) — every evidence target
    from the §B.13 map that the fixture can host is PRESENT: a resonant 250 Hz band → the
    tonal card + a visible #tonalPanel; swing in `detail` → the swing card whose target
    #rhyPanel sits inside the COLLAPSED "Evidence & detail" drawer; masking + stems → a
    timecoded card; .als → #autoPanel. Reuses the completeness-gate fixture data (the one
    synthetic build where every panel is populated)."""
    import test_completeness_gate as gate
    tmp = Path(tempfile.mkdtemp(prefix="tc_nav_"))
    sw = tmp / "stems_web"
    sw.mkdir()
    for stem in ("drums", "bass", "other"):
        (sw / f"{stem}.m4a").write_bytes(b"\x00" * 16)
    out = tmp / "widget.html"
    build_widget.build_html(
        gate._core(), {"swing_global_ms": 45.0}, gate._masking(), gate._als(), str(out),
        "Card Nav Test", build_widget.STRINGS, als_offset_s=0.0,
        stemmap=gate._stemmap(), rhythm=gate._rhythm(), notes=gate._notes(),
        audio_stems_rel="stems_web",
        narrative_md="The track builds steadily.")
    return str(out)


# Click a card selected by `sel` with a scrollIntoView spy + a seek spy installed first,
# then read back the SYNCHRONOUS facts of the click (pulse classes, drawer state, spies).
def _click_js(sel):
    return (
        "(function(){document.body.classList.remove('simple');"
        "var scrolled=[],seeked=false;"
        "var sp=Element.prototype.scrollIntoView;"
        "Element.prototype.scrollIntoView=function(){scrolled.push(this.id||'');return sp.apply(this,arguments);};"
        "window.__seek=function(){seeked=true;};"
        "var c=document.querySelector(" + repr(sel) + ");"
        "if(!c)return {missing:true,evs:Array.prototype.map.call("
        "document.querySelectorAll('#recs .rec'),function(e){return e.getAttribute('data-ev');})};"
        "var pre={cursor:getComputedStyle(c).cursor,title:c.getAttribute('title')||''};"
        "c.click();"
        "function pulsed(id){var e=document.getElementById(id);return !!(e&&e.classList.contains('pulse'));}"
        "return {cursor:pre.cursor,title:pre.title,scrolled:scrolled,seeked:seeked,"
        "story:pulsed('storyPanel'),tonal:pulsed('tonalPanel'),rhy:pulsed('rhyPanel'),"
        "vitals:pulsed('vitals'),"
        "drawerOpen:(document.getElementById('evidence')||{}).open===true,"
        "rhyH:(document.getElementById('rhyPanel')||{offsetHeight:-1}).offsetHeight,"
        "store:localStorage.getItem('tc_view'),"
        "errors:TC.errors()};})()"
    )


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class CardEvidenceNav(unittest.TestCase):
    """INV-48b/c/d/e (SPEC §B.13, s61) — a card leads to ITS evidence. Clicking a card
    scrolls + pulses the panel its based-on names (not always the story arc), opens a
    collapsed ancestor drawer on the way, makes global cards clickable where their target
    is present, and degrades to the 0.8.28 behaviour when the target is absent. Written
    RED against 1.2.1 (every click went to #storyPanel; global cards were inert)."""

    @classmethod
    def setUpClass(cls):
        cls.nav = _build_nav_widget()      # every target present
        cls.bare = _build_rich_widget()    # no stems/als/rhythm; 1-band tonal → panel hidden

    def test_click_pulses_the_cards_own_target(self):  # INV-48b
        r = hc.probe(self.nav, _click_js('#recs .rec[data-ev="tonalPanel"]'),
                     width=1100, height=900)
        self.assertFalse(r.get("missing"), f"no tonal card in the nav fixture: {r.get('evs')}")
        self.assertTrue(r.get("tonal"), "the click must pulse the card's OWN target (#tonalPanel)")
        self.assertFalse(r.get("story"), "the story arc must NOT pulse for a tonal card")
        self.assertIn("tonalPanel", r.get("scrolled", []),
                      "the click must scroll the target panel into view")
        self.assertEqual(r.get("errors"), [], "card navigation must be JS-clean")

    def test_global_card_clickable_with_pointer_and_title(self):  # INV-48e
        r = hc.probe(self.nav, _click_js('#recs .rec[data-ev="tonalPanel"]'),
                     width=1100, height=900)
        self.assertFalse(r.get("missing"), f"no tonal card in the nav fixture: {r.get('evs')}")
        self.assertEqual(r.get("cursor"), "pointer",
                         "a global card with a present target must read as clickable")
        self.assertTrue(r.get("title"), "the clickable global card must carry a jump title")
        self.assertFalse(r.get("seeked"), "a global card has no moment — the click must NOT seek")

    def test_collapsed_drawer_opens_and_target_has_height(self):  # INV-48c
        r = hc.probe(self.nav, _click_js('#recs .rec[data-ev="rhyPanel"]'),
                     width=1100, height=900)
        self.assertFalse(r.get("missing"), f"no swing card in the nav fixture: {r.get('evs')}")
        self.assertTrue(r.get("drawerOpen"),
                        "navigation must OPEN the collapsed Evidence & detail drawer")
        self.assertGreater(r.get("rhyH", -1), 0,
                           "after the click the target panel must be visible with real height "
                           "(the drawer's toggle listeners resized it — prover CN-2)")
        self.assertTrue(r.get("rhy"), "the pulse must land on #rhyPanel")
        self.assertIsNone(r.get("store"), "navigation must persist NOTHING (§B.15 fence)")
        self.assertEqual(r.get("errors"), [], "drawer navigation must be JS-clean")

    def test_missing_target_falls_back_and_global_goes_inert(self):  # INV-48d
        # The bare fixture's 1-band tonal_balance fires the tonal CARD but hides the PANEL.
        r = hc.probe(self.bare, _click_js('#recs .rec[data-ev="tonalPanel"]'),
                     width=1100, height=900)
        self.assertFalse(r.get("missing"), f"no tonal card in the bare fixture: {r.get('evs')}")
        self.assertNotEqual(r.get("cursor"), "pointer",
                            "a global card whose target is hidden must NOT read as clickable")
        self.assertEqual(r.get("title", ""), "", "an inert card carries no jump title")
        self.assertFalse(r.get("tonal") or r.get("story"),
                         "an inert card's click must pulse nothing — and not error")
        self.assertEqual(r.get("errors"), [], "the inert click must be JS-clean")
        # A timecoded card keeps the 0.8.28 behaviour: seek + story scroll + pulse.
        r2 = hc.probe(self.bare, _click_js('#recs .rec[data-t]'), width=1100, height=900)
        self.assertFalse(r2.get("missing"), "no timecoded card in the bare fixture")
        self.assertTrue(r2.get("story"), "a timecoded card still pulses the story arc")
        self.assertTrue(r2.get("seeked"), "a timecoded card still seeks the playhead")

    def test_map_panel_note_cards_stay_inert(self):  # prover CN-8 — `.rec` outside #recs
        js = ("(function(){document.body.classList.remove('simple');"
              "var ev=document.getElementById('evidence');if(ev)ev.open=true;"
              "return Array.prototype.map.call("
              "document.querySelectorAll('#mapNotes .rec'),function(e){"
              "return {cursor:getComputedStyle(e).cursor,ev:e.getAttribute('data-ev'),"
              "t:e.getAttribute('data-t')};});})()")
        rows = hc.probe(self.nav, js, width=1100, height=900)
        self.assertTrue(rows, "the nav fixture must render at least one map-panel note card")
        for row in rows:
            self.assertNotEqual(row.get("cursor"), "pointer",
                                "map-panel note cards reuse .rec but are NOT recs — never clickable")
            self.assertIsNone(row.get("ev"), "map-panel note cards must carry no evidence target")
            self.assertIsNone(row.get("t"), "map-panel note cards must carry no timecode")


def _globals_only_core(n=48, dur=120.0):
    """A core that spawns ONLY global (t=None) cards — energy_flat, wobble, true-peak,
    squashed, tonal — so the arc has NO timecoded cues at all (INV-49c zero bound):
    flat energy with an EARLY peak (no climax), no section bounds (no long_section),
    flat brightness (no brightness rec), low endpoint cosine (no endpoint rec)."""
    tb = [round(i * dur / n, 3) for i in range(n)]
    flat = [round(0.5 + (0.05 if i == 3 else 0.0), 3) for i in range(n)]  # peak at i=3, early
    return {
        "duration_s": dur, "time_bins": tb, "tempo": 123,
        "energy": flat, "brightness": [0.5] * n,
        "density": [0.5] * n, "stereo_width": [0.5] * n,
        "energy_trend": 0.02, "brightness_trend": 0.03, "density_trend": 0.02,
        "stereo_width_trend": 0.02,
        "wobble_rate_start_hz": 3.0, "wobble_rate_end_hz": 3.2,
        "endpoint_cosine": 0.5,
        "vitals": {"true_peak_db": 0.6, "dynamic_range_db": 4.5},
        "tonal_balance": [{"band": "250", "dev_db": 6.0}],
    }


def _build_globals_only_widget():
    tmp = Path(tempfile.mkdtemp(prefix="tc_nocue_"))
    out = tmp / "widget.html"
    build_widget.build_html(_globals_only_core(), {}, None, None, str(out),
                            "No Cues Test", build_widget.STRINGS, mode="full",
                            narrative_md="Globals only.")
    return str(out)


# INV-49 probes — scan a DEEP horizontal line across the arc canvas (y = 60% of its
# height, far below the 22px triangle band) with synthetic mousemoves; where the cursor
# turns `pointer` is a cue COLUMN. The zone is discovered by scanning the real affordance,
# never by re-computing the canvas layout constants (prover AB-1 discipline).
_ARC_SCAN_JS = (
    "(function(){document.body.classList.remove('simple');"
    "var cv=document.getElementById('story');if(!cv)return {noCanvas:true};"
    "var r=cv.getBoundingClientRect();var deepY=r.top+r.height*0.6;"
    "var segs=[],cur=null,tips=[];"
    "function mm(x){cv.dispatchEvent(new MouseEvent('mousemove',"
    "{clientX:x,clientY:deepY,bubbles:true}));return getComputedStyle(cv).cursor;}"
    "for(var x=Math.ceil(r.left)+1;x<r.right-1;x+=2){"
    " if(mm(x)==='pointer'){"
    "  if(!cur){cur={a:x,b:x};segs.push(cur);"
    "   var tip=document.getElementById('ctip');tips.push(tip?tip.innerHTML:'');}"
    "  else cur.b=x;}"
    " else cur=null;}"
    "return {segs:segs,tips:tips,h:r.height,"
    "lets:document.querySelectorAll('#recs .rec[data-let]').length};})()"
)


def _arc_click_js(mode):
    """mode='cue' clicks the centre of the first pointer segment at deep y;
    mode='gap' clicks the deep-y point FARTHEST from every segment (>25px away)."""
    return (
        "(function(){document.body.classList.remove('simple');"
        "var cv=document.getElementById('story');if(!cv)return {noCanvas:true};"
        "var r=cv.getBoundingClientRect();var deepY=r.top+r.height*0.6;"
        "var segs=[],cur=null;"
        "function mm(x){cv.dispatchEvent(new MouseEvent('mousemove',"
        "{clientX:x,clientY:deepY,bubbles:true}));return getComputedStyle(cv).cursor;}"
        "for(var x=Math.ceil(r.left)+1;x<r.right-1;x+=2){"
        " if(mm(x)==='pointer'){if(!cur){cur={a:x,b:x};segs.push(cur);}else cur.b=x;}"
        " else cur=null;}"
        "var scrolled=[],seeks=[];"
        "var sp=Element.prototype.scrollIntoView;"
        "Element.prototype.scrollIntoView=function(){scrolled.push(this.id||"
        "(this.classList&&this.classList.contains('rec')?'rec':''));"
        "return sp.apply(this,arguments);};"
        "window.__seek=function(t){seeks.push(t);};"
        "var href0=location.href,store0=localStorage.getItem('tc_view');"
        "var cx=null;"
        "if(" + ("true" if mode == "cue" else "false") + "){if(!segs.length)return {noSegs:true};"
        " cx=(segs[0].a+segs[0].b)/2;}"
        "else{var best=null,bd=-1;"
        " for(var x=Math.ceil(r.left)+1;x<r.right-1;x+=2){var d=1e9;"
        "  segs.forEach(function(s){d=Math.min(d,Math.max(s.a-x,x-s.b,0));});"
        "  if(d>bd){bd=d;best=x;}}"
        " if(bd<25)return {noGap:true,segs:segs.length};cx=best;}"
        "cv.dispatchEvent(new MouseEvent('click',{clientX:cx,clientY:deepY,bubbles:true}));"
        "var f=document.querySelector('#recs .rec.flash');"
        "return {seeks:seeks,scrolled:scrolled,segs:segs.length,"
        "flashLet:f?f.getAttribute('data-let'):null,"
        "flashT:f?parseFloat(f.getAttribute('data-t')):null,"
        "hrefSame:location.href===href0,"
        "storeSame:localStorage.getItem('tc_view')===store0,"
        "errors:TC.errors()};})()"
    )


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class ArcBackpointer(unittest.TestCase):
    """INV-49a-d (SPEC §B.13 "the arc answers back", 2026-07-05 late) — a cue's click
    zone is its whole COLUMN on the arc canvas, not only the 22px triangle band. Written
    RED against 1.3.0 (cueAt returned null below y=26, so a deep click never lit a card)."""

    @classmethod
    def setUpClass(cls):
        cls.nav = _build_nav_widget()            # timecoded cards → cues on the arc
        cls.nocue = _build_globals_only_widget()  # global cards only → NO cues

    def test_cue_column_is_hoverable_full_height(self):  # INV-49a
        r = hc.probe(self.nav, _ARC_SCAN_JS, width=1100, height=900)
        self.assertFalse(r.get("noCanvas"), "the nav fixture must render the arc canvas")
        segs, lets = r.get("segs", []), r.get("lets", 0)
        self.assertGreater(lets, 0, "the nav fixture must carry timecoded (lettered) cards")
        self.assertGreaterEqual(len(segs), 1,
                                "hovering DEEP below the triangle band at a cue's moment "
                                "must read as clickable (the whole column is the zone)")
        self.assertLessEqual(len(segs), lets,
                             "there must be no pointer zones beyond the cues "
                             "(nearby cues may merge into one segment)")
        for tip in r.get("tips", []):
            self.assertIn("click to read below", tip,
                          "hovering the column must show the cue tooltip, not the "
                          "generic time/scene readout")

    def test_column_click_seeks_and_lights_the_card(self):  # INV-49b + INV-49d
        r = hc.probe(self.nav, _arc_click_js("cue"), width=1100, height=900)
        self.assertFalse(r.get("noSegs"), "no pointer column found on the arc — INV-49a broken")
        self.assertEqual(len(r.get("seeks", [])), 1, "the column click must seek exactly once")
        self.assertIsNotNone(r.get("flashLet"),
                             "the column click must light (flash) the cue's card")
        self.assertIn("rec", r.get("scrolled", []),
                      "the lit card must be scrolled into view")
        self.assertIsNotNone(r.get("flashT"), "the lit card must be a timecoded card")
        self.assertLess(abs(r["seeks"][0] - r["flashT"]), 0.5,
                        "the seek must land on the CUE'S moment, not the raw pixel time")
        self.assertTrue(r.get("hrefSame"), "the backpointer must not touch the URL (INV-49d)")
        self.assertTrue(r.get("storeSame"), "the backpointer must not write the store (INV-49d)")
        self.assertEqual(r.get("errors"), [], "the arc backpointer must be JS-clean")

    def test_click_between_cues_stays_plain_seek(self):  # INV-49c
        r = hc.probe(self.nav, _arc_click_js("gap"), width=1100, height=900)
        self.assertFalse(r.get("noGap"),
                         f"no deep-y gap >25px from all {r.get('segs')} cue columns — "
                         "fixture too crowded to test the plain-seek side")
        self.assertEqual(len(r.get("seeks", [])), 1, "a gap click must still seek")
        self.assertIsNone(r.get("flashLet"), "a gap click must light NO card")
        self.assertNotIn("rec", r.get("scrolled", []),
                         "a gap click must not scroll any card into view")
        self.assertEqual(r.get("errors"), [], "plain seek must stay JS-clean")

    def test_no_timecoded_cards_no_columns(self):  # INV-49c zero bound
        r = hc.probe(self.nocue, _ARC_SCAN_JS, width=1100, height=900)
        self.assertFalse(r.get("noCanvas"), "the globals-only fixture must render the arc")
        self.assertEqual(r.get("lets", -1), 0,
                         "fixture drift: the globals-only build grew a timecoded card — "
                         "rebuild the core so every card stays global")
        self.assertEqual(len(r.get("segs", [])), 0,
                         "with no cues the whole arc must stay a pure seek surface")


if __name__ == "__main__":
    unittest.main()
