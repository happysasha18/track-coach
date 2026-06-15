#!/usr/bin/env python3
"""
rhythm_quality.py — Part C: per-stem rhythm + separation confidence.

Two independent measurements from the separated stems:

1. RHYTHM, per stem
   • onset rate — hits per second (how busy the part is rhythmically)
   • onset density over time — for a sparkline, so you see where it gets busy
   • timing tightness — mean distance of each hit from the nearest 1/16 grid line,
     in milliseconds (small = locked to the grid, large = loose/human)
   • syncopation — share of hits landing on the off-beats (the "e"/"a" 1/16 slots)

2. SEPARATION CONFIDENCE — how much to trust the split
   • reconstruction error — mix minus the sum of all stems, in dB relative to the
     mix. Demucs is built so stems sum back to the mix; a high residual means the
     stems you're reading aren't the whole picture.
   • leakage — correlation of each stem pair's loudness over time. Two stems that
     rise and fall together are bleeding into each other (the same sound in both),
     so neither is a clean isolation.

Usage:
  python rhythm_quality.py --manifest stems_6s/stems_manifest.json \
      [--tempo 142] [--out result_rhythm.json]
"""
import sys, argparse, json
from pathlib import Path
from itertools import combinations
import numpy as np
import librosa
sys.path.insert(0, str(Path(__file__).parent))
from _common import make_bins, bin_series, frames_to_time, norm, write_json, WIN, HOP, SR


def onset_features(y, tempo, nb):
    """Onset times + binned density + timing tightness + syncopation for one stem."""
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    onsets = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=HOP,
                                         units="time", backtrack=False)
    dur = len(y) / SR
    n = len(onsets)
    rate = n / dur if dur > 0 else 0.0

    # density over time (onsets per window), on the shared grid
    dens = np.zeros(nb)
    for t in onsets:
        i = int(t // WIN)
        if 0 <= i < nb:
            dens[i] += 1

    # timing vs a 1/16 grid; syncopation = share on the off-beat 1/16 slots
    offgrid_ms, syncopation = None, None
    if n >= 4 and tempo and tempo > 0:
        beat = 60.0 / tempo
        sixteenth = beat / 4.0
        devs, off = [], 0
        for t in onsets:
            slot = (t % beat) / sixteenth        # 0..4 within the beat
            nearest = round(slot) % 4
            devs.append(abs(slot - round(slot)) * sixteenth * 1000.0)  # ms to nearest 1/16
            if nearest in (1, 3):                # the "e" and "a" — syncopated slots
                off += 1
        offgrid_ms = round(float(np.median(devs)), 1)
        syncopation = round(100.0 * off / n, 1)

    return {"n_onsets": n, "onset_rate": round(rate, 2),
            "onset_density": [int(x) for x in dens],
            "offgrid_ms": offgrid_ms, "syncopation_pct": syncopation}


def rms_env(y, nb):
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    return bin_series(frames_to_time(rms), rms, nb)


def main():
    p = argparse.ArgumentParser(description="track-coach: rhythm + separation quality (Part C)")
    p.add_argument("--manifest", required=True, help="stems_manifest.json (has mix_path + stems)")
    p.add_argument("--tempo", type=float, default=None, help="BPM for grid (default: detect)")
    p.add_argument("--out", default="result_rhythm.json")
    args = p.parse_args()

    man = json.loads(Path(args.manifest).read_text())
    mix_path = man.get("mix_path")
    stems = man["stems"]

    # load stems mono
    Y = {}
    dur = 0.0
    for name, path in stems.items():
        print(f"  load stem {name}")
        y, _ = librosa.load(path, sr=SR, mono=True)
        Y[name] = y
        dur = max(dur, len(y) / SR)
    nb, tb = make_bins(dur)

    tempo = args.tempo
    if not tempo:
        # detect from the busiest (drums) stem if present, else the mix
        ref = Y.get("drums")
        if ref is None and mix_path:
            ref, _ = librosa.load(mix_path, sr=SR, mono=True)
        if ref is not None:
            tempo = float(np.atleast_1d(librosa.beat.tempo(y=ref, sr=SR))[0])
    print(f"  tempo for grid: {tempo:.1f} BPM" if tempo else "  no tempo")

    # 1) rhythm per stem
    rhythm = {name: onset_features(y, tempo, nb) for name, y in Y.items()}

    # 2) separation confidence
    L = min(len(y) for y in Y.values())
    stack = np.stack([y[:L] for y in Y.values()])
    summed = stack.sum(axis=0)
    recon_db = None
    if mix_path and Path(mix_path).exists():
        mix, _ = librosa.load(mix_path, sr=SR, mono=True)
        Lm = min(len(mix), L)
        resid = mix[:Lm] - summed[:Lm]
        mix_p = float(np.sum(mix[:Lm] ** 2)) + 1e-12
        recon_db = round(10.0 * np.log10(float(np.sum(resid ** 2)) / mix_p + 1e-12), 1)

    # leakage: correlation of stem loudness envelopes (pairwise)
    envs = {name: rms_env(y, nb) for name, y in Y.items()}
    leaks = []
    for a, b in combinations(envs, 2):
        ea, eb = envs[a], envs[b]
        if np.std(ea) < 1e-9 or np.std(eb) < 1e-9:
            continue
        r = float(np.corrcoef(ea, eb)[0, 1])
        leaks.append({"a": a, "b": b, "r": round(r, 2)})
    leaks.sort(key=lambda d: -d["r"])

    if recon_db is None:
        recon_text = "No mix available to check completeness."
    elif recon_db < -25:
        recon_text = f"Stems sum back to the mix almost perfectly ({recon_db} dB residual) — the split is complete, nothing is missing."
    elif recon_db < -12:
        recon_text = f"Stems mostly reconstruct the mix ({recon_db} dB residual) — minor material is unaccounted for."
    else:
        recon_text = f"Stems do NOT add back up to the mix ({recon_db} dB residual) — a lot of the track isn't captured by any stem. Read them with caution."

    out = {
        "duration_s": round(dur, 1), "tempo": round(tempo, 1) if tempo else None,
        "bins": [round(float(x), 1) for x in tb],
        "rhythm": rhythm,
        "separation": {
            "reconstruction_error_db": recon_db, "reconstruction_text": recon_text,
            "leakage": leaks[:6],
        },
    }
    write_json(out, args.out)

    print("\n── Rhythm per stem ──")
    for s, d in rhythm.items():
        sy = f"{d['syncopation_pct']}% off-beat" if d['syncopation_pct'] is not None else "—"
        og = f"{d['offgrid_ms']}ms" if d['offgrid_ms'] is not None else "—"
        print(f"  {s:8s} {d['onset_rate']:5.2f} hits/s   tight {og:>7}   {sy}")
    print("\n── Separation ──")
    print(f"  {recon_text}")
    if leaks:
        print("  top leakage:", ", ".join(f"{d['a']}↔{d['b']} {d['r']}" for d in leaks[:4]))


if __name__ == "__main__":
    main()
