# stamp_s28_progress.md — s28 stamp package progress

Started: 2026-06-29

## STEP 1 — Namespace legend in TEST_MATRIX.md
STATUS: IN PROGRESS

## STEP 1 — Namespace legend in TEST_MATRIX.md
STATUS: DONE
Inserted blockquote after title line in docs/TEST_MATRIX.md (right after the h1 heading, before "This one document…").

## STEP 2 — Comment annotations on test classes
STATUS: IN PROGRESS

## STEP 2 — Comment annotations on test classes
STATUS: DONE
- Added `# D-INV-30 — per-facet reference read vs centroid` above `ReferenceReadBars` in tests/test_reference_read.py (line 153)
- Added `# D-INV-29 — web-style ★/☆ plaque (facets tied to measurement)` above `ReferenceReadRichLook` in tests/test_reference_read.py (line 444)
- Confirmed `TopKBasics` in tests/test_similarity_columns.py already cites D-INV-27 at lines 198+209 (inline assertion comments)
- File: tests/test_similarity_columns.py::TopKBasics

## STEP 3 — Append D-INV-27..30 rows to TEST_MATRIX.md
STATUS: IN PROGRESS

## STEP 3 — Append D-INV-27..30 rows to TEST_MATRIX.md
STATUS: DONE
Appended 4 rows (D-INV-27, D-INV-28, D-INV-29, D-INV-30) immediately after the D-INV-26 row in docs/TEST_MATRIX.md.

## STEP 4 — Fix RC-INV-10 row
STATUS: IN PROGRESS

## STEP 4 — Fix RC-INV-10 row
STATUS: DONE
Changed RC-INV-10 "not built" note to: "partial-run logic built+tested — test_completeness::PartialRunIsAnError; UI re-measure command not built (backlog)"

## STEP 5 — Version bump to 0.9.0
STATUS: IN PROGRESS

## STEP 5 — Version bump to 0.9.0
STATUS: DONE
Changed TC_VERSION from "0.8.34" to "0.9.0" in scripts/build_widget.py line 31.
0.8.34 no longer appears in any active code file (only in pre-existing data/state_verify_s28.md snapshot, which is a historical record).

## STEP 6 — CHANGELOG.md new 0.9.0 entry
STATUS: IN PROGRESS

## STEP 6 — CHANGELOG.md new 0.9.0 entry
STATUS: DONE
Inserted [0.9.0] entry at the top of the version list (before [0.8.31]) in CHANGELOG.md.

## STEP 7 — Run full test suite
STATUS: IN PROGRESS

## STEP 7 — Full test suite
STATUS: DONE
Runner: uv run --python 3.11 --with numpy/librosa/soundfile/audioread/scipy/scikit-learn/pyloudnorm/pytest python -m pytest tests/ -q
Result: **449 passed, 2 skipped in 1.24s** — ZERO failures.
(The 2 skips are the pre-existing INV-29/INV-30 source-file symmetry tests, known planned/not-built.)

---

## FINAL STATUS: ALL 7 STEPS COMPLETE
- docs/TEST_MATRIX.md — namespace legend added, D-INV-27..30 rows appended, RC-INV-10 fixed
- tests/test_reference_read.py — D-INV-29 comment above ReferenceReadRichLook, D-INV-30 above ReferenceReadBars
- tests/test_similarity_columns.py — TopKBasics already cites D-INV-27 (lines 198+209, confirmed)
- scripts/build_widget.py — TC_VERSION bumped 0.8.34 → 0.9.0
- CHANGELOG.md — [0.9.0] entry inserted at top of version list
- Suite: 449 passed, 2 skipped, 0 failures
