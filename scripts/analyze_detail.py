#!/usr/bin/env python3
"""
analyze_detail.py — Fast mode: tonality / articulation / harmony / dynamics / swing.

Based on analyze3.py from the original session (Appendix A), with:
  - gaps filled in (crest factor, swing deviation)
  - f0/yin computed once (not 3×)
  - PATH → CLI argument
  - common utilities from _common.py

Outputs result_detail.json.

Etalon for Wobble Drift v0.6.1:
  swing_global_ms ≈ 26  (free, unquantised groove)
  wobble_rate_median_hz ≈ 1..4.7 Hz drift across track
"""
import sys, argparse
import numpy as np
import librosa
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _common import (load_audio, make_bins, bin_series, frames_to_time,
                     norm, write_json, WIN, HOP, SR)


def analyse(audio_path: str, out_path: str):
    y, sr, dur = load_audio(audio_path, mono=True)
    nb, tb = make_bins(dur)

    def binit(t, v):
        return bin_series(t, v, nb)

    # ── tempo & beats (needed for swing) ────────────────────────────────────
    print("Computing tempo & beats...")
    tempo_arr, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo_arr)[0])
    beat_t = librosa.frames_to_time(beats, sr=sr, hop_length=HOP)

    # ── 1. TONAL vs ATONAL: HPSS + spectral flatness ────────────────────────
    print("HPSS (harmonic/percussive separation)...")
    H, P = librosa.effects.hpss(y)
    h_rms = librosa.feature.rms(y=H, hop_length=HOP)[0]
    p_rms = librosa.feature.rms(y=P, hop_length=HOP)[0]
    tonality = h_rms / (h_rms + p_rms + 1e-9)   # 1=tonal, 0=percussive
    flat     = librosa.feature.spectral_flatness(y=y, hop_length=HOP)[0]
    tonal_clar = 1.0 - norm(flat)                 # high=clear pitch

    t_h = frames_to_time(h_rms)
    ton_b  = binit(t_h, tonality)
    clar_b = binit(frames_to_time(tonal_clar), tonal_clar)

    # ── 2. ARTICULATION: onset density + sustain ratio ───────────────────────
    print("Articulation / sustain...")
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    ons  = librosa.onset.onset_detect(
        onset_envelope=oenv, sr=sr, hop_length=HOP, units='time')
    rms_raw = librosa.feature.rms(y=y, hop_length=HOP)[0]
    flux_rms = np.abs(np.diff(rms_raw))
    short_long = binit(frames_to_time(flux_rms), flux_rms)   # high=choppy

    art = np.array([
        np.sum((ons >= i * WIN) & (ons < (i + 1) * WIN)) / WIN
        for i in range(nb)
    ])

    # ── 3. HARMONY: chroma + harmonic change ────────────────────────────────
    print("Chroma & harmonic change...")
    chroma = librosa.feature.chroma_cqt(y=H, sr=sr, hop_length=HOP)
    ct = frames_to_time(chroma[0])
    chroma_b = np.zeros((12, nb))
    for i in range(nb):
        m = (ct >= i * WIN) & (ct < (i + 1) * WIN)
        if m.any():
            chroma_b[:, i] = chroma[:, m].mean(axis=1)
    dom_pc = np.argmax(chroma_b, axis=0)
    harm_change = np.zeros(nb)
    for i in range(1, nb):
        harm_change[i] = float(np.linalg.norm(chroma_b[:, i] - chroma_b[:, i - 1]))

    # ── 4. PITCH MOVEMENT (yin — computed ONCE) ──────────────────────────────
    print("Pitch / YIN (this may take ~10s)...")
    f0 = librosa.yin(H, fmin=65, fmax=2000, sr=sr, hop_length=HOP)
    pitch_var = binit(frames_to_time(f0), np.abs(np.gradient(f0)))

    # ── 5. WOBBLE (amplitude modulation rate) ────────────────────────────────
    print("Wobble / LFO rate...")
    fps = SR / HOP
    env = rms_raw - rms_raw.mean()
    wob_b     = np.zeros(nb)
    wobrate_b = np.zeros(nb)
    for i in range(nb):
        a_i = int(i * WIN * fps)
        b_i = int(min((i + 1) * WIN * fps, len(env)))
        seg = env[a_i:b_i]
        if len(seg) > 16:
            sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
            fr = np.fft.rfftfreq(len(seg), 1.0 / fps)
            band = (fr > 0.5) & (fr < 12.0)
            if band.any():
                wob_b[i]     = sp[band].max()
                wobrate_b[i] = fr[band][np.argmax(sp[band])]

    active = wobrate_b[wobrate_b > 0]
    wobble_rate_median = float(np.median(active)) if len(active) else 0.0

    # ── 6. CREST FACTOR (peak/RMS per window) ────────────────────────────────
    # High crest = punchy transients. Low crest = compressed/limiter.
    print("Crest factor...")
    crest = np.zeros(nb)
    samples_per_win = int(WIN * SR)
    for i in range(nb):
        a_i = i * samples_per_win
        b_i = min((i + 1) * samples_per_win, len(y))
        seg = y[a_i:b_i]
        rms_seg = float(np.sqrt(np.mean(seg ** 2)))
        peak    = float(np.max(np.abs(seg)))
        crest[i] = peak / (rms_seg + 1e-9)

    # ── 7. SWING DEVIATION ───────────────────────────────────────────────────
    # Mean absolute deviation of beat onsets from an even grid (in ms).
    # High = free/humanised groove. Near 0 = quantised.
    # Etalon: Wobble Drift ≈ 26 ms.
    print("Swing deviation...")
    swing_global_ms = 0.0
    swing_b = np.zeros(nb)
    if len(beat_t) > 2:
        # ideal grid: uniform spacing = mean beat interval
        mean_interval = float(np.mean(np.diff(beat_t)))
        grid = beat_t[0] + np.arange(len(beat_t)) * mean_interval
        deviations = np.abs(beat_t - grid) * 1000.0   # ms
        swing_global_ms = float(np.mean(deviations))
        # per window: mean deviation of beats falling in that window
        for i in range(nb):
            m = (beat_t >= i * WIN) & (beat_t < (i + 1) * WIN)
            swing_b[i] = deviations[m].mean() if m.any() else 0.0

    # ── assemble output ──────────────────────────────────────────────────────
    out = {
        "duration_s":             round(dur, 1),
        "tempo":                  round(tempo, 1),
        "swing_global_ms":        round(swing_global_ms, 1),
        "tonality_mean":          round(float(np.mean(ton_b)), 3),
        "crest_mean":             round(float(np.mean(crest)), 2),
        "wobble_rate_median_hz":  round(wobble_rate_median, 2),
        "time_bins":     [round(float(x), 1) for x in tb],
        "tonality":      [round(float(x), 3) for x in ton_b],
        "tonal_clarity": [round(float(x), 3) for x in norm(clar_b)],
        "articulation":  [round(float(x), 2) for x in art],
        "short_long":    [round(float(x), 3) for x in norm(short_long)],
        "harm_change":   [round(float(x), 3) for x in norm(harm_change)],
        "dom_pitchclass":[int(x) for x in dom_pc],
        "pitch_move":    [round(float(x), 3) for x in norm(pitch_var)],
        "crest":         [round(float(x), 3) for x in norm(crest)],
        "swing":         [round(float(x), 2) for x in swing_b],
        "wobble":        [round(float(x), 3) for x in norm(wob_b)],
        "wobble_rate":   [round(float(x), 2) for x in wobrate_b],
        "chroma": [
            [round(float(chroma_b[p, i]), 3) for i in range(nb)]
            for p in range(12)
        ],
        "beats_s": [round(float(x), 2) for x in beat_t],
    }

    write_json(out, out_path)

    print("\n── Detail analysis summary ──")
    print(f"  tempo:              {out['tempo']} BPM")
    print(f"  swing_global_ms:    {out['swing_global_ms']:.1f} ms  (etalon: ≈26 ms)")
    print(f"  tonality_mean:      {out['tonality_mean']:.3f}  (1=fully tonal)")
    print(f"  crest_mean:         {out['crest_mean']:.2f}  (higher=punchier)")
    print(f"  wobble_rate_median: {out['wobble_rate_median_hz']:.2f} Hz")


def main():
    p = argparse.ArgumentParser(description="track-coach: detail analysis")
    p.add_argument("audio", help="Path to audio file (mp3/wav/m4a/aiff/flac)")
    p.add_argument("--out", default="result_detail.json",
                   help="Output JSON path (default: result_detail.json)")
    args = p.parse_args()
    analyse(args.audio, args.out)


if __name__ == "__main__":
    main()
