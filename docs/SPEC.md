# track-coach — SPEC (prover-facing). Scope: the CREDIBILITY layer (§A–§B.11) + the ARTISTIC layer (§B.12–§B.14) + the REFERENCE layer (§D, 0.9 DRAFT)

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

**The current gap (Sasha, 2026-06-20):** "it ticks along and produces plausible-sounding WORDS, but the moment you dig in — it falls apart." It produces plausible-sounding words that don't survive scrutiny. So **before** any
composition / coaching features, the numbers behind the words must be made defensible. This SPEC's first
job is that credibility layer.

## A. Entities (analysis layer)
- **audio feature** — a measured curve/scalar over the mix (energy, brightness, density, modulation,
  stereo width, tonal balance, vitals). Has a unit and a valid range.
- **stem** — a Demucs-separated layer. Carries a **significance** state and a **mapped identity**.
  - **significance (Sasha, 2026-06-20):** a stem is SIGNIFICANT iff it has enough information in BOTH
    axes — **loudness AND time**. Quiet-all-the-time, or one loud "blip" (transient) in silence, is NOT
    significant. So the gate is **temporal coverage** — the fraction of the track where the stem is above
    a dB floor (or its real onset activity over time) — not a single peak. (This corrects a peak-only
    test: e.g. a stem with median −76 dB but one −16 dB stab is NOT significant; one with steady onsets
    across the track IS, even if quiet.) States: `significant` / `insignificant (quiet/empty)`.
    - **KNOWN DEBT (2026-06-23, Sasha's call — leave the code, record the gap).** The SHIPPED gate
      (`significant_stems`, `build_widget.py`) is level-only: `loud_level` (85th-pct broadband) ≥
      `STEM_EMPTY_FLOOR_DB` (−55). The 85th-pct rejects a single stab (good), but the **onset-activity /
      temporal axis above is NOT implemented** — a quiet-but-steady stem (e.g. a −58 dB perc loop ticking
      the whole track) is dropped as "empty" though this definition says it is significant. No real track
      has hit this yet, so the fix is deferred (like CR-4a). When a track exposes it, add an OR-branch:
      significant if `loud_level ≥ −55` **OR** onset-coverage ≥ ⟨X⟩ over the track. Until then the gate is
      whole-track + level-only by design, and so is per-scene significance (CR-2a is also deferred, §B.1).
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
  not down). The dip/tension before it (the "dip before the lift") is the **Build/Breakdown**. So a
  Drop is **defined by the contrast**: a lower section immediately precedes a top-band section. Without a
  preceding dip/build it is not a Drop — just a loud section.
  Today's bug: `build_widget.py:769` calls any section ≥0.8 of peak a Drop (`tier = ti / mx`, relative),
  ignoring the required preceding dip → a continuously-loud track reads as "all drops." The signal
  lives in the **shape** of the curve (fall/build → sharp return + family entrance + density jump), read
  **in aggregate**. The original ambition was for the interpretation layer (an LLM reading the real curves)
  to make the call rather than a single hard threshold; **what SHIPPED (§B.2, G5/G6) is a hand-coded
  NECESSARY condition** — a Drop requires a strictly-lower predecessor (`LIFT`=0.12 tier) — validated by the
  necessary-condition tests in `tests/test_credibility.py` (G5/G6), NOT a phantom "§D". The LLM-reads-the-curve
  version stays a possible future direction; for now the threshold IS the design. Prefer labelling the
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
    the E "dips" are timbral/density shifts, not energy valleys (self-sim/MFCC catches them, energy
    doesn't). Confirms the call must be **aggregate** (self-sim boundary + energy + density + family
    entrance), per "read the data in aggregate".

- **CR-6 — repetition is read on the significant stems too.** Self-similarity / returns are computed on
  the non-empty stems, not only the mix, so "this part returns" is grounded in real recurring material.
  (Today: mix-level only.) ⟨DECIDE⟩ which stems count as "significant" (drums+bass+the loudest melodic?).

- **CR-7 — Ableton↔stem correspondence is stated only where defensible.** Map at group/track level where
  the correlation is strong; stay silent / caveat where it isn't. (Base exists: `map_stems`.) Hard —
  flagged for design, not a hard promise yet.

### B.1 Phase-2 resolutions (folded back from `prover_runs/spec_credibility_2026-06-20.md`)
- **CR-1a (from P2):** mix-level claims (energy/brightness/density/vitals/arc) are INDEPENDENT of stem
  significance — an all-insignificant-stems run still gives the full arc; only the stem layer is omitted.
- **CR-2a (from P1) — DEFERRED (2026-06-23): the shipped gate is whole-track.** The intent: significance
  is **per-scene**, not whole-track — a stem that carries only the drop is significant THERE; "omit + don't
  parse" would apply only to a stem insignificant in EVERY scene. NOT implemented — `significant_stems` is
  whole-track + level-only (§A KNOWN DEBT). Nothing downstream depends on the per-scene refinement yet.
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
- **CR-6 (G11) COMPUTED, then SURFACED (G20, 0.8.18).** `stem_repetition()` reads each significant stem's
  own self-sim (recurrence 0..1), gated by `significant_stems()`; the pipeline writes `result_selfsim_<stem>.json`
  for significant stems and build_widget auto-discovers them. **Surfacing (G20):** one "Development · what
  carries it vs what loops" card contrasts the part that EVOLVES (recurrence ≤ `EVOLVE_MAX_RECURRENCE`=0.25,
  carrying the development) with the ones that LOOP (≥ `LOOP_MIN_RECURRENCE`=0.45). Honest-naming rules: parts
  named by their character label, never the raw Demucs name (a stem with no label is skipped); shared labels
  are DEDUPED ("the mid, the mid" → "the mid", the §B.7 salad). Fires only on a real spread (someone clearly
  evolves AND someone clearly loops) and only when characters exist. Verified by deed on Lazy_Sparks: *"The
  bass keeps changing (recurrence 0.14) — carrying the development — while the mid and the drums mostly loop."*
  Tests: `G20_RepetitionSurfacing` (7). ⟨DECIDE⟩ the two thresholds (tune as tracks land).

### B.4 Stem CHARACTER labels (0.8.3 → 0.8.6, 2026-06-21 — G12, G13)
> ⚠ **SUPERSEDED FOR THE DISPLAYED LABEL by §B.7 (0.8.11) + §B.8/G18 (0.8.15).** The displayed label no
> longer uses `tonal` (→ base role `mid`), no longer uses `air` (→ `high`), and shows NO `≈` marker; the
> freq-role is taken from the per-stem spectral CENTROID (§B.8), with the G14 high-pass kept only as a
> no-centroid fallback. B.4 is retained as the G12–G15 DERIVATION HISTORY (how the buckets are computed),
> not as the current label vocabulary. Read B.4 for mechanism; read §B.7 for what the user actually sees.

Raw Demucs labels (`vocals`/`guitar`/…) are wrong for electronic music ([[track-coach-stem-labels]]): Sasha
makes synths, not a band. So we name a SIGNIFICANT stem by what its SOUND measurably IS — **never by which
instrument made it, EXCEPT the `bass` and `drums` families, which Demucs separates reliably and which Sasha
confirmed we read reliably (the low-end exception, §B.7)** — and the label must be DETERMINISTIC (same track → same label every run; no per-run
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
    was skipped) keeps the honest **`tonal`** umbrella INTERNALLY — we never invent a melody/chord verdict
    from missing data (CR-1). **It is DISPLAYED as the base role `mid`, never the word `tonal`** (§B.7 INV).
    All five new labels are `approx`.
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

- **G15 (0.8.7) — percussive-vs-tonal by CONTENT, not onset alone (found by deed on track 2).** G12 set
  `percussive = onset_rate ≥ ONSET_PERCUSSIVE`(3.0) and a percussive stem short-circuits to kick/perc/hats
  BEFORE the G13 tonal split runs. On *Simon Fava — Ta Bueno Ya* this mislabeled two clearly PITCHED mid
  stems as `perc`: `other` (onset 3.18, polyphony 0.49, sustain 0.73 — a real pad/chord layer) and
  `vocals` (onset 3.72, monophonic — a vocal line), both just over the 3.0 gate. Same family as G14: judge
  by CONTENT. A stem with real pitched content — basic-pitch transcribed notes, so `polyphony()` returns
  a value — is TONAL even when rhythmic; `perc` is reserved for transient stems with NO pitched content.
  - rule: `percussive = (onset_rate ≥ ONSET_PERCUSSIVE) AND NOT pitched`, where `pitched` = the stem has
    transcribed notes (polyphony measurable). Drums have no transcribed notes → still `kick`. A pitched
    rhythmic synth → routes to the G13 split (melody/lead/chord/pad) instead of `perc`.
  - **Safe fallback:** with no per-stem notes (a render without transcription) `pitched` is false → the
    old onset-only behaviour, so nothing regresses when notes are absent.
  - Verify-by-deed (Simon Fava): `other` → `pad` (was `perc`), `vocals` → `melody` (was `perc`); drums
    still `kick`, bass still `bass`.

### B.5 Individual recommendations — name the PART, not a template (G16, 0.8.8, Sasha's #2)
Sasha's standing complaint (2026-06-20, looking at the Lazy_Sparks render): recommendations "feel samey
because `build_recommendations` is a FIXED template catalog fired by thresholds — same handful repeats
track-to-track." The bet: now that we measure each stem, a rec can name the SPECIFIC part, band, and time
instead of a generic line. First target = the masking/frequency-clash rec, which already has the data per
conflict (`masking_flags`: which low stem buries which mid stem, in which band, at which times, by how much).
- **Before:** one generic card — `bass covers "{mid}" in {pct}% of spots` — using the RAW Demucs stem name
  (`guitar`, `vocals`), which is wrong for electronic music.
- **After (G16):** one card PER masked significant stem, naming both parts by their measured G13/G14
  CHARACTER label (the hard requirement [[track-coach-stem-labels]]: real terms, never raw Demucs names):
  e.g. *"the bass buries the lead around 250–600 Hz ~18% of the track, worst around 1:18"*. Carries the
  band's frequency range, the `pct_masked`, and the worst flag's time (pinned on the timeline).
- gated to `significant_stems()` (a near-silent stem like an empty `piano` is never named); the carrier is
  the masking low stem named by its character label (`bass`→"bass", `drums`→"drums" since §B.7 — was "kick").
  Falls back to the old generic card when stem characters aren't available (no masking/rhythm).
- **EVALUATION (Sasha's metric):** specificity up = fewer generic-type cards, more named-stem/time cards.
  Deed on Fragile: the one generic masking card → two named cards ("bass buries the lead 18%", "…the
  melody 15%"), piano (empty) dropped.

### B.6 The `late_entry` rec — name the part, never the raw Demucs name (G17, 0.8.9, Sasha's #2 cont.)
Continuing #2 ("wire per-stem character into MORE recs beyond masking"): the `late_entry` rec — fired
when a stem is silent for almost the whole track and only appears near the end — was the last LIVE rec
still printing the **raw Demucs stem name** (`Stem "{st}" is silent… bring "{st}" in earlier`). That
violates the hard requirement [[track-coach-stem-labels]] (Sasha makes electronic music — a `vocals`
stem is a synth, etc.) exactly as the masking card did before G16.
- **Wrinkle:** `late_entry` is BY DEFINITION about a near-silent stem, and `stem_character` only labels
  SIGNIFICANT stems — so the G16 character label is usually ABSENT here. We can't lean on it alone.
- **Honest naming hierarchy (most → least specific, never the raw name):**
  1. the measured **character** label (`_lbl`), if the stem happens to be significant enough to have one;
  2. else the **stemmap real-track name** — `stems[st].track_matches[0].track` — but ONLY when the
     stemmap verdict is `clear` (a strong, unambiguous match to one project part). `mixed`/`nomatch`/
     `empty` verdicts are NOT trustworthy enough to name a part, so we don't.
  3. else a neutral **"a new element"** — never the raw Demucs `{st}`.
- The template loses `{st}` entirely; it now interpolates `{part}` (the resolved phrase) so the rec reads
  *"A part (lead) is silent for almost the whole track and only appears at 3:40…"* / *"A new element
  enters right at the end…"* when unidentifiable. INV: a `late_entry` rec's text never contains a raw
  Demucs family name unless that name is also the real mapped track name.
- **The real cleanup wasn't the name — it was DON'T CRY WOLF (0.8.10, found by deed on Lazy_Sparks when
  Sasha asked "the card existed before — what's the point?").** late_entry was firing on the `vocals`
  stem whose late spike only reached **−61 dB** (peak), median −81, stemmap verdict `empty` — i.e. a
  near-silent SEPARATION ARTIFACT at the very end, not a musical event. Renaming it honestly is cosmetic;
  the card shouldn't fire at all. So late_entry is now GATED: it fires only when the entering peak clears
  the real-content floor `arr[peak] ≥ STEM_EMPTY_FLOOR_DB` (−55 dB). This is CR-1 "don't paint silence"
  applied to recs (same floor `significant_stems` uses), and it's peak-based (not `loud_level`/`empties`)
  on purpose: a GENUINE late accent is silent most of the track so its 85th-pct is low — only its PEAK
  proves it's real content. On Lazy_Sparks this card now correctly DISAPPEARS. INV: late_entry never
  fires on a stem whose entering peak is below the empty floor.

### B.7 ONE plain label per stem — kill the label salad (0.8.11, Sasha s14)
Sasha, looking at the real Lazy_Sparks render: *"what is this salad?"* The stem area had THREE overlapping,
half-confident systems stacked on each stem — (1) measured `character` with a `≈` "uncertain" prefix,
(2) the stem↔project map verdict (which ALSO used `≈`, meaning the OPPOSITE — "matches a family"), and
(3) per-stem repetition letters. Worse, the headline character often degraded: on Lazy_Sparks the **bass
stem read `≈ tonal`** (G14's high-pass drop didn't trip on a synth bass with mid harmonics), the whole
`drums` stem read `kick`, and empty stems STILL leaked the **raw Demucs name** (`vocals`) into the lane
label (G17 had only fixed the recs, not the panel). Decision — collapse to ONE plain label per stem:
- **Trust the stem for the reliable low-end families.** Demucs separates bass & drums cleanly and Sasha
  confirmed we read the low end reliably, so a `bass` stem is **"bass"** (we do NOT run it through the G14
  high-pass that demoted it) and a `drums` stem is **"drums"** (not "kick" — kick is a drum-breakdown
  sub-part). Only these two exact families are trusted by name; every other (electronic) stem name stays
  untrusted and is read by measurement ([[track-coach-stem-labels]]).
- **Character only when confident; else the base role.** A confident G13 determination (lead/melody/
  chord/pad) shows; otherwise the stem shows its plain **base role ("mid"/"high")** — never the jargon
  "tonal", never a `≈`-uncertain marker (Sasha: *"if not sure, just the base role"*).
- **No raw Demucs name in the lane label, ever.** No character ⇒ "near-silent" (the stem is empty),
  never `L.name`.
- **Sub-line = the REAL project track, never the raw Demucs name (0.8.12/0.8.13, updated from the 0.8.11
  text above).** The tiny line under each lane now shows the real project track name when the stemmap
  verdict is `clear` (e.g. guitar→"Guitar"), "near-silent" for empty stems, and NOTHING otherwise — the
  raw Demucs name and the `→ family` marker are both GONE (0.8.11's "guitar · → other" salad is removed).
  The sub-line is also suppressed when it would merely repeat the main label (0.8.13 — no double
  "near-silent").
- **Three surfaces name a stem differently ON PURPOSE** (cross-ref §B.6): the late_entry rec needs one
  best single guess (character → clear track-name → "a new element"); the lane shows the measured ROLE as
  the headline and the real track-name as supporting sub-text. Same data, different jobs.
- Verified by deed (Lazy_Sparks 0.8.11–0.8.15): drums→"drums", bass→"bass", other→"lead", guitar→"mid",
  vocals/piano→"near-silent"; guitar sub-line→"Guitar".
- **INV (label set).** The displayed lane label is EXACTLY one of:
  `bass`, `drums`, `kick`, `perc`, `hats`, `lead`, `melody`, `chord`, `pad`, `mid`, `high`, `near-silent`.
  **Never** `tonal`, never a `≈` prefix, never a raw Demucs family name. **Internal buckets that DON'T appear
  verbatim:** `tonal` (G13 fallback) is displayed as the base role `mid`; `air` (G12/G14 high-sustained) is
  displayed as `high`; `noise` is inert (the flatness gate never fires — §B.4/G13 — so it is never emitted,
  and it is intentionally NOT in the displayed set until a real noise/riser stem exists to verify it). Note:
  `bass` is reachable two ways — the trusted `bass` family, AND an UNTRUSTED stem whose centroid is <
  `LOW_CENTROID_HZ` (§B.8, role `low`); the latter is intentional (it occupies the bass range) but see the
  OPEN question below on whether to split that word.
- **OPEN (asked Sasha):** where the map verdict is genuinely `clear` AND the matched real project track
  looks meaningful (e.g. guitar→"Guitar"), fold that real name in as the primary label instead of the
  base role "mid"? Held because `clear` matches are noisy (drums→"7-Impulse"). NOTE: 0.8.12 already put the
  real name in the SUB-line, so if it's ever promoted to PRIMARY, drop the sub-line duplicate (else
  "Guitar / Guitar").

### B.8 Freq-role from the per-stem FREQUENCY ANALYZER (centroid) — G18, 0.8.14/0.8.15 (Sasha's idea, s14)
Sasha (s14): *"you can run the frequency analyzer on each stem too."* We already run full spectral
analysis on the MIX; per stem we only had 6 coarse bands + flatness. So `masking.py:stem_spectrum(y)` now
computes, per stem (reusing the loaded audio, one extra STFT):
- **spectral centroid** (Hz) — energy-weighted "centre of gravity" of the spectrum = where the stem's
  energy sits (≈ perceived brightness). Power-weighted across frames (reflects "when it plays").
- a **32-bin log-frequency spectrum** profile (dB, peak-normalised) — emitted as `spectrum`/`spectrum_freqs`
  for a future per-stem spectrum VIZ (data is forwarded into the widget payload at 0.8.16; the canvas draw
  is deferred until it can be visually verified).
- **G18 — freq-role now from the centroid (supersedes G14's high-pass for the role).** A SUSTAINED
  (non-trusted) stem's role = `low` if `centroid < LOW_CENTROID_HZ` (250), `high` if `> HIGH_CENTROID_HZ`
  (3500), else `mid`. This is the robust signal Sasha asked for — it fixes the synth-bass-→-`tonal`
  failure at the root (a 6-band high-pass drop was a poor proxy for "where the energy is"). The **G14
  high-pass drop is kept ONLY as the fallback** when the masking carries no centroid (pre-0.8.14 jsons),
  so nothing regresses. Trusted `bass`/`drums` (§B.7) still short-circuit before any role computation.
- VERIFY-BY-DEED (Lazy_Sparks, regenerated masking): centroids bass 117 / drums 203 / piano 602 /
  vocals 633 / other 942 / guitar 1008 Hz; resulting labels bass→bass, drums→drums, guitar→mid, other→
  lead — identical to 0.8.11 but now centroid-derived, no regression. Unit tests: `G18_CentroidFreqRole`.
- INV: when `spectral_centroid[st]` is present, a non-trusted sustained stem's role is a pure function of
  it (deterministic); `< LOW_CENTROID_HZ` ⇒ role `low` ⇒ label `bass`.
- ⟨DECIDE⟩ thresholds: `LOW_CENTROID_HZ`=250, `HIGH_CENTROID_HZ`=3500 (tune as tracks land). **OPEN (F5,
  asked Sasha):** should an UNTRUSTED low-centroid stem read `bass`, or a neutral `low` so "bass" stays
  identity-only? Currently it reads `bass` (honest about the frequency range it occupies).
- IDEA (Sasha s14): split into MORE than 32 bins to drive concrete MIXING recs ("cut 3 dB at 380 Hz on
  the bass") — **DONE: §B.9 (G19) named the spot; 0.8.20 bumped the grid 32→64 bins** (see §B.9 note).

### B.9 PRECISE masking frequency — name the cut spot, not the whole band (G19, 0.8.17, Sasha's idea a)
The §B.5 masking card said *"the bass buries the lead around **250–600 Hz**"* — the whole coarse band, the
same range for every conflict. Sasha's s14 idea (a): the per-stem spectra (§B.8 `spectrum`/`spectrum_freqs`)
already say WHERE inside the band the two parts fight, so the card can name a cut frequency.
- **Mechanism (`build_widget.mask_collision_freq`, pure-python so the build stays numpy-free):** within the
  zone's band, the collision sits where the OVERLAP of the two peak-normalised spectra is greatest —
  `min(masker_db, maskee_db)` is large only where BOTH stems have energy at that bin. Pick that bin's
  centre frequency. Computed at REC time from the masking JSON (not stored), so no `masking.py` change.
- **Credibility gate (CR — "don't over-claim"):** name a precise frequency ONLY when the buried part
  genuinely has energy at that bin (its level ≥ `MASK_FREQ_MIN_LEVEL_DB` = −24 dB of its own peak).
  Otherwise → `None`, and the card KEEPS the coarse band range. Pre-0.8.14 jsons (no `spectrum`) also fall
  back. So the card never invents a spot the maskee isn't in.
- **After (G19):** *"the bass is louder than the lead around **≈380 Hz** (in 250–600 Hz) ~18% … Notch the
  bass around ≈380 Hz."* Each conflict gets its OWN frequency. `fmt_hz`: nearest 10 Hz, kHz above 1 kHz.
- VERIFY-BY-DEED (Lazy_Sparks, regenerated masking): distinct, in-band spots — bass↔other ≈270 Hz,
  bass↔vocals ≈510 Hz, bass↔guitar ≈340 Hz, kick↔bass (sub) ≈60 Hz (was a flat "250–600 Hz" for all).
- INV: the named frequency always lies inside the zone's band; an out-of-band overlap is never chosen; a
  silent/absent spectrum yields the band-range fallback. Unit tests: `G19_PreciseMaskingFreq` (7).
- ⟨DECIDE⟩ `MASK_FREQ_MIN_LEVEL_DB` = −24 dB (tune as tracks land). OPEN: scale the SUGGESTED cut depth
  ("a couple dB") from the measured overlap — held; the depth stays advice-not-measurement for now.
- **0.8.20 — grid bumped 32→64 bins (`masking.SPEC_NBINS`), the finer frequency analyzer.** At 32 bins (~3.3/octave)
  two DIFFERENT low-mid clashes (bass↔other, bass↔guitar) both snapped to ≈270 Hz — too coarse to tell apart.
  Experiment across 32/48/64/96 bins (verified by deed on Lazy_Sparks): at ≥48 they separate (other ≈290,
  guitar ≈260) and stay STABLE through 96. Chose 64 (~6.6/oct): clear discrimination, stable, not so fine it
  chases spectral spikes. Pure schema change (spectrum array 32→64 long); G19/centroid consume it unchanged.

### B.10 "Where does it get boring?" — the development plateau (G21, 0.8.19, Sasha's idea)
Sasha (2026-06-22): *"for evolving tracks, the idea is to show at what point it gets boring."* For an
EVOLVING track, mark the onset after which it stops introducing NEW material and only recombines sections
already heard.
- **Mechanism (`development_plateau(selfsim, dur)`, pure-python).** Read the self-sim segment letters in time
  order (same letter = a returning section). The onset = the END (`t1`) of the last segment that introduces a
  NEW letter; after it, every segment is a repeat. Returns `{onset_s, tail_frac, n_sections}`.
- **Gates (so it's honest, not a blanket "this is boring"):** fires only when the track DEVELOPS
  (≥ `MIN_DEV_SECTIONS`=3 distinct sections) AND the no-new-material tail is ≥ `PLATEAU_MIN_FRAC`=30% of the
  track. A track that keeps introducing new sections to the end → `None` (correctly NOT flagged); a track that
  never develops → `None`. NOT a value judgement: the card says "no new material from here", action left to
  the producer; anchored to the onset time on the timeline.
- VERIFY-BY-DEED (3 library tracks): **Shared_Memories** plateaus — letters `A B C B C D C D C B`, last new
  `D` at 2:53, tail 49% → *"After 2:53 nothing new is introduced — the last 49% recombines earlier sections."*
  **Lazy_Sparks** (`A B C D C E C E C F A`, new `F` near the end) and **Wobble_Drift** (`A B C D E C`, new `E`
  late) → `None`, both still developing. So the gate discriminates on real material.
- INV: the onset always equals the end of a NEW-letter segment; `None` whenever distinct letters < 3 or the
  no-new tail < 30%. Tests: `G21_DevelopmentPlateau` (5).
- ⟨DECIDE⟩ `MIN_DEV_SECTIONS`=3, `PLATEAU_MIN_FRAC`=0.30. **OPEN (refinement):** this catches only the
  END plateau (last new material → end). An INTERNAL repetitive stretch (e.g. Lazy's `C E C E C` oscillation
  in the middle, before a later new section) is NOT yet caught — a future "longest no-new run" variant could.

### B.11 Per-stem measurements — run the track tools on each stem (PROPOSED, Sasha 2026-06-22, #2 advanced)
**Sasha's model (verbatim intent):** *"we had a bunch of tools pointed at the whole track. one of those tools was stems. let's point everything (except stem separation itself) at each individual stem."* The
whole-track measurements that `analyze_core`/`analyze_detail` produce — **energy, brightness, density,
stereo width, modulation, loudness/dynamics** over time — are, today, computed ONLY on the mix (see the
matrix below). This runs that same set on **each significant stem**. (Stem separation itself is excluded —
you don't separate a stem. Stem-only tools that DON'T run on the mix — melody/chord/percussion/noise
classification, drum-hit breakdown, masking, role — already exist; this is the missing other half.)

- **Entity (new).** *per-stem audio feature* — the same measured curve as a mix `audio feature`, but over one
  stem's wav. Inherits the stem's **significance** state (A): computed ONLY for `significant` stems (CR-2);
  an empty/quiet stem gets no per-stem feature, no card. Same units/ranges as the mix feature.
- **Mechanism.** Re-run the existing core measurement on each significant stem wav (the stems are already on
  disk in `stems_6s/`), producing `result_core_<stem>.json` analogous to `result_selfsim_<stem>.json` (B.3,
  already auto-discovered). No new DSP — the SAME functions, different input.

- **CR-11 (the credibility consequence — Sasha's core objection, do NOT skip).** *"we haven't validated the hypothesis — will it actually show useful info, or just more stuff that's hard to make sense of."* So per-stem output is gated on **usefulness, not volume**: a per-stem card fires **only when the
  stem's curve diverges NOTABLY from the REST of the track** — the bass brightens while the rest darkens; one
  stem's density drops out while the rest rises; a stem's energy arc runs opposite the others. **"Same as the
  rest" → NO card** (it's redundant, it just adds noise). The signal is DIVERGENCE, not the raw per-stem number.
  - **Baseline = the mix MINUS this stem (prover F1).** Compare each stem to the rest of the track, NOT the
    full mix — the mix contains the stem, so a loud stem (bass/drums) is partly compared to itself, which
    SUPPRESSES exactly the "it runs opposite the track" insight we want. Build the baseline from the other
    stems' aggregate.
  - **Shape, not magnitude.** Compare curve SHAPE over time (normalized / correlation), since a stem sits far
    below the mix in absolute level. ⟨DECIDE⟩ the divergence threshold (trend sign differs AND |Δtrend| ≥ τ;
    and/or correlation with the rest < ρ).
  - **Score importance, then budget the TOTAL — no fixed per-stem cap (Sasha 2026-06-22).** Do NOT hard-cap
    cards per stem. Instead: (1) each candidate insight gets an **importance score** (how big the divergence,
    how clear/actionable it is); (2) all candidates — the existing track-level recs AND the new per-stem/composite
    ones — compete in ONE ranked pool; (3) show the top by score up to a **total card budget** kept near today's
    "normal" count, not an explosion. ⟨DECIDE⟩ the budget (calibrate to the current count).
  - **Diversity, so one stem can't hog the list.** A balance rule so the top cards aren't all about the drums
    (e.g. a per-source soft quota / penalty for repeats from the same stem). ⟨DECIDE⟩ the rule.
  - **Cards can be COMPOSITE, not one-per-stem (Sasha 2026-06-22).** A card may combine signals — two stems
    diverging together, or a stem-vs-track relationship ("energy rises but the drums thin out") — not just a
    single stem × single measure. The scoring/budget pool holds composite candidates alongside per-stem ones;
    the "one stem, one measure" shape is the simplest case, not the only one. A naive per-stem enumerator is
    explicitly rejected.
  - **Correlated measures collapse — SMART (Sasha 2026-06-22, refined).** Energy/density are correlated
    activity/loudness axes, so a single PART firing on both reads as a pile-up ("The mid — sparser" + "The mid
    — quieter"). Collapse per stem: **same direction** (both "more" or both "less" — quieter+sparser restate the
    same "this part pulls back") → keep the **strongest** only; **opposite directions** (louder BUT sparser — a
    genuine contrast: bigger yet fewer hits) → **MERGE into ONE richer card** ("louder but sparser") so the
    contrast survives instead of being dropped. Either way each part yields at most one divergence card.
    Composite cards (a different KIND) are unaffected. Code: `collapse_correlated` before `select_cards`.
  - **"Show more" on demand (Sasha 2026-06-22).** The default budget stays tight (only the high-score cards).
    A separate control / command lowers the score threshold to reveal the next tier of lower-rated candidates
    for a user who wants to dig — the strict default is what's shown first, the deeper set is opt-in (it never
    changes the default view, so the calm/Simple read stays uncluttered). ⟨DECIDE⟩ the lowered threshold.
  - **Per-measurement validity (prover F5).** Significance (loudness+time) doesn't make a SPECIFIC measure
    meaningful — brightness of an all-sub bass, stereo width of a mono stem, is junk. Each measure carries its
    own precondition (brightness only with real high-freq energy; stereo only when not effectively mono); unmet
    → omit that card (same "don't paint silence" as CR-1).
- **USEFULNESS IS DEFINED OBJECTIVELY — the system self-judges, no per-track human approval (Sasha 2026-06-22:
  "I can't look at and approve cards for every track in the world — write yourself the criteria").** Divergence
  alone is a weak proxy (a true-but-boring wobble diverges). So a candidate's **importance score** is built from
  measurable properties, and only that decides whether it earns a slot:
  1. **Big** — divergence magnitude ≥ τ (not a tiny wobble).
  2. **Persistent** — holds over a real span (≥ a min seconds / % of the track), not one frame — same "enough
     material" discipline as CR-1; one blip is not an insight.
  3. **Specific / actionable** — names a part + a time + a direction (reuse the #2 metric: named & timed). A
     vague candidate scores low and loses to a specific one.
  4. **Non-redundant** — adds something a higher-ranked card or the mix-level reading doesn't already say
     (dedupe by claim). A card that restates the mix scores ~0.
  These four ARE the definition of "useful"; the score ranks candidates and the budget/diversity rule picks the
  top. ⟨DECIDE⟩ the weights + τ + min-span — I **calibrate them ONCE on the 3 library tracks and freeze them as
  defaults** (like the other settled ⟨DECIDE⟩ values), not per track.
- **PROMINENCE — a near-silent stem ranks BELOW the louder ones (Sasha 2026-06-22).** *"If a stem is
  near-silent, its cards are better placed below the others."* A quiet part diverging from the track matters
  LESS than a loud part diverging — so each candidate's score is multiplied by a **prominence weight (0..1)**
  measuring how loud that stem is RELATIVE to the loudest significant stem. Truly sub-floor stems never reach
  here (no `result_core_<stem>.json` is written for them, CR-2); this orders the SIGNIFICANT-but-quiet ones.
  It is a soft down-rank, NOT a drop: a near-silent part's card still appears if its divergence is strong
  enough to win a budget slot, it just sorts after the prominent parts. Relative, not absolute — `weight =
  clamp(1 + (loud_db − loudest_stem_db) / SPAN, FLOOR, 1)`, loud_db = the §A `loud_level` (85th-pct broadband,
  the same number the significance gate uses, NOT the self-normalized per-stem energy curve, which peaks at 1
  for every stem). ⟨DECIDE⟩ `PROMINENCE_SPAN_DB` (24) + `PROMINENCE_FLOOR` (0.4), calibrate with the others.
- **Composite cards are WORDED into the pool (0.8.23).** `composite_candidates` (a stem moving against the
  whole track, e.g. "the beat thins out as the track builds") now competes in the SAME budget/diversity
  selection as the per-stem divergence cards and is worded by character label, not the raw Demucs name —
  previously the composite scorer existed but only divergence cards were rendered.
- **The eval is a regression guard, not an approval gate.** `scripts/eval_*` measures, on the 3 fixtures,
  that the shown cards satisfy the four criteria (share specific, share non-redundant, none below τ) — so a
  future change can't quietly fill the budget with noise. Sasha's eye is a one-time sanity check on those 3
  fixtures while I calibrate, never a per-track requirement.
- **Back-compat (prover F6).** A run with no `result_core_<stem>.json` (pre-B.11) yields no per-stem cards and
  NO error — same graceful fallback as pre-0.8.14 masking falling back to the band range.

- **WHERE it shows (Sasha 2026-06-22).** Per-stem cards live in the **Detailed view only** by default (they
  are depth, not the headline). **Promotion to Simple** only for a STRONG divergence (⟨DECIDE⟩ a higher
  threshold) — *"if there's something really important there, why not put it in Simple too."* Respects the view ladder
  (`quick ⊆ Simple ⊆ Detailed`, the view ladder — INV-19 in `docs/TEST_MATRIX.md`): a card promoted to
  Simple is therefore also in Detailed.
- **SORT TOGGLE (Sasha 2026-06-22) — Detailed only.** Today the advice cards are ordered by **urgency**
  (`build_widget.py:1493` `_rank crit<do<concept`) while the lettered cues a/b/c on the timeline are ordered
  **chronologically** (`build_widget.py:1999`) — a deliberate-but-confusing split. Add a Detailed-only toggle
  to switch the CARD list between **by urgency** (default, unchanged) and **chronological** (matching the
  letters). Pure presentation reorder; never adds/removes a card. ⟨DECIDE⟩ default = urgency (current).

#### B.11.1 Resolution (2026-06-22) — BRIGHTNESS is descriptive, not a prescriptive per-stem card (Sasha)
When A1 (per-measure validity) reached brightness, Sasha rejected the *premise*, not just the threshold:
*"I'm not convinced yet that anything *should* be brighter than anything else — and whether it's a mistake,
how would you know? Maybe the drums are meant to burst in, maybe a synth. Better to push this to some
visualization later."* The point:
a part being **brighter/darker than the rest is not a defect** — brightness divergence carries no intent, the
coach cannot know whether the bright burst is wanted (a drum fill, a synth stab) or a mistake. A prescriptive
card ("the lead is brighter than the rest — worth a second listen") therefore **asserts a problem it can't
justify** (the credibility invariant: don't present a guess as a finding). Resolution:
1. **Brightness is REMOVED from the prescriptive per-stem divergence measures.** `PER_STEM_MEASURES` =
   `("energy", "density")` only. Energy/density divergence stay because they read against the *arc* (a part
   fighting the energy build, dropping out as everything lifts) — closer to an actionable observation; brightness
   does not. (This SUPERSEDES the earlier plan A1, which treated brightness as a card needing only a validity
   gate.) The F5 validity discipline still governs any FUTURE measure added in E2 (stereo on a mono stem, etc.).
2. **Relative brightness, if surfaced at all, is DESCRIPTIVE — one balance reading, or (preferred) a future
   VIZ, never a per-part nudge.** Backlog: a single "relative brightness balance across the parts" card (no
   judgement) OR a small per-stem brightness visualization. Deferred — Sasha leans viz-later.
3. **Broader steer (informs E2 — widen the funnel).** "How would you know it's an error?" applies to ANY
   per-stem MEASURE divergence: most are descriptive facts, not defects. So widening `PER_STEM_MEASURES` must
   distinguish **arc-relevant / actionable** axes (worth a prescriptive card) from **descriptive** axes (belong
   in a viz / one balance card). Default to descriptive unless an axis has a defensible "this fights the track"
   reading. This is a stronger filter than raw validity and is why E2 widens AFTER this, not before.

### B.12 Producer's read — name HOW it develops, flag an idle axis (2026-06-23, Sasha — the artistic layer)
The Producer's read is authored prose — *"here's what I hear, and my thoughts as I go"* (Sasha). Its job is
**OBSERVATION**, not a command: the actionable "do X" lives in the **cards**; the read carries thinking-aloud
+ technical remarks (the two-layer principle, memory `track-coach-two-layers-cards-vs-read`). So the read MAY
state a precise observation or a soft flag **without** forcing a fake action item.
Sasha (2026-06-23): the read shows the curves and what's heard, but never states a short **verdict of which
FORM the development takes**, nor FLAGS a dimension that sits idle. Add to the read's "shape" paragraph one
observation:
- name the **dominant development mode(s)** — which of {energy/loudness, brightness, density, stereo width}
  actually trend across the track, **each with its DIRECTION** (the trend's sign): louder vs pulls back,
  brightens vs darkens, busier vs thins, widens vs tightens the image. (F1, prover 2026-06-23: dominance is on
  `|trend|`, so any axis can be dominant while moving DOWN — the read must never say "grows by brightness" on a
  darkening track.)
- **flag an idle axis** as a soft option, never a defect — *"stereo and density barely move — the image
  stays narrow the whole way; if you want it to open up toward the finale, that's an unused axis."*
- **Credibility:** the verdict comes from the measured trends via a pure helper `development_mode(core)`
  reading `energy_trend` / `brightness_trend` / `density_trend` / `stereo_width_trend`. **All four are the SAME
  metric — Pearson correlation of the curve with its time index (`_common.trend`), in [−1,1], scale-invariant
  (direction/monotonicity, not magnitude)** — so ONE threshold across all four is sound (F4 resolved by deed,
  prover 2026-06-23). Dominant = `|trend| ≥ DEV_DOMINANT` (0.12); idle = `|trend| < DEV_IDLE` (0.10); the
  0.10–0.12 gap is "moderate" (neither named nor flagged). NEVER name a mode whose `|trend|` is below
  DEV_DOMINANT; flag an idle axis ONLY when ≥1 axis is dominant. **Flat-track postcondition (F5):** when NO
  axis reaches DEV_DOMINANT, `development_mode` returns empty dominant + empty idle, and the read adds **no**
  development sentence (it does not say "no dominant mode" — that would double-cover `energy_flat`). Calibrated
  by deed on the 3 library tracks (Lazy → grows by loud+bright, idle density+stereo; Shared → busier + image
  tightens; Wobble → opens only in brightness) — matches the hand-written stories in `docs/signal_value_map.md`.
- **NOT a card** (no fake action) — an observation IN the read. The helper is pure + unit-tested; the prose is
  authored, and `SKILL.md` carries the writing rule so every read includes it.
- **Standalone (2026-06-23, by deed on Wobble — a Demucs run with NO authored narrative):** the line renders
  even when there's no authored read, so a developing track without a written read still gets this one real
  observation. The read panel hides ONLY when BOTH the dev line is empty (flat track) AND there's no narrative.
  (This SUPERSEDES the earlier "empty narrative → panel always hidden" rule.)

### B.13 Card evidence — every card names where it came from (the "based-on" line; 2026-06-23, Sasha)
Sasha: *"show which signals drove each card."* Every recommendation card carries a plain
line saying what it is **based on**. The credibility trap (memory `track-coach-card-evidence`): a raw lone
number/tag says nothing — *"dynamics 30.7 — is that a lot? measured in what, oranges?"* (Sasha). So the based-on line is
in **plain language, never a bare metric identifier** (`true_peak_db`, `dynamic_range_db`).
- **Scope of "every card" (F2, prover 2026-06-23): the `D.recs` list** rendered at `#recs` (the "Start here"
  advice) — mix-level recs AND per-stem cards. The separately-built note cards in the separation / rhythm /
  project panel (export, model, leakage) are an evidence SURFACE, out of scope this increment.
- **Tier-A vs Tier-B/C wording (F3, prover 2026-06-23):** a **single-signal (Tier-A)** card (true-peak,
  swing, tonal resonance) honestly comes from one number — its based-on names that **one signal in plain
  words** ("from the master's true-peak meter"), which is allowed; the ban is only on a bare tag. A
  **fused (Tier-B/C)** card names the **combination** ("the bass and the lead overlap around ≈290 Hz for ~half
  the track"), the fusion from `signal_value_map.md`. Source is multi-level: a whole-track signal / a separated
  part / an `.als` moment.
- **Build order = MEANING then NAVIGATION** (Sasha): (1) the plain based-on line per card — done 0.8.27;
  (2) **NAVIGATION (0.8.28):** clicking a timecoded card seeks the playhead to that moment AND scrolls the
  main graph into view (already wired), now plus a brief **attention pulse on the graph container** so the eye
  catches that the playhead jumped there. The pulse is a **CSS/DOM class toggle on the graph panel — it does
  NOT touch the canvas drawing** (deliberately low-risk: the canvas render is the fragile surface we never edit
  blind). A deeper per-lane / per-part highlight (light up the exact lane the card is about) stays deferred —
  it needs canvas work and a live render review.
- **Subtle in the UI** — transparency, not overload (Sasha's "don't overload" steer). A quiet muted line under
  the card body.
- **Machine-checkable invariant (the rest is authoring quality):** every `D.recs` entry has a **non-empty**
  `based_on`. "Plain language / not a bare tag / does not restate the action" is authored-prose quality, not
  unit-tested.

### B.14 The synced player as a STATE MACHINE (2026-06-23, cold-session maintenance — the most interactive, least-spec'd surface)
The full-mode player is the widget's most interactive surface (play/pause × per-stem mute × solo × seek ×
card-click) and was, until this pass, NOT in the spec and tested only by string-matching the JS source — so
the COMBINATIONS were never exercised (the seek-stops-playback bug, 0.8.28/INV-33, was exactly this class).
This section names the machine; the cross-control invariants are extracted into pure, DOM-free JS helpers
(`pgains` / `toggleStem` / `seekResult`) so they can be unit-tested by EXECUTING the real shipped code in
node — not by mirroring it in Python (assert against the artifact, not a fragment).

- **State.** Transport ∈ {`playing`, `paused`}. Each stem carries `{mute: bool, solo: bool}`. Derived:
  `anySolo = some stem.solo`. Audible(stem) = `anySolo ? stem.solo : !stem.mute`. The browser flag set on
  each `<audio>` is `muted = !audible` — computed by `pgains(stems) → muted[]`.
- **Controls / transitions.**
  - **play/pause** (the transport button): toggles `playing`↔`paused`; on play, every stem's `currentTime`
    is re-synced to the master before `play()` (stems never drift apart).
  - **mute(i)**: `toggleStem(stems, i, "mute")` flips stem i's mute; if it became muted, **clears every
    solo** (you drop into "mute mode").
  - **solo(i)**: `toggleStem(stems, i, "solo")` flips stem i's solo; if it became soloed, **clears every
    mute** (you drop into "solo mode").
  - **seek(t)** (chart click / rec card / cue / lane gutter / rewind): `seekResult(t, dur, wasPlaying)`
    clamps t to [0, dur] and reports whether to resume; every stem's `currentTime := t`; if it was playing,
    all stems resume together (re-synced).
  - **card-click** (timecoded rec): = seek(t) + scroll `#storyPanel` into view + a CSS `pulse` on the graph
    panel (DOM/CSS only, never the canvas — §B.13/INV-34).
- **Cross-control INVARIANTS (the combinations that were untested).**
  1. **One mode at a time (Sasha, 2026-06-21 — he called the mixed state wrong).** After ANY sequence of mute/solo toggles,
     never `(some stem muted) AND (some stem soloed)` simultaneously. `toggleStem` guarantees it.
  2. **Solo resolves gains.** When `anySolo`, the audible set is EXACTLY the soloed stems (every non-soloed
     stem is muted), regardless of individual mute flags.
  3. **Mute resolves gains.** When NOT `anySolo`, audible(stem) = `!stem.mute`.
  4. **Seek preserves transport AND mix.** A seek does not change any stem's `{mute, solo}` and resumes iff
     it was playing (a seek while paused stays paused). So: solo a stem → seek while playing → the same one
     stem is still the only one audible AND playback continues (INV-33 generalised to the combination).
  5. **Seek clamps.** The resulting time is always in [0, dur]; a gutter/negative/over-dur click never seeks
     out of range.
  6. **The player COMPOSES with the VIEW axis — solo/mute is a Detailed-only capability (2026-06-23, Sasha
     found by deed: solo a stem → switch to Simple → the soloed part visually vanishes and you can't un-solo
     it).** The stem grid (`#stemlanes`, where the M/S controls + waveforms live) is hidden in Simple and
     absent in quick (the view ladder, INV-18/22). So a per-stem mute/solo state is only **visible and
     reversible in Detailed**. Invariant: **entering Simple RESETS the per-stem mix to the full mix**
     (`resetMix` clears every mute+solo, then `pgains` → all audible) — so the user is never left hearing a
     solo / muted part they can't see or undo. Re-entering Detailed starts from the full mix (no hidden
     leftover state). This is the general rule the original §B.14 missed by modelling the player on the audio
     axis ALONE: an interactive surface must be specified across EVERY view/mode axis it lives under, not just
     its own. (Quick never has the grid, so it never reaches this state.)
- **Mix-mode (quick run).** One source, transport + seek only — no mute/solo grid; `pgains`/`toggleStem`
  are not wired (a single source is always audible). `seekResult` still governs its seeks.

## D. The REFERENCE layer (0.9 — DRAFT, 2026-06-24, Sasha). "Хочу как Aphex Twin."
**Status: DRAFT, mid-design — Sasha was actively widening the scope as this was written. Every ⟨DECIDE⟩ is
open; the SHAPE below is agreed, the THRESHOLDS/metrics are not. Do NOT derive tests/code until this layer is
proven AND Sasha has confirmed the draft.** This layer is AUDIO-ANALYSIS + COACHING; it builds on §A–§B and
must not re-open the credibility/artistic invariants.

### D.0 Why this layer exists (purpose — REFRAMED by Sasha mid-session)
The point is **not to clone a reference 1:1.** The point is: point at a reference — a track, or a whole
*direction* (an album / several albums by an artist) — understand it deeply (composition, sound, mood, style,
hypnotic↔hysteria, and more), see **where my track already sits relative to it** and **where it's my own**,
and then **bias track-coach's existing recommendations + read to be "more in the style of" that reference.**
Comparison (map + read) is how you SEE the direction; the re-flavoured coaching is the PAYOFF. (Sasha,
2026-06-24: "цель не сделать один к одному… но чтобы рекомендации были более 'в стиле' референс трека.")

Ties to the standing principles: the artistic north-star (OBSERVE & OFFER, never grade —
`track-coach-artistic-northstar`) and the two-layer split (cards = actionable, read = observation —
`track-coach-two-layers-cards-vs-read`). A reference NEVER produces a grade.

### D.0.1 The reading stance (Sasha, 2026-06-24 — the design decision that shapes the whole layer)
Character (psychotic / hypnotic / a mood / a style) is **NOT a single hand-engineered metric with a
threshold.** That path templated and went stale before (the artistic spine, NEXT_STEPS s18). Character lives
in the **interrelations of many signals**, which is exactly what a holistic read synthesises well — proven by
deed: with no metric and no mapping given, the read called `wobble drift` psychotic and the other two hypnotic
purely from the signals (live transcript 2026-06-24; NOT a stored classifier — code has only one generic
"hypnotic" template string, `build_widget.py:197`). So:
- **Measured signals (§A–§B) stay the credible floor — they are the EVIDENCE/proof.** Unchanged; still
  deterministic and tested as today.
- **Character is a holistic READ over the whole constellation of those signals** (the two-layer read register
  §B.12), not a formula. The reference comparison is "does my track read as the **same family** as the
  reference?" across the whole fingerprint — not an axis-by-axis pass/fail.
- **The anti-fabrication discipline (extends CR-1 / the based-on line §B.13):** every character word is
  **anchored to a real piece of evidence OR a COMBINATION of evidence** (Sasha: "прибито к улике или к
  комбинации улик"). Synthesis composes the words; the numbers prove them — "psychotic *because* novelty
  spikes + density ruptures + the meter breaks at 1:40 & 2:10 together." A character claim with no evidence
  (single or combined) behind it is a CR-1 violation, omitted not rendered.
- **Two uses of the same evidence:** the **numbers** drive the constellation-MAP geometry (similarity over the
  signal vector, §D.7/S1); the **read** drives the WORDS. One evidence base, two outputs.

### D.1 Entities (reference layer)
- **reference track** — a third-party track analysed with the SAME pipeline as my tracks, but **AUDIO-ONLY**
  (a local audio file at start; **never has an `.als`**). So every `.als`-derived surface (arrangement,
  automation intention-vs-result, locators, .als parts §A) is **absent** for a reference — the pipeline runs
  its audio subset only. Lives in a **separate reference catalog** (§D.7). Has an **artist** attribute (a
  name string) and optional **artist metadata** (§D.5).
- **reference direction** (a.k.a. **reference cloud**) — a user-named SET of reference tracks (one album, or
  several albums grouped under one name, e.g. "Venetian Snares", "scsi-9 + deepchord"). Defines a **region** in
  the signal-fingerprint space = `{centroid, spread}` over its member fingerprints (§D.2.1, for the map), and a
  shared **mood/style read** (§D.2). **A direction with fewer than N members IS reduced mode (§D.4) — there is
  no separate "point-direction" state** [resolves prover A1/D-7]: below N there is no meaningful spread, so it
  reads as plain track-vs-track, no range cited. ⟨DECIDE D-1⟩ the threshold N (the one number that says "enough
  members to be a cloud").
- **read dimensions** — what a track is actually read & compared on: **mood** and **style** (§D.2), holistic
  reads, not mechanical meters. Under them sits the **evidence pool** — the existing measured signals (§A–§B:
  arc/development, palette, density, meter, stereo, novelty) that each read CITES (single or combined,
  D-INV-10) and that also serve as the numeric fingerprint for the map. The set of read-dimensions can grow,
  but each stays a read over evidence, never a hardcoded axis (Sasha, 2026-06-24).
- **aspiration mapping** — a **user-authored, MANY-TO-MANY** link: my track(s) → reference direction(s). The
  tool does **NOT guess** which direction I aspire to; I declare it (e.g. `wobble drift → Venetian Snares`;
  `{lazy sparks, shared memories} → {scsi-9, deepchord}`). Cardinality both ways: one of my tracks may aspire
  to several directions; one direction may be the aspiration of several of my tracks. ⟨DECIDE D-2⟩ where the
  mapping is stored (a project-level file? the library index?) and how it's edited.
- **my track** — the existing library entity (§A, the catalog), now additionally **PLACEABLE** against a
  direction (gets a mood/style read + a position in the signal-fingerprint space for the map, §D.2/§D.7) and
  **re-flavourable** (§D.6).

### D.1.1 Lifecycle of directions & mappings — who edits, what recomputes [resolves prover F4 / D-2]
The direction and the mapping are the layer's data backbone; both are **user-authored content** (the tool
never creates or guesses them, D-INV-4). ⟨DECIDE D-2⟩ the store (a project-level file vs the library index)
and the edit surface; the TRANSITIONS below hold regardless of store.
- **reference track** — `import` (analyse audio subset, build its fingerprint §D.2.1) → `remove` (drops it
  from every direction it belonged to → those directions recompute, below).
- **reference direction** — `create` (name + ≥1 member), `add-member` / `remove-member`, `rename`, `delete`.
  Any membership change RECOMPUTES `{centroid, spread}` + the direction's mood/style read, and therefore every
  placement read of a my-track mapped to it. **`delete` CASCADES:** the mappings pointing to it are removed and
  the affected my-tracks revert to un-flavoured coaching (D-INV-5) with a one-line note — never a dangling
  mapping (D-INV-13).
- **aspiration mapping** — `create` (user links my-track(s) ↔ direction(s)), `delete`. If a my-track is removed
  from the library, or a direction is deleted, the dependent mappings are dropped (D-INV-13).
- **The reference set moves, not your track — make it visible (F11).** Because a membership change can flip a
  placement read (in-zone → diverge) without the my-track changing, every placement read is **stamped with the
  reference set it was computed against** — direction name + member count + date ("vs Venetian Snares · 6
  tracks · 2026-06-24"). So a changed verdict is explainable, not spooky (D-INV-14, observability).
- **Atomic recompute [resolves prover G3].** A placement read and its stamp are written TOGETHER from the same
  recompute — a verdict is never shown with a stamp from a different reference-set version (no fresh verdict
  under a stale "vs N tracks · old-date"). If a recompute is interrupted, the prior consistent (read, stamp)
  pair stands until the next completes.
- **Actor:** the user for every create/edit/delete; the tool only recomputes derived reads + fingerprints in
  response. No automated direction/mapping authorship, ever.

### D.2 What we read & compare on: MOOD & STYLE (with the measured signals as evidence underneath)
We do NOT present a list of mechanical meters to compare on (Sasha, 2026-06-24: drop the axis taxonomy). The
dimensions a producer actually reads a track — and a reference — on are **mood** and **style** ("настроение").
Under them sits the credible **EVIDENCE POOL**: the existing measured signals (§A–§B) — arc/development shape,
palette (9-band tonal + brightness), density, meter, stereo width, self-similarity novelty — which the read
**cites** (a single signal OR a combination, D-INV-10). The signals are the PROOF and the map coordinates;
they are not themselves the things you "score against."

- **mood** — a holistic read (§D.0.1) over the constellation of signals. Facets live inside it: e.g.
  **hypnotic ↔ psychotic/hysteric** (steady-loop vs ruptured) is a *facet of mood*, read from self-similarity
  novelty + density + meter together — NOT a standalone axis with a threshold. Anchored to its evidence.
- **style / family** — a holistic family read (§D.0.1): "reads like the scsi-9 / deepchord lineage". Surfaces
  as a named family/tag per direction. ⟨DECIDE D-5⟩ whether it ever needs a numeric coordinate (for the map)
  or stays purely a read/label.
- (the set of read-dimensions can grow, but each is a READ over the evidence pool, never a hardcoded meter.)

**The web's role (Sasha, 2026-06-24, refined).** Pulling the reference ARTIST's known mood/style from the
internet (§D.5) is a **LEAD that helps connect the dots** — it helps explain WHY the signals you measured
relate to a felt mood ("the web says X is anxious, claustrophobic techno → and indeed my reading sees the
density never resolving + the meter staying rigid"). **But it is a lead, not evidence (playbook: a paraphrase
is a lead, not proof) — it must be CONFIRMED against the actual measured signals before it's stated (Sasha:
"но проверил!").** A web-suggested mood the signals don't support is NOT asserted; the signals win. Web mood
labelled external (D-INV-2); never the source of a stated fact.

**IN ZONE / DIVERGE is itself a read, not a threshold test** (§D.0.1). Whether my track "caught the vibe" of a
direction is the same-family judgement over the whole fingerprint, anchored to the evidence that makes it
so/not-so — not "within k·spread on axis X". The cloud's `{centroid, spread}` numbers still exist as EVIDENCE
the read cites and as MAP geometry (§D.2.1), but the in-zone *verdict* is read, not arithmetic. For a sub-N
direction (reduced mode, §D.4) there is no spread — the read degrades to a plain track-vs-track family read,
no spread cited.

### D.2.1 The fingerprint — the numeric side (map geometry only) [resolves prover F2]
The constellation map (§D.7/S1) needs coordinates, so — and ONLY here — the evidence pool is reduced to a
fixed numeric **fingerprint vector**. This is geometry, NOT a verdict; it never produces words (the words are
the holistic read, §D.0.1/§D.2).
- **Contents.** A FIXED, named list of scalars summarising the evidence-pool signals (§D.2): the development
  trends (energy/brightness/density/stereo, the §B.12 `_common.trend` scalars, already in [−1,1]), the
  palette (the 9-band tonal-balance vector + brightness centre), density level, meter-change rate,
  self-similarity novelty (mean + variance). Curves are reduced to these scalars; the vector has the SAME
  shape for every track (mine or reference).
- **Normalisation — FROZEN, not population-relative [resolves prover G1].** Each component is normalised
  against **fixed statistics computed ONCE from my library** (the per-component mean + std, stored as
  constants like the other calibrated thresholds). Every track — mine or a reference — is projected into that
  SAME frozen space. So a track's coordinates are a pure function of ITS OWN signals: adding/removing a
  reference, or toggling the switch, never moves any existing point. (An explicit, rare `recalibrate` action
  may re-derive the constants; nothing else does.) This is what makes D-INV-12 true — z-scoring against the
  changing on-map set would have moved every marker whenever the set changed.
- **Distance.** Euclidean in the normalised space (or cosine — ⟨DECIDE D-17⟩); deterministic — the same
  signals always give the same position (D-INV-12), because the normalisation is frozen (above).
- **Weighting.** ⟨DECIDE D-18⟩ equal weights to start, or emphasise some components; calibrate once on the
  library like the other settled thresholds, never per track.
- A direction's `{centroid, spread}` (§D.1) = the mean and dispersion of its members' fingerprint vectors.

**The map distance and the worded verdict answer DIFFERENT questions — and must never flatly contradict
[resolves prover F1].** The map distance = overall fingerprint similarity (all components, geometry); the
read (in-zone/diverge, §D.3) = the mood/style FAMILY judgement (a holistic subset, words). They can differ in
nuance (close overall yet a different mood, or vice versa) — that's legitimate and even informative. What is
FORBIDDEN is a flat contradiction: the read never says **in-zone** while the marker sits clearly OUTSIDE
the direction's region, nor **diverge** while clearly INSIDE it (D-INV-11). When they'd conflict, the read
must name which facet pulls it the other way ("sits inside their sound overall, but the mood reads colder").
- **This is an AUTHORING guard, not a unit test [resolves prover G2].** The map is a 2-D PROJECTION (⟨DECIDE
  D-12⟩) of the high-dim fingerprint, and projection distorts distance — so "inside/outside" is judged
  against the **rendered 2-D blob** (the drawn `{centroid, spread}` region), checked BY EYE like §B.13's
  based-on, not asserted by a test. "Clearly" = outside the blob by a stated margin (⟨DECIDE D-19⟩, e.g. >½ a
  blob-radius), so a point grazing the edge is never called a contradiction. (A machine-checkable version would
  test full-dim cloud membership instead of the projected blob — rejected, it re-introduces the threshold the
  reading stance dropped.)

### D.3 The placement read (my track vs a direction)
For a my-track mapped (§D.1) to a direction: a **mood/style read** (§D.2) of how it sits — **IN ZONE** (reads
as the same family) or **DIVERGE** — with the difference in plain words, each anchored to its evidence
("palette colder than theirs", "their arc ruptures, yours stays level"). Aggregate observation
**"своё / my own" [definition tightened, prover F9]** = a facet (mood or style) where my track **diverges from
EVERY direction it's mapped to**. It needs **≥2 mapped directions** to be meaningful — only then is "outside
all of them" a voice rather than a single divergence. With **one mapping** it is NOT computed (the read just
says "diverges from X" on that facet); in **reduced mode** (no cloud, §D.4) it is NOT computed (there is no
range to be outside of). Framed as **observation / possible voice, NOT an error and NOT a grade** (north-star). The read OFFERS options where it diverges ("you could let the meter
break here, the way they do"), never commands. This is a **READ** (two-layer principle), not an actionable
card — see §D.7 composition.

**The checkable contract [resolves prover F3].** The WORDS stay authored quality (like §B.13's based-on, not
unit-tested). The layer pins **two machine-checkable guarantees** + **one authoring guard** so a refactor
can't silently drift the core output:
1. **Anchored (machine-checkable)** — every placement statement references ≥1 named evidence signal, non-empty
   (D-INV-10), exactly like a card's `based_on`.
2. **Deterministic geometry (machine-checkable)** — the fingerprint vector + distance are a pure function of
   the signals, unit-tested on a fixture (D-INV-12); the map never moves a marker run-to-run for the same input
   (the normalisation is frozen, §D.2.1/G1).
3. **No flat contradiction (authoring guard, by eye)** — the verdict doesn't blatantly disagree with the
   marker's visible position (D-INV-11, §D.2.1/G2) — reviewed like based-on, not unit-tested.
**Empty/low-confidence read (F8, mirrors §B.12 flat-track):** when nothing anchors a read against a direction,
S2 shows an explicit "no clear read against this yet", never a half-empty panel; the map marker still appears
(geometry is independent of the worded read).

### D.4 Granularity: reduced vs full — ONE state machine, decided by member count [resolves prover A1/D-7]
Comparison granularity is NOT a separate user toggle and NOT a second "single reference" concept — it is a
property of the direction's size (Sasha: "может быть и просто трек с треком в reduced варианте"):
- **reduced (track ↔ track)** — a direction with **< N members** (§D.1). No aggregation, no cloud/spread; a
  direct mood/style read of my track against the reference(s) (§D.2). The light path; "своё"/in-zone-vs-cloud
  language is not used (there's no range to be in).
- **full (track ↔ direction/cloud)** — a direction with **≥ N members**. My track read against the
  `{centroid, spread}` (§D.1–§D.3). Adds the in-zone/diverge + "своё" reads.
Crossing N (adding/removing members, §D.1.1) moves a direction between the two — the single fact "how many
members" decides it, so there is exactly one notion of "single/few reference" in the spec.

### D.5 Artist metadata from the web (external enrichment — OPTIONAL, never core)
Sasha: "можешь ещё по исполнителю подтянуть данные о нём из интернета." For a reference's **artist**, optionally
fetch public info (genre/style tags, era, known techniques, bio) to ENRICH the mood/style READ (§D.2) and the
read's wording. **It is a LEAD, confirmed against the measured signals before stated (§D.2, "но проверил") —
strictly enrichment, never a source of the credibility-layer numbers.**
- **Fetch KEY = the reference TRACK's artist, not the direction name [prover F7].** Metadata is fetched per
  DISTINCT artist across a direction's tracks and attached to that artist — NOT to the direction. The direction
  NAME is never a fetch key (it can be arbitrary — "scsi-9 + deepchord" — or a vibe label, not a real act).
- **Per-direction aggregation [prover F7].** If all of a direction's tracks share one artist → that artist's
  info leads the direction's read. If the direction **spans artists** → present PER-ARTIST, never a single
  merged claim ("по данным сети: scsi-9 — …; deepchord — …"). A read never blends two artists into one fact.
- **Name ambiguity → omit, don't guess (CR-1).** An ambiguous artist string (the same name shared by acts, or
  no confident match) yields NO external info for that artist, never a guessed one.
- **Actor.** ⟨DECIDE D-8⟩ who triggers the fetch — automatic on reference import, or an explicit user action?
- **Safety (no-over-claiming, extends CR-1 §B).** Web facts are LABELLED as external ("по данным сети: …"),
  never merged into the measured/observational read as if track-coach measured them; never fabricated — if a
  fact isn't found, it's omitted, not guessed (CR-1 "don't cry wolf"). A web claim must carry its source.
- **Liveness.** The fetch can fail / time out / be offline. The reference feature MUST work fully without it
  (metadata is additive); a failed fetch degrades to "no external info", never blocks analysis or the map.
- ⟨DECIDE D-9⟩ source(s) + caching (don't refetch every render; respect that this is an offline-first tool —
  the widget is offline HTML).

### D.6 Recommendation re-flavouring — the payoff ("in the style of") [D-10 RESOLVED, Sasha 2026-06-24]
The deepest value (§D.0). When my track is mapped to a direction, track-coach's EXISTING recommendation cards
(§B.5–B.11) and the producer's read (§B.12) are **re-flavoured toward that direction** — same engine, same
findings, reference-aware. **Three levers, all in the OBSERVE-&-OFFER register** (Sasha's call: never a
command, even on cards — north-star, D-INV-1):
- **A. Re-order (presentation only).** Cards on a facet where I **diverge** from the direction surface higher;
  in-zone facets sink. **It NEVER adds or removes a card vs the un-flavoured view** (Sasha: "ничего не прячем")
  — same shown set as today, only the ORDER changes (like the §B.11 sort toggle). So re-flavouring is fully
  transparent + testable: mapped vs unmapped show the identical card SET (D-INV-15).
- **B. Re-frame the target (wording).** A card gains a direction, phrased as an OPTION: "the bass buries the
  lead around ≈290 Hz" → "…— and <direction> keeps that low-mid clearer; an option, if you want to lean that
  way." The reference gives the suggestion somewhere to point; it never becomes "do X".
- **C. Resolve intent by MARKING, never suppressing (the soul — and it closes §B.11.1's intent gap).** §B.11.1
  records that the coach **can't know** whether a trait (density, brightness) is a mistake or the point, so it
  won't prescribe. The reference is the missing intent signal — BUT, per Sasha, when my "problem" trait
  **matches** the aspired style, the card is **kept, not hidden**, and gains a note: "…though <direction>
  sits this dense too — maybe it's the point." Nothing is silenced; the ambiguity is SURFACED, not silently
  resolved. (When the trait DIVERGES from the style, B's option-framing applies instead.)
- **Credibility unbroken (extends D-INV-2):** every re-flavoured card still fires only on a real measured
  finding and still cites the SAME `based_on` (§B.13); the reference changes order / wording / the on-style
  note, never the truth or the underlying signal.
- **Two-layer respected:** re-flavouring touches BOTH the cards (still actionable, but option-framed) and the
  read (observation, "у <direction> это звучит так…"), each in its own register.
- ⟨DECIDE D-11⟩ off-by-default? A my-track with NO aspiration mapping shows the normal (un-flavoured) coaching
  exactly as today — the reference layer is purely additive and never changes a track that isn't mapped
  (D-INV-5). **Recommend: yes, off unless mapped** (re-flavouring requires an aspiration to point at).

### D.7 Surfaces & cross-section composition (prover-critical)
Two surfaces, BOTH shipped (Sasha chose "оба"):

**(S1) Constellation map** — ONE shared 2-D space where my tracks (markers) and reference clouds (centroid +
spread blob) appear together; visual **distance = similarity** over the signal fingerprint. The map GEOMETRY
is numeric (the one place numbers position things directly, §D.0.1) — similarity over the whole signal vector,
not the holistic word-read. ⟨DECIDE D-12⟩ the projection (similarity/embedding of the full vector to 2-D, vs a
user-picked pair of axes on x/y).
- **The reference SWITCH (Sasha: "можно свитч сделать").** A toggle controls whether references are shown
  **separate** (my library only) vs **overlaid** on the map. State: `refs ∈ {hidden, shown}`. ⟨DECIDE D-13⟩
  default value. This switch is the SAME control referenced by the catalog (below) — **one switch, one name**;
  do not let "the map overlay toggle" and "the catalog switch" read as two things.
- The constellation map is a **distinct view/surface**; it is NOT the synced player (§B.14). Composition with
  the player: ⟨DECIDE D-14⟩ does clicking a map marker open that track's widget/player, or just its read
  panel (S2)? State that the map does not carry transport state — it is a navigational/overview surface.

**(S2) Per-track read panel** — clicking my track opens the placement read (§D.3): "тянется к <direction>",
the mood/style in-zone/diverge read, "своё", each anchored to its evidence. It is a **READ** (observation), living in the producer's-read layer
(§B.12), NOT among the actionable cards — the two-layer line holds (cards stay strictly actionable §B.5–B.11;
the reference contributes a read + re-flavours cards via §D.6, it does not add a new card species).

**The reference catalog (the switch's other face).** References live in a **separate catalog** by default
(so third-party tracks never pollute my library catalog / its signatures, memory `track-coach-catalog-viz`),
with the **same switch** (above) merging/overlaying them onto the shared map. The catalog row signature for a
reference is the audio-only subset (no `.als` columns).

**Composition with the 3-view ladder (quick ⊆ Simple ⊆ Detailed, the monotonic ladder, memory
`track-coach-view-ladder`, INV-18/22).** The reference surfaces must obey the ladder:
- ⟨DECIDE D-15⟩ which reference surfaces appear in which view. Proposed (to confirm): **quick** = no reference
  surfaces (cheapest read, like it has no stems); **Simple** = the placement read summary (S2) + "тянется к
  X" line, no map; **Detailed** = full map (S1) + full per-axis read + the switch. Must be MONOTONIC: nothing
  in Simple that's absent in Detailed.
- **State across the axis (like §B.14 player).** The reference SWITCH (`refs hidden/shown`) is a stateful
  control. If it lives only in Detailed (where the map is), entering Simple/quick must **not strand** an
  overlay the user can't see or toggle — ⟨DECIDE D-16⟩ entering a view without the map RESETS/ignores the
  overlay state (mirror the §B.14 inv-6 rule: a control's state is only live where its surface is visible).
- The aspiration mapping (§D.1) is **content, not view-state** — it persists across views (it's authored data,
  like the .als); only the *display* of reference surfaces is gated by view.
- **Mode (reduced/full) composes too [prover F6].** Reduced vs full is NOT a per-view toggle — it's the
  direction's member count (§D.4), so a direction renders in its own mode inside WHATEVER view shows reference
  surfaces. On the Detailed map (S1): a **full** direction draws its centroid + spread blob; a **reduced**
  direction (sub-N) draws its member track(s) as plain markers, **no blob** — my track is a marker either way,
  distance still reads. **A reduced direction's markers still carry their direction's identity [resolves prover
  G4]** — a shared per-direction colour/glyph (+ label on hover) — so the user sees WHICH dots are "the Aphex
  direction" even without a blob; the grouping is never invisible just because the direction is small (⟨DECIDE
  D-20⟩ the exact visual). In Simple: the read summary is the cloud read for full, the track-vs-track read for
  reduced. The **switch** (`refs hidden/shown`) is orthogonal to mode — it shows/hides ALL reference markers
  and blobs alike; when every mapped direction is reduced (no clouds at all) the switch still toggles the bare
  reference markers. So the full product view × mode × switch is defined: view gates WHETHER references show,
  mode gates AS-cloud-or-as-markers, the switch gates VISIBLE-or-not.

### D.8 Invariants (reference layer)
**Safety — must NEVER happen:**
- **D-INV-1 (no grade).** No reference surface emits a score/grade/pass-fail. Only observation + offered
  options (north-star). "DIVERGE" is descriptive, never "wrong".
- **D-INV-2 (credibility holds, CR-1 extends).** A reference never makes track-coach state an unmeasured
  number as fact; web metadata (§D.5) is labelled external; a re-flavoured card (§D.6) still only fires on a
  real finding.
- **D-INV-3 (reference is audio-only).** No `.als`-derived surface is ever shown for a reference track; the
  reference catalog row has no .als columns.
- **D-INV-4 (no auto-guessed aspiration).** The aspiration mapping is only ever user-authored; the tool never
  silently assigns my track to a direction.
- **D-INV-5 (additive / no-mapping = unchanged) [scoped, prover F5].** A my-track with no aspiration mapping
  has its EXISTING widget — cards, producer's read, player — byte-for-byte as pre-0.9 (D-10/D-11). The
  constellation map (§D.7/S1) is a NEW additive view that shows ALL my tracks (mapped or not); appearing as a
  marker there is not a "change" to the track's widget. The layer never degrades the existing experience.
- **D-INV-6 (one switch, one name).** The reference visibility toggle is a single named control shared by the
  map overlay and the catalog; no view strands its state (composition with the ladder, §D.7).
- **D-INV-7 (separate catalogs).** Reference tracks never enter my library catalog's set/signatures unless the
  switch overlays them onto the shared MAP (display only) — the underlying catalogs stay separate.
- **D-INV-10 (every character word is anchored).** Every character / mood / style / in-zone read (§D.0.1, §D.2,
  §D.3) carries the real evidence — a single signal OR a combination — behind it (extends §B.13 based-on). A
  character claim with no evidence is omitted (CR-1), never rendered. This is the authoring guard on the read;
  no character is a hardcoded threshold or a hardcoded label (Sasha, 2026-06-24: no hardcoding, no regression
  anchors for now).
- **D-INV-11 (map and read never flatly contradict) [prover F1, AUTHORING guard — G2].** The read never claims
  **in-zone** while the marker sits clearly OUTSIDE the direction's rendered 2-D blob (by the D-19 margin), nor
  **diverge** while clearly INSIDE (§D.2.1). Checked by eye like §B.13 based-on, NOT unit-tested (the map is a
  projection). They may differ in nuance; on tension the read names the facet that pulls the other way.
- **D-INV-12 (deterministic geometry) [prover F3, machine-checkable].** The fingerprint vector + distance
  (§D.2.1) are a pure function of the measured signals — the same input always yields the same map position
  (unit-tested on a fixture) — BECAUSE the normalisation is frozen, not population-relative (§D.2.1/G1).
- **D-INV-13 (no dangling mapping) [prover F4].** No aspiration mapping ever points at a deleted direction or a
  removed my-track; delete/remove cascades to drop the dependent mappings (§D.1.1). The affected my-tracks
  revert to un-flavoured coaching (D-INV-5), never a broken reference.
- **D-INV-14 (a verdict change is explainable) [prover F11].** Every placement read carries the reference set
  it was computed against (direction · member count · date, §D.1.1), so a verdict that moved because the
  REFERENCE changed (not the track) is visible, not spooky.
- **D-INV-15 (re-flavouring is transparent — same card SET) [D-10, Sasha].** Re-flavouring (§D.6) changes a
  card's ORDER, WORDING, and may add an on-style NOTE, but never adds or removes a card vs the un-flavoured
  view, never suppresses an on-style "problem" card, and never changes a card's `based_on`. Mapped and
  unmapped render the identical card set; only order/text differ. Stays in the observe-&-offer register (no
  command), D-INV-1.

**Liveness — must EVENTUALLY happen:** (IDs are stable, not sequential — 8/9 are the original liveness pair.)
- **D-INV-8 (web fetch terminates).** Any artist-metadata fetch (§D.5) completes, fails, or times out, and the
  feature proceeds either way (never hangs the analysis/render).
- **D-INV-9 (reference analysis terminates / degrades).** Importing/analysing a reference either yields a
  placeable fingerprint (§D.2.1) + read, or reports which signals it couldn't compute (CR-1 style omission),
  never a partial silent state.

### D.9 Open ⟨DECIDE⟩ summary (nothing below is settled — Sasha's calls)
**Resolved by the reading stance (§D.0.1):** D-3 (hypnotic metric) and D-6 (in-zone threshold) became holistic
evidence-anchored reads, not metrics; D-4 (mood) likewise. No hardcoded thresholds, no regression anchors.
**Resolved by the prover-fix pass (2026-06-24):** D-7 (reduced vs point — now ONE state by member count, §D.4);
prover F1 (map↔read consistency, D-INV-11), F2 (fingerprint defined, §D.2.1), F3 (checkable contract, §D.3 /
D-INV-12), F4 (lifecycle + no dangling, §D.1.1 / D-INV-13), F5 (D-INV-5 scoped), F8 (empty-read state, §D.3),
F11 (verdict stamp, D-INV-14). D-2 has its TRANSITIONS pinned (§D.1.1); only the STORE/edit-surface is open.
**D-10 RESOLVED (2026-06-24, Sasha):** re-flavouring = three levers (re-order / re-frame-as-option /
mark-on-style), all observe-&-offer, never changes the card SET, never suppresses, always same `based_on`
(§D.6, D-INV-15). Closes §B.11.1's intent gap by SURFACING intent, not silently resolving it.
Still open (genuine policy/tuning):
D-1 member threshold N for a cloud · D-2 mapping store + edit surface · D-5 style: numeric coordinate or
read/label only · D-8 web-fetch trigger/actor · D-9 web source + caching (offline-first) · D-11 off-by-default
for unmapped tracks (recommend yes) · D-12 full-vector→2-D map projection · D-13 switch default · D-14
map-marker click target · D-15 reference surfaces per view (monotonic) · D-16 overlay-state reset across the
ladder · D-17 distance metric (euclidean vs cosine) · D-18 fingerprint component weighting · D-19 contradiction
margin · D-20 reduced-group visual.
**Also resolved (2026-06-24, second fix pass):** F6 (mode × view × switch composed, §D.7), F7 (web key =
per-artist, per-direction aggregation, name ambiguity omitted, §D.5), F9 ("своё" needs ≥2 directions, §D.3).
**Third pass (prover G1–G4):** G1 (normalisation FROZEN to library constants, not population-relative —
restores deterministic geometry, §D.2.1), G2 (D-INV-11 reclassified as an authoring guard + "clearly" margin
D-19, §D.2.1), G3 (verdict+stamp written atomically, §D.1.1), G4 (reduced direction keeps a per-direction
colour/glyph, D-20, §D.7). All prover findings F1–F11 + G1–G4 now folded; remaining items below are genuine
policy/tuning ⟨DECIDE⟩, not holes (added: D-17 metric, D-18 weights, D-19 contradiction margin, D-20 reduced
group visual).

## C. (RESOLVED) Increment-1 inputs that needed Sasha's domain call
All three original blocking ⟨DECIDE⟩ inputs are settled and shipped: (1) the dB floors — empty/don't-parse
`STEM_EMPTY_FLOOR_DB` = −55, colour floor `STEM_COLOUR_FLOOR_DB` = −60 (§B.2); (2) the musical definition
of **Drop** — strictly-lower predecessor, `LIFT` = 0.12, sustained-high = "Main" (§B.2, CR-5); (3) which
stems count as significant for repetition — `significant_stems()` gate (§B.3, CR-6). The method (write SPEC
→ product-prover → derive matrix/tests → fix code, bug → spec → test → code) is now the standing process,
not a one-time setup. Remaining ⟨DECIDE⟩ points are per-feature tuning thresholds, flagged inline above.

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
- **reference direction / cloud** (0.9, §D) = a named set of someone else's tracks (an album / a few albums)
  that stands for a *direction* you're reaching toward — a region in the shared feature-space, not a single
  target to copy.
- **aspiration mapping** (0.9, §D) = YOUR declaration of "this track of mine reaches toward that direction".
  Many-to-many, authored by you; the tool never guesses it.
- **in zone / diverge** (0.9, §D) = on a given axis, my track sits inside the reference cloud's range (caught
  the vibe) / outside it. Descriptive, never a pass/fail.
- **своё / my own** (0.9, §D) = where my track sits outside every reference I aimed it at — read as a possible
  voice, not an error.
- **hypnotic ↔ psychotic/hysteric** (0.9, §D) = a FACET OF MOOD (§D.2): how steady vs ruptured the track is
  over time (steady loop vs frequent breaks), read from self-similarity novelty + density + meter together —
  not a standalone axis or threshold; a sibling to the "how it develops" read (§B.12).
- **mood / style read** (0.9, §D) = the human-meaningful dimensions we read a track on; holistic, anchored to
  the measured signals (the evidence pool), optionally led by verified web info about the artist.
- **constellation map** (0.9, §D) = the overview where my tracks and reference clouds share one space and
  distance ≈ similarity; a navigational view, not the player.
