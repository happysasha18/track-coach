---
description: Track Coach — full deep analysis (stems, player, evidence). Opens calm by default.
---

Use the **track-coach** skill to run a **FULL** analysis.

Target: $ARGUMENTS
(If empty, ask the user for the audio file, the .als, or the project folder — whatever they have.)

Full mode = run everything per the skill's SKILL.md: Demucs stems, masking, rhythm,
drum breakdown, note transcription, self-similarity, .als parsing, the synced
stem player/sequencer, and the evidence drawer.

Follow the skill exactly, and in particular:
- Create the output folder with `scripts/run_dir.py init --mode full` so this run is
  versioned and never overwrites a previous one.
- If a recent run already exists for this track, use `run_dir.py resume` and reuse the
  already-computed core/detail/als instead of recomputing them.
- Pass `--src-audio`, `--src-als` (if any), `--track-version` and a 1–2 sentence
  `--verdict` to `build_widget.py` so the header shows what/when and the calm Simple
  view has a headline.

The widget opens in the **Simple** view by default; tell the user the **Detailed**
toggle (top-right) reveals stems, player and full evidence — and that toggling is free
(pure offline JS, no recompute).

**Library.** Every build auto-deposits the widget into the global library and rebuilds
the cross-version Catalog. Offer to open it:
`python3 "$SKILL_DIR/scripts/library.py" catalog --open` ((re)build + open the Catalog in
a new window). See SKILL.md "Global library" for `list` / `clean`.
