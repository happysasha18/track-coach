# Recon: Read Redesign — Session 28
Generated: 2026-06-29 by sonnet-worker (read-only; no changes made)

---

## Q1 — Source Audio Availability

### What each widget records (D.meta.audio in JS blob)

| Track | Audio file recorded in widget | ALS recorded |
|---|---|---|
| Lazy Sparks | `Total_Reboot_-_Lazy_Sparks_edit2026.wav` | `Lazy_Sparks_Live_12.2.als` |
| Shared Memories | `Total_Reboot_-_Shared_Memories_[2026_version].wav` | `Shared_Memories_Live_12.2.als` |
| Wobble Drift | `Total_Reboot_-_Wobble_Drift_[v0.6.2].wav` | `Fragile_Live12.1.1_minimal.als` |

Source: in each widget, `const META=D.meta||{}` → `META.audio` / `META.als`.
The JS populates `#srcmeta` via `META.audio` and `META.als` fields (build_widget.py:2878–2886 area).

### Disk existence — exact canonical path for each

**Lazy Sparks** (113 MB, wav):
- `/Users/sashaabramovich/Desktop/Projects/Lazy_Sparks/Lazy_Sparks Project/Total_Reboot_-_Lazy_Sparks_edit2026.wav` — EXISTS
- Duplicate also at: `/Users/sashaabramovich/Desktop/Projects/Set-2026-basedon-Set1c-dubsteppish Project/Total_Reboot_-_Lazy_Sparks_edit2026.wav` — EXISTS

**Shared Memories** (85 MB, wav):
- `/Users/sashaabramovich/Desktop/Projects/Shared Memories Folders/Shared_Memories/Shared_Memories Project/Total_Reboot_-_Shared_Memories_[2026_version].wav` — EXISTS
- Duplicate also at: `/Users/sashaabramovich/Desktop/Projects/Set-2026-basedon-Set1c-dubsteppish Project/Total_Reboot_-_Shared_Memories_[2026_version].wav` — EXISTS

**Wobble Drift** (76 MB, wav):
- `/Users/sashaabramovich/Desktop/Projects/Fragile_Live12.1.1 Project/Total_Reboot_-_Wobble_Drift_[v0.6.2].wav` — EXISTS

### Re-render verdict
All three audio files exist on disk. Re-render of all three widgets is possible with no recovery work needed.

---

## Q2 — Simple/Detailed View-State Mechanism

### Body class
- Simple mode: `document.body.classList.toggle("simple", v==="simple")` — sets `body.simple`
- Detailed mode: body class `simple` is absent (no separate `body.detailed` class)
- Quick mode: `body.quick` (server-side via `__BODYCLASS__`); toggle JS bails early when `D.mode==="quick"`

### Toggle control (build_widget.py lines 2871–2899)
```js
// lines 2871–2899 (verbatim)
// ── Simple⇄Detailed toggle. PURE presentation: flips a body class that hides/shows
// already-embedded panels and re-filters the story lanes. No network, no recompute.
(function(){const tg=document.getElementById("viewToggle");if(!tg)return;
 if(D.mode==="quick")return;
 tg.setAttribute("aria-label",T.view_aria||"Detail level");
 tg.innerHTML=`<button data-v="simple">${T.view_simple||"Simple"}</button>`+
  `<button data-v="full">${T.view_full||"Detailed"}</button>`;
 let _viewInited=false;
 function apply(v){document.body.classList.toggle("simple",v==="simple");
  tg.querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.v===v));
  if(v==="simple"&&window.__resetMix)window.__resetMix();
  try{localStorage.setItem("tc_view",v);}catch(e){}
  if(_viewInited){try{history.replaceState(null,'',v==='simple'?'#simple':'#detailed');}catch(e){}}
  window.dispatchEvent(new Event("resize"));}
 tg.querySelectorAll("button").forEach(b=>b.onclick=()=>apply(b.dataset.v));
 // initial view: ALWAYS open Simple (the calm default) unless the URL hash explicitly
 // asks for Detailed (#full/#detailed). We deliberately do NOT restore a previous
 // Detailed choice from localStorage — every fresh open is calm; the toggle still works
 // in-session.
 let init="simple";const h=(location.hash||"").toLowerCase();
 if(h.indexOf("full")>=0||h.indexOf("detail")>=0)init="full";
 apply(init);_viewInited=true;})();
```

### URL hash behaviour
- On load: hash `#full` or `#detailed` → opens Detailed; anything else (including bare `#simple`) → opens Simple
- On toggle (after init): `history.replaceState` writes `#simple` or `#detailed`
- `_viewInited` flag prevents URL mutation during the initial `apply()` call

### localStorage / sessionStorage
- `localStorage.setItem("tc_view", v)` — written on every toggle (build_widget.py:2886)
- `localStorage` is NOT read back on page load (deliberately; comment at 2894: "We deliberately do NOT restore a previous Detailed choice from localStorage")
- `sessionStorage`: zero uses anywhere in build_widget.py or catalog.py (confirmed by grep)

### Catalog page view concept
- `catalog.py` generates a single flat view with no Simple/Detailed toggle
- Sort, filter (mode/quality chips), and one-button preview player are present, but no view-level toggle

---

## Q3 — Section Order in Widget Body

Top-to-bottom emission order in `build_widget.py` HTML template (lines ~2715–2829):

| # | Section | ID / element | Line |
|---|---|---|---|
| 1 | Header / topbar (title, viewToggle, brandkick) | `.topbar` | 2717 |
| 2 | Source metadata (audio file, analyzed_at) | `#srcmeta` | 2726 |
| 3 | Mode note (quick-only explainer) | `__MODENOTE__` | 2728 |
| 4 | Vitals (BPM, key, duration, LUFS etc.) | `#vitals` | 2732 |
| 5 | Verdict (calm headline) | `#verdict` | 2736 |
| 6 | **Track Story + Player** (arc canvas + stemlanes + playback controls) | `#storyPanel` | 2739 |
| 7 | **Recommendations** (cards, Simple shows timecoded only) | `#recsPanel` | 2759 |
| 8 | **The READ** (producer's narrative, server-side rendered prose) | `#readPanel` / `#readBody` | 2767 |
| 9 | **Reference READ** (per-facet bars vs centroid; ★/☆ glyphs) | `__REFREAD__` → `#refRead` | 2775 |
| 10 | **Tonal Balance** (octave-band spectrum canvas) | `#tonalPanel` | 2779 |
| 11 | Evidence drawer (`<details>`, collapsed by default) | `#evidence` | 2785 |
| 11a | — Arrangement (project clips canvas) | `#arrPanel` | 2788 |
| 11b | — Automation (intention vs result) | `#autoPanel` | 2795 |
| 11c | — Stem↔Track map | `#mapPanel` | 2801 |
| 11d | — Rhythm quality | `#rhyPanel` | 2807 |
| 11e | — Notes / transcription | `#notePanel` | 2813 |
| 12 | Catalog (collapsed `<details>`) | `#catalog` | 2823 |
| 13 | Footer | `#foot` | 2829 |

Key notes on targeted sections:
- **(a) Producer's READ** — #8 above, `#readPanel` at line 2767. Server-side rendered via `__READBODY__` placeholder; `_read_html()` converts markdown to HTML. Comment: "Detailed-only via CSS (body.simple #refRead)" — the READ itself is ALWAYS visible; only `#refRead` is Detailed-only.
- **(b) Tonal Balance** — #10 above, `#tonalPanel` at line 2779. Always visible (not gated). Comment in source: "pulled OUT of the Evidence drawer (Sasha: 'он прикольный') so it's always visible."
- **(c) Reference READ vs centroid (per-facet bars)** — #9 above, `__REFREAD__` at line 2775. Emitted server-side by `_ref_read_html(run_dir)`. Gated: Detailed-only via CSS `body.simple #refRead{display:none!important}` (line 2514).
- **(d) Web ★/☆ plaque** — lives INSIDE the Reference READ panel (#9). The ★/☆ glyphs appear on individual facet bar rows. No separate standalone web-text panel in the widget (see Q4).

---

## Q4 — Web ★/☆ Plaque: What Actually Renders

### In the per-track widget (build_widget.py)

The `#refRead` panel (rendered by `render_reference_read`, lines 2308–2417) contains:
1. "How you sit vs the direction" heading
2. "Leans toward **[direction_name]**" with distance summary (Closest on / Furthest on)
3. Per-facet bar rows: category chip | facet label (with ★ or ☆ if confirmed) | bar | words (e.g. "noticeably lower")
4. A legend at the bottom explaining ★ and ☆:
   - `★` = "The web describes this as the artist's signature — and our measurement of their tracks confirms it directly."
   - `☆` = "The web describes it — our measurement confirms it indirectly but soundly."
   - (no mark) = normal facet, no web signature

**The widget does NOT contain any web-sourced artist description prose.** No "what the web says about this artist", no "dub techno / Detroit", no narrative about the artist's style. Only the ★/☆ glyphs and their legend.

The relevant emit code (lines 2399–2416):
```python
legend_html = (
    '<div class="refread-legend">'
    '<span><b>★</b> The web describes this as the artist\'s signature — and our measurement of their tracks confirms it directly.</span>'
    '<span><b>☆</b> The web describes it — our measurement confirms it indirectly but soundly.</span>'
    '<span>(no mark) A normal facet — not a web-described signature.</span>'
    '<span><span class="refread-chip">char</span> Character axis — assessed without loudness weighting...</span>'
    '</div>'
)
return (
    '<div id="refRead" class="panel">'
    '<h2>How you sit vs the direction</h2>'
    + tabs_html
    + ''.join(panels_html)
    + tab_js
    + legend_html
    + '</div>'
)
```

### The separate web digest page

`~/.track-coach/explore/reference_notes.html` (499 lines) — contains the full web research digest:
- Title: "Reference Artist Notes — Web research digest — 2026-06-29 — Track Coach"
- Three artists covered: **DeepChord** (Rod Modell), **Venetian Snares**, and **SCSI-9**
- Each artist has: genre + era context, technique notes, and a bulleted list of style traits each marked with ★ ("measurement confirms") or "– web says; our tracks don't show it" (contradicted or unmeasurable)
- This is a standalone human-readable reference page, not linked from the per-track widget

### Gate explaining "can't see the internet info panel"

The GATE is at **build_widget.py line 2514**:
```css
body.simple #refRead{display:none!important}
```

The widget opens in **Simple mode by default** (line 2897: `let init="simple"`). In Simple mode, the entire `#refRead` panel is `display:none`. Since #refRead is the ONLY place in the widget that references web-described traits (even via ★/☆ glyphs), a user in Simple mode sees NOTHING from the web research — not even the legend explaining what ★ means.

Additionally, the web-sourced artist description prose is not in the widget at all — it lives only in the separate `reference_notes.html` page. So even in Detailed mode, the user sees only "Leans toward X" + facet bars, not "DeepChord is dub techno from Detroit with lava-lamp stasis tracks."

---

## File paths cited
- Widgets: `~/.track-coach/library/widgets/Total_Reboot_*.html`
- Build script: `~/.claude/skills/track-coach/scripts/build_widget.py`
- Catalog script: `~/.claude/skills/track-coach/scripts/catalog.py`
- Data: `~/.claude/skills/track-coach/data/reference_directions.json`
- Data: `~/.claude/skills/track-coach/data/facet_confirmation.json`
- Web digest: `~/.track-coach/explore/reference_notes.html`
