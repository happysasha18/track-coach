#!/usr/bin/env python3
"""check_pin_drift.py — architecture SYMBOL anchors must not rot silently.

Adopted from live-spec's check-pin-drift.sh (row 90, the track-coach lesson: 7 of 17
pins drifted in ONE session, silently). FIT DECISION (2026-07-17): the pack gate reads
`path/to/file:line` pins from a `## Nodes` table. track-coach's ARCHITECTURE.md instead
carries SYMBOL anchors — `build_recommendations:1355`, `PLAYER_LOGIC:4071`, `:root:2924` —
where the NORMATIVE thing is the named symbol and the `:line` is a cache (SPEC E-14). The
owning file is the nearest ``*.py`` named earlier on the SAME table row. Leaving these
unguarded was the other option; guarding them is the root fix, so this checker resolves each
anchor's file from its row and verifies the symbol still lives near its cached line.

For each `symbol:line` anchor:
  RED   — owning file missing, or `:line` beyond end of file (a hard break);
  DRIFT — the symbol text is not found within +/-25 lines of the cached line
          (reported as drift; RED when --strict, which track-coach passes since its
          anchors carry real symbols).

Usage: check_pin_drift.py [architecture-file] [--strict]
"""
import re
import sys
from pathlib import Path

WINDOW = 25  # +/- lines around the cached line to look for the symbol

# a backtick-wrapped `.py` file token, with its span on the line
FILE_RE = re.compile(r"`([A-Za-z0-9_]+\.py)`")
# track-coach writes anchors in TWO notations, both guarded here:
#   (a) `<symbol>:<line>`  — symbol AND line inside one backtick pair (`PLAYER_LOGIC:4071`);
#       symbol is everything before the final `:<digits>` (so `:root:2924` -> symbol `:root`).
#   (b) `<symbol>`:<line>  — symbol backticked, the `:line` trailing OUTSIDE (`cueAt`:3754).
# A line may be a single number or a `NNNN-NNNN` / `NNNN–NNNN` range (first number is the pin).
ANCHOR_A_RE = re.compile(r"`([^`]+?):(\d+)(?:[–-]\d+)?`")
ANCHOR_B_RE = re.compile(r"`([^`]+?)`:(\d+)(?:[–-]\d+)?")


def _owning_file(line: str, anchor_start: int):
    """The `.py` file named nearest-before the anchor's position on this line."""
    best = None
    for m in FILE_RE.finditer(line):
        if m.start() < anchor_start:
            best = m.group(1)
        else:
            break
    return best


def main(argv):
    strict = "--strict" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    repo_root = Path(__file__).resolve().parents[1]
    arch = Path(args[0]) if args else repo_root / "docs" / "ARCHITECTURE.md"
    if not arch.is_file():
        print(f"FAIL (pin drift): architecture file not found: {arch}")
        return 1

    hard_fail = 0
    drift = 0
    checked = 0
    unresolved = 0

    for raw in arch.read_text().splitlines():
        # collect anchors from both notations, keyed by position so a token is counted once
        anchors = {}
        for m in ANCHOR_A_RE.finditer(raw):
            anchors[m.start()] = (m.group(1), int(m.group(2)))
        for m in ANCHOR_B_RE.finditer(raw):
            anchors.setdefault(m.start(), (m.group(1), int(m.group(2))))
        for start in sorted(anchors):
            symbol, line = anchors[start]
            fname = _owning_file(raw, start)
            if not fname:
                # an anchor with no `.py` file on its row cannot be resolved -> a finding
                print(f"FAIL (pin drift): `{symbol}:{line}` — no owning .py file named on its row")
                unresolved += 1
                continue
            full = repo_root / "scripts" / fname
            if not full.is_file():
                # last resort: search the repo for the named file
                hits = list(repo_root.glob(f"**/{fname}"))
                hits = [h for h in hits if ".git" not in h.parts]
                if not hits:
                    print(f"FAIL (pin drift): `{symbol}:{line}` — owning file '{fname}' missing")
                    hard_fail += 1
                    continue
                full = hits[0]
            checked += 1
            lines = full.read_text(errors="replace").splitlines()
            if line > len(lines):
                print(f"FAIL (pin drift): `{fname}:{symbol}:{line}` — beyond end of file "
                      f"({len(lines)} lines)")
                hard_fail += 1
                continue
            lo = max(0, line - 1 - WINDOW)
            hi = min(len(lines), line - 1 + WINDOW + 1)
            window = "\n".join(lines[lo:hi])
            if symbol not in window:
                print(f"DRIFT (pin drift): `{fname}:{symbol}:{line}` — symbol not found "
                      f"within +/-{WINDOW} lines of the cached line")
                drift += 1

    if checked == 0 and unresolved == 0:
        print(f"FAIL (pin drift): no symbol anchors parsed from {arch}")
        return 1

    if hard_fail or unresolved:
        print("  Fix: re-run the anchor's grep and update the file/line (SPEC E-14).")
        return 1
    if drift and strict:
        print("  Fix (strict): re-resolve each drifted anchor's named symbol and refresh its cached line.")
        return 1

    tail = ", drift reported above (non-strict)" if drift else ""
    print(f"OK (pin drift): {checked} symbol anchor(s) checked{tail}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
