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
class PreRenderSmoke(unittest.TestCase):
    """The standing ship gate (scripts/prerender_smoke.py) must pass on a real render:
    no JS console error, no escaped-tag leak, recs non-empty, every core surface visible
    in both views. This runs the exact function the ship-checklist CLI runs, so the gate
    can never silently rot away from the checklist."""

    def test_smoke_clean_on_a_full_widget(self):
        import prerender_smoke  # noqa: E402  (scripts is already on sys.path)
        fails = prerender_smoke.run_smoke(_build_rich_widget(with_stems=True))
        self.assertEqual(fails, [], "pre-render smoke found render defects:\n" + "\n".join(fails))


if __name__ == "__main__":
    unittest.main()
