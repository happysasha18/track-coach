# s28 Web Panel Build — progress log

## Step 1 — reference_web_notes.json (one-source data file)
**Status: DONE**

Created `data/reference_web_notes.json`. Sources: `~/.track-coach/explore/web_facets_draft.md` (web research 2026-06-29) and `data/facet_confirmation.json` (curated 2026-06-29).

Rules applied:
- (a) All 29 existing `facet_confirmation.json` entries (direct/indirect) carried over verbatim as traits.
- (b) Draft NONE / un-tied items NOT in `facet_confirmation.json` added with `tier: "none"`:
  - Venetian Snares: "odd time signatures (7/4)" — axis null (not measurable per draft)
  - SCSI-9: "mid-tempo groove (~122–128 BPM)" (axis tempo), "warm mid-bass pulse" (axis bass_share), "moderate controlled dynamics" (axis dynamics) — all in draft as DIRECT but excluded from facet_confirmation.json curation; added as tier "none", expect null
- (c) Phrases short and faithful from draft; blurbs faithfully condensed (2–3 sentences, no new claims)
- (d) DeepChord: no NONE rows in the draft table; "no clear facet mapping" notes (lead_share, energy_build) are absence notes, not web claims — not included

```json
{
  "_note": "One-source data file for the rich web panel (SPEC §D.10.2), side page, and ★/☆ computation. Supersedes facet_confirmation.json. Source: ~/.track-coach/explore/web_facets_draft.md (web research 2026-06-29), curated 2026-06-30. Each direction: artist, genre/era, 2-3 sentence blurb (faithfully condensed from the draft, no new claims), and traits [{phrase, axis, expect, tier}]. Render rule: tier=direct AND centroid agrees by >= _confirm_z → ★; tier=indirect AND agrees → ☆; tier=none OR contradicted/unmeasured → 'web says · our tracks don't show it'. _confirm_z: minimum |centroid z| to count as confirmed.",
  "_confirm_z": 0.4,
  "DeepChord": {
    "artist": "DeepChord",
    "genre_era": "Dub techno / ambient techno, Detroit. Mid-1990s–present.",
    "blurb": "Second-wave Basic Channel sound with heavier ambient and field-recording influence than most dub techno. Rod Modell processes sounds through deep reverb, Eventide Orville, Korg Stage Echos, and spring reverbs until 'little of the original remains', producing spatial, dronal textures. Tracks always start with the ambient parts — described as 'sounds like 4am' — and the kick drum is added last as a metronome under the ambience.",
    "traits": [
      {"phrase": "slow meditative tempo", "axis": "tempo", "expect": "low", "tier": "direct"},
      {"phrase": "deep bass anchor", "axis": "bass_share", "expect": "high", "tier": "direct"},
      {"phrase": "deep sustained bass", "axis": "bass_sustain", "expect": "high", "tier": "direct"},
      {"phrase": "restrained flat dynamics", "axis": "dynamics", "expect": "low", "tier": "direct"},
      {"phrase": "wide stereo field", "axis": "stereo", "expect": "high", "tier": "direct"},
      {"phrase": "ambient pads dominate", "axis": "other_share", "expect": "high", "tier": "direct"},
      {"phrase": "long sustained pads", "axis": "pad_sustain", "expect": "high", "tier": "direct"},
      {"phrase": "dark, muted", "axis": "brightness", "expect": "low", "tier": "direct"},
      {"phrase": "dark pad timbre", "axis": "pad_bright", "expect": "low", "tier": "direct"},
      {"phrase": "sparse minimal drums", "axis": "drums_share", "expect": "low", "tier": "direct"},
      {"phrase": "very sparse arrangement", "axis": "density", "expect": "low", "tier": "direct"},
      {"phrase": "held pad, no melody", "axis": "pad_notes", "expect": "low", "tier": "direct"}
    ]
  },
  "Venetian Snares": {
    "artist": "Venetian Snares",
    "genre_era": "Breakcore / IDM / glitch, Winnipeg, Canada. Late 1990s–present.",
    "blurb": "Aaron Funk is widely credited with defining breakcore — hyper-fast (180–200+ BPM) mutilated amen breaks assembled into 'organized chaos' with obsessive rhythmic complexity. His style splits sharply by album: breakcore works are a constant terrorizing barrage, while orchestral-fusion albums (notably Rossz Csillag Alatt Született) pair shredded drums with long sampled strings from Bartók, Mahler, and Elgar.",
    "traits": [
      {"phrase": "hyper-fast tempo", "axis": "tempo", "expect": "high", "tier": "direct"},
      {"phrase": "drum-driven texture", "axis": "drums_share", "expect": "high", "tier": "direct"},
      {"phrase": "dense, busy", "axis": "density", "expect": "high", "tier": "direct"},
      {"phrase": "compressed, loud", "axis": "dynamics", "expect": "low", "tier": "direct"},
      {"phrase": "bright staccato highs", "axis": "brightness", "expect": "high", "tier": "direct"},
      {"phrase": "constant intensity", "axis": "energy_build", "expect": "low", "tier": "indirect"},
      {"phrase": "long sustained pads", "axis": "pad_sustain", "expect": "high", "tier": "direct"},
      {"phrase": "high orchestral share", "axis": "other_share", "expect": "high", "tier": "direct"},
      {"phrase": "bright orchestral pads", "axis": "pad_bright", "expect": "high", "tier": "direct"},
      {"phrase": "odd time signatures (7/4)", "axis": null, "expect": null, "tier": "none"}
    ]
  },
  "SCSI-9": {
    "artist": "SCSI-9",
    "genre_era": "Deep house / tech-house / minimal techno, Moscow, Russia. Active from ~2001.",
    "blurb": "Duo Anton Kubikov and Maxim Milyutenko, released on Kompakt and Force Tracks. Resident Advisor describes their sound as 'hypermelodic tech-house': wistful melodic synth phrases and 'bell-tone droplets' over warm bass pulses, with 'kaleidoscopic dub effects' and 'spacey reverb' in the background. Described as 'geometric but above all analog' — mathematical minimalism deliberately not sweaty or frenetic.",
    "traits": [
      {"phrase": "punchy short bass", "axis": "bass_sustain", "expect": "low", "tier": "direct"},
      {"phrase": "melodic lead synths", "axis": "lead_share", "expect": "high", "tier": "direct"},
      {"phrase": "ambient pad bed", "axis": "other_share", "expect": "high", "tier": "direct"},
      {"phrase": "wide stereo field", "axis": "stereo", "expect": "high", "tier": "direct"},
      {"phrase": "bright pad timbre", "axis": "pad_bright", "expect": "high", "tier": "direct"},
      {"phrase": "bright mix overall", "axis": "brightness", "expect": "high", "tier": "direct"},
      {"phrase": "sparse but detailed", "axis": "density", "expect": "low", "tier": "direct"},
      {"phrase": "gentle energy rise", "axis": "energy_build", "expect": "high", "tier": "indirect"},
      {"phrase": "mid-tempo groove (~122-128 BPM)", "axis": "tempo", "expect": null, "tier": "none"},
      {"phrase": "warm mid-bass pulse", "axis": "bass_share", "expect": null, "tier": "none"},
      {"phrase": "moderate controlled dynamics", "axis": "dynamics", "expect": null, "tier": "none"}
    ]
  }
}
```

## Step 2 — build_widget.py: rich panel rendering
**Status: DONE**

Changes:
- `_web_panel_html`: added `web_data=None` parameter. When provided (dict from reference_web_notes.json), renders rich mode: genre_era + blurb + full sorted trait list in three tiers (★ direct+confirmed, ☆ indirect+confirmed, "web says · our tracks don't show it" for none/contradicted). Simple mode (backward-compat) kept for when only `conf_entries` is supplied.
- `render_reference_read`: added `web_notes=None` parameter. One-source principle: when `web_notes` supplied and `confirmation` is None, auto-derives `confirmation` from direct/indirect traits so bar ★/☆ still works. Passes `focused_web` to `_web_panel_html`.
- `_ref_read_html` (disk loader): loads `reference_web_notes.json` first; falls back to `facet_confirmation.json` for bar ★/☆ only if web notes file absent.

## Step 3 — Header style (#webPanel>summary)
**Status: DONE**

Changed `#webPanel>summary` from faint 13px muted to match peer drawers:
- `color:var(--ink)` (was `var(--muted)`)
- `font-size:15px` (was 13px)
- `font-weight:620` (was absent)
- `::before` arrow now uses `color:var(--wob)` (was `opacity:.6`)

Added new CSS classes: `.web-genre-era`, `.web-blurb`, `.web-facet-nosay`, `.web-nosay` pill.

## Step 4 — Stale chip clarity (catalog.py)
**Status: DONE**

- `_stale_chip`: inner text changed from bare "stale" → "older analysis · v{wv} → re-analyse" (title tooltip kept)
- `.stale` CSS: added `white-space:nowrap` so longer label doesn't wrap
- `test_catalog.py` `StaleWidgetFlag` class: updated 5 assertions from `">stale<"` / `assertNotIn(">stale<", ...)` to check `class="stale"`, `"older analysis"`, `"v0.0.1"` instead

## Step 5 — Side page (reference_notes.html)
**Status: SKIPPED**

The existing `~/.track-coach/explore/reference_notes.html` is a complex hand-crafted HTML page with its own light-theme CSS, many CSS classes, and rich per-artist layout. Faithfully regenerating it from the new JSON would require a dedicated script matching all existing structure exactly. Risk of breaking the existing content outweighs the benefit for this session. The widget panel is the primary deliverable per the task. Noted for a future session: write a `scripts/build_reference_notes.py` that generates the side page from `data/reference_web_notes.json`.

## Step 6 — Tests
**Status: DONE**

Added `WebPanelRichRendering` class (9 tests) to `test_reference_read.py`:
- `test_blurb_in_panel` — blurb text in HTML
- `test_genre_era_in_panel` — genre_era in HTML
- `test_star_row_appears_for_confirmed_direct` — ★ glyph for direct+confirmed
- `test_halfstar_row_appears_for_confirmed_indirect` — ☆ glyph for indirect+confirmed
- `test_nosay_row_appears_for_none_tier` — "web says" pill for none-tier (⟨D-30⟩ resolved)
- `test_nosay_row_appears_for_contradicted_direct` — contradicted direct → web-facet-nosay
- `test_star_row_before_nosay_row` — ★ row BEFORE "web says" row in HTML (sort order)
- `test_panel_absent_when_no_web_content` — empty blurb+traits → panel absent
- `test_bar_star_derived_from_web_notes` — one-source: bar ★ auto-derived from web_notes
- `test_panel_present_when_only_nosay_traits` — panel present even when all traits land in tier 3

Updated `StaleWidgetFlag` in `test_catalog.py` — 5 existing assertions updated.

## Step 7 — Version + CHANGELOG
**Status: DONE**

TC_VERSION: 0.9.1 → 0.9.2
CHANGELOG ## [0.9.2] — 2026-06-30 added.

## Step 8 — Suite run
**Status: DONE — GREEN**

```
477 passed, 2 skipped in 1.57s
```
(2 skipped = Lazy Sparks disk-gated tests, always skipped in CI)
No regressions.
