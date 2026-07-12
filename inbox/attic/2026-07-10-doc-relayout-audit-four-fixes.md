# Audit of the s63 doc re-layout — APPROVE-with-fixes (four findings)

Source: read-only audit from the live-spec window, 2026-07-10 ~15:00, on the owner's word
(the specs are ready, audit them). Auditor: a fresh opus reviewer under the product-prover method,
over SPEC.md + ARCHITECTURE.md + TEST_MATRIX.md at commit c858766.

Both fixes from the previous audit LANDED and are verified: the four D.10.x heading tails are
clean (SPEC.md:1344/1470/1622/1781), the journal chapter for the re-layout session stands
(JOURNAL.md:3309) with its commit at HEAD. The re-layout itself carried no regressions: every
Contents anchor in SPEC and TEST_MATRIX resolves, no dropped sections, no broken intra-doc
links, the line multiset preserved. Push still HELD per the standing gate (his word only).

## The four findings, by severity

1. **Must-fix — duplicate `### G.4` heading.** SPEC.md:2076 ("One-off cleanup of pre-marker
   references") and SPEC.md:2199 ("How it composes") both carry the number G.4; the §G run is
   G.0 · G.4 · G.1 · G.2 · G.3 · G.4 · G.5. An ambiguous number in a doc whose anchors are
   machine handles. Predates the re-layout (present in parent d93df77) — the re-layout only
   reordered that neighbourhood without catching it. Fix: renumber the misplaced block to G.6
   after G.5.

2. **Should-clarify — ARCHITECTURE cites matrix-only sections as SPEC facts.** N7 cites
   §A-metre, N12 cites §4/§5, N20 cites §6/§D10F (ARCHITECTURE.md:68/94/116) — those sections
   exist only in TEST_MATRIX, not in SPEC. Every node's spec-fact column should point at a real
   SPEC clause.

3. **Should-clarify — dangling invariant ids.** D-INV-32/33/34 (SPEC.md:1280) and D-INV-36b
   (SPEC.md:1568) are referenced but never defined; both sit in removed/deferred aim-picker
   context, and the traceability regex silently masks them. Drop them or annotate as tombstones.

4. **Worth-considering — §C Contents label drift.** The Contents entry says "domain calls
   (resolved)" while the heading reads "(RESOLVED) … inputs that needed … domain call"; the
   anchor still resolves, cosmetic only.

Verdict: ready to push (when his word comes) after findings 1–2; 3–4 can ride the same edit.
