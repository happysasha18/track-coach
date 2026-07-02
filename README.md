# track-coach

**A local, fully-offline compositional coach for music producers — a [Claude Code](https://claude.com/claude-code) skill.**

Drop the folder into `~/.claude/skills/track-coach/`, run `bash setup.sh` (safe to re-run), then just talk to Claude about your track. Point it at an audio file (and optionally your Ableton project), and it runs the complete analysis pipeline, then builds **one self-contained offline HTML widget**.

The widget is not a dashboard of numbers. It's a mirror: the synced player, the arrangement from your project, the graphs, and the cards all live on one page, all pointing at the same moments in the track — so you can hear what you're looking at.

> **Status:** early and actively evolving. macOS-first (v1). The exact version is printed in every widget's footer and tracked in [`CHANGELOG.md`](CHANGELOG.md).

---

## Philosophy

The coach does two things, and keeps them distinct.

**The mirror** — player, graphs, arrangement, automation — shows what is actually there. It reads your project file directly rather than guessing from audio alone, so the arrangement view is ground truth, not an approximation.

**The cards** fire selectively: where a section stalls, where a strong move is worth naming, where intention and result have visibly drifted apart. A card names the signal behind it (*"the bass and the lead overlapping around 290 Hz for half the track"*) so you always see what the advice rests on.

Three layers, always kept separate:

1. **Measured** — exact numbers, measured — nothing inferred
2. **What it means** — a concrete reading: not *"energy is low"* but *"bass dominates 250–500 Hz in the first two minutes; the mids are present but buried"*
3. **Your call** — the creative decision stays yours; the coach names the pattern and shows its evidence

The same track gives the same answer every time — it reports what it measured, not a re-improvised opinion. The same instinct runs through this whole skill family: facts over plausible fiction, the decision always yours.

---

## What it analyses

**From the audio:**

- Energy, brightness, density, modulation and stereo-width arcs over time; section structure (self-similarity / recurrence)
- Stem separation — up to 6 stems; per-stem character labels derived from measurement (`kick`, `bass`, `lead`, `chord`, `pad`…), never the separator's raw names
- Frequency masking between stems (e.g. *"bass masks mid in 250–500 Hz during bars 8–24"*)
- Per-stem rhythm: onset density, timing, syncopation, separation confidence
- Drum-hit breakdown: kick / snare / hat density in the drums stem
- Note transcription: pitch content per stem, polyphony, mono vs chord character
- Vitals: tempo, key/scale, length, LUFS, true-peak dBTP, dynamic range, stereo width, phase correlation

**From the Ableton `.als` (when provided):**

- Every arrangement track: MIDI clips (note density → brightness) and audio clips, aligned to the rendered audio
- Automation envelopes by target parameter (filter cutoff, gain, pitch, sends…)
- Locators and time-signature changes
- The render offset — which locator the bounce starts from — so project time and audio time line up exactly

**Reference layer:**

- The track is compared to named reference directions (other artists / styles). Each direction is a measured fingerprint; the widget shows how far the track "leans toward" each one, per facet.
- Web-described style traits for each direction are cross-checked against measurement: ★ confirmed directly, ☆ confirmed indirectly, or flagged as "web says; our tracks don't show it." The web suggests — measurement decides.

---

## The widget

One self-contained HTML file. Everything is offline; data is embedded. The player needs the co-located `stems_web/` folder for audio.

**Synced player.** Play / seek / mute / solo; the playhead is linked to every chart. Click anywhere on any graph to jump there. In full mode, each stem has its own lane with stacked frequency bands (low / mid / high) so you can see *what* is playing, not just *that* something is.

**Arrangement.** The real project arrangement straight from the `.als`: MIDI blocks (brightness = note density), audio-clip strips, and labelled locators — all aligned to the rendered audio on the same timeline as the player.

**Intention vs. result.** Automation envelopes from the `.als` — filter, gain, pitch, sends — each scaled to its own range, plotted against the measured brightness arc. Where a curve flattens but the sound keeps moving, you can see where they drifted apart.

**Stem ↔ project map.** Each separated stem is matched against the real project tracks by envelope similarity. Confident matches are shown; ambiguous or near-silent stems are labelled honestly.

**Reference read** (shown in the Detailed view of a full run). Per-facet bars comparing the track to each reference direction, with selectable direction tabs. Followed by a "What the web says about [artist]" panel: genre/era, a prose blurb, and the full trait list sorted by evidence strength. Both the widget panel and the standalone reference side page render from the same source, so they can't drift.

**Recommendations.** A short ranked list — most important first — with the evidence behind each card and a concrete move. Timecoded cards seek the player to their moment on click.

**Producer's read.** A plain-language account of how the track develops: which dimensions actually trend (louder, brighter, busier, wider) and which sit idle. Written into the widget from the analysis.

All content panels are collapsible. The Evidence drawer (arrangement, stem map, rhythm, transcribed notes, tonal balance) is collapsed by default — available when you want the depth, out of the way when you don't.

---

## Views

Three views on a monotonic ladder — each adds to the one before; nothing visible in a lighter view disappears in a heavier one.

| View | What you see |
|---|---|
| **Quick read** | Verdict, vitals, structure bar + power curve, single-track mix player, producer's read, top recommendations. Fast — no stem separation. A note says what a full run adds. |
| **Simple** (default, full analysis) | Everything in Quick, plus the synced player (full stem audio, one transport). The Evidence drawer is available but collapsed. |
| **Detailed** | Adds the per-stem visualisation lanes, the modulation and stereo-width curves, and the full recommendation list. Mute / solo live here. |

The view preference is remembered in `localStorage` — open any track and it lands in whichever view you used last. A first-time open defaults to Simple (calm). A `#detailed` link is a one-shot entry that doesn't change the stored preference.

The Simple/Detailed toggle is pure client-side JS — it never recomputes or hits the network, so flipping it is free and instant.

---

## Commands

**`/tc`** — full deep analysis. Runs stem separation, all analysis steps, and builds the widget with the per-stem player and full evidence. Takes a few minutes (stem separation runs on Apple MPS on Apple Silicon — fast).

**`/tc-quick`** — fast calm read, no stems. Runs core + detail analysis only, encodes a single-track mix player, and builds the widget in seconds. Can be upgraded to a full run later without re-running what's already there.

The skill triggers automatically when you mention a track, a mix, an arrangement, an `.als` file, or ask things like *"why does this sound stuck?"* or *"analyse my project."* No need to use the slash command explicitly — just talk about your track.

---

## Install

macOS only (v1). Requires Python 3.11 (managed by `uv`), `ffmpeg`, and the pinned Python deps.

```bash
bash setup.sh
```

`setup.sh` is idempotent — safe to re-run; already-installed tools are detected and skipped in seconds. What it does, in order:

1. **Homebrew** — installs it if missing. This is the only step that may prompt for your Mac login password (once, from the Homebrew installer itself). Everything after is hands-off.
2. **ffmpeg** — via `brew install ffmpeg` (needed for audio transcoding).
3. **uv** — Python package and runtime manager; installs to `~/.local/bin` without sudo.
4. **Python 3.11** — `uv` can fetch its own, so this is a convenience check, not a hard requirement.
5. **node / npm** — optional; only needed if you want to (re)install Claude Code itself.
6. **Package cache warm-up** — pre-fetches the analysis packages (~200 MB on first run: librosa, torch, Demucs, basic-pitch) so the first real track starts instantly.

If anything fails, the script prints the exact command to fix it. See [`references/install_troubleshooting.md`](references/install_troubleshooting.md) if you hit an issue.

**Key Python deps (pinned):** `numpy==1.26.4`, `librosa==0.10.2`, `scipy==1.13.1`, `scikit-learn==1.5.1`, `pyloudnorm==0.1.1`; deep mode adds `torch==2.3.1`, `torchaudio==2.3.1`, `demucs==4.0.1`; note transcription adds `basic-pitch[onnx]`. Full list in [`requirements.txt`](requirements.txt).

Already have `ffmpeg` and a Python 3.11 environment? Install the deps from `requirements.txt` yourself and skip the script entirely.

---

## Usage

Drop the folder into `~/.claude/skills/track-coach/` and talk to Claude:

> *"why does my track sound stuck?"*  
> *"analyse this project"*  
> *"compare these two versions"*

Claude finds the latest render and `.als` from a project folder automatically, runs the pipeline, and opens the widget. While stem separation runs it narrates what it's looking for.

The pipeline runs as three steps: **measure** (deterministic scripts, same input → same output) → **interpret** (the skill writes the producer's read) → **render** (builds the widget once, deposits it to the global library).

---

## Output

**The widget** — a self-contained HTML file per run, versioned and timestamped so re-analysing the same track never overwrites a previous result. Run directories live under `~/.track-coach/projects/<track-slug>/` — outside your Ableton project folders so a folder tidy-up can't touch them. The player needs the co-located `stems_web/` folder; everything else is embedded.

If you have pre-0.9.5 run directories sitting inside Ableton project folders, consolidate them with `python scripts/track_analyzer.py migrate` (dry-run) or `migrate --apply` (execute). Version history is preserved.

**The global library** — every finished widget is deposited automatically to `~/.track-coach/library/`. A global catalog page (`index.html`) gives a sortable, searchable row per track/version: spectral signature ribbon, vitals, mood/style tags, and a one-button preview player. Open it with `scripts/library.py catalog --open`.

---

## Under the hood

| | |
|---|---|
| `SKILL.md` | Orchestration — how Claude runs the pipeline and writes the read |
| `scripts/track_analyzer.py` | One-command entrypoint: `analyze` (measure) then `build` (render) |
| `scripts/` | Analysis units: `analyze_core`, `analyze_detail`, `masking`, `separate` (Demucs), `parse_als`, `self_similarity`, `transcribe` (basic-pitch), `rhythm_quality`, `drum_breakdown`, `map_stems`, `make_web_stems`, `build_widget`, `library` |
| `data/reference_web_notes.json` | One source for reference web notes (widget panel + side page) |
| `tests/` | Regression suite (run with `pytest` inside the project's pinned `uv` environment) — asserts on the real rendered HTML, not source fragments |
| `references/` | `methodology.md`, `interpretation.md`, `install_troubleshooting.md` |
| `docs/` | Screenshots, `SPEC.md`, `TEST_MATRIX.md` |
| `setup.sh` · `requirements.txt` | Environment setup, pinned deps |

Built on [`librosa`](https://librosa.org) (analysis), [Demucs](https://github.com/facebookresearch/demucs) (stem separation), [basic-pitch](https://github.com/spotify/basic-pitch) (note transcription), and `ffmpeg` — all run deterministically through [`uv`](https://github.com/astral-sh/uv).

---

## License

[MIT](LICENSE) © Alexander Abramovich — covers this repository's own orchestration and analysis code. Deep mode pulls in **Demucs** and **PyTorch**, which carry their own licenses; check those before any commercial or redistributive use.
