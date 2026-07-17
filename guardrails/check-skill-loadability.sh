#!/usr/bin/env bash
# check-skill-loadability.sh — every shipped skill LOADS and can SCOPE itself
# (adopted from live-spec, the Trail-of-Bits lesson: a skill the harness can't
# index or a reader can't scope is a broken artifact however good its prose).
#
# track-coach FIT DECISION (2026-07-17): the pack gate globs `skills/*/SKILL.md`
# for a repo-of-skills. track-coach is ONE tool-skill whose SKILL.md sits at the
# repo root — so this adaptation checks that ROOT SKILL.md (and any nested
# skills/*/SKILL.md, should the repo ever grow some). The checks are identical:
# a frontmatter block, a name matching its folder, a description, a metadata
# version, and a "when NOT to use" section.
#
# Usage: check-skill-loadability.sh [repo-root]

set -euo pipefail

ROOT="${1:-$(git rev-parse --show-toplevel)}"

# The root SKILL.md is named for the repo's own folder; any skills/*/SKILL.md is
# named for its own subfolder. Both are checked with the same rules.
skill_mds=()
[ -f "$ROOT/SKILL.md" ] && skill_mds+=("$ROOT/SKILL.md")
for nested in "$ROOT"/skills/*/SKILL.md; do
  [ -f "$nested" ] && skill_mds+=("$nested")
done

fail=0
count=0
for skill_md in "${skill_mds[@]}"; do
  count=$((count+1))
  # the root skill is named for the repo folder; a nested skill for its own folder
  if [ "$skill_md" = "$ROOT/SKILL.md" ]; then
    dir_name="$(basename "$ROOT")"
  else
    dir_name="$(basename "$(dirname "$skill_md")")"
  fi

  # frontmatter block: first line ---, a closing --- within the first 40 lines
  if [ "$(head -1 "$skill_md")" != "---" ] || ! sed -n '2,40p' "$skill_md" | grep -q '^---$'; then
    echo "FAIL (loadability): $dir_name — no frontmatter block"; fail=1; continue
  fi
  fm="$(awk '/^---$/{n++; next} n==1{print} n>=2{exit}' "$skill_md")"

  name="$(printf '%s\n' "$fm" | sed -n 's/^name:[[:space:]]*//p' | head -1)"
  if [ -z "$name" ]; then
    echo "FAIL (loadability): $dir_name — frontmatter has no name:"; fail=1
  elif [ "$name" != "$dir_name" ]; then
    echo "FAIL (loadability): $dir_name — name '$name' does not match its folder"; fail=1
  fi

  if ! printf '%s\n' "$fm" | grep -q '^description:'; then
    echo "FAIL (loadability): $dir_name — frontmatter has no description:"; fail=1
  fi

  if ! printf '%s\n' "$fm" | grep -Eq '^[[:space:]]+version:[[:space:]]*[0-9]+\.[0-9]+\.[0-9]+'; then
    echo "FAIL (loadability): $dir_name — no metadata version (semver under metadata:)"; fail=1
  fi

  if ! grep -qi 'when NOT to' "$skill_md"; then
    echo "FAIL (loadability): $dir_name — no 'when NOT to use' section"; fail=1
  fi
done

if [ "$count" -eq 0 ]; then
  echo "FAIL (loadability): no SKILL.md found at $ROOT (or $ROOT/skills/*/)"; exit 1
fi

if [ "$fail" -ne 0 ]; then
  echo "  Fix: repair the skill's frontmatter/section; a skill that can't load or scope itself must not ship."
  exit 1
fi

echo "OK (loadability): $count skill(s) load, named, versioned, negative-scoped."
exit 0
