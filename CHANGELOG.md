# Changelog

All notable changes to **track-coach** are documented here. The project is early/unstable;
versions are the analyzer version printed in the widget footer (`TC_VERSION`).

The format loosely follows [Keep a Changelog](https://keepachangelog.com/). Newest first.

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
