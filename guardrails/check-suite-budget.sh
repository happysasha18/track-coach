#!/usr/bin/env bash
# check-suite-budget.sh — the suite wall-time budget's mechanical net (SPEC INV-41, INV-164,
# ROADMAP row 361).
#
# ARCHITECTURE.md states a quality budget for the full suite's wall-time; nothing machine-read it
# against the real number, which is exactly how the stated budget (once ≤ 60 s) drifted silently
# behind the measured figure (~95 s) until a full prover pass caught it (2026-07-16). This gate
# closes the hole: it reads the run's own pytest tail line ("N passed in X.XXs (...)") and the
# architecture's stated budget row, and reds the moment the measured figure exceeds the stated one
# — naming BOTH numbers, so the failure is fixable on sight (speed the suite, or re-set the budget
# to the fresh measured figure) and a budget claim can never again go unread.
#
# Usage: check-suite-budget.sh <log-file> [architecture-md]
#   log-file         a captured pytest -q run's stdout/stderr (its LAST "in <float>s" tail line
#                     is read — a run may print several such lines from earlier tool output).
#   architecture-md   defaults to ARCHITECTURE.md at the repo root.

set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

LOG="${1:-}"
ARCH="${2:-$REPO_ROOT/docs/ARCHITECTURE.md}"  # track-coach: spec docs live under docs/

if [ -z "$LOG" ] || [ ! -f "$LOG" ]; then
  echo "FAIL (suite budget): no readable log file given ('$LOG')."
  exit 1
fi

# the LAST line matching pytest's own tail shape: "<N> passed in <float>s" (may also read
# "... in <float>s (H:MM:SS)" — only the seconds figure right after "in" is read).
measured="$(grep -oE 'in [0-9]+\.[0-9]+s' "$LOG" 2>/dev/null | tail -n1 | grep -oE '[0-9]+\.[0-9]+' || true)"

if [ -z "$measured" ]; then
  echo "FAIL (suite budget): the log's duration line was unreadable — no 'in <float>s' tail found in $LOG."
  exit 1
fi

if [ ! -f "$ARCH" ]; then
  echo "FAIL (suite budget): the budget row was unreadable — $ARCH not found."
  exit 1
fi

# the architecture's quality-budget row: "| full suite wall-time | ... <= <int> s ..."
budget_line="$(grep -F '| full suite wall-time |' "$ARCH" 2>/dev/null | head -n1 || true)"
budget="$(printf '%s' "$budget_line" | grep -oE '≤ *[0-9]+' | head -n1 | grep -oE '[0-9]+' || true)"

if [ -z "$budget" ]; then
  echo "FAIL (suite budget): the budget row was unreadable — no '≤ <int>' figure found in $ARCH's full suite wall-time row."
  exit 1
fi

# integer compare against a float measured figure without bc/awk dependency assumptions —
# compare via awk, which ships with the base system this repo already relies on elsewhere.
over="$(awk -v m="$measured" -v b="$budget" 'BEGIN { print (m > b) ? "1" : "0" }')"

if [ "$over" = "1" ]; then
  echo "FAIL (suite budget): measured ${measured} s exceeds the stated ${budget} s (ARCHITECTURE.md, full suite wall-time)."
  echo "  Fix: speed the suite, or re-set the budget row with the fresh measured figure — the number must match reality (SPEC INV-41, INV-164)."
  exit 1
fi

echo "OK (suite budget): measured ${measured} s within the stated ${budget} s (ARCHITECTURE.md, full suite wall-time)."
exit 0
