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
