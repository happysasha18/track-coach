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
import time
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Substrings that mark an INFRASTRUCTURE crash of headless Chrome (NOT a test failure).
# Under system load the headless browser dies mid-render with this signature and a
# DIFFERENT random subset of tests fails every full-suite run — each passing cleanly on
# a re-run in isolation. When a render fails AND Chrome's stderr carries any of these,
# the render is retried (see _probe_render). A genuine JS error, a real assertion-shaped
# result, or a malformed probe expression never carries these markers and is NEVER retried
# — the retry stays narrow to the crash so it can never mask a real failure.
_CRASH_MARKERS = (
    "NOTREACHED hit",
    "browser_context_impl.cc",
    "ProcessHeadlessCommands",
    "mach_vm_read",
    "crashpad",
    "invalid address",
)

# How many times a crashed render is attempted in total (1 original + 2 retries).
_RENDER_ATTEMPTS = 3


def _looks_like_crash(stderr: str) -> bool:
    """True when Chrome's stderr shows the headless-crash signature (see _CRASH_MARKERS)."""
    s = stderr or ""
    return any(marker in s for marker in _CRASH_MARKERS)

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


_PROBE_RE = re.compile(r'<script id="__tc_probe"[^>]*>(.*?)</script>', re.S)


def _probe_render(chrome_args: list[str]) -> str:
    """Render with Chrome and return the raw JSON text of the injected __tc_probe node.

    The ONE place probe-style renders run + parse, so the crash-retry lives here alone and
    every caller (probe, and run_smoke through it) inherits it. Retries ONLY the
    infrastructure crash: the probe node is absent AND Chrome's stderr shows the crash
    signature. A probe node that is simply absent with no crash markers (a malformed `js`
    expression, a page that genuinely never produced the node) FAILS IMMEDIATELY, exactly
    as before — the retry can never mask a real test failure. A genuine JS error or a real
    assertion result comes back INSIDE the probe node, so it parses on the first attempt and
    never reaches the retry path at all."""
    for attempt in range(1, _RENDER_ATTEMPTS + 1):
        cp = _run_chrome(chrome_args)
        m = _PROBE_RE.search(cp.stdout)
        if m:
            return m.group(1)
        crashed = _looks_like_crash(cp.stderr)
        if crashed and attempt < _RENDER_ATTEMPTS:
            sys.stderr.write(
                f"headless render crashed (Chrome NOTREACHED), "
                f"retrying {attempt}/{_RENDER_ATTEMPTS - 1}…\n")
            sys.stderr.flush()
            try:
                time.sleep(0.5)  # brief backoff; harmless if it no-ops
            except Exception:
                pass
            continue
        # Either a non-crash miss (fail now, never retried) or the crash outlived every
        # attempt (fail after exhausting retries) — same visible error as before.
        raise RuntimeError(
            "probe result not found in dumped DOM (page may not have loaded). "
            f"stderr tail: {cp.stderr[-400:]}")
    # Unreachable: the loop always returns or raises.
    raise RuntimeError("probe render exhausted without a result")


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
        # Render + parse is centralised in _probe_render, which retries ONLY the
        # headless-Chrome infrastructure crash (never a real test failure). The tmp file
        # persists across attempts (unlinked in finally), so a retry re-renders the same page.
        result_json = _probe_render([
            f"--window-size={width},{height}",
            f"--virtual-time-budget={virtual_time}",
            "--run-all-compositor-stages-before-draw",
            "--dump-dom", tmp.as_uri() + url_suffix,
        ])
        return json.loads(result_json)
    finally:
        tmp.unlink(missing_ok=True)


def screenshot(html_path: str, out_png: str, width: int = 1200,
               height: int = 2400, virtual_time: int = 6000) -> str:
    args = [
        f"--window-size={width},{height}",
        f"--virtual-time-budget={virtual_time}",
        "--run-all-compositor-stages-before-draw",
        f"--screenshot={out_png}", Path(html_path).resolve().as_uri(),
    ]
    # Same infrastructure-crash retry as _probe_render: if the PNG is missing AND Chrome's
    # stderr shows the crash signature, re-render (up to _RENDER_ATTEMPTS). A missing PNG
    # with no crash markers is a genuine failure and raises immediately, as before.
    for attempt in range(1, _RENDER_ATTEMPTS + 1):
        cp = _run_chrome(args)
        if Path(out_png).exists():
            return out_png
        if _looks_like_crash(cp.stderr) and attempt < _RENDER_ATTEMPTS:
            sys.stderr.write(
                f"headless screenshot crashed (Chrome NOTREACHED), "
                f"retrying {attempt}/{_RENDER_ATTEMPTS - 1}…\n")
            sys.stderr.flush()
            try:
                time.sleep(0.5)
            except Exception:
                pass
            continue
        raise RuntimeError(f"screenshot not produced at {out_png}")
    raise RuntimeError(f"screenshot not produced at {out_png}")


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
