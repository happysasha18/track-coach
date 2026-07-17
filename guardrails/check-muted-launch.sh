#!/usr/bin/env bash
# check-muted-launch.sh — SPEC INV-157's THIRD net: a tracked script that drives a real headless
# browser must launch it MUTED. This gate reds if any tracked script shows a browser-LAUNCH signal
# with no mute signal anywhere in that same file. It exists because a hand-rolled or forked test
# harness that launches Chrome without `--mute-audio` plays sound on the machine it runs on during a
# test run — tlvphotos did exactly this. The pack's own two nets for INV-157 never hear a divergent
# fork's sound: a string-check of the shipped template (`templates/headless_harness.py`) only reads
# the pack's OWN file, and a consumer's by-deed process-group diff only proves teardown, not the
# launch flags. This third net scans the whole tree so a fork that diverges from the template is
# caught by machine, in place of waiting for a human to hear it play.
#
# Usage: check-muted-launch.sh [path]
#   no arg  — scan the repo's tracked executable surfaces (default, the push gate)
#   path    — scan one file or directory (used by the guardrail's own test)
#
# What it flags: a FILE (not a line — a real launch's arg list often spans multiple lines) whose
# comment-stripped CODE carries both a browser-LAUNCH signal (`--headless`, `--remote-debugging-port`,
# `puppeteer.launch`, `chromium.launch`) and a code INVOCATION token (`subprocess`, `Popen`, `spawn`,
# `.launch(`, and kin) but carries `mute-audio` NOWHERE in that code. A file that launches muted
# (`--mute-audio` in the code, in any argument spelling) passes; a file with no launch signal, or one
# that merely NAMES a flag in a docstring or comment with no real invocation, passes. Portable across
# GNU and BSD grep (no \b). Prose surfaces (spec, ROADMAP, inbox, this checker, its own test)
# legitimately NAME the flags and are excluded from the repo scan. Honest boundary: this is a
# structural grep keyed on the Chrome launch flags plus an invocation token — the default scan covers
# every tracked file the extension patterns name plus a tracked EXTENSIONLESS file whose first line
# is a shebang (F5 fold, 2026-07-16: closed the prior extension-allowlist scope hole) — and it is not
# a proof that every possible indirect launch (a bare-shell `chromium --headless`, a wrapper, an
# env-var-built arg list, a non-Chrome driver) is muted; those a fork still owns under INV-158.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# a browser-LAUNCH signal: this file drives a real headless Chrome/Chromium (--mute-audio is Chrome's
# flag, so the scope is the Chrome family — a firefox/webkit driver is out of scope, stated in INV-157).
LAUNCH='(--headless|--remote-debugging-port|puppeteer\.launch|chromium\.launch)'
# a code INVOCATION token: evidence real code launches a process, not prose that merely names a flag.
# Required alongside the launch signal so a docstring or a string literal that only NAMES `--headless`
# is not flagged (the false-positive that once forced a hardcoded per-file exclusion).
INVOKE='(subprocess|Popen|spawn|execSync|child_process|os\.system|\.launch\(|exec\()'

scan_file() {
  # strip trailing #-comments, then work on the CODE only. A file reds when its code carries BOTH a
  # launch signal AND an invocation token, and carries mute-audio NOWHERE in that code. Both the
  # launch check and the mute check read the same comment-stripped text, so a mute flag named only in
  # a comment cannot satisfy the mute check (the machine-defeating evasion this closes), and a flag
  # named only in a comment cannot raise a launch signal either. A hit is FILE-level, so a real
  # launch's multi-line arg list is caught.
  local f="$1"
  local stripped
  local kind="shell"
  case "$f" in
    *.js|*.mjs|*.cjs|*.ts|*.jsx|*.tsx)
      kind="js"
      ;;
    *.py|*.sh)
      kind="shell"
      ;;
    *)
      # extensionless (F5, 2026-07-16 audit, row 356): the extension has already picked "shell" above
      # for anything unrecognized; a tracked file with NO extension carries no such signal at all, so
      # pick the checker by its shebang interpreter instead — the same evidence `list_shebang_scripts`
      # below used to decide the file belongs in the scan in the first place.
      case "${f##*/}" in
        *.*) : ;;  # has an extension — "shell" default already stands
        *)
          case "$(head -n1 "$f" 2>/dev/null || true)" in
            '#!'*node*) kind="js" ;;
            '#!'*) kind="shell" ;;  # sh/bash/python/anything else named — shell's `#` stripping covers it
          esac
          ;;
      esac
      ;;
  esac
  # per-language comment stripping (batch audit 2026-07-16, F2): a JS/TS file's `//` or `/* */`
  # comment naming --mute-audio must not satisfy the mute check any more than a Python/shell `#` one.
  case "$kind" in
    js)
      stripped="$(awk '{ l=$0; sub(/\/\/.*/,"",l); gsub(/\/\*[^*]*\*\//,"",l); print l }' "$f" 2>/dev/null || true)"
      ;;
    *)
      stripped="$(awk '{ l=$0; sub(/#.*/,"",l); print l }' "$f" 2>/dev/null || true)"
      ;;
  esac
  # here-strings, never a pipe: under `set -o pipefail` a `printf | grep -q` pipeline reds
  # falsely on a LARGE file — grep exits at its first match, printf catches SIGPIPE once the
  # remainder outgrows the pipe buffer, and pipefail reads that 141 as "no match" (the CI-only
  # false red of 2026-07-17, deterministic past ~64 KB; the by-deed red rides
  # tests/test_muted_launch_guardrail.py::test_big_muted_file_survives_the_pipe).
  if grep -qE "$LAUNCH" 2>/dev/null <<< "$stripped" \
     && grep -qE "$INVOKE" 2>/dev/null <<< "$stripped"; then
    if ! grep -q 'mute-audio' 2>/dev/null <<< "$stripped"; then
      echo "$f"
    fi
  fi
}

list_shebang_scripts() {
  # F5 (2026-07-16 audit, row 356): a tracked file with NO extension (e.g. `bin/serve`) matches none
  # of the extension patterns below and is invisible to the scan, extension being the only signal
  # those patterns read. A real script still announces itself by its first line, so a tracked,
  # extensionless file whose first line is a shebang belongs in the scan too — scan_file() above then
  # picks its checker (shell vs js comment stripping) from that same shebang.
  git ls-files 2>/dev/null | while IFS= read -r f; do
    case "${f##*/}" in
      *.*) continue ;;  # has an extension — already covered by the patterns below
    esac
    [ -f "$f" ] || continue
    case "$(head -n1 "$f" 2>/dev/null || true)" in
      '#!'*) echo "$f" ;;
    esac
  done
}

hits=""
target="${1:-}"

if [ -n "$target" ]; then
  if [ -d "$target" ]; then
    while IFS= read -r f; do
      hit="$(scan_file "$f")"
      [ -n "$hit" ] && hits="$hits$hit"$'\n'
    done < <(find "$target" -type f \( -name '*.sh' -o -name '*.py' -o -name '*.js' \
          -o -name '*.ts' -o -name '*.jsx' -o -name '*.tsx' -o -name '*.mjs' -o -name '*.cjs' \
          -o -name '*.txt' -o -name '*.md' \))
  else
    hits="$(scan_file "$target")"
  fi
else
  cd "$REPO_ROOT"
  while IFS= read -r f; do
    # the checker and its own test legitimately NAME the launch/mute flags to forbid or exercise them
    [ "$f" = "guardrails/check-muted-launch.sh" ] && continue
    [ "$f" = "tests/test_muted_launch_guardrail.py" ] && continue
    hit="$(scan_file "$f")"
    [ -n "$hit" ] && hits="$hits$hit"$'\n'
  done < <(
    { git ls-files '*.sh' '*.py' '*.js' '*.ts' '*.jsx' '*.tsx' '*.mjs' '*.cjs' 'scripts/*' 2>/dev/null
      list_shebang_scripts
    } | sort -u
  )
fi

hits="$(printf '%s' "$hits" | grep -vE '^[[:space:]]*$' || true)"

if [ -n "$hits" ]; then
  echo "FAIL (muted-launch): a tracked script drives a real headless browser without --mute-audio (SPEC INV-157):"
  printf '%s\n' "$hits" | sed 's/^/  /'
  echo "  Fix: add --mute-audio to the browser launch, or adopt the pack's canonical muted harness"
  echo "  templates/headless_harness.py (INV-158) in place of a hand-rolled or forked launch."
  exit 1
fi

echo "OK (muted-launch): every browser-driving script launches muted (INV-157)."
exit 0
