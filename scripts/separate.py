#!/usr/bin/env python3
"""
separate.py — Deep mode: stem separation via Demucs.

Separates a mix into 4 stems: drums / bass / other / vocals.
On CPU this takes ~2-5 minutes — the script prints progress commentary
explaining WHAT we're looking for in the masking step, not just a spinner.

Usage:
  python separate.py <audio_path> --out-dir <stems_dir>

Output:
  <stems_dir>/
    drums.wav
    bass.wav
    other.wav
    vocals.wav
  stems_manifest.json   ← paths + metadata for masking.py
"""
import sys, argparse, json, time
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description="track-coach: Demucs stem separation")
    p.add_argument("audio", help="Path to mix audio (mp3/wav/m4a/aiff/flac)")
    p.add_argument("--out-dir", default="stems",
                   help="Directory to write stems (default: stems/)")
    p.add_argument("--model", default="htdemucs",
                   help="Demucs model (default: htdemucs)")
    args = p.parse_args()

    audio_path = Path(args.audio).resolve()
    out_dir    = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── pre-run UX: explain what we're looking for ───────────────────────────
    print()
    print("── Demucs stem separation (Deep mode) ──")
    print()
    print("Separating stems — on CPU this takes 2-5 minutes.")
    print("While it runs, here's what we're looking for in the next step:")
    print()
    print("  MASKING ANALYSIS looks for frequency-pocket conflicts between stems.")
    print("  The key zone is 200–500 Hz (low-mid): bass and mid instruments")
    print("  compete here. If the bass layer dominates this pocket, the")
    print("  melody/chords get masked — you hear them as 'buried' or 'dull',")
    print("  not absent. The mix sounds cloudy rather than hollow.")
    print()
    print("  Sub zone (20–80 Hz): kick + bass. If both are full here without")
    print("  sidechaining or EQ separation, the sub gets congested — you feel")
    print("  pressure but lose punch definition.")
    print()
    print("  High-mid (2k–8k): presence & articulation. If the low-mid mask")
    print("  is heavy, this zone sounds recessed even when the material is there.")
    print()
    print("  We compare RMS energy in each band per stem per time-window,")
    print("  then flag windows where the dominant low stem is >X dB louder")
    print("  than the mid stem in the same pocket — that's the masking signal.")
    print()

    # ── import torch / demucs ────────────────────────────────────────────────
    try:
        import torch
    except ImportError:
        print("ERROR: torch not found. Run setup.sh first.")
        sys.exit(1)

    try:
        from demucs.pretrained import get_model
        from demucs.apply import apply_model
        import torchaudio
    except ImportError:
        print("ERROR: demucs not found. Run setup.sh first.")
        sys.exit(1)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"  Using device: {device}")
    if device == "cpu":
        print("  (Apple MPS not available — CPU mode, expect ~3-5 min for a 5 min track)")
    print()

    # ── load model ───────────────────────────────────────────────────────────
    print("Loading Demucs model...")
    t0 = time.time()
    model = get_model(args.model)
    model.to(device)
    model.eval()
    print(f"  Model loaded in {time.time()-t0:.1f}s")
    print(f"  Stems: {model.sources}")   # typically: drums, bass, other, vocals
    print()

    # ── load audio ───────────────────────────────────────────────────────────
    print(f"Loading audio: {audio_path.name}")
    wav, sr = torchaudio.load(str(audio_path))
    # resample to model sample rate if needed
    if sr != model.samplerate:
        wav = torchaudio.functional.resample(wav, sr, model.samplerate)
        sr  = model.samplerate
    # ensure stereo
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    wav = wav.unsqueeze(0).to(device)  # (1, 2, samples)
    dur = wav.shape[-1] / sr
    print(f"  {dur:.1f}s  {sr} Hz  stereo")
    print()

    # ── separate ─────────────────────────────────────────────────────────────
    print("Running separation...")
    t1 = time.time()
    with torch.no_grad():
        sources = apply_model(model, wav, device=device, progress=True)
    elapsed = time.time() - t1
    print(f"\n  Separation done in {elapsed:.0f}s")
    print()

    # ── save stems ───────────────────────────────────────────────────────────
    stem_paths = {}
    for i, name in enumerate(model.sources):
        stem_wav = sources[0, i].cpu()   # (2, samples)
        stem_path = out_dir / f"{name}.wav"
        torchaudio.save(str(stem_path), stem_wav, sr)
        stem_paths[name] = str(stem_path)
        print(f"  Saved: {stem_path.name}")

    # manifest
    manifest = {
        "mix_path":   str(audio_path),
        "stems_dir":  str(out_dir),
        "model":      args.model,
        "sample_rate": sr,
        "duration_s": round(dur, 1),
        "stems":      stem_paths,
    }
    manifest_path = out_dir / "stems_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"  Manifest: {manifest_path.name}")
    print()
    print("Stems ready. Next: run masking.py for frequency-pocket conflict analysis.")


if __name__ == "__main__":
    main()
