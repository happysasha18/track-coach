#!/usr/bin/env bash
# check-shipped-language.sh — the shipped-artifact language gate (SPEC INV-120, ROADMAP row 275;
# composes with row 274's impersonal voice). Refuses a shipped file that carries Cyrillic outside
# a deliberate user-language string, or an owner/personal name, reporting each as file:line.
# The engine (Unicode-robust, allowlist-aware) is scripts/check-shipped-language.py.
set -euo pipefail
REPO_ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$REPO_ROOT"
exec python3 "$REPO_ROOT/scripts/check-shipped-language.py" --root "$REPO_ROOT"
