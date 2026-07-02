#!/usr/bin/env python3
"""Traceability tests — mechanically enforce that spec / matrix / tests stay in sync.

These checks fail when the three artefacts drift apart; they do NOT fix drift.
On failure each method lists every violation so the senior can triage.

Checks
------
1. test_no_dangling_owning_test
   Every `test_file::Class[::method]` citation in TEST_MATRIX.md must resolve:
   the file must exist AND the cited identifier must appear in it.
   Rows explicitly marked REMOVED / skipped / planned are excluded.

2. test_no_duplicate_invariant_id
   No invariant id matching (D-)?INV-\\d+ is defined in two or more table rows in
   TEST_MATRIX.md (first-cell definition rows only; prose mentions don't count).
   Note: INV-31 and D-INV-31 are DIFFERENT namespaces — not a collision.

3. test_every_spec_invariant_has_a_matrix_row
   Every (D-)?INV-\\d+ token that appears in SPEC.md must also appear somewhere in
   TEST_MATRIX.md (even as a tombstone / prose mention).  G-INV / F-INV / RC-INV /
   H-INV tokens are excluded (different namespaces, not enumerated here).

4. test_no_stale_decide_marker
   No single line in SPEC.md or TEST_MATRIX.md may carry BOTH a live ⟨DECIDE marker
   AND the word RESOLVED.  A resolved decision must drop the ⟨…⟩ marker.

Pure stdlib unittest — no pytest, no librosa, no heavy deps.
Run with:  python3 -m unittest tests.test_traceability
"""
import re
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "SPEC.md"
MATRIX = ROOT / "docs" / "TEST_MATRIX.md"
TESTS_DIR = ROOT / "tests"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Matches invariant ID tokens in ONLY the two enumerated namespaces:
#   INV-\d+      (bare per-stem / UI-ladder invariants)
#   D-INV-\d+    (§D reference layer invariants)
# The negative lookbehind (?<![-A-Za-z]) excludes IDs embedded in longer
# prefixes like G-INV-*, F-INV-*, RC-INV-*, H-INV-* (the `-` before INV
# would satisfy the lookbehind and block the match for those forms).
INV_TOKEN_RE = re.compile(r"(?<![-A-Za-z])(?:D-)?INV-\d+")

# Matches owning-test citations that name a real test file.
# Only backtick-quoted content that STARTS with `test_` is captured;
# abbreviated `…::ClassName` forms are silently ignored.
CITATION_RE = re.compile(r"`(test_[^`]+)`")

# Keywords that mark a row as tombstoned / not-yet-built (case-insensitive).
_SKIP_WORDS = ("removed", "skipped", "planned")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lines(path: Path):
    return _read(path).splitlines()


def _is_skip_row(line: str) -> bool:
    """Return True when the whole row line is explicitly tombstoned or planned."""
    lower = line.lower()
    return any(word in lower for word in _SKIP_WORDS)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TraceabilityChecks(unittest.TestCase):
    """Four independent mechanised traceability checks."""

    # ------------------------------------------------------------------
    # Check 1 — no dangling owning-test citations
    # ------------------------------------------------------------------
    def test_no_dangling_owning_test(self):
        """Every owning-test citation in TEST_MATRIX.md must resolve to a real
        file + identifier.  Rows marked REMOVED / skipped / planned are excluded.

        A citation `` `test_file::ClassName::test_method` `` is resolved when:
          (a) tests/<test_file>.py exists, AND
          (b) the last :: token (ClassName or test_method) appears as an
              identifier somewhere in that file.

        A citation with only one segment (`` `test_file` ``) is checked for
        file existence only (no identifier check needed).
        """
        violations = []
        for lineno, line in enumerate(_lines(MATRIX), 1):
            if _is_skip_row(line):
                continue
            for m in CITATION_RE.finditer(line):
                citation = m.group(1)
                parts = citation.split("::")

                # Resolve the file stem (strip optional .py)
                raw_file = parts[0]
                stem = raw_file[:-3] if raw_file.endswith(".py") else raw_file
                test_path = TESTS_DIR / f"{stem}.py"

                # (a) File must exist
                if not test_path.exists():
                    violations.append(
                        f"  line {lineno}: `{citation}` -> {test_path.name} not found"
                    )
                    continue

                # (b) Last token must appear as an identifier in the file
                if len(parts) == 1:
                    # Just a file reference — existence is enough
                    continue
                last_token = parts[-1]
                file_src = test_path.read_text(encoding="utf-8")
                if not re.search(r"\b" + re.escape(last_token) + r"\b", file_src):
                    violations.append(
                        f"  line {lineno}: `{citation}` -> "
                        f'"{last_token}" not found as identifier in {test_path.name}'
                    )

        if violations:
            self.fail(
                f"TEST_MATRIX.md has {len(violations)} unresolved owning-test citation(s):\n"
                + "\n".join(violations)
            )

    # ------------------------------------------------------------------
    # Check 2 — no duplicate invariant ID definitions
    # ------------------------------------------------------------------
    def test_no_duplicate_invariant_id(self):
        """No invariant ID is DEFINED in two or more table rows in TEST_MATRIX.md.

        A 'definition' row is a Markdown table row whose first cell (after the
        leading | and optional whitespace) is exactly an id matching
        (D-)?INV-\\d+ with no trailing content before the next |.

        Example definition rows:
          | INV-1  | ...
          | D-INV-21 | ...

        Non-definition rows (first cell has extra text like '| D-INV-15 (stage-2) |')
        are intentionally excluded — they are not new definitions.

        Note: INV-31 and D-INV-31 are different namespaces and are NOT a collision.
        """
        row_pat = re.compile(r"^\s*\|\s*((?:D-)?INV-\d+)\s*\|")
        seen: dict[str, list[int]] = {}
        for lineno, line in enumerate(_lines(MATRIX), 1):
            m = row_pat.match(line)
            if m:
                inv_id = m.group(1)
                seen.setdefault(inv_id, []).append(lineno)

        violations = []
        for inv_id, linenos in sorted(seen.items()):
            if len(linenos) >= 2:
                violations.append(
                    f"  {inv_id} defined on lines: {', '.join(str(n) for n in linenos)}"
                )

        if violations:
            self.fail(
                f"TEST_MATRIX.md has {len(violations)} duplicate invariant ID definition(s):\n"
                + "\n".join(violations)
            )

    # ------------------------------------------------------------------
    # Check 3 — every SPEC invariant has a matrix row
    # ------------------------------------------------------------------

    # Pre-existing §D matrix-projection debt, frozen 2026-07-02. New gaps still fail.
    # Close these + shrink this set — see NEXT_STEPS "complete §D matrix projection".
    KNOWN_MATRIX_GAPS_2026_07_02 = {
        "D-INV-4", "D-INV-5", "D-INV-6", "D-INV-7", "D-INV-8", "D-INV-9",
        "D-INV-10", "D-INV-11", "D-INV-16", "D-INV-18", "D-INV-19", "D-INV-20",
    }

    def test_every_spec_invariant_has_a_matrix_row(self):
        """Every (D-)?INV-\\d+ token in SPEC.md must appear somewhere in
        TEST_MATRIX.md (even as prose or a tombstone row).

        G-INV / F-INV / RC-INV / H-INV tokens are in separate namespaces and
        are NOT checked here (they would need their own rules).  The lookbehind
        in INV_TOKEN_RE already excludes them automatically.

        A REMOVED tombstone row in TEST_MATRIX.md counts as 'present'.

        Known pre-existing gaps (§D matrix-projection debt) are allowlisted in
        KNOWN_MATRIX_GAPS_2026_07_02 so they do not block the suite.  Any NEW
        gap not in that set still causes a failure.
        """
        spec_text = _read(SPEC)
        matrix_text = _read(MATRIX)

        spec_ids = sorted(set(INV_TOKEN_RE.findall(spec_text)))
        missing = [inv_id for inv_id in spec_ids if inv_id not in matrix_text]

        new_gaps = [inv_id for inv_id in missing
                    if inv_id not in self.KNOWN_MATRIX_GAPS_2026_07_02]

        if new_gaps:
            self.fail(
                f"SPEC.md references {len(new_gaps)} invariant ID(s) absent from "
                f"TEST_MATRIX.md (not in known-gap baseline):\n"
                + "\n".join(f"  {inv_id}" for inv_id in new_gaps)
            )

    # ------------------------------------------------------------------
    # Check 4 — no stale ⟨DECIDE marker
    # ------------------------------------------------------------------
    def test_no_stale_decide_marker(self):
        """No line in SPEC.md or TEST_MATRIX.md may contain BOTH a live
        ⟨DECIDE marker AND the word RESOLVED.

        A DECIDE that has been settled must have its ⟨…⟩ marker removed from
        the doc.  Finding both on the same line means the marker was left in
        after the resolution note was added — a stale open-decision signal.
        """
        violations = []
        for path in (SPEC, MATRIX):
            fname = path.name
            for lineno, line in enumerate(_lines(path), 1):
                if "⟨DECIDE" in line and "RESOLVED" in line:
                    # Truncate very long lines to keep the failure readable
                    snippet = line.strip()
                    if len(snippet) > 160:
                        snippet = snippet[:157] + "..."
                    violations.append(f"  {fname}:{lineno}: {snippet}")

        if violations:
            self.fail(
                f"Found {len(violations)} line(s) with both ⟨DECIDE and RESOLVED "
                f"(resolve the decision, then drop the live marker):\n"
                + "\n".join(violations)
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
