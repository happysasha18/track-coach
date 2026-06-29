# product-prover run — §D reference layer (0.9 MINOR-gate, pass 1 of 3)

Date: 2026-06-29 (s28). Scope: whole-spec preventive-maintenance review, focused on the §D.10 reference
layer (D-INV-27 selector / D-INV-29 ★ plaque / D-INV-30 reference read) and its cross-section composition
with §F own-library column, §E completeness, and the view-ladder / catalog / run-mode axes.

Readiness verdict: **needs another small iteration before the 0.9.0 stamp** — geometry, completeness
discipline (§E), and §D↔§F composition are solid; blockers are scoping clarity + two interaction/state holes.
All "decide + write one sentence", none requiring rework.

## MUST-FIX
- **P2-1 (composition).** §D.10.1 mixes 0.9-buildable (descriptive leans-toward) with ⟨D-2⟩-gated
  aim-dependent rows (aim glyph, pinned-aimed entry, re-flavouring). Mark each row's scope; add a header line
  "aim-dependent rows are inert until the mapping input ⟨D-2⟩ exists." The 0.9 ship = descriptive only.
- **P2-2 (transitions).** Collapsed catalog cell "expands" by an unnamed gesture that collides with "every
  click = navigation". Pick a dedicated disclosure affordance (caret / "+2" chip), separate from name-links.

## SHOULD-CLARIFY
- **P2-3 (abstraction).** Per-entry colour cue has two definitions ("relative lean vs the field" vs "gap to
  the next"). Pin one — recommend gap-to-next-shown-entry, z-normed, same formula at every position.
- **P3-1 (consistency).** Column-presence (D-INV-22) conflates "has a leans-toward" with "has reference
  data"; a library where every track is "no close direction yet" is contradictory. Restate presence on
  "has a computed reference result (lean / no-close / can't-compare)".
- **P3-2 (state-space).** When no close direction + a pinned aimed-far direction, the collapsed cell reads
  "no close direction yet" and hides the aim — contradicts "intent is the useful thing". Show the pinned aim
  in the collapsed cell.
- **P3-3 (liveness/dead-end).** Read panel "falls back to nearest" on recompute assumes a nearest survives;
  if recompute empties the list while the panel is open there's none. Add: collapse to "no close direction
  yet" (drop tabs/bars, keep prose), re-stamp.
- **P3-4 (composition).** Switch CONTROL placement across views unstated (only the flag's globality is).
  Simple shows reference prose but maybe no toggle. Render the control wherever a reference surface renders.

## OPS / HUMAN
- **P4-1 (ops-ux).** Two numbering spaces INV-n (§B) and D-INV-n (§D) both reach 27–30; bare "INV-29" grep
  conflates the source-header invariant with the ★-plaque one (a verification pass this session did exactly
  that). In TEST_MATRIX always write the D- prefix; pin the new D-INV-27..30 rows to the REAL reference tests
  (test_similarity_columns / reference-read), not the per-stem ones.
- **P4-2 (cognitive-load).** Five near-synonymous empties (no close direction yet / full analysis only /
  can't compare / no comparison yet / absent column). Worth a once-only catalog-tail legend.

## ACKNOWLEDGED (carry past stamp with recommendations)
- ⟨D-2⟩ mapping/direction-authoring surface — load-bearing, undesigned; 0.9 ships descriptive-only.
- ⟨D-1⟩ cloud member threshold — pick + freeze (recommend ≥4).
- ⟨D-13⟩ switch default · ⟨D-25⟩ Simple chip · ⟨D-30⟩ contradicted-facet display · ⟨D-21⟩ note cap — tuning.

## PASTE-READY PROPERTIES (for spec-author to fold in)
1. "The reference column appears whenever ≥1 version has a computed reference result (a lean, 'no close
   direction yet', or 'can't compare'); it is absent only when no version has any reference computation."
2. "If a recompute leaves no direction clearing the lean bar while a reference read is open, the read
   collapses to 'no close direction yet' (tabs + per-facet bars removed, prose retained), re-stamped."
3. "The per-entry colour cue is the gap from that entry to the next-shown entry, z-normalised; same formula
   at every list position."
4. "When a track has a pinned aimed direction but no close lean, the collapsed catalog cell shows the pinned
   aim (red + aim glyph), not bare 'no close direction yet'."
