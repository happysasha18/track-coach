#!/usr/bin/env bash
# Shell-agnostic, dependency-pinned runner for track-coach's Python steps.
#
# WHY THIS EXISTS: the pipeline used a `UV="uv run --with …"; $UV python …` pattern that
# relies on POSIX word-splitting. zsh — the default macOS login shell — does NOT split an
# unquoted $UV, so those snippets failed there with:
#     command not found: uv run --python 3.11 --with numpy==1.26.4 …
# Because this file is always executed via its own bash shebang, it behaves identically no
# matter which shell the caller uses, and it keeps every pinned dependency set in ONE place.
#
# USAGE:  bash tc_uv.sh <profile> <script.py> [args…]
#   profiles:
#     core  — analyze_core (adds pyloudnorm for LUFS)
#     fast  — librosa/scipy/sklearn set (detail, als, masking, map_stems, rhythm, drums,
#             self_similarity, make_web_stems, build_widget, --dump-strings)
#     deep  — fast + torch/torchaudio/demucs (separate.py / Demucs)
#     bp    — basic-pitch transcription (transcribe.py)
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

if [ "$#" -lt 2 ]; then
  echo "usage: bash tc_uv.sh <core|fast|deep|bp> <script.py> [args…]" >&2
  exit 2
fi
profile="$1"; shift

base=(--python 3.11 --with numpy==1.26.4 --with librosa==0.10.2 --with soundfile==0.12.1 \
      --with audioread==3.0.1 --with scipy==1.13.1 --with scikit-learn==1.5.1)

case "$profile" in
  core) deps=("${base[@]}" --with pyloudnorm) ;;
  fast) deps=("${base[@]}") ;;
  deep) deps=("${base[@]}" --with torch==2.3.1 --with torchaudio==2.3.1 --with demucs==4.0.1) ;;
  bp)   deps=(--python 3.11 --with "basic-pitch[onnx]" --with numpy==1.26.4 --with "setuptools<70") ;;
  *)    echo "tc_uv.sh: unknown profile '$profile' (want core|fast|deep|bp)" >&2; exit 2 ;;
esac

exec uv run "${deps[@]}" python "$@"
