# matrix_audit_s28.md — Cross-reference audit (s28)

Audited: 2026-06-29  
Sources: `docs/SPEC.md`, `docs/TEST_MATRIX.md`, `tests/*.py`  
Scope: D-INV-1..30, F-INV-1..8, RC-INV-1..12 (incl. 5a, 5b, 7a)

---

## Table 1 — D-INV-1..30 (§D reference layer)

Matrix rows exist only for D-INV-21..26 (§D10F section of TEST_MATRIX.md, lines 226–231).
D-INV-1..20 and D-INV-27..30 have NO matrix row.

| id | SPEC line | gloss (6-10 words) | matrix row (line# or ABSENT) | test (file:line + name or NONE) | notes |
|---|---|---|---|---|---|
| D-INV-1 | 841 | No grade/score/pass-fail from any reference surface | ABSENT | NONE | Core safety rule, never enumerated in matrix |
| D-INV-2 | 843 | Web info labelled external; card still needs real finding | ABSENT | NONE | |
| D-INV-3 | 845 | Reference track audio-only, no Ableton project surfaces | ABSENT | NONE | |
| D-INV-4 | 846 | Tool never guesses aspiration mapping, always user's | ABSENT | NONE | |
| D-INV-5 | 849 | Track with no mapping byte-for-byte unchanged | ABSENT | NONE | |
| D-INV-6 | 857 | Show/hide reference = one named switch, never strands | ABSENT | NONE | |
| D-INV-7 | 859 | Reference tracks never enter library catalog/signatures | ABSENT | NONE | |
| D-INV-8 | 904 | Web fetch always completes/fails/times-out, never hangs | ABSENT | NONE | Liveness rule |
| D-INV-9 | 911 | Reference produces full fingerprint or reports gap, never half-silent | ABSENT | NONE | |
| D-INV-10 | 861 | Every mood/style statement has a real measured signal | ABSENT | NONE | |
| D-INV-11 | 867 | Verdict in full-dimensional space, no lossy projection | ABSENT | NONE | |
| D-INV-12 | 872 | Fingerprint deterministic per epoch, never moves silently | ABSENT | NONE | |
| D-INV-13 | 874 | No mapping points at deleted direction or removed track | ABSENT | NONE | |
| D-INV-14 | 885 | Placement carries human stamp AND content-hash pair | ABSENT | NONE | |
| D-INV-15 | 887 | Re-flavouring only re-orders/re-words; card set identical | ABSENT | NONE | |
| D-INV-16 | 890 | «своё»/in-zone only against cloud, never reduced direction | ABSENT | NONE | |
| D-INV-17 | 896 | Re-flavouring across many directions is deterministic | ABSENT | NONE | |
| D-INV-18 | 880 | Add/remove member both recompute cloud and re-stamp reads | ABSENT | NONE | |
| D-INV-19 | 899 | in-zone/diverge = pure function of full-dim fingerprint | ABSENT | NONE | |
| D-INV-20 | 855 | Reference is full-run-only; quick never referenceable | ABSENT | NONE | Also cited §D.3 |
| D-INV-21 | 1076 | Catalog column = plaque chip = read panel, one geometry | L226 | `test_similarity_columns.py:32,41` — `LeansTowardPicksNearestDirection` | Geometry half built; render side "not built" per matrix |
| D-INV-22 | 1098 | Quick-only version → "full analysis only", never blank-implies-none | L227 | NONE | Matrix: "not built — lands with catalog render" |
| D-INV-23 | 1108 | Both placements under one references switch; never strands | L228 | NONE | Matrix: "not built" |
| D-INV-24 | 1116 | Recompute + re-stamp on library/epoch change | L229 | `test_reference_read.py:446` — `ReferenceReadRichLook` (docstring cites D-INV-24) | Matrix: "not built — composes with placement code" |
| D-INV-25 | 1120 | Never a raw number—direction name + coarse cue only | L230 | `test_reference_read.py:187` (`ReferenceReadBars::test_no_raw_numbers_on_surface`); `test_reference_read.py:557` (`ReferenceReadRichLook::test_no_raw_decimal_numbers_in_visible_text`); `test_similarity_columns.py:140` (`NoNumberLeaksOut`); `test_similarity_columns.py:232` (`TopKBasics::test_result_levels_are_words_not_numbers`) | Multiple test guards |
| D-INV-26 | 1139 | Closeness = colour-only, green/amber/red, greyscale-safe glyph | L231 | `test_similarity_columns.py:46` (`RelativeLeanBuckets`); `test_similarity_columns.py:117` (`NearestOwnRedIsLastResort`) | Geometry BUILT+TESTED; colour render not built |
| D-INV-27 | 1149 | Up-to-three nearest selector, never pads with far filler | ABSENT | `test_similarity_columns.py:198` (`TopKBasics::test_far_directions_excluded_never_in_result`); `test_similarity_columns.py:209` (`TopKBasics::test_all_equidistant_returns_empty`) | Test IS about the reference top-k selector — CORRECT, not mis-mapped |
| D-INV-28 | 1175 | Every click = navigation only, no persisted selection state | ABSENT | NONE | |
| D-INV-29 | 1227 | Plaque shows only facets tied to measurement (★/☆ marks) | ABSENT | NONE | `ReferenceReadRichLook` tests ★/☆ logic but does NOT cite D-INV-29 by ID |
| D-INV-30 | 1304 | Per-facet bar: your track vs centroid, no raw distance | ABSENT | NONE | `ReferenceReadBars` tests bar rendering but does NOT cite D-INV-30 by ID |

---

## Table 2 — F-INV-1..8 (§F own-library column)

All F-INV-1..8 are present in TEST_MATRIX.md §D10F section (lines 236–243).

| id | SPEC line | gloss (6-10 words) | matrix row (line# or ABSENT) | test (file:line + name or NONE) | notes |
|---|---|---|---|---|---|
| F-INV-1 | 1345 | Up to 3 nearest own-tracks; red last-resort, never empty | L236 | `test_similarity_columns.py:100` (`NearestOwnBasics::test_ranked_nearest_first_and_excludes_self`, `test_cap_of_three`); `test_similarity_columns.py:117` (`NearestOwnRedIsLastResort`); `test_catalog_columns.py:107,124` (`SiblingCellRendering`) | Geometry built; render side "not built" per matrix |
| F-INV-2 | 1347 | Track never its own neighbour; display may be asymmetric | L237 | `test_similarity_columns.py:101` (`NearestOwnBasics` — docstring says "F-INV-1/2") | Geometry built |
| F-INV-3 | 1350 | No number shown — names + colour cue only | L238 | NONE | Matrix: "not built — assert rendered cell no numeric-score token" |
| F-INV-4 | 1355 | Click neighbour → catalog scrolls to row, pure navigation | L239 | NONE | Matrix: "not built — lands with catalog client-JS" |
| F-INV-5 | 1367 | Quick-only version → "full analysis only" (silent) | L240 | NONE | Matrix: "not built — lands with catalog render" |
| F-INV-6 | 1370 | Missing fingerprint axis: not listed, not offered as neighbour | L241 | `test_similarity_columns.py:92` (`LeansTowardCompleteness::test_missing_axes_track_is_not_comparable`) — covers the "not comparable" geometry that F-INV-6 depends on; also `test_completeness.py:59` (`TooFewSharedIsNotComparable`) via RC-INV-5a | Matrix: "geometry NOW; render not built". F-INV-6 is geometry-only tested, not surface-tested |
| F-INV-7 | 1372 | No other comparable track → "no comparison yet", not broken | L242 | `test_similarity_columns.py:129` (`NearestOwnRedIsLastResort::test_library_of_one_has_no_comparison`) — comment cites F-INV-7 | Geometry built |
| F-INV-8 | 1376 | Recompute on library/epoch change; cascade on deletes | L243 | NONE | Matrix: "not built — composes with placement + deposit/clean" |

---

## Table 3 — RC-INV-1..12 (§E run-completeness layer)

All RC-INV-1..12 (incl. sub-variants 5a, 5b, 7a) are present in TEST_MATRIX.md §E section (lines 194–208).

| id | SPEC line | gloss (6-10 words) | matrix row (line# or ABSENT) | test (file:line + name or NONE) | notes |
|---|---|---|---|---|---|
| RC-INV-1 | 1414 | Missing (None/NaN) ≠ measured-zero; never collapse | L194 | `test_completeness.py:22` (`MissingIsNotZero`) | ✓ built+tested |
| RC-INV-2 | 1419 | Run carries completeness manifest; read it, not a sentinel | L195 | `test_completeness.py:36` (`MissingIsNotZero` — sub-test on manifest key) | ✓ built+tested |
| RC-INV-3 | 1427 | Never impute missing → real value then show/compare | L196 | `test_completeness.py:41` (`CompareOverSharedAxesOnly`) | ✓ built+tested |
| RC-INV-4 | 1432 | Surface shows "not measured"; omits the card (no evidence) | L197 | NONE | Matrix: "not built — lands with per-facet/catalog render" |
| RC-INV-5 | 1437 | Compare over BOTH-present axes only; never 0/max gap | L198 | `test_completeness.py:41` (`CompareOverSharedAxesOnly`) | ✓ built+tested (same class as RC-INV-3) |
| RC-INV-5a | 1445 | < MIN_SHARED_AXES → "not comparable", never a fake 0 | L199 | `test_completeness.py:59` (`TooFewSharedIsNotComparable`) | ✓ built+tested |
| RC-INV-5b | 1451 | Rank directions by per-axis (RMS) distance, axis-count-fair | L200 | `test_completeness.py:76` (`RankingIsAxisCountFair`) | ✓ built+tested |
| RC-INV-6 | 1455 | Centroid averaged per-axis over members that have it; absent ≠ 0 | L201 | `test_completeness.py:100` (`CentroidSkipsMissingMembers`) | ✓ built+tested |
| RC-INV-7 | 1466 | Missing-by-mode = silent; missing-in-promised-surface = shown | L202 | NONE | Matrix: "not built — composes with view ladder INV-18/22" |
| RC-INV-7a | 1476 | Rung→promised-surface list is the single authority | L203 | NONE | Matrix: "not built — keys off §B.14/INV-18/22" |
| RC-INV-8 | 1470 | Same missing axis reads identically across coach/catalog/§D | L204 | NONE | Matrix: "not built — lands with manifest render" |
| RC-INV-9 | 1491 | Pick most-complete run; its run-id in content-hash | L205 | NONE | Matrix: "not built — lands with run selection + §D placement" |
| RC-INV-10 | 1507 | Gap → re-measure (flag), never impute; manual re-run | L206 | `test_completeness.py:152` (`PartialRunIsAnError`) | DISCREPANCY: matrix says "not built — re-measure command (backlog)" but `PartialRunIsAnError` tests the pure `is_partial_failure` / `incomplete_axes` logic. The UI surface (re-measure command) is not built; the pure logic IS tested. |
| RC-INV-11 | 1497 | Significance has third "unknown (not measured)" state | L207 | `test_completeness.py:174` (`SignificanceHasUnknown`) | ✓ built+tested |
| RC-INV-12 | 1481 | One per-run completeness line; absence ≠ all-clear | L208 | NONE | Matrix: "not built — lands with the coach render" |

---

## Summary

### (a) Invariants with NO matrix row

**D-INV namespace — 24 of 30 have no matrix row:**
D-INV-1 through D-INV-20 (all twenty), plus D-INV-27, D-INV-28, D-INV-29, D-INV-30.

The §D10F section of TEST_MATRIX.md covers only D-INV-21..26. The core §D.5 safety rules (D-INV-1..20) and the §D.10.1/D.10.2/D.10.3 rules (D-INV-27..30) are defined in SPEC.md but have no corresponding matrix rows.

**F-INV namespace — 0 absent:** All F-INV-1..8 have matrix rows (§D10F, lines 236–243).

**RC-INV namespace — 0 absent:** All RC-INV-1..12 (incl. 5a, 5b, 7a) have matrix rows (§E, lines 194–208).

---

### (b) Invariants with NO test

**D-INV:** No test for D-INV-1..20 (none cited by ID in any test file), D-INV-22, D-INV-23, D-INV-28, D-INV-29, D-INV-30.
- D-INV-21, D-INV-24, D-INV-25, D-INV-26, D-INV-27 each have at least one test that cites the ID.

**F-INV:** No test for F-INV-3, F-INV-4, F-INV-5, F-INV-8.
- F-INV-1, F-INV-2, F-INV-7 have tests that cite the ID.
- F-INV-6 has a geometry-level adjacent test (does not cite F-INV-6 by ID, but covers the underlying mechanism via `LeansTowardCompleteness` and `TooFewSharedIsNotComparable`).

**RC-INV:** No test for RC-INV-4, RC-INV-7, RC-INV-7a, RC-INV-8, RC-INV-9, RC-INV-12.
- RC-INV-10 has a test (`PartialRunIsAnError`) despite the matrix saying "not built" — see discrepancy note in Table 3.

---

### (c) D-INV-27..30 special check

| id | (a) matrix row? | (b) test covers it? | mis-mapped? |
|---|---|---|---|
| D-INV-27 | ABSENT | YES — `test_similarity_columns.py::TopKBasics::test_far_directions_excluded_never_in_result` (line 198) and `::test_all_equidistant_returns_empty` (line 209). Both cite `D-INV-27` and test the reference top-k selector function — NOT a per-stem or source-header test. | NO — correct test |
| D-INV-28 | ABSENT | NO TEST | n/a |
| D-INV-29 | ABSENT | NO TEST (by ID). `ReferenceReadRichLook` tests ★/☆ star mark logic — the substance of D-INV-29 — but never cites `D-INV-29` in any name/docstring/comment. | n/a |
| D-INV-30 | ABSENT | NO TEST (by ID). `ReferenceReadBars` tests the per-facet bar rendering — the substance of D-INV-30 — but never cites `D-INV-30` in any name/docstring/comment. | n/a |

No D-INV-27..30 test is mis-mapped to a non-reference (per-stem or source-header) feature. The bare `INV-27..30` namespace (in §Per-stem and §PLANNED sections of TEST_MATRIX.md) covers CandidateScore/Prominence/SourceFileSymmetry — entirely separate tests, none of which cite the `D-INV-` prefix.

---

*Audit written 2026-06-29. All findings are grounded by grep on the three source files; no claims made from memory.*
