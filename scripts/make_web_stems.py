#!/usr/bin/env python3
"""
make_web_stems.py — Part E helper: compress stems for the in-page player.

The raw Demucs stems are ~100 MB each (44.1 kHz WAV). Six of them is ~600 MB,
far too heavy for a browser to preload. This transcodes each to a small AAC .m4a
(~5 MB) that every browser can stream from a local file. The widget's stem player
then points at this folder via --audio-stems-rel.

Usage:
  python make_web_stems.py --stems-dir stems_6s [--out-dir stems_web] [--bitrate 128k]
"""
import sys, argparse, subprocess, shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="track-coach: compress stems for the web player (Part E)")
    ap.add_argument("--stems-dir", required=True)
    ap.add_argument("--out-dir", default=None, help="default: <stems-dir>/../stems_web")
    ap.add_argument("--bitrate", default="128k")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not found on PATH.")
        sys.exit(1)

    src = Path(args.stems_dir)
    out = Path(args.out_dir) if args.out_dir else src.parent / "stems_web"
    out.mkdir(parents=True, exist_ok=True)

    wavs = sorted(src.glob("*.wav"))
    if not wavs:
        print(f"ERROR: no .wav files in {src}")
        sys.exit(1)

    for w in wavs:
        dst = out / (w.stem + ".m4a")
        print(f"  {w.name} → {dst.name}")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(w),
                        "-c:a", "aac", "-b:a", args.bitrate, str(dst)], check=True)
    print(f"Done. Web stems in: {out}")
    print(f"Build the widget with: --audio-stems-rel {out.name}")


if __name__ == "__main__":
    main()
