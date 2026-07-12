#!/usr/bin/env python3
"""Headless-Chrome render harness for track-coach widgets.

WHY this exists: the whole test suite (665 funcs, s33) asserted against the raw
HTML *string* or a node-DOM stub with no stylesheet. Two visibility/escaping bugs
shipped to the user's eyes twice in one day because `style.display=""` "passed"
with no CSS and card `<b>` was never read, only counted. This harness renders the
REAL shipped artifact with its REAL CSS + JS in a REAL browser and reads back
what the eye actually sees: computed style, layout geometry, visible text,
escaping — per [[track-coach-show-proper-renders]] and "assert the REAL shipped
artifact rendered in a browser".

Zero pip dependencies: drives `Google Chrome --headless=new` directly.

Two capabilities:
  probe(html_path, js, width, height) -> dict
      Injects a read-only <script> that evaluates `js` (a JS expression returning
      a JSON-serialisable object) AFTER the widget's own JS has rendered, then
      reads the result out of the dumped DOM. The artifact's own CSS/JS run
      unchanged; the probe only *reads* getComputedStyle/geometry and appends a
      results node.
  screenshot(html_path, out_png, width, height) -> path
      Renders at a concrete window size (catch layout skew a wide shot hides).

CLI:
  python headless_check.py probe  <widget.html> --js '<expr>' [--width W --height H]
  python headless_check.py shot   <widget.html> <out.png>     [--width W --height H]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Standard probe helpers a test can compose into its `js` expression. Kept as a
# JS prelude so tests read declaratively (see docstring of probe()).
JS_PRELUDE = r"""
var TC = {
  // computed display/visibility of the first match (what the eye sees).
  vis: function(sel){var e=document.querySelector(sel); if(!e) return null;
    var cs=getComputedStyle(e);
    return {display:cs.display, visibility:cs.visibility, opacity:cs.opacity,
            w:e.offsetWidth, h:e.offsetHeight,
            shown:(cs.display!=='none' && cs.visibility!=='hidden' && cs.opacity!=='0' && e.offsetHeight>0)};},
  // grid column tracks actually laid out (viewport/container-resolved px).
  gridCols: function(sel){var e=document.querySelector(sel); if(!e) return null;
    var t=getComputedStyle(e).gridTemplateColumns;
    return {raw:t, n:(t==='none'?0:t.split(/\s+/).filter(Boolean).length)};},
  // geometry of every match (detect skew: unequal x within a row, ragged tops).
  boxes: function(sel){return Array.prototype.map.call(document.querySelectorAll(sel),function(e){
    var r=e.getBoundingClientRect();
    return {x:Math.round(r.left), y:Math.round(r.top), w:Math.round(r.width), h:Math.round(r.height)};});},
  count: function(sel){return document.querySelectorAll(sel).length;},
  // literal escaped-tag leak in VISIBLE markup — a tag that shipped as text instead of
  // rendering. Script bodies are stripped first: they legitimately carry such sequences
  // in their own source (regexes, this harness's injected probe), which are not visible.
  escLeak: function(sel){var e=document.querySelector(sel); if(!e) return null;
    var h=e.innerHTML.replace(/<script[\s\S]*?<\/script>/gi,'');
    return (h.match(/&lt;\/?[a-z]/gi)||[]).length;},
  text: function(sel){var e=document.querySelector(sel); return e?e.textContent.trim():null;},
  // vertical top of the first match (px, viewport-relative) — for read-order checks.
  top: function(sel){var e=document.querySelector(sel); if(!e) return null;
    return Math.round(e.getBoundingClientRect().top);},
  // JS errors captured since page load (window.onerror + console.error). Empty = clean.
  errors: function(){return (window.__tcErrors||[]).slice();},
};
"""

# Installed in <head> BEFORE the widget's own scripts run, so a console.error or an
# uncaught exception during render is captured (a probe injected at </body> would miss
# an error thrown earlier). Read back via TC.errors().
JS_ERROR_COLLECTOR = (
    "<script>window.__tcErrors=[];"
    "window.addEventListener('error',function(e){"
    "window.__tcErrors.push(String((e&&e.message)||(e&&e.error)||e));});"
    "window.addEventListener('unhandledrejection',function(e){"
    "window.__tcErrors.push('unhandledrejection: '+String((e&&e.reason)||e));});"
    "var _ce=console.error;console.error=function(){"
    "try{window.__tcErrors.push(Array.prototype.map.call(arguments,String).join(' '));}"
    "catch(_){}_ce.apply(console,arguments);};</script>"
)


def _run_chrome(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    if not Path(CHROME).exists():
        raise RuntimeError(f"Chrome not found at {CHROME}")
    return subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--hide-scrollbars", *args],
        capture_output=True, text=True, timeout=timeout,
    )


def probe(html_path: str, js: str, width: int = 1200, height: int = 2400,
          settle_ms: int = 250, virtual_time: int = 6000,
          url_suffix: str = "") -> dict:
    """Render html_path in headless Chrome, evaluate `js` (a JS expression that
    returns a JSON-serialisable object, with TC.* helpers available) after the
    page settles, and return the parsed result dict.

    url_suffix: appended verbatim to the file:// URI (e.g. "?direction=Beta#detailed"),
    so entry-parameter behaviour (D-INV-37) is testable against a real page load."""
    src = Path(html_path).read_text(encoding="utf-8")
    injected = (
        "<script>window.addEventListener('load',function(){setTimeout(function(){"
        + JS_PRELUDE
        + "var __r;try{__r=(" + js + ");}catch(e){__r={__error:String(e)};}"
        "var n=document.createElement('script');n.id='__tc_probe';"
        "n.type='application/json';n.textContent=JSON.stringify(__r);"
        "document.body.appendChild(n);"
        "}," + str(settle_ms) + ");});</script>"
    )
    # Install the error collector as early as possible (before the widget's scripts).
    if "<head>" in src:
        src = src.replace("<head>", "<head>" + JS_ERROR_COLLECTOR, 1)
    else:
        src = JS_ERROR_COLLECTOR + src

    if "</body>" in src:
        src = src.replace("</body>", injected + "</body>", 1)
    else:
        src = src + injected

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     dir=Path(html_path).parent, encoding="utf-8") as f:
        tmp = Path(f.name)
        f.write(src)
    try:
        cp = _run_chrome([
            f"--window-size={width},{height}",
            f"--virtual-time-budget={virtual_time}",
            "--run-all-compositor-stages-before-draw",
            "--dump-dom", tmp.as_uri() + url_suffix,
        ])
        m = re.search(
            r'<script id="__tc_probe"[^>]*>(.*?)</script>', cp.stdout, re.S)
        if not m:
            raise RuntimeError(
                "probe result not found in dumped DOM (page may not have loaded). "
                f"stderr tail: {cp.stderr[-400:]}")
        return json.loads(m.group(1))
    finally:
        tmp.unlink(missing_ok=True)


def screenshot(html_path: str, out_png: str, width: int = 1200,
               height: int = 2400, virtual_time: int = 6000) -> str:
    _run_chrome([
        f"--window-size={width},{height}",
        f"--virtual-time-budget={virtual_time}",
        "--run-all-compositor-stages-before-draw",
        f"--screenshot={out_png}", Path(html_path).resolve().as_uri(),
    ])
    if not Path(out_png).exists():
        raise RuntimeError(f"screenshot not produced at {out_png}")
    return out_png


def _main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("html")
    p.add_argument("--js", required=True)
    p.add_argument("--width", type=int, default=1200)
    p.add_argument("--height", type=int, default=2400)
    s = sub.add_parser("shot")
    s.add_argument("html")
    s.add_argument("out")
    s.add_argument("--width", type=int, default=1200)
    s.add_argument("--height", type=int, default=2400)
    a = ap.parse_args()
    if a.cmd == "probe":
        print(json.dumps(probe(a.html, a.js, a.width, a.height), indent=2))
    else:
        print(screenshot(a.html, a.out, a.width, a.height))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
