#!/usr/bin/env python3
"""
analyze_core.py — Fast mode: arc + development direction + cosine start↔end.

Outputs result_core.json with:
  - energy / brightness / density trends (Pearson r with time)
  - local_var per feature (variety / novelty)
  - cosine similarity start↔end (endpoint_cosine ≈ 0.97 → no irreversible change)
  - modulation drift: wobble rate per window (LFO frequency via FFT of RMS envelope)
  - section boundaries (agglomerative, up to 8)
  - per-window time series for the widget

Usage:
  python analyze_core.py <audio_path> [--out result_core.json]

Etalon for Wobble Drift v0.6.1 (~5:02):
  energy_trend ≈ -0.02, density_trend ≈ +0.10, brightness_trend ≈ +0.42
  endpoint_cosine ≈ 0.97
  wobble_rate: starts ~1 Hz, ends ~4.7 Hz
"""
import sys, argparse
import numpy as np
import librosa
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from _common import (load_audio, make_bins, bin_series, frames_to_time,
                     norm, trend, local_var, write_json, WIN, HOP, SR)


def analyse(audio_path: str, out_path: str):
    y, sr, dur = load_audio(audio_path, mono=True)
    nb, tb = make_bins(dur)

    # ── tempo & beats ───────────────────────────────────────────────────────
    print("Computing tempo & beats...")
    tempo_arr, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo_arr)[0])
    beat_t = librosa.frames_to_time(beats, sr=sr, hop_length=HOP)

    # ── frame-level features ────────────────────────────────────────────────
    print("Computing RMS, spectral centroid, onset density...")
    rms  = librosa.feature.rms(y=y, hop_length=HOP)[0]
    cent = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=HOP)[0]
    t_frames = frames_to_time(rms)

    oenv   = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    onsets = librosa.onset.onset_detect(
        onset_envelope=oenv, sr=sr, hop_length=HOP, units='time')

    # ── windowed bins ────────────────────────────────────────────────────────
    rms_b  = bin_series(t_frames, rms,  nb)
    cent_b = bin_series(t_frames, cent, nb)
    dens_b = np.array([
        np.sum((onsets >= i * WIN) & (onsets < (i + 1) * WIN)) / WIN
        for i in range(nb)
    ])

    # ── trends & variety ────────────────────────────────────────────────────
    tr_energy     = trend(rms_b)
    tr_brightness = trend(cent_b)
    tr_density    = trend(dens_b)
    lv_energy     = local_var(rms_b)
    lv_brightness = local_var(cent_b)
    lv_density    = local_var(dens_b)

    # ── cosine start↔end (endpoint cosine) ──────────────────────────────────
    # Stack [rms_n, cent_n, dens_n] per window; compare first N vs last N windows
    print("Computing endpoint cosine similarity...")
    N = max(1, nb // 5)   # ~20% of track from each end
    stack = np.column_stack([norm(rms_b), norm(cent_b), norm(dens_b)])
    vec_start = stack[:N].mean(axis=0)
    vec_end   = stack[-N:].mean(axis=0)
    denom = np.linalg.norm(vec_start) * np.linalg.norm(vec_end)
    endpoint_cosine = float(np.dot(vec_start, vec_end) / denom) if denom > 1e-9 else 1.0

    # ── MFCC-based cosine (more detailed, used alongside) ────────────────────
    print("Computing MFCC-based self-similarity...")
    S = np.abs(librosa.stft(y, hop_length=HOP))
    mfcc = librosa.feature.mfcc(
        S=librosa.power_to_db(S**2), sr=sr, n_mfcc=13)
    # beat-sync to reduce noise
    if len(beats) > 4:
        msync = librosa.util.sync(mfcc, beats, aggregate=np.mean)
    else:
        msync = mfcc
    nb_m = msync.shape[1]
    N_m  = max(1, nb_m // 5)
    m_start = msync[:, :N_m].mean(axis=1)
    m_end   = msync[:, -N_m:].mean(axis=1)
    d2 = np.linalg.norm(m_start) * np.linalg.norm(m_end)
    mfcc_cosine = float(np.dot(m_start, m_end) / d2) if d2 > 1e-9 else 1.0

    # ── section boundaries ───────────────────────────────────────────────────
    print("Computing section boundaries...")
    try:
        bounds = librosa.segment.agglomerative(msync, 8)
        bound_times = (
            librosa.frames_to_time(beats[bounds], sr=sr, hop_length=HOP).tolist()
            if len(beats) > 4 else []
        )
    except Exception:
        bound_times = []

    # ── wobble / modulation rate (LFO via FFT of RMS envelope) ──────────────
    print("Computing wobble rate (amplitude modulation)...")
    fps = SR / HOP
    env = rms - rms.mean()
    wob_b      = np.zeros(nb)
    wobrate_b  = np.zeros(nb)
    for i in range(nb):
        a_i = int(i * WIN * fps)
        b_i = int(min((i + 1) * WIN * fps, len(env)))
        seg = env[a_i:b_i]
        if len(seg) > 16:
            window = np.hanning(len(seg))
            sp = np.abs(np.fft.rfft(seg * window))
            fr = np.fft.rfftfreq(len(seg), 1.0 / fps)
            band = (fr > 0.5) & (fr < 12.0)
            if band.any():
                wob_b[i]     = sp[band].max()
                wobrate_b[i] = fr[band][np.argmax(sp[band])]

    # wobble_rate summary: ignore zero-bins
    active = wobrate_b[wobrate_b > 0]
    wobble_rate_start  = float(active[:max(1, len(active)//5)].mean())  if len(active) else 0.0
    wobble_rate_end    = float(active[-max(1, len(active)//5):].mean()) if len(active) else 0.0
    wobble_rate_median = float(np.median(active)) if len(active) else 0.0

    # ── stereo width (side / (mid+side) energy per window) ───────────────────
    # 0 = mono / centred, 1 = very wide. Reads the original file in stereo;
    # a mono source or mono render simply reports ~0 throughout.
    print("Computing stereo width...")
    width_b = np.zeros(nb)
    phase_corr = None   # L/R correlation: +1 mono-safe, 0 wide, <0 out-of-phase (mono cancels)
    try:
        ys, _ = librosa.load(audio_path, sr=SR, mono=False)
        if getattr(ys, "ndim", 1) == 2 and ys.shape[0] == 2:
            mid = (ys[0] + ys[1]) * 0.5
            side = (ys[0] - ys[1]) * 0.5
            mrms = librosa.feature.rms(y=mid, hop_length=HOP)[0]
            srms = librosa.feature.rms(y=side, hop_length=HOP)[0]
            t_s = frames_to_time(mrms)
            width_b = bin_series(t_s, srms / (mrms + srms + 1e-9), nb)
            # phase correlation — energy-weighted mean of per-window L·R correlation, so
            # loud sections dominate the verdict and silent gaps don't skew it.
            L, R = ys[0], ys[1]
            win = int(SR * 0.5)
            cs, ws = 0.0, 0.0
            for a in range(0, len(L) - win, win):
                l, r = L[a:a + win], R[a:a + win]
                denom = float(np.sqrt(np.sum(l * l) * np.sum(r * r)))
                if denom > 1e-9:
                    w = float(np.sum(l * l) + np.sum(r * r))
                    cs += (float(np.sum(l * r)) / denom) * w
                    ws += w
            if ws > 0:
                phase_corr = round(cs / ws, 2)
    except Exception as ex:
        print(f"  stereo width skipped: {ex}")
    stereo_width_mean = float(np.mean(width_b))
    stereo_width_trend = trend(width_b)

    # ── VITALS: the credible spec-sheet shown at the very top ────────────────
    # These are single, authoritative numbers about the FINISHED mix (no time
    # axis) — the "this is a real measurement, not vibes" markers. tempo /
    # duration / stereo are already computed above; here we add key, loudness,
    # true peak and dynamic range.
    print("Computing vitals (key, loudness, true peak, dynamic range)...")

    # key / scale — Krumhansl-Schmuckler on the mean chroma vector. Run on the
    # HARMONIC component (HPSS) so kick/snare transients don't smear the chroma —
    # noticeably steadier key + higher confidence than the raw mix.
    key_name, key_conf = None, 0.0
    try:
        try:
            y_harm = librosa.effects.harmonic(y, margin=3.0)
        except Exception:
            y_harm = y
        chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, hop_length=HOP)
        cv = chroma.mean(axis=1)
        cv = (cv - cv.mean()) / (cv.std() + 1e-9)
        MAJ = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
        MIN = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
        MAJ = (MAJ - MAJ.mean()) / MAJ.std(); MIN = (MIN - MIN.mean()) / MIN.std()
        PITCH = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
        best = (-2.0, None)
        for i in range(12):
            rm = float(np.corrcoef(cv, np.roll(MAJ, i))[0, 1])
            rn = float(np.corrcoef(cv, np.roll(MIN, i))[0, 1])
            if rm > best[0]: best = (rm, f"{PITCH[i]} major")
            if rn > best[0]: best = (rn, f"{PITCH[i]} minor")
        key_conf, key_name = round(best[0], 2), best[1]
    except Exception as ex:
        print(f"  key estimation skipped: {ex}")

    # integrated loudness (LUFS) — pyloudnorm if available (industry standard).
    lufs = None
    try:
        import pyloudnorm as pyln
        try:
            ystereo, _ = librosa.load(audio_path, sr=SR, mono=False)
        except Exception:
            ystereo = y
        data = ystereo.T if getattr(ystereo, "ndim", 1) == 2 else ystereo
        meter = pyln.Meter(SR)
        L = float(meter.integrated_loudness(data))
        if np.isfinite(L):
            lufs = round(L, 1)
    except Exception as ex:
        print(f"  LUFS skipped (pip install pyloudnorm): {ex}")

    # true peak (dBTP) — 4× oversample, max abs sample.
    true_peak_db = None
    try:
        up = librosa.resample(y, orig_sr=SR, target_sr=SR * 4)
        pk = float(np.max(np.abs(up)))
        if pk > 0:
            true_peak_db = round(20 * np.log10(pk), 1)
    except Exception as ex:
        print(f"  true peak skipped: {ex}")

    # dynamic range (dB) — peak-to-RMS (crest) of the whole mix; higher = more
    # dynamic / punchy, lower = squashed/limited.
    dr_db = None
    try:
        full_rms = float(np.sqrt(np.mean(y ** 2)))
        full_pk = float(np.max(np.abs(y)))
        if full_rms > 0 and full_pk > 0:
            dr_db = round(20 * np.log10(full_pk / full_rms), 1)
    except Exception as ex:
        print(f"  dynamic range skipped: {ex}")

    # tonal balance — average spectrum of the MIX in octave bands. Reference-free and
    # honest: we flag bands that stick OUT from their neighbours (a resonance) or sit in a
    # hole, rather than against a genre-specific target curve we'd have to guess. A +5 dB
    # bump vs its neighbours at 250 Hz reads as "boxy"; a dip at 4 kHz as "dull".
    print("Computing tonal balance (mix spectrum)...")
    tonal_bands = []
    try:
        Sfull = np.abs(librosa.stft(y, n_fft=4096, hop_length=2048))
        psd = (Sfull ** 2).mean(axis=1)
        ffreq = librosa.fft_frequencies(sr=sr, n_fft=4096)
        BANDS = [(20, 60, "20–60"), (60, 120, "60–120"), (120, 250, "120–250"),
                 (250, 500, "250–500"), (500, 1000, "0.5–1k"), (1000, 2000, "1–2k"),
                 (2000, 4000, "2–4k"), (4000, 8000, "4–8k"), (8000, 16000, "8–16k")]
        raw = []
        for lo, hi, lab in BANDS:
            m = (ffreq >= lo) & (ffreq < hi)
            p = float(psd[m].sum()) if m.any() else 0.0
            raw.append((lab, 10 * np.log10(p) if p > 0 else -120.0))
        ref = max(d for _, d in raw)
        rel = [(lab, d - ref) for lab, d in raw]            # 0 dB = loudest band
        vals = [d for _, d in rel]
        # smooth neighbour curve → deviation flags resonances / holes
        for i, (lab, d) in enumerate(rel):
            lo_i, hi_i = max(0, i - 1), min(len(vals), i + 2)
            smooth = sum(vals[lo_i:hi_i]) / (hi_i - lo_i)
            tonal_bands.append({"band": lab, "rel_db": round(d, 1),
                                "dev_db": round(d - smooth, 1)})
    except Exception as ex:
        print(f"  tonal balance skipped: {ex}")

    vitals = {
        "tempo_bpm": round(tempo, 1),
        "duration_s": round(dur, 1),
        "key": key_name, "key_conf": key_conf,
        "lufs": lufs, "true_peak_db": true_peak_db,
        "dynamic_range_db": dr_db,
        "stereo_width": round(stereo_width_mean, 2),
        "phase_corr": phase_corr,
    }

    # ── assemble output ──────────────────────────────────────────────────────
    out = {
        "duration_s":        round(dur, 1),
        "tempo":             round(tempo, 1),
        "vitals":            vitals,
        "tonal_balance":     tonal_bands,
        # trends (-1..+1, positive = grows across track)
        "energy_trend":      round(tr_energy, 3),
        "brightness_trend":  round(tr_brightness, 3),
        "density_trend":     round(tr_density, 3),
        # variety (local novelty, 0..1)
        "energy_lv":         round(lv_energy, 3),
        "brightness_lv":     round(lv_brightness, 3),
        "density_lv":        round(lv_density, 3),
        # cosine start↔end
        "endpoint_cosine":   round(endpoint_cosine, 4),
        "mfcc_cosine":       round(mfcc_cosine, 4),
        # wobble / modulation
        "wobble_rate_start_hz":  round(wobble_rate_start, 2),
        "wobble_rate_end_hz":    round(wobble_rate_end, 2),
        "wobble_rate_median_hz": round(wobble_rate_median, 2),
        # stereo width (0 mono … 1 wide), genre-neutral
        "stereo_width_mean":  round(stereo_width_mean, 3),
        "stereo_width_trend": round(stereo_width_trend, 3),
        # section boundaries
        "section_bounds_s":  [round(float(t), 1) for t in bound_times],
        # beat times
        "beats_s": [round(float(t), 2) for t in beat_t],
        # per-window series (normalised 0-1 for widget)
        "time_bins":   [round(float(x), 1) for x in tb],
        "energy":      [round(float(x), 3) for x in norm(rms_b)],
        "brightness":  [round(float(x), 3) for x in norm(cent_b)],
        "density":     [round(float(x), 3) for x in norm(dens_b)],
        "wobble":      [round(float(x), 3) for x in norm(wob_b)],
        "wobble_rate": [round(float(x), 2) for x in wobrate_b],
        "stereo_width":[round(float(x), 3) for x in width_b],
    }

    write_json(out, out_path)

    # print summary for quick sanity check
    print("\n── Core analysis summary ──")
    print(f"  duration:          {out['duration_s']}s   tempo: {out['tempo']} BPM")
    print(f"  energy_trend:      {out['energy_trend']:+.3f}  (etalon: ≈-0.02)")
    print(f"  brightness_trend:  {out['brightness_trend']:+.3f}  (etalon: ≈+0.42)")
    print(f"  density_trend:     {out['density_trend']:+.3f}  (etalon: ≈+0.10)")
    print(f"  endpoint_cosine:   {out['endpoint_cosine']:.4f}  (etalon: ≈0.97)")
    print(f"  wobble_rate:       {out['wobble_rate_start_hz']:.2f}→{out['wobble_rate_end_hz']:.2f} Hz  "
          f"median {out['wobble_rate_median_hz']:.2f} Hz  (etalon: ~1→4.7 Hz)")
    print(f"  sections detected: {len(out['section_bounds_s'])}")
    v = out["vitals"]
    print(f"  vitals: {v['tempo_bpm']} BPM · {v['key']} · {v['lufs']} LUFS · "
          f"peak {v['true_peak_db']} dBTP · DR {v['dynamic_range_db']} · width {v['stereo_width']} · phase {v['phase_corr']}")


def main():
    p = argparse.ArgumentParser(description="track-coach: core arc analysis")
    p.add_argument("audio", help="Path to audio file (mp3/wav/m4a/aiff/flac)")
    p.add_argument("--out", default="result_core.json",
                   help="Output JSON path (default: result_core.json)")
    args = p.parse_args()
    analyse(args.audio, args.out)


if __name__ == "__main__":
    main()
