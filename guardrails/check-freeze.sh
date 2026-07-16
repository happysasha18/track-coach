#!/usr/bin/env bash
# check-freeze.sh — gate k: the compaction freeze (the 2.0 movement's Phase-0 safety).
#
# Verifies the guarded docs' anchor-OCCURRENCE map, structural marker lines, numbers-with-units,
# and backticked paths against the session's frozen baseline (scripts/spec-freeze.py --verify
# --compaction). This catches, before a push, the silent meaning changes the register lint cannot
# see: a dropped mid-paragraph citation, a drifted ratio or size, a changed [target]/[default]
# marker line.
#
# The baseline lives in .spec-freeze/ — a LOCAL, regenerable working artifact (gitignored), blessed
# per session with `python3 scripts/spec-freeze.py --freeze <docs> --compaction`. So a fresh
# checkout with no baseline SKIPS this check with a note rather than blocking; the PERMANENT,
# CI-run locks are the live style/redundancy ratchet (tests/test_convergence_locks.py) and the
# shipped-language gate (check-shipped-language.sh). Within a working session, with the baseline
# present, this blocks a drift before it reaches the remote.
set -euo pipefail
REPO_ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$REPO_ROOT"

# The stable-law docs. ROADMAP.md is deliberately excluded: it is a living queue whose rows are
# added and archived by design, so an anchor-occurrence freeze would fight its natural churn; its
# language is guarded instead by check-shipped-language.sh (English-only, no verbatim quotes).
DOCS="PRODUCT_SPEC.md ARCHITECTURE.md TEST_MATRIX.md"

# No local baseline at all → nothing to verify against; skip (a fresh clone, or CI).
if [ ! -e "$REPO_ROOT/.spec-freeze/PRODUCT_SPEC.md.json" ]; then
  echo "OK (freeze): no local baseline in .spec-freeze/ — session-local check skipped."
  echo "  (regenerate with: python3 scripts/spec-freeze.py --freeze $DOCS --compaction)"
  exit 0
fi

set +e
out="$(python3 "$REPO_ROOT/scripts/spec-freeze.py" --verify $DOCS --compaction 2>&1)"
code=$?
set -e

# A missing baseline for one of the docs is reported as its own violation line; treat that as a
# skip signal (partial baseline = an un-blessed doc), not a hard drift.
if printf '%s\n' "$out" | grep -q "no frozen baseline"; then
  echo "OK (freeze): a guarded doc has no frozen baseline yet — session-local check skipped."
  echo "  (regenerate with: python3 scripts/spec-freeze.py --freeze $DOCS --compaction)"
  exit 0
fi

if [ "$code" -ne 0 ]; then
  printf '%s\n' "$out"
  echo "FAIL (freeze): a guarded doc drifted from its frozen baseline — an anchor vanished or was"
  echo "  invented, a number/path drifted, or a [target]/[default] marker line changed. Restore the"
  echo "  law, or (if the change is intended and reviewed) re-freeze in this same commit."
  exit 1
fi

printf '%s\n' "$out"
echo "OK (freeze): the guarded docs match their frozen baseline."
exit 0
