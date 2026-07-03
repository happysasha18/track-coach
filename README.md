# track-coach

**A local, fully offline compositional coach for music producers. Point it at a track; it builds one page where you can hear everything it found.**

*macOS (v1) · runs entirely on your machine · a [Claude Code](https://claude.com/claude-code) skill · version in every page footer and in [`CHANGELOG.md`](CHANGELOG.md)*

![The analysis page: vitals, and the track's shape over time](docs/hero.png)

Give it a bounce — and, if you like, the Ableton project behind it — and it runs a full analysis, then builds one self-contained HTML page: a synced multi-stem player, the real arrangement from your project, the track's shape over time, and a short list of specific, evidence-backed observations. Nothing leaves your machine and nothing is invented: every claim on the page traces back to a measurement, and the creative call stays yours. Every run is kept, so your work builds into a library instead of a folder of one-off reports.

---

## What it does

### Hear what you're looking at

The page is built around a player, not a report. Each separated stem gets its own lane — play, seek, mute, solo — and a single playhead runs through every chart on the page. Click any point on any graph and the track jumps there, so a spike on a curve is never abstract: you hear the exact moment it describes. Lanes are drawn as stacked low / mid / high bands, so you see *what* each part is doing, not just that something is playing.

![The synced stem player: one lane per part, one playhead across every chart](docs/player.png)

### Nothing gets lost

Every analysis is stored under its own version and date — re-running a track never overwrites an earlier result. The library page lists everything you've analysed: one row per version with its spectral signature, vitals, mood and style tags, and a one-button preview player, sortable and searchable. Each track's own page carries its full version history, so you can open last month's bounce next to today's and see what actually moved.

![The library: every track and version in one sortable table](docs/catalog.png)

### Where it sits among your music

A full run places the track in context. It names the reference directions the track leans toward — artists whose music you've analysed as references — and shows, facet by facet, where you're already close and where you go your own way. It also finds the nearest siblings in your own library: which of *my* tracks does this one sound closest to — useful for building a set, planning a transition, or an honest A/B. Closeness is shown as colour and per-facet bars, never a score: the coach observes, it doesn't grade. Reference tracks are kept in their own catalog, so other people's music never mixes into your library.

![The reference read: facet-by-facet bars against the nearest direction](docs/similarity.png)

*Similarity needs the full analysis — a quick read has no fingerprint to compare.*

---

## Quick start

Get the skill into Claude Code's skills folder and run the installer once:

```bash
git clone https://github.com/happysasha18/track-coach.git ~/.claude/skills/track-coach
bash ~/.claude/skills/track-coach/setup.sh
```

`setup.sh` is safe to re-run — it checks every dependency (Homebrew, ffmpeg, uv, Python 3.11) and installs only what's missing. If anything fails, it prints the exact command to fix it; see [`references/install_troubleshooting.md`](references/install_troubleshooting.md).

Then open Claude Code and either use a command:

| Command | What it does |
|---|---|
| `/tc` | Full analysis — stems, the synced player, similarity, all evidence. A few minutes. |
| `/tc-quick` | Quick read — the track's shape, vitals, and top observations, no stems. Seconds. Upgradeable to a full run later without redoing what's done. |

— or just talk about your track:

> *"why does my track sound stuck?"* · *"analyse this project"* · *"compare these two versions"*

Point it at a project folder and it finds the latest render and the `.als` itself, asking before it guesses anything that matters.

---

## The page it builds

The player and the reference read above are two panels on one page. The rest:

**Arrangement.** The real project arrangement straight from the `.als`: MIDI blocks (brightness = note density), audio-clip strips, and labelled locators — all aligned to the rendered audio, on the same timeline as the player. This is ground truth from the project, not an approximation from the audio.

![The arrangement from the Ableton project, aligned to the rendered audio](docs/arrangement.png)

**Intention vs. result.** Automation envelopes from the `.als` — filter, gain, pitch, sends — each scaled to its own range and plotted against the measured brightness arc. Where a curve flattens but the sound keeps moving, you can see where they drifted apart.

**Stem ↔ project map.** Each separated stem is matched to the real project tracks by envelope similarity. Confident matches are named; ambiguous or near-silent stems are labelled honestly rather than guessed.

**Recommendations.** A short ranked list — most important first — each card carrying the evidence behind it and one concrete move. Timecoded cards seek the player to their moment on click.

**Producer's read.** A plain-language account of how the track develops: which dimensions actually trend (louder, brighter, busier, wider) and which sit idle.

All content panels are collapsible; the Evidence drawer (arrangement, stem map, rhythm, transcribed notes, tonal balance) is collapsed by default — there when you want the depth, out of the way when you don't.

Three views on one ladder — each adds to the one before, and nothing you saw in a lighter view disappears in a heavier one. The page remembers which view you last used.

| View | What you see |
|---|---|
| **Quick read** | Vitals, structure bar + power curve, single-track mix player, producer's read, top recommendations. Fast — no stem separation. A note says what a full run adds. |
| **Simple** (default, full analysis) | Everything in Quick, plus the synced multi-stem player. The Evidence drawer is available but collapsed. |
| **Detailed** | Adds the per-stem visualisation lanes, the modulation and stereo-width curves, and the full recommendation list. Mute / solo live here. |

---

## How it reads a track

The coach keeps two things separate. **The mirror** — player, graphs, arrangement, automation — shows what is actually there, reading your project file directly rather than guessing from audio. **The cards** fire selectively: where a section stalls, where a strong move is worth naming, where intention and result have drifted apart — and each card names the measurement it rests on.

Three layers, never blurred: what was **measured** (exact numbers, nothing inferred), what it **means** (a concrete reading — not *"energy is low"* but *"bass dominates 250–500 Hz for the first two minutes; the mids are present but buried"*), and **your call** — the creative decision stays yours. The same track gives the same answer every time: it reports what it measured, not a re-improvised opinion.

---

## What it measures

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

Reference directions (the similarity layer) are measured fingerprints too: web-described style traits for each direction are cross-checked against measurement — ★ confirmed directly, ☆ confirmed indirectly, or flagged as "web says; our tracks don't show it." The web suggests; measurement decides.

---

## Where things live

Every run is a self-contained HTML file, versioned and timestamped so re-analysing a track never overwrites an earlier result. Run directories live under `~/.track-coach/projects/<track-slug>/` — outside your Ableton project folders, so a folder tidy-up can't touch them. The player needs the co-located `stems_web/` folder; everything else is embedded in the page.

Every finished widget is deposited automatically to the global library at `~/.track-coach/library/`. Its catalog page gives a sortable, searchable row per track and version — spectral signature, vitals, mood/style tags, and a one-button preview player. Open it with `scripts/library.py catalog --open`.

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
