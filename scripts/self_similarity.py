#!/usr/bin/env python3
"""
self_similarity.py — find REPEATING sections of a track from the audio itself.

Why: the Track Story scene letters (A·B·A) were derived only from which instrument
*families* are active + an intensity tier. That confirms "something changed", not
"this is the same musical material coming back". This script adds the missing piece:
a self-similarity / recurrence analysis that groups the track into a few labels so
that REPEATS share a label (chorus comes back = same label = same colour on the map).

Method: McFee & Ellis (2014) Laplacian structural decomposition (the standard
librosa recipe):
  beat-sync log-CQT → weighted recurrence matrix (what sounds alike, anywhere)
  + a sequence graph from beat-sync MFCC (what's locally continuous)
  → normalised graph Laplacian → spectral embedding → KMeans into k labels.
Contiguous beats with the same label = one segment; segments with the same label =
the same recurring part.

Outputs result_selfsim.json:
  - segments: [{t0, t1, label, letter}]  (letter A,B,C… by first appearance)
  - n_labels, k
  - labels_per_beat + beat_times  (for debugging / finer overlays)

Usage:
  python self_similarity.py <audio> [--out result_selfsim.json] [--k N]
  (k omitted → chosen from track length, clamped 3…7)
"""
import sys, argparse
import numpy as np
import scipy
import librosa
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _common import load_audio, write_json, HOP, SR

BINS_PER_OCTAVE = 12 * 3
N_OCTAVES = 7


def analyse(audio_path: str, out_path: str, k: int = None):
    y, sr, dur = load_audio(audio_path, mono=True)

    print("CQT + beat tracking...")
    C = librosa.amplitude_to_db(
        np.abs(librosa.cqt(y=y, sr=sr, bins_per_octave=BINS_PER_OCTAVE,
                           n_bins=N_OCTAVES * BINS_PER_OCTAVE, hop_length=HOP)),
        ref=np.max)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=HOP, trim=False)
    if len(beats) < 8:
        print("  too few beats for structure analysis; writing empty.")
        write_json({"segments": [], "n_labels": 0, "k": 0,
                    "labels_per_beat": [], "beat_times": []}, out_path)
        return

    Csync = librosa.util.sync(C, beats, aggregate=np.median)
    beat_times = librosa.frames_to_time(
        librosa.util.fix_frames(beats, x_min=0, x_max=C.shape[1]),
        sr=sr, hop_length=HOP)

    print("Recurrence matrix (what sounds alike, anywhere)...")
    R = librosa.segment.recurrence_matrix(Csync, width=3, mode='affinity', sym=True)
    # smooth along the time-lag diagonals so repeats read as solid stripes
    df = librosa.segment.timelag_filter(scipy.ndimage.median_filter)
    R = df(R, size=(1, 7))

    print("Sequence graph (local continuity from MFCC)...")
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=HOP)
    Msync = librosa.util.sync(mfcc, beats)
    path_distance = np.sum(np.diff(Msync, axis=1) ** 2, axis=0)
    sigma = np.median(path_distance) if np.median(path_distance) > 0 else 1.0
    path_sim = np.exp(-path_distance / sigma)
    R_path = np.diag(path_sim, k=1) + np.diag(path_sim, k=-1)

    # balance the two graphs (McFee: weight by degree so neither dominates)
    deg_path = np.sum(R_path, axis=1)
    deg_rec = np.sum(R, axis=1)
    denom = np.sum((deg_path + deg_rec) ** 2)
    mu = deg_path.dot(deg_path + deg_rec) / denom if denom > 0 else 0.5
    A = mu * R + (1 - mu) * R_path

    print("Laplacian spectral embedding...")
    L = scipy.sparse.csgraph.laplacian(A, normed=True)
    evals, evecs = scipy.linalg.eigh(L)
    evecs = scipy.ndimage.median_filter(evecs, size=(9, 1))
    Cnorm = np.cumsum(evecs ** 2, axis=1) ** 0.5

    nb = Csync.shape[1]
    if k is None:
        # more labels for longer tracks; clamp to a readable range. ~55 s/label keeps
        # the form legible (too many labels fragments into sub-phrase noise).
        k = int(min(6, max(3, round(dur / 55.0))))
    k = min(k, nb)

    from sklearn.cluster import KMeans
    X = evecs[:, :k] / (Cnorm[:, k - 1:k] + 1e-9)
    seg_ids = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)

    # contiguous runs → segments
    bound_beats = 1 + np.flatnonzero(seg_ids[:-1] != seg_ids[1:])
    bound_beats = librosa.util.fix_frames(bound_beats, x_min=0, x_max=nb)
    segs = []
    for i in range(len(bound_beats) - 1):
        b0, b1 = bound_beats[i], bound_beats[i + 1]
        t0 = float(beat_times[min(b0, len(beat_times) - 1)])
        t1 = float(beat_times[min(b1, len(beat_times) - 1)])
        if t1 <= t0:
            continue
        segs.append({"t0": round(t0, 2), "t1": round(t1, 2),
                     "label": int(seg_ids[b0])})
    if segs:
        segs[-1]["t1"] = round(float(dur), 2)

    # clean-up: spectral clustering leaves sub-phrase slivers at boundaries. Merge any
    # segment shorter than MIN_SEG into a neighbour (prefer one with the same label;
    # else the longer neighbour keeps its label), then coalesce adjacent same-label runs.
    MIN_SEG = 7.0
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for i, s in enumerate(segs):
            if s["t1"] - s["t0"] >= MIN_SEG:
                continue
            left = segs[i - 1] if i > 0 else None
            right = segs[i + 1] if i < len(segs) - 1 else None
            if left and left["label"] == s["label"]:
                tgt = left
            elif right and right["label"] == s["label"]:
                tgt = right
            else:
                tgt = max([x for x in (left, right) if x],
                          key=lambda x: x["t1"] - x["t0"])
            tgt["t0"] = min(tgt["t0"], s["t0"])
            tgt["t1"] = max(tgt["t1"], s["t1"])
            segs.pop(i)
            changed = True
            break
    coalesced = []
    for s in segs:
        if coalesced and coalesced[-1]["label"] == s["label"]:
            coalesced[-1]["t1"] = s["t1"]
        else:
            coalesced.append(s)
    segs = coalesced

    # letters by first appearance of each label
    order, letter_of = [], {}
    for s in segs:
        if s["label"] not in letter_of:
            letter_of[s["label"]] = chr(ord("A") + len(order))
            order.append(s["label"])
    for s in segs:
        s["letter"] = letter_of[s["label"]]

    out = {
        "segments": segs,
        "n_labels": len(order),
        "k": k,
        "labels_per_beat": [int(x) for x in seg_ids],
        "beat_times": [round(float(t), 2) for t in beat_times],
    }
    write_json(out, out_path)

    print("\n── Structure / repeats summary ──")
    print(f"  {len(segs)} segments, {len(order)} distinct labels (k={k})")
    reps = {}
    for s in segs:
        reps.setdefault(s["letter"], 0)
        reps[s["letter"]] += 1
    rep_letters = [L for L, n in reps.items() if n > 1]
    print("  repeated parts: " + (", ".join(
        f"{L}×{reps[L]}" for L in rep_letters) if rep_letters else "none detected"))
    for s in segs:
        print(f"   {s['letter']}  {s['t0']:6.1f}–{s['t1']:6.1f}s")


def main():
    p = argparse.ArgumentParser(description="track-coach: self-similarity / repeats")
    p.add_argument("audio")
    p.add_argument("--out", default="result_selfsim.json")
    p.add_argument("--k", type=int, default=None, help="number of structural labels")
    args = p.parse_args()
    analyse(args.audio, args.out, args.k)


if __name__ == "__main__":
    main()
