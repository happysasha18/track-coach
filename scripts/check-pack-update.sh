#!/bin/bash
# check-pack-update.sh — once a day, ask the public repo whether the pack moved past this machine (SPEC E-25).
# PROPOSES only — never installs (the human's gate, ACT-1). Offline or unreadable remote = one honest
# skip line naming the address, exit 0, stamp left unwritten so the next session retries.
# Forward only: a machine ahead of the public repo reads as up to date, never a downgrade proposal.
# Test/override flags: --remote-file <path> (bypass network) · --installed-file <path> · --stamp-file <path> · --force (ignore today's stamp)
set -u

REMOTE_URL="https://raw.githubusercontent.com/happysasha18/live-spec/main/VERSION"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLED_FILE="$ROOT/VERSION"
STAMP_FILE="$HOME/.claude/live-spec/update-check-stamp"
REMOTE_FILE=""
FORCE=0
MANIFEST=""
PACK_ROOT=

while [ $# -gt 0 ]; do
  case "$1" in
    --remote-file)    REMOTE_FILE="$2";    shift 2 ;;
    --installed-file) INSTALLED_FILE="$2"; shift 2 ;;
    --stamp-file)     STAMP_FILE="$2";     shift 2 ;;
    --force)          FORCE=1;             shift ;;
    --manifest)       MANIFEST="$2";       shift 2 ;;
    --pack-root)      PACK_ROOT="$2";      shift 2 ;;
    *) echo "check-pack-update: unknown flag $1" >&2; exit 2 ;;
  esac
done

today="$(date +%Y-%m-%d)"
if [ "$FORCE" -eq 0 ] && [ -f "$STAMP_FILE" ] && [ "$(cat "$STAMP_FILE" 2>/dev/null)" = "$today" ]; then
  echo "pack update check: already ran today ($today) — skipped"
  exit 0
fi

if [ -n "$REMOTE_FILE" ]; then
  src="$REMOTE_FILE"
  remote="$(cat "$REMOTE_FILE" 2>/dev/null)"
else
  src="$REMOTE_URL"
  remote="$(curl -fsS --max-time 10 "$REMOTE_URL" 2>/dev/null)"
fi

if ! printf '%s' "$remote" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "pack update check: skipped — offline or unreadable remote ($src)"
  exit 0
fi

installed="$(cat "$INSTALLED_FILE" 2>/dev/null)"
if ! printf '%s' "$installed" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "pack update check: skipped — no readable installed version at $INSTALLED_FILE"
  exit 0
fi

mkdir -p "$(dirname "$STAMP_FILE")" && printf '%s' "$today" > "$STAMP_FILE"

check_manifest() {
  # Vendored-copy staleness (SPEC INV-177): runs on EVERY check, not only when the pack itself moved —
  # the standing state is a current pack and a lagging host, and a watcher silent exactly there would
  # re-open the hole it was built to close (batch audit 2026-07-16, F1). The pin compares against the
  # LOCAL pack VERSION: the newest truth this machine can act on.
  local pack_now="$1"
  [ -z "$MANIFEST" ] && [ -f "scripts/ratchet-manifest.json" ] && MANIFEST="scripts/ratchet-manifest.json"
  [ -z "$PACK_ROOT" ] && PACK_ROOT="$ROOT"
  if [ -n "$MANIFEST" ] && [ -f "$MANIFEST" ]; then
    python3 - "$MANIFEST" "$PACK_ROOT" "$pack_now" <<'PYEOF'
import hashlib, json, os, sys
manifest_path, pack_root, pack_now = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    man = json.load(open(manifest_path))
except (OSError, ValueError):
    sys.exit(0)
def _v(t):
    try:
        return tuple(int(x) for x in t.split("."))
    except ValueError:
        return ()
pinned = str(man.get("pack_version", ""))
if pinned and _v(pinned) and _v(pack_now) and _v(pinned) < _v(pack_now):
    stale = []
    for rel, sha in (man.get("vendored") or {}).items():
        src = os.path.join(pack_root, rel)
        if os.path.isfile(src):
            cur = hashlib.sha256(open(src, "rb").read()).hexdigest()
            if cur != sha:
                stale.append(rel)
    print("  VENDORED GATES PINNED TO %s — the pack moved past the pin (now %s):" % (pinned, pack_now))
    for rel in stale:
        print("    stale vs current pack: %s" % rel)
    if not stale:
        print("    (no vendored file differs from the local pack copy — the pin alone is old)")
    # Name the road per stale kit (2026-07-16 fix): a scaffold-only host was pointed at the ratchet
    # installer, which doesn't touch scaffold/guardrails/ at all. Manifest keys tell the kits apart —
    # install-scaffold.sh always pins under the pack-relative scaffold/guardrails/<name> prefix;
    # install-ratchet.sh's own vendor set never uses that prefix.
    scaffold_stale = [rel for rel in stale if rel.startswith("scaffold/guardrails/")]
    ratchet_stale = [rel for rel in stale if not rel.startswith("scaffold/guardrails/")]
    if scaffold_stale:
        print("  re-install road: bash <pack>/adopt/install-scaffold.sh --force  (re-vendoring the scaffold checks)")
    if ratchet_stale or not stale:
        print("  re-install road: bash <pack>/adopt/install-ratchet.sh --force  (re-seeding caps is explicit, never silent)")
PYEOF
  fi
}

newest="$(printf '%s\n%s\n' "$installed" "$remote" | sort -V | tail -1)"
if [ "$remote" = "$installed" ] || [ "$newest" = "$installed" ]; then
  echo "pack update check: up to date ($installed)"
  arm_out="$(check_manifest "$installed")"
  if [ -n "$arm_out" ]; then
    printf '%s\n' "$arm_out"
    echo "  PROPOSAL ONLY — nothing installed; updating is the human's word."
  fi
  exit 0
fi

echo "PACK UPDATE AVAILABLE: $remote (this machine runs $installed)"
echo "  what changed: https://github.com/happysasha18/live-spec/blob/main/JOURNAL.md"
echo "  update road: install.sh (attic-backed) — or a plain 'git pull' where the repo itself runs the pack"

check_manifest "$installed"

echo "  PROPOSAL ONLY — nothing installed; updating is the human's word."
exit 0
