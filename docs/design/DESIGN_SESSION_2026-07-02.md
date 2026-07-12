# Design-system session — decisions to vivify into code (2026-07-02, v3)

Source: the owner's design session on claude.ai/design (project `track-coach`,
aae67990-57e7-472c-877b-5a1570411df3). Four workspace artifacts hold the reasoning
(`Token revision` = colour, `Layout and grid` = layout, `Motion and states` = motion+states,
`Drift toward a system` = radii+segmented control). Those artifacts are a SPEC, not edits to the
design-system source files, so `/design-sync` does NOT pull them — they are applied here in code.

STATUS: **SETTLED (v3, 2026-07-02).** The owner pasted the full 4-artifact changelog; ALL taste
calls are decided by him (--bright kept · tc-panel animates · reftabs→segment · radii snap 6/12 ·
no --radius-xs · near-whites→ink/ink-dim/muted · reds→--bad + magma stays · stems stay categorical).
The ONE remaining open item is §8 typography (weights/sizes) — he explicitly returns the taste there
to design; do the same code-audit as colour, apply safe mechanical snaps, FLAG the weight-placement
calls for him. This file is the implementable record; it mirrors his latest paste (v3).

The pull (done 2026-07-02): Claude Design project == seed == the current 11 code tokens; nothing
to bring back structurally (only cosmetic entity→unicode normalisation in 2 files). Real work = below.

Real code targets: widget `:root` at `scripts/build_widget.py:2705`; catalog `PALETTE` at
`scripts/catalog.py:41` (+ `_SIM_COL` at :40).

---

## 0. Single token source (DO FIRST — root of the drift)

catalog.py already diverged from the widget on the SAME roles:
- `ink`: catalog #e8ecf6 vs widget #e8ecf5
- `line`: catalog #2a3142 vs widget #262c3c

While one role lives as two values in two files, any cleanup re-drifts. Collapse to ONE token
source that both files import. Canon = the WIDGET values (#e8ecf5 / #262c3c) — all components use
them; catalog is the deviation. (Confirmed by code inspection this session — matches the finding.)

---

## 1. Colour

Neutrals (`--bg --panel --panel2 --line --ink --muted`) and `--wob` — UNCHANGED.

States:
- `--good #46d39a`, `--warn #ffb454`, `--bad #ff6b6b` — the base triple.
- `--bright (#ffd166)`: **RESOLVED 2026-07-02 — the owner's call (v3 paste): KEEP as its own token,
  role = "highlight/attention" (yellow ≠ amber). Do NOT merge into `--warn`.**
  Implementation reconciliation (grepped all 14 `#ffd166` by deed): the hex serves TWO roles that
  coincide by value — keep them separate at vivify time:
  · **UI `--bright` (the "attention" role → `var(--bright)`):** the ★ climax marker (`build_widget.py:3393`),
    the meter-change marker lines + labels (:3416-17), the reference-overlay dashes (:3550), favicon bars.
  · **Data-viz literals (STAY as raw hex — the "dedup does NOT touch the stems" rule):** the `lead` stem colour
    (:1582, :3481, :3577, :3722), Demucs `other` (:3614), the Brightness data series (:1835, :1905),
    the drum `snare` (:3777). These coincide with #ffd166 but are categorical/series — leaving them raw
    is correct (tokenising them would falsely couple stems to a UI role).

Data-viz — TWO distinct sets, BOTH outside the UI palette, BOTH left untouched (v3):
- **Arc / frequency** — colormap magma/viridis (#4cc9f0 … #fcfdbf #8c2981 #3b0f70), a perceptual
  gradient. **DO NOT tokenise.**
- **Stems** — fixed CATEGORICAL colours (real, from `build_widget.py`):
  `kick #ff5d73 · bass #a78bfa · drums #4cc9f0 · hats #5ad1c2 · chord #46d39a · lead #ffd166 · other #8b94a8`.
  Document as a separate plaque group, leave as-is.
  **⚠ CRITICAL for the dedup step:** some stems share a hex with a UI token (bass=--wob, chord=--good,
  other=--muted, lead=#ffd166/--bright, drums=cyan, hats=teal, kick=pink-red) — but the ROLE differs.
  The "exact-dupe → var(--…)" pass must NOT touch the stem literals: keep #5ad1c2 (hats) and #4cc9f0
  (drums) DIFFERENT; do NOT merge #ff5d73 (kick) into --bad. Tokenising stems would falsely couple
  data categories to UI roles.
- Separately: clip types (MIDI = purple, audio = cyan) are a categorical viz-pair; may be named
  (`--clip-midi` / `--clip-audio`) if wanted, but that is viz, not UI.

Near-dupe raw hex ("needs an eye" bucket — taste calls, DECIDED here):
- 8 near-whites (#cfd6e6 #eef1f8 #cdd5e6 #c3cbdc #aeb6c8 #aab3c7 #a0a8bc #8b93a7) → text ladder:
  `--ink #e8ecf5` / `--ink-dim ~#aeb6c8` / `--muted #8b94a8`. 8 → 3.
- Reds (#ff5d73 #ff6b9d #de4968 #e0594f): UI-red → `--bad`; magma-reds stay in the gradient.
- Exact mechanical dupes (#a78bfa×14, #ffd166×13, #8b94a8×10, #46d39a×8, #0c0e14×8 …) → plain
  `var(--…)`, no decision.

Colour drift in components (hardcoded past the palette — reduce to tokens):
- `#6fdfb8` → `--good`
- `#ffb13f` (reference star) → `--warn`
- category backgrounds `#3a4060 / #2e3a52 / #3a3040 / #3a2832` → derive from `--panel2`/`--line`
  or one service token.

rec-card semantics: left stripe = severity `good / warn / bad` (ADD a `bad` variant, red).
`--wob` is the neutral/brand accent, NOT an alarm level.

---

## 2. Layout & Grid (new layer — these tokens do not exist yet)

Container widths: `--w-prose: 640px` (text, advice panels) · `--w-content: 1120px` (main column) ·
`--w-full: 100%` (ribbons, graphs).

Card grid (no media queries):
```
grid-template-columns: repeat(auto-fill, minmax(<min>px, 1fr));
```
cols = `floor((width + gap) / (minCard + gap))`; `<min>` chosen from desired cols at target window.
- Fluid sizes → `clamp(min, preferred, max)` instead of breakpoints.
- A component in variable-width slots → container query (`@container`), not media.

Spacing — split the one row into two roles:
- `--gap: 8 / 12 / 16` (within a group)
- `--rhythm: 28 / 44` (between sections)

---

## 3. Motion (new tokens)

- `--dur-fast: 120ms` (hover, highlight, small colour change)
- `--dur-base: 180ms` (appear, state change, expand)
- `--ease: ease-out` (no springs)
- Replace the `.12s / .15s` scatter in components with these.

## 4. States — one ladder for buttons / segments / fields

- `rest` — muted text / thin border
- `hover` — text → `--ink`, or the accent fills `--wob`; transition `--dur-fast`
- `focus` — ring: `box-shadow: 0 0 0 3px rgba(167,139,250,.4)`
- `active` — `transform: translateY(1px)`
- `selected` — fill `--wob` + text `#0c0e14`, bold
- `disabled` — `opacity: .45`, `cursor: not-allowed`

---

## 5. Radii (5 random → scale of 4)

- Snap `6 / 8 / 9 / 11` → `--radius (10)`
- Add `--radius-xl: 18` (for `.tc-panel`, currently ad-hoc 18)
- Keep `--radius-lg: 14`, `--radius-pill: 20`
- Result: `10 / 14 / 18 / 20`

## 6. Segmented control — one instead of three

Merge `.seg`, `.viewtoggle`, `.reftabs` into one:
- container: `border: 1px solid --line`, `border-radius: --radius (10)`, `overflow: hidden`
- buttons: padding `9px 14px`
- `selected`: fill `--wob` + text `#0c0e14`, bold
- `rest`: transparent bg, text `--muted`; `hover` → `--ink`; transition `--dur-fast`

---

## 7. Per-component pass — all 10 (the layer not previously reconciled)

Status key: ✅ decided · ◑ partial · ✎ taste. **All taste calls here are DECIDED (v3).**

1. **buttons** ✅ — `.pbtn` (accent), `.pmini/.backlink/.copen` (ghost), `.cplay` (round). Apply the
   state ladder (§4); radius 9/8 → `--radius (10)`; `.cplay` stays 50%.
2. **chips** ✅ — `.pill` → `--radius-pill`; `.chip-level` close/mid/far = good/warn/bad (already right);
   `.chip-char` → `--radius (10)`. Keep the `color-mix` tints. Static — no hover.
3. **collapsible-panel (tc-panel)** ✅ — radius 18 → `--radius-xl`; nested 12 → `--radius-lg (14)`;
   ▸/▾ marker = closed/open state on `--wob`; expansion ANIMATES height (`--dur-base 180ms`), not the
   native jump; nested level background `rgba(0,0,0,.12)`.
4. **panel** ✅ — `.panel/.panel2` → `--radius-lg (14)`; backgrounds `--panel/--panel2`; kicker `--wob`; no states.
5. **player-transport** ◑ — `.pbtn/.pmini` as in buttons; `.ptime` tabular-nums `--muted`; `.seekbar`
   (custom range): track `--panel2` + fill `--wob`, thumb `--wob` + ring `rgba(wob)`; `.pstem` mute.on
   = `--bad`, solo.on = `--good` (already right); button radius 6 → `--radius (10)`.
6. **rec-card** ✅ — left stripe = severity good/warn/bad (ADD bad); `--radius-lg`; stripe 3px.
7. **reference-bar** ✅ — `.reftabs` → the one segmented control (§6); `.refread-cat` hardcoded
   backgrounds (#3a4060/#2e3a52/#3a3040/#3a2832) → derive from `--panel2/--line`; `.refread-bar`
   good/warn/bad (right); star #ffb13f → `--warn`, chip #6fdfb8 → `--good`, halfstar #a0a8bc → `--muted`.
8. **search** ✅ — `#q` focus (state ladder); `.seg` → the one segment; `.count` `--muted`.
9. **view-toggle** ✅ — `.viewtoggle` → the one segment; `.viewhint` `--muted`.
10. **vitals** ✅ — `.vitals` → `--radius-lg`; `.vval` .warn/.bad/.good (right); `.vlabel` `--muted`;
    `::before` separators on `--line`; `.srcmeta` `--muted` + `b` → `--ink`. Tokenise, no states.

**Radius list is wider than before:** the code also has `4` and `12`. Final — snap all to
`10 / 14 / 18 / 20` (12→14, 6→10); NO separate `--radius-xs`, the 4px bars are decoration.

## 8. Typography — NOT worked this session (needs the same audit as colour)

Honest: the type scale was not touched. Tokens exist (`--fs-kicker 10.5 · --fs-1..6 = 12/13/14/15/20/28`)
but components drift. Run the same code-audit as for hex:
- **Weights:** `620` and `650` appear (tc-panel summary, h1 in search/view-toggle) — off the usual
  400/500/600/700. Snap to 600/700.
- **Heading sizes:** `21px` / `22px` (h1) — off scale (`--fs-5 20` / `--fs-6 28`). Decide: snap to 20
  or add a heading token.
- **Fractional sizes:** `13.5 / 12.5 / 11.5` scattered — fold into `--fs-1..4`.
- Action: grep `font-size` / `font-weight`, count frequencies (like hex), snap to the clean scale;
  **the taste calls (which weight where) return to the owner** — audit + safe snaps here, ASK on weights.

## Sequencing for the eventual pipeline (spec settled; --bright kept)

Order §0 → §1 → §5 → §3 → §4 → §6 → §2, because §0 gives the single source everything else
references, §1 fixes the token set, and §6/§4 depend on the motion (§3) + radius (§5) tokens.
This is a big multi-surface visual change → build-pipeline (spec-author into SPEC.md, product-prover
whole-spec, TEST_MATRIX with ≥ browser-rendered rows for every colour/layout fact, then code).
New "no raw hex that duplicates a token" guard test. Commit when green; PUSH HELD (the owner's rule)
until he reviews the before/after render. Version: PATCH bump per delivered build.

## Open items awaiting the owner
1. **§8 typography weights** — the ONLY open taste call. Do the audit + safe mechanical snaps in
   code, but the "which weight goes where" decision returns to the owner (the owner's v3 instruction). ASK before
   finalising the weight placement.
   (RESOLVED and folded above: --bright kept · data swatches re-pulled 2026-07-02, colormap + stems
   left untouched · all §7 component taste calls decided.)
