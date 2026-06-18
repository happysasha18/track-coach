# Changelog

All notable changes to **track-coach** are documented here. The project is early/unstable;
versions are the analyzer version printed in the widget footer (`TC_VERSION`).

The format loosely follows [Keep a Changelog](https://keepachangelog.com/). Newest first.

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
