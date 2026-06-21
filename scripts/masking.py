#!/usr/bin/env python3
"""
masking.py — Deep mode: frequency-pocket masking analysis from stems.

Takes stems from separate.py (or user-provided stems) and computes
per-window band-energy for each stem. Flags windows where a low-frequency
stem dominates a pocket that also contains mid/melody content.

KEY PRINCIPLE (from methodology):
  Low energy in a band ≠ absence of material.
  Check masking BEFORE saying "empty". A masked mid is not a silent mid.

Usage:
  python masking.py --manifest stems/stems_manifest.json [--out result_masking.json]
  # OR provide stems directly:
  python masking.py --bass stems/bass.wav --mid stems/other.wav [--out result_masking.json]

Frequency bands (electronic music focused):
  sub      20–80 Hz
  low      80–250 Hz
  low_mid  250–600 Hz   ← main conflict zone: bass vs melody
  mid      600–2000 Hz
  hi_mid   2000–8000 Hz
  air      8000–20000 Hz
"""
import sys, argparse, json
from pathlib import Path
import numpy as np
import librosa
sys.path.insert(0, str(Path(__file__).parent))
from _common import make_bins, bin_series, frames_to_time, norm, write_json, WIN, HOP, SR

# Frequency bands in Hz [low_cut, high_cut]
BANDS = {
    "sub":     (20,   80),
    "low":     (80,   250),
    "low_mid": (250,  600),
    "mid":     (600,  2000),
    "hi_mid":  (2000, 8000),
    "air":     (8000, 20000),
}

# Masking threshold: flag windows where dominant low stem exceeds mid stem by this many dB
MASKING_THRESHOLD_DB = 12.0

# High-resolution VISUALISATION grid (separate from the 4 s analysis WIN).
# The analysis stays on WIN=4 s windows (sections, masking, recommendations are
# tuned to it); but the sequencer waveform reads much finer than 4 s, so we emit
# a dedicated fine envelope just for drawing: loudness + a 3-group frequency split
# (low/mid/high) per stem, at VIZ_WIN_S resolution. ~0.25 s ⇒ ~8× more detail.
VIZ_WIN_S = 0.25
# how the 6 analysis bands collapse into the 3 colour groups the waveform paints
VIZ_GROUPS = {"low": ("sub", "low"), "mid": ("low_mid", "mid"), "high": ("hi_mid", "air")}


def _fine_power_bin(t_frames: np.ndarray, power: np.ndarray, nbf: int) -> np.ndarray:
    """Average per-frame POWER into VIZ_WIN_S bins (energy-correct, like the 4 s pass)."""
    idx = np.clip((t_frames / VIZ_WIN_S).astype(int), 0, nbf - 1)
    sums = np.zeros(nbf)
    cnt = np.zeros(nbf)
    np.add.at(sums, idx, power)
    np.add.at(cnt, idx, 1)
    cnt[cnt == 0] = 1.0
    return sums / cnt


def band_rms(y: np.ndarray, sr: int, band: tuple, hop: int = HOP) -> np.ndarray:
    """Compute per-frame RMS energy in a frequency band [low, high] Hz."""
    low, high = band
    # bandpass filter via STFT masking
    S = librosa.stft(y, hop_length=hop)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2 * (S.shape[0] - 1))
    mask = (freqs >= low) & (freqs <= high)
    S_band = S.copy()
    S_band[~mask, :] = 0.0
    y_band = librosa.istft(S_band, hop_length=hop, length=len(y))
    rms = librosa.feature.rms(y=y_band, hop_length=hop)[0]
    return rms


def load_stem(path: str) -> tuple:
    """Load a stem as mono at SR. Returns (y, sr, dur)."""
    y, sr = librosa.load(path, sr=SR, mono=True)
    return y, sr, len(y) / sr


def analyse(stems: dict, out_path: str, dur_hint: float = None):
    """
    stems: dict of {role: path}, e.g. {'bass': '...', 'other': '...', ...}
    """
    print("\n── Masking analysis ──")
    print(f"  Stems: {list(stems.keys())}")

    # load all stems, find duration
    loaded = {}
    dur = dur_hint or 0.0
    for role, path in stems.items():
        print(f"  Loading {role}: {Path(path).name}")
        y, sr, d = load_stem(path)
        loaded[role] = y
        dur = max(dur, d)

    nb, tb = make_bins(dur)

    # ── fine visualisation grid (for the sequencer waveform only) ────────────
    nbf = int(np.ceil(dur / VIZ_WIN_S))
    viz_bins = [round(float(x), 2) for x in (np.arange(nbf) + 0.5) * VIZ_WIN_S]
    viz_bb = {}    # {stem: [nbf × dB]}  broadband loudness, fine
    viz_band = {}  # {stem: {low/mid/high: [nbf × dB]}}  3-group colour, fine

    # ── compute band RMS per stem ────────────────────────────────────────────
    band_data = {}   # {stem_name: {band_name: [nb floats]}}
    flatness = {}    # {stem_name: float}  energy-weighted mean spectral flatness (0..1); high = noisy/no clear pitch
    sustain  = {}    # {stem_name: float}  continuity of the envelope within its active span (0..1); high = a held drone/pad
    for role, y in loaded.items():
        print(f"  Band analysis: {role}...")
        band_data[role] = {}
        # Spectral flatness per stem (G13): feeds the melody/chord vs noise split in stem_character. We
        # ENERGY-WEIGHT the per-frame flatness by that frame's RMS power so silence/near-silence doesn't
        # drag the number — the label should reflect what the stem sounds like WHEN it plays, not its gaps.
        flat_f = librosa.feature.spectral_flatness(y=y, hop_length=HOP)[0]
        rms_f  = librosa.feature.rms(y=y, hop_length=HOP)[0]
        n_f    = min(len(flat_f), len(rms_f))
        w      = rms_f[:n_f] ** 2
        flatness[role] = round(float(np.sum(flat_f[:n_f] * w) / (np.sum(w) + 1e-12)), 4)
        # Sustain (G13 pad-vs-chord): how CONTINUOUSLY the stem sounds within its active span. A held pad
        # drones (≈0.85+); rhythmic chord stabs leave gaps (≈0.5). "Sounding" = within 20 dB of the stem's
        # own 95th-pct RMS; sustain = sounding frames ÷ frames from first-to-last sounding. (Replaces the
        # broken note-length proxy — basic-pitch fragments held synths, so note duration never reads pad.)
        peak = float(np.quantile(rms_f, 0.95)) if len(rms_f) else 0.0
        if peak > 0:
            sounding = rms_f >= peak * (10 ** (-20 / 20.0))
            idx = np.where(sounding)[0]
            span = int(idx[-1] - idx[0] + 1) if len(idx) else 0
            sustain[role] = round(float(len(idx) / span), 3) if span > 0 else 0.0
        else:
            sustain[role] = 0.0
        t_frames = frames_to_time(librosa.feature.rms(y=y, hop_length=HOP)[0])
        frame_pow = {}   # per-frame POWER per band, kept for the fine viz grid
        for bname, brange in BANDS.items():
            rms = band_rms(y, SR, brange, HOP)
            t_b = frames_to_time(rms)
            # Average POWER (rms²) per bin, not amplitude. Arithmetic-averaging the
            # per-frame RMS amplitude badly under-reports intermittent stems (a bass
            # that only hits some beats reads ~50 dB too low). Power-averaging is the
            # physically correct energy measure and matches a direct FFT band reading.
            p = rms ** 2
            frame_pow[bname] = (t_b, p)
            binned_power = bin_series(t_b, p, nb)
            db = 10.0 * np.log10(np.maximum(binned_power, 1e-12))
            band_data[role][bname] = [round(float(x), 1) for x in db]

        # fine broadband loudness (sum of all band power per frame → fine bins)
        any_t = frame_pow["sub"][0]
        tot_p = np.sum([frame_pow[b][1] for b in BANDS], axis=0)
        bb_db = 10.0 * np.log10(np.maximum(_fine_power_bin(any_t, tot_p, nbf), 1e-12))
        viz_bb[role] = [int(round(float(x))) for x in bb_db]
        # fine 3-group colour split
        viz_band[role] = {}
        for g, members in VIZ_GROUPS.items():
            gp = np.sum([frame_pow[b][1] for b in members], axis=0)
            gdb = 10.0 * np.log10(np.maximum(_fine_power_bin(any_t, gp, nbf), 1e-12))
            viz_band[role][g] = [int(round(float(x))) for x in gdb]

    # ── masking detection: low vs mid in the conflict zones ─────────────────
    # Focus: low_mid (250-600 Hz) — bass vs other/lead
    # and sub (20-80 Hz) — bass+drums collision
    masking_flags = {}   # {zone: list of {window_idx, time_s, low_stem, mid_stem, diff_db}}

    def find_masking(low_stem, mid_stem, band_name):
        flags = []
        if low_stem not in band_data or mid_stem not in band_data:
            return flags
        low_arr = np.array(band_data[low_stem][band_name])
        mid_arr = np.array(band_data[mid_stem][band_name])
        for i in range(nb):
            diff = low_arr[i] - mid_arr[i]
            if diff > MASKING_THRESHOLD_DB:
                flags.append({
                    "window_idx": i,
                    "time_s": round(float(tb[i]), 1),
                    "low_stem": low_stem,
                    "mid_stem": mid_stem,
                    "low_db": round(float(low_arr[i]), 1),
                    "mid_db": round(float(mid_arr[i]), 1),
                    "diff_db": round(float(diff), 1),
                })
        return flags

    # low_mid conflict: bass vs other (or lead, or vocals)
    mid_candidates = [r for r in loaded if r not in ("bass", "drums")]
    for mid_role in mid_candidates:
        key = f"low_mid__{mid_role}"
        masking_flags[key] = find_masking("bass", mid_role, "low_mid")

    # sub conflict: bass vs drums (kick)
    if "bass" in loaded and "drums" in loaded:
        masking_flags["sub__drums"] = find_masking("bass", "drums", "sub")

    # ── summary stats ────────────────────────────────────────────────────────
    total_windows = nb
    masking_summary = {}
    for zone, flags in masking_flags.items():
        pct = round(100.0 * len(flags) / total_windows, 1)
        masking_summary[zone] = {
            "flagged_windows": len(flags),
            "total_windows": total_windows,
            "pct_masked": pct,
            "mean_diff_db": round(
                float(np.mean([f["diff_db"] for f in flags])), 1
            ) if flags else 0.0,
        }

    out = {
        "duration_s":       round(dur, 1),
        "total_windows":    total_windows,
        "masking_threshold_db": MASKING_THRESHOLD_DB,
        "time_bins":        [round(float(x), 1) for x in tb],
        "stems_analysed":   list(loaded.keys()),
        "band_rms_db":      band_data,        # {stem: {band: [nb × dB]}}
        "spectral_flatness": flatness,        # {stem: float 0..1} energy-weighted; G13 noise/pitch split
        "sustain":          sustain,          # {stem: float 0..1} envelope continuity; G13 pad (held) vs chord (stabs)
        "masking_flags":    masking_flags,
        "masking_summary":  masking_summary,
        "viz": {                              # fine grid for the sequencer waveform only
            "win_s":  VIZ_WIN_S,
            "bins":   viz_bins,               # [nbf] centre times
            "bb":     viz_bb,                 # {stem: [nbf dB]} loudness → wave height
            "band":   viz_band,               # {stem: {low/mid/high: [nbf dB]}} → colour
        },
    }

    write_json(out, out_path)

    # print readable summary
    print("\n── Masking summary ──")
    for zone, s in masking_summary.items():
        print(f"  {zone}: {s['pct_masked']}% windows masked "
              f"(mean diff {s['mean_diff_db']} dB, threshold {MASKING_THRESHOLD_DB} dB)")
    print()
    print("NOTE: Low dB in a band ≠ no material. If low_mid is masked, the")
    print("      mid content is present but buried — not absent.")


def main():
    p = argparse.ArgumentParser(description="track-coach: masking analysis from stems")
    p.add_argument("--manifest", help="stems_manifest.json from separate.py")
    p.add_argument("--bass",  help="Path to bass stem (wav)")
    p.add_argument("--drums", help="Path to drums stem (wav)")
    p.add_argument("--other", help="Path to other/lead stem (wav)")
    p.add_argument("--vocals",help="Path to vocals stem (wav)")
    p.add_argument("--out", default="result_masking.json")
    args = p.parse_args()

    if args.manifest:
        with open(args.manifest) as f:
            manifest = json.load(f)
        stems = manifest["stems"]
        dur   = manifest.get("duration_s")
    else:
        stems = {}
        dur   = None
        for role in ("bass", "drums", "other", "vocals"):
            val = getattr(args, role)
            if val:
                stems[role] = val

    if not stems:
        print("ERROR: provide --manifest or at least one stem path.")
        sys.exit(1)

    analyse(stems, args.out, dur)


if __name__ == "__main__":
    main()
