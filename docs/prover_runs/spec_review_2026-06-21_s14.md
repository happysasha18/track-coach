# product-prover review — SPEC.md after the session-14 label overhaul (2026-06-21)

Run at the user's request (confirm with the prover that nothing breaks) after G16–G18 + the label-salad
cleanup. Consistency / no-regression check, not a greenfield review. Verdict: **needs another iteration
on the DOC** — code is green + deed-verified, but the spec drifted behind it. All findings below were
APPLIED the same session (see SPEC §B.4 banner, §B.7, new §B.8).

## Findings (applied)
- **F1 (must-fix, consistency)** — B.4 still presented `tonal`/`air`/`≈` as the current vocabulary → the
  exact "next session anchors on an old quote" regression. FIX: superseded-banner at top of B.4.
- **F2 (must-fix, missing-rule)** — G18 centroid freq-role (now the PRIMARY mechanism) was absent from §B;
  G14 high-pass still read as current. Violated bug→SPEC→test→code (code/tests/JOURNAL landed, spec didn't).
  FIX: added §B.8 (centroid role, supersedes G14-as-fallback, thresholds, deed, INV).
- **F3 (should-clarify, consistency)** — B.7's sub-line paragraph was 2 patches stale (still said raw name +
  `→ family`); 0.8.12/0.8.13 show the real project track name / near-silent / nothing. FIX: rewrote the bullet.
- **F4 (should-clarify, contradiction)** — B.4 "never by which instrument made it" vs B.7 trusting bass/drums
  Demucs identity. FIX: carved the low-end exception into B.4's sentence.
- **F5 (should-clarify, invariant)** — `bass` reachable as a base-role label for an UNTRUSTED low-centroid
  stem, but the INV listed base role as only mid/high. FIX: INV now enumerates the full label set + notes
  the two paths to `bass`; left OPEN (ask the user) whether untrusted-low should read `low` instead.
- **F6 (worth-considering, state-space)** — `noise` reachable but inert and not in the INV set. FIX: listed
  in the INV, marked inert.
- **F7 (worth-considering, cognitive-load)** — three naming hierarchies (late_entry / lane main / sub-line)
  uncross-referenced. FIX: added a "three surfaces on purpose" cross-ref to §B.6 in B.7.

## Still OPEN for the user
- F5: untrusted low-centroid stem → `bass` vs neutral `low`?
- Promote the real track-name from sub-line to PRIMARY label where `clear` + meaningful (drop the sub-line
  duplicate if so) — held, `clear` matches are noisy (drums→"7-Impulse").
