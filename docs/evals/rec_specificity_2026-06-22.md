# Rec specificity eval — template vs per-stem (NEXT_STEPS #2)

**Date:** 2026-06-22 (session 15). **Tool:** `scripts/eval_rec_specificity.py` (reproducible).
**Hypothesis (Sasha, NEXT_STEPS #2):** per-stem-derived recommendations are more INDIVIDUAL than the old
fixed-template catalogue — fewer generic cards, more cards that name a specific part / time / frequency.

**Method.** On each track's REAL analysis, build the recommendations twice on the *same* data:
- **template** path — `character=None, repetition=None` (old generic catalogue);
- **per-stem** path — `character` + `repetition` computed (G16 named masking, G19 precise freq, G20 dev-vs-loop).

Then count: **total** cards · **named** (text contains a measured part label) · **timed** (anchored to a
timeline moment) · **freq** (names a precise "≈… Hz"). Masking regenerated with the 0.8.14 per-stem
spectrum so the freq metric is live on all three.

## Results

| track | path | total | named | timed | freq |
|---|---|---:|---:|---:|---:|
| Lazy_Sparks | template | 2 | 2 | 1 | 0 |
| Lazy_Sparks | **per-stem** | **5** | **5** | **4** | **3** |
| Shared_Memories | template | 2 | 2 | 1 | 0 |
| Shared_Memories | **per-stem** | **4** | **4** | **4** | **3** |
| Wobble_Drift | template | 3 | 3 | 2 | 0 |
| Wobble_Drift | **per-stem** | **4** | **4** | **4** | **2** |
| **AGGREGATE** | template | 7 | 7 | 4 | 0 |
| **AGGREGATE** | **per-stem** | **13** | **13** | **12** | **8** |

## Read

- **Verdict: hypothesis SUPPORTED.** Per-stem nearly DOUBLES the cards (7→13), TRIPLES the timecoded ones
  (4→12), and adds **8 precise cut frequencies** where the template had zero. The arrangement advice goes
  from "carve a 250–600 Hz dip in the bass" (same line every track) to "Notch the bass around ≈270 Hz at
  1:18 / ≈340 Hz / ≈510 Hz" + "the bass carries the development while the mid and drums loop".
- **Caveat on the `named` metric** (honest): it saturates — it reads 100% on BOTH paths because the
  template's generic masking line *"bass covers other in X% of spots"* also contains the word "bass". So
  `named` does NOT discriminate here; the real specificity signal is **timed (4→12)** and **freq (0→8)**,
  plus total card count. A sharper future metric = count DISTINCT parts named, or named-excluding-generic.
- **Scope.** All three deposited library tracks. Per-stem self-similarity (the G20 development card) exists
  only for Lazy_Sparks (recent pipeline step); the other two contribute G16/G19 cards only — so the true
  per-stem advantage is if anything UNDER-counted on two of the three tracks.

**Conclusion:** keep investing in per-stem recs — they measurably individualise the advice. Next lever
(NEXT_STEPS): finer-than-32-bin spectrum for even tighter cut frequencies; name parts in breakdown/swing too.
