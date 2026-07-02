#!/usr/bin/env python3
"""Standing pre-render smoke — the last gate before a widget is shown to Alexander.

WHY this exists (s36): PART 1 of the test overhaul added a browser harness + first
render tests; the two bugs that shipped to Alexander's eyes twice in one day (a
crooked one-column recs grid, card `<b>` leaking as `&lt;b&gt;`) are exactly the
class a string test cannot see. This smoke renders a REAL widget in headless Chrome
and asserts the four things a human notices FIRST when a render is broken:

  1. no JS console error / uncaught exception during render  (TC.errors() empty)
  2. no literal escaped-tag leak anywhere in the body        (&lt;tag&gt; as text)
  3. the recs panel is non-empty in the default view         (a blank panel = broken)
  4. every core, every-view surface is visibly rendered      (story/read/evidence/player)

`run_smoke(widget_path)` returns a list of human-readable failures ([] = clean); it is
called both by the suite (tests/test_headless_render.py::PreRenderSmoke) and by this CLI.

Ship-checklist use:
  python scripts/prerender_smoke.py <freshly-built-widget.html>
  # exit 0 = clean; exit 1 = one or more failures printed. Run it on a REAL render
  # before showing Alexander (per the "show real, batched, verified" rule).
Run with no path to smoke a synthetic rich widget (self-test of the render path).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import headless_check as hc  # noqa: E402

# Core every-view surfaces: present + visibly rendered in BOTH Simple and Detailed.
# NOT the player — it is data-gated (no audio ⇒ no player, by design); the always-on
# surfaces are the story arc, the producer read, and the evidence drawer.
CORE_SURFACES = ["#story", "#evidence", "#readBody"]


def run_smoke(widget_path: str) -> list[str]:
    """Render widget_path headless and return a list of failures ([] = clean)."""
    fails: list[str] = []

    # (1) console errors / uncaught exceptions + (2) escaped-tag leak, default view.
    r = hc.probe(
        widget_path,
        "(function(){return {errors:TC.errors(),leak:TC.escLeak('body'),"
        "recs:Array.prototype.filter.call(document.querySelectorAll('#recs > .rec'),"
        "function(e){return e.getBoundingClientRect().height>0;}).length};})()",
        width=1100, height=3200)
    if r.get("errors"):
        fails.append(f"JS errors during render: {r['errors']}")
    if r.get("leak"):
        fails.append(f"escaped-tag leak in body ({r['leak']} occurrence(s) of &lt;tag&gt;)")
    # (3) recs non-empty in the default view.
    if not r.get("recs"):
        fails.append("recs panel is empty in the default view (no visible cards)")

    # (4) core surfaces visible in BOTH views.
    for view in ("simple", "detailed"):
        body = "true" if view == "simple" else "false"
        lst = ",".join(f'"{s}"' for s in CORE_SURFACES)
        js = ("(function(){document.body.classList.toggle('simple'," + body + ");"
              "var o={};[" + lst + "].forEach(function(s){var e=document.querySelector(s);"
              "o[s]=e?(getComputedStyle(e).display!=='none' && e.offsetHeight>0):null;});"
              "return o;})()")
        vis = hc.probe(widget_path, js, width=1100, height=3200)
        for sel in CORE_SURFACES:
            if vis.get(sel) is not True:
                fails.append(f"{sel} not visibly rendered in {view} view")
    return fails


def _build_synthetic_widget() -> str:
    """Build a rich widget from synthetic data — a self-test of the render path when
    no real widget path is given."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_widget as bw
    n, dur = 48, 120.0
    core = {
        "duration_s": dur, "time_bins": [round(i * dur / n, 3) for i in range(n)], "tempo": 123,
        "energy": [round(0.15 + 0.8 * i / n, 3) for i in range(n)],
        "brightness": [round(0.1 + 0.85 * i / n, 3) for i in range(n)],
        "density": [round(0.3 + 0.5 * (i % 5) / 5, 3) for i in range(n)],
        "wobble_rate": [round(1.0 + (i % 4), 3) for i in range(n)],
        "stereo_width": [round(0.4 + 0.3 * (i % 3) / 3, 3) for i in range(n)],
        "energy_trend": 0.5, "brightness_trend": 0.6, "density_trend": 0.05,
        "stereo_width_trend": 0.1, "wobble_rate_start_hz": 3.0, "wobble_rate_end_hz": 3.2,
        "section_bounds_s": [round(dur * 0.1, 2), round(dur * 0.15, 2)],
        "endpoint_cosine": 0.97,
        "vitals": {"true_peak_db": 0.6, "dynamic_range_db": 4.5},
        "tonal_balance": [{"band": "250", "dev_db": 6.0}],
    }
    out = Path(tempfile.mkdtemp(prefix="tc_smoke_")) / "widget.html"
    bw.build_html(core, {}, None, None, str(out), "Smoke Test", bw.STRINGS, mode="full",
                  narrative_md="The mix reads clear.\n\nBass is forward early.")
    return str(out)


def _main() -> int:
    widget = sys.argv[1] if len(sys.argv) > 1 else _build_synthetic_widget()
    if not Path(hc.CHROME).exists():
        print(f"SKIP: headless Chrome not found at {hc.CHROME}")
        return 0
    fails = run_smoke(widget)
    if fails:
        print(f"PRE-RENDER SMOKE FAILED ({len(fails)}):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"PRE-RENDER SMOKE PASSED — {widget}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
