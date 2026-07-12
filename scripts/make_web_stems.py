#!/usr/bin/env python3
"""
make_web_stems.py — Part E helper: compress audio for the in-page player.

Two modes:
  • --stems-dir : the Demucs stems (~100 MB each WAV; six ≈ 600 MB) are far too heavy for a
    browser to preload. Transcode each to a small AAC .m4a (~5 MB). The widget's per-stem player
    points at this folder via --audio-stems-rel.
  • --audio     : a QUICK run has no stems, but it still has the mix. Encode that ONE file to
    `<out>/mix.m4a` so the widget can offer a single-track player (transport + seek), pointed at via
    --audio-mix-rel. (2026-06-20: quick mode still gets a player.)

Usage:
  python make_web_stems.py --stems-dir stems_6s [--out-dir stems_web] [--bitrate 128k]
  python make_web_stems.py --audio mix.wav    [--out-dir mix_web]    [--bitrate 128k]
"""
import sys, argparse, subprocess, shutil
from pathlib import Path


def _encode(src_file: Path, dst: Path, bitrate: str):
    print(f"  {src_file.name} → {dst.name}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src_file),
                    "-c:a", "aac", "-b:a", bitrate, str(dst)], check=True)


def main():
    ap = argparse.ArgumentParser(description="track-coach: compress audio for the web player (Part E)")
    ap.add_argument("--stems-dir", default=None, help="dir of Demucs stem .wavs → per-stem player")
    ap.add_argument("--audio", default=None, help="a single mix file → single-track player (quick)")
    ap.add_argument("--out-dir", default=None,
                    help="default: <stems-dir>/../stems_web, or <audio>/../mix_web for --audio")
    ap.add_argument("--bitrate", default="128k")
    args = ap.parse_args()

    if bool(args.stems_dir) == bool(args.audio):
        print("ERROR: pass exactly one of --stems-dir or --audio.")
        sys.exit(2)
    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not found on PATH.")
        sys.exit(1)

    if args.audio:  # single mix → mix.m4a (the quick-run player source)
        src_file = Path(args.audio)
        if not src_file.exists():
            print(f"ERROR: audio not found: {src_file}")
            sys.exit(1)
        out = Path(args.out_dir) if args.out_dir else src_file.parent / "mix_web"
        out.mkdir(parents=True, exist_ok=True)
        _encode(src_file, out / "mix.m4a", args.bitrate)
        print(f"Done. Web mix in: {out}")
        print(f"Build the widget with: --audio-mix-rel {out.name}")
        return

    src = Path(args.stems_dir)
    out = Path(args.out_dir) if args.out_dir else src.parent / "stems_web"
    out.mkdir(parents=True, exist_ok=True)
    wavs = sorted(src.glob("*.wav"))
    if not wavs:
        print(f"ERROR: no .wav files in {src}")
        sys.exit(1)
    for w in wavs:
        _encode(w, out / (w.stem + ".m4a"), args.bitrate)
    print(f"Done. Web stems in: {out}")
    print(f"Build the widget with: --audio-stems-rel {out.name}")


if __name__ == "__main__":
    main()
