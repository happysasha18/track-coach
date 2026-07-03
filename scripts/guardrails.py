#!/usr/bin/env python3
"""guardrails.py — Automated integrity runner for track-coach.

WHY this exists: three independent invariants must all pass before code can ship, and
forgetting to run any one of them silently degrades the quality gate. This script
runs them in sequence and exits non-zero if any fails, so a CI step or pre-commit hook
can call a single command.

Checks (in order):
  1. Completeness gate — tests/test_completeness_gate.py (INV-GATE / INV-45 / INV-46).
     Every user-facing panel must be POPULATED in a full browser render. A failure here
     means a surface silently emptied — Alexander would find it by eye on the next open.

  2. Traceability checks — tests/test_traceability.py.
     Spec / matrix / tests must stay in sync: no dangling citations, no duplicate IDs,
     no spec invariant without a matrix row, no stale DECIDE markers, every browser-level
     row must cite a headless-harness test (the reverse-verify gate).

  3. Tests-present check — if any file in scripts/*.py is staged/modified in the last
     commit diff (git diff HEAD), at least one file in tests/ must also be present in
     that diff. "Code touched, no test touched" is the exact pattern that let the first
     regression slip through.

Usage:
  python3 scripts/guardrails.py          Run all checks; exit 0 = all green, 1 = failure.
  python3 scripts/guardrails.py --skip 3 Skip the tests-present check (e.g. doc-only run).

Exit codes:
  0  all checks passed
  1  one or more checks failed (details printed to stdout)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_pytest(test_path: str) -> tuple[bool, str]:
    """Run pytest on a single test file. Returns (passed, output).

    Uses `uv run --python 3.11 --with pytest` so the call works regardless of
    whether the caller's Python environment has pytest (the project environment
    is managed by uv). Falls back to the current Python if uv is not found.
    """
    uv_cmd = ["uv", "run", "--python", "3.11", "--with", "pytest",
               "python", "-m", "pytest", "-v", "--tb=short", test_path]
    result = subprocess.run(
        uv_cmd, capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode == 127 or "No such file" in (result.stderr or ""):
        # uv not found — fall back to current Python
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-v", "--tb=short", test_path],
            capture_output=True, text=True, cwd=str(ROOT),
        )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def _check_tests_present() -> tuple[bool, str]:
    """Check that if scripts/*.py were touched in the last commit, tests/ were too.

    Uses `git diff HEAD~1 HEAD --name-only` to find changed files in the last commit.
    If no git history (first commit), always passes.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--name-only"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        if result.returncode != 0:
            # Likely no prior commit (first commit) — skip check
            return True, "  (no prior commit — tests-present check skipped)"
        changed = result.stdout.strip().splitlines()
    except FileNotFoundError:
        return True, "  (git not found — tests-present check skipped)"

    scripts_touched = [f for f in changed if f.startswith("scripts/") and f.endswith(".py")]
    tests_touched   = [f for f in changed if f.startswith("tests/")]

    if scripts_touched and not tests_touched:
        detail = (
            f"  FAIL: {len(scripts_touched)} script(s) changed but no test file touched.\n"
            f"  Scripts: {scripts_touched}\n"
            f"  Either add/update a test for this change or update the matrix row."
        )
        return False, detail

    detail_lines = []
    if scripts_touched:
        detail_lines.append(f"  scripts touched: {scripts_touched}")
        detail_lines.append(f"  tests touched:   {tests_touched}")
    else:
        detail_lines.append("  no scripts/*.py changed in last commit — tests-present check not triggered")
    return True, "\n".join(detail_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="track-coach integrity runner")
    parser.add_argument("--skip", type=int, metavar="N", default=None,
                        help="Skip check number N (1=completeness, 2=traceability, 3=tests-present)")
    args = parser.parse_args()

    skip = {args.skip} if args.skip else set()
    failures: list[str] = []

    # ── Check 1: completeness gate ────────────────────────────────────────
    if 1 not in skip:
        print("=" * 60)
        print("CHECK 1: Completeness gate (test_completeness_gate)")
        print("=" * 60)
        passed, out = _run_pytest("tests/test_completeness_gate.py")
        print(out)
        if passed:
            print("CHECK 1: PASSED\n")
        else:
            print("CHECK 1: FAILED\n")
            failures.append("completeness gate (test_completeness_gate.py)")
    else:
        print("CHECK 1: SKIPPED (--skip 1)\n")

    # ── Check 2: traceability ─────────────────────────────────────────────
    if 2 not in skip:
        print("=" * 60)
        print("CHECK 2: Traceability (test_traceability)")
        print("=" * 60)
        passed, out = _run_pytest("tests/test_traceability.py")
        print(out)
        if passed:
            print("CHECK 2: PASSED\n")
        else:
            print("CHECK 2: FAILED\n")
            failures.append("traceability (test_traceability.py)")
    else:
        print("CHECK 2: SKIPPED (--skip 2)\n")

    # ── Check 3: tests-present ────────────────────────────────────────────
    if 3 not in skip:
        print("=" * 60)
        print("CHECK 3: Tests-present (code change → test change)")
        print("=" * 60)
        passed, detail = _check_tests_present()
        print(detail)
        if passed:
            print("CHECK 3: PASSED\n")
        else:
            print("CHECK 3: FAILED\n")
            failures.append("tests-present (code change without a test change)")
    else:
        print("CHECK 3: SKIPPED (--skip 3)\n")

    # ── Summary ───────────────────────────────────────────────────────────
    print("=" * 60)
    if failures:
        print(f"GUARDRAILS: {len(failures)} check(s) FAILED:")
        for f in failures:
            print(f"  - {f}")
        print("=" * 60)
        return 1
    else:
        print("GUARDRAILS: all checks PASSED")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
