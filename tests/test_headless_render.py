"""Browser-level regression tests — assert the REAL shipped artifact RENDERED.

WHY this file exists (s34, Alexander EMPHATIC): the other ~660 tests assert on the
HTML *string* or a node-DOM stub with NO stylesheet. Two visible bugs still shipped
to Alexander's eyes twice in one day — the recs grid collapsed to one crooked column,
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
    """The reference read (#refRead), the web plaque (#webPanel) and the tonal-balance
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
        # here and stacked every card in one column at Alexander's ~2/3-screen window.
        # The container query must now give two columns. A test at a wide (>760px)
        # window would NOT have caught the shipped bug.
        r = hc.probe(self.widget, _COLS_JS, width=720, height=3600)
        self.assertEqual(
            r["cols"], 2,
            f"recs grid must show 2 columns at a 720px window; saw {r['cols']} "
            "(the crooked single-column regression Alexander saw)")

    def test_more_columns_when_theres_room(self):
        # Alexander: "when there's plenty of room give 3 or more." auto-fit adds a
        # column as the panel widens (capped only by the wrap max-width).
        r = hc.probe(self.widget, _COLS_JS, width=1100, height=2800)
        self.assertGreaterEqual(
            r["cols"], 3,
            f"recs grid must add a 3rd column on a wide window; saw {r['cols']}")

    def test_single_column_when_cramped(self):
        r = hc.probe(self.widget, _COLS_JS, width=460, height=4000)
        self.assertEqual(
            r["cols"], 1,
            f"recs grid must reflow to 1 column when narrow; saw {r['cols']}")

    def test_cards_have_vertical_breathing_room(self):
        # Alexander: the plates felt glued together. Assert a real gap between
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
    — the regression this fixture guards is that they vanish with no acknowledgment."""
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
    guard (Alexander 2026-07-02): they used to render; 0.8.1 stripped them from the draw
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
        self.assertIn("vocals", text, "the omitted stem 'vocals' must be named in the stem panel")
        self.assertIn("piano", text, "the omitted stem 'piano' must be named in the stem panel")
        self.assertTrue("omit" in text or "near-silent" in text or "silent" in text,
                        "the acknowledgment must say WHY they are absent (omitted / near-silent)")

    def test_omitted_stems_sink_below_the_significant_ones(self):
        # Layout (Alexander s37): an empty lane in the MIDDLE reads as a gap; the near-silent stems
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
    REAL geometry a string test can't see. `@media(max-width:1100px)` hides cols 9–12
    (mood/style, mode, similarity); `@media(max-width:880px)` also hides col 3 (date). This
    is the same class of bug as the crooked recs grid — a computed `display:none` under a
    viewport width, invisible to a string/DOM-stub test. INV-10 / responsive-table."""

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

    def test_wide_shows_shed_columns(self):
        self.assertTrue(self._col_shown(1400, 9), "col 9 (mood/style) must show at 1400px")
        self.assertTrue(self._col_shown(1400, 3), "col 3 (date) must show at 1400px")

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
    """D-INV-19: the per-facet signed bars (ёлочка decomposition) must physically RENDER
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


if __name__ == "__main__":
    unittest.main()
