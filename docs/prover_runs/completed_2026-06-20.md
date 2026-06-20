# product-prover — run on the COMPLETED TEST_MATRIX.md + diff vs baseline

_Run 2026-06-20 (session 12), AFTER the completeness pass (§2 data axis, §5 3D grid, §4b style layer,
§6 split, §7 cross-page grid, INV-19…22, bidirectional traceability). Compare against
`baseline_asis_2026-06-20.md` to judge whether completing the matrix was worth it._

TRIAGE: PROCEED.

## Opening assessment

The completeness pass closed the structural backbone of the baseline. The state space is now honestly
3-dimensional (§2 names stems/.als/web-mix; §5 carries a `data gate` column), the two historically
unmodeled axes — **cross-page** and **styling** — are now first-class (§7 invariant grid, §4b style
layer), and the headline principle (the ladder) is pinned as a property (INV-19) with an
artifact-grounded test, not just per-element. Six of the eight baseline findings are fully closed; one
is closed-with-a-caveat; one is downgraded to an open question. The doc moved from "needs another
iteration" to "ready to build against." The residual risk is small and mostly about keeping the new
machinery from drifting (the monotonicity test duplicates the §5 grid) plus one genuinely new gap the
deeper spec now makes visible: the stem-identity semantics (Demucs labels ≠ the real parts).

## Diff against baseline — finding by finding

- **F1 (grid is 2D, should be 3D) — CLOSED.** §2 adds the data axis; §5 gains a `data gate` column and
  splits the evidence/stem rows. The conditional rows that were prose ("need stems / need .als") are now
  enumerable cells.
- **F2 (empty-stem state unmodeled) — CLOSED.** §2 states `stems {none, present, empty}`; §5 adds the
  `empty-stem caveat` row gated on `stems=empty`.
- **F3 (cross-page is prose, untested) — CLOSED.** §7 is now a four-row invariant grid (X1–X4), each
  with an owning test; X1 is pinned by the new INV-20 + `CrossPageModeAgreement` (asserts word + colour
  on BOTH rendered surfaces).
- **F4 (no style layer) — CLOSED.** §4b models the CSS visibility contract; INV-22 +
  `test_view_ladder::CssGatingContract` assert it on the rendered stylesheet, including the junior's
  finding that there is **no `body.detailed` class** (Detailed = absence of `.simple`).
- **F5 (ladder monotonicity not a property) — CLOSED.** INV-19 + `LadderIsMonotonic` assert
  `quick ⊆ Simple ⊆ Detailed` over the whole element set; a new element that inverts the ladder now
  turns the suite red.
- **F6 (§6 collapsed six elements) — CLOSED.** §6 split into one row per element with its own data gate.
- **F7 (no placeholder-completeness invariant) — CLOSED.** INV-21 + `NoResidualPlaceholder` (widget +
  catalog) assert zero residual `__[A-Z_]+__` in both shipped surfaces.
- **F8 (one-directional traceability) — CLOSED.** All INV-1…22 audited by deed to have a real asserting
  test; owning tests now back-reference their `INV-N`; §8 records it; INV-2's owner named precisely.

Acknowledged-gap carryovers:
- **A1 (deferred option-b deposit==version integration test) — still open**, still parked on the
  fixtures decision. Unchanged.
- **A2 (stale "INV-1…13" text) — CLOSED.** §8 now reads INV-1…22.

## New findings the deeper spec makes visible

N1 — The monotonicity test duplicates the §5 grid instead of deriving from it

> "GRID = { … 'stemlanes': (0, 0, 1), 'recs(non-timecoded)': (0, 0, 1) … }" — `test_view_ladder::LadderIsMonotonic::test_grid_visibility_is_monotonic`

The property test hand-maintains a Python dict that mirrors §5's visibility. Two sources of the same
truth can drift: someone edits §5 but not the dict (or vice-versa), and the "monotonicity" guard then
checks a stale grid while the real §5 says something else. The other half of the test (CSS hide-sets on
the rendered HTML) is drift-proof; this half isn't.

Either (a) keep the dict but add a one-line note in §5 that the dict mirrors it and both move together
(cheap, matches the change protocol), or (b) later, parse the §5 markdown table into the grid so there
is ONE source. Prefer (a) now, (b) when the spec stops moving.

`should-clarify · over-specific (abstraction)`

N2 — Stem identity is unspecified: the spec never says the Demucs label may not be the real part

> "**stem** — a Demucs-separated instrument layer (drums/bass/other/vocals/guitar/piano)." — §1

The deeper data model now names stems everywhere, but nothing states that the LABEL is a source-model
approximation — for electronic material "vocals" is often a synth, "piano"/"guitar" some other synth,
and a stem can be `empty` / `nomatch`. A reader (or the per-stem recs work, NEXT_STEPS #2) could build
advice that says "the vocals are masked" when there are no vocals — confidently wrong. The mapping
machinery exists (`map_stems.py` → `result_stemmap.json` with clear/mixed/nomatch/empty), but the spec
doesn't make speaking-in-mapped-terms an invariant.

Add an invariant for the per-stem work: "Any stem surfaced to the producer is named by its mapped
project identity + confidence; empty/nomatch stems are dropped or caveated, never asserted as a part."
(Already captured as a hard requirement in NEXT_STEPS #2 + memory `track-coach-stem-labels`.)

`worth-considering · missing-rule (invariant)` — fire when #2 is built, not before.

N3 — Re-deposit of the same run: update path still unspecified (carried from baseline open question)

> "deposit — a copy of a run's widget into the library + an `index.json` entry" — §1

Depositing the same run twice (a re-render) — does it replace the entry or add a second? The grouping by
audio sha collapses versions in the catalog VIEW, but the index CRUD update path isn't stated. Low
operational impact today (deposits are infrequent, idempotent in practice), so not urgent.

State in §1/§8: "a deposit of an existing (src_run_dir) replaces that entry in place" (or documents the
collapse rule that makes duplicates harmless). `should-clarify · partial-success-risk (atomicity)`.

## Verdict — was completing the matrix worth it?

Yes, clearly. Baseline: 7 hidden findings (3 must-fix) + 1 acknowledged, overall "needs another
iteration." Completed: all 7 closed, the two must-fix axes (3D grid, styles) now modeled and tested,
+12 tests (154 → 166). The second run surfaces only 3 residuals — one hygiene note (N1), one genuinely
new and useful gap the richer model exposed (N2, the stem-identity rule, which maps straight onto the
deferred #2 work), and one low-impact carryover (N3). That's the signature of a spec that got more
complete: fewer structural holes, and the remaining findings are deeper and more specific rather than
"you forgot a whole axis." Net: the completeness pass converted broad structural risk into a short, named
residual list — worth it.

Overall readiness: **ready to build against.**
