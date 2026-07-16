"""Compaction ratchet locks for track-coach's living docs (live-spec 2.0.0 adoption, 2026-07-16).

WHY this file exists: the pack's 2.0.0 major makes compaction a GATE, not a habit (INV-164) — a quality a
machine can verify is held by a check every push, not by a reader's attention. track-coach adopts that
ratchet here, scoped to Alexander's own language laws:

  - The style lint's ERRORS are exactly his laws — the scissors ban (no "X, not Y" contrast frame),
    negation-opener (say what a thing IS), and machine-jargon. ALL-CAPS emphasis and second-person "you"
    stay ADVISORY (warnings), because track-coach's spec uses both on purpose. So the floor is ZERO errors.
  - Redundancy has a floor, not a zero: the 29 open pairs are the spec's deliberate cross-section
    restatements (see scripts/spec-debt-cap.json). The cap stops NEW duplication and only ratchets down.

Both caps live in scripts/spec-debt-cap.json. Lowering a cap is an ordinary commit; raising one is a
deliberate, named edit — this test makes either move visible in the diff.
"""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DOCS = ROOT / "docs"
CAP = json.loads((SCRIPTS / "spec-debt-cap.json").read_text())
GUARDED_DOCS = ["SPEC.md", "ARCHITECTURE.md", "TEST_MATRIX.md"]


def _style(doc):
    """Run the style lint (DEFAULT mode = his-law errors only) and return its JSON summary."""
    r = subprocess.run(
        ["python3", str(SCRIPTS / "spec-style-lint.py"), str(DOCS / doc)],
        capture_output=True, text=True)
    # the summary is the last JSON line on stdout; errors also print above it
    line = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("{")][-1]
    return json.loads(line)


def _redundancy(doc):
    r = subprocess.run(
        ["python3", str(SCRIPTS / "spec-redundancy-precheck.py"), str(DOCS / doc)],
        capture_output=True, text=True)  # exits 1 while any pair is open — read stdout, not the code
    line = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("{")][-1]
    return json.loads(line)


class CompactionLocks(unittest.TestCase):
    def test_style_floor_is_zero_his_law_errors(self):
        """Every guarded doc holds ZERO scissors / negation-opener / machine-jargon errors. A new one
        blocks the push; caps/second-person stay advisory (they are track-coach's own voice)."""
        for doc in GUARDED_DOCS:
            summary = _style(doc)
            self.assertLessEqual(
                summary["errors"], CAP["style_errors_max"],
                f"{doc}: {summary['errors']} his-law style errors (cap {CAP['style_errors_max']}). "
                f"Fix the scissors/negation-opener, or — only if a rule genuinely changed — raise the cap "
                f"deliberately in scripts/spec-debt-cap.json and say why.")

    def test_redundancy_only_ratchets_down(self):
        """SPEC redundancy stays at or below its frozen floor. New duplication blocks; the deliberate
        cross-section restatements already counted are not asked to merge."""
        summary = _redundancy("SPEC.md")
        self.assertLessEqual(
            summary["open"], CAP["redundancy_open_max"],
            f"SPEC.md redundancy rose to {summary['open']} (cap {CAP['redundancy_open_max']}). A new "
            f"near-duplicate crept in — merge it, or raise the cap deliberately with a reason if it is a "
            f"genuine new cross-section restatement.")


if __name__ == "__main__":
    unittest.main()
