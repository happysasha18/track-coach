---
description: Track Coach — full deep analysis (stems, player, evidence). Opens calm by default.
---

Use the **track-coach** skill to run a **FULL** analysis.

Target: $ARGUMENTS
(If empty, ask the user for the audio file, the .als, or the project folder — whatever they have.)

Full mode = run everything per the skill's SKILL.md: Demucs stems, masking, rhythm,
drum breakdown, note transcription, self-similarity, .als parsing, the synced
stem player/sequencer, and the evidence drawer.

Follow the skill exactly. The whole pipeline is ONE entrypoint — do not hand-drive the
internal steps; drive `scripts/track_analyzer.py`, which versions the run, deposits into the
library, and rebuilds the catalog for you:

```bash
# 1) MEASURE (heavy): runs everything → result_*.json + stems. Prints {run_dir}. No widget yet.
python3 "$SKILL_DIR/scripts/track_analyzer.py" analyze "<AUDIO>" \
    [--als "<ALS>" --als-offset-s <N>] --mode full [--track-version "<vX.Y or omit>"]

# 2) INTERPRET (you): read the result_*.json, write your Producer's Read to <run_dir>/narrative.md.

# 3) RENDER: build the widget with the read + deposit + rebuild the catalog, one pass.
python3 "$SKILL_DIR/scripts/track_analyzer.py" build --run-dir "<RUN_DIR>" \
    --title "<Track name + version>" --verdict "<1–2 sentence verdict>" \
    --mood-tags "dark,driving" --style-tags "melodic techno"   # genre is YOUR call; '' clears
```

`analyze` auto-resumes a recent run for the same track (reusing the already-computed
core/detail/als) and inherits the previous run's narrative/title/verdict, so nothing you
set is lost. Add `--dry-run` to `analyze` to print the plan without running.

The widget opens in the **Simple** view by default; tell the user the **Detailed**
toggle (top-right) reveals stems, player and full evidence — and that toggling is free
(pure offline JS, no recompute).

**Library.** The `build` step above auto-deposits the widget into the global library and
rebuilds the cross-version Catalog — that is where the deposit actually happens, so keep
the build on this entrypoint. Offer to open it:
`python3 "$SKILL_DIR/scripts/library.py" catalog --open` ((re)build + open the Catalog in
a new window). See SKILL.md "Global library" for `list` / `remove` / `prune-versions`.
