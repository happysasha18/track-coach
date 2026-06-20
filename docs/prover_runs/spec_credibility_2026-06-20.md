# product-prover on docs/SPEC.md (credibility layer) — Phase 2 of #4

_Session 12, 2026-06-20. Stress-tests the SPEC draft (not the matrix). Output = holes in the
credibility spec + the DERIVED guardrail-test list for Phase 3 (bug→spec→test→code). This is the flip
Sasha asked for: spec-first → prover → derive tests._

TRIAGE: PROCEED — a genuine spec with entities, an invariant (CR-1), and consequences (CR-2…7).

## Opening assessment
Strong spine: one credibility invariant (CR-1) with concrete, evidence-backed consequences, and an
honest testing model (§D: deterministic necessary-conditions + expert-labeled golden fixtures + judgment
in the interpretation layer). The gaps are mostly about **time**: significance, leakage, and "drop"
contrast are specified globally but the track is sectional — a stem/relationship can be valid in one
section and not another. Resolve the time-locality of the three gates and this is ready to derive tests
from.

## Findings

P1 — Significance is global; it should be per-section
> "a stem is SIGNIFICANT iff it has enough information in BOTH axes — loudness AND time" — §A/stem
A stem can carry the whole drop and be silent elsewhere (a topline that only plays the C sections). A
whole-track significance gate would mark it borderline and risk dropping real, section-local material.
Make significance **per-scene** (significant-in-section S), and "omit" applies only where it's insignificant
everywhere. `should-clarify · over-general (abstraction)`

P2 — All-insignificant-stems run has no stated floor of what we CAN still say
> "below a validity threshold, the claim is omitted with a one-line note" — CR-1
If every stem is insignificant (quiet/ambient track, or a poor separation), CR-1 omits the whole stem
layer — but the mix-level arc (energy/brightness/density/vitals) doesn't depend on stems and must
survive. State it: **mix-level claims are independent of stem significance.** `must-fix · missing-rule (invariant)`

P3 — Leakage honesty (CR-4) is time-blind
> "Where a stem's band energy is dominated by measured leakage … it is caveated" — CR-4
Leakage is one global pairwise number, but bleed varies over time (bass bin the drop, gone in the
breakdown). Suppressing "guitar low" globally could hide real guitar low where the bass is absent. Make
the leakage check **windowed**, or caveat rather than suppress. `should-clarify · missing-scenario (state-space)`

P4 — CR-5a leans on self-sim but doesn't state self-sim's own validity
> "Accurate structure source = the self-sim segmentation" — CR-5a
Self-sim's `k` (cluster count) is a parameter; a quiet/uniform track can over- or under-segment. The
spec adopts self-sim as truth without saying when self-sim itself is trustworthy (enough distinct
material, stable across k). Add a precondition for using the self-sim segmentation; fall back to a
coarser bar when it's unstable. `should-clarify · missing-prerequisite (precondition)`

P5 — "Drop = lower section immediately precedes it" needs the return case spelled out
> "a lower section immediately precedes a top-band section" — CR-5
A main section C that RETURNS after a breakdown E (…C E C…) — the second C follows E (lower), so it
qualifies as a drop. Good, but state explicitly that a RETURN to a prior high level after a dip is a
drop (the Lazy_Sparks case: C returns 4×, each after D/E). Otherwise an implementer might require a NEW
peak. `should-clarify · undefined-path (transitions)`

P6 — Golden fixtures (§D layer 2) are a hard dependency that doesn't exist yet
> "Expert-labeled golden fixtures … a handful of Sasha's real tracks where HE marks the truth" — §D
Layer-2 (precision/recall on the judgment) can't run until Sasha labels tracks. So Phase 3 ships **layer-1
guardrails now**; layer-2 is blocked on fixtures. Make that explicit so the judgment quality isn't
assumed-tested by the guardrails alone. `acknowledged · stuck-state (liveness)`

P7 — Omission must be observable (which stems, why)
> "omitted with a one-line note" — CR-1
A panel that just disappears confuses the producer. The note must NAME the omitted stems and the reason
("vocals, piano — too little material"), so a missing panel reads as a decision, not a bug.
`should-clarify · hard-to-monitor (observability)`

## DERIVED guardrail tests (Phase 3, layer-1 — codeable now, no expert labels)
Necessary conditions; they don't pin the musical verdict, only what can NEVER be true.

- **G1 (CR-2/CR-7):** an insignificant stem produces NO per-stem output (no notes/rhythm/masking/viz),
  and the widget carries an "omitted: <names> — too little material" note that names them (P7).
- **G2 (CR-1/P2):** the mix-level arc (energy/brightness/density/vitals) is present even when ALL stems
  are insignificant.
- **G3 (CR-3):** no per-stem colour/band is rendered for a stem below the absolute-dB floor (a silent
  stem renders empty, not full-colour).
- **G4 (CR-5a):** scene boundaries derive from the self-sim segmentation (align to its segments), not the
  coarse `section_bounds_s`; on the Lazy_Sparks fixture the middle is NOT one 167 s blob.
- **G5 (CR-5):** every scene named "Drop" is immediately preceded by a lower-intensity scene; and not
  more than ~⅓ of scenes are Drops (catches "весь из дропов").
- **G6 (CR-5):** scene names ∈ the allowed vocabulary; Drop numbering is contiguous (no gap like
  "Drop, Drop 3").
- **G7 (CR-6):** per-stem self-similarity runs only on significant stems.

Layer-2 (later, needs Sasha's labels): precision/recall of drops/breakdowns vs his marks, with tolerance.

## Closing
Top 3 to resolve before coding: **P2** (mix survives all-insignificant stems), **P1** (per-section
significance), **P4** (self-sim validity precondition). Then G1–G7 are directly codeable. Readiness:
**ready to derive Phase-3 tests** once P1/P2/P4 are folded into the SPEC.
