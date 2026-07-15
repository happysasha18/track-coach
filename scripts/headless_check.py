#!/usr/bin/env python3
"""Headless-Chrome render harness for track-coach widgets.

WHY this exists: the whole test suite (s33) asserted against the raw HTML *string*
or a node-DOM stub with no stylesheet. Two visibility/escaping bugs shipped to the
user's eyes twice in one day because `style.display=""` "passed" with no CSS and a
card `<b>` was never read, only counted. This harness renders the REAL shipped
artifact with its REAL CSS + JS in a REAL browser and reads back what the eye
actually sees: computed style, layout geometry, visible text, escaping — per
[[track-coach-show-proper-renders]] and "assert the REAL shipped artifact".

DESIGN (2026-07-15, the "royal road" rework): ONE persistent headless Chrome is
launched for the whole test session and driven over its DevTools pipe
(`--remote-debugging-pipe`: newline/NUL-delimited JSON over two file descriptors —
zero pip dependencies, no WebSocket). Each probe opens a tab, navigates, WAITS for
the real page-load event, evaluates the read expression directly with
`Runtime.evaluate`, and closes the tab. This replaces the previous model of
spawning a fresh `Chrome --headless=new … --dump-dom` subprocess PER probe (60+
cold starts a suite) and parsing an injected node out of stdout — a model that,
under machine load, occasionally dumped truncated DOM and failed a random test
every full run. Reusing one browser and waiting on the load event (instead of a
fixed sleep + a 60 s subprocess timeout + a stdout regex) removes the cause of that
flake outright, so no test-level retry is needed.

Two capabilities, API-compatible with the old harness:
  probe(html_path, js, width, height, ...) -> dict
      Evaluates `js` (a JS expression returning a JSON-serialisable object, with
      the TC.* helpers available) AFTER the page's load event, and returns the
      parsed result. The artifact's own CSS/JS run unchanged; the probe only reads.
  screenshot(html_path, out_png, width, height) -> path
      Renders at a concrete viewport and captures a PNG over the protocol.

CLI:
  python headless_check.py probe <widget.html> --js '<expr>' [--width W --height H]
  python headless_check.py shot  <widget.html> <out.png>     [--width W --height H]
"""
from __future__ import annotations

import argparse
import atexit
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Substrings that mark a headless-Chrome INFRASTRUCTURE crash (NOT a test failure).
# Kept for browser-liveness recovery: if the persistent browser dies, it is relaunched
# ONCE for the current probe (see _Browser.call / probe). A genuine JS error or a real
# assertion-shaped result never carries these markers, so recovery can never mask a
# real failure.
_CRASH_MARKERS = (
    "NOTREACHED hit",
    "browser_context_impl.cc",
    "ProcessHeadlessCommands",
    "mach_vm_read",
    "crashpad",
    "invalid address",
)

# How many times a probe is attempted across a browser-liveness relaunch (1 + 1 relaunch).
# NOT an assertion retry: only a dead/broken browser transport triggers a relaunch; the
# read itself runs once against a live browser.
_RENDER_ATTEMPTS = 2


def _looks_like_crash(stderr: str) -> bool:
    """True when Chrome's stderr shows the headless-crash signature (see _CRASH_MARKERS)."""
    s = stderr or ""
    return any(marker in s for marker in _CRASH_MARKERS)


# Standard probe helpers a test composes into its `js` expression. Kept as a JS prelude
# so tests read declaratively. Unchanged from the previous harness — the same reads.
JS_PRELUDE = r"""
var TC = {
  vis: function(sel){var e=document.querySelector(sel); if(!e) return null;
    var cs=getComputedStyle(e);
    return {display:cs.display, visibility:cs.visibility, opacity:cs.opacity,
            w:e.offsetWidth, h:e.offsetHeight,
            shown:(cs.display!=='none' && cs.visibility!=='hidden' && cs.opacity!=='0' && e.offsetHeight>0)};},
  gridCols: function(sel){var e=document.querySelector(sel); if(!e) return null;
    var t=getComputedStyle(e).gridTemplateColumns;
    return {raw:t, n:(t==='none'?0:t.split(/\s+/).filter(Boolean).length)};},
  boxes: function(sel){return Array.prototype.map.call(document.querySelectorAll(sel),function(e){
    var r=e.getBoundingClientRect();
    return {x:Math.round(r.left), y:Math.round(r.top), w:Math.round(r.width), h:Math.round(r.height)};});},
  count: function(sel){return document.querySelectorAll(sel).length;},
  escLeak: function(sel){var e=document.querySelector(sel); if(!e) return null;
    var h=e.innerHTML.replace(/<script[\s\S]*?<\/script>/gi,'');
    return (h.match(/&lt;\/?[a-z]/gi)||[]).length;},
  text: function(sel){var e=document.querySelector(sel); return e?e.textContent.trim():null;},
  top: function(sel){var e=document.querySelector(sel); if(!e) return null;
    return Math.round(e.getBoundingClientRect().top);},
  errors: function(){return (window.__tcErrors||[]).slice();},
};
"""

# Installed BEFORE any page script (Page.addScriptToEvaluateOnNewDocument), so a
# console.error or an uncaught exception during render is captured. Read via TC.errors().
_ERROR_COLLECTOR_SRC = (
    "window.__tcErrors=[];"
    "window.addEventListener('error',function(e){"
    "window.__tcErrors.push(String((e&&e.message)||(e&&e.error)||e));});"
    "window.addEventListener('unhandledrejection',function(e){"
    "window.__tcErrors.push('unhandledrejection: '+String((e&&e.reason)||e));});"
    "var _ce=console.error;console.error=function(){"
    "try{window.__tcErrors.push(Array.prototype.map.call(arguments,String).join(' '));}"
    "catch(_){}_ce.apply(console,arguments);};"
)


class _BrowserDead(RuntimeError):
    """The persistent browser transport is broken (process died / pipe closed)."""


class _Browser:
    """A persistent headless Chrome driven over --remote-debugging-pipe.

    Messages are NUL-delimited JSON: we WRITE commands to Chrome's fd 3 and READ
    responses/events from its fd 4. Sessions are flattened, so every command carries
    its `sessionId` and every reply/event is routed by it. One instance per process."""

    def __init__(self):
        if not Path(CHROME).exists():
            raise RuntimeError(f"Chrome not found at {CHROME}")
        cmd_r, cmd_w = os.pipe()      # we write commands -> Chrome reads as fd 3
        resp_r, resp_w = os.pipe()    # Chrome writes as fd 4 -> we read responses

        def _preexec():
            os.dup2(cmd_r, 3)
            os.dup2(resp_w, 4)

        # Chrome's stderr goes to a throwaway file (not /dev/null): when the CDP pipe dies, the
        # crash reason is read out of it, so a renderer/browser death names itself instead of
        # surfacing as a bare "pipe closed" (the pattern proven in tlvphotos/tests/headless.py).
        self._stderr_f = tempfile.NamedTemporaryFile(
            "w+b", prefix="tc_chrome_", suffix=".log", delete=False)
        self._proc = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--hide-scrollbars", "--remote-debugging-pipe", "about:blank"],
            preexec_fn=_preexec, pass_fds=(3, 4),
            stdout=subprocess.DEVNULL, stderr=self._stderr_f,
        )
        os.close(cmd_r)
        os.close(resp_w)
        self._cmd_w = cmd_w
        self._resp_r = resp_r
        self._buf = b""
        self._id = 0
        # Fail fast if the browser never comes up.
        self.call("Browser.getVersion", timeout=20)

    # -- transport ---------------------------------------------------------------
    def _write(self, obj):
        try:
            os.write(self._cmd_w, json.dumps(obj).encode("utf-8") + b"\0")
        except OSError as e:
            raise _BrowserDead(f"write to Chrome failed: {e}")

    def _read_message(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            if b"\0" in self._buf:
                raw, self._buf = self._buf.split(b"\0", 1)
                if not raw.strip():
                    continue
                return json.loads(raw.decode("utf-8"))
            if self._proc.poll() is not None:
                raise _BrowserDead("Chrome process exited")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _BrowserDead("timed out reading from Chrome")
            try:
                chunk = os.read(self._resp_r, 1 << 16)
            except OSError as e:
                raise _BrowserDead(f"read from Chrome failed: {e}")
            if not chunk:
                raise _BrowserDead("Chrome pipe closed")
            self._buf += chunk

    def call(self, method, params=None, sessionId=None, timeout=30):
        self._id += 1
        mid = self._id
        msg = {"id": mid, "method": method, "params": params or {}}
        if sessionId:
            msg["sessionId"] = sessionId
        self._write(msg)
        while True:
            m = self._read_message(timeout)
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"CDP {method} error: {m['error']}")
                return m.get("result", {})
            # otherwise an event or another session's reply — ignore and keep reading.

    def wait_event(self, method, sessionId, timeout=30):
        while True:
            m = self._read_message(timeout)
            if m.get("method") == method and m.get("sessionId") == sessionId:
                return m.get("params", {})
            # A stray reply/other event: keep waiting for the target event.

    # -- sessions ----------------------------------------------------------------
    def new_session(self, width, height):
        tid = self.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        sid = self.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.call("Page.enable", sessionId=sid)
        self.call("Runtime.enable", sessionId=sid)
        self.call("Emulation.setDeviceMetricsOverride",
                  {"width": int(width), "height": int(height),
                   "deviceScaleFactor": 1, "mobile": False}, sessionId=sid)
        self.call("Page.addScriptToEvaluateOnNewDocument",
                  {"source": _ERROR_COLLECTOR_SRC}, sessionId=sid)
        return tid, sid

    def close_session(self, tid):
        try:
            self.call("Target.closeTarget", {"targetId": tid}, timeout=10)
        except Exception:
            pass

    def stderr_tail(self, n=1500):
        """The tail of Chrome's stderr — the crash reason when the browser dies."""
        try:
            self._stderr_f.flush()
            with open(self._stderr_f.name, "rb") as f:
                return f.read()[-n:].decode("utf-8", "replace").strip()
        except Exception:
            return ""

    def shutdown(self):
        try:
            self.call("Browser.close", timeout=5)
        except Exception:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        for fd in (self._cmd_w, self._resp_r):
            try:
                os.close(fd)
            except Exception:
                pass
        try:
            self._stderr_f.close()
            os.unlink(self._stderr_f.name)
        except Exception:
            pass


_BROWSER = None


def _browser():
    global _BROWSER
    if _BROWSER is None:
        _BROWSER = _Browser()
        atexit.register(_shutdown)
    return _BROWSER


def _shutdown():
    global _BROWSER
    if _BROWSER is not None:
        _BROWSER.shutdown()
        _BROWSER = None


def _one_probe(html_path, js, width, height, settle_ms, url_suffix):
    """A single probe against the live browser. Raises _BrowserDead if the transport
    breaks (the caller relaunches once); raises RuntimeError for a real read failure."""
    b = _browser()
    uri = Path(html_path).resolve().as_uri() + url_suffix
    tid, sid = b.new_session(width, height)
    try:
        b.call("Page.navigate", {"url": uri}, sessionId=sid)
        # Condition wait on the REAL load event (not a blind sleep + subprocess timeout).
        try:
            b.wait_event("Page.loadEventFired", sid, timeout=30)
        except _BrowserDead:
            raise
        except Exception:
            pass  # some data:/edge pages never fire load; the settle + evaluate still runs
        # Small settle so the widget's own load handler finishes painting, then read once.
        time.sleep(max(settle_ms, 250) / 1000.0)
        expr = ("(function(){" + JS_PRELUDE +
                "try{return JSON.stringify((" + js + "));}"
                "catch(e){return JSON.stringify({__error:String(e)});}})()")
        r = b.call("Runtime.evaluate",
                   {"expression": expr, "returnByValue": True, "awaitPromise": True},
                   sessionId=sid)
        if "exceptionDetails" in r:
            exc = r["exceptionDetails"]
            raise RuntimeError(f"probe JS threw: {exc.get('text')} {exc.get('exception', {})}")
        val = r.get("result", {}).get("value")
        if val is None:
            raise RuntimeError("probe returned no value (page may not have rendered)")
        return json.loads(val)
    finally:
        b.close_session(tid)


def probe(html_path: str, js: str, width: int = 1200, height: int = 2400,
          settle_ms: int = 250, virtual_time: int = 6000,
          url_suffix: str = "") -> dict:
    """Render html_path in the shared headless Chrome, evaluate `js` (a JS expression
    returning a JSON-serialisable object, with TC.* helpers available) after the page's
    load event, and return the parsed result dict.

    `virtual_time` is accepted for API compatibility and is no longer needed — the harness
    waits on the real load event instead of budgeting virtual time. `url_suffix` is appended
    to the file:// URI (e.g. "?direction=Beta#detailed") so entry-parameter behaviour is
    testable against a real page load.

    A broken browser transport (a crashed/killed Chrome) is recovered by relaunching the
    browser ONCE and re-running this probe — browser-liveness recovery, never an assertion
    retry: the read itself runs once against a live browser, and a real read failure raises."""
    global _BROWSER
    last = None
    for attempt in range(1, _RENDER_ATTEMPTS + 1):
        try:
            return _one_probe(html_path, js, width, height, settle_ms, url_suffix)
        except _BrowserDead as e:
            last = e
            tail = _BROWSER.stderr_tail() if _BROWSER is not None else ""
            reason = f"{e}" + (f" | chrome stderr: {tail[-400:]}" if tail else "")
            _shutdown()  # drop the dead browser; the next attempt relaunches a fresh one
            if attempt < _RENDER_ATTEMPTS:
                sys.stderr.write(f"headless browser died ({reason}); relaunching "
                                 f"{attempt}/{_RENDER_ATTEMPTS - 1}…\n")
                sys.stderr.flush()
                time.sleep(0.3)
                continue
            raise RuntimeError(f"headless browser did not stay alive: {reason}")
    raise RuntimeError(f"probe failed: {last}")


def screenshot(html_path: str, out_png: str, width: int = 1200,
               height: int = 2400, virtual_time: int = 6000) -> str:
    """Render html_path at a concrete viewport in the shared browser and capture a PNG."""
    for attempt in range(1, _RENDER_ATTEMPTS + 1):
        b = _browser()
        tid, sid = b.new_session(width, height)
        try:
            b.call("Page.navigate", {"url": Path(html_path).resolve().as_uri()}, sessionId=sid)
            try:
                b.wait_event("Page.loadEventFired", sid, timeout=30)
            except _BrowserDead:
                raise
            except Exception:
                pass
            time.sleep(0.25)
            data = b.call("Page.captureScreenshot", {"format": "png",
                          "captureBeyondViewport": True}, sessionId=sid)["data"]
            Path(out_png).write_bytes(base64.b64decode(data))
            return out_png
        except _BrowserDead as e:
            _shutdown()
            if attempt < _RENDER_ATTEMPTS:
                sys.stderr.write(f"headless browser died ({e}); relaunching for screenshot…\n")
                time.sleep(0.3)
                continue
            raise RuntimeError(f"screenshot browser did not stay alive: {e}")
        finally:
            try:
                b.close_session(tid)
            except Exception:
                pass
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
