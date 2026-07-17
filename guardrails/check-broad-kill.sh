#!/usr/bin/env bash
# check-broad-kill.sh — SPEC INV-162 (ROADMAP 334): a cleanup kill targets the test
# resource UNIQUELY — by a recorded PID / process group or an install path — and never a
# broad NAME pattern that can match the human's own program. This gate reds if any tracked
# script resolves a browser by a bare name and kills it. It exists because a broad
# `pkill chrome` / `pkill chrome_crashpad_handler` closed the user's REAL browser
# mid-session, destroying work state outside git — the effect base rule 17 forbids.
#
# Usage: check-broad-kill.sh [path]
#   no arg  — scan the repo's tracked executable surfaces (default, the push gate)
#   path    — scan one file or directory (used by the guardrail's own test)
#
# What it flags: a line that, with its comments stripped, invokes a killing verb
# (`pkill`, `killall`, or `kill`) AND names a BARE browser (chrome / Chrome / crashpad /
# puppeteer) that is not part of a path. A path-scoped kill (`~/.cache/puppeteer/...chrome`,
# a `--user-data-dir`) is safe because the browser token sits behind a `/`, so it is not
# bare and does not match. `kill $(pgrep chrome)` and `pgrep chrome | xargs kill` are caught
# because the line carries both `kill` and a bare `chrome`. Portable across GNU and BSD grep
# (no \b). Prose surfaces (spec, ROADMAP, inbox, this checker, its own test) legitimately
# NAME the patterns to forbid or exercise them and are excluded from the repo scan.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# a killing verb as a shell word: not part of killpg / skill / os.killpg, so the char before
# it is start-of-line or a non-identifier (and not '.', to skip python's own os.kill(pid)).
VERB='(^|[^a-zA-Z._])(pkill|killall|kill)([^a-zA-Z]|$)'
# a BARE browser name: not preceded by '/' or an identifier char (so a path component or a
# longer word like "mychrome" does not match, but "chrome_crashpad" and a quoted name do).
BARE='(^|[^/a-zA-Z0-9_])(chrome|Chrome|crashpad|puppeteer|Puppeteer)'
# the install-path / profile scope that makes a kill's target UNIQUE (the legal form). Applied
# AFTER comments are stripped, so a path sitting only in a comment cannot launder a broad kill
# (the founding-incident bypass), while a path in the actual kill argument correctly exempts it.
SCOPED='\.cache/puppeteer|user-data-dir'

scan_file() {
  # strip trailing comments, then require a killing verb AND a bare browser name, and let a
  # genuinely path-scoped target (its path in the code, not a comment) through.
  awk '{ l=$0; sub(/#.*/,"",l); print NR": "l }' "$1" 2>/dev/null \
    | grep -E "$VERB" 2>/dev/null \
    | grep -E "$BARE" 2>/dev/null \
    | grep -vE "$SCOPED" 2>/dev/null \
    | sed "s#^#$1:#" || true
}

hits=""
target="${1:-}"

if [ -n "$target" ]; then
  if [ -d "$target" ]; then
    while IFS= read -r f; do hits="$hits$(scan_file "$f")"$'\n'; done \
      < <(find "$target" -type f \( -name '*.sh' -o -name '*.py' -o -name '*.js' \
            -o -name '*.ts' -o -name '*.mjs' -o -name '*.cjs' -o -name '*.txt' -o -name '*.md' \))
  else
    hits="$(scan_file "$target")"
  fi
else
  cd "$REPO_ROOT"
  while IFS= read -r f; do
    # the checker and its own test name the patterns in order to forbid / exercise them
    [ "$f" = "guardrails/check-broad-kill.sh" ] && continue
    [ "$f" = "tests/test_broad_kill_guardrail.py" ] && continue
    hits="$hits$(scan_file "$f")"$'\n'
  done < <(git ls-files '*.sh' '*.py' '*.js' '*.ts' '*.mjs' '*.cjs' 'scripts/*' 2>/dev/null)
fi

hits="$(printf '%s' "$hits" | grep -vE '^[[:space:]]*$' || true)"

if [ -n "$hits" ]; then
  echo "FAIL (broad-kill): a cleanup resolves a browser by a bare name and kills it (SPEC INV-162):"
  printf '%s\n' "$hits" | sed 's/^/  /'
  echo "  Fix: kill only the test resource by its recorded PID / process group or install path"
  echo "  (~/.cache/puppeteer/...); never pkill/killall/kill a bare chrome / Chrome / crashpad /"
  echo "  puppeteer, which reaches the human's real browser (row 334, base rule 17)."
  exit 1
fi

echo "OK (broad-kill): no cleanup kills a browser by a bare name pattern (INV-162)."
exit 0
