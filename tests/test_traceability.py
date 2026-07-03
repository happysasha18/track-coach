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

5. test_browser_level_rows_cite_a_browser_test   (the REVERSE-VERIFY gate)
   Every ACTIVE (built, non-deferred) TEST_MATRIX row that declares its Level as
   `browser` must cite an owning test that lives in a real headless-harness module
   (BROWSER_HARNESS_MODULES).  A render claim ("the widget shows …", Level=browser)
   backed only by a STRING test is the exact drift that let the omitted-stems
   regression ship for a month (INV-42) — a string test cannot see what a browser
   renders.  Known rows still on string tests are allowlisted + tracked for
   conversion; any NEW browser-level row backed by a non-harness test fails.

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

    # §D matrix-projection debt — CLOSED 2026-07-02 (s36): all 12 core §D invariants
    # (D-INV-4…11/16/18/19/20) now have a real TEST_MATRIX row under
    # "### §D core reference-layer invariants" (built rows cite a live test, deferred
    # rows name the surface they land with). No baseline gaps remain; a NEW absent
    # invariant still fails check-3.
    KNOWN_MATRIX_GAPS_2026_07_02: set[str] = set()

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
        ⟨DECIDE marker AND the word 'resolved' (matched case-insensitively).

        A DECIDE that has been settled must have its ⟨…⟩ marker removed from
        the doc.  Finding both on the same line means the marker was left in
        after the resolution note was added — a stale open-decision signal.
        """
        violations = []
        for path in (SPEC, MATRIX):
            fname = path.name
            for lineno, line in enumerate(_lines(path), 1):
                # Case-insensitive on 'resolved' — a stale marker leaks the same
                # way whether the note is RESOLVED or resolved (s36 hardening).
                if "⟨DECIDE" in line and "resolved" in line.lower():
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

    # ------------------------------------------------------------------
    # Check 5 — the REVERSE-VERIFY gate: browser-level rows need a browser test
    # ------------------------------------------------------------------

    # Test modules backed by the real headless browser harness (scripts/headless_check.py).
    # A "Level = browser" matrix claim is only honoured by a test in this set;
    # a string/node test asserting HTML source cannot verify what a browser renders.
    BROWSER_HARNESS_MODULES: set[str] = {"test_headless_render", "test_completeness_gate"}

    # Browser-level rows still backed by STRING tests — tracked debt, to convert to
    # the headless harness (the reference-read render surfaces: header + facet bars).
    # A NEW browser-level row backed by a non-harness test is NOT allowlisted and fails.
    # 2026-07-02 (s6b): D-INV-5 / D-INV-10 / D-INV-19 converted — allowlist now empty.
    KNOWN_BROWSER_LEVEL_STRING_ROWS_2026_07_02: set[str] = set()

    # An ACTIVE browser-level declaration: `Level = browser…` / `Level: browser…` or a bare
    # `browser-render` / `browser-comp[uted]` token. Deliberately does NOT match a mere mention
    # like "browser conversion lands …" on a row whose declared Level is string/node — otherwise a
    # string-level row that names a future browser conversion would false-positive (caught by deed).
    _BROWSER_LEVEL_RE = re.compile(
        r"level\s*[=:]\s*\**\s*browser|browser-render|browser-comp|browser-computed",
        re.IGNORECASE)
    _ROW_ID_RE = re.compile(r"^\s*\|\s*((?:D-)?INV-\d+)\s*\|")

    def test_browser_level_rows_cite_a_browser_test(self):
        """Every browser-level matrix row that CITES a test must cite a harness test.

        A row is checked when its first cell is an invariant id, its cell declares a
        `browser` Level, AND it cites at least one `test_file::…` — i.e. it has a
        BUILT test.  Pure not-yet-built rows (which name the surface they will land
        with but carry no test) cite nothing, so they are naturally skipped; this is
        deliberately test-presence-driven, not phrase-driven, so a MIXED row (a built
        browser test + a deferred clause like "lands with …") is still checked on its
        built citation rather than slipping through on the deferred phrase.

        For a checked row every cited citation must resolve to a module in
        BROWSER_HARNESS_MODULES; otherwise the render claim rests on a string test.
        Rows in KNOWN_BROWSER_LEVEL_STRING_ROWS_2026_07_02 are known debt and skipped.
        """
        violations = []
        for lineno, line in enumerate(_lines(MATRIX), 1):
            idm = self._ROW_ID_RE.match(line)
            if not idm:
                continue
            if not self._BROWSER_LEVEL_RE.search(line):
                continue
            cited = [m.group(1) for m in CITATION_RE.finditer(line)]
            if not cited:
                continue  # pure not-yet-built browser row — no test to check yet
            inv_id = idm.group(1)
            if inv_id in self.KNOWN_BROWSER_LEVEL_STRING_ROWS_2026_07_02:
                continue
            for citation in cited:
                raw = citation.split("::")[0]
                stem = raw[:-3] if raw.endswith(".py") else raw
                if stem not in self.BROWSER_HARNESS_MODULES:
                    violations.append(
                        f"  line {lineno} ({inv_id}): browser-level claim backed by "
                        f"`{citation}` — {stem} is not a headless-harness module "
                        f"{sorted(self.BROWSER_HARNESS_MODULES)}"
                    )

        if violations:
            self.fail(
                f"{len(violations)} browser-level matrix row(s) not backed by a "
                f"headless-harness test (a render claim needs a browser test):\n"
                + "\n".join(violations)
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
