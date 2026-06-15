# track-coach — Interpretation Guide

**PURPOSE OF THIS FILE**: Source for the "what this typically means" layer in the three-layer output.
Every interpretation here is *typical, not diagnostic*. The author decides what applies.

Output format rule (enforced in SKILL.md):
> **Measured** → exact numbers from scripts
> **What this typically means** → from this file, clearly labelled as "typical"
> **Up to you** → no directives. Author decides.

---

## endpoint_cosine

| Range | Typical meaning |
|---|---|
| 0.95–1.00 | End is spectrally very similar to beginning. Large-scale irreversible change is low. The track may vary but tends to cycle back. Common in loop-based and ambient electronic music. |
| 0.85–0.94 | Moderate difference between start and end. Some material has entered or transformed. |
| < 0.85 | Clear large-scale change. The end is spectrally distinct from the beginning. |

**Not a verdict.** A high cosine can be intentional (hypnotic, groove-focused, ambient drone). The value is knowing which kind of track you're making.

---

## energy_trend / brightness_trend / density_trend

(Pearson r, range −1 to +1)

| Range | Typical direction |
|---|---|
| > +0.3 | Feature generally rises across the track |
| −0.2 to +0.2 | Feature is roughly flat — no strong directional arc |
| < −0.3 | Feature generally falls across the track |

**Important**: a flat trend does not mean nothing happens. A track can have high local_var (lots of local change) with a flat trend. These measure different things.

If energy_trend ≈ 0 AND local_var is high AND endpoint_cosine ≈ 1.0:
→ Typically: the track has rich internal variety but no large-scale arc. Holds interest section by section but the overall shape is flat.

---

## modulation rate drift (start → end)  — genre-neutral

Measures how fast the sound pulses/modulates (any rhythmic movement: LFO, tremolo,
sidechain pump, gating, filter movement), read from the amplitude envelope. Internal
JSON key is still `wobble_rate`, but the UI calls it **Modulation** — don't use the word
"wobble" in output unless the user's own track/genre uses it.

| Pattern | Typical meaning |
|---|---|
| Stable across track | Modulation rate is consistent — the movement character doesn't evolve. |
| Rising | Modulation accelerates over time — a real development vector; the movement intensifies. |
| Falling | Modulation decelerates — settling, relaxing, resolving. |

Even if energy is flat, a clear modulation-rate drift is a form of irreversible development
(the movement state at the end differs from the start).

## stereo_width (0 mono … 1 wide)

Side/(mid+side) energy per window. ~0 = centred/mono, higher = wider image.

| Pattern | Typical meaning |
|---|---|
| Low & flat | Narrow, centred mix — focused but can feel small; intentional for mono-compatible club low-end. |
| Rising into sections | The image opens up (often pads/FX/reverb widening) — a common lift into drops/choruses. |
| Very high | Wide — big and immersive, but watch mono-compatibility and a hollow centre. |

Width is character, not quality — a tight centred track and a wide one are both valid.

---

## swing_global_ms

| Range | Typical meaning |
|---|---|
| 0–5 ms | Tightly quantised. Grid-locked. |
| 5–15 ms | Light groove, slight humanisation. |
| 15–30 ms | Free, humanised groove. Beats fall away from the grid in a natural-feeling way. |
| > 30 ms | Heavy swing or significant timing looseness. |

**Not a quality judgment.** Quantised can be intentional (industrial, techno precision). Loose can be intentional (IDM, organic feel).

---

## Masking (Deep mode only)

**The core principle — memorise this:**
> Low energy in a frequency band ≠ absence of material.
> Check masking BEFORE concluding a band is "empty" or "hollow".

If band_rms for the mid stem in low_mid (250–600 Hz) is low, there are two possible explanations:
1. There is genuinely little mid content in that pocket
2. The bass layer in that pocket is 12+ dB louder, masking the mid content psychoacoustically

The masking analysis distinguishes these by comparing stem energy in the same band.

### low_mid masking (250–600 Hz — bass vs lead/chords)

| pct_masked | Typical reading |
|---|---|
| < 20% | Low conflict. Mid content has space in this pocket most of the time. |
| 20–50% | Moderate masking. Some windows have bass dominating the low-mid. Audible as "muddiness" in those sections. |
| > 50% | Heavy masking. The low-mid pocket is dominated by bass for most of the track. Mids present but buried. |

### sub masking (20–80 Hz — bass vs kick)

| pct_masked | Typical reading |
|---|---|
| < 30% | Reasonable coexistence. Bass and kick have some separation in the sub. |
| > 50% | Heavy sub congestion. Both instruments are full in the sub simultaneously. You feel pressure but lose individual punch. |

### Typical remedy zone (information, not instruction)

When low_mid masking is high, the conflict is typically in the 250–500 Hz range. What to *do* about it is the author's decision — there are multiple valid approaches (notch on bass, shelving on lead, sidechain, re-arranging notes, different bass timbre). This tool identifies *that* the conflict exists and *when* in the track; the author decides *whether and how* to address it.

---

## tonality_mean

| Range | Typical meaning |
|---|---|
| > 0.7 | Predominantly tonal material (pitched instruments dominate) |
| 0.4–0.7 | Mixed — significant percussive and tonal energy |
| < 0.4 | Predominantly percussive/atonal texture |

---

## crest_mean

(Crest factor: peak/RMS, higher = more transient punch)

| Range | Typical meaning |
|---|---|
| > 6 | Plenty of dynamic headroom, transients intact |
| 3–6 | Moderate compression, transients somewhat softened |
| < 3 | Heavy compression or limiting present |

**Context**: EDM mixes often sit in 3–5 during drops. Lower crest is not inherently bad — depends on genre and intention.

---

## harmonic change

| Pattern | Typical meaning |
|---|---|
| Consistently low | Drone or static harmony — chords barely move. Intentional in hypnotic/drone IDM. |
| Mostly low with spikes | Harmonic movement concentrated at specific moments (transitions, climaxes) |
| Consistent high | Fast harmonic movement throughout — complex, demanding, or erratic |

---

## articulation (onset density, onsets/sec)

| Range | Typical meaning |
|---|---|
| < 2/s | Sparse, legato, sustained material |
| 2–6/s | Moderate activity |
| > 8/s | Dense, choppy, percussive |

---

## Sidechain notes (context for Deep mode)

When user-provided stems are available, the masking analysis can give direct evidence on sidechain relationships. If kick stem RMS in sub peaks exactly when bass stem RMS dips, that typically suggests sidechain compression kick→bass is working. If they both peak simultaneously, there may be sub congestion.

These are observable patterns, not definitive electrical evidence of sidechain routing.

---

# Project-aware & per-stem layers (B / C / D / F / G)

These come from the newer scripts: `map_stems.py` (B), `rhythm_quality.py` (C),
`drum_breakdown.py` + `transcribe.py` (D), and `parse_als.py` audio-clips + automation
(F/G). Same rule: typical readings, not verdicts.

## Stem ↔ project match (map_stems.py)

Each Demucs stem is correlated *in time* with each real project family (when the stem
gets louder vs. when each part plays).

| Verdict | Typical reading |
|---|---|
| **clear** (r ≥ ~0.25, clearly ahead of 2nd) | The stem follows one project part — trust it for EQ/level reads. |
| **mixed** (top two within ~0.1) | The stem blends several parts; separation didn't isolate one. Read with care. |
| **weak** (best r < ~0.25) | No project part tracks this stem — it's near-empty or leakage. Don't base decisions on it. |

**Why weak ≠ broken:** parts that play almost continuously (a pad, a constant hat) have
little on/off variation, so timing correlation is naturally low even when separation is
fine. Low correlation flags *"can't confirm"*, not *"separation failed"*. The reliable
fix when a project exists is always exporting that part's **group stem** from Ableton.

## Separation confidence (rhythm_quality.py)

**Reconstruction residual** = mix minus the sum of all stems, in dB relative to the mix.
Demucs is built so stems sum back to the mix.

| Residual | Typical reading |
|---|---|
| < −25 dB | Stems reconstruct the mix almost perfectly — complete, trust the split. |
| −25 to −12 dB | Mostly complete; minor material unaccounted for. |
| > −12 dB | A lot of the track isn't captured by any stem — read per-stem panels as approximate. |

**Leakage** = correlation of two stems' loudness envelopes over time. r ≳ 0.2 means the
same sound bleeds into both stems (neither is a clean isolation). Low values = clean split.

## Rhythm per stem (rhythm_quality.py)

- **onset rate (hits/sec)** — how busy a part is rhythmically. A bass at ~0.3/s is sparse
  (or barely captured); drums at ~5/s are dense.
- **timing tightness (ms off the 1/16 grid)** — same scale as swing: ~0 locked, >30 ms loose.
- **off-beat share** — fraction of hits on the "e"/"a" 1/16 slots. **~50% is the baseline**
  for evenly-spread hits, so values near 50% are normal — don't read them as "very syncopated".
  Well above 50% = genuinely off-beat-heavy; well below = on-beat/four-on-the-floor.

## Drum breakdown (drum_breakdown.py)

Each hit in the drums stem is **classified** (not separated) into kick / snare / hat by its
spectral shape. It answers *when* each drum type hits, not clean audio. Reading the three
density lanes: a kick lane that goes empty for a stretch = a real breakdown; hats entering
only in the back half = a classic energy-lift.

## Transcribed notes (transcribe.py)

Notes pulled from a stem's **audio** (basic-pitch), so they're trustworthy for parts the
stem actually carries (lead, the melodic "other"). On a near-empty stem the transcription
is mostly noise — ignore it there (the active-% and "weak" verdict tell you which stems).

## Automation — intention vs result (parse_als.py + widget)

Automation envelopes (cutoff, gain, pitch, sends…) are the producer's **intention**; the
measured arcs (energy/brightness/density) are the **result**. Compare them on the shared
timeline:

| Pattern | Typical reading |
|---|---|
| Curve and arc move together | Intention and result agree — the automation is doing what you hear. |
| Curve flat/closing but the arc keeps moving | Something *else* is driving the change (a layer, reverb, distortion). The skill flags this as "intention vs result" with timecodes. |
| Curve moves but the arc sits still | The automation isn't audibly landing — masked, too subtle, or on a silent part. |

The widget auto-detects the clearest case (e.g. a filter that stops opening while brightness
keeps rising) and writes it as a timecoded recommendation. Absence of that card means no
clear divergence was found — not that nothing is automated.
