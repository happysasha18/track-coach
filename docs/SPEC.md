# track-coach — SPEC (prover-facing) — DRAFT, increment 1: the CREDIBILITY layer

_Session 12, 2026-06-20. This SPEC sits ALONGSIDE `TEST_MATRIX.md`. The matrix is the spec projected
into a checkable grid (UI/render invariants). This SPEC is the prose-first source: what the product IS,
why it exists, and — first — **what every number is allowed to claim**. Methodology (NEXT_STEPS 🪜):
write the SPEC → run `product-prover` on it → DERIVE the matrix/tests from it (spec-first, not
matrix-first). Language = WHAT-SASHA-SEES; internal ids are translated._

> **Status: DRAFT for Sasha's review.** Points needing his domain call are marked **⟨DECIDE⟩**. The SPEC
> encodes his corrections, so it is reviewed like code, not shipped silently.

## 0. Why the product exists (purpose)
track-coach reads a producer's track + Ableton project and tells them, in plain words, **what is
actually happening** in the music — the arc, the masking, the arrangement — so they can decide what to
change. Its whole value is **trust**: a true, specific reading they can act on.

**The current gap (Sasha, 2026-06-20):** "оно тикает и выдаёт похожие на правду СЛОВА, а копнёшь —
неубедительно." It produces plausible-sounding words that don't survive scrutiny. So **before** any
composition / coaching features, the numbers behind the words must be made defensible. This SPEC's first
job is that credibility layer.

## A. Entities (analysis layer)
- **audio feature** — a measured curve/scalar over the mix (energy, brightness, density, modulation,
  stereo width, tonal balance, vitals). Has a unit and a valid range.
- **stem** — a Demucs-separated layer. Carries a **significance** state and a **mapped identity**.
  - **significance (Sasha, 2026-06-20):** a stem is SIGNIFICANT iff it has enough information in BOTH
    axes — **loudness AND time**. Quiet-all-the-time, or one loud "писк" (transient) in silence, is NOT
    significant. So the gate is **temporal coverage** — the fraction of the track where the stem is above
    a dB floor (or its real onset activity over time) — not a single peak. (This corrects a peak-only
    test: e.g. a stem with median −76 dB but one −16 dB stab is NOT significant; one with steady onsets
    across the track IS, even if quiet.) States: `significant` / `insignificant (quiet/empty)`.
  - **mapped identity** + confidence (clear/mixed/nomatch/empty) from `map_stems`. The Demucs LABEL is
    an approximation, NOT the identity (Sasha makes electronic: "vocals" is a synth). See memory
    `track-coach-stem-labels`.
- **stem band energy** — per-stem energy in a frequency band. May be REAL or **leakage** (another
  stem bleeding in; `rhythm_quality` already measures pairwise leakage).
- **scene** — a named, lettered section of the track (Intro/Build/Drop/Breakdown/…). The NAME is a
  musical claim; the LETTER is a returns-pattern claim.
- **.als part** — a project track / group / return, with automation + clips.

## B. The credibility invariant + its consequences (PROPOSED spec)
**CR-1 (credibility invariant).** track-coach never presents, as fact, a number derived from invalid or
insufficient input. If the input for a claim is below a validity threshold, the claim is **omitted with
a one-line note**, not rendered as if real. "Don't cry wolf, and don't paint silence."

Concrete consequences (each a finding observed on Lazy_Sparks, evidence by deed; each becomes a derived
matrix cell + test once Sasha confirms the ⟨DECIDE⟩ points):

- **CR-2 — empty stems are omitted, not parsed.** A stem whose broadband level is below the floor is
  dropped from analysis: no notes / rhythm / masking / per-stem viz are computed for it (saves compute),
  and the widget shows "stems X, Y omitted — too little material to read." Evidence: Lazy_Sparks vocals
  −92 dB (peak −61), piano −88 dB (peak −42) — silent, yet currently shown. ⟨DECIDE⟩ floor value: code
  already uses **−55 dB** broadband for the "empty" caveat (`build_widget.py:900`) — reuse that, or set
  a dedicated "don't-parse" floor (e.g. peak < −45 dB)?

- **CR-3 — per-stem visuals are gated on ABSOLUTE level, not per-stem normalization.** A silent stem
  must render as empty, never full-colour. Evidence: vocals sits at −92 dB yet its loudest band
  normalizes to full colour → looks like content. ⟨DECIDE⟩ the dB at which a band reads as "present" on
  the strip (e.g. −60 dB absolute floor for any colour).

- **CR-4 — bled energy is not attributed to the wrong stem.** Where a stem's band energy is dominated by
  measured leakage from another stem, it is caveated or not shown as that stem's content. Evidence:
  guitar low −40 dB > its own mid −46 dB; bass low is −26 dB (~14 dB louder) and bass↔guitar leakage =
  0.24 → the guitar's "low/red" is bass bleed. ⟨DECIDE⟩ when to suppress vs caveat (e.g. if a band is
  within N dB of a higher-leakage neighbour's same band).

- **CR-5 — scene names are MUSICAL (read from curve DYNAMICS), not relative-loudness.**
  **Definition (pinned 2026-06-20 — standard EDM term, written down for precision):** a **Drop** is the
  high-energy RELEASE that enters right after a build/breakdown — energy goes UP ("the bass drops IN",
  not down). The dip/tension before it (the "яма перед поднятием") is the **Build/Breakdown**. So a
  Drop is **defined by the contrast**: a lower section immediately precedes a top-band section. Without a
  preceding dip/build it is not a Drop — just a loud section.
  Today's bug: `build_widget.py:769` calls any section ≥0.8 of peak a Drop (`tier = ti / mx`, relative),
  ignoring the required preceding яма → a continuously-loud track reads as "весь из дропов." The signal
  lives in the **shape** of the curve (fall/build → sharp return + family entrance + density jump), read
  **in aggregate** — the hard call belongs to the interpretation layer (the LLM reading the real curves),
  NOT a hand-coded threshold; guarded by the necessary-condition tests in §D. Prefer labelling the
  **pair** "Build/Breakdown → Drop" as a unit rather than scattering "Drop". Numbering must be gap-free
  (today names are set before `_coalesce_scenes` merges → "Drop, Drop 3, Drop 5"). ⟨DECIDE⟩ the Δ and the
  name for sustained-high non-lift sections ("Main"/"Peak"/letter only)?
  **Dig on Lazy_Sparks (by deed, 2026-06-20) — two more findings:**
  - **CR-5a: structure SOURCE is wrong.** The story bar uses `core.section_bounds_s` (agglomerative, ≤8)
    and flattened 170–337 s into ONE "Drop 3" (167 s), swallowing what self-similarity correctly sees as
    `C E C E C` (the main section C returns 4×, two E breakdowns between) — so it "didn't find
    everything." Accurate structure source = the **self-sim segmentation** (`result_selfsim.json`, 11
    segments: `A B C D C E C E C F A`), not the coarse section_bounds. Build scenes from self-sim.
  - **CR-5b: energy alone misses breakdowns.** An energy-dip→rise detector found ZERO transitions here —
    the E "ямы" are timbral/density shifts, not energy valleys (self-sim/MFCC catches them, energy
    doesn't). Confirms the call must be **aggregate** (self-sim boundary + energy + density + family
    entrance), per "смотреть на данные в совокупности".

- **CR-6 — repetition is read on the significant stems too.** Self-similarity / returns are computed on
  the non-empty stems, not only the mix, so "this part returns" is grounded in real recurring material.
  (Today: mix-level only.) ⟨DECIDE⟩ which stems count as "significant" (drums+bass+the loudest melodic?).

- **CR-7 — Ableton↔stem correspondence is stated only where defensible.** Map at group/track level where
  the correlation is strong; stay silent / caveat where it isn't. (Base exists: `map_stems`.) Hard —
  flagged for design, not a hard promise yet.

### B.1 Phase-2 resolutions (folded back from `prover_runs/spec_credibility_2026-06-20.md`)
- **CR-1a (from P2):** mix-level claims (energy/brightness/density/vitals/arc) are INDEPENDENT of stem
  significance — an all-insignificant-stems run still gives the full arc; only the stem layer is omitted.
- **CR-2a (from P1):** significance is **per-scene**, not whole-track — a stem that carries only the drop
  is significant THERE. "Omit + don't parse" applies only to a stem insignificant in EVERY scene.
- **CR-4a (from P3):** leakage honesty is windowed (bleed varies over time) — caveat rather than globally
  suppress.
- **CR-5c (from P4/P5):** using the self-sim segmentation requires it be stable (enough distinct
  material across `k`); fall back to a coarser bar otherwise. A RETURN to a prior high level after a dip
  (…C E C…) IS a drop — don't require a new global peak.
Open ⟨DECIDE⟩ thresholds remain tuning, to settle on fixtures.

### B.2 Phase-3 resolutions (0.8.1, 2026-06-21 — coded + tested, `tests/test_credibility.py` G1–G7)
RESOLVED in code (guard in parens): **CR-2/CR-7** insignificant stems dropped + named (G1), gate =
`significant_stems()` at **−55 dB** (`STEM_EMPTY_FLOOR_DB`); **CR-1a** mix arc survives all-insignificant
(G2); **CR-3** per-stem viz scales vs an absolute **−60 dB** floor (`STEM_COLOUR_FLOOR_DB`), not per-stem
max (G3); **CR-5a** scenes follow self-sim when stable (≥3 segs, ≥2 labels; G4); **CR-5** Drop requires a
strictly-lower predecessor (`LIFT`=**0.12** tier), sustained-high = **"Main"**, numbered after coalesce
(G5/G6). ⟨DECIDE⟩ now settled: empty floor −55, colour floor −60, LIFT 0.12, sustained-high name = "Main".
Derived correction to the prover's G5: a strict "⅓ Drop cap" is **too strict** (an honest alternating
build→drop track is ~½ Drops); the real necessary condition is **≤ ½** (every Drop needs a non-Drop dip
before it) — encoded that + a positive "real drops still detected" test instead.
STILL OPEN (not in the G1–G7 layer-1 set): **CR-4** leakage honesty (windowed caveat), **CR-6** the actual
per-stem self-sim computation (the gate exists; the analysis doesn't yet), **CR-7** Ableton↔stem.

### B.3 Phase-3 cont. (0.8.2, 2026-06-21 — CR-4/CR-6/CR-7, guards G9–G11)
- **CR-4 (G9) DONE:** `leakage_caveats()` flags a SIGNIFICANT stem's single loudest band as likely bleed
  when a carrier owns that band ≥ `LEAK_LOUDER_DB` (10) louder AND r ≥ `LEAK_CORR_MIN` (0.2). Conservative
  + identity-agnostic (a naive "any louder neighbour" rule over-flags); rendered in the separation panel.
  Layer-1 uses per-band MEDIANS, not windows — CR-4a's time-windowing is a later refinement.
- **CR-7 (G10) DONE (as a lock):** the map panel already states a project family only on a `clear` verdict
  (only `map_clear` carries `{fam}`); G10 prevents a non-clear verdict from ever naming one. No new UI.
- **CR-6 (G11) COMPUTED, SURFACING OPEN:** `stem_repetition()` reads each significant stem's own self-sim
  (recurrence 0..1), gated by `significant_stems()`; the pipeline writes `result_selfsim_<stem>.json` for
  significant stems and build_widget auto-discovers them. Worded surfacing deferred — it must use
  stem→real-name mapping (never raw Demucs labels) and is Sasha's design call.

### B.4 Stem CHARACTER labels (0.8.3 → 0.8.6, 2026-06-21 — G12, G13)
Raw Demucs labels (`vocals`/`guitar`/…) are wrong for electronic music ([[track-coach-stem-labels]]): Sasha
makes synths, not a band. So we name a SIGNIFICANT stem by what its SOUND measurably IS — never by which
instrument made it — and the label must be DETERMINISTIC (same track → same label every run; no per-run
renaming) and gated to `significant_stems()`. Same credibility family as CR-1: a label is a claim, so it
must be backed by a measurement, marked `approx` (shown `≈`) when the measurement is indicative not certain.

- **G12 (0.8.3) — the two coarse axes.** freq-role (which third of the spectrum carries the energy,
  EXCLUDING CR-4-bled bands) × percussive-vs-sustained (`onset_rate ≥ ONSET_PERCUSSIVE`). Gives:
  low·perc=`kick`, low·sus=`bass` (both `clear` — Sasha confirmed we read the low end reliably), mid·perc=
  `perc`, high·perc=`hats`, high·sus=`air`. mid·sustained was the honest umbrella **`tonal`** (`approx`) —
  it DELIBERATELY did not claim melody-vs-pad, because freq+onset can't split those.

- **G13 (0.8.6, THIS pass) — split the `tonal` umbrella into 5 measured buckets** (Sasha's call,
  2026-06-21: he wants to tell a chord from a melody, and it IS measurable — polyphony). Only the mid·sustained
  (old `tonal`) case is refined; every other G12 label is unchanged. Two new MEASURES per significant stem:
  1. **polyphony** — run `basic-pitch` (`transcribe.py`) on each significant non-drum stem →
     `result_notes_<stem>.json`; `poly_frac` = fraction of the stem's SOUNDING time during which ≥2 notes
     overlap (interval sweep; deterministic). mono = `poly_frac < POLY_FRAC_MONO_MAX`.
  2. **per-stem spectral flatness** — `masking.py` computes an energy-weighted mean
     `librosa.feature.spectral_flatness` per stem (audio already in RAM; one number, no extra audio pass).
     High flatness = broadband/noisy = no clear pitch.
  Decision (only on a mid·sustained stem):
  - flatness ≥ `FLATNESS_NOISE_MIN` → **`noise/air`** (broadband, no pitch to call melody vs chord).
  - else MONO (`poly_frac < POLY_FRAC_MONO_MAX`): the loudest mono-tonal stem (within `LEAD_MARGIN_DB`
    of the loudest) → **`lead`**, the quieter ones → **`melody`**. _This loudness split is the WEAKEST
    of the five (relative loudness, not a content measure) — Sasha was shown this when he chose 5 buckets;
    it stays `approx` and the JOURNAL flags it for tuning._
  - else POLY: envelope CONTINUITY (`masking.sustain`) ≥ `PAD_SUSTAIN_MIN` → **`pad`** (a held drone),
    else → **`chord`** (rhythmic stabs). `sustain` = sounding-frames ÷ frames-in-active-span (a drone-pad
    reads ~0.88, a chord/arp ~0.49 on real stems). Was mean note duration — that NEVER fired because
    basic-pitch fragments held synths into ~0.2 s notes; the envelope holds up where note length didn't.
  - **fallback:** a mid·sustained stem with NO transcribed notes (basic-pitch found nothing, or transcribe
    was skipped) keeps the honest **`tonal`** umbrella — we never invent a melody/chord verdict from
    missing data (CR-1). All five new labels are `approx`.
  - **NO vocabulary / NO ML text-prompts** — Sasha explicitly rejected defining prompt vocabularies
    (he called that "a bit dumb"). Every bucket is a deterministic threshold on a measured quantity.
  - ⟨DECIDE⟩ thresholds (tune as more tracks land): `POLY_FRAC_MONO_MAX`=0.20, `PAD_SUSTAIN_MIN`=0.7.
    `lead` = the single loudest mono line (exclusive; no margin).
  - **VERIFY-BY-DEED (2026-06-21, real Fragile stems) — status of the 5 buckets:**
    - `melody`/`lead`/`chord` (polyphony + exclusive-loudest lead): WORKING. Fragile → vocals `melody`,
      guitar `lead`, other `chord`. (Earlier dual-lead from a loudness margin was fixed → single lead.)
    - `pad`: now via envelope `sustain` (≥0.7), NOT note length. Mechanism validated on real values
      (drone-pad piano 0.88 vs chord/arp other 0.49); fires only on a genuinely held poly stem — on
      Fragile nothing significant sustains that high, so pad correctly doesn't appear. Pad CASE still
      wants a track with a significant held pad to confirm by deed (calibration backlog).
    - `noise`: STILL DEFERRED. Real energy-weighted flatness on harmonic stems is 0.000–0.003, so
      `FLATNESS_NOISE_MIN`=0.30 never fires; can't enable a noise label without a track that has a real
      noise/riser stem to verify against. Kept inert (never a wrong label) until such a test track exists.

- **G14 (0.8.6, THIS pass) — robust freq-ROLE via a HIGH-PASS drop (Sasha's idea, 2026-06-21).** G12 typed
  the role from the loudest band-group, which broke on real intermittent stems two different ways (found by
  deed): typing by per-band **median** makes a bass that only hits some beats read as ~silence in every band
  (its role becomes noise → it got mislabeled mid/"melody"); typing by **loud-level** (85th pct) instead
  picks up a guitar's loud kick-BLEED in the low and mislabels the guitar "bass" (the exact CR-4 failure).
  Sasha's fix sidesteps the bleed argument entirely: **high-pass the stem (ignore `sub`+`low`) and ask how
  much energy it LOSES.** A genuine low/bass stem loses almost everything; a mid stem with bled low keeps
  its real mid content.
  - measure (no extra audio pass — reuse the per-band loud-levels): `hp_drop` = full loud-level −
    high-passed loud-level (combining `low_mid`+`mid`+`hi_mid`+`air`).
  - rule: a SUSTAINED stem with `hp_drop ≥ HP_DROP_DB` → **`bass`** (low carrier); otherwise it's a mid/high
    part (→ G13 split, or `air` if its surviving energy sits in `hi_mid`+`air`). Percussive stems keep the
    G12 onset path (kick/perc/hats).
  - Use the **relative drop, NOT an absolute residue floor** — verify-by-deed track 2: a loud bass dropped
    27 dB yet its residue (−42.6) was still above the −55 empty-floor, so a floor rule would have missed it.
    The drop self-normalizes: bass dropped 22–27 dB on both tracks; every non-bass stem 0–8 dB.
  - **Leaves CR-4 `leakage_caveats` UNTOUCHED** — role no longer depends on it (it stays only for the
    separation-panel UI). ⟨DECIDE⟩ default `HP_DROP_DB`=15 (clean gap between 8 and 22 on the two tracks).

## C. What I need from Sasha to derive the matrix + tests
The ⟨DECIDE⟩ points above — especially: (1) the dB floor(s) for "empty / don't-parse" and "no colour";
(2) the musical definition of **Drop** (and the name for sustained-loud non-lifts); (3) which stems are
"significant" for repetition. With those, I run product-prover on this SPEC, then derive the §-grids +
tests, then fix the code (bug → spec → test → code).

## Glossary (plain-language definitions; expand it whenever a term needed explaining)
- **red on the band strip** = high energy shown on the per-stem band strip.
- **drop** = a `Drop`-named scene.
- **empty stem** = a stem below the validity floor (near-silent; omitted from per-stem analysis).
- **Demucs label vs identity** = the raw Demucs stem name (`vocals`/`guitar`/…) is NOT the real
  instrument — Sasha makes electronic music, so a `vocals` stem is usually a synth. We label by measured
  character, never by the raw name.
- **bleed** (2026-06-21) = leakage BETWEEN stems. Demucs separation isn't perfect, so a loud part still
  shows up faintly inside another stem's file — e.g. the kick bleeds into the `guitar` stem's low band.
  It is NOT audio clipping / "going over the edge"; the levels are small (often only a few dB of a band).
  Why it matters: a stem can look like it lives in a frequency range that isn't really its own. CR-4
  (`leakage_caveats`) flags it for the UI; G14 sidesteps it for the freq-role via a high-pass.
- **high-pass** = ignore the bottom frequencies (sub+low) and look at what's left. We don't filter audio —
  we already have per-band energy, so "high-pass" = "don't count the bottom bands". Used by G14 to ask
  "is this really a bass?" by how much loudness vanishes when the bottom is dropped.
- **polyphony** = how many notes sound at once. ~1 at a time = a melody/lead (monophonic); stacked =
  chords/pad (polyphonic). Measured from the transcribed notes (basic-pitch).
