#!/usr/bin/env python3
"""check_deferral_marker.py — the mechanical net for wrongly-parked work.

WHY this exists (2026-07-15, from the owner's word that day — he never asked to be waited on):
The recurring failure was work parked for his greenlight that was actually the
agent's own. A code-vs-spec defect — where the code diverges from an already-correct
spec — is DERIVABLE from that spec sentence, so by the derivability rule (SPEC INV-152
/ host profile override 6) it never needs a human greenlight; it is fixed through the
bug door with a red-first test. A prose rule kept being forgotten. This is the
mechanical guard that catches the pattern on sight instead of relying on memory.

WHAT it checks in NEXT_STEPS.md (the resume file where parked work lives):

  A. WAIT-MARKER ON A DERIVABLE DEFECT.  A row that BOTH carries a "wait for the
     human to unblock" marker (greenlight / awaiting Alexander / his OK to reopen /
     reopen the closed dev on his word) AND describes a code-vs-spec defect (code
     diverged, spec is right, code-ahead-of-spec) is the finding: it is derivable,
     so it is the agent's own — remove the wait, fix it.

  B. A HUMAN-PARKED ROW THAT NAMES NO HUMAN-ONLY FACT.  A row parked as the human's
     (🙋 marker, "his call", "he decides", "Alexander drives") must name a legitimate
     human-only fact: taste, scope, look/feel, policy, promotion/marketing, an
     outward or irreversible act (publish / MAJOR version), or an explicit
     "spec is silent / undecided / no artifact holds it" gap. A parked row naming
     none of these is itself the finding (the converse of INV-152).

The check is heading-aware: a bullet inherits the human-only fact named on the
"🙋 …" / "His call …" heading it sits under, so the fact need be named once per block.

Exit 0 = clean; 1 = at least one finding (printed with NEXT_STEPS line numbers).

Usage:
  python3 guardrails/check_deferral_marker.py [path-to-NEXT_STEPS.md]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A "wait for the human to unblock" marker — the agent is blocked pending his word.
WAIT_MARKERS = [
    "greenlight",
    "awaiting alexander",
    "awaiting his",
    "his ok to reopen",
    "his greenlight",
    "reopen the closed dev",       # only illegitimate when paired with a defect (see below)
    "on his word to reopen",
    "waiting for his",
    "his word to reopen",
]

# Signals that a row is a code-vs-spec DEFECT (derivable → the agent's own).
DEFECT_SIGNALS = [
    "code diverged",
    "code-vs-spec",
    "code ahead of spec",
    "code-ahead-of-spec",
    "spec is right",
    "diverges from the spec",
    "diverged from the spec",
    "product-code defect",
]

# Markers that a row is parked as the HUMAN's to decide.
HUMAN_PARK_MARKERS = [
    "🙋",
    "his call",
    "he decides",
    "his to decide",
    "alexander drives",
]

# Legitimate human-only facts. If a parked row (or its heading) names one of these,
# the park is justified.
HUMAN_ONLY_FACTS = [
    "taste", "scope", "look", "feel", "his preference", "he prefers", "policy",
    "promotion", "promote", "marketing",
    "publish", "public", "major version", "version bump", "version flip",
    "irreversible", "outward",
    "spec is silent", "spec never says", "spec never declares", "undecided",
    "no artifact", "decide + spec", "decide and spec", "which invariant wins",
    "his to correct", "his read", "his eye", "his device", "on his machine",
    "recommend", "recommendation",   # a "his call — I recommend X" row names the taste fork
]


# Negations that clear a wait-marker — the sentence is stating the ABSENCE of a wait
# ("no greenlight", "without his OK") or asserting the item is the agent's own.
NEGATIONS = [
    "no greenlight", "without greenlight", "no wait", "not awaiting",
    "without his", "no his ok", "the agent's own", "no human", "removed",
]


def _has(text: str, needles: list[str]) -> bool:
    low = text.lower()
    return any(n in low for n in needles)


def _is_heading(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("#") or s.startswith("**") or bool(re.match(r"^\*\*", s))


def check(path: Path) -> list[str]:
    """Return a list of finding strings (empty = clean)."""
    findings: list[str] = []
    if not path.exists():
        return [f"NEXT_STEPS not found at {path} — nothing to check (treated as clean)."]

    lines = path.read_text(encoding="utf-8").splitlines()

    # ── First pass: block map for Check B. A "park block" is a park heading plus
    #    every line until the next heading; the block is justified if the heading OR
    #    any line inside it names a human-only fact. This lets "🙋 His call …" name
    #    the fact once and its bullets inherit it. ─────────────────────────────
    block_justified: dict[int, bool] = {}   # heading line-no → justified?
    block_of_line: dict[int, int] = {}       # any park-block line-no → its heading line-no
    cur_head: int | None = None
    cur_is_park = False
    cur_fact = False
    cur_members: list[int] = []

    def _close_block():
        if cur_head is not None and cur_is_park:
            block_justified[cur_head] = cur_fact
            for m in cur_members:
                block_of_line[m] = cur_head

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if _is_heading(line):
            _close_block()
            cur_head = i
            cur_is_park = _has(line, HUMAN_PARK_MARKERS)
            cur_fact = _has(line, HUMAN_ONLY_FACTS)
            cur_members = [i]
        else:
            if cur_is_park and line.strip():
                cur_members.append(i)
                if _has(line, HUMAN_ONLY_FACTS):
                    cur_fact = True
    _close_block()

    # ── Second pass: line-by-line findings. ──────────────────────────────────
    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        if not line.strip():
            continue

        # ── Check A: a wait-marker sitting on a derivable defect ──────────────
        if (_has(line, WAIT_MARKERS) and _has(line, DEFECT_SIGNALS)
                and not _has(line, NEGATIONS)):
            findings.append(
                f"  A  L{i}: a code-vs-spec defect carries a wait-for-greenlight marker. "
                f"A defect where the spec is right is DERIVABLE → the agent's own to fix "
                f"(INV-152), no greenlight. Remove the wait.\n       > {line.strip()[:140]}"
            )

        # ── Check B: a human-parked block that names no human-only fact ───────
        # Flag only the block's HEADING once, not every bullet, to stay quiet.
        if _is_heading(line) and _has(line, HUMAN_PARK_MARKERS):
            if not block_justified.get(i, False):
                findings.append(
                    f"  B  L{i}: a block parked as the human's names no human-only fact "
                    f"(taste / scope / policy / outward / spec-silent) in its heading OR any "
                    f"row. If none applies, it is the agent's own (INV-152). Name the fact "
                    f"or unpark it.\n       > {line.strip()[:140]}"
                )

    return findings


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else (ROOT / "NEXT_STEPS.md")
    findings = check(path)
    print("=" * 66)
    print(f"DEFERRAL-MARKER CHECK — {path}")
    print("=" * 66)
    if not findings:
        print("CLEAN: no wrongly-parked work found.")
        print("=" * 66)
        return 0
    print(f"{len(findings)} FINDING(S) — a marker that cannot name its human-only fact "
          f"is itself the finding (INV-152):")
    for f in findings:
        print(f)
    print("=" * 66)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
