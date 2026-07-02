# Design-system session — decisions to vivify into code (2026-07-02, v2)

Source: Alexander's design session on claude.ai/design (project `track-coach`,
aae67990-57e7-472c-877b-5a1570411df3). Four workspace artifacts hold the reasoning
(`Ревизия токенов` = colour, `Layout и сетка` = layout, `Движение и состояния` = motion+states,
`Дрейф к системе` = radii+segmented control). Those artifacts are a SPEC, not edits to the
design-system source files, so `/design-sync` does NOT pull them — they are applied here in code.

STATUS: spec is STILL MOVING — Alexander is adding missing swatches on claude.ai/design and will
have me re-pull soon. Do NOT start coding until the spec settles AND the one open taste call (§1
--bright A/B) is decided. This file is the implementable record; keep it in sync with his latest paste.

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
- `--bright (#ffd166)`: **DECIDE (NOT an auto-replace).** Audit found 13 live uses — it may be a
  real "highlight/attention" role (yellow ≠ amber), not a warn dup. **A** — keep as its own token;
  **B** — merge into `--warn`. Taste call. ← OPEN, needs Alexander. [blocks the colour layer]

Data-viz (UPDATED by code audit — CANCELS the earlier --data-1/2/3 plan):
- Arc/stem colours are colormap steps (magma / viridis: #4cc9f0 … #fcfdbf #8c2981 #3b0f70), a
  perceptual gradient. **DO NOT tokenise** — leave as a colormap. (This is why the earlier "merge
  teal→cyan" is dropped: it would have collided drums #4cc9f0 with hats #5ad1c2 in the lanes.)
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

## Sequencing for the eventual pipeline (once spec settles + --bright decided)

Order §0 → §1 → §5 → §3 → §4 → §6 → §2, because §0 gives the single source everything else
references, §1 fixes the token set, and §6/§4 depend on the motion (§3) + radius (§5) tokens.
This is a big multi-surface visual change → build-pipeline (spec-author into SPEC.md, product-prover
whole-spec, TEST_MATRIX with ≥ browser-rendered rows for every colour/layout fact, then code).
New "no raw hex that duplicates a token" guard test. Commit when green; PUSH HELD (Alexander's rule)
until he reviews the before/after render. Version: PATCH bump per delivered build.

## Open items awaiting Alexander
1. §1 `--bright` A (keep) vs B (merge into --warn) — blocks the colour layer.
2. Missing swatches he is adding on claude.ai/design → re-pull, then reconcile this file.
