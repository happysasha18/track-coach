# Changelog

All notable changes to **track-coach** are documented here. The project is early;
versions are the analyzer version printed in the widget footer (`TC_VERSION`).

The format loosely follows [Keep a Changelog](https://keepachangelog.com/). Newest first.

## [0.8.5] — 2026-06-21

### Fixed
- **Mute and solo are now mutually exclusive across the whole player.** You could mute one stem while
  soloing another (a contradictory state). Now muting clears every solo and soloing clears every mute —
  the player is always in one coherent mode.

## [0.8.4] — 2026-06-21

### Fixed
- **A lane can no longer be both soloed and muted** — enabling one now clears the other (they were
  independent toggles, so you could leave both on).

### Changed
- A sustained pitched layer now reads **`≈ tonal`** instead of `≈ melody`. "Melody" over-claimed — the
  same measurement can be a pad, lead, or chords, and we can't tell them apart yet (that needs a
  tonal-vs-noise measure). `tonal` says what we actually know: pitched, sustained, mid-range.

## [0.8.3] — 2026-06-21

### Changed
- **Player lanes are named by what they SOUND like, not the raw separation label.** Each stem lane now
  reads `kick` / `bass` / `≈ melody` / `≈ hats` / `≈ air` — derived from measured features (where its
  energy sits in the spectrum, excluding bleed; and whether it's percussive or sustained), not the
  Demucs `vocals/guitar/piano` label that means little for electronic music. `≈` marks an approximation;
  low end (kick/bass) is read confidently. The raw stem name still shows tiny beneath, so you always
  know which file it is. Same track always yields the same labels (deterministic — no run-to-run drift).

### Internal
- New `stem_character()` (deterministic, gated to significant stems, reuses CR-4 leakage to avoid typing
  a stem by another's bleed) + guard G12. Tests 198 → 205.

## [0.8.2] — 2026-06-21

Credibility, part 2 (SPEC CR-4/CR-6/CR-7).

### Changed
- **Bled energy isn't blamed on the wrong instrument.** When a stem's loudest frequency band is really a
  louder, correlated neighbour bleeding in, the separation panel now says so ("guitar's low is likely
  drums bleed") instead of letting you read it as that stem's own — conservatively, only the clearest case.

### Added
- **Per-part repetition** (computed): each real (non-silent) stem's own self-similarity → how much that
  part repeats vs. evolves (e.g. on one track the drums/melody lean on a returning section while the bass
  barely repeats — it's doing the development). In the data now; how it's shown is still being decided.

### Internal
- New guardrails G9 (leakage attribution), G10 (stem↔project family asserted only on a "clear" match —
  locks existing honesty), G11 (per-stem repetition gated to significant stems). `track_analyzer` runs
  per-stem self-similarity for significant stems only. Tests 186 → 198.

## [0.8.1] — 2026-06-21

Credibility pass (SPEC `docs/SPEC.md`, Phase 3): the numbers behind the words are now defensible.
"Don't cry wolf, and don't paint silence."

### Changed
- **Near-silent stems are omitted, not drawn.** A stem the separation barely filled (e.g. a −90 dB
  "vocals" or "piano") is dropped from the per-stem view and **named** as omitted — instead of being
  shown as if it were real content.
- **Per-stem colour is honest.** Each stem's frequency colour/height is now scaled against a fixed
  loudness floor, so a quiet stem reads as the near-silence it is — it can no longer "light up" by
  stretching its own loudest band to full colour.
- **Structure reads the real form.** Scenes now follow the track's self-similarity (its actual
  repeats) when that's reliable, instead of a coarse section split that could flatten several distinct
  sections into one block.
- **"Drop" means a drop.** A section is only called a **Drop** when a lower section (a build/breakdown)
  comes right before it. A track that's just loud the whole way is no longer labelled "all drops"; a
  sustained-loud section with no lift before it reads **Main**. Drop numbering is now always gap-free.

### Internal
- New credibility guardrail tests G1–G7 (`tests/test_credibility.py`), derived from the SPEC via
  product-prover. New `significant_stems()` gate; absolute colour floor; self-sim-sourced scenes;
  contrast-based Drop naming numbered after coalescing. Tests: 166 → 183.

## [0.8.0] — 2026-06-20

Milestone: the project grew up. The spec/test matrix now covers **every dimension** the product has —
the three views, both pages, all the data states, and styling — so changes can't quietly break quality.
Status drops "unstable": it's **early**, not fragile.

### Changed
- Status is now **early** (was "early / unstable"). The widget footer reads `v0.8.0`.

### Internal
- The spec + test matrix (`docs/TEST_MATRIX.md`) completed to all dimensions: an explicit data axis
  (stems present/empty/none, project file, web mix), a 3-D element grid, a styling-contract layer, and a
  cross-page (catalog ↔ track) invariant grid. New invariants INV-19…22 (view-ladder monotonicity,
  cross-page mode agreement, no leftover template placeholders, the CSS gating contract). Every
  invariant (INV-1…22) now has a test that names it, both ways. Tests: 154 → 166.
- A product-prover A/B (before vs after the completeness pass) is kept under `docs/prover_runs/`.

## [0.7.7] — 2026-06-20

The three views are now a clear **information ladder**: the quick read shows the least, the calm
(Simple) view adds to it, and the detailed view adds the most — nothing visible in a lighter view ever
disappears in a heavier one.

### Fixed
- **The "Evidence & detail" drawer is now available in every view** — including the calm view, where it
  used to vanish. It stays a collapsed, opt-in drawer, so the calm view stays calm; the deep per-stem
  visualisation remains detailed-only.
- **The quick read now shows brief recommendations** (only the ones pinned to a moment on the graph),
  matching the calm view, instead of dumping the full list — so the quick read is genuinely the lightest.

### Changed
- The catalog's preview player gives feedback when a track's audio has moved since it was filed: the
  play button is disabled with a "preview unavailable" tooltip instead of doing nothing.

### Internal
- Library deposits now refuse a malformed run dir instead of writing a junk entry; the "out of date"
  flag no longer depends on the widget's filename; new invariants INV-14…18 with tests (154 total).

## [0.7.6] — 2026-06-20

### Fixed
- **Quick read — the Producer's read no longer shows stray "#" or giant-heading text.** The write-up is
  now rendered properly (headings, bold, bullets) regardless of how the markdown was wrapped.
- **Quick read — no more empty Simple/Detailed switch.** A quick run has nothing extra to reveal (no
  stems), so the switch is replaced by a hint ("run a full analysis for stem-by-stem detail"), and the
  evidence drawer + all recommendations are shown by default.
- **Quick read — the Track Story graph opens in the same calm view as every other widget** (no longer
  the busier detailed graph).
- **Structure bar (the coloured scene strip) no longer shows a part as a row of slivers with gaps** —
  adjacent identical scenes are merged and the bar runs edge to edge. Applies to every track.

### Added
- **Play a track straight from the Library.** Each row now has a one-button preview player; the
  signature ribbon doubles as a scrubber — click along it to seek. (Full runs become playable after a
  re-analysis.)
- **`docs/TEST_MATRIX.md`** — a complete map of what every page shows in every state, backing the tests.

## [0.7.5] — 2026-06-20

### Added
- **Quick runs now have a player.** A quick read keeps no Demucs stems, but it still has the mix — so
  the widget now offers a **single-track player** (play / seek, synced to the charts). Per-instrument
  mute/solo and the stem lanes remain a full-run feature.
- **Clear run-mode badge.** Every widget shows a badge by the title — green **Full analysis** or amber
  **Quick read** — and a quick read adds a one-line note of what a full run would add (stem player,
  masking, drum/note breakdown, section instrument labels). The Library already tags each row Full/Quick.
- **The Library footer shows the version** that generated the page.

### Changed
- **What a quick read shows is now intentional and signposted.** It keeps the vitals, verdict, the
  Producer's read, the full Track-Story graph + A/B/C structure bar, the mix player, recommendations
  and tonal balance; the stem-dependent panels (per-stem lanes, masking, rhythm, drums, notes,
  stem↔track map, per-section instrument labels) appear only in a full run — and the badge says so.

### Internal
- Re-rendered the deposited widgets to the current version from their cached analysis (no re-separation)
  and pruned the old per-version widget copies, so the Library and the widgets agree on the version.
- Tests: added render-level coverage for the quick widget (mix player, badge, graph/sections), the
  section-lead data path, and the quick mix-encode step; 104 → 111, all green.

## [0.7.4] — 2026-06-20

### Changed
- **Library table: the track name is the link.** The separate "open" column is gone — click a track's
  **title** to open its widget; the whole row highlights on hover so it reads as clickable.
- **Library table is now genuinely responsive.** On a non-maximised window it sheds its least-important
  columns (mood/style + mode → date) instead of clipping, keeping the signature and the core spec
  readable; horizontal scroll remains as a last-resort fallback on very narrow screens. Long file-name
  subtitles truncate so they can't blow the table wide.
- **Dropped the "verdict" column** from the Library — it was the widest, most variable column and the
  main thing knocking the table off-screen. The verdict still lives inside each track's widget.
- **Library footer now shows the version** that generated the page (e.g. `· v0.7.4 ·`).
- **README** now shows the Library right after the hero (refreshed screenshot) and explains the
  measured → interpretation → "up to you" layering in plain language.

### Internal
- **Test suite reworked for robustness.** Widget tests now assert on the **rendered HTML the skill
  ships**, not the template source — so cosmetic refactors stop breaking the suite. Behavioural facts
  (curves, per-view lanes, player/back wiring) live once at the render level; the contract file covers
  only structure + CSS visibility. Net 108 → 103 tests, de-duplicated, all green.

## [0.7.3] — 2026-06-19

### Added
- **Catalog row signature** — each library row now shows a rich per-track signature instead of a plain
  energy sparkline: a spectral *ribbon* (height = energy, colour = brightness, line weight = density)
  over a 9-band *tonal strip* (the spectrum, in the widget's low-red→mid-green→high-blue colours,
  flagged bands brightened). Fully visible by tap — no hover needed. Degrades to ribbon-only, then to
  the old sparkline, for older library entries that lack the data.
- **Favicon on the Library page** — the catalog page now carries the same Track Coach bar-chart icon
  as the per-track widgets.
- **"← Library" back button** in each widget — returns to the catalog you came from (shown only when
  there's somewhere to go back to; portable, no hard-coded path).

### Changed
- **Catalog rows are shorter and responsive** — verdict clamped to two lines, mood/style chips pack
  horizontally instead of one-per-line, tighter row padding; the table now scrolls horizontally on
  narrow screens instead of squishing.

### Fixed
- **Simple graph set to its agreed form** — Simple shows **four** lanes (energy + brightness + density
  + stereo); Detailed shows all five (+ modulation). The curve-area height is now **proportional to the
  lane count** (a constant per-lane height in both views), so Simple's area is smaller than Detailed's.
  The widget tests pin the lane set *and* the proportional-height rule with the source citations, so
  the suite fails loudly on any future drift. (Nothing in 0.7.x had shipped; this is the corrected
  end-state after the lane set flip-flopped during the session.)

## [0.7.1] — 2026-06-19

### Fixed
- **Player no longer dies when opening a track from the Catalog.** The catalog's "open →" now opens the
  original widget in its run folder (where the stems live), not the stem-less library copy — so the
  multi-stem player actually plays. Old catalog entries fall back to the copy as before.

### Tests
- **New render-level tests** (`tests/test_widget_render.py`): build a widget from a fixture and assert
  on the real output — all five curves reach the payload, each view draws the right curve set, and the
  player is wired to one source per stem. The previous tests only checked the static template, so a
  broken render could still pass. Template tests kept; suite 85 → 95.

## [0.7.0] — 2026-06-19

### Added
- **Global Catalog page** — a standalone, offline, always-current `index.html` at
  `~/.track-coach/library/`: the front-end of the library store. A FLAT, sortable, searchable table;
  each row is a **version** of a track, with a coloured mini-arc (energy sparkline), BPM/key/length/
  LUFS, mood + style tags, mode, and a relative "open →" into the archived widget. Regenerated
  automatically after every `build`, or on demand via `library.py catalog [--open]` /
  `catalog.py build [--open]`. New module `scripts/catalog.py` (the VIEW); `library.py` stays the store.
- **Versions keyed by audio content hash** — `analyze` records `audio_sha256` + `audio_mtime`; the
  catalog groups a track's runs by hash (re-analyses of the same bounce collapse to the newest run),
  numbers them v1..vN by mtime (explicit `--track-version` wins), and shows LUFS/length/BPM deltas vs
  the previous version.
- **Mood + style tags** — heuristic draft (`scripts/tags.py`, a valence–arousal model over
  tempo/key/brightness/energy/wobble) written at `analyze` time; the agent overrides via
  `build --mood-tags/--style-tags`. Heuristic-only tags are marked "draft" in the catalog.

### Notes
- Research informing the tag model: DJ-library conventions (genre/energy-level/mood) and the
  valence–arousal model used by tools like Cyanite/Mixed In Key.
- Tests 61 → 85. MINOR bumped (0.6.11 → 0.7.0) as the catalog milestone.

## [0.6.11] — 2026-06-19

### Changed
- **Recommendations now sit directly under the graph**, and the separate callout list under the
  graph (`#storyCues`) is gone — the timeline triangles point straight at the recommendation cards.
  New panel order: graph → Recommendations → Producer's read.
- **Simple vs Detailed for the cards is now timecoded-vs-all** (reverses [0.6.10]'s fixed cap):
  Simple shows only the recs that have a triangle on the graph; Detailed shows all. The count is
  per-track (e.g. Shared Memories = 2 timecoded of 5).
- Clicking a timeline triangle flashes its card in the Recommendations panel.
- Tests 61 → 61 (two `#storyCues`-cap tests replaced by a timecoded-recs contract test).

## [0.6.10] — 2026-06-19

### Changed
- **Callout cards under the graph**: Simple shows the first 3 (calm), Detailed shows all
  ("в детальном больше"). CSS cap on `#storyCues` in Simple only.
- **Tonal balance moved OUT of the Evidence drawer** into a standalone panel, placed last before
  the collapsible — always visible in both views (Sasha: "он прикольный"). The Evidence drawer is
  now arrangement + automation + stem↔track map + rhythm + transcribed notes (no tonal).
- Default view confirmed Simple. Tests 60 → 61.

## [0.6.9] — 2026-06-19

### Fixed
- **Transcribed-notes panel rendered broken/empty.** Its canvas height ran away (260 → ~900px)
  because `resize()` read `clientHeight` back into `cv.height` on a `width:100%` canvas with no CSS
  height. Pinned a fixed 260px height like the other canvases — the piano roll (3354 notes here)
  now draws correctly.
- **"Transcribed notes — other" was meaningless.** "other" is Demucs's raw catch-all stem name.
  Relabelled to **"the melodic layer (synths / keys / pads)"** with a hint explaining it's the
  Demucs "other" stem (everything that isn't drums/bass/vocals — where chords & leads live).

### Changed
- Removed the verbose "Callouts on the timeline — tap a triangle…" header above the callout chips.
- Removed "(click to open)" from the Evidence drawer summary (the ▸ marker already says it).

## [0.6.8] — 2026-06-19

### Changed
- **View toggle, corrected to what Sasha actually asked for** (see JOURNAL): the **demux/per-stem
  visualisation** (`#stemlanes` + its key) is now **Detailed-only** — hidden in Simple — while the
  play/seek transport stays usable in both. The Track-Story component lanes: **Simple = 2 full-size
  (Energy + Brightness), Detailed = all 5**. (0.6.7 had set 3/5 on a wrong reading of the history.)
- Tests (58 → 60): `test_demux_stems_hidden_in_simple`, `test_player_transport_visible_in_simple`;
  reworked the Simple-gating + graph-reacts contracts.

## [0.6.7] — 2026-06-19

### Changed
- **The Track-Story graph reacts to the Simple/Detailed toggle again.** (Superseded by 0.6.8's
  2/5 split.) One line in `pickComps` — restored the 0.5.13 behaviour the 0.6 refactor left flat.
- Tests (57 → 58): `test_widget_contract.py::SimpleViewContract::test_story_graph_reacts_to_the_toggle`.
- Started a per-project decision **`JOURNAL.md`** (engineering/design diary, with the WHY) — seeded
  with the reconstructed Simple/Detailed history so intent isn't lost again.

## [0.6.6] — 2026-06-19

### Added
- **Restored the "Intention vs result" automation chart** (regressed out in the 0.6 declutter
  while its data kept riding in the payload). New `#autoPanel` in the Evidence drawer plots the
  real project envelopes (`ALS.automations`, up to 8, filter/gain/pitch/sends prioritised) as
  small-multiple lanes — each scaled to its own range, on the same time axis as the arrangement,
  with locator gridlines, a shared playhead, and a per-time hover readout. The measured
  **Brightness** arc is ghosted (faint dashed) into every lane so a flat automation against a
  still-rising sound reads at a glance — the visual the existing `intention_result` rec describes.
  Wires the dormant `auto_title`/`auto_hint` strings.
- Tests (53 → 57): `tests/test_widget_contract.py::AutomationPanel` — panel + canvas present,
  bound to `ALS.automations`, strings referenced, and nested inside the Evidence drawer.
- Docs: regenerated `docs/automation.png`; restored the README "Intention vs. result" showcase.

## [0.6.5] — 2026-06-18

### Added
- **Global widget library** (`scripts/library.py`). One place that collects every rendered
  widget across projects, at `~/.track-coach/library/` (override `$TRACK_COACH_LIBRARY`):
  `widgets/<track>__<version>__<stamp>.html` + `index.json`. `build` now **deposits**
  automatically (best-effort; `--no-deposit` to skip). Subcommands: `path`, `list [--track]`,
  `clean` with `--all/--yes`, `--older-than DAYS`, `--keep-per-track N`, `--track`, `--missing`,
  `--dry-run`. Archives the self-contained HTML only (never stems/audio).
- Tests (44 → 53): `tests/test_library.py` — canonical naming/sanitize, `upsert` dedupe, the pure
  `clean_plan` policy (all/older-than/keep-per-track/missing + track scope), and a deposit
  round-trip (copies the widget, indexes it, re-deposit upserts not duplicates).

## [0.6.4] — 2026-06-18

### Changed
- **"All analyses" panel renamed to "Library"** (`cat_title` + hint) — the cross-version index at
  the bottom now reads "Library — every track & version (N)". First step toward the planned global
  library; in-widget behaviour unchanged.

## [0.6.3] — 2026-06-18

### Fixed
- **Re-analysing a track no longer drops the Producer's read.** A fresh `analyze` makes a new
  dated run dir; the hand-written `narrative.md` (+ title/verdict) from the prior run used to
  vanish — the root cause of "the producer view is gone". `analyze` now inherits the most recent
  sibling run's narrative + title + verdict into the new run (without clobbering anything the new
  run already set). Pure picker `pick_inherit_source()` + `inherit_prior_read()`.
- **Quick runs no longer mislabelled "deep mode".** The header subtitle was the hardcoded string
  "deep mode" for every run. The widget now carries `mode` and shows "quick read" for quick runs,
  "deep mode" for full. Verified in the rendered DOM (Fragile → "quick read", SM → "deep mode").

### Added
- Tests (37 → 44): `pick_inherit_source`/`inherit_prior_read` carry-forward (incl. the exact
  "new run, prior holds the read" incident and a no-clobber case), and a contract test that the
  header subtitle branches on `mode` rather than hardcoding "deep mode".

## [0.6.2] — 2026-06-18

### Changed
- **Simple view stops hiding substance.** Previously Simple hid the stem player, the Producer's
  read and capped recommendations to 3 — they read as "things vanished". Now Simple shows the
  player, the Producer's read and **all** recommendation cards; the ONLY panel gated to Detailed
  is the deep "Evidence & detail" drawer.

### Fixed
- **Rebuilds no longer drop the title / verdict / narrative.** `build` resolved title only from
  its flag, so a bare rebuild silently replaced a curated title (e.g. "Total Reboot — Shared
  Memories (2026)") with the raw folder name. Title + verdict are now persisted to `run_meta.json`
  and reused, and narrative defaults to `<run>/narrative.md`. Logic extracted to the pure
  `resolve_build_inputs()` (flag > run_meta > derived/auto).

### Added
- **Regression tests for exactly what kept breaking** (22 → 37):
  - `tests/test_widget_contract.py` — the player, Producer's read and recs must exist in the
    template and must NOT be hidden in Simple (Simple may gate only `#evidence`).
  - `tests/test_build_inputs.py` — a bare `build` reuses persisted title/verdict and picks up
    `narrative.md`; explicit flags still win.
- A grounded `narrative.md` for the Shared Memories run (it had none → its Producer's read was
  empty); the read is now populated.

## [0.6.1] — 2026-06-18

### Changed
- **One structure bar.** The Track-Story used to stack two rows above the power curve that
  clashed on A/B/C: a self-similarity "Form / repeats" lane on top and the named scenes
  (Intro/Build/Drop) below, each on its own letter+colour scheme. They're now a single bar —
  the named scenes are the only row, and each scene is **coloured and lettered by the
  self-similarity recurrence cluster that dominates it** (max time-overlap). A returning part
  therefore shares one letter+colour across the track (e.g. `B` green at the build *and* again
  at the outro), repeating parts are outlined, and a `lead: <instrument>` sublabel shows when
  the lead actually varies between sections. One scheme, not two.

### Removed
- The standalone Form/repeats lane (`#formWrap` + its canvas/JS, the `.formlabel`/`#formWrap`
  CSS, the now-dead `tcol`/`SC` intensity-colour helpers, and the `form_label` string) — its
  information lives in the merged bar now.

### Internal
- Merge happens in `build_html` (Python) right after per-section leads are attached and before
  recommendations, so `story.scenes[].letter/lead` carry the cluster; the story-canvas JS just
  recolours the ribbon (`SPAL` palette, `sreps`, `sceneLeadVaries`, ribbon height `RIB` 24→30).
- Verified headless in both modes: full (Shared Memories, with .als → real lead labels) and
  quick (Fragile, no .als/stems → no lead sublabels, as expected). 22 tests still pass.

## [0.6.0] — 2026-06-18

Architecture: move the brittle pipeline orchestration out of SKILL.md prose and into one
deterministic CLI entrypoint. The app measures and renders; the skill decides and interprets.

### Added
- **`scripts/track_analyzer.py` — one-command engine.** `analyze` runs the whole deterministic
  flow (run dir → fast analysis → .als → Demucs → masking/maps/rhythm/drums/notes/web-stems →
  first build + catalog); `build` cheaply rebuilds an existing run to inject the agent's read +
  the cross-version catalog. Stdlib-only, shells every heavy step through `tc_uv.sh`, feeds one
  `$STEMS` dir to every deep step (the `stems/` vs `stems_6s/` path-class bug can't recur), and
  supports `--dry-run`.
- **`tests/test_pipeline_plan.py` — first tests.** Assert the orchestration *plan* via `--dry-run`
  (no audio/deps/Demucs): deep steps share one stems dir, web-stems is always produced in full
  mode, quick mode never touches Demucs, run-dir first / build last. Run: `python3 -m unittest
  discover tests`.

### Changed
- **SKILL.md now drives the pipeline through the entrypoint** instead of hand-running each step;
  the per-step sections remain as methodology reference.

## [0.5.20] — 2026-06-18

### Changed
- **The two bottom collapsibles now share one style.** The "Evidence & detail" drawer was bare
  (just a top-border line and small muted text) while "All analyses — every track & version" sat
  in a rounded framed card. The evidence drawer (`.more`) now uses the same framed-card style as
  the catalog — panel background, border, 18px radius, white 15px summary, purple ▸ marker — so
  both fold-outs match each other and the rest of the panels.

## [0.5.19] — 2026-06-17

Producer-read readability, header/branding, file naming, default view, and a shell-safe
runner. (Diff against the last published release, 0.5.13.)

### Fixed
- **Producer's read was a wall of text.** The narrative renderer turned every soft newline
  into a `<br>`, so a hard-wrapped source produced a forced line break mid-sentence ("looks
  like an Enter at the end of every line"). Soft newlines now collapse to spaces; only a real
  Markdown hard break (two trailing spaces) becomes a `<br>`.
- **Bullet lists weren't rendered.** The renderer had no list support, so a `- ` block with no
  blank lines between items collapsed into one run-on paragraph with literal dashes inline.
  `- `/`* ` blocks now render as a real `<ul>` (continuation lines fold into their item).
- **Missing stem player / stem lanes after a deep run.** The deep pipeline separated into
  `stems_6s/` but several later steps hard-coded `stems/`, so `make_web_stems` read a missing
  directory, `stems_web/` was never built, and the widget silently dropped `--audio-stems-rel`.
  A single `$STEMS` variable now feeds every step, and web-stems is marked mandatory.
- **Fabricated filename versions.** A non-version tag (e.g. `[2026_version]`) could become a
  nonsense `analysis_widget_v2026.html`. Versions are no longer invented: if there's no real
  version in the source name, the filename falls back to the analyzer version.

### Changed
- **Read typography reworked for scanning:** calm muted body so the white bold and the yellow
  section headers carry the hierarchy, more line-height and paragraph spacing, and a divider
  above each `H3` section (dividers between sections only — not between bullets). Full width.
- **Header leads with the track name.** The `H1` no longer forces a "Track Coach ·" prefix;
  the brand moved to a small eyebrow above the title (and stays in the footer and browser tab).
- **Self-identifying filenames** — `analysis_widget_v<version>.html`, using the track's real
  version when present, else the analyzer version.
- **Opens in Simple by default**, every time. A previous Detailed choice is no longer restored
  from `localStorage`; `#full` / `#detailed` in the URL still forces Detailed.

### Added
- **`scripts/tc_uv.sh`** — a shell-agnostic, dependency-pinned runner (`tc_uv.sh <profile>
  <script.py> …`, profiles `core`/`fast`/`deep`/`bp`). It runs under its own bash shebang, so it
  behaves identically under bash or zsh, fixing the `command not found: uv run …` failures the
  old `$UV` word-splitting pattern hit on zsh (the default macOS shell). All SKILL.md steps now
  call it.

## [0.5.13] — 2026-06-16

### Added
- **Versioned, non-clobbering output.** `scripts/run_dir.py` creates a per-track timestamped run
  folder, records `run_meta.json`, and appends to an append-only `index.json` history.
- **Simple ⇄ Detailed view.** The widget opens in a calm Simple view (verdict, vitals, power
  curve, top-3 recs); a toggle reveals the player, all lanes, the full read, and the evidence
  drawer. Pure offline JS — no recompute, no network.
- **Cross-version catalog** of every analysis at the bottom of the widget, with relative links.
- Source filename / project / version / date shown in the header and footer.

### Fixed
- **De-duplicated callouts** — an insight's full prose now lives only in its Recommendation card;
  the under-player index is a compact pointer, not a second copy.

## [0.5.10] — 2026-06-15

- **Initial public release.** The full pipeline: core + detail audio analysis, Demucs stem
  separation, frequency-masking, per-stem rhythm and drum-hit breakdown, note transcription, and
  Ableton `.als` parsing (tracks, MIDI, audio clips, automation, locators) — rendered into one
  offline, self-contained HTML widget with a synced multi-stem player, the real arrangement on a
  timeline, and the three-layer "measured → what it means → up to you" read.

[0.5.19]: https://github.com/happysasha18/track-coach/commits/main
[0.5.13]: https://github.com/happysasha18/track-coach/commits/main
[0.5.10]: https://github.com/happysasha18/track-coach/commits/main
