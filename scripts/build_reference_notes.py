#!/usr/bin/env python3
"""Side-page generator for reference artist notes (§D.10.2 one-source renderer).

Reads:  data/reference_web_notes.json
Writes: ~/.track-coach/explore/reference_notes.html

Uses the shared `render_reference_notes()` from build_widget.py, so the in-widget dark panel
and this light-theme side page share one source AND one renderer. Only the CSS theme differs.

Usage (from skill root):
    python3 scripts/build_reference_notes.py
"""
import json
import os
import sys
from pathlib import Path

# Resolve paths relative to this script's location
SKILL_DIR = Path(__file__).resolve().parent.parent
DATA_DIR  = SKILL_DIR / "data"
NOTES_JSON = DATA_DIR / "reference_web_notes.json"

DEFAULT_OUT = Path(os.path.expanduser("~/.track-coach/explore/reference_notes.html"))

sys.path.insert(0, str(SKILL_DIR / "scripts"))
from build_widget import render_reference_notes  # noqa: E402


# ── Light-theme CSS for the same tc-rn-* classes ─────────────────────────────
LIGHT_CSS = """
:root {
  --bg:    #f8f9fb;
  --card:  #ffffff;
  --ink:   #1d2026;
  --muted: #6b7280;
  --line:  #e3e6ea;
  --good:  #1e7e4d;
  --warn:  #92620a;
  --accent:#2563c9;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--ink);
  font: 14px/1.5 -apple-system, "SF Pro Display", Inter, "Segoe UI", sans-serif;
  padding: 32px 20px;
}
h1 {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 6px;
}
.subtitle {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 32px;
}
.artist-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 20px 24px;
  margin-bottom: 20px;
  max-width: 820px;
}
/* tc-rn-* light theme */
.tc-rn-head    { margin-bottom: 3px; }
.tc-rn-artist  { font-size: 15px; font-weight: 700; color: var(--ink); }
.tc-rn-realname { font-size: 12.5px; color: var(--muted); margin-left: 6px; font-style: italic; }
.tc-rn-genre   { font-size: 12px; color: var(--muted); margin: 3px 0 10px; font-style: italic; }
.tc-rn-note {
  border-left: 3px solid var(--warn);
  padding: 6px 12px;
  margin: 0 0 12px;
  font-size: 12.5px;
  color: #6b4a10;
  background: #fffbf0;
  border-radius: 0 6px 6px 0;
  line-height: 1.5;
}
.tc-rn-blurb {
  font-size: 13px;
  color: var(--ink);
  margin-bottom: 14px;
  line-height: 1.65;
}
.tc-rn-traits-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: var(--muted);
  margin-bottom: 8px;
}
.tc-rn-traits {
  list-style: none;
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.tc-rn-trait {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  font-size: 12.5px;
  color: var(--ink);
}
.tc-rn-trait-title { flex: 1; line-height: 1.4; }
.tc-rn-pill {
  flex: 0 0 auto;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.tc-rn-pill.is-direct   { background: #d1fae5; color: var(--good); }
.tc-rn-pill.is-indirect { background: #d1fae5; color: var(--good); opacity: .75; }
.tc-rn-pill.is-webonly  { background: #f1f2f4; color: var(--muted); }
.tc-rn-pill.is-na       { background: #f1f2f4; color: var(--muted); font-style: italic; }
.tc-rn-sources-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: var(--muted);
  margin-bottom: 6px;
}
.tc-rn-sources {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.tc-rn-sources a {
  font-size: 12px;
  color: var(--accent);
  text-decoration: none;
}
.tc-rn-sources a:hover { text-decoration: underline; }
/* Variant A readable layout (2026-07-04) — glyph-led confirmed rows + muted web-only group */
.rn-section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: var(--muted);
  margin: 12px 0 7px;
}
.rn-webonly-label { margin-top: 16px; }
.rn-webonly-qualifier { font-weight: 400; text-transform: none; letter-spacing: 0; opacity: .75; }
.rn-confirmed-list {
  list-style: none;
  margin: 0 0 4px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.rn-trait-row {
  display: flex;
  gap: 9px;
  align-items: baseline;
  font-size: 12.5px;
  color: var(--ink);
  line-height: 1.5;
}
.rn-trait-glyph {
  flex: 0 0 16px;
  text-align: center;
  color: var(--good);
  font-size: 13px;
}
.rn-trait-glyph.rn-trait-glyph-indirect { opacity: .8; }
.rn-trait-text { flex: 1; line-height: 1.4; }
.rn-webonly-group {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.65;
  margin: 0 0 12px;
  opacity: .85;
}
.rn-footnote {
  font-size: 11px;
  color: var(--muted);
  opacity: .72;
  margin: 12px 0 0;
  font-style: italic;
  line-height: 1.5;
}
"""


def build(out_path: Path = DEFAULT_OUT) -> None:
    with NOTES_JSON.open(encoding="utf-8") as f:
        data = json.load(f)

    # Collect artist entries (skip metadata keys starting with _)
    entries = [v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)]

    cards_html = ""
    for entry in entries:
        body = render_reference_notes(entry)
        cards_html += f'<div class="artist-card">{body}</div>\n'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reference Artist Notes — Track Coach</title>
<style>
{LIGHT_CSS}
</style>
</head>
<body>
<h1>Reference Artist Notes</h1>
<p class="subtitle">One-source view — generated from <code>data/reference_web_notes.json</code>
by <code>scripts/build_reference_notes.py</code>. Same renderer as the in-widget panel (§D.10.2).</p>

{cards_html}
</body>
</html>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Reference notes written: {out_path}  ({len(entries)} artists)")


if __name__ == "__main__":
    build()
