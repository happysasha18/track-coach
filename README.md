# track-coach

**A full-stack compositional coach for music producers — a [Claude Code](https://claude.com/claude-code) skill.**

Give it a track (and optionally your Ableton project), and it runs the complete analysis pipeline, then builds **one offline, self-contained HTML widget** with a synced multi-stem player, the real arrangement on a timeline, masking and rhythm diagnostics, and concrete, specific feedback — not "energy is low," but *"bass masks the mids in 250–500 Hz during bars 8–24"* and *"the cutoff automation ends at 2:45 but brightness keeps rising to 3:10."*

> **Status:** early / unstable (`v0.5.10`). macOS-first. Built and refined hands-on.

![Track story — the whole song at a glance](docs/hero.png)

<sub>**The whole song at a glance:** a colour-coded form map (repeated sections share a colour), the power curve broken into the lanes that drive it — energy, brightness, density, modulation, stereo width — drum lanes underneath, and a synced stem player at the bottom. Press play; click anywhere to jump.</sub>

---

## What it does

Everything runs by default — no need to ask for "deep mode":

- **Development-arc analysis** — energy, brightness, loudness (LUFS), and how the track evolves over time
- **Stem separation** (Demucs) — drums / bass / vocals / other, with a synced player (play / seek / mute / solo, playhead linked to every chart)
- **Frequency masking** — which stem buries which, in which band, during which bars
- **Per-stem rhythm + separation quality** — groove consistency and how cleanly each stem was isolated
- **Drum-hit breakdown** — kick / snare / hat detection and timing
- **Note transcription** — basic-pitch on the melodic content
- **Ableton `.als` parsing** — tracks, MIDI + audio clips, automation envelopes, locators
- **Intention vs. result** — overlays your automation against what actually happened in the audio
- **Demucs-stem ↔ real-track map** — connects separated stems back to your project's tracks

All wrapped in three honest output layers: **Measured** (exact numbers only) → **What this typically means** (specific interpretation) → **Up to you** (patterns, never directives).

---

## A look at the output

| Arrangement on a timeline | Stems + synced player | Automation: intention vs result |
|---|---|---|
| ![arrangement](docs/arrangement.png) | ![stems](docs/stems.png) | ![automation](docs/automation.png) |

---

## Install

macOS (v1). Requires Python 3.11, `ffmpeg`, and the deps in `requirements.txt`.

```bash
./setup.sh
```

`setup.sh` installs [Homebrew](https://brew.sh) (if missing), `ffmpeg`, and [`uv`](https://github.com/astral-sh/uv), then the pinned Python deps. It will ask **once** for your Mac login password — that prompt comes from the Homebrew installer itself.

See [`references/install_troubleshooting.md`](references/install_troubleshooting.md) if anything fails.

---

## Usage

This is a **Claude Code skill** — drop the folder into `~/.claude/skills/track-coach/` and just talk to Claude about your track:

> *"why does my track sound stuck?"* · *"analyse this project"* · *"compare these two versions"*

Claude grabs the audio (and `.als` if available), runs the pipeline, and opens the widget. You can also point it at a whole project folder and it'll find the latest render and `.als` itself.

---

## How it's built

| | |
|---|---|
| `SKILL.md` | Orchestration — how Claude runs the pipeline and writes the read-out |
| `scripts/` | The analysis engine (Python): `analyze_core`, `masking`, `separate`, `parse_als`, `build_widget`, … |
| `references/` | `methodology.md` (the conceptual framework), `interpretation.md` (numeric ranges), troubleshooting |
| `docs/` | Screenshots |
| `setup.sh` · `requirements.txt` | Environment setup, pinned deps |

---

## License

Personal project. All rights reserved (for now).
