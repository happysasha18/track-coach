#!/usr/bin/env python3
"""
drum_breakdown.py — Part D (drums): split the drums stem into kick / snare / hat.

This is NOT source separation — it does not produce three audio files. It detects
every drum hit in the drums stem and classifies each one by its spectral shape:

  • kick  — energy concentrated in the lows (< 150 Hz)
  • hat   — energy concentrated in the highs (> 6 kHz), little low end
  • snare — broadband / noisy body in between (the rest)

That gives an honest, model-free answer to "when do the kicks / snares / hats hit",
which is what you actually want to see on the timeline. It's labelled as hit
classification, not separation, so it's never mistaken for clean stems.

Usage:
  python drum_breakdown.py --drums stems_6s/drums.wav [--out result_drums.json]
"""
import sys, argparse, json
from pathlib import Path
import numpy as np
import librosa
sys.path.insert(0, str(Path(__file__).parent))
from _common import make_bins, write_json, WIN, HOP, SR


def classify_hit(y, sr, t):
    """Classify a single onset at time t into kick/snare/hat by band energy."""
    i0 = int(t * sr)
    seg = y[i0:i0 + int(0.06 * sr)]          # 60 ms after the transient
    if len(seg) < 256:
        return None
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1.0 / sr)
    p = S ** 2
    tot = p.sum() + 1e-12
    low = p[freqs < 150].sum() / tot
    high = p[freqs > 6000].sum() / tot
    centroid = float((freqs * p).sum() / tot)
    if low > 0.45:
        return "kick"
    # hats: bright, little low end — catch by high-band share OR a high centroid
    if low < 0.18 and (high > 0.22 or centroid > 5000):
        return "hat"
    return "snare"


def main():
    ap = argparse.ArgumentParser(description="track-coach: drum hit breakdown (Part D)")
    ap.add_argument("--drums", required=True, help="drums stem wav")
    ap.add_argument("--out", default="result_drums.json")
    args = ap.parse_args()

    y, _ = librosa.load(args.drums, sr=SR, mono=True)
    dur = len(y) / SR
    nb, tb = make_bins(dur)

    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    onsets = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=HOP,
                                        units="time", backtrack=True)
    print(f"  {len(onsets)} drum onsets over {dur:.1f}s")

    classes = ["kick", "snare", "hat"]
    times = {c: [] for c in classes}
    for t in onsets:
        c = classify_hit(y, SR, t)
        if c:
            times[c].append(round(float(t), 3))

    density = {c: [0] * nb for c in classes}
    for c in classes:
        for t in times[c]:
            i = int(t // WIN)
            if 0 <= i < nb:
                density[c][i] += 1

    out = {
        "duration_s": round(dur, 1), "bins": [round(float(x), 1) for x in tb],
        "classes": classes,
        "counts": {c: len(times[c]) for c in classes},
        "onsets": times,
        "density": density,
    }
    write_json(out, args.out)
    print("── Drum breakdown ──")
    for c in classes:
        print(f"  {c:6s} {out['counts'][c]:4d} hits")


if __name__ == "__main__":
    main()
