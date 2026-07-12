"""Design-system token guards (SPEC §I, 2026-07-02).

These assert the REAL shipped CSS in build_widget.TEMPLATE + the catalog PALETTE:
- DS-INV-2: the catalog's shared roles equal the widget's (no re-drift / single source).
- DS-INV-3: the near-white text ladder + drift colours are tokenised in the UI CSS.
- DS-INV-7c: the guard is keyed by LOCATION — data-viz literals (stem arrays + the one
  canvas meter label) keep their raw hex; only the CSS-rule region is de-hexed.
"""
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402
import catalog  # noqa: E402


def _css_region():
    """The <style>…</style> block of the shipped template (UI CSS only)."""
    return build_widget.TEMPLATE.split("<style>", 1)[1].split("</style>", 1)[0]


def _js_region():
    """Everything after the CSS — canvas draws + stem-colour arrays (data-viz)."""
    return build_widget.TEMPLATE.split("</style>", 1)[1]


def _root_tokens():
    css = _css_region()
    root = re.search(r":root\{[^}]*\}", css).group(0)
    return dict(re.findall(r"--([\w-]+):(#[0-9a-fA-F]{3,8})", root))


# DS-INV-2 — one source: the catalog re-declares the SAME values as the widget on shared roles.
def test_catalog_palette_matches_widget_root():
    root = _root_tokens()
    mismatches = []
    for key, val in catalog.PALETTE.items():
        token = key.replace("_", "-")  # ink_dim -> ink-dim
        if token in root and root[token].lower() != val.lower():
            mismatches.append(f"{key}: catalog {val} != widget {root[token]}")
    assert not mismatches, "catalog palette drifted from widget :root: " + "; ".join(mismatches)


# DS-INV-3 — the text ladder token exists.
def test_ink_dim_token_defined():
    assert "ink-dim" in _root_tokens(), "--ink-dim must be defined in the widget :root"


# DS-INV-3 — the near-white + drift raw hexes are gone from the CSS RULES (token defs excepted).
FORBIDDEN_IN_CSS = [
    "#eef1f8", "#cfd6e6", "#cdd5e6", "#c3cbdc", "#aab3c7", "#a0a8bc", "#8b93a7",  # near-whites
    "#ffb13f", "#6fdfb8",  # drift → warn / good
]


def test_ladder_and_drift_tokenised_in_css():
    css = _css_region()
    root = re.search(r":root\{[^}]*\}", css).group(0)
    rules = css.replace(root, "")  # strip the token definitions; check only the rules
    leaked = [hx for hx in FORBIDDEN_IN_CSS if hx in rules]
    assert not leaked, f"UI CSS still carries raw hex that should be a token: {leaked}"


# DS-INV-7c — the guard is by LOCATION: the data-viz literals are LEFT raw.
def test_stem_and_canvas_literals_untouched():
    js = _js_region()
    for hx in ["#ff5d73", "#5ad1c2", "#4cc9f0", "#ffd166", "#a78bfa"]:
        assert hx in js, f"stem colour {hx} must stay a raw literal in the data-viz region"
    # the meter-change label is a canvas draw (data-viz), deliberately not tokenised
    assert 'ctx.fillStyle="#cfd6e6"' in js, "canvas meter label must keep its raw hex"


# ── Movement 2 (SPEC §I.2–I.6) — radii, motion, dedup, one segmented control ──

def _source():
    """The shipped build_widget.py source text (asserts the real emitted markup)."""
    return pathlib.Path(build_widget.__file__).read_text()


def _root_block():
    return re.search(r":root\{[^}]*\}", _css_region()).group(0)


def _css_rules():
    """CSS with the :root token definitions stripped — the component rules only."""
    css = _css_region()
    return css.replace(_root_block(), "")


# DS-INV-12 — every single-value UI border-radius is on the 10/14/18/20 scale
# (the ad-hoc 6/8/9/11/12 snap in). Compound notch shapes (`0 6px 6px 0`) and tiny
# decorative swatch/bar radii (<=5px) are exempt per spec.
def test_radii_snapped_to_scale():
    vals = re.findall(r"border-radius:\s*(\d+)px\s*[;}]", _css_region())
    on_scale = {10, 14, 18, 20}
    decorative = {1, 2, 3, 4, 5}
    off = sorted({int(v) for v in vals if int(v) not in on_scale | decorative})
    assert not off, f"UI border-radius off the 10/14/18/20 scale (snap or tokenise): {off}px"


# DS-INV-12 — the radius tokens exist in :root.
def test_radius_tokens_defined():
    root = _root_block()
    for t in ("--radius:", "--radius-lg:", "--radius-xl:", "--radius-pill:"):
        assert t in root, f"{t} must be defined in :root"


# DS-INV-10 — motion tokens exist and the raw .12s/.15s literals leave the component rules.
def test_motion_tokens_defined_and_used():
    root = _root_block()
    for t in ("--dur-fast:", "--dur-base:"):
        assert t in root, f"{t} must be defined in :root"
    rules = _css_rules()
    leaked = [lit for lit in (".12s", ".15s") if lit in rules]
    assert not leaked, f"component transitions still carry raw duration literals: {leaked}"


# DS-INV-1/4 — the dark-on-accent text uses var(--bg), not raw #0c0e14, in the CSS rules.
def test_bg_token_not_raw_in_css_rules():
    assert "#0c0e14" not in _css_rules(), "CSS rules must use var(--bg), not raw #0c0e14"


# DS-INV-13 — ONE segmented-control class, worn by BOTH former controls; selected = --wob fill.
def test_one_segmented_control():
    css = _css_region()
    assert ".seg{" in css, "the unified segmented-control class .seg must exist"
    src = _source()
    assert 'class="viewtoggle seg"' in src, "the view-toggle must wear the shared .seg class"
    assert 'class="reftabs seg"' in src, "the reference tabs must wear the shared .seg class"
    # selected = CALM (2026-07-02): the old panel2 lift, SAME weight, NO inverted contrast.
    seg_sel = re.search(r"\.seg>button\.on[^}]*\}", css).group(0)
    assert "var(--panel2)" in seg_sel, "the selected state uses the calm panel2 fill"
    assert "var(--bg)" not in seg_sel, "the selected state must not invert to dark text on a bright fill"
    assert "font-weight:700" not in seg_sel, "the selected tab must not suddenly go bold"
