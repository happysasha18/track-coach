---
description: Track Coach — quick calm read (fast & cheap, no stems). Upgradeable to full later.
---

Use the **track-coach** skill to run a **QUICK** analysis — the low-cost, not-overwhelming read.

Target: $ARGUMENTS
(If empty, ask the user for the audio file or folder.)

Quick mode = **fast analysis, no Demucs**: no stems, no per-stem player, no masking — those
are the heavy parts. It still encodes a single-track **mix player** (transport + seek), so the
widget is never silent. This finishes in seconds.

Follow the skill. The whole pipeline is ONE entrypoint — do not hand-drive the internal steps;
drive `scripts/track_analyzer.py --mode quick`, which versions the run, deposits into the
library, and rebuilds the catalog for you:

```bash
# 1) MEASURE (fast): fast analysis + .als + self-similarity, and encodes mix_web/mix.m4a
#    for the single-track player. Prints {run_dir}. No stems.
python3 "$SKILL_DIR/scripts/track_analyzer.py" analyze "<AUDIO>" \
    [--als "<ALS>" --als-offset-s <N>] --mode quick [--track-version "<vX.Y or omit>"]

# 2) INTERPRET (you): read the result_*.json, write your Producer's Read to <run_dir>/narrative.md.

# 3) RENDER: build the widget with the read + deposit + rebuild the catalog, one pass.
python3 "$SKILL_DIR/scripts/track_analyzer.py" build --run-dir "<RUN_DIR>" \
    --title "<Track name + version>" --verdict "<1–2 sentence verdict>" \
    --mood-tags "dark,driving" --style-tags "melodic techno"   # genre is YOUR call; '' clears
```

Every stem-dependent panel auto-omits when its data is absent, so the quick widget is calm by
construction. The widget opens in the **Simple** view — the calm essentials. Tell the user they
can later run **/tc** for the full deep version, and it will **reuse** what was already computed
here (the same track auto-resumes) instead of starting over.

**Library.** The `build` step above auto-deposits this quick run into the global library and
rebuilds the cross-version Catalog — the deposit happens there, so keep the build on this
entrypoint. Offer to open it:
`python3 "$SKILL_DIR/scripts/library.py" catalog --open` ((re)build + open in a new
window). See SKILL.md "Global library" for `list` / `remove` / `prune-versions`.
