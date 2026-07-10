#!/usr/bin/env bash
# ============================================================================
# track-coach setup — fully automated.
#
# Checks every dependency and installs whatever is missing, in order:
#   Homebrew → ffmpeg → uv → python3 → node/npm (optional) → warms the uv cache
#
# Idempotent: safe to run repeatedly. Already-installed tools are left alone.
#
# THE ONLY THING THAT WILL ASK FOR INPUT:
#   Installing Homebrew (if you don't have it) prompts ONCE for your Mac login
#   password. That prompt comes from Apple/Homebrew itself — no script can or
#   should bypass it. Everything after that is hands-off.
#
# Usage:  bash setup.sh
# ============================================================================
set -uo pipefail   # NOTE: deliberately NOT using -e — we handle each failure
                   # explicitly so one optional step can't abort the whole run.

# ── pretty output ───────────────────────────────────────────────────────────
BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; DIM=$'\033[2m'; RST=$'\033[0m'
say()  { printf "%s\n" "${BOLD}$*${RST}"; }
ok()   { printf "  ${GREEN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YELLOW}!${RST} %s\n" "$*"; }
err()  { printf "  ${RED}✗${RST} %s\n" "$*"; }
step() { printf "\n${BOLD}── %s ──${RST}\n" "$*"; }

FAILED=0
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # this repo's own dir

say ""
say "=== track-coach setup ==="
say ""

# ── 0. platform guard ───────────────────────────────────────────────────────
OS="$(uname -s)"
if [ "$OS" != "Darwin" ]; then
    warn "This setup targets macOS. On Linux, uv/ffmpeg are usually already present —"
    warn "the analysis scripts will still work, but brew steps below are skipped."
fi

# ── 1. Homebrew ─────────────────────────────────────────────────────────────
# Needed only on macOS, and only to install ffmpeg/python/node if those are
# missing. Detect the correct prefix for Apple Silicon vs Intel and put brew
# on PATH for the rest of THIS script even on a fresh install.
ensure_brew_on_path() {
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"      # Apple Silicon
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"         # Intel
    fi
}

if [ "$OS" = "Darwin" ]; then
    step "Homebrew"
    ensure_brew_on_path
    if command -v brew &>/dev/null; then
        ok "brew already installed ($(brew --version | head -1))"
    else
        warn "Homebrew not found — installing it now."
        warn "This step will ask ONCE for your Mac login password (it's the brew"
        warn "installer, not this script). Type it when prompted."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        ensure_brew_on_path
        if command -v brew &>/dev/null; then
            ok "Homebrew installed ($(brew --version | head -1))"
        else
            err "Homebrew install did not complete. Re-run this script, or install"
            err "manually from https://brew.sh and run it again."
            FAILED=1
        fi
    fi
fi

# ── 2. ffmpeg ───────────────────────────────────────────────────────────────
step "ffmpeg"
if command -v ffmpeg &>/dev/null; then
    ok "ffmpeg already installed"
elif [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
    warn "Installing ffmpeg via brew (no password needed)..."
    if brew install ffmpeg; then
        ok "ffmpeg installed"
    else
        err "ffmpeg install failed. Try manually: brew install ffmpeg"
        FAILED=1
    fi
else
    err "ffmpeg missing and no package manager available to install it."
    err "macOS: install Homebrew first (re-run this script). Linux: apt install ffmpeg."
    FAILED=1
fi

# ── 3. uv (Python package/runtime manager) ──────────────────────────────────
# uv manages Python AND the analysis packages. No venv, no manual pip.
step "uv"
ensure_uv_on_path() { export PATH="$HOME/.local/bin:$PATH"; }
ensure_uv_on_path
if command -v uv &>/dev/null; then
    ok "uv already installed ($(uv --version))"
else
    warn "Installing uv (no password needed)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ensure_uv_on_path
    if command -v uv &>/dev/null; then
        ok "uv installed ($(uv --version))"
    else
        err "uv install failed. Try manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
        FAILED=1
    fi
fi

# ── 4. python3 ──────────────────────────────────────────────────────────────
# uv can fetch its own Python (we pin 3.11 in the run commands), so this is a
# convenience check rather than a hard requirement. Don't fail the run on it.
step "python3"
if command -v python3 &>/dev/null; then
    ok "python3 present ($(python3 --version 2>&1))"
elif [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
    warn "Installing python via brew..."
    brew install python && ok "python installed" || warn "python install skipped (uv provides its own 3.11 anyway)"
else
    warn "system python3 not found — fine, uv fetches its own pinned 3.11."
fi

# ── 5. node / npm (OPTIONAL — only needed to install Claude Code itself) ─────
# You may already have Claude Code. This is here purely so the box is fully
# self-provisioning if you ever want to (re)install it. Never fatal.
step "node / npm (optional, for Claude Code)"
if command -v npm &>/dev/null; then
    ok "npm present ($(npm --version))"
elif [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
    warn "Installing node via brew..."
    brew install node && ok "node installed ($(node --version))" || warn "node install skipped (not required for analysis)"
else
    warn "npm not found — only needed if you want to (re)install Claude Code."
fi

# ── 6. warm the uv package cache ────────────────────────────────────────────
# First analysis run otherwise downloads ~200 MB (librosa, torch, demucs).
# Pre-pulling here means the first real track starts instantly.
step "Warming Python package cache (one-time, ~1-2 min)"
if command -v uv &>/dev/null; then
    warn "Pre-fetching analysis packages..."
    if uv run --python 3.11 \
        --with numpy==1.26.4 --with librosa==0.10.2 --with soundfile==0.12.1 \
        --with audioread==3.0.1 --with scipy==1.13.1 --with scikit-learn==1.5.1 \
        python -c "import librosa, scipy, sklearn, soundfile; print('fast deps OK')"; then
        ok "Fast-analysis packages cached"
    else
        warn "Fast-deps warm-up hit an issue — they'll install on first run instead."
    fi

    warn "Pre-fetching Demucs / PyTorch (the big one)..."
    if uv run --python 3.11 \
        --with numpy==1.26.4 --with torch==2.3.1 --with torchaudio==2.3.1 \
        --with demucs==4.0.1 --with soundfile==0.12.1 --with audioread==3.0.1 \
        python -c "import torch, demucs; print('deep deps OK,', 'MPS' if torch.backends.mps.is_available() else 'CPU')"; then
        ok "Demucs / PyTorch cached"
    else
        warn "Deep-deps warm-up hit an issue — they'll install on first Demucs run instead."
    fi

    warn "Pre-fetching basic-pitch (note transcription, Part D)..."
    # resampy still imports pkg_resources, removed in setuptools 81+, so pin setuptools<70.
    if uv run --python 3.11 --with 'basic-pitch[onnx]' --with numpy==1.26.4 --with 'setuptools<70' \
        python -c "from basic_pitch import ICASSP_2022_MODEL_PATH; print('basic-pitch OK')"; then
        ok "basic-pitch cached"
    else
        warn "basic-pitch warm-up skipped — it'll install on first transcription run instead."
    fi
else
    warn "uv unavailable — skipping cache warm-up."
fi

# ── Claude Code commands (/tc, /tc-quick) ───────────────────────────────────
# The two slash-commands live in the repo and are copied into the user's Claude
# commands folder, so a fresh clone gets /tc and /tc-quick — not just the skill.
step "Claude Code commands (/tc, /tc-quick)"
CMD_DIR="$HOME/.claude/commands"
if mkdir -p "$CMD_DIR" 2>/dev/null; then
    for c in tc tc-quick; do
        if cp "$SKILL_DIR/commands/$c.md" "$CMD_DIR/$c.md" 2>/dev/null; then
            ok "/$c ready  (→ $CMD_DIR/$c.md)"
        else
            warn "could not install /$c — you can still ask for the track-coach skill by name."
        fi
    done
else
    warn "could not create $CMD_DIR — /tc and /tc-quick unavailable; ask for the skill by name instead."
fi

# ── summary ─────────────────────────────────────────────────────────────────
say ""
if [ "$FAILED" -eq 0 ]; then
    say "${GREEN}=== setup complete — everything is ready ===${RST}"
    say ""
    say "Next: open a NEW terminal tab (so PATH refreshes), then:"
    printf "  ${DIM}cd ~/your-music-folder && claude${RST}\n"
    say "…and ask it to analyse a track."
else
    say "${RED}=== setup finished with some issues (see x above) ===${RST}"
    say "Fix the flagged item(s) and re-run:  bash setup.sh"
    exit 1
fi
say ""
