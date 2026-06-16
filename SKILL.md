---
name: track-coach
description: >
  Full-stack compositional coach for music producers. Runs everything by default:
  audio arc analysis, Demucs stem separation, frequency masking, per-stem rhythm +
  separation-quality, drum-hit breakdown (kick/snare/hat), note transcription, AND
  Ableton .als parsing (tracks, MIDI, AUDIO clips, automation envelopes, locators).
  Builds one offline HTML widget with a synced multi-stem PLAYER (play/seek/mute/solo,
  playhead linked to every chart), the real project arrangement on the timeline, an
  automation "intention vs result" layer, and a Demucs-stem ↔ real-track map. Gives
  concrete, specific diagnostics — not generic numbers, but "bass masks mid in 250–500 Hz
  during bars 8–24" and "Cutoff automation ends at 2:45 but brightness keeps rising to 3:10".

  ALWAYS USE THIS SKILL when the user mentions: a track, a mix, an arrangement, an .als
  file, "why does it sound stuck/raw/flat/cloudy", "compare versions", "check the arc",
  "analyse my project", "what's happening in my track" — even casually, even without the
  word "analyse". Grab the audio file AND the .als if available. Run everything. Don't ask
  permission to run Deep mode — just do it and narrate while Demucs runs.

  Supports mp3 / wav / m4a / aiff / flac + Ableton .als. macOS only (v1).
compatibility: "Runs fully via the Bash tool — no computer use needed. Best on the user's Mac via Claude Code (local compute, MPS, no timeouts); also works in the Cowork sandbox (Demucs in background). macOS or Linux."
---

# track-coach

Full-stack compositional coach for music producers. Runs the complete pipeline by default.

**Core principle — three output layers (always):**
1. **Measured** — exact numbers from scripts only, never invented
2. **What this typically means** — specific, concrete interpretation (not "energy is low" but "bass dominates 250–500 Hz in the first 2 minutes, mids are present but buried")
3. **Up to you** — patterns observed, no directives. The author decides what to do.

Read `references/methodology.md` for the conceptual framework (variety vs development, masking principle, what each metric measures). Read `references/interpretation.md` for the numerical ranges. Read `references/install_troubleshooting.md` if setup fails.

---

## Step 0 — Welcome + collect files

Greet the user warmly and frame the inputs as tiers — every tier works, more just
unlocks more. **Speak the user's language** (match how they wrote; default to English).
Translate the example, don't paste it verbatim:

> "Let's break your track down properly. The more you give me, the deeper it goes:
> • **Just an mp3/wav** — good: full development arc, stems, masking, rhythm, drum
>   breakdown, note transcription, and a synced stem player.
> • **+ the Ableton .als** — great: I overlay the real arrangement (every track, MIDI
>   and audio), the automation envelopes, and check intention vs. result on the timeline.
> • **The whole project folder** — ideal: I find the .als and the latest render myself,
>   so you don't have to hunt for files.
>
> While Demucs runs (~2-3 min) I'll narrate what I'm looking for."

Don't ask for permission to run Deep mode. Run everything by default.

**If the user gives a folder (or you can see the project folder):** discover inputs
yourself instead of asking.
- Audio render: pick the newest matching file —
  `ls -t <folder>/*.{wav,mp3,m4a,aiff,flac} 2>/dev/null | head -1` (prefer a bounced
  render over stems). If several look like versions, show the top few and confirm which.
- Project: newest `.als` — `ls -t <folder>/*.als 2>/dev/null | head -1` (skip the
  `Backup/` subfolder). If the audio is a render of a *section*, you'll still need the
  render offset — ask which locator it starts from (see Step 2).
Tell the user which files you picked before running, so a wrong guess is caught early.

## Step 0b — Environment check + auto-setup

The skill ships a single self-provisioning installer, `setup.sh`. It checks every
dependency and installs whatever is missing — Homebrew, ffmpeg, uv, python, node —
then warms the package cache. It is idempotent: run it every session; already-present
tools are detected and skipped in seconds.

```bash
SKILL_DIR="<absolute path to this skill folder>"
bash "$SKILL_DIR/setup.sh"
```

What to expect:
- **Fresh Mac with no Homebrew:** the script installs brew, which prompts ONCE for the
  user's Mac login password (that prompt is from the brew installer itself — it cannot
  and should not be bypassed). Everything after is hands-off. Tell the user this is
  coming so the password prompt isn't a surprise.
- **Everything already installed:** finishes in a few seconds, all ✓.
- The script never hard-fails on optional pieces (node, system python) — it only exits
  non-zero if a hard requirement (ffmpeg or uv) truly couldn't be installed, and prints
  the exact manual command in that case.

If the script exits non-zero, read its output, surface the one flagged line to the user,
and stop — don't try to limp forward with a missing dependency.

If ffmpeg is missing — tell the user to run `brew install ffmpeg` in their terminal, wait for confirmation, then re-run from the top.

Do NOT attempt sudo. uv installs in `~/.local/bin` and works without sudo.

**Where this runs — read this carefully, it determines the whole flow:**

- **Claude Code on the user's Mac (recommended for this skill):** every command in this
  file runs locally on the user's machine. There is NO sandbox timeout. Demucs runs
  inline like any other step — on Apple Silicon it auto-detects MPS (GPU) and finishes
  a 5-minute track in well under a minute. Do NOT use computer use. Do NOT route Demucs
  through a separate Terminal. Just run it.

- **Cowork bash sandbox (fallback):** individual bash calls have a ~45s timeout, and
  compute happens on the sandbox CPU, not the user's hardware. Demucs still works but a
  full track exceeds one call. Run it in the background and poll:
  ```bash
  nohup $UV_DEEP python "$SKILL_DIR/scripts/separate.py" "$AUDIO" \
      --out-dir "$OUT_DIR/stems" > "$OUT_DIR/demucs.log" 2>&1 &
  echo $! > "$OUT_DIR/demucs.pid"
  ```
  Then poll `demucs.log` / check the pid every ~30s until `stems_manifest.json` appears.
  Do NOT push Demucs onto the user's Mac via computer use — that path is removed.

Detect which environment you are in: if `uname` is Darwin you are on the user's Mac
(run everything inline); if Linux you are in the sandbox (use the background pattern
for Demucs only — core/detail/als/masking/widget all finish within one call).

---

## Step 0c — Output folder (versioned, NEVER overwrite)

Every run gets its OWN timestamped folder so re-analysing the same track never
clobbers a previous verdict. **Do not invent the path** — let `run_dir.py` (stdlib,
no deps, instant) create it and tell you where it is:

```bash
SKILL_DIR="<absolute path to skill>"
AUDIO="<path to audio file>"
# ALS="<path to .als>"   # only if the user gave a project

# Make a fresh run folder; capture its absolute path. MODE is quick or full (see below).
OUT_DIR="$(python3 "$SKILL_DIR/scripts/run_dir.py" init --audio "$AUDIO" \
            ${ALS:+--als "$ALS"} --mode full)"
echo "$OUT_DIR"   # e.g. .../track-coach-output/My_Track/v0.6.2__2026-06-16_2231
```

This writes `run_meta.json` (audio + .als filename, track version, date), appends the
run to `track-coach-output/index.json` (honest append-only history), and points a
`latest` symlink at it. Use this `$OUT_DIR` for the WHOLE run below.

**Upgrading a quick run to full** (the user looked at the calm view and wants the
stems/player): don't recompute what's already there. Find the last run and reuse it:

```bash
python3 "$SKILL_DIR/scripts/run_dir.py" resume --audio "$AUDIO"
# → prints {"run_dir":..., "computed":[core,detail,...], "missing":[masking,...]}
```
Point `OUT_DIR` at that `run_dir` and run ONLY the missing heavy steps (Demucs →
masking → stemmap → web stems), then rebuild the widget. core/detail/als are reused.

### Modes — quick vs full (cost control)

The friend-feedback driver: a full run is great but heavy, and the widget can feel
like a lot. So there are two depths AND a calm default view:

- **`full`** (default, `/tc`): everything — Demucs stems, masking, sequencer, player,
  evidence. Minutes of compute.
- **`quick`** (`/tc-quick`): Fast analysis ONLY (core + detail, + .als if given). No
  Demucs/stems/player. Seconds, cheap. Build the widget with just `--core/--detail`
  (+ `--als`, `--selfsim` if you ran it) — every stem-dependent panel auto-omits.

Independently of mode, the widget opens in a **calm "Simple" view** (verdict + vitals +
power curve + repeats + top-3 recs); a **Detailed** toggle reveals the rest. That toggle
is pure client-side JS — it never recomputes or calls anything, so it's free to flip.

---

## Step 1 — Run Fast analysis (audio)

Once you have the audio file, immediately run core + detail. These run in Cowork's bash sandbox (fast, no timeout issues):

```bash
SKILL_DIR="<absolute path to skill>"
AUDIO="<path to audio file>"
OUT_DIR="<the folder from Step 0c>"

UV="uv run --python 3.11 --with numpy==1.26.4 --with librosa==0.10.2 --with soundfile==0.12.1 --with audioread==3.0.1 --with scipy==1.13.1 --with scikit-learn==1.5.1"

# analyze_core also computes the VITALS spec-sheet (key/scale, integrated LUFS,
# true-peak dBTP, dynamic range) shown at the very top of the widget. LUFS needs
# pyloudnorm — add it to this one call (everything else degrades gracefully if absent).
$UV --with pyloudnorm python "$SKILL_DIR/scripts/analyze_core.py" "$AUDIO" --out "$OUT_DIR/result_core.json"
$UV python "$SKILL_DIR/scripts/analyze_detail.py" "$AUDIO" --out "$OUT_DIR/result_detail.json"
```

While these run, tell the user what you're computing and why.

## Step 2 — Parse .als (if provided)

If the user gave an .als file:

```bash
$UV python "$SKILL_DIR/scripts/parse_als.py" "$ALS" --out "$OUT_DIR/result_als.json"
```

No extra dependencies needed — parse_als.py uses only stdlib + numpy. It extracts,
per arrangement (session-view clips are filtered out): MIDI clips + notes, **audio
clips** (the audio-track arrangement), and **automation envelopes** named by their
target param/device (cutoff, gain, pitch, sends…), plus markers/locators, tempo.

**Render offset — ASK, never guess.** The audio is usually a render of one *section*
of the project, so project time ≠ audio time. To align the .als arrangement to the
audio you need the project time (seconds) where the render starts — almost always a
locator. If the locators don't line up with the audio length, ask the user: "From
which locator does this render start?" The only safe auto-case is trimming leading
silence before the first locator. Pass the answer as `--als-offset-s <seconds>` to
the widget (Step 4). Without it, the arrangement/automation layers are omitted.

## Step 3 — Demucs stem separation (runs locally — NO computer use)

Demucs is a normal step. Run it inline. Do NOT route it through computer use or a
separate Terminal — that detour has been removed.

```bash
SKILL_DIR="<absolute path to skill>"
AUDIO="<path to audio file>"
OUT_DIR="<output directory>"

UV_DEEP="uv run --python 3.11 \
  --with numpy==1.26.4 \
  --with torch==2.3.1 \
  --with torchaudio==2.3.1 \
  --with demucs==4.0.1 \
  --with soundfile==0.12.1 \
  --with audioread==3.0.1"

$UV_DEEP python "$SKILL_DIR/scripts/separate.py" "$AUDIO" --out-dir "$OUT_DIR/stems"
```

On the user's Mac (Claude Code) this finishes fast on MPS — run it and wait.
In the Cowork sandbox, use the background `nohup … &` + poll pattern from Step 0b
instead, because a full track exceeds the 45s single-call limit.

While Demucs runs, narrate to the user **in their language** (the text below is
English — translate, don't paste verbatim):
> "Separating stems with Demucs — ~2-3 min on CPU. I'm looking for conflicts in the
> frequency pockets:
> **250–600 Hz (low-mid)**: bass and melody share this pocket. If the bass is 12+ dB
> louder here, the melody is present but buried, not absent — the usual cause of a
> 'muddy' or 'cloudy' feel.
> **20–80 Hz (sub)**: kick and bass. If both are full at once, you get pressure but the
> punch smears."

5. After Demucs finishes, run masking in bash:

```bash
$UV python "$SKILL_DIR/scripts/masking.py" \
    --manifest "$OUT_DIR/stems/stems_manifest.json" \
    --out "$OUT_DIR/result_masking.json"
```

---

## Step 3 — Run the scripts

Set SKILL_DIR to the absolute path of this skill folder. Set AUDIO to the user's file.
Set OUT_DIR to a working directory (e.g. a `track-coach-output/` subfolder next to the audio file).

**All scripts run via `uv run`** — packages are downloaded automatically on first run (~2 min).
On subsequent runs they're cached and start instantly.

Define the uv run prefix:
```bash
SKILL_DIR="/var/folders/76/f5bl3yp57wsd1n_wc5z8yxmw0000gn/T/claude-hostloop-plugins/66078eafcb0b97d4/skills/track-coach"
UV="uv run --python 3.11 \
  --with numpy==1.26.4 \
  --with librosa==0.10.2 \
  --with soundfile==0.12.1 \
  --with audioread==3.0.1 \
  --with scipy==1.13.1 \
  --with scikit-learn==1.5.1"
UV_DEEP="$UV \
  --with torch==2.3.1 \
  --with torchaudio==2.3.1 \
  --with demucs==4.0.1"
```

### Fast mode

```bash
# Core analysis (energy arc, endpoint cosine, wobble drift, section boundaries)
$UV python "$SKILL_DIR/scripts/analyze_core.py" \
    "$AUDIO" --out "$OUT_DIR/result_core.json"

# Detail analysis (tonality, articulation, harmonic change, crest, swing)
$UV python "$SKILL_DIR/scripts/analyze_detail.py" \
    "$AUDIO" --out "$OUT_DIR/result_detail.json"
```

### Deep mode (after Fast)

```bash
# Stem separation (2-5 min on CPU — give the user the narrative above while waiting).
# Use htdemucs_6s when the track has melodic/harmonic parts (chords, leads, synths) so
# guitar + piano get their own stems instead of being dumped into 'other'. Keep masking,
# map_stems, make_web_stems all pointed at THIS same stems dir (here: stems_6s/).
$UV_DEEP python "$SKILL_DIR/scripts/separate.py" \
    "$AUDIO" --model htdemucs_6s --out-dir "$OUT_DIR/stems_6s"

# Masking analysis — run on the SAME stem set the player/sequencer will draw.
# If you separated with htdemucs_6s (recommended when melodic parts exist), point this
# at stems_6s/ so guitar + piano also get viz band data → frequency-colour detail in
# their lanes. Using the 4-stem manifest leaves guitar/piano flat. Match it to map_stems.
$UV python "$SKILL_DIR/scripts/masking.py" \
    --manifest "$OUT_DIR/stems_6s/stems_manifest.json" \
    --out "$OUT_DIR/result_masking.json"
```

If the user provides their own stems (not Demucs), use `--bass`, `--drums`, `--other` flags instead of `--manifest`. See `scripts/masking.py --help`.

### Deep mode — project-aware mapping, rhythm, drums, notes (B/C/D)

Run these after stems exist. They add the layers that make the widget specific.
`map_stems.py` needs the `.als` AND the render offset (Step 2); the others don't.

```bash
# B — map each Demucs stem to the real project tracks by envelope correlation,
#     recommend a model, and suggest exporting Ableton group stems.
#     Use the SAME stems dir as masking (stems_6s/). HONEST verdicts (v0.5.3):
#       - "empty"   = stem is near-silent (energy < -28 dB vs loudest stem) — Demucs put nothing here.
#       - "clear"   = strong, unambiguous match to ONE family (only then is ≈family claimed).
#       - "mixed"   = follows several parts at once (overlapping arrangement) — no family claimed.
#       - "nomatch" = HAS real signal, but timing doesn't line up with one part (NOT "lost").
#     Correlates loudness envelope vs project MIDI note-density AND audio-clip presence.
#     This method is unreliable for dense electronic music (everything plays together), so it
#     errs toward humility — track_matches (per-track) are usually more meaningful than family.
$UV python "$SKILL_DIR/scripts/map_stems.py" \
    --stems-dir "$OUT_DIR/stems_6s" --als "$OUT_DIR/result_als.json" \
    --als-offset-s "$OFFSET" --out "$OUT_DIR/result_stemmap.json"

# C — per-stem onset density / timing / syncopation + separation confidence
#     (mix vs sum-of-stems residual, pairwise leakage). Pass --tempo from the .als.
$UV python "$SKILL_DIR/scripts/rhythm_quality.py" \
    --manifest "$OUT_DIR/stems/stems_manifest.json" \
    --tempo "$BPM" --out "$OUT_DIR/result_rhythm.json"

# D — classify drum hits in the drums stem into kick/snare/hat (not separation)
$UV python "$SKILL_DIR/scripts/drum_breakdown.py" \
    --drums "$OUT_DIR/stems/drums.wav" --out "$OUT_DIR/result_drums.json"

# STRUCTURE — find REPEATING sections from the audio (self-similarity / recurrence,
# McFee-Ellis Laplacian segmentation). Powers the "Form" lane: same colour = the same
# part returns (reprise), confirming motif/variation/repeat beyond the family letters.
# Needs scikit-learn (already in $UV). Runs on the full mix; no .als/offset needed.
$UV python "$SKILL_DIR/scripts/self_similarity.py" \
    "$AUDIO" --out "$OUT_DIR/result_selfsim.json"

# D — transcribe a melodic/bass stem to real notes (basic-pitch). Run on the stem
#     that actually carries pitch (usually 'other'); skip on near-empty stems.
UV_BP="uv run --python 3.11 --with 'basic-pitch[onnx]' --with numpy==1.26.4 --with 'setuptools<70'"
$UV_BP python "$SKILL_DIR/scripts/transcribe.py" \
    --stem "$OUT_DIR/stems/other.wav" --label other --out "$OUT_DIR/result_notes_other.json"
```

### Web stems for the player (E)

The raw Demucs WAVs are ~100 MB each — too heavy for the in-page player. Transcode
them to small AAC `.m4a` once (needs ffmpeg):

```bash
$UV python "$SKILL_DIR/scripts/make_web_stems.py" \
    --stems-dir "$OUT_DIR/stems" --out-dir "$OUT_DIR/stems_web"
```

Then point the widget's player at that folder with `--audio-stems-rel stems_web`.

---

## Step 4 — Build the widget

The widget ships **English** text built in. Other languages are NOT special-cased:
no language is hardcoded in the script — any language is supplied the same way,
as a translated strings file.

**Language rule:** match the user. Detect the language they are writing in (and/or
the system locale). If it is English, run the plain command below. If it is anything
else — Russian, Hebrew, Thai, whatever — localise it:

```bash
# 1. get the canonical English strings schema
$UV python "$SKILL_DIR/scripts/build_widget.py" --dump-strings > "$OUT_DIR/strings_en.json"
# 2. YOU (the agent) translate every value in that JSON into the user's language,
#    keeping keys and {placeholders} intact, and write it to strings_<lang>.json
# 3. pass it with --strings (missing keys fall back to English)
```

Then build (add `--strings "$OUT_DIR/strings_<lang>.json"` when localised). Pass every
layer that exists — the widget shows a panel only when its data is present, so it
degrades gracefully when the user gave audio only:

```bash
$UV python "$SKILL_DIR/scripts/build_widget.py" \
    --core    "$OUT_DIR/result_core.json" \
    --detail  "$OUT_DIR/result_detail.json" \
    --out     "$OUT_DIR/analysis_widget.html" \
    --title   "<track name + version>" \
    --src-audio "<audio filename, e.g. My_Track_[v0.6.2].mp3>" \
    --track-version "<the track's own version, e.g. v0.6.2>" \
    --verdict "<your 1–2 sentence headline for the calm Simple view>" \
    $([ -n "$ALS" ] && echo "--src-als $(basename "$ALS")") \
    $([ -f "$OUT_DIR/result_masking.json" ]      && echo "--masking $OUT_DIR/result_masking.json") \
    $([ -f "$OUT_DIR/result_als.json" ]          && echo "--als $OUT_DIR/result_als.json") \
    $([ -n "$OFFSET" ]                           && echo "--als-offset-s $OFFSET") \
    $([ -f "$OUT_DIR/result_stemmap.json" ]      && echo "--stemmap $OUT_DIR/result_stemmap.json") \
    $([ -f "$OUT_DIR/result_rhythm.json" ]       && echo "--rhythm $OUT_DIR/result_rhythm.json") \
    $([ -f "$OUT_DIR/result_notes_other.json" ]  && echo "--notes $OUT_DIR/result_notes_other.json") \
    $([ -f "$OUT_DIR/result_drums.json" ]        && echo "--drums-breakdown $OUT_DIR/result_drums.json") \
    $([ -f "$OUT_DIR/result_selfsim.json" ]      && echo "--selfsim $OUT_DIR/result_selfsim.json") \
    $([ -d "$OUT_DIR/stems_web" ]                && echo "--audio-stems-rel stems_web") \
    $([ -f "$OUT_DIR/narrative.md" ]             && echo "--narrative $OUT_DIR/narrative.md")
```

**Catalog of all versions (v0.5.12).** After this build (which records THIS run's verdict
into `index.json`), generate the cross-version catalog and rebuild once with `--catalog`
so the widget gets a collapsible **"All analyses"** list at the bottom — every track and
every version, with each past verdict and a RELATIVE link to its widget (so the links keep
working if the whole `track-coach-output/` tree is moved/published):

```bash
CAT="$(python3 "$SKILL_DIR/scripts/run_dir.py" catalog --self "$OUT_DIR")"
# re-run the SAME build_widget command as above, adding:  --catalog "$CAT"
```
The catalog is shown in BOTH Simple and Detailed views (it's reference, not analysis).
`#catalog` in the URL opens it. The verdict shown for each older version is whatever was
passed as `--verdict` when that version was built — so always give a good `--verdict`.

**Write your Producer's Read (Step 5) to `$OUT_DIR/narrative.md` BEFORE this build** so
`--narrative` picks it up — then the widget opens with your words on top. Optional flags
also: `--presence-threshold 0.3` (playing cutoff).

**`--verdict`** is the calm one-glance headline shown at the very top of the Simple view:
the single most important takeaway in 1–2 plain sentences (what KIND of track + the one
thing that matters). Distil it from your Step 5 read. If you omit it, the widget falls
back to the first sentences of `narrative.md` — so always give a narrative at minimum.

The widget storytelling is a FUNNEL (v0.5.4, user-driven): **quick measured facts →
SEE it → understand it → act**. Top → bottom (each panel appears only if its data is present):

**Simple⇄Detailed view (v0.5.11, friend-feedback):** the widget opens in a calm **Simple**
view so a non-power-user isn't overwhelmed — header **verdict** (1–2 sentences, `--verdict`),
vitals, power curve + repeats + locators, the 3 power-driver lanes (energy/brightness/density),
and the top-3 recs. A segmented **toggle** (top-right, `#viewToggle`) flips to **Detailed**,
which adds the stem player/sequencer, the modulation/stereo lanes, the full prose read, all
recs, and the evidence drawer. It is **pure offline JS** (a `body.simple` class + lane re-filter)
— it never recomputes or hits the network, so it's free to flip. Hash deep-links: `…#full` /
`…#simple`. A **source-meta line** (`#srcmeta`) + footer show the analysed **filename, track
version and date** (from `--src-audio`/`--src-als`/`--track-version`/`--analyzed-at`).

0. **Vitals strip** (`#vitals`) — the credible spec-sheet, read in one glance, builds trust
   ("this is real measurement, not vibes"). Single authoritative numbers about the FINISHED
   mix, no time axis: **tempo · key/scale · length · metre · LUFS · true-peak dBTP · dynamic range ·
   stereo width · phase** (from `core["vitals"]`, computed in analyze_core; **metre** merged from the
   .als `time_signature`). Values cross-fade to warn/bad colour at known thresholds (e.g. true peak
   **> 0 dBTP = inter-sample clipping** → red). **Phase correlation (v0.5.10):** energy-weighted L/R
   correlation — +1 mono-safe, ~0.3–0.7 healthy-wide, **< 0 = out of phase** (low end cancels on a
   mono club system) → flagged. A credible mono-compatibility marker. **Metre changes (v0.5.8):** parse_als now extracts
   every `RemoteableTimeSignature` (num/den/beat) and collapses them to transition points
   (`time_sig_changes`); when the metre actually switches mid-track the vitals shows "+N change" and
   the Track Story draws labelled dashed marks at each switch. Constant 4/4 → no marks (honest).
1. **Track story** — VISUAL FIRST: the hero map + player/sequencer is the centrepiece and the
   proof. Everything on one timeline, synced to the player embedded right under it: scenes (named,
   repeat letters A·B·A) + the **power curve** (meta = loudness+busy-ness+brightness) with ★ peak
   + key moments, then that curve **decomposed** into component lanes (energy, brightness, density,
   modulation, stereo width), then compact family texture + locators. One glance = the whole shape.
   **Lane verdicts (v0.5.4):** each component lane carries its one-word over-time conclusion on a
   small pill at its **right edge** (e.g. energy → "stays even", brightness → "gets brighter") —
   the conclusion lives ON the shape. This REPLACES the old metric-card grid (removed): the
   trend cards just echoed these lanes. Verdicts come from `build_story` (`component.verdict`).
   **Form / repeats lane (v0.5.5):** a thin coloured strip ABOVE the story canvas (`#formlane`,
   from `--selfsim`), aligned to the same scale. Each section is a block; **same colour + letter =
   the same musical material returns** (a reprise, repeats outlined). It answers "what repeats?"
   from the AUDIO (self-similarity), not just from which families are active. Hover = part + span;
   click = seek. Hidden if self-sim wasn't run. The label calls out which letters repeat (↻).
   **Per-section LEAD (v0.5.7, upgraded v0.5.10):** each block shows which melodic part *leads* it.
   **Prefers the .als** — the project's own melodic tracks (Violin1, Lead, Operator Pad…) ranked by
   MIDI/clip activity overlapping the segment (families chord/lead/other). This gives REAL instrument
   names and catches reprise-with-variation (the same letter returning led by a different instrument,
   e.g. C first led by Chord Midi, the reprise by the Instrument Rack). Falls back to the loudest
   Demucs stem (minus drums/bass) only when there's no .als — and the label is **hidden when the lead
   doesn't vary** (a uniform "lead: other" from Demucs lumping every melodic part into one stem is
   noise). Shown on wide blocks + in the hover.
   **Timeline callouts (v0.5.3; de-duped v0.5.13):** the located recs are placed on the timeline as
   **downward triangles above the scenes**, lettered A·B·C… and coloured by class (crit/do/concept).
   Under the player sits `#storyCues` — a **COMPACT INDEX**, NOT a second copy of the recs: each item
   is just **letter · when · one-line headline**. **Tap a triangle** → seek + flash its compact index
   item (stays near the player, good for scrubbing). **Tap an index item** → seek + scroll to and flash
   the matching **full** card in "Recommendations" (`flashRec`). **The paragraph + "→ Try" fix live in
   exactly ONE place — the bottom Recommendations cards** (this fixed the v0.5.10 bug where the same
   insight, e.g. "the end sounds like the start", appeared in full both under the player AND at the
   bottom). The same letters tag the recs (rec cards carry `data-let`). `CUES` is built once from
   `D.recs` (time-sorted) and shared by triangles, the index, and the badges.
   **One-card-one-text rule:** an insight's full prose belongs to its Recommendation card only;
   everything else (timeline triangle, `#storyCues` index, lane verdicts) is a pointer/headline to it,
   never a re-statement. The "→ Try" action label is shown ONLY on the bottom rec cards — keep the
   fix-line format consistent (don't render a bare "→ fix" elsewhere).
   Below the sequencer sits the **transport** (v0.5.3 moved it UNDER the lanes): a compact
   **⏮ rewind-to-start** button + **Play** + time. No seek slider — the moving playhead line
   IS the scrub UI; click any chart/lane to jump. (Clicking the lane GUTTER no longer seeks to 0.)
   The **stem sequencer** (`#stemlanes`): one playable lane per stem with **M/S** boxes
   (mute/solo, click — toggling them no longer drops the playhead). Same PADL=70 scale as the
   story, one shared playhead. **Stacked frequency layers (v0.5.6, user's "area chart" idea):**
   each lane's waveform is drawn as **three STACKED bands** — low (red) / mid (green) / high (blue),
   bottom→top — instead of one blended colour. Total height = loudness; each band's height = its
   share of the energy. So **several tall bands at once = those frequencies hit together** (kick +
   snare), which a single mixed hue used to hide. Drawn on a **fine ~0.25 s grid** — masking.py emits
   a dedicated `viz` envelope (broadband + low/mid/high per stem); `bandFracs()` feeds the stack.
   **IMPORTANT: run masking on the SAME stem set the player draws** (all 6 if you used htdemucs_6s →
   `stems_6s/`), or guitar/piano lanes get no band detail and fall back to a flat family colour. The
   **drums lane** stacks kick/snare/hat hit-density with kick at the BOTTOM (low→high); its labels sit
   in the **left gutter**, off the waveform. A **slim legend** (`#seqKey`) explains the **stacked
   bass/mids/highs layers** and **≈ name =
   which project track this stem sounds like, shown only when confident** (the trivial height=loud
   and the M/S rows were dropped per user feedback). The **bridge label** on a lane is shown only
   when the stem map is genuinely **confident** (verdict `clear`) — otherwise nothing, or
   `near-silent` for a truly empty stem. No more wrong `≈ family` guesses.
2. **Producer's read** — your written narrative (from `--narrative`). Sits UNDER the visual now
   (v0.5.4): the diagnosis in prose, after the user has seen the track. Weave the vitals' MEANING
   into it ("loud at −9 LUFS but DR 12 keeps it punchy", "true peak clips at +0.5 dBTP").
3. **Recommendations** (renamed from "Start here", v0.5.4) — the few things worth attention, most
   important first (auto-generated). **Time-bound vs global is now VISUAL:** a rec tied to a moment
   gets a yellow **⏱ {timecode}** pill and is clickable (jump + scroll to story); a global rec gets
   a quiet **"whole track"** pill. Each rec also carries an explicit highlighted **"→ Try"** line
   (the concrete fix option(s)) so the action is visible, not buried. Body = what's wrong + why;
   Try = what to do (often two options, "… — or …"). Driven by `fix` + `t` fields per rec.
4. **Evidence & detail** — a **collapsed `<details>` drawer** (`#evidence`) holding the power-user
   panels: **tonal balance** · **arrangement from the project** (MIDI blocks + audio strips +
   locators) · **stem ↔ project** mapping · **rhythm & separation quality** · **transcribed notes**.
   Collapsed by default; opening it dispatches a resize so its canvases draw at full width.
   **Tonal balance (v0.5.10):** a bar chart of the mix's average spectrum per octave band
   (`core["tonal_balance"]` from analyze_core), coloured low→high. Reference-free: it flags bands
   that stick out from their NEIGHBOURS (a resonance = boxy/harsh) or sit in a hole (dull/thin) via
   `dev_db`, rather than against a guessed genre target. A deviation ≥4 dB also emits a
   `tonal_resonance` recommendation with a concrete EQ move.
   **The metric-card grid was REMOVED (v0.5.4):** trend cards duplicated the Track Story lanes
   (now carried as lane-edge verdicts); the snapshot facts moved into the vitals strip. `build_cards`
   is no longer called.
   **Declutter (v0.5.2):** the standalone *automation small-multiples*, *stem frequency
   heatmap*, *drum breakdown* and *masking summary* panels were **removed** — the sequencer's
   colour-as-frequency + drums lane now carry that information, and raw automation curves
   weren't actionable. Their data still rides in the payload (unused) so nothing else breaks.

Naming: keep the UI **genre-neutral** — the modulation metric is "Modulation" (not
"wobble"); it measures any rhythmic movement (LFO/tremolo/sidechain/gating). `analyze_core`
also emits `stereo_width` (0 mono…1 wide); no extra flag needed.

Then open it (`open "$OUT_DIR/analysis_widget.html"`) and tell the user — **in their
language** — that the widget is ready: hover gives a shared cursor across all lanes,
the playhead is synced across every chart (click anywhere to scrub), and the project layers (arrangement,
automation) are the ground truth that separation only approximates.

---

## Step 5 — The Producer's Read (LEAD WITH THIS)

This is the heart of the tool. Before any tables, talk like a great, experienced
producer listening over the user's shoulder — warm, specific, opinionated, plain
language. The data is your ears: you have more than most tools (arcs, sections,
masking, full arrangement from the .als, automation envelopes, per-stem rhythm,
pattern letters from `build_story`). Synthesise it into a musical read, not a readout.

**Write it in the user's language. Ground every claim in a measured fact** (cite the
moment/number in passing, e.g. "the peak lands late, ~4:25"). Never invent what the
data can't show — say "from the arrangement / automation / arcs I can see…", not "I hear".

### 5.1 — First: what KIND of track is this? (classify before judging)
A 2–3 sentence read of the track's nature, inferred from the data:
- **Song vs instrumental**: vocals stem present & active + verse/chorus-like repetition ⇒ a song; vocals near-empty ⇒ instrumental.
- **Textural/ambient vs groove/structured vs narrative**: low onset density + flat arcs + few sections ⇒ textural; clear drops/breakdowns + strong drum families ⇒ groove/structured (electronic); strong endpoint change + rising arcs ⇒ narrative/journey.
- **Genre family & how it works**: infer from tempo, tonality (tonal vs percussive), bass/drum character, section pattern (A/B/A letters). State plainly how the track operates ("drop-based bass tune that rides groove and texture, not harmony", "hypnotic loop", "build-and-release").
Get this right first — the advice that follows depends on what the track is *trying* to be.

### 5.2 — Then: the scene-by-scene read (with opinions + concrete moves)
Walk the track using the `build_story` scenes, pattern letters and moments. For the
moments that matter, give a real producer's opinion AND a concrete move, with timecodes:
- name structure in musical terms: "intro motif", "that's a variation of the first theme, not a new idea", "reprise of A but underdeveloped", "the drop at 2:30".
- judge it: "the drop runs long and the energy on the way out sags", "the breakdown's there but there's only one — the back half drags", "the title promises a drifting wobble but the modulation barely moves".
- prescribe, concretely and in producer language, framed as options not orders:
  "I'd accelerate the wobble into the climax", "open a filter through the build so brightness is intentional", "widen the lead across the stereo field and push 8–12 kHz air", "carve a second, deeper breakdown before the last drop", "do the low-end EQ on the bass *group*, not the separated stem". Pull these from the recommendations + intention-vs-result + masking + arrangement data.

Keep it to the few things that actually matter — the same priority as the widget's
"Recommendations". Opinionated, but the author decides; no equipment/plugin names guessed from audio.

### 5.3 — (Optional) inject the read into the widget
You may pass your written read to the widget as a top "Producer's read" panel via
`--narrative narrative.md` (plain text/markdown). The widget renders it above the
visual Track Story, so the page opens with words first, charts as evidence.

---

## Step 6 — Three-layer evidence (the numbers behind the read)

**Read the JSON files** — do NOT invent numbers. Every number in your response must come directly from result_core.json or result_detail.json or result_masking.json.

Structure your response exactly as follows:

---

### 📊 Measured
*(exact values from scripts — no interpretation yet)*

- Duration: [duration_s]s · Tempo: [tempo] BPM
- Energy arc: trend [energy_trend:+.3f] · variety [energy_lv:.3f]
- Brightness arc: trend [brightness_trend:+.3f] · variety [brightness_lv:.3f]
- Density arc: trend [density_trend:+.3f] · variety [density_lv:.3f]
- Endpoint cosine (feature stack): [endpoint_cosine:.4f]
- Endpoint cosine (MFCC): [mfcc_cosine:.4f]
- Wobble rate: [wobble_rate_start_hz:.1f] Hz → [wobble_rate_end_hz:.1f] Hz (median [wobble_rate_median_hz:.1f] Hz)
- Swing deviation: [swing_global_ms:.0f] ms
- Tonality mean: [tonality_mean:.3f]
- Crest factor mean: [crest_mean:.2f]
- Sections detected: [len(section_bounds_s)]

*(Deep only)*
- Masking: [zone] → [pct_masked]% of windows masked (mean diff [mean_diff_db] dB, threshold 12 dB)

---

### 🔍 What this typically means
*(from interpretation.md — labelled as typical, not diagnostic)*

For each metric where the value is notable, cite the relevant range from interpretation.md.
Keep this factual and hedge clearly: "typically", "often indicates", "in electronic music this usually means".

**Masking principle (always include if masking data present):**
> Low dB in a band ≠ no material. If low_mid is masked, the mid content is
> present but buried — not absent.

---

### 🎛 Up to you
*(observations only — no directives, no equipment names)*

Summarise what patterns are present without telling the author what to do.
Examples of allowed phrasing:
- "The wobble rate drifts from X to Y — this is a real development vector even though the energy arc is flat."
- "The endpoint cosine is 0.97 — the end is spectrally similar to the beginning. Whether that's the intended character is your call."
- "Low-mid masking is present in [N]% of windows — the mid content appears to be there but buried in those moments."

Forbidden in this section:
- "You should...", "Try...", "Consider removing...", "Add..." — no directives
- Naming equipment, plugins, or processing inferred from audio
- Contradicting the data (e.g. saying "development is strong" when energy_trend ≈ 0.0)

---

## Checklist before saying "done"

- [ ] All numbers in the output came from JSON files, not memory
- [ ] No equipment/plugins named based on audio inference
- [ ] No structure claimed that contradicts the energy arc data
- [ ] Mid described as masked (not absent) if low_mid energy is low but material is present
- [ ] Output ends with "up to you" layer, not a directive
- [ ] Cross-platform not claimed (macOS only)
- [ ] Demucs wait filled with substantive text (not silence)
- [ ] All dependency versions pinned
- [ ] No monetisation language
