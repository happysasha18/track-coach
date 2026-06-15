# track-coach — Methodology

## Why this tool exists

Most audio analysis tools answer: *what are the track's numbers?*
(BPM, LUFS, spectral centroid, stereo width, etc.)

This tool answers a different question: *does the track develop, or does it cycle?*

That's compositional dramaturgy, not acoustic measurement. These are complementary, not competing.

---

## Core concepts

### Variety vs. Development

These are distinct and often confused:

**Variety** — local, reversible change. The texture shifts, a layer drops out, a filter sweeps. But if you compare bars 1–8 with bars 120–128, they sound similar. The track varies but doesn't *go anywhere*. High local novelty, low directional momentum.

**Development** — irreversible, directed movement. Something is gained, transformed, or resolved that cannot be undone. A modulation that keeps accelerating. A harmonic progression that resolves only at bar 96. The end is fundamentally different from the beginning.

Most electronic tracks are high in variety and low in development. This is not wrong — it's a genre choice. But it is useful to *know which one you're making*.

### How we measure each

| Concept | Metric | How it's calculated |
|---|---|---|
| Variety | `local_var` | Mean abs window-to-window change in normalised feature |
| Development | `*_trend` | Pearson r of feature value with time index |
| Irreversibility | `endpoint_cosine` | Cosine similarity of feature vector: first 20% of track vs last 20% |

**endpoint_cosine near 1.0** (e.g. 0.97) means the end sounds spectrally similar to the beginning. Large-scale irreversibility is low. The track may vary richly in the middle without permanently *arriving* somewhere different.

This is not a verdict. Many great tracks have endpoint_cosine > 0.95.

---

## What each metric actually measures

### Energy trend / Energy local_var
- **Measured**: RMS amplitude per 4-second window, Pearson r with time
- **What it is**: loudness arc. Does the track get louder, quieter, or stay flat?
- **What it is NOT**: emotional intensity, perceived loudness (LUFS), mastering level

### Brightness trend
- **Measured**: spectral centroid per window (Hz), normalised, Pearson r
- **What it is**: does high-frequency content grow or decrease across the track?
- **Common meaning**: opening up filters, adding air/shimmer, or conversely closing down

### Density trend / Density local_var
- **Measured**: onset events per second per window
- **What it is**: how busy is the rhythmic/textural activity?
- **What it is NOT**: note count (MIDI), complexity of harmony

### Endpoint cosine (two variants)
1. **feature-stack cosine**: uses normalised [energy, brightness, density]
2. **MFCC cosine**: uses 13 MFCCs (more detailed spectral texture)
Both compare a mean vector of the first 20% vs last 20% of the track.

### Wobble rate (amplitude modulation frequency)
- **Measured**: dominant frequency in the RMS envelope within 0.5–12 Hz per window (FFT)
- **What it is**: the LFO rate of amplitude modulation — the "wobble" in wobble bass / tremolo / chorus-like movement
- **Why it matters**: drift in wobble rate across the track is a form of development — the modulation itself evolves. A track named "Wobble Drift" should show this drift.

### Tonality
- **Measured**: h_rms / (h_rms + p_rms) via HPSS — ratio of harmonic to percussive energy
- **What it is**: how tonal vs percussive is the texture in each window?

### Tonal clarity
- **Measured**: 1 − normalised spectral flatness
- **What it is**: how clear/defined are the pitches? (High flatness = noise-like)

### Articulation (onset density)
- **Measured**: onset events per second per window
- **What it is**: how choppy vs legato is the material?

### Harmonic change
- **Measured**: Euclidean distance between consecutive chroma vectors (window-to-window)
- **What it is**: rate of harmonic movement. High = fast chord changes or modulation. Low = drone or static harmony.

### Crest factor
- **Measured**: peak / RMS per window
- **What it is**: transient punch. High crest = dynamic, punchy. Low crest = compressed/saturated.

### Swing deviation
- **Measured**: mean abs deviation of beat onsets from an ideal uniform grid (milliseconds)
- **What it is**: groove / humanisation. ~0 ms = quantised. ~20–30 ms = free, humanised. The grid is constructed from the detected beat interval — no external tempo reference needed.

---

## Frequency bands (used in Deep / masking mode)

| Band | Range | Typical content (electronic music) |
|---|---|---|
| sub | 20–80 Hz | Sub-bass, rumble, kick fundamental |
| low | 80–250 Hz | Bass body, kick punch, low synths |
| low_mid | 250–600 Hz | **Main conflict zone**: bass harmonics vs melody low end |
| mid | 600–2000 Hz | Vocals, leads, chords, presence |
| hi_mid | 2000–8000 Hz | Articulation, bite, clarity |
| air | 8000–20 kHz | Sparkle, reverb tails, cymbals |

---

## Additive accumulation / transformation / tension-release

These are three compositional strategies that appear in the analysis differently:

**Additive accumulation**: layers enter over time → density_trend positive, energy_trend positive, endpoint_cosine < 1.0 (more content at end than beginning)

**Transformation**: the same material mutates without adding layers → energy flat, but wobble_rate drifts, harm_change increases, endpoint_cosine may still be < 1.0

**Tension–release**: energy arc peaks then resolves → energy_trend ≈ 0 but local_var high in middle; crest factor drops during peak (compression kicking in), recovers at end

These are interpretive frames, not diagnostic categories. The analysis surfaces the numbers; the author maps them to intent.

---

## What this tool cannot tell you

- Whether the track sounds good
- What equipment or plugins were used (this cannot be inferred from audio)
- Whether a specific element should be removed or added
- Whether the structure is "correct" for a genre
- Anything about the mix that requires hearing it (phase, stereo imaging feel, emotional resonance)

The author's ears are the final arbiter. This tool gives the author *additional information* to bring to those ears.
