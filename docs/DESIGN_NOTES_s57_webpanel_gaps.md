# Design review — web panel + panel gaps (the owner, 2026-07-05, pre-restart)

Durable record of the owner's review of the 1.0.0 render so a memory wipe loses nothing. **Scope he set:
touch ONLY the web-panel plaque + the vertical panel gaps — nothing else.** Fixes go through the method
(spec-author → prove → matrix → test → code), per feature. Grounded facts below (measured / read from code),
not memory.

## Q0 — "Wobble Drift has no similar tracks — wasn't it Venetian Snares?" — ANSWERED, not a bug

- The catalog shows Wobble's LEANS-TOWARD as "no close direction yet". Its widget has NO web panel and its
  `#refRead` shows the no-close state (verified in `analysis_widget_v1.0.0.html`).
- **By design:** `catalog.py:37` — "close=green, mid=amber, **far → 'no close direction yet'** (grey, no
  red)"; D-INV-27 never pads with weak/far filler. So Wobble's nearest reference (historically Venetian
  Snares) now sits in the FAR band, and the catalog withholds a far match rather than surfacing a weak lean.
- **NOT in scope to change.** If the owner wants Venetian to count as a real (amber) lean for Wobble, that is
  a far/mid BOUNDARY CALIBRATION decision (the 2026-06-25 note had "Wobble→Venetian amber"; the band boundary
  has since moved it to far). Flag for a separate tuning pass — do not touch under this scope.

## Q1 — Panel gap hierarchy is INVERTED (real) — this is F5 / DS-INV-9

- **Measured** (Lazy Sparks widget, Detailed, panels open, headless probe): INTER-panel gap (top-level
  `#webPanel` bottom → `#evidence` top) = **24 px**; INTRA-panel gap (`#rhyPanel` → `#notePanel`, both INSIDE
  `#evidence`) = **30 px**. So internal (30) > external (24) — the reverse of correct hierarchy (between
  separate panels should be LARGER than between sub-sections of one panel).
- **Root cause:** ONE `.tc-panel` class serves BOTH levels — top-level panels AND the sub-panels nested
  inside `#evidence` (`build_widget.py:3284` `#rhyPanel` / `:3291` `#notePanel` both `class="tc-panel"`).
  Per-id overrides exist (`#webPanel{margin:10px 0 0}`, `#evidence,#catalog{margin:24px 0 0}`) but nested
  sub-panels get no smaller-gap role. This is exactly DS-INV-9's unbuilt `--gap` (within a group) vs
  `--rhythm` (between sections) split (F5, deferred POST-1.0).
- **FIX direction (clear):** inter-panel gap must be clearly LARGER than intra-panel. **Exact px values are
  the owner's taste** (F5 was deferred precisely because which of 5/6/7 → 8 is the owner's call). Proposed:
  intra (sub-panels in evidence) → ~14-16 px; inter (between top-level panels) → ~32-40 px. Awaiting the owner's numbers.

## Q2 — Web-panel brightness hierarchy INVERTED (real) — "letters brighter than the section heading"

- Token brightness ladder: `--ink #e8ecf5` (brightest) > `--ink-dim #aeb6c8` > `--muted #8b94a8` (dimmest).
- Section headings are DIMMER than the body they head: `#webPanel .rn-section-label` ("Your measurement backs
  these up" / "Web describes these") and `.tc-rn-sources-label` ("Sources") = **`--muted`, 10 px** — but the
  body under them, `.tc-rn-blurb` and `.rn-trait-row` (the ★ confirmed traits), = **`--ink` (brightest),
  12.5 px**. So content out-shouts its own heading. (`build_widget.py:2990-3008`.)
- **FIX (clear):** raise the section headings so a heading is never dimmer than its body — lift
  `.rn-section-label` / `.tc-rn-sources-label` from `--muted` to `--ink` (keep the uppercase+bold+small role
  that distinguishes them). Token choice is the correct fix, minimal taste.

## Q3 — Sources don't read as a bulleted list OR as links

- `#webPanel .tc-rn-sources{list-style:none}` (no marker) and `.tc-rn-sources a{color:--muted;
  text-decoration:none}` — muted, no underline, no icon → doesn't read as a link, and (unlike the ★-led
  "your measurement" list) has no leading marker so doesn't read as a list. (`build_widget.py:3009-3011`.)
- **FIX:** give each source a link affordance — an external-link icon (↗) + link treatment (underline and/or
  a link-ish colour). The owner's steer: maybe make a link icon. Exact icon/treatment = the owner's taste.

## Q4 — Everything in the panel is small (taste)

- Panel type sizes: artist 13 px, blurb/traits 12.5 px, genre/realname/webonly/sources 11.5 px, section
  labels + sources label 10 px, footnote 10.5 px. The owner: "all good except the really small font — is that
  intended?" **The owner's call** whether to bump the base up (e.g. blurb/traits 12.5→13, labels 10→11).

## Q5 — MERGE the reference read + web panel into ONE panel with ONE selector (the owner, evolving, 2026-07-05)

This SUPERSEDES the earlier "add a second selector to the web panel" idea. Final ask:
- **Merge `#refRead` (the per-facet centroid read — "You vs your closest match", the diverging bars) and
  `#webPanel` ("What the web says about ⟨artist⟩") into ONE panel** — grouped like the lower panels (the
  evidence sub-panels are under one drawer).
- **ONE shared direction selector** (the existing up-to-3 `.reftab` mechanism, `build_widget.py:2749-2765`)
  drives BOTH sub-sections at once: pick SCSI-9 → shows SCSI-9's bars AND SCSI-9's web notes.
- **Selector shown only if >1 nearest direction** (if there is more than one nearest track). Exactly 1 → no selector,
  just that direction's content. (Today `#refRead` builds tabs via `_ref_read_html`; check the 1-direction
  case hides the tab row.)
- **Empty handling (Q-earlier B, folded in):** if the selected direction has NO web notes → show the bars,
  HIDE the web sub-block (don't show an empty "what the web says"). If there is NO close direction at all →
  the whole merged panel is ABSENT (not an empty plaque). VERIFIED current state: `_web_panel_html` already
  returns "" when blurb+traits empty, and Fragile/Wobble widgets render ZERO web panels (absent). The merge
  must preserve "absent when empty" at both the whole-panel and per-direction-web level.

**This is a SURFACE RESTRUCTURING, not cosmetics** — it changes §D.10.3 read order, the one-surface-one-name
map (two names → one), `USER_SURFACES` (today registers `refRead` + `webPanel` separately; INV-46 registry),
INV-18/22 hide-set (`{#refRead,#webPanel}`), D-INV-28 (selector ownership/ephemerality), D-INV-29/30, the
completeness gate test_22/test_23, and pass-3's P3-1 viewport test. MUST go through spec-author →
product-prover → matrix → test → code, as ONE feature, proven not to break the others. Do it AFTER (or folded
with) the cosmetic fixes Q1-Q3, one at a time.

### Open DESIGN decisions for the owner (needed before speccing):
- **Internal order** of the merged panel: selector → per-facet bars → web notes? (measurement first, web
  context second — matches today's tonal→refRead→webPanel order). Confirm.
- **Panel title** for the merged surface (e.g. "You vs your closest match" with the web notes as a labelled
  sub-section inside). The owner's wording call.
- Whether the web sub-section keeps its own collapse, or the whole merged panel is one collapsible.

## DECIDED by the owner 2026-07-05 (answers to the 3 questions) — these are the build spec

1. **Merged-panel internal order:** TITLE → SELECTOR (only if >1 direction) → then TWO collapsible
   sub-sections, both OPEN by default: (a) the centroid per-facet read (bars), then (b) the web notes.
   **The web sub-section is OPTIONAL** — absent when the selected direction has no web notes (may be nothing
   at all). So structurally the merged panel is a container (like `#evidence`) holding two nested
   `tc-panel` collapsibles, driven by one selector.
2. **Font (not slapdash — align to the established scale):** the widget's clean scale (design doc
   2026-07-02) is kicker 10.5 · body 12/13 · … — but the `--fs-*` TOKENS were never built (0 in code;
   verified). The reference panel's 10 / 11.5 / 12.5 are the "scattered fractional" sizes the audit flagged.
   FIX (in-panel scope only): snap the panel's fonts UP to the established whole-number scale — section
   labels/kicker 10→11, footnote 10.5→11, blurb/traits 12.5→13, genre/realname/webonly/sources 11.5→12.
   Do NOT roll out a widget-wide type-token refactor (out of fence). Fixes both "too small" (Q4) together.
3. **Gaps (from the design system):** DS-INV-9 (SPEC §I.2) already DESIGNS the two roles — `--gap 8/12/16`
   (within a group) and `--rhythm 28/44` (between sections) — but they were never built (F5). The owner:
   take it from the design system. So BUILD the minimal slice: sub-panels within a container use the smaller
   group `--gap` (→ ~12-16), top-level panels use the larger section `--rhythm` (→ ~28), so inter > intra
   (fixes the 24<30 inversion) with HIS pre-approved spec values — not a guess. Scope: the panel-to-panel +
   sub-panel gaps only (NOT a full 13-literal normalization — that broader F5 stays future).

Clear fixes NOT needing more input: Q2 brightness (section labels `--muted`→`--ink` so heading ≥ body),
Q3 sources (add ↗ external-link icon + link affordance).

## PIPELINE PLAN (his rule: spec-author → product-prover → matrix → test → code, one feature at a time)
Order (bugfixes before the feature, per convergence rule): (1) cosmetic fixes Q2 brightness + Q3 sources +
font-snap + gap-hierarchy → (2) the Q5 MERGE (surface restructuring) LAST, since it's the structural one
that must be proven not to break the gate/registry/read-order. Each updates SPEC §D.10.2/.3 + §I.2, re-proved,
matrix rows, tests (browser-level for visibility/layout), then code. Suite must stay green; widget bump PATCH.

## What NOT to touch (the owner's fence): everything except the web-panel/reference plaque (`#refRead` + `#webPanel` /
`render_reference_notes` / `_ref_read_html`) and the panel vertical gaps. No credibility, cards, player,
catalog data, etc. (The merge necessarily touches `#refRead` too — that is now IN scope as the merge target.)
