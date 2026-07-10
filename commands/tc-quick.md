---
description: Track Coach — quick calm read (fast & cheap, no stems). Upgradeable to full later.
---

Use the **track-coach** skill to run a **QUICK** analysis — the low-cost, not-overwhelming read.

Target: $ARGUMENTS
(If empty, ask the user for the audio file or folder.)

Quick mode = **Fast analysis only**: `analyze_core.py` + `analyze_detail.py` (+ parse the
.als and run self-similarity if cheaply available). **Do NOT run Demucs / stems / player /
masking** — those are the heavy parts. This finishes in seconds.

Follow the skill, and in particular:
- Create the output folder with `scripts/run_dir.py init --mode quick` (versioned, never
  overwrites).
- Build the widget with just `--core` and `--detail` (plus `--als` / `--selfsim` if you
  ran them). Every stem-dependent panel auto-omits when its data is absent.
- Still pass `--src-audio`, `--track-version`, `--verdict` so the header + calm headline
  are populated.

The widget opens in the **Simple** view — the calm essentials. Tell the user they can
later run **/tc** for the full deep version, and it will **reuse** what was already
computed here (via `run_dir.py resume`) instead of starting over.

**Library.** This quick run is auto-deposited into the global library and rebuilds the
cross-version Catalog too. Offer to open it:
`python3 "$SKILL_DIR/scripts/library.py" catalog --open` ((re)build + open in a new
window). See SKILL.md "Global library" for `list` / `clean`.
