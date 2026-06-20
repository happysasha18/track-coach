# product-prover — BASELINE run on TEST_MATRIX.md "as-is"

_Run 2026-06-20 (session 12), against `docs/TEST_MATRIX.md` at git `aac4298` (TC_VERSION 0.7.7,
18 invariants). This is the BEFORE artifact: re-run product-prover after the matrix is completed
(3D grid + cross-page grid + styles section + placeholder invariant) and diff the findings to judge
whether completing the matrix was worth it._

---

TRIAGE: PROCEED — this is a genuine spec + test matrix: entities, states/transitions, invariants,
two element grids, cross-page links, coverage status. Analyzable.

## Opening assessment

This is a strong, unusually disciplined doc — the spec and the test grid live in one file, every
invariant names an owning test, and there's an explicit bug→matrix→test→code protocol. The two best
things: (1) the invariant layer (§3) genuinely captures the cross-state rules a flat grid misses, and
it's honest about *why* each exists (KI references); (2) the state model (§2) correctly collapses
quick to a single state and names the three effective states F-S / F-D / Q. What needs attention is
**completeness of the grids**: §5 is two-dimensional (element × view) when the real state space is
three-dimensional (element × view × data-state), the cross-page correspondences in §7 are prose, not
enumerable cells, and there is no section at all for **styling correctness** — the exact axis the
project's history says keeps breaking (the Simple/Detailed CSS gating). Overall: ready to build from,
but NOT yet scrupulous enough to prevent silent quality regressions once features start changing —
which is precisely its stated job. Needs one more iteration on grid completeness.

## Phase 1 — The model

Entities (from §1): run, mode {full, quick}, view {simple, detailed} (full-only), surface {S1, S2},
scene/structure-bar, stem, web-mix, deposit.

States (§2): effective states **F-S**, **F-D**, **Q**; the model multiplies mode × view × .als-present
but only enumerates the view/mode product as effective states.

Transitions: toggle (S↔D, full only); navigate (S2→S1 title link; S2 in-place preview).

Actors: the producer (toggles view, clicks catalog links/preview); the skill/operator (runs analyze,
writes narrative, runs build/deposit); the deterministic pipeline (renders).

### What I assumed

- I read **data-state** as a first-class hidden parameter even though §2 only names `.als present`.
  The grids reference at least three more data-states inline — stems present / absent / **empty**
  (separation found nothing), and web-mix present/absent. I treated those as real states the model
  should enumerate, not passing remarks.
- I read "styling" as in scope (you asked), though the doc has no styles section; I inferred the CSS
  layer only from the `· CSS` tag on the `recs` row in §5.
- I treated the six Demucs stem kinds (drums/bass/other/vocals/guitar/piano) as a variable cardinality
  (4 or 6 by model) rather than a fixed 4, based on §1 + the htdemucs_6s mention elsewhere.

## Phase 2 — Structural issues

F1 — The element grid is 2D (element × view) but the state space is 3D (element × view × data-state)

> "## §5 — S1 widget: element grid (show? per state · how · layer)" with columns "F-S | F-D | Q" — §5

The visibility of half the rows actually depends on a data-state, not the view: `evidence` inner
panels need `.als` (arr/auto) or stems (map/rhythm/notes); `structure bar` leads "need stems (full)";
`recs` differ by stems. Those dependencies are written as inline prose ("need stems", "need .als"),
so they aren't enumerable cells and nothing forces a test per (element × data-state). A producer on a
quick run with no `.als` and an *empty* stem can hit a combination the grid never states, and a future
refactor that breaks one such cell turns no test red.

Add a data-state axis to §5: split each data-dependent row into its states, or add explicit columns
(stems ∅ / empty / present) × (.als ∅ / present). Minimum: every cell that today says "need stems / need
.als" becomes its own row with a show/hide value and an owning test.

`must-fix · over-general (abstraction)`

F2 — "Empty stem" is a distinct data-state the model never lists, though invariants depend on it

> "no audio ⇒ NO player (never an empty shell)" — §3 / INV-7; and "Stem(s) … are nearly empty" — string in build_widget

§2 enumerates `.als present {yes,no}` but not stem-state. Yet INV-7 (player), INV-16 (als panels),
the structure-bar leads, and the empty-stem warning all branch on stems being absent vs present vs
*empty* (separation returned near-silence). Three different states, collapsed to none in §2. The
operator reading §2 to enumerate test cases will miss the empty-stem column entirely — the exact class
that produced KI-1.

State the stem axis in §2: `stems {none (quick), present, empty}` and `.als {none, present}`, then
fold it into the §5 grid (F1).

`must-fix · missing-scenario (state-space)`

F3 — Cross-page correspondences (§7) are prose, not enumerable invariants, and mostly untested

> "mode badge (S1) ↔ mode pill (S2) same word+colour · title link opens the matching-badge widget · Track Story arc (S1) ↔ signature ribbon (S2) same source · S1 player ↔ S2 one-button preview (same mix)." — §7

These are four real invariants stated as one comma-run of prose. None carries an owning test in the
line. A drift where S2 shows "Quick" but the linked S1 says "Full" (e.g. a re-render changed mode but
the catalog entry wasn't refreshed) is exactly the kind of silent inconsistency a producer would hit
when scanning the catalog — and nothing here is checkable.

Promote §7 to a grid: one row per correspondence | S1 source | S2 source | rule | owning test |. At
minimum add an invariant "S2 mode pill word+colour == the linked S1 mode badge for the same run."

`must-fix · missing-rule (invariant)`

F4 — No styling/CSS layer in the spec, though it's a named layer and the historical break point

> "`recs` … quick filters via `body.quick`, Simple via `body.simple` · INV-3 · L-js + CSS" — §5 (the ONLY `CSS` mention)

The doc models L-py and L-js (§4) but never models the CSS layer, even though view gating is *implemented*
in CSS (`body.simple` / `body.quick` hide/show rules) and the project's own history (the recurring
Simple/Detailed regression) lives there. There's no enumeration of "for body-class X, which elements
must be display:none vs visible," so a CSS edit that re-hides the wrong element passes every test that
only checks the HTML/JS.

Add §4b "Style layer": a grid of (`body.simple` / `body.quick` / `body.detailed`) × element → expected
visibility, each backed by a test that asserts the *rendered CSS rule* (not just the element's presence).

`must-fix · missing-rule (invariant)`

F5 — The view ladder is asserted element-by-element; the monotonicity property itself is never stated as an invariant

> "Quick is the LADDER FLOOR … shows BRIEF recs … Evidence is always visible (INV-18)" — §3 / INV-3, and INV-18

The ladder `quick ⊆ Simple ⊆ Detailed` is the doc's headline principle, but it appears only as
per-element rules (INV-3 recs, INV-4 lanes, INV-18 evidence). There is no single invariant that says
"anything visible at a lower tier is visible at every higher tier," and no test that enforces it across
the *whole* element set. A future element added to Simple but forgotten in Detailed (or shown in quick
but hidden in Simple) re-creates exactly the inversion INV-3 just fixed — and no existing test would
catch a NEW element's inversion.

Add INV-19: "For every element E and tiers q ⊆ s ⊆ d: visible(E, lower) ⇒ visible(E, higher)." Back it
with a property test that walks the §5 grid rows and asserts no row is visible at a lower tier but
hidden at a higher one.

`must-fix · missing-rule (invariant)`

F6 — §6 collapses ~6 catalog elements into one grid row, hiding per-element coverage

> "spec cols / `mode` pill / `modeseg` filter / search / responsive / footer ver | ✓ | ✓ | INV-10 · catalog.py" — §6

Six distinct elements (the spec columns, the mode pill, the segment filter, the search box, responsive
shedding, the footer version) share one row and one owning reference. If search breaks but responsive
shedding is fine, the grid can't express that, and there's no per-element test obligation. An operator
debugging "search returns nothing" has no matrix cell to anchor on.

Split the row: one row per element with its own show/state/test. Keep INV-10 on responsive only.

`should-clarify · over-general (abstraction)`

F7 — Template placeholder substitution has no completeness invariant

> "**L-py** server template + substitutions (`__MODEBADGE__`, `__VIEWTOGGLE__`, `__READBODY__`, …)" — §4

The template ships with `__PLACEHOLDER__` tokens that L-py substitutes. Nothing states the invariant
"the rendered HTML contains zero residual `__…__` tokens." A new placeholder added to the template but
not wired in the Python emits a literal `__NEWTHING__` into the producer's widget — visible garbage,
caught by no test.

Add INV: "rendered S1/S2 HTML contains no residual `__[A-Z_]+__` placeholder." One regex test over a
real build output.

`should-clarify · missing-outcome-check (postcondition)`

### CRUD coverage (deposit / index entry as the managed entity)

| Entity | Create | Read | Update | Delete | Notes |
|---|---|---|---|---|---|
| run dir | covered (analyze) | covered (build) | partial (re-analyze inherits) | missing | no spec for pruning a run dir; only library `clean` covers deposited copies |
| index entry (deposit) | covered (INV-15) | covered (catalog render) | partial | covered (`clean`, INV not cited) | update path (re-deposit same run) not stated: does it replace or duplicate? |
| widget file | covered (build) | covered | covered (re-build) | partial (clean --missing) | — |

### Invariants per state

| State | Invariants stated | Invariants missing |
|---|---|---|
| F-S | INV-1,2,4,5,8-12,16,17,18 | ladder-monotonicity (F5), CSS-gating (F4) |
| F-D | INV-4,7 + above | ladder-monotonicity, CSS-gating |
| Q | INV-3,4,6,7,16,18 | empty-stem column (F2), no-placeholder (F7) |
| S2 catalog | INV-8,9,10,12,14,17 | cross-page correspondence as invariant (F3), per-element split (F6) |

## Phase 3.5 — Acknowledged gaps

A1 — Option-b deposit==version integration test is explicitly deferred

> "(Option b — an integration test that every deposit == `TC_VERSION` — is deferred to fixtures, Phase 5.)" — §8 / INV-12

Until that test exists, a deposit can store a stale `tc_version` and the only guard is the per-row stale
chip, which the operator might not notice. Worth doing when the fixtures decision (real vs synthetic)
lands.

`acknowledged · missing-outcome-check (postcondition)`

A2 — §8 coverage text is stale: claims "INV-1…INV-13"

> "Every invariant INV-1…INV-13 now has an owning test." — §8

The doc now defines INV-1…18; the closing line wasn't updated, so a reader trusting §8 believes
coverage stops at 13. Update to …18 and add the bidirectional tag (tests should reference their INV).

`acknowledged · hard-to-operate (ops-ux)`

## Phase 4 — Human / operational factors

F8 — Invariant↔test traceability is one-directional (matrix→test only)

The matrix names an owning test for each invariant, but the tests don't back-reference the invariant
(only 11 of 18 INV ids appear in the test files). An operator who breaks `StructureBarIsTidy` and reads
the failure has no pointer back to INV-5/6; and grepping `INV-7` finds the matrix but not its guard.

Add an `INV-N` reference in each owning test's docstring/name; verify by deed that each named owning
test exists and asserts its invariant (don't trust the matrix's paraphrase).

`should-clarify · hard-to-operate (ops-ux)`

## Phase 5 — Closing summary

### Top 3 to fix before development
1. **F1/F2** — make §5 three-dimensional (element × view × data-state incl. empty-stem); the grid
   can't currently express most of its own conditional rows.
2. **F4** — add a Style-layer grid (body-class × element → visibility, tested on rendered CSS); the
   historical regression lives here and is unmodeled.
3. **F5** — state ladder monotonicity as INV-19 + a property test over the whole grid, so a NEW
   element can't re-create the inversion.

### Properties to state explicitly (paste-ready)
- "For every element and tiers quick ⊆ Simple ⊆ Detailed: visible at a lower tier ⇒ visible at every
  higher tier."
- "The S2 catalog mode pill (word + colour) equals the mode badge of the S1 widget it links to, for the
  same run."
- "The rendered S1 and S2 HTML contain no residual `__PLACEHOLDER__` tokens."
- "Every data-dependent element states its visibility for stems ∈ {none, empty, present} and .als ∈
  {none, present}."

### Open questions (author only)
- Re-deposit of the same run: replace the existing index entry or version it? (CRUD update path.)
- Is the CSS visibility contract asserted on the rendered stylesheet, or is checking the element's
  computed state out of scope for unit tests (would need a DOM)? Affects how F4 is testable.

Overall readiness: **needs another iteration** — solid spine, but grid completeness (3D states,
cross-page, styles, ladder-as-property) must close before it can do its stated job of catching
regressions during feature work.
