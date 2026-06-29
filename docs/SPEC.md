# track-coach — SPEC

track-coach reads your track (and, if you have it, your Ableton project) and tells you, in plain words,
what is actually happening in the music — so you can decide what to change. This document is what the
product IS: the things it reasons about, the rules it must never break, and why.

It is written **for a human to read first.** The short `tags` and codes at the ends of rule lines
(`CR-1`, `G12`, `INV-18`, `D-INV-10`, ⟨DECIDE⟩) are quiet handles for the test matrix and the reviewer
(`product-prover`) — a person can skip them; the prose carries the meaning. Edit history and the
session-by-session "why we changed it" live in `JOURNAL.md`, not here.

**How the layers stack:**
- **§A–§B.11 — the credibility layer** (shipped): make every number defensible before any advice is given.
- **§B.12–§B.14 — the artistic layer** (shipped): the producer's read, card evidence, the player.
- **§D — the reference layer** (0.9 design): compare against a direction and re-flavour the coaching.
- **§E — run completeness** (cross-cutting): one rule for partial runs / missing measurements that every
  layer above obeys, so a not-measured signal is never read or compared as a real zero.

This SPEC is the source; `TEST_MATRIX.md` is it projected into a checkable grid, and the tests are derived
from it (`spec → prove → matrix → test → code`). Points still needing Alexander's call are marked ⟨DECIDE⟩.

## 0. What it's for, and the gap it had to close

track-coach's whole value is **trust**: a true, specific reading you can act on — the arc, the masking,
the arrangement, in plain words.

The reason §A–§B exist: early on it "produced plausible-sounding WORDS, but the moment you dig in, it fell
apart" (Alexander). So before any coaching features, the numbers behind the words had to be made defensible.
That is the credibility layer, and it is the first thing this spec pins down.

## A. The building blocks (what track-coach reasons about)

The nouns the rest of the spec talks about. Each is a real measured thing with a unit and a valid range.

- **audio feature** — a measured curve or number over the mix: energy, brightness, density, modulation,
  stereo width, tonal balance, vitals. Each has a unit and a valid range.
- **stem** — one Demucs-separated layer of the track. It carries two states: whether it's **significant**
  (worth reading at all) and its **mapped identity** (which real project part it is).
  - **What "significant" means** (Alexander): a stem matters only if it has enough information in BOTH
    loudness AND time. Quiet the whole way, or one loud blip in silence, does NOT count. The real gate is
    **temporal coverage** — how much of the track the stem is actually above a loudness floor — not a
    single peak. (So a stem at median −76 dB with one −16 dB stab is not significant; a quiet stem with
    steady hits across the track is.) States: `significant` / `insignificant (quiet/empty)` / `unknown (not
    measured)` — the third for a run that lacks the gate's inputs (quick mode, a partial stem), which must NOT
    be dropped as empty (§E / RC-INV-11).
    - _Known debt (Alexander's call — leave the code, record the gap):_ the shipped gate is loudness-only —
      `loud_level` (85th-percentile broadband) ≥ −55 dB (`STEM_EMPTY_FLOOR_DB`). That correctly rejects a
      single stab, but the **time-coverage half above isn't built yet** — a quiet-but-steady stem (e.g. a
      −58 dB perc loop ticking the whole track) is wrongly dropped as "empty". No real track has hit this,
      so the fix waits: when one does, add an OR-branch (significant if loud enough **or** its onsets cover
      enough of the track). Until then the gate is whole-track + loudness-only by design (and so is
      per-scene significance — deferred too). `tags: STEM_EMPTY_FLOOR_DB=−55 · CR-2a/CR-4a deferred · §B.1`
  - **mapped identity** + a confidence (clear / mixed / nomatch / empty), from `map_stems`. The raw Demucs
    label is only an approximation, never the identity — Alexander makes electronic music, so a "vocals" stem
    is usually a synth. See [[track-coach-stem-labels]].
- **stem band energy** — one stem's energy in a frequency band. It can be real, or **leakage** — another
  stem bleeding into this one's file (`rhythm_quality` measures the pairwise bleed). See "bleed" in the
  terminology.
- **scene** — a named, lettered section of the track (Intro / Build / Drop / Breakdown / …). The **name**
  is a musical claim about what the section does; the **letter** is a claim about what returns later.
- **.als part** — one project track, group, or return, with its automation and clips.

## B. The credibility layer — never say more than the numbers support

This is the foundation: one rule, and the concrete consequences of taking it seriously. Everything below is
shipped and tested. The detail under each point is precise on purpose (it's what the tests check); read the
bold headline of each to get the shape, drop into the detail when you need the exact threshold.

**The one rule (CR-1).** track-coach never presents, as fact, a number it can't stand behind. If the input
for a claim is too weak to be real, the claim is **left out with a one-line note**, not dressed up as a
finding. "Don't cry wolf, and don't paint silence."

**What that forces (each first found by deed on a real track — Lazy_Sparks):**

- **CR-2 — empty stems are omitted, not parsed.** A stem whose broadband level is below the floor is
  dropped from analysis: no notes / rhythm / masking / per-stem viz are computed for it (saves compute),
  and the widget shows "stems X, Y omitted — too little material to read." Evidence: Lazy_Sparks vocals
  −92 dB (peak −61), piano −88 dB (peak −42) — silent, yet currently shown. ⟨DECIDE⟩ floor value →
  **SETTLED §B.2: −55 dB broadband (`STEM_EMPTY_FLOOR_DB`)** — reused the existing empty-caveat floor, no
  dedicated peak floor.

- **CR-3 — per-stem visuals are gated on ABSOLUTE level, not per-stem normalization.** A silent stem
  must render as empty, never full-colour. Evidence: vocals sits at −92 dB yet its loudest band
  normalizes to full colour → looks like content. ⟨DECIDE⟩ the dB at which a band reads as "present" →
  **SETTLED §B.2: −60 dB absolute (`STEM_COLOUR_FLOOR_DB`)**, not per-stem max.

- **CR-4 — bled energy is not attributed to the wrong stem.** Where a stem's band energy is dominated by
  measured leakage from another stem, it is caveated or not shown as that stem's content. Evidence:
  guitar low −40 dB > its own mid −46 dB; bass low is −26 dB (~14 dB louder) and bass↔guitar leakage =
  0.24 → the guitar's "low/red" is bass bleed. ⟨DECIDE⟩ suppress vs caveat → **SETTLED §B.3 (G9): caveat,
  not suppress** — `leakage_caveats()` flags the loudest band when a carrier owns it ≥ `LEAK_LOUDER_DB`(10)
  louder AND r ≥ `LEAK_CORR_MIN`(0.2); windowed time-refinement (CR-4a) deferred.

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

Raw Demucs labels (`vocals`/`guitar`/…) are wrong for electronic music ([[track-coach-stem-labels]]): Alexander
makes synths, not a band. So we name a SIGNIFICANT stem by what its SOUND measurably IS — **never by which
instrument made it, EXCEPT the `bass` and `drums` families, which Demucs separates reliably and which Alexander
confirmed we read reliably (the low-end exception, §B.7)** — and the label must be DETERMINISTIC (same track → same label every run; no per-run
renaming) and gated to `significant_stems()`. Same credibility family as CR-1: a label is a claim, so it
must be backed by a measurement, marked `approx` (shown `≈`) when the measurement is indicative not certain.

- **G12 (0.8.3) — the two coarse axes.** freq-role (which third of the spectrum carries the energy,
  EXCLUDING CR-4-bled bands) × percussive-vs-sustained (`onset_rate ≥ ONSET_PERCUSSIVE`). Gives:
  low·perc=`kick`, low·sus=`bass` (both `clear` — Alexander confirmed we read the low end reliably), mid·perc=
  `perc`, high·perc=`hats`, high·sus=`air`. mid·sustained was the honest umbrella **`tonal`** (`approx`) —
  it DELIBERATELY did not claim melody-vs-pad, because freq+onset can't split those.

- **G13 (0.8.6, THIS pass) — split the `tonal` umbrella into 5 measured buckets** (Alexander's call,
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
    of the five (relative loudness, not a content measure) — Alexander was shown this when he chose 5 buckets;
    it stays `approx` and the JOURNAL flags it for tuning._
  - else POLY: envelope CONTINUITY (`masking.sustain`) ≥ `PAD_SUSTAIN_MIN` → **`pad`** (a held drone),
    else → **`chord`** (rhythmic stabs). `sustain` = sounding-frames ÷ frames-in-active-span (a drone-pad
    reads ~0.88, a chord/arp ~0.49 on real stems). Was mean note duration — that NEVER fired because
    basic-pitch fragments held synths into ~0.2 s notes; the envelope holds up where note length didn't.
  - **fallback:** a mid·sustained stem with NO transcribed notes (basic-pitch found nothing, or transcribe
    was skipped) keeps the honest **`tonal`** umbrella INTERNALLY — we never invent a melody/chord verdict
    from missing data (CR-1). **It is DISPLAYED as the base role `mid`, never the word `tonal`** (§B.7 INV).
    All five new labels are `approx`.
  - **NO vocabulary / NO ML text-prompts** — Alexander explicitly rejected defining prompt vocabularies
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

- **G14 (0.8.6, THIS pass) — robust freq-ROLE via a HIGH-PASS drop (Alexander's idea, 2026-06-21).** G12 typed
  the role from the loudest band-group, which broke on real intermittent stems two different ways (found by
  deed): typing by per-band **median** makes a bass that only hits some beats read as ~silence in every band
  (its role becomes noise → it got mislabeled mid/"melody"); typing by **loud-level** (85th pct) instead
  picks up a guitar's loud kick-BLEED in the low and mislabels the guitar "bass" (the exact CR-4 failure).
  Alexander's fix sidesteps the bleed argument entirely: **high-pass the stem (ignore `sub`+`low`) and ask how
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

### B.5 Individual recommendations — name the PART, not a template (G16, 0.8.8, Alexander's #2)
Alexander's standing complaint (2026-06-20, looking at the Lazy_Sparks render): recommendations "feel samey
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
- **EVALUATION (Alexander's metric):** specificity up = fewer generic-type cards, more named-stem/time cards.
  Deed on Fragile: the one generic masking card → two named cards ("bass buries the lead 18%", "…the
  melody 15%"), piano (empty) dropped.

### B.6 The `late_entry` rec — name the part, never the raw Demucs name (G17, 0.8.9, Alexander's #2 cont.)
Continuing #2 ("wire per-stem character into MORE recs beyond masking"): the `late_entry` rec — fired
when a stem is silent for almost the whole track and only appears near the end — was the last LIVE rec
still printing the **raw Demucs stem name** (`Stem "{st}" is silent… bring "{st}" in earlier`). That
violates the hard requirement [[track-coach-stem-labels]] (Alexander makes electronic music — a `vocals`
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
  Alexander asked "the card existed before — what's the point?").** late_entry was firing on the `vocals`
  stem whose late spike only reached **−61 dB** (peak), median −81, stemmap verdict `empty` — i.e. a
  near-silent SEPARATION ARTIFACT at the very end, not a musical event. Renaming it honestly is cosmetic;
  the card shouldn't fire at all. So late_entry is now GATED: it fires only when the entering peak clears
  the real-content floor `arr[peak] ≥ STEM_EMPTY_FLOOR_DB` (−55 dB). This is CR-1 "don't paint silence"
  applied to recs (same floor `significant_stems` uses), and it's peak-based (not `loud_level`/`empties`)
  on purpose: a GENUINE late accent is silent most of the track so its 85th-pct is low — only its PEAK
  proves it's real content. On Lazy_Sparks this card now correctly DISAPPEARS. INV: late_entry never
  fires on a stem whose entering peak is below the empty floor.

### B.7 ONE plain label per stem — kill the label salad (0.8.11, Alexander s14)
Alexander, looking at the real Lazy_Sparks render: *"what is this salad?"* The stem area had THREE overlapping,
half-confident systems stacked on each stem — (1) measured `character` with a `≈` "uncertain" prefix,
(2) the stem↔project map verdict (which ALSO used `≈`, meaning the OPPOSITE — "matches a family"), and
(3) per-stem repetition letters. Worse, the headline character often degraded: on Lazy_Sparks the **bass
stem read `≈ tonal`** (G14's high-pass drop didn't trip on a synth bass with mid harmonics), the whole
`drums` stem read `kick`, and empty stems STILL leaked the **raw Demucs name** (`vocals`) into the lane
label (G17 had only fixed the recs, not the panel). Decision — collapse to ONE plain label per stem:
- **Trust the stem for the reliable low-end families.** Demucs separates bass & drums cleanly and Alexander
  confirmed we read the low end reliably, so a `bass` stem is **"bass"** (we do NOT run it through the G14
  high-pass that demoted it) and a `drums` stem is **"drums"** (not "kick" — kick is a drum-breakdown
  sub-part). Only these two exact families are trusted by name; every other (electronic) stem name stays
  untrusted and is read by measurement ([[track-coach-stem-labels]]).
- **Character only when confident; else the base role.** A confident G13 determination (lead/melody/
  chord/pad) shows; otherwise the stem shows its plain **base role ("mid"/"high")** — never the jargon
  "tonal", never a `≈`-uncertain marker (Alexander’s call: when uncertain, fall back to the base role).
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
- **OPEN (asked Alexander):** where the map verdict is genuinely `clear` AND the matched real project track
  looks meaningful (e.g. guitar→"Guitar"), fold that real name in as the primary label instead of the
  base role "mid"? Held because `clear` matches are noisy (drums→"7-Impulse"). NOTE: 0.8.12 already put the
  real name in the SUB-line, so if it's ever promoted to PRIMARY, drop the sub-line duplicate (else
  "Guitar / Guitar").

### B.8 Freq-role from the per-stem FREQUENCY ANALYZER (centroid) — G18, 0.8.14/0.8.15 (Alexander's idea, s14)
Alexander (s14): *"you can run the frequency analyzer on each stem too."* We already run full spectral
analysis on the MIX; per stem we only had 6 coarse bands + flatness. So `masking.py:stem_spectrum(y)` now
computes, per stem (reusing the loaded audio, one extra STFT):
- **spectral centroid** (Hz) — energy-weighted "centre of gravity" of the spectrum = where the stem's
  energy sits (≈ perceived brightness). Power-weighted across frames (reflects "when it plays").
- a **32-bin log-frequency spectrum** profile (dB, peak-normalised) — emitted as `spectrum`/`spectrum_freqs`
  for a future per-stem spectrum VIZ (data is forwarded into the widget payload at 0.8.16; the canvas draw
  is deferred until it can be visually verified).
- **G18 — freq-role now from the centroid (supersedes G14's high-pass for the role).** A SUSTAINED
  (non-trusted) stem's role = `low` if `centroid < LOW_CENTROID_HZ` (250), `high` if `> HIGH_CENTROID_HZ`
  (3500), else `mid`. This is the robust signal Alexander asked for — it fixes the synth-bass-→-`tonal`
  failure at the root (a 6-band high-pass drop was a poor proxy for "where the energy is"). The **G14
  high-pass drop is kept ONLY as the fallback** when the masking carries no centroid (pre-0.8.14 jsons),
  so nothing regresses. Trusted `bass`/`drums` (§B.7) still short-circuit before any role computation.
- VERIFY-BY-DEED (Lazy_Sparks, regenerated masking): centroids bass 117 / drums 203 / piano 602 /
  vocals 633 / other 942 / guitar 1008 Hz; resulting labels bass→bass, drums→drums, guitar→mid, other→
  lead — identical to 0.8.11 but now centroid-derived, no regression. Unit tests: `G18_CentroidFreqRole`.
- INV: when `spectral_centroid[st]` is present, a non-trusted sustained stem's role is a pure function of
  it (deterministic); `< LOW_CENTROID_HZ` ⇒ role `low` ⇒ label `bass`.
- ⟨DECIDE⟩ thresholds: `LOW_CENTROID_HZ`=250, `HIGH_CENTROID_HZ`=3500 (tune as tracks land). **OPEN (F5,
  asked Alexander):** should an UNTRUSTED low-centroid stem read `bass`, or a neutral `low` so "bass" stays
  identity-only? Currently it reads `bass` (honest about the frequency range it occupies).
- IDEA (Alexander s14): split into MORE than 32 bins to drive concrete MIXING recs ("cut 3 dB at 380 Hz on
  the bass") — **DONE: §B.9 (G19) named the spot; 0.8.20 bumped the grid 32→64 bins** (see §B.9 note).

### B.9 PRECISE masking frequency — name the cut spot, not the whole band (G19, 0.8.17, Alexander's idea a)
The §B.5 masking card said *"the bass buries the lead around **250–600 Hz**"* — the whole coarse band, the
same range for every conflict. Alexander's s14 idea (a): the per-stem spectra (§B.8 `spectrum`/`spectrum_freqs`)
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

### B.10 "Where does it get boring?" — the development plateau (G21, 0.8.19, Alexander's idea)
Alexander (2026-06-22): *"for evolving tracks, the idea is to show at what point it gets boring."* For an
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

### B.11 Per-stem measurements — run the track tools on each stem (Alexander 2026-06-22)

In plain words: we already measure energy/brightness/density/etc. on the whole mix; this points the same
tools at each significant stem, and shows a card ONLY when a stem behaves notably differently from the rest
of the track (divergence, scored and budgeted — not "more numbers"). The detail below is the scoring and
the honesty gates.

**Alexander's model (verbatim intent):** *"we had a bunch of tools pointed at the whole track. one of those tools was stems. let's point everything (except stem separation itself) at each individual stem."* The
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

- **CR-11 (the credibility consequence — Alexander's core objection, do NOT skip).** *"we haven't validated the hypothesis — will it actually show useful info, or just more stuff that's hard to make sense of."* So per-stem output is gated on **usefulness, not volume**: a per-stem card fires **only when the
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
  - **Score importance, then budget the TOTAL — no fixed per-stem cap (Alexander 2026-06-22).** Do NOT hard-cap
    cards per stem. Instead: (1) each candidate insight gets an **importance score** (how big the divergence,
    how clear/actionable it is); (2) all candidates — the existing track-level recs AND the new per-stem/composite
    ones — compete in ONE ranked pool; (3) show the top by score up to a **total card budget** kept near today's
    "normal" count, not an explosion. ⟨DECIDE⟩ the budget (calibrate to the current count).
  - **Diversity, so one stem can't hog the list.** A balance rule so the top cards aren't all about the drums
    (e.g. a per-source soft quota / penalty for repeats from the same stem). ⟨DECIDE⟩ the rule.
  - **Cards can be COMPOSITE, not one-per-stem (Alexander 2026-06-22).** A card may combine signals — two stems
    diverging together, or a stem-vs-track relationship ("energy rises but the drums thin out") — not just a
    single stem × single measure. The scoring/budget pool holds composite candidates alongside per-stem ones;
    the "one stem, one measure" shape is the simplest case, not the only one. A naive per-stem enumerator is
    explicitly rejected.
  - **Correlated measures collapse — SMART (Alexander 2026-06-22, refined).** Energy/density are correlated
    activity/loudness axes, so a single PART firing on both reads as a pile-up ("The mid — sparser" + "The mid
    — quieter"). Collapse per stem: **same direction** (both "more" or both "less" — quieter+sparser restate the
    same "this part pulls back") → keep the **strongest** only; **opposite directions** (louder BUT sparser — a
    genuine contrast: bigger yet fewer hits) → **MERGE into ONE richer card** ("louder but sparser") so the
    contrast survives instead of being dropped. Either way each part yields at most one divergence card.
    Composite cards (a different KIND) are unaffected. Code: `collapse_correlated` before `select_cards`.
  - **"Show more" on demand (Alexander 2026-06-22).** The default budget stays tight (only the high-score cards).
    A separate control / command lowers the score threshold to reveal the next tier of lower-rated candidates
    for a user who wants to dig — the strict default is what's shown first, the deeper set is opt-in (it never
    changes the default view, so the calm/Simple read stays uncluttered). ⟨DECIDE⟩ the lowered threshold.
  - **Per-measurement validity (prover F5).** Significance (loudness+time) doesn't make a SPECIFIC measure
    meaningful — brightness of an all-sub bass, stereo width of a mono stem, is junk. Each measure carries its
    own precondition (brightness only with real high-freq energy; stereo only when not effectively mono); unmet
    → omit that card (same "don't paint silence" as CR-1).
- **USEFULNESS IS DEFINED OBJECTIVELY — the system self-judges, no per-track human approval (Alexander 2026-06-22:
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
- **PROMINENCE — a near-silent stem ranks BELOW the louder ones (Alexander 2026-06-22).** *"If a stem is
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
  future change can't quietly fill the budget with noise. Alexander's eye is a one-time sanity check on those 3
  fixtures while I calibrate, never a per-track requirement.
- **Back-compat (prover F6).** A run with no `result_core_<stem>.json` (pre-B.11) yields no per-stem cards and
  NO error — same graceful fallback as pre-0.8.14 masking falling back to the band range.

- **WHERE it shows (Alexander 2026-06-22).** Per-stem cards live in the **Detailed view only** by default (they
  are depth, not the headline). **Promotion to Simple** only for a STRONG divergence (⟨DECIDE⟩ a higher
  threshold) — *"if there's something really important there, why not put it in Simple too."* Respects the view ladder
  (`quick ⊆ Simple ⊆ Detailed`, the view ladder — INV-19 in `docs/TEST_MATRIX.md`): a card promoted to
  Simple is therefore also in Detailed.
- **SORT TOGGLE (Alexander 2026-06-22) — Detailed only.** Today the advice cards are ordered by **urgency**
  (`build_widget.py:1493` `_rank crit<do<concept`) while the lettered cues a/b/c on the timeline are ordered
  **chronologically** (`build_widget.py:1999`) — a deliberate-but-confusing split. Add a Detailed-only toggle
  to switch the CARD list between **by urgency** (default, unchanged) and **chronological** (matching the
  letters). Pure presentation reorder; never adds/removes a card. ⟨DECIDE⟩ default = urgency (current).

#### B.11.1 Resolution (2026-06-22) — BRIGHTNESS is descriptive, not a prescriptive per-stem card (Alexander)
When A1 (per-measure validity) reached brightness, Alexander rejected the *premise*, not just the threshold:
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
   judgement) OR a small per-stem brightness visualization. Deferred — Alexander leans viz-later.
3. **Broader steer (informs E2 — widen the funnel).** "How would you know it's an error?" applies to ANY
   per-stem MEASURE divergence: most are descriptive facts, not defects. So widening `PER_STEM_MEASURES` must
   distinguish **arc-relevant / actionable** axes (worth a prescriptive card) from **descriptive** axes (belong
   in a viz / one balance card). Default to descriptive unless an axis has a defensible "this fights the track"
   reading. This is a stronger filter than raw validity and is why E2 widens AFTER this, not before.

### B.12 Producer's read — name HOW it develops, flag an idle axis (2026-06-23, Alexander — the artistic layer)
The Producer's read is authored prose — *"here's what I hear, and my thoughts as I go"* (Alexander). Its job is
**OBSERVATION**, not a command: the actionable "do X" lives in the **cards**; the read carries thinking-aloud
+ technical remarks (the two-layer principle, memory `track-coach-two-layers-cards-vs-read`). So the read MAY
state a precise observation or a soft flag **without** forcing a fake action item.
Alexander (2026-06-23): the read shows the curves and what's heard, but never states a short **verdict of which
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

### B.13 Card evidence — every card names where it came from (the "based-on" line; 2026-06-23, Alexander)
Alexander: *"show which signals drove each card."* Every recommendation card carries a plain
line saying what it is **based on**. The credibility trap (memory `track-coach-card-evidence`): a raw lone
number/tag says nothing — *"dynamics 30.7 — is that a lot? measured in what, oranges?"* (Alexander). So the based-on line is
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
- **Build order = MEANING then NAVIGATION** (Alexander): (1) the plain based-on line per card — done 0.8.27;
  (2) **NAVIGATION (0.8.28):** clicking a timecoded card seeks the playhead to that moment AND scrolls the
  main graph into view (already wired), now plus a brief **attention pulse on the graph container** so the eye
  catches that the playhead jumped there. The pulse is a **CSS/DOM class toggle on the graph panel — it does
  NOT touch the canvas drawing** (deliberately low-risk: the canvas render is the fragile surface we never edit
  blind). A deeper per-lane / per-part highlight (light up the exact lane the card is about) stays deferred —
  it needs canvas work and a live render review.
- **Subtle in the UI** — transparency, not overload (Alexander's "don't overload" steer). A quiet muted line under
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
  1. **One mode at a time (Alexander, 2026-06-21 — he called the mixed state wrong).** After ANY sequence of mute/solo toggles,
     never `(some stem muted) AND (some stem soloed)` simultaneously. `toggleStem` guarantees it.
  2. **Solo resolves gains.** When `anySolo`, the audible set is EXACTLY the soloed stems (every non-soloed
     stem is muted), regardless of individual mute flags.
  3. **Mute resolves gains.** When NOT `anySolo`, audible(stem) = `!stem.mute`.
  4. **Seek preserves transport AND mix.** A seek does not change any stem's `{mute, solo}` and resumes iff
     it was playing (a seek while paused stays paused). So: solo a stem → seek while playing → the same one
     stem is still the only one audible AND playback continues (INV-33 generalised to the combination).
  5. **Seek clamps.** The resulting time is always in [0, dur]; a gutter/negative/over-dur click never seeks
     out of range.
  6. **The player COMPOSES with the VIEW axis — solo/mute is a Detailed-only capability (2026-06-23, Alexander
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

## D. Reference & Compare — «хочу как Aphex Twin» (0.9)

Point track-coach at someone else's music as a *direction* you're reaching toward, see where your track
already sits relative to it and where it goes its own way, and let that gently re-flavour the coaching you
already get — "more in the style of X". Not a copy: a direction. This section is written to be read by a
human first; the short `tags` at the ends of rule lines are handles for the test matrix and the prover.

> This is a 0.9 DESIGN, proven by `product-prover` but not yet built. Everything marked ⟨DECIDE⟩ is an open
> call. Edit history lives in `JOURNAL.md`, not here.

### D.0 What this is for

The point is **not to clone a reference 1:1.** It is to: aim your track at a direction (a track, or a whole
album / a few albums by an artist), *understand that direction* — its mood, its style, how it moves — then
**see where you're already close and where you're your own**, and have track-coach's existing advice + read
start speaking "in the style of" that direction. The comparison (the «leans toward» line + a written read) is
how you SEE the direction; the re-flavoured coaching is the point of it.

It stays true to the two standing principles: it **observes and offers, never grades** (the artistic
north-star), and it keeps the **two layers** separate — the cards stay the actionable layer, the read stays
the observation layer. A reference never produces a score.

### D.1 Terminology

Every term used below, defined once.

- **reference track** — a track by someone else, analysed by the same pipeline as yours but **audio-only**
  (no Ableton project, ever). Lives in its own catalog, separate from your library.
- **reference direction** (or **cloud**) — a set of reference tracks you give a name (one album, or a few,
  e.g. "Venetian Snares", "scsi-9 + deepchord"). It stands for a *direction you're reaching toward*, not a
  single target. A big enough set forms a **cloud** (a region with a centre and a spread); a small one is
  just a point.
- **aspiration mapping** — *your* statement "this track of mine reaches toward that direction". You write it;
  the tool never guesses it. It's many-to-many: one of your tracks can aim at several directions, one
  direction can be the aim of several of your tracks.
- **mood / style read** — the human-meaningful things we actually read a track on (e.g. hypnotic vs
  hysteric, cold vs warm, dense vs airy). Holistic, in words.
- **evidence pool** — the real measured signals underneath the read (arc, palette, density, meter, stereo,
  repetition/novelty). They are the PROOF a read cites, and the coordinates of the fingerprint. They are not a
  checklist you "score against".
- **fingerprint** — the **full-dimensional** numeric vector of one track's signals. It grounds the
  in-zone/diverge verdict (read in full dimensions, D-INV-19) AND the «leans toward» nearest-direction
  computation (§D.10). It is read in full dimensions — there is **no** lossy projection of it.
- **the «leans toward» line** — the compact surface (a catalog column + a Detailed plaque chip) naming the
  reference direction this track's fingerprint sits nearest to; in Detailed it expands to an **up-to-three
  nearest-first selector** (§D.10.1) and a per-direction **web-style plaque** (§D.10.2). See §D.10. (There is
  **no** 2-D/3-D constellation map — dropped 2026-06-26: we show the nearest centroid, not a flattened picture.)
- **the read panel** — click your track and read, in words, how it sits against a direction.
- **in-zone / diverge** — on a facet, your track reads as the same family as the direction (in-zone) or not
  (diverge). Descriptive, never pass/fail. **It is a per-facet test in FULL-dimensional fingerprint space**
  (your track within the cloud's per-facet spread = in-zone). It is read directly in full-dimensional
  fingerprint space, never off a projection (there is no map); a per-facet drop can still read "diverge"
  even when the overall fingerprint sits near (D-INV-19).
- **«своё» (my own)** — a facet where your track diverges from *every* **cloud** direction it's aimed at —
  read as a possible voice, not an error. Reduced directions (too few members for in-zone/diverge) do NOT
  participate: «своё» needs a real zone to be outside of, so a track aimed only at reduced directions has
  no «своё» computed (D-INV-16).
- **reduced vs full** — comparing against a small reference (track-vs-track, no cloud) vs a real cloud.
- **the switch** — one toggle that shows/hides the reference surfaces (the §D.10 column + the plaque chip).
- **re-flavouring** — biasing your existing cards + read toward a direction ("in the style of X").
- **artist info (the web)** — optional public info about a reference's artist, used as a *lead* to understand
  the mood — always confirmed against the signals before it's stated.

### D.2 The reading stance (the idea everything rests on)

Character — psychotic, hypnotic, a mood, a style — is **not a single number with a threshold.** That path
templated and went stale once already. Character lives in how *many signals relate to each other*, which is
exactly what a holistic read does well: with no metric given, the read once called `wobble drift` psychotic
and the other two hypnotic, purely from the signals.

So the layer splits cleanly:

- the **measured signals stay the credible floor** — unchanged, deterministic, the same evidence as today;
- **character is a read over the whole constellation** of them, in words, not a formula;
- the one rule that keeps it honest: **every character word is backed by a real signal, or a combination of
  signals** — "psychotic *because* the novelty spikes and the density ruptures and the meter breaks together
  at 1:40 and 2:10." Synthesis writes the words; the numbers prove them. No anchor → it isn't said.

`tags: anchored-read · D-INV-10`

### D.3 Building blocks

What the layer is made of. Each block: the plain idea, then its precise properties.

**Reference track.** A third-party track run through the audio half of the pipeline only — it never has an
Ableton project, so none of the project surfaces (arrangement, automation, locators) ever appear for it. It
carries an *artist* name and, optionally, web info about that artist. It lives in a separate reference
catalog so other people's music never mixes into your library's signatures. `tags: audio-only · D-INV-3`

**Reference direction (cloud).** A named set of reference tracks. A direction with **enough members** is a
*cloud*: it has a centre and a spread, and your track can be read as in-zone or diverging from it. A
direction with **too few** members is *reduced mode* — just track-vs-track, no spread, no "in-zone" talk.
The same single fact, "how many members", decides which it is — there is no second separate "single
reference" concept. The count is **placeable members only** — a reference missing a fingerprint axis is
catalogued but contributes no coordinates (D-INV-9), so it doesn't count toward the cloud threshold. A
direction emptied to **zero** members persists as a named-but-inert reduced direction (your mappings to it
survive); it is never auto-deleted. ⟨DECIDE D-1⟩ how many placeable members make a cloud.

**The fingerprint (the numeric side).** The «leans toward» line and the in-zone/diverge verdict need
coordinates, so each track's signals are boiled down to a **full-dimensional** vector of numbers (the
development trends, the tonal palette, density, meter rate, repetition). This is geometry: it grounds the
**geometric** in-zone/diverge verdict (D-INV-19) and the nearest-direction «leans toward» (§D.10) — but it
never writes the **worded** mood/style read (that's §D.2's holistic synthesis, anchored to signals). The
numbers are
**normalised against statistics over the current set** (your library + the reference groups in play) — so a
coordinate is meaningful relative to everything it's being compared against, not in a vacuum. The honesty
rule is NOT "never recompute" — it's **never move silently** (Alexander 2026-06-24): a coordinate is a
deterministic pure function of *(its signals, the current normalisation epoch)*. When the inputs change — you
add library tracks, or add/remove members of a reference group — every dependent fingerprint and read
**recomputes together and is re-stamped** (D-INV-12). The skill detects the change on each run by a **content
hash of the dependency unit's inputs — the member set's track ids + the normalisation epoch id** — NOT the
human-readable "name · count · date" stamp: the hash catches an *equal-count swap* (drop track A, add track B
— the count is unchanged but the cloud moved) and a *library-normalisation change* (which the reference-set
stamp wouldn't see), so nothing moves unnoticed. A read recomputes iff its input hash differs from the hash it
was last computed against; the skill surfaces that it recomputed, so a reading that moved is always explained,
never spooky. The **dependency unit is a reference group together with the set of your tracks aimed at it** —
a change on EITHER side recomputes that unit (Alexander’s framing: each of his track-groups can have a matching reference group).
⟨DECIDE D-17⟩ distance measure (straight-line vs angle); ⟨DECIDE D-18⟩ whether some signals weigh more.
`tags: recompute-on-change · D-INV-12 · D-INV-14`

**Mood / style read + the evidence pool.** We read a track on **mood** and **style**, in words, over the
constellation of measured signals beneath. "Hypnotic ↔ psychotic" is a *facet of mood* (steady loop vs
ruptured), read from repetition + density + meter together — not its own dial. Style is a family read ("reads
like the scsi-9 / deepchord lineage"), usually a named tag. Style stays a pure label (⟨DECIDE D-5⟩ dropped
2026-06-26 — the map that might have needed a style number is gone).

**Artist info from the web (a lead, never a fact).** For a reference's artist we may pull public info (genre
tags, era, known techniques) to help explain *why* the signals read as a certain mood — "the web says X is
anxious, claustrophobic techno, and indeed the density never resolves and the meter stays rigid." But it's a
lead: it must be **confirmed against the measured signals before it's said**, it's always labelled as coming
from the web, and if it isn't found or is ambiguous it's simply left out — never guessed. The fetch is keyed
on the *artist of the track*, not the direction's name (which can be arbitrary); a direction spanning several
artists shows them separately, never blended into one claim. ⟨DECIDE D-8⟩ what triggers the fetch; ⟨DECIDE
D-9⟩ which source + caching (we're offline-first). `tags: web-is-a-lead · D-INV-2 · D-INV-8`

**Aspiration mapping.** Your authored link from your track(s) to direction(s). The tool never assigns it.
Where it's stored and how you edit it is open. ⟨DECIDE D-2⟩. `tags: D-INV-4`

**The two surfaces — the «leans toward» line and the read panel.** The «leans toward» line (§D.10) is the
glanceable handle: a catalog column + a Detailed plaque chip naming the nearest reference direction with a
colour closeness cue. The read panel opens when you click your track: "leans toward Venetian Snares", the
in-zone/diverge read, "своё", each backed by its evidence. The read panel is a *read* (observation), it
never becomes an action card. Both draw from the SAME full-dimensional fingerprint, so they can never
disagree about which direction is nearest (D-INV-11). ⟨DECIDE D-13⟩ the switch's default.

### D.4 How you use it (worked scenarios)

**1 — An album as a direction (the full case).** You drop the Venetian Snares album in as a reference
direction and say "wobble drift reaches toward this." track-coach analyses the album (audio only), forms the
cloud, and reads wobble drift against it: its fingerprint sits just inside the cloud. You click it
and read: "leans toward Venetian Snares — on the hysteric, ruptured feel you're in their zone; the palette runs
colder than theirs; their arc breaks where yours stays level." Your usual cards reorder so the ones about
where you diverge come up first, and one gets a note: "their low-mid stays clearer around 290 Hz — an option,
if you want to lean that way." Nothing is hidden; nothing is graded.

**2 — A single reference track (reduced).** You only have one scsi-9 track, not the album. That's *reduced
mode*: no cloud, no spread, no "in-zone". You still get a straight track-vs-track read ("your track is denser
and warmer than this one") and both are catalogued, but there's no region to be inside, so "своё" isn't
computed — **not because you only have one direction (one CLOUD is enough for «своё», D-INV-16), but because
a reduced direction has no zone to be outside of.**

**3 — Several artists, the web, and deleting a direction.** You make a direction "scsi-9 + deepchord". The
web lead is shown per artist, never merged. Later you delete that direction: every mapping that pointed at it
is dropped, the affected tracks quietly go back to plain coaching, and nothing is left pointing at a deleted
thing. If instead you just *add* a track to the direction, its cloud and every dependent read recompute — and
each read is stamped "vs scsi-9 + deepchord · 7 tracks · <date>" so a verdict that moved because the
*reference* changed (not your track) is explainable, not spooky.

### D.5 Rules that never break

**Never happens (safety).**

- No reference surface ever shows a grade, score, or pass/fail — only observation and offered options;
  "diverge" describes, it never means "wrong". `D-INV-1`
- A reference never makes the tool state an unmeasured number as fact: web info is labelled as external, and
  a re-flavoured card still only fires on a real measured finding. `D-INV-2`
- A reference track never shows any Ableton-project surface — it's audio-only, and its catalog row has no
  project columns. `D-INV-3`
- The tool never guesses which direction your track aims at — the mapping is always yours. `D-INV-4`
- A track with no mapping is byte-for-byte as it is today (its cards, read, player). The «leans toward» line
  and the reference catalog are *new* surfaces about your tracks; carrying a leans-toward isn't a change to
  the track's widget. `D-INV-5`
- **Reference / compare is a FULL-run-only feature — quick mode is never referenceable** (Alexander 2026-06-25:
  quick mode is not for reference). The fingerprint is per-stem; a quick (mix-only, no Demucs) run has no
  fingerprint to place or compare, so "хочу как X", the «leans toward» line, and re-flavouring are simply **not offered**
  on a quick run — shown as "full analysis only", never a half-comparison on mix axes alone.
  This is the canonical missing-by-mode case (RC-INV-7): quick never promised reference, so its absence is
  silent, not an error (it is NOT a partial-run failure under RC-INV-10). `D-INV-20`
- The show/hide-references control is one named switch shared by the reference column and the plaque chip;
  no view strands its state where you can't see or undo it. `D-INV-6`
- Reference tracks never enter your library's catalog/signatures; the switch only surfaces them through the
  reference column for display. `D-INV-7`
- Every character / mood / style / in-zone statement carries its real evidence — one signal or a combination;
  with none, it's omitted, never shown. `D-INV-10`
- The verdict is read in **full dimensions** and is authoritative; there is **no lossy projection** — the
  2-D/3-D map was dropped (Alexander, 2026-06-26: any flattening drops dimensions, so we show the nearest
  centroid via the «leans toward» line, not a flattened picture). The «leans toward» line and the read both
  derive from the **same full-dimensional fingerprint** at the current epoch, so they can never disagree about
  which direction is nearest. A per-facet drop can still read "diverge" even when the fingerprint sits near
  overall — that's the facet test (D-INV-19), not a contradiction. `D-INV-11`
- The fingerprint geometry is **deterministic per epoch and never moves silently**: a position (and the
  nearest-direction it implies) is a pure function of *(its signals, the current normalisation epoch)*. It is
  NOT frozen-forever — when the inputs change (library grows, a reference group gains/loses members) every
  dependent position recomputes together and is re-stamped (D-INV-14); within one epoch, nothing drifts
  run-to-run. `D-INV-12`
- No mapping ever points at a deleted direction or a removed track; deletes cascade, and affected tracks
  revert to plain coaching. `D-INV-13`
- **Adding AND removing a member are symmetric** (Alexander 2026-06-24, recompute-on-change): both recompute the
  direction's cloud and every dependent read, and re-stamp them. If a **removal crosses the cloud below the
  member threshold** (D-1), the direction becomes *reduced* — its dependent reads drop their in-zone/diverge
  and «своё» content (a reduced direction has no zone to be inside, D-INV-16) rather than keeping a stale
  cloud-mode verdict; if an **addition crosses up**, the in-zone/diverge read appears. A read's stamp always
  matches the member count it was computed against. `D-INV-18`
- Every placement read carries TWO things, written together with the read so a fresh verdict never carries a
  stale stamp: a **human stamp** (name · member count · date) shown to you, AND a **content hash** of its
  inputs (member track-ids + normalisation epoch) used to detect change. A read recomputes iff its input hash
  differs — the count alone is never the change key (an equal-count swap must still trigger recompute, §D.3).
  `D-INV-14`
- Re-flavouring only re-orders, re-words, and may add an "on-style" note — it never adds, removes, or
  suppresses a card versus the plain view, and never changes a card's "based-on". `D-INV-15`
- «своё» and in-zone/diverge are computed only against **cloud** directions; a reduced direction (too few
  members for a zone) never produces an in-zone/diverge/«своё» verdict, and a track aimed only at reduced
  directions has no «своё». `D-INV-16`
- Re-flavouring over several aimed-at directions is **deterministic**: a card's order rank is its strongest
  divergence across all of them (largest divergence breaks ties), so the card list has one well-defined order
  even when directions pull opposite ways. The card SET is still identical to the plain view (D-INV-15).
  Re-flavouring re-orders **within the active §B.11 sort mode** as a SECONDARY key, never a third competing
  order: in urgency mode divergence sub-sorts within each tier; in strict chronological mode (no ties) the
  re-order lever is inert and only re-word/on-style act. `D-INV-17`
- in-zone/diverge/«своё» is a **pure function of the full-dimensional fingerprint** (per-facet spread test).
  There is no projection to disagree with it — the full-dimensional verdict is the only one, and it is
  authoritative (D-INV-11). `D-INV-19`

**Always, eventually (liveness).**

- Any web fetch completes, fails, or times out, and the feature carries on either way — it never hangs the
  analysis or the render. `D-INV-8`
- Analysing a reference either produces a placeable fingerprint and read, or reports which signals it
  couldn't compute — never a half-finished silent state. A reference **missing any fingerprint axis is
  catalogued but NOT comparable** (a nearest-direction needs every coordinate — we don't impute a
  fake one and lean on a misleading distance), with a one-line "couldn't compare: ⟨signals⟩" note. It gets
  **no own leans-toward and is never offered as a neighbour**, but it **still contributes per-axis to the
  centroid of any direction it belongs to** (RC-INV-6) — not comparable as an own placement, never excluded
  from its cloud. Its written read still renders from whatever signals DID compute. `D-INV-9`

### D.6 How the coaching changes — re-flavouring (the payoff)

When your track is mapped to a direction, the *existing* cards and read are re-flavoured toward it. A track
can aim at **several directions at once** (the mapping is many-to-many, D-INV-4), and re-flavouring **mixes
them all** (Alexander, 2026-06-24: re-flavouring mixes all aimed directions at once), not one-at-a-time. Same engine, same findings — three
levers, all in the "observe and offer" register (never a command):

1. **Re-order.** Cards about where you *diverge* rise; where you're already in-zone, they sink. With several
   aimed-at directions a card's rank is its **strongest divergence across all of them** (a facet where you
   diverge from ANY aimed direction rises; the largest divergence breaks ties) — so the order is
   deterministic even when two directions pull opposite ways (D-INV-17). Divergence is a **secondary key
   inside the active §B.11 sort mode, not a promotion over it**: in urgency mode it sub-sorts within each
   tier (crit/do/concept) so diverging cards come first within their tier; in the **strict chronological
   mode there are no ties, so the re-order lever is inert** — only the re-word + on-style levers act. It is
   never a third competing sort. The set of cards shown never changes — only the order. Nothing is hidden.
2. **Re-frame as an option.** A card gains a direction, phrased as a choice: "the bass buries the lead around
   ≈290 Hz" → "…and Venetian Snares keeps that low-mid clearer; an option, if you want to lean that way."
   When directions genuinely disagree (one keeps that low-mid clearer, another sits dense too) **both options
   are offered** — that's the observe-and-offer register; the coach never picks for you. Notes are deduped
   and capped so a card isn't buried under one note per direction. ⟨DECIDE D-21⟩ the per-card note cap.
3. **Mark on-style, don't suppress.** We used to leave a trait unflagged because the coach couldn't know if
   it was a mistake or the point. The reference is that missing intent signal — but when your "problem"
   *matches* the aspired style of **any** aimed direction, the card is **kept and marked**, not hidden:
   "though Venetian Snares sits this dense too — maybe it's the point." The doubt is surfaced, never silently
   resolved.

Through all of it the card still stands on its real finding and cites the same "based-on" — re-flavouring
changes emphasis and words, never the truth. A track with no mapping is untouched. `tags: D-INV-15 · D-INV-2
· ⟨DECIDE D-11⟩ recommend off unless mapped`

### D.7 How it fits the views, the switch, and the player

- **The view ladder (quick ⊆ Simple ⊆ Detailed).** Reference surfaces obey it. **Quick shows none — and not
  by view but by mode: reference is full-run-only (D-INV-20), a quick run has no fingerprint, so there is
  nothing to reference, not even a hidden one.** Within a full run: Simple shows the written read + "leans toward
  X"; Detailed adds the plaque chip and the switch. Nothing in Simple is absent from Detailed. ⟨DECIDE D-15⟩.
- **The switch across views.** If the switch lives only where the chip lives (Detailed), entering a view
  without the chip must not strand a hidden state — the same rule the player follows (state is only live
  where its surface is visible). ⟨DECIDE D-16⟩.
- **Reduced vs full across views.** Whether a direction is a cloud or just a point is decided by its member
  count, not the view: a full direction yields an in-zone/diverge read and a centroid to lean toward; a
  reduced one yields only a track-vs-track read and leans toward its nearest member. The switch shows/hides
  the reference surfaces alike in every view.
- **The mapping is content, not view state** — it persists across views like the project does; only the
  *display* of reference surfaces is gated by view.

### D.8 What's machine-checked vs eyeballed (and how we'll test the spec)

The *words* of a read stay authoring quality, judged by eye (like the "based-on" line). But three things are
pinned so a refactor can't quietly break the core:

1. **Anchored** — every placement statement names at least one real evidence signal (checkable). `D-INV-10`
2. **Deterministic geometry (per epoch)** — the fingerprint + distance are a pure function of *(the signals,
   the current normalisation epoch)*, tested on a fixture; within an epoch readings never drift run-to-run,
   and across an epoch change they recompute together + re-stamp, never silently. `D-INV-12`
3. **Transparent re-flavouring** — mapped vs unmapped show the identical card set; only order/wording differ
   (checkable). `D-INV-15`

There is no map↔read relationship to guard — the map was dropped (D-INV-11); the read and the «leans toward»
line share one full-dimensional computation, so nothing can drift between them. Only the anchoring of
*wording* stays an authoring guard, reviewed by eye.

### D.9 Open decisions (need Alexander)

Settled already by the reading stance: how to measure hypnotic/mood and where the "in-zone" line is — both
became reads, not numbers; no hardcoded thresholds, no regression anchors. Still open, all genuine tuning, no
structural holes:

- ⟨DECIDE D-1⟩ how many members make a cloud (below it = reduced).
- ⟨DECIDE D-2⟩ where the mapping is stored + how it's edited.
- ⟨DECIDE D-5⟩ ~~does style ever need a number for the map~~ → **DROPPED 2026-06-26**: the map is gone;
  style stays a label.
- ⟨DECIDE D-8⟩ what triggers the web fetch.
- ⟨DECIDE D-9⟩ web source + caching (offline-first).
- ⟨DECIDE D-11⟩ off-by-default for unmapped tracks (recommend: yes).
- ⟨DECIDE D-12⟩ ~~how signals collapse onto the map + its dimensionality~~ → **DROPPED 2026-06-26**: no map
  is drawn at all (Alexander 2026-06-26: no point drawing a map we never show — we show the nearest centroid).
  The full-dimensional fingerprint is read directly; the «leans toward» line names the nearest centroid. No
  projection to design.
- ⟨DECIDE D-13⟩ the switch's default.
- ⟨DECIDE D-14⟩ ~~what clicking a map marker opens~~ → **DROPPED 2026-06-26**: no map markers. The plaque
  chip carries a hover label (D-INV-26); own-library click-to-scroll is specified in §F.2 (F-INV-4).
- ⟨DECIDE D-15⟩ which reference surfaces show in which view.
- ⟨DECIDE D-16⟩ **SETTLED 2026-06-26:** one global persisted show/hide-references flag; the catalog page and a track's widget both read it (D-INV-23) — not a per-page toggle.
- ⟨DECIDE D-17⟩ distance measure — **SETTLED 2026-06-25 (Alexander): straight-line.** (He weighed an
  on-the-manifold/surface measure and chose not to over-engineer; straight-line and angle agree on the
  real 3-track library anyway. Revisit only if a larger library shows them diverging.)
- ⟨DECIDE D-18⟩ whether some signals weigh more in the fingerprint.
- ⟨DECIDE D-19⟩ ~~the "clearly outside" margin for the map↔read guard~~ → **DROPPED 2026-06-24**: the read is
  authoritative and the map is a labelled lossy viewport (D-INV-11), so there is no map↔read guard to tune.
- ⟨DECIDE D-20⟩ ~~the visual that groups a reduced direction's markers~~ → **DROPPED 2026-06-26**: no map
  markers to group; a reduced direction simply yields a track-vs-track read and its nearest-member lean.
- ⟨DECIDE D-21⟩ the per-card note cap when several aimed directions each add an option-note (§D.6 lever 2).
- ⟨DECIDE D-22⟩ does the reference line show its descriptive «leans toward» for tracks you've written **no
  mapping** for, or stay off until mapped? (recommend: show the descriptive line for every full run; gate
  only re-flavouring on mapping, as D-11 already leans).
- ⟨DECIDE D-24⟩ runner-up direction — **RESOLVED 2026-06-26 by listing, not tinting (§D.10.1, D-INV-27).** The
  earlier worry (a *tied* second under relative lean means the nearest does NOT stand apart, so a second tint
  in one cell is self-contradictory) dissolves once the surface is an **up-to-three nearest-first selector**:
  a list HAS an order to carry the ranking, exactly as §F does, so a 2nd/3rd direction is its own ordered,
  cued entry rather than a crammed second tint. No co-leaders tied-pair tint needed.
- ⟨DECIDE D-25⟩ does the **Simple** view also show the compact plaque chip, or does the chip stay
  Detailed-only while Simple keeps "leans toward X" as prose in the read? (recommend: Detailed-only chip;
  the up-to-three selector and the web-style plaque are Detailed-only by §D.10.1/§D.10.2).
- ⟨DECIDE D-29⟩ aimed direction outside the three nearest — **RESOLVED 2026-06-29 (Alexander).** Pin **only the
  single nearest of the aimed** ones, as an additive entry (it never displaces a nearer one), shown **even if it
  tints far** because a declared aim is intent, not filler; the other aimed directions live in the read panel.
  At most one pinned aimed entry. `§D.10.1`
- ⟨DECIDE D-30⟩ a web facet the measurement **contradicts** — silently **dropped** (recommend) or shown
  **struck-through** as a teaching contrast ("web says wide stereo; the signals run narrow")? `§D.10.2`
- ⟨DECIDE D-32⟩ where the **facet→signal map** lives and how it's curated — the table tying a web style phrase
  to a measured axis (★ direct) or a sound indirect signal (☆). It's authored, not learned; recommend a
  versioned in-repo table maintained like the other frozen constants, reviewed when a new ☆ tie is claimed.
  `§D.10.2`
- ⟨DECIDE D-31⟩ a **second ★-style mark for "your track shares this confirmed trait"** (per-your-track, atop
  the v1 ★ that means "true of the direction") — build it, or leave ★ as direction-only? (deferred; v1 =
  direction-only). `§D.10.2`
- ⟨DECIDE D-27⟩ the exact boundaries of the own-library high/medium/low buckets (§F) — relative to the
  library's own distribution of pairwise distances (recommend: terciles / a spread multiple), since §F has no
  cloud spread to borrow.
- ⟨DECIDE D-28⟩ the reference cue basis — **SETTLED 2026-06-25 (Alexander): RELATIVE lean** (how strongly the
  nearest direction stands apart from the track's other directions), NOT absolute depth inside one cloud
  (which read "far" for every own track). Shown by colour only — green/amber/red tint on the direction name,
  no closeness words (color-only).

> _(⟨DECIDE D-23⟩ own-track neighbours is no longer open — Alexander 2026-06-25 chose YES, as its **own
> column** beside the reference one, scoped to **1.0**. It is specced as its own surface in **§F**, not
> folded into the reference line.)_

### D.10 The reference line — the «leans toward» surface (catalog column + Detailed plaque) — 0.9

One compact surface that answers, at a glance, *which direction is this track closest to?* — without opening
the full read panel. It appears in two places but is **ONE surface**: a **column on the catalog** (the library page) and a
**chip on the Detailed plaque** of a track's widget. Both draw the identical fact from the identical
computation; they are not two features, and not a second name for the read panel. It is one of the **two catalog
similarity columns** — the *reference* one (this section); the *own-library* one is §F. `tags:
one-surface-two-placements`

**Two facts it can carry, never conflated.**

- **Leans toward X (descriptive).** The reference **cloud whose centre is nearest** this track in
  full-dimensional fingerprint space. It is computed for ANY full run and needs **no aspiration mapping** —
  "nearest" is just a measured fact about the fingerprints. It carries a **coarse closeness cue — high /
  medium / low** read as **how strongly the track leans to its nearest direction versus its other directions**
  (relative lean, ⟨DECIDE D-28⟩ settled = relative; Alexander 2026-06-25) — never the raw distance, never the
  absolute depth inside one cloud (which read "far" for every own track, since a producer sits outside the
  album clusters they reach toward). The cue is shown by **colour, not words** (Alexander 2026-06-25,
  color-only): the direction's name is tinted green (close) → amber (mild). A would-be **red (no real lean) is
  not shown as a named direction at all** — the cell reads **"no close direction yet"** instead (Alexander
  2026-06-29, §D.10.1): a far direction named in red would mislead. The column header stays "leans toward" and
  the cell carries no per-row closeness word. Colour is the only cue — never a number, never a grade (D-INV-26).
  **The single nearest is chosen across ALL your reference directions at once** — clouds ranked by their centroid
  (straight-line, ⟨DECIDE D-17⟩), reduced directions by their nearest member — using the axis-count-fair per-axis
  distance (RC-INV-5b), so a direction isn't picked just for sharing fewer axes. With **no reference directions
  defined at all** (or none clearing the lean bar), there is nothing to lean toward and the cell is empty with a
  quiet "no close direction yet", never a fabricated nearest.
- **Aimed at X (aspiration).** Your written mapping (D-INV-4). When you have aimed this track at a direction,
  the line marks it with an aim glyph — and when the direction you *aim at* is not the one you're *nearest*
  to, it shows both ("nearest DeepChord · aimed SCSI-9"), because that gap is exactly the useful thing to see.

**Same geometry, named once.** The "nearest" here is the **same full-dimensional fingerprint distance** that
grounds the in-zone/diverge read (D-INV-12/19), at the current normalisation epoch — never a 2-D marker
distance (there is no map). So the catalog column, the plaque chip, and the read panel can never disagree
about which direction is nearest: one geometry, drawn three ways. `D-INV-21`

**How it composes across the axes.**

- **The view ladder (the plaque chip).** The chip lives in the per-track widget, so it obeys quick ⊆ Simple ⊆
  Detailed. **Quick shows nothing** — reference is full-run-only (D-INV-20): a quick run has no fingerprint, so
  there is no nearest to name. **Detailed shows the chip.** Whether **Simple** also shows it is ⟨DECIDE D-25⟩:
  Simple already carries "leans toward X" as *prose inside the read* (§D.7), which is a different surface (the
  read panel — authored words) from this glanceable chip. The chip and the read's prose are **not two names for
  one thing** — the chip is a glance handle, the read is the words; both cite the same leans-toward fact. The
  ladder stays monotonic: Detailed adds the chip without removing the Simple-level prose. `tags: view-ladder ·
  D-INV-20 · ⟨DECIDE D-25⟩`
- **The run mode (the catalog column).** The catalog is its own page (a row per version), governed by run
  MODE, not the per-track view ladder. A **full-run** version shows its leans-toward; a **quick-only**
  version's cell reads "full analysis only" — the canonical missing-by-mode case (D-INV-20, RC-INV-7): quick
  never promised reference, so the empty cell is silent, never an error and never blank-implying-"no
  direction". A catalog row collapses a version's runs, so the column reads the version's **most-complete
  run** (E.4); "full analysis only" shows only when that version has **no** full run at all.
  **The column appears whenever at least ONE version has a computed reference RESULT** — a lean, a "no close
  direction yet", or a "can't compare" (Alexander 2026-06-25: don't hide it if there's data for even one
  track); it is **absent only when no version has any reference computation at all** (an all-quick library, or
  no directions defined). "Has a result" is the presence test, NOT "has a *lean*" — a library where every
  track computes to "no close direction yet" still has reference data and still shows the column (it is not the
  same as no-data). So a brand-new column never reads as a missing feature, and an all-quick library doesn't
  carry an all-empty column. It sits as one of the **last two columns** with a slightly smaller font
  than the spec columns, as long as the look holds (placement P-1). `D-INV-22`
- **Completeness (a full run that couldn't measure everything).** A version whose fingerprint is **missing an
  axis is not comparable** — its cell and chip read "can't compare — ⟨missing signals⟩", never a fabricated
  nearest. It draws this from the same run manifest as the coach and §D, so one gap reads identically in all
  three (E.3). **Because the cue is colour, the not-measured / not-comparable cell uses a NEUTRAL grey (or a
  dash), never the red "far" tint** — red is a *measured* "far", grey is "no measurement"; collapsing them
  would be the missing-as-value trap (RC-INV-1) in colour form. `tags: D-INV-9 · RC-INV-5a · RC-INV-1 · E.3`
- **The switch.** The reference line is a reference surface in both placements, so it is governed by the **one
  show/hide-references switch** (D-INV-6) shared by the catalog column and the plaque chip: hiding references
  hides the column and the chip together, and the switch never strands the line where you can't see or restore it. The switch is **one global persisted flag** that both the catalog page and a track's widget read, so hiding references on either page hides both — one flag, never a per-page toggle (⟨DECIDE D-16⟩ resolved).
  **The toggle CONTROL renders wherever a reference surface renders** — the catalog page, and **both** the
  Simple and Detailed widget (since Simple already shows reference prose, §D.7) — every instance reads and
  writes the one global flag. So content and its off-switch are never separated: a producer who works only in
  Simple still has the control beside the reference prose, and never sees references with no way to hide them.
  (The §F own-library column is NOT reference content and is NOT under this switch.) `D-INV-23`
- **Unmapped tracks.** Because leans-toward is descriptive, it CAN show for a track you've written no mapping
  for. Whether it does by default is ⟨DECIDE D-22⟩ (tied to D-11) — recommend showing the descriptive line for
  every full run and adding the aim glyph only when you've aspired; re-flavouring stays
  off-unless-mapped as before. `tags: ⟨DECIDE D-22⟩ · D-INV-5`
- **Recompute, never stale.** The named direction and its cue are a pure function of (fingerprints, epoch);
  when the library grows or a direction gains/loses members, the line recomputes and re-stamps with every
  other placement (D-INV-12/14/18) — the catalog never shows a "leans toward" the current geometry no longer
  supports. `D-INV-24`

**Never happens (safety), specific to this surface.** The reference line never shows a number — no raw
distance, score, rank, percentage, or "match %"; it names a direction and a coarse cue. "leans toward" is
observation, never "you should sound like this" (the artistic north-star, D-INV-1). `D-INV-25`

**The closeness cue is a colour, not a number or a grade.** The cue is a coarse three-level closeness shown
as **colour only — green (close) / amber (medium) / red (far)** — no closeness words and no number on the
cell (Alexander 2026-06-25, color-only); a small legend names the colours once. It is never a quality
judgement (red means *far from this direction*, never *a worse track*). Its **basis differs by surface, both
relative**: the reference column tints by **lean strength** — how much the nearest direction stands apart
from the track's other directions (⟨DECIDE D-28⟩ settled = relative, not absolute cloud-depth); the §F own
column tints by closeness against the **library's own distance distribution** (⟨DECIDE D-27⟩). **Green and
amber are the default; red is a last-resort tint** in §F — used only when nothing closer qualifies, never
hiding that the sibling is far. A reference **runner-up (+second direction) is now RESOLVED by listing, not
tinting** (⟨DECIDE D-24⟩ resolved 2026-06-26): the surface shows the **up to three nearest directions as a
nearest-first selector** (§D.10.1, D-INV-27), so a second and third direction are their own ordered, colour +
glyph-cued entries — not a self-contradictory second tint crammed into one cell. The old worry (a *tied*
second under relative lean means the nearest does NOT stand apart) dissolves because a list HAS an order to
carry the ranking, exactly as §F's own-library list does. So colour is never the *sole* channel:
in **§F** (a list of up to three) the **nearest-first order** carries the ranking; in the **§D reference
column** (one direction per cell, no order to lean on) a **greyscale-safe glyph tier** (●●● close / ●●○ mild /
●○○ no real lean) sits beside the name. A **hover label** names the closeness on both. So the cue stays
readable in greyscale, in print, and for a colour-blind reader without adding closeness words. `D-INV-26`

### D.10.1 The up-to-three selector — your three nearest directions, chosen one at a time — 0.9

**The «leans toward» surface lists up to your three nearest directions, not just the single nearest.**
Earlier the surface named one direction and a runner-up was deferred, because cramming a *second* colour tint
into one cell was self-contradictory under relative lean — a tied second means the nearest does NOT stand
apart, so "also close" contradicted itself. A **nearest-first list with a selector dissolves that**: a list
HAS an order, and the order carries the ranking exactly as §F's own-library list does, so a second and third
direction are no longer a confusing second tint in one cell but their own clearly-ordered, clearly-cued
entries. The runner-up is resolved by listing, not by tinting (⟨DECIDE D-24⟩ resolved). `D-INV-27`

**Scope split (what ships in 0.9 vs what waits on the mapping input ⟨D-2⟩).** The **descriptive** rows below —
the up-to-three nearest *clouds* ranked by fingerprint distance, the per-entry colour/glyph cue, "no close
direction yet", and the inline links — ship in **0.9**: they need no aspiration mapping, only the measured
fingerprints. The **aim-dependent** rows — the aim glyph, the pinned-aimed-direction entry, and re-flavouring
(§D.6) — are **inert until the mapping input surface (⟨DECIDE D-2⟩) exists**; they are authored here so the
composition is proven, but a 0.9 build neither renders nor tests them. `tags: scope-0.9-descriptive · ⟨DECIDE D-2⟩`

**What the list holds and how it's cued.**
- **Up to the three nearest reference clouds that are a REAL lean** — ranked nearest-first, in the **same
  full-dimensional fingerprint geometry** as the single-nearest (D-INV-21). The list shows only the directions
  that clear the lean bar (green / amber); it **never pads to three with weak or far filler**. If even the
  nearest is only a weak lean (no direction stands apart), the surface reads **"no close direction yet"**
  rather than naming a red one — better to show nothing than a misleading "you lean toward X" when you don't
  (Alexander 2026-06-29). **This supersedes the earlier "always name the nearest even at a low cue"** for the
  reference list: a far *direction* is noise, whereas §F keeps its single-red last-resort because a far *own
  sibling* is still a real track you might mix. With no directions defined at all, "no direction yet" (D-INV-22).
  `tags: fewer-not-filler · supersedes-F-INV-1-for-§D · D-INV-27`
- **Each shown direction is tinted by its OWN closeness, order carries the rank.** Each entry's colour + glyph
  cue (D-INV-26) reflects **how close THAT direction is to the track**, by **one fixed formula at every list
  position: the gap from this entry to the NEXT-shown entry** (the relative-lean basis, ⟨DECIDE D-28⟩,
  z-normalised) — a big gap to the next reads as a strong lean, a small gap as a mild one. (Not "stand apart
  from the whole field" — that's a different number; the gap-to-next is the one we use, so two builders paint
  the same colours.) The nearest-first order carries which is closest. So the cue is defined for every entry
  shown, not only the top one, and a list of two amber entries reads honestly as "two mild leans, neither
  strong". `tags: D-INV-26 · per-entry-cue · gap-to-next · D-INV-27`
- **No numbers, no "#1/#2/#3".** Position in the list IS the ranking; the surface never prints a rank number,
  distance, or score (D-INV-25 unchanged).
- **Ties resolve deterministically.** When two directions sit at the same distance, the order — and which is
  the default-shown nearest in the collapsed cell — is broken by a stable secondary key (the direction name),
  so the list and the collapsed cell never flicker between runs. `tags: deterministic-order`

**Everything is clickable, and a click is always NAVIGATION — never a persisted selection.** The surface
carries no lingering "which one is selected" state on the catalog (Alexander 2026-06-29: everything clickable,
like the own-track column). `D-INV-28`
- **On the catalog (the library list).** Every name is a link: clicking your **track** opens it; clicking an
  **own sibling** scrolls to that track's row (F-INV-4); clicking a **direction** opens THIS track's read
  panel already focused on that direction. The catalog cell shows the up-to-three nearest directions **inline,
  as a nearest-first vertical stack of coloured links** (no collapse/expand gesture — what shipped, owner-approved
  2026-06-29) — the order IS the ranking and the stack IS the glance; it is a row of links, never a stateful
  picker. Because every click is a jump, nothing on the list page can strand. **Click-to-focus wiring (a
  direction link opening the read pre-focused on it) is 0.9.x** — in 0.9 the links render (`href` placeholder)
  and carry the colour/order; the cross-page focus hand-off is specified below (URL entry-focus) and wired next.
  `tags: clickable-navigation · inline-stack · F-INV-4`
- **In the per-track read panel.** Here the up-to-three list is a set of **direction tabs**: the read defaults
  to the **nearest**, and switching a tab re-targets the read's in-zone/diverge words and the web-style plaque
  (§D.10.2) to that direction. The tab is **ephemeral view state** (it changes no analysis, and does not
  persist across a reload — like the view ladder itself). **The catalog → widget focus hand-off is a one-shot
  URL *entry* parameter, not persisted tab state:** arriving from a catalog direction-link, the widget reads
  the wanted direction once on load and opens that tab; thereafter clicking tabs does NOT write back to the URL
  (the tab stays ephemeral, D-INV-28). So "opens focused on that direction" is buildable across the page
  boundary without contradicting the not-in-URL rule — entry-focus on load ≠ tab persisted in the URL. On a
  recompute (D-INV-24) that drops the focused direction out of the shown list, the read **falls back to the
  nearest**; and if the recompute leaves **no direction clearing the lean bar at all**, the open reference read
  **collapses to the "no close direction yet" state** — tabs and the §D.10.3 per-facet bars are removed, the
  one-line prose read is retained, and it re-stamps — so an open panel never strands on a vanished direction
  and never shows empty tabs. `tags: ephemeral-view-state · url-entry-focus · no-strand · recompute-empties · D-INV-24 · D-INV-28`
- **The aim glyph rides the list.** A direction you've *aimed at* (D-INV-4) is marked with the aim glyph
  wherever it appears. Because aspiration is many-to-many, several directions can be aimed at; when **none of
  the aimed is among the shown nearest**, the surface pins **only the single nearest of the aimed ones** as an
  extra entry — shown **even if it tints far/red**, because a declared aim is intent, not filler, and the
  nearest↔aimed gap ("aimed SCSI-9 · but far from it") is exactly the useful thing to see. The other aimed
  directions live in the read panel, not the catalog cell. So at most one pinned aimed entry (⟨DECIDE D-29⟩
  resolved). `tags: D-INV-4 · intent-not-filler · ⟨DECIDE D-29⟩`

**How it composes across the axes.**
- **The catalog column (run mode).** A full-run row shows the up-to-three nearest directions **inline, as a
  nearest-first stack of coloured links** (no collapse/expand — the shipped cell). Quick-only rows read "full
  analysis only" (D-INV-20); the column appears whenever ≥1 version has a **computed reference result** — a
  lean, "no close direction yet", or "can't compare" — not only when ≥1 has a *lean* (D-INV-22). `tags:
  view-ladder · inline-stack · D-INV-22`
- **The per-track widget (view ladder).** **Quick** shows nothing (no fingerprint). **Simple** keeps the
  single **nearest** as prose in the read (§D.7) — no tabs; the ladder's bottom rung stays a one-line glance.
  **Detailed adds the up-to-three direction tabs and the 2nd/3rd directions**, monotonically — Detailed only
  ADDS, never removes Simple's nearest. ⟨DECIDE D-25⟩ (Simple chip) is unchanged: Simple's reference content
  stays prose-only. `tags: view-ladder · ⟨DECIDE D-25⟩ · D-INV-27`
- **Beside the §F own-library list — two parallel up-to-three lists, both clickable, named apart.** §D.10's
  list (reference *directions*, other artists, under the show/hide-references switch) sits beside §F's list
  (your OWN *tracks*, always-on, F-INV-4). They look parallel — both up-to-three, both nearest-first, both
  colour-cued, **both clickable** — so the spec names the one real difference, the click TARGET: **a direction
  click opens THIS track's read focused on that direction; an own-track click scrolls the catalog to that
  track's row.** Both are navigation, never a persisted selection; never merged, never the same control; the
  references switch hides only the §D list. One more rule difference: §D shows only the close directions (else
  "no close direction yet"), while §F keeps a single-red last-resort sibling — a far direction is noise, a far
  sibling is still a real track. `tags: one-surface-one-name · D-INV-7 · F-INV-4 · D-INV-27`

**Never happens (safety), specific to the list.** The list never shows more than the three nearest close
directions (plus at most one pinned aimed direction); it never pads with weak/far filler; it never prints a
number or rank; a click never edits a mapping and never changes the cards/read content beyond which direction
the read compares against; and the read's focused direction never strands on a hidden or dropped direction
(it falls back to the nearest). `D-INV-28`

### D.10.2 The web-style plaque and the ★ cross-validation mark — 0.9

**Beside the focused direction, a small plaque lists what the web told us about that direction's style — but
only the parts we can tie to measurement.** When the read is focused on a direction (§D.10.1), a compact
**bulleted plaque** shows style facets pulled from the web for that direction's artist (dense unresolving
harmony, wide stereo pads…). It is the visible face of the web-descriptor layer — **web suggests, measurement
decides** (D-INV-2). `D-INV-29`

**What gets onto the plaque — only facets a curated map ties to a measured signal.** A web phrase is shown
**only if** the curated **facet→signal map** connects it to a measured fingerprint axis; everything else the
web says is dropped, never shown as untethered prose. Two marks, by how the tie holds:
- **★ — directly confirmed.** The map ties the facet to an axis AND the direction's measurement bears it out
  (e.g. "wide stereo pads" ↔ stereo-width axis reads wide). The ★ is the only thing that asserts a direct
  measured confirmation. `tags: D-INV-2 · facet→signal-map`
- **☆ — indirect but soundly tied.** The map ties the facet to a measured signal by a sound, unambiguous
  argument even though no axis confirms it head-on (e.g. "underwater, dubby" ↔ a steep low-pass + long
  reverb tail). ☆ is a **curated judgement** that the tie is unambiguous, not a free-floating web claim
  (Alexander 2026-06-29). `tags: D-INV-2 · indirect-tie`
- **Withheld — the web claimed it but measurement CONTRADICTS it.** A trait the signals don't bear out is
  **not stated** (it would mislead). ⟨DECIDE D-30⟩ whether a contradicted facet is silently dropped
  (recommend) or shown struck-through as a teaching contrast ("web says wide stereo; the signals run narrow").
  `tags: D-INV-2 · ⟨DECIDE D-30⟩`

**The marks are compact — two glyphs and one footnote, never long per-row labels.** Each facet carries just
★ or ☆; a single footnote under the plaque explains both once (★ = web said, measurement confirms directly;
☆ = measurement doesn't show it head-on but it's unambiguously tied to what we measure). No per-row "web said ·
measured" tag strings — they read long and slow (Alexander 2026-06-29). `tags: compact-marking · D-INV-29`

**What ★ / ☆ are measured against — the direction's CENTROID.** Both marks judge the trait on the
direction's **cloud centroid** — the same full-dimensional reference point that grounds "leans toward"
(D-INV-21) — not on any single member track and not on a majority vote, so the plaque and the nearest-centroid
read can never disagree about what the direction measurably is. It is NOT (yet) a claim about *your* track.
⟨DECIDE D-31⟩: a richer second mark — "and YOUR track shares this confirmed trait" — is the natural next layer
(which of the direction's web-described traits you actually have), but v1's ★/☆ stay "true of the direction";
the per-your-track shared mark is deferred. `tags: D-INV-21 · centroid · ⟨DECIDE D-31⟩`

**Per artist, never blended.** A direction spanning several artists shows each artist's facets
**separately**, never merged into one claim (the existing per-artist rule, D-INV-2); each artist's facets
carry their own ★/☆. `tags: D-INV-2`

**No plaque is a valid, silent state.** A web fetch that fails, times out, or finds nothing — or finds only
claims the facet→signal map can't tie to measurement — leaves the plaque **simply absent** for that direction,
never a blank box implying "this artist has no style", never a guess. Because there is no untethered web-only
tier, an empty plaque and a plaque present-but-only-☆ are honestly distinct: *no plaque* (nothing fetched or
nothing tie-able) ≠ *plaque with ☆ only* (tied indirectly, none directly confirmed) ≠ *plaque with ★* (some
directly confirmed). `tags: D-INV-2 · liveness`

**Completeness-aware (a direction whose fingerprint is incomplete).** ★/☆ ask a measurement to confirm or
soundly tie; if the direction's fingerprint is **missing the axis** a facet would need, that facet **cannot be
★ or ☆** and is simply **not shown** — never auto-starred, never auto-withheld as "contradicted" (missing ≠
contradicted, the RC-INV-1 trap in star form). It reads the same run manifest as the coach and §D (E.3).
`tags: RC-INV-1 · RC-INV-5a · E.3 · D-INV-29`

**Recompute, never stale.** ★/☆ are a pure function of (the facet→signal map, the direction's centroid, the
current normalisation epoch); on a recompute (D-INV-24) a facet that no longer confirms loses its ★ (or drops
to ☆, or off the plaque) and re-stamps with every other reference placement — the catalog never shows a ★ the
current geometry no longer supports. The web fetch itself is cached on its own clock (⟨DECIDE D-9⟩), separate
from the measurement epoch. `tags: D-INV-24 · D-INV-29`

**How it composes across the view ladder.** The plaque is **explanatory detail**, so it lives where detail
lives: the **read panel** (when you click your track) and the **Detailed** per-track widget. **Simple** keeps
the prose read without the facet plaque; **quick** shows nothing (no fingerprint, no reference, D-INV-20). The
**catalog cell never carries the plaque** — too dense for a glance; the cell stays name + cue, and the plaque
opens with the read. It is governed by the **one show/hide-references switch** (D-INV-23) like every reference
surface. `tags: view-ladder · D-INV-23 · D-INV-20`

**Never happens (safety), specific to the plaque.** The plaque never shows a web claim the facet→signal map
can't tie to measurement; **★** appears only when measurement directly confirms and **☆** only when the tie is
sound and unambiguous (neither is ever decorative); no numbers, no grade (D-INV-25 stance); and "leans toward"
+ its plaque remain observation, never "you should sound like this" (D-INV-1). `D-INV-29`

### D.10.3 The reference read — how you sit vs the direction's centroid, per facet — 0.9

When you click your track in the catalog, the per-track widget opens a **reference read**: not a coloured
word, but the geometry of how your track sits against the focused direction's **centroid** — the mean point
of that artist's cloud in fingerprint space. This is where "the centroid and all that" is shown, for a
producer who reads vectors. It is **not a map** (dropped, D-INV-11); it is a per-facet decomposition plus the
overall closeness.

**What it shows (Detailed, against the focused direction).**
- **Per-facet comparison — your value vs the centroid, axis by axis.** For each producer facet (a fingerprint
  axis), a small signed bar places the direction's centroid at zero and **your track as an offset** (more /
  less), z-normalised so axes are comparable. You read where you overlap and where you part — "denser, but
  darker and narrower than DeepChord" — dimension by dimension, never collapsed into one number. `D-INV-30`
- **Ordered most-divergent first**, so "where you part from them" is at the top and the overlapping facets
  sit below. `tags: most-divergent-first`
- **The overall closeness is the same level/colour as the catalog** (D-INV-21/26) — one geometry shown twice;
  a short honest summary names the extremes ("closest on groove, density · furthest on brightness, stereo").
  No raw distance number on the surface (D-INV-25).
- **The angle is the bars.** Which axes diverge and which way IS the per-facet decomposition (the direction of
  the gap, not just its size); v1 shows no separate angle number. `tags: angle-as-decomposition`

**How it composes.** Detailed-only — the deep read is depth (quick ⊆ Simple ⊆ Detailed): **Simple** keeps the
one-line "leans toward X" prose, **quick** shows nothing (no fingerprint, D-INV-20). It reads against the
direction the §D.10.1 tabs focus, and falls back to the nearest on a recompute that drops the focused one
(D-INV-28). Completeness-aware: a facet the run didn't measure is **omitted, not drawn at zero** (missing ≠
"same as them", RC-INV-1). Under the one references switch (D-INV-23). `tags: view-ladder · RC-INV-1 ·
D-INV-23 · D-INV-28`

**Never happens (safety).** No raw distance, score, or percentage; observation, never a grade (D-INV-1/25); a
missing facet is never drawn as zero-divergence (it is left out). `D-INV-30`

## F. Similar in your own library — the DJ column (1.0)

A second catalog column, sitting beside the reference one (§D.10), that answers a different question:
*which of MY OWN other tracks does this one sound closest to?* Alexander's use case (2026-06-25): a DJ
glances down the library and sees, per track, its **1–3 nearest siblings** — handy for building a set, a
transition, an A/B. It is a 1.0 surface; 0.9 finishes on the reference feature (§D).

It is deliberately **not** a reference surface: the neighbours are tracks already in *your* library, so this
column is **always-on library data, never under the show/hide-references switch** (D-INV-7 keeps other
people's music out of your signatures; this column only ever lists your own). `tags: own-library · not-a-reference`

### F.1 What it shows

- **Up to three nearest own-tracks — but only the close ones.** The versions in your library nearest this one
  by **full-dimensional fingerprint** (same geometry as §D, D-INV-12/19, straight-line ⟨DECIDE D-17⟩,
  axis-count-fair RC-INV-5b), capped at three and ranked nearest-first. **By default it lists the green/amber
  (close/medium) siblings** (D-INV-26); if **none** qualify it falls back to the **single nearest, honestly
  tinted red (far)** — a last resort, never empty when another track exists (Alexander 2026-06-25). Because
  the red tint reads plainly as "far", it isn't a distant track dressed up as close — that was the worry, and
  the colour answers it. **This own-sibling last-resort red differs from the §D reference list**, which shows
  "no close direction yet" rather than a far direction (Alexander 2026-06-29, §D.10.1): a far *sibling* is
  still a real track you might mix, a far *direction* is just noise. «no comparison yet» (F-INV-7) is reserved
  for when there is truly no other placeable track at all. `F-INV-1`
- **A track is never its own neighbour**, and the relation is **symmetric in geometry** but shown per-row
  (A may list B without B's top-3 listing A, since each row shows ITS three nearest). `F-INV-2`
- **No number shown — closeness is a colour, not a score.** It names the neighbour tracks, each tinted by the
  same green/amber/red closeness cue as §D (D-INV-26), never a percentage, rank number, or raw distance. Same
  observe-don't-grade stance as D-INV-1/D-INV-25. `F-INV-3`

### F.2 Navigation — click a neighbour, scroll to it (Alexander: «чтобы к ним скроллилось»)

- **Click a listed neighbour → the catalog scrolls to that track's row and highlights it.** The catalog is
  the one surface that moves; the click is a pure navigation, it changes no analysis state. `F-INV-4`
- **If the target row is currently hidden by a search/sort filter**, the click must not scroll to nothing:
  ⟨DECIDE F-1⟩ either clear the filter first, or briefly surface the row — never a silent no-op that looks
  broken. `tags: ⟨DECIDE F-1⟩`
- **On a track's own widget plaque** (not the catalog) there is no catalog to scroll, so ⟨DECIDE F-2⟩
  whether the own-library neighbours appear on the plaque at all, and if so each name **opens that track's
  widget** rather than scrolling. Recommend: catalog-only for 1.0; revisit the plaque later.

### F.3 How it composes across the axes

- **Run mode.** Nearest-own uses the full-dimensional fingerprint, so it is **full-run-only** like §D: a
  **quick-only** version has no fingerprint, so its cell reads "full analysis only" — silent, not an error
  (RC-INV-7), exactly as the reference column does (D-INV-22). `F-INV-5`
- **Completeness.** A version **missing a fingerprint axis is not comparable**, so it neither lists neighbours
  nor is offered AS a neighbour to others (it would be a fabricated nearest) — its cell reads "can't compare —
  ⟨missing signals⟩" from the same run manifest as the coach, the catalog, and §D (E.3, RC-INV-5a). `F-INV-6`
- **A library of one (or of one placeable track).** With no other placeable own-track, the column reads
  "no comparison yet" rather than an empty cell that looks broken. `F-INV-7`
- **Recompute, never stale.** Neighbours are a pure function of (the library's fingerprints, the current
  normalisation epoch); when the library grows or an epoch changes, every row's neighbour list recomputes and
  re-stamps together (D-INV-12/14) — the catalog never shows a neighbour the current geometry no longer
  supports, and never points at a deleted version (cascade like D-INV-13). `F-INV-8`
- **The two columns side by side.** The reference column (§D.10) and this own-library column read the same
  fingerprint geometry but answer different questions (a *direction* you reach toward vs a *sibling* already in
  your library); they are two named columns, never merged, and only the reference one is under the references
  switch. `tags: two-columns · cross-link §D.10`

### F.4 Open decisions (need Alexander)

- ⟨DECIDE F-1⟩ click-to-scroll when the target row is filtered out (clear filter vs surface-the-row).
- ⟨DECIDE F-2⟩ do own-library neighbours also appear on the per-track plaque (and open the track), or stay
  catalog-only for 1.0 (recommend catalog-only).
- ⟨DECIDE F-3⟩ how many neighbours — **SETTLED 2026-06-25 (Alexander): up to 3, and only the close ones**
  (high/medium proximity bucket, D-INV-26), so a distant sibling is never listed as if close (F-INV-1).
- ⟨DECIDE F-4⟩ the distance measure for own↔own — **SETTLED 2026-06-25 (Alexander): inherit §D's straight-line
  (⟨DECIDE D-17⟩), one geometry across the whole tool.**
- ⟨DECIDE D-27⟩ (shared with §D.9) the own-library high/medium/low bucket boundaries — relative to the
  library's own distance distribution, since §F has no cloud spread to borrow.
- **Placement (P-1).** This column is the **other of the last two columns**, beside the §D.10 reference one,
  with the same slightly-smaller font (Alexander 2026-06-25). Both are catalog-tail columns.

## E. Run completeness & missing measurements (cross-cutting — applies to §A, §B, the catalog incl. its §D.10/§F similarity columns, §D, and §F)

Every reading in this tool stands on measurements from one **run**. But a run can be **partial**: a quick run
has no stems at all; an older run predates a signal (no `sustain` field); note transcription may have covered
only some stems (the real case that forced this section — Lazy Sparks was transcribed on the `other` stem
only, so bass/lead note-counts came back **0 — meaning "not measured", not "no notes"**). The danger is
uniform and shows up anywhere a number is read or compared: a missing measurement silently read as a real
**0** becomes a false musical claim ("no bass notes", "dead pad") or a false distance ("identical here"). This
section is the one rule for that, shared by the coach, the catalog, and the reference layer — so no surface
has to reinvent it, and the prover can check it once. `tags: §A-significance-debt · D-INV-9 · D-INV-16`

### E.1 The state every measurement carries

**A measurement is either *measured* or *missing* — and missing is a real, first-class state, never a value.**
"Missing" means the step that would produce it did not run or produced nothing for this signal/stem on this
run (quick mode → no stems; old schema → no `sustain`; transcription skipped a stem; a step failed). It is
**distinct from a measured zero / silence**: a stem measured and found near-silent is *measured* (and handled
by the §A significance gate — `STEM_EMPTY_FLOOR_DB`); a stem never analysed is *missing*. The two must never
collapse into the same 0. `RC-INV-1`

**A run carries a completeness manifest — which signals and stems it actually has — so every reader branches
on data, not assumption.** The pattern already exists (`masking.json` lists `stems_analysed`); this generalises
it: from a run you can ask "is axis X present here?" without guessing from a value. Readers consult the
manifest, not a sentinel number. `RC-INV-2`

### E.2 What must never happen (safety)

- **Missing is never silently imputed to a real value and then shown or compared.** No step fills a missing
  measurement with 0, the pool mean, or any default and then treats it as measured — in a card, a read, a
  catalog cell, a fingerprint axis, or a distance. Imputation for an internal projection is allowed **only**
  when its result is not presented as a measured fact and the gap is disclosed (the reference layer already does
  this the honest way: a fingerprint missing any axis is **not comparable**, D-INV-9). `RC-INV-3`
- **A surface renders a missing measurement as "not measured" (not measured), never as a number or a bar.** A
  card or read that would rest on a missing measurement is **omitted** (it has no evidence — the §B.13 based-on
  line and §D's D-INV-10 already require evidence; missing = no evidence = no claim). A per-facet bar / catalog
  cell for a missing axis shows the explicit not-measured marker, never a zero-length or centred bar that reads
  as data. `RC-INV-4`
- **Any pairwise comparison is computed only over axes present on BOTH sides; a missing axis is dropped from
  that pair, never scored as a 0-gap or a max-gap.** This binds every comparison the tool makes — fingerprint
  distance, the per-facet reference read, the reference-explorer divergence, and a direction's centroid. A
  missing axis must not read as "identical" (0 gap) nor as "maximally different"; it is simply **not part of
  that comparison**, and the result discloses how many axes it was computed over. `RC-INV-5`
- **Too few shared axes ⇒ "not comparable", never a number.** When two sides share fewer than `MIN_SHARED_AXES`
  = **10** measured axes (Alexander 2026-06-25), the pair is declared **not comparable** — the same honest move as a
  fingerprint that can't be placed (D-INV-9) — with a one-line "too few shared measurements (N)" note, never a
  distance of 0 (false "identical") or a filled bar. The floor guards against **missing DATA, not dissimilar
  music**: two very different tracks that are both fully measured share all axes and SHOULD be compared (a big
  divergence is the useful answer). The floor only fires between two *full* runs where one is partial enough to
  share too little; a quick run never reaches this test at all, because reference is full-run-only (D-INV-20) —
  forcing a comparison where too little is shared. `RC-INV-5a`
- **Ranking directions uses distance PER shared axis, never the raw sum.** Because two directions can share a
  different number of axes with your track (different members miss different signals), raw Euclidean sums are
  not comparable across directions — more shared axes inflate the sum and would bias "nearest" toward the
  direction you happen to share fewest axes with. So the nearest-direction verdict ranks on **per-axis (RMS)
  distance over each pair's shared set**, or over the single axis set common to all candidates; disclosing the
  axis count (RC-INV-5) is necessary but not sufficient — the rank must be axis-count-fair. `RC-INV-5b`
- **A direction's centroid (or any pooled summary) is averaged per-axis over only the members that HAVE that
  axis; a member missing an axis does not drag it toward 0.** One reference track lacking `sustain` must not
  pull the cloud's sustain toward zero. An axis no member has is **absent from the cloud**, not zero.
  `RC-INV-6`

### E.3 How it composes with the views and the run modes

**Completeness rides the view ladder, it doesn't break it.** The ladder is `quick ⊆ Simple ⊆ Detailed`
(INV-18/22): quick is the stemless run, so every per-stem axis is *missing-by-mode*, and the calm read simply
**doesn't offer** per-stem character there — nor the whole reference/compare feature (full-run-only, D-INV-20)
— it never shows a stemmed claim as "not measured" clutter, because at the quick rung those surfaces aren't
promised at all. Within a full (stemmed) run, a per-stem axis that a *partial* run failed to measure DOES
surface as "not measured" on Simple/Detailed, because there the surface IS promised and its absence is
information. So: **missing-by-mode is silent (the rung never promised it); missing-within-a-promised-surface is
shown.** `RC-INV-7`

**The same missing axis reads identically in the coach, the catalog, and the reference layer** — one track's
fingerprint, its catalog row, and its dot/divergence in §D all draw "not measured" from the same manifest, so a
facet can't read as present in one surface and absent in another. `RC-INV-8`

**Which per-stem surfaces each rung promises is stated once, and RC-INV-7 keys off it.** The view ladder
(INV-18/22, §B.14) is the authority for what is promised at quick / Simple / Detailed; missing-by-mode vs
missing-within-a-promised-surface (RC-INV-7) reads "promised here?" from that ladder, never from a second,
divergent list — so two builders can't disagree on whether a failed pad-transcription shows "not measured" in
Simple. `RC-INV-7a`

**Absence-of-card from missing data is disclosed once per run, so a clean widget isn't misread as all-clear.**
A coach read omitted for a missing input (RC-INV-4) looks identical to "nothing to flag here"; to keep that
honest the run shows a single completeness line — "measured N of M signals; skipped: ⟨reads⟩" — in the same
register as the §B.13 based-on line, not one note per suppressed card. `RC-INV-12`

### E.4 Choosing the run, and closing the gap

**When a track has several runs, the tool reads from the most-complete one** — it prefers a run that has the
richer measurement set (e.g. `sustain` present, and the most stems transcribed) over an older/partial run, so
a usable measurement is never missed just because the newest run happened to be thinner. Completeness is
**still checked per-axis at use time** (RC-INV-2) — picking the best run reduces gaps but never assumes them
away. **The chosen run's id is part of the placement content-hash (D-INV-14)** — so when a re-measure produces
a more-complete run and the selection changes, the dependent fingerprint and nearest-direction **recompute and
re-stamp visibly** (D-INV-12), they never drift silently to a new spot. `RC-INV-9`

**A stem whose significance-gate inputs weren't measured is `unknown`, not `insignificant`.** The §A
significance gate needs loudness (and, when built, time-coverage) data; on a run that lacks it (quick mode, a
partial stem) the stem is **significance-unknown**, a third state distinct from `significant` /
`insignificant (quiet/empty)` — shown as "not measured", never dropped as empty. This is the §A debt seen on
the completeness axis: a not-measured stem must not masquerade as a measured-silent one (RC-INV-1). `RC-INV-11`

**A partial run is a TECHNICAL ERROR — flag it and re-run; never invent the value.** (Alexander, 2026-06-25: a partial run is a technical error — don’t fake or invent around it) When a measurement that the run's mode **should**
have produced is missing (Lazy's un-transcribed bass/lead notes; an old run with no `sustain`), the run is
**incomplete** — the tool says plainly "incomplete run — re-run" and the user re-runs it; it is NOT
auto-fixed, NOT imputed, NOT silently degraded. This is distinct from **missing-by-mode**, which is not an
error: a quick run has no stems *by design* (RC-INV-7), so per-stem axes aren't "broken", they're simply not
promised. So: *should-have-measured-but-didn't* = error, re-run; *mode-never-promised-it* = silent. Until a
genuinely-incomplete run is re-run, its missing axes stay *missing* under the rules above (dropped from
comparison, shown as "not measured"). ⟨DECIDE E-1⟩ **RESOLVED — flag-and-re-run, manual; auto-trigger rejected**
(a Demucs/transcription re-run is expensive and surprising — the user pulls the trigger). `RC-INV-10`

### E.5 Decisions (settled 2026-06-25, Alexander)

- **E-1 — SETTLED:** a partial run is a technical error → flag "incomplete run — re-run", manual re-run,
  no auto-trigger, no imputation (RC-INV-10). Missing-by-mode (quick has no stems) is not an error.
- **E-2 — SETTLED:** `MIN_SHARED_AXES` = **10**. Below 10 shared measured axes a pair is not comparable
  (RC-INV-5a) — guards against too little DATA (quick vs full), not against dissimilar music.

## C. (RESOLVED) Increment-1 inputs that needed Alexander's domain call
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
  instrument — Alexander makes electronic music, so a `vocals` stem is usually a synth. We label by measured
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
- **measured vs missing vs measured-zero** (§E) = three different things that must never blur. *Measured* = the
  step ran and produced a value. *Measured-zero / near-silent* = the step ran and the value is ~0 (a real
  musical fact — handled by the §A significance gate). *Missing / "not measured"* = the step never ran for this
  signal/stem on this run (quick mode, old schema, an un-transcribed stem). A missing value read as a real 0 is
  the bug §E exists to prevent.
- **completeness manifest** (§E) = the list a run carries of which signals/stems it actually measured, so a
  reader asks "is this axis present?" instead of guessing from a sentinel number. Generalises
  `masking.json: stems_analysed`.
- **partial run** (§E) = a run missing some measurements another run of the same track could have (fewer stems
  transcribed, an older schema, quick mode). The tool reads from the **most-complete** run available and still
  checks each axis at use time.
- **quick — run mode, not just a view** (clarified 2026-06-24). "quick" is a *cheaper run* (`tc-quick`,
  no Demucs stems) that produces a **mix-mode player** (one source, transport + seek, no mute/solo grid —
  §B.14). The view ladder `quick ⊆ Simple ⊆ Detailed` (INV-18/22) describes what's VISIBLE at each rung;
  Simple/Detailed are view toggles within a full stemmed run, while quick is the stemless run beneath them.
  So "quick" names one thing — the stemless run and the calm view it shows — not two. **Quick is not
  referenceable** — with no stems there is no fingerprint, so §D reference/compare is full-run-only (D-INV-20).
- _(0.9 reference-layer terms — reference direction, aspiration mapping, in-zone/diverge, «своё», mood/style
  read, fingerprint, the «leans toward» line — are defined once in §D.1 Terminology, not duplicated here.)_
