"""
_common.py — shared utilities for all track-coach analysis scripts.
Import with: from _common import load_audio, bin_series, norm, write_json
"""
import json, sys
import numpy as np
import librosa

WIN = 4.0   # window size in seconds (all scripts use this)
HOP = 1024  # STFT hop length (frames)
SR  = 44100 # target sample rate


def load_audio(path: str, mono: bool = True):
    """Load audio file. Returns (y, sr). Supports mp3/wav/m4a/aiff/flac."""
    print(f"Loading: {path}")
    y, sr = librosa.load(path, sr=SR, mono=mono)
    dur = y.shape[-1] / sr
    ch = "mono" if mono else "stereo"
    print(f"  {dur:.1f}s  {sr} Hz  {ch}")
    return y, sr, dur


def make_bins(dur: float):
    """Return (nb, tb) — number of windows and their centre times."""
    nb = int(np.ceil(dur / WIN))
    tb = np.arange(nb) * WIN + WIN / 2
    return nb, tb


def bin_series(t: np.ndarray, v: np.ndarray, nb: int) -> np.ndarray:
    """Average v into WIN-second bins using time array t."""
    out = np.zeros(nb)
    for i in range(nb):
        m = (t >= i * WIN) & (t < (i + 1) * WIN)
        out[i] = v[m].mean() if m.any() else 0.0
    return out


def frames_to_time(v: np.ndarray) -> np.ndarray:
    return librosa.frames_to_time(np.arange(len(v)), sr=SR, hop_length=HOP)


def norm(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, float)
    lo, hi = a.min(), a.max()
    return (a - lo) / (hi - lo) if hi - lo > 1e-9 else np.zeros_like(a)


def trend(a: np.ndarray) -> float:
    """Pearson correlation of a with its time index (monotonic direction)."""
    a = np.asarray(a, float)
    if np.std(a) < 1e-9:
        return 0.0
    idx = np.arange(len(a))
    return float(np.corrcoef(idx, a)[0, 1])


def local_var(a: np.ndarray) -> float:
    """Mean abs window-to-window change (local novelty)."""
    return float(np.mean(np.abs(np.diff(norm(a)))))


def write_json(data: dict, path: str):
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
    print(f"Saved: {path}")
