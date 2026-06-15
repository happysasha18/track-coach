#!/usr/bin/env python3
"""
check_env.py — verify track-coach prerequisites.

Only checks system-level dependencies (uv, ffmpeg).
Python packages are managed automatically by uv run — no venv needed.

Exit 0: ready. Exit 1: something missing (prints exact fix).
"""
import sys, shutil, subprocess

ok = True

def check(label, passed, fix=None):
    global ok
    mark = "✓" if passed else "✗"
    print(f"  {mark} {label}")
    if not passed:
        ok = False
        if fix:
            print(f"    → {fix}")

print("\n=== track-coach environment check ===\n")

# uv
uv_path = shutil.which("uv")
if uv_path:
    try:
        ver = subprocess.check_output(["uv", "--version"],
                                      stderr=subprocess.STDOUT).decode().strip()
    except Exception:
        ver = "?"
    check(f"uv ({ver})", True)
else:
    check("uv", False,
          'Install: curl -LsSf https://astral.sh/uv/install.sh | sh   then restart terminal')

# ffmpeg
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path:
    try:
        ver_line = subprocess.check_output(
            ["ffmpeg", "-version"], stderr=subprocess.STDOUT
        ).decode().splitlines()[0]
    except Exception:
        ver_line = "ffmpeg"
    check(f"ffmpeg  ({ver_line[:60]})", True)
else:
    check("ffmpeg", False,
          "Install: brew install ffmpeg\n"
          "    (No Homebrew? → https://brew.sh  then: brew install ffmpeg)")

print()
if ok:
    print("All checks passed. Python packages will be installed automatically on first run.\n")
    sys.exit(0)
else:
    print("Fix the above, then try again.\n")
    sys.exit(1)
