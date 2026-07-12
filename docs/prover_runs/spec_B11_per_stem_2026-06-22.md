# product-prover run — SPEC §B.11 "Per-stem measurements" (2026-06-22, session 16)

Focused review of the PROPOSED per-stem measurements design (SPEC §B.11 / CR-11) and matrix INV-23..26,
run before deriving tests (methodology: spec → prover → tests → code). Verdict: **needs another iteration**
— 3 must-fix design changes, then the tests.

## Must-fix

**F1 — the comparison baseline includes the thing being compared.** The mix curve is the sum of all
stems, so comparing a loud stem (bass/drums) to the full mix is partly comparing it to itself — dominant
stems under-report divergence, quiet stems over-report. The headline insight ("the bass runs opposite the
track") is the case this baseline suppresses. **Fix:** compare each stem to the REST of the track
(mix-minus-this-stem / other stems' aggregate), not the full mix. `abstraction`.

**F2 — validation measures divergence, but the goal is usefulness.** Divergence is a proxy; a stem can
diverge in a way that's true but uninteresting ("hat stereo wobbles 3%"). A divergence-share eval can
report "supported" while the cards are still noise — exactly what the user asked to rule out. **Fix:** one
human pass first — render the per-stem cards on the 3 library tracks, the user marks each useful/noise, set
an acceptance bar (⟨DECIDE⟩, e.g. ≥70% useful) BEFORE shipping. The automated divergence-share is the
cheap proxy tracked afterward, calibrated to that pass. `postcondition`.

**F3 — one stem can spawn many near-duplicate cards.** 6 measurements × several stems, and
energy/density/loudness move together — a divergent stem yields 3 cards saying one thing. Re-introduces the
clutter the feature avoids. **Fix:** ≤ N cards per stem; collapse correlated measures (energy/density/
loudness) into one naming the strongest. `invariant`.

## Should-clarify

**F4 — chronological sort undefined for timeless cards.** The a/b/c letters attach only to timecoded cards
(`build_widget.py:1999`); concept cards (swing, modulation) have no time, so their position under
chronological sort is non-deterministic and the list could reshuffle between builds. **Fix:** timeless
cards form a fixed trailing block in urgency order; timecoded sort by time with urgency as tiebreak.
`transitions`.

**F5 — per-measurement validity isn't gated.** Significance (loudness + time coverage) doesn't make a
SPECIFIC measurement meaningful — brightness of an all-sub bass, stereo of a mono stem, is junk that will
diverge for the wrong reason. **Fix:** per-measurement precondition (brightness only where the stem has
real high-freq energy; stereo only where not effectively mono); omit that card when unmet, same "don't
paint silence" as CR-1. `precondition`.

**F6 — old runs have no per-stem data; back-compat unstated.** Pre-B.11 runs lack `result_core_<stem>.json`.
**Fix:** state the fallback — missing file → no per-stem cards, no error (like pre-0.8.14 masking falls back
to the band range). `precondition`.

## Properties to add to the spec
- A per-stem feature is compared against the mix WITH THAT STEM REMOVED, never the full mix.
- At most N cards per stem; correlated measures (energy/density/loudness) collapse to one.
- Under chronological sort, timeless cards form a fixed trailing block ordered by urgency; equal times
  break ties by urgency.
- A missing `result_core_<stem>.json` yields no per-stem cards and no error.

## Open question for the user
The acceptance bar for F2: what share of per-stem cards must read as genuinely useful (the user's eye, 3
tracks) to call the hypothesis supported and keep the feature?
