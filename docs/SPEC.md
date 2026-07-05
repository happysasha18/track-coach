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
- **metre changes** — arrangement-level time-signature shifts read from the master time-signature
  automation envelope (`EnumEvent`s on the `MainTrack`'s `TimeSignature` parameter), NOT from
  `RemoteableTimeSignature` (which is per-clip only). Encoding: `log2(den) * 99 + (num − 1)`;
  e.g. 201 = 4/4, 309 = 13/8, 404 = 9/16. `tags: parse_als/decode_ts_enum`

## B. The credibility layer — never say more than the numbers support

This is the foundation: one rule, and the concrete consequences of taking it seriously. Everything below is
shipped and tested. The detail under each point is precise on purpose (it's what the tests check); read the
bold headline of each to get the shape, drop into the detail when you need the exact threshold.

**The one rule (CR-1).** track-coach never presents, as fact, a number it can't stand behind. If the input
for a claim is too weak to be real, the claim is **left out with a one-line note**, not dressed up as a
finding. "Don't cry wolf, and don't paint silence."

**What that forces (each first found by deed on a real track — Lazy_Sparks):**

- **CR-2 — empty stems are not PARSED, but stay VISIBLE and IDENTIFIED.** A stem below the floor is dropped
  from *analysis* — no notes / rhythm / masking / per-stem viz (nothing honest to read in silence), and it is
  never placed in the rhythm tiles (no pulse in silence). But it is NOT erased: it stays as a **muted, labelled
  row in the player lanes** and is **named in the omitted note** (`"stems Bass Sub, low-mid omitted — too
  little material to read"`), each via its identifying near-silent label (`INV-STEMNAME-NEARSILENT-ID`), never a
  bare count and never an anonymous "near-silent, near-silent" (that was the s45 regression — the fix that
  excluded them from the lanes/tiles erased which stem they were; Alexander wants them SEEN, identified).
  The acknowledgment itself must RENDER — a missing lane reads as a decision, not a bug. `INV-42`
  Evidence: Lazy_Sparks vocals −92 dB (peak −61), piano −88 dB (peak −42). ⟨DECIDE⟩ floor value →
  **SETTLED §B.2: −55 dB broadband (`STEM_EMPTY_FLOOR_DB`)** — reused the existing empty-caveat floor, no
  dedicated peak floor. **INV-45 (APPROVED — Alexander 2026-07-03): a near-silent stem's lane starts MUTED
  on first load** (`build_widget.py:3868`, `if(startMuted)a.muted=true`). This avoids surprise silence
  when the producer hits play (a muted lane carries no real content). The mute is cosmetic-initial only:
  the M/S buttons still work, and the lane is visible and identified as usual (CR-2 visibility unaffected).

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
- **INV (label set).** The displayed lane label is EXACTLY one of three FORMS (this is a pattern, not a fixed
  member list — the near-silent form is stated as a pattern per `INV-STEMNAME-NEARSILENT-ID` below, so a
  membership test asserts the FORM, not a frozen word set):
  - a **character label** — one of `bass`, `drums`, `perc`, `hats`, `lead`, `melody`, `chord`, `pad`, `mid`,
    `high` — when the stem is **significant**;
  - the pattern **`⟨identifying word⟩ (near-silent)`** when the stem is **measured and found empty** — the
    identifying word is the mapped real project-track name, ELSE a frequency-band descriptor
    (`low`/`low-mid`/`mid`/`high`); always suffixed ` (near-silent)`, **NEVER a bare `near-silent`** (that
    erased which stem it was — the s45 regression);
  - **`not measured`** when significance is unknown / character unmeasurable (the third stem state from
    §A/RC-INV-11 — distinct, never collapsed into "near-silent").
  **`kick` is NOT a lane label.** A `drums`-family stem renders as `drums` (§B.7 trusts the low families), and a
  low+percussive UNTRUSTED stem is itself the drums family — so no path emits a standalone `kick` lane. `kick`
  lives ONLY in the drum-hit breakdown (§B.11 — the kick/snare/hat sub-parts) and its stem colour there; it is
  never a member of the lane-label set, so a membership test must not carry it. (F4, s54: closed the phantom
  member the prover flagged.)
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
- **INV-STEMNAME-ALL (0.9.22, s45 — Fable pre-1.0 blocker #1; the §B.7 rule now binds EVERY surface, not just
  the lane).** The bug: the SAME stem showed DIFFERENT names across surfaces (arc bar "lead: other" · player
  lane "melody" · rhythm tile "other" · notes "Demucs's 'other' stem"), and raw splitter/model/tool names
  (`other`/`vocals`/`guitar`/`piano`, `Demucs`/`htdemucs`/`htdemucs_6s`, `basic-pitch`) leaked. Rule:
  - **ONE display name per stem, resolved ONCE at build.** `stem_display_name(stem)` has three branches: (1) the `stem_character` label when the stem is **significant**; (2) an **IDENTIFIED near-silent label** when the stem is **measured and found empty** — the mapped real project-track name if the stem maps to an `.als` track (via `stemmap`), ELSE a frequency-band descriptor (`low`/`low-mid`/`mid`/`high`, derived from the stem's dominant band) — always suffixed ` (near-silent)`; **NEVER a bare `near-silent`** (that erased which stem it was — the s45 regression, Alexander), and **NEVER the raw Demucs family word** (`piano`/`vocals`) even for an empty stem (Alexander's standing rule: those labels lie for electronic music); (3) **`"not measured"`** when the stem's significance is **unknown or the character cannot be computed** (significance-gate inputs absent, quick-mode stem, partial run) — distinct from near-silent, per §A/RC-INV-11: a not-measured stem must never be read as measured-silent. **NEVER** the raw Demucs family name on any path. `INV-STEMNAME-NEARSILENT-ID` (= `INV-44`; s46, Alexander): every near-silent stem carries an identifying word (track name or frequency band) + the `(near-silent)` qualifier — two near-silent stems can never collide into an anonymous "near-silent, near-silent". The full `{raw_stem → display}` map ships in the payload as `stem_display`; every JS surface reads it through one `disp(stem)` helper; every Python surface uses the same resolver. Same stem ⇒ identical word on the arc bar, player lane, rhythm tiles, stem↔project panel, masking cards, notes title. `INV-STEMNAME-NOTMEASURED`
  - **No model/tool name in ANY user-facing string.** `Demucs`→"the separator/splitter", `htdemucs_6s`→"a
    6-stem model" (established 0.9.21), `basic-pitch`→"read from the audio". Applies to static STRINGS
    (`play_note`, `map_hint`, `note_hint`, `note_hint_other`) AND prose from `map_stems.py`
    (`verdict_text`, `model_why`, `model_recommendation`).
  - **The three deliberate-different-name surfaces (§B.7 above) still hold** — they differ in JOB (best-guess
    rec vs role-headline vs track-sub-line), never by leaking a raw name; all three draw from the one resolver.
  - **Guard (class-level, catches future regressions):** a rendered widget on the NO-`.als` path (the leaking
    path) contains NONE of the raw tokens in user-facing text: `other`/`vocals`/`guitar`/`piano` as a standalone
    part name, `Demucs`/`htdemucs`/`htdemucs_6s`/`basic-pitch`. Test `NoRawStemNameOnAnySurface`. One instance
    reported ⇒ whole class owned (Alexander's "never patch pointwise").
  - **Partition of stem-name surfaces (F1/F5 — explicit two-column split, s45 pre-1.0 gate).** Two named sets,
    never conflated:
    - **Byte-identical set** — all via the `disp()` resolver, same word for the same stem on BOTH the `.als`
      and no-`.als` path: **arc bar, player lane, rhythm tiles, stem↔project card title, masking cards, notes title.**
      Property: "Every surface in the byte-identical set renders a stem via `disp()` and shows the same word for
      the same stem on BOTH the `.als` and no-`.als` path." `INV-STEMNAME-PARTITION`
    - **Deliberate-different set** — differ by JOB (not by leaking a raw name): the `late_entry` rec (best
      single guess: character → clear track-name → "a new element"); the lane sub-line (real project track name
      when the stemmap verdict is `clear`); AND the **arc-bar scene-lead WHEN a `.als` IS PRESENT** — it shows
      the real project ARRANGEMENT track name (e.g. "Lead Synth"), which is domain-correct and a different job
      from the stem's character role. ⟨pending Alexander's confirm — he may want the arc lead to match the
      lane's character role (fold into byte-identical set) rather than show the arrangement name⟩
  - **Back-compat (F4 — widgets deposited before 0.9.22).** When `stem_display` is absent from a payload (any
    widget deposited before 0.9.22), no surface shows the raw stem key — the `disp()` fallback is `"a part"`,
    never the raw key — and every deposited widget is **re-rendered to the current version before a release**
    (the CLAUDE.md re-render-all rule applied as a ship precondition, so the catalog never opens a stale leaking
    widget). `INV-STEMNAME-BACKCOMPAT`

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
  `INV-32`
- **NOT a card** (no fake action) — an observation IN the read. The helper is pure + unit-tested; the prose is
  authored, and `SKILL.md` carries the writing rule so every read includes it.
- **Standalone (2026-06-23, by deed on Wobble — a Demucs run with NO authored narrative):** the line renders
  even when there's no authored read, so a developing track without a written read still gets this one real
  observation. The producer's read hides ONLY when BOTH the dev line is empty (flat track) AND there's no narrative.
  (This SUPERSEDES the earlier "empty narrative → panel always hidden" rule.)

### B.13 Card evidence — every card names where it came from (the "based-on" line; 2026-06-23, Alexander)
Alexander: *"show which signals drove each card."* Every recommendation card carries a plain
line saying what it is **based on**. The credibility trap (memory `track-coach-card-evidence`): a raw lone
number/tag says nothing — *"dynamics 30.7 — is that a lot? measured in what, oranges?"* (Alexander). So the based-on line is
in **plain language, never a bare metric identifier** (`true_peak_db`, `dynamic_range_db`). It names the
**result and a simple unit** (a dB figure, a percentage, a time) but **not the measurement METHOD** — the
technical *how* (`4× oversampled`, `peak-to-RMS`, `self-similarity`) is a signal-processing detail, not the
finding, so it stays out of the user-facing line (Alexander 2026-07-02). `tags: result-not-method`
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
  (2) navigation — a click takes you to the card's evidence (the block below). The attention pulse is a
  **CSS/DOM class toggle on the target panel — it does NOT touch the canvas drawing** (deliberately low-risk:
  the canvas render is the fragile surface we never edit blind). A deeper per-lane / per-part highlight (light
  up the exact lane the card is about) stays deferred — it needs canvas work and a live render review. `INV-34`

**A card leads to ITS evidence — the click shows what the based-on line names (2026-07-05, the navigation
half of Alexander's "card evidence" wish).** The based-on line SAYS where the advice came from; clicking the
card SHOWS it. Before this, every clickable card scrolled to the story arc even when its evidence renders
elsewhere — the automation card pulsed the arc while the "intention vs result" envelopes sat further down,
closed; the tonal-resonance card wasn't clickable at all though the offending band is right there in the
Tonal-balance bars.
*Fences — neighbouring promises that stay true through this change:* the based-on line itself is untouched
(INV-31); the pulse stays CSS/DOM-only (INV-34, above); a timecoded card's click still seeks the playhead and
seek still preserves playback (§B.14, INV-33/38); the view ladder is untouched — a card click never switches
Simple↔Detailed and never writes `tc_view` (§B.15, INV-41); the `?direction` entry-focus path is unaffected
(D-INV-37).

- **Every card carries an evidence target** — the id of the panel where its based-on evidence actually
  renders, shipped on the card as `ev` in `D.recs`. The map is honest — a card whose evidence has no
  dedicated panel keeps the story arc, because the player IS that evidence (seek to the worst moment, solo
  the named parts): `INV-48a`
  | evidence target | cards |
  |---|---|
  | `#storyPanel` — the arc + player | structure/arc/energy family (long section, flat energy, brightness, ending≈opening, wobble, climax, plateau, breakdown), late entry, per-part repetition, masking, per-stem cards |
  | `#tonalPanel` — the spectrum bars | tonal resonance |
  | `#vitals` — the master's numbers strip | true-peak clipping, squashed dynamics |
  | `#rhyPanel` — drum timing | swing |
  | `#autoPanel` — intention vs result | automation parts-ways |
- **Click = seek (when timecoded) + reveal + pulse the TARGET.** Clicking a card whose target panel is
  present scrolls THAT panel into view and fires the attention pulse on it — one shared pulse style for every
  target, so the emphasis reads the same everywhere `[default]`. A timecoded card seeks the playhead first,
  exactly as today. `INV-48b`
- **Global cards become clickable too** — a whole-track card (tonal resonance, squashed dynamics…) with a
  present target gets the same pointer cursor + jump title as timecoded cards and navigates on click (no seek
  — it has no moment). Simple never sees this: it hides global cards (INV-22), so the interaction exists only
  where the card does. `INV-48e`
- **A collapsed ancestor opens on the way.** `#rhyPanel` and `#autoPanel` live inside the collapsed
  "Evidence & detail" drawer — navigation sets `open` on every closed ancestor `<details>` before scrolling,
  so the click never lands on a shut drawer; the user can fold it back, nothing is persisted. `INV-48c`
- **A missing target degrades to today's behaviour.** When the target panel isn't in this run's DOM (quick
  run, no `.als`, a data-gated panel): a timecoded card behaves exactly as before (seek + story-arc scroll +
  pulse); a global card renders NOT clickable — no cursor, no title, no dead click. `INV-48d`
- *Composed across the axes:* view — targets in the map are visible in both Simple and Detailed (nothing in
  the map is Simple-hidden; `#stemlanes` is inside `#storyPanel`, whose container always shows), and the
  click changes no view state; mode — quick runs simply lack most sources, so INV-48d covers them; viewport —
  the same scroll-into-view at any width, panels stack vertically `[default]`; persistence — navigation
  writes NOTHING (no localStorage, no URL), reopening the widget starts neutral; touch — a tap is the click,
  the hover title is advisory only, never the sole affordance `[default]`; keyboard — card clicks stay
  pointer-only this increment, parity with the existing timecoded cards `[default]`, a known gap; empty/
  error/loading — the widget is a static local page (no loading state) and INV-48d is the empty/error rule;
  performance — one class toggle + one scroll per click, no envelope change; two windows — no shared state,
  two open copies never interact.
- *Non-goals:* the per-lane canvas highlight (stays deferred, above); a graph→card BACK pointer (clicking a
  moment on the arc to light its card) — a separate story; any change to the based-on wording; any automatic
  view switch. *Success measure:* on the library tracks, clicking one card of each family lands the panel its
  based-on names in view with the pulse on it — verified by deed at landing; no usage counter `[default]`.
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
     never `(some stem muted) AND (some stem soloed)` simultaneously. `toggleStem` guarantees it. `INV-35`
  2. **Solo resolves gains.** When `anySolo`, the audible set is EXACTLY the soloed stems (every non-soloed
     stem is muted), regardless of individual mute flags. `INV-36`
  3. **Mute resolves gains.** When NOT `anySolo`, audible(stem) = `!stem.mute`. `INV-37`
  4. **Seek preserves transport AND mix.** A seek does not change any stem's `{mute, solo}` and resumes iff
     it was playing (a seek while paused stays paused). So: solo a stem → seek while playing → the same one
     stem is still the only one audible AND playback continues (INV-33 generalised to the combination). `INV-38`
  5. **Seek clamps.** The resulting time is always in [0, dur]; a gutter/negative/over-dur click never seeks
     out of range. `INV-39`
  6. **The player COMPOSES with the VIEW axis — solo/mute is a Detailed-only capability (2026-06-23, Alexander
     found by deed: solo a stem → switch to Simple → the soloed part visually vanishes and you can't un-solo
     it).** The stem grid (`#stemlanes`, where the M/S controls + waveforms live) is hidden in Simple and
     absent in quick (the view ladder, INV-18/22). So a per-stem mute/solo state is only **visible and
     reversible in Detailed**. Invariant: **entering Simple RESETS the per-stem mix to the full mix**
     (`resetMix` clears every mute+solo, then `pgains` → all audible) — so the user is never left hearing a
     solo / muted part they can't see or undo. Re-entering Detailed starts from the full mix (no hidden
     leftover state). This is the general rule the original §B.14 missed by modelling the player on the audio
     axis ALONE: an interactive surface must be specified across EVERY view/mode axis it lives under, not just
     its own. (Quick never has the grid, so it never reaches this state.) `INV-40`
- **Mix-mode (quick run).** One source, transport + seek only — no mute/solo grid; `pgains`/`toggleStem`
  are not wired (a single source is always audible). `seekResult` still governs its seeks.

### B.15 The view selector as remembered state (2026-06-29, Alexander — one global view, calm on first use)
The Simple/Detailed selector is the second interactive widget-state machine (beside the player, §B.14). Until
this pass each widget opened in Simple and **deliberately did NOT restore** a prior choice — the "opens calm by
default" stance (it was even in the skill's one-liner). Alexander revised that (2026-06-29): the chosen view is
**remembered and uniform across all tracks**, so opening any track lands you in the view you last used — *but a
brand-new user still meets the calm screen first.*

- **State + storage.** The current view ∈ {`Simple`, `Detailed`} is a **single global preference** persisted in
  `localStorage` (`tc_view`), shared by every widget — not per-widget URL-only state. Toggling the selector
  writes it; the next widget you open reads it. (Quick is a run MODE, not a selectable view — it is never
  stored as a view choice; a quick run shows its quick rung regardless of `tc_view`.) The `localStorage`
  reach across `file://` widgets is **verify-by-deed** (browser-dependent); if it doesn't share, an equivalent
  global-scope mechanism stands in — the rule is "one remembered view", not the specific store. `INV-41`
- **Write rule (only a toggle persists).** **Only an explicit view toggle writes `tc_view`**; resolving the
  open view from a URL hash or from the calm default **never writes the store**. So a shared `#detailed` deep
  link is genuinely one-shot — it opens Detailed for that visit but never flips your durable preference. `tags:
  one-shot-hash · INV-41`
- **Read-on-load, no live cross-tab sync.** A widget reads `tc_view` **once on open**; an already-open widget
  does **not** retro-change when another widget toggles. Uniformity is across the NEXT open, not live across two
  open tabs — two simultaneously-open widgets may briefly differ until reload, by design (simplest, no
  cross-tab listener). `tags: read-on-load · INV-41`
- **Degrade-safe.** If the store is unavailable or throws (private mode, a `file://` restriction), the selector
  **degrades to calm-default-per-open and never errors view initialisation** — the old always-calm behaviour is
  the safe floor; a store failure can never leave the widget with no view class / broken layout. `tags:
  degrade-safe · INV-41`
- **On open (precedence).** A widget picks its initial view by: (1) a one-shot **URL hash override**
  (`#detailed`/`#simple`) if present — the entry-focus pattern, for a shared/deep link; else (2) the remembered
  `tc_view`; else (3) **calm (Simple)** on the first-ever open, before any choice exists. So a newcomer still
  meets the calm screen; a returning user lands where they left off. The hash is a one-shot entry, not a
  persisted channel; the remembered preference is the durable one. (Alexander 2026-06-29: remember last,
  first-use calm.) `tags: view-state · entry-override · calm-first-use · INV-41`
- **It does NOT touch the ladder.** This changes only WHERE the initial view comes from, never WHAT is visible
  at each rung — `quick ⊆ Simple ⊆ Detailed` (INV-18/22) is untouched, and entering Simple still resets the
  per-stem mix (§B.14) so no soloed part strands. Remembering Detailed never makes a Simple-hidden surface
  visible in Simple; it just opens Detailed when that's your remembered view. `tags: view-ladder-unchanged · INV-41`
- **Why it matters for the reference read.** The reference panel (centroid read + web notes, one container
  since the 2026-07-05 merge, D-INV-36) lives in Detailed (depth, §D.10.3), and Simple hides `#refPanel` —
  its nested disclosures with it. With the old always-calm open it was invisible unless you switched every
  time — the reason a producer couldn't find it. Remembering Detailed is what makes it reliably present.
  `tags: INV-41 · D-INV-30 · D-INV-36`

## D. Reference & Compare — «хочу как Aphex Twin» (0.9)

Point track-coach at someone else's music as a *direction* you're reaching toward, see where your track
already sits relative to it and where it goes its own way, and let that gently re-flavour the coaching you
already get — "more in the style of X". Not a copy: a direction. This section is written to be read by a
human first; the short `tags` at the ends of rule lines are handles for the test matrix and the prover.

> ⛔ **DEFERRED / FUTURE — not in 1.0 (Alexander, 2026-07-03).** The whole "aim / reaches-toward / «leans
> toward»" mechanism is CUT: the aim-setting UI was excised in 0.9.15 (a persisted aim auto-swapped and read
> as broken) and Alexander confirmed it stays out. What ships in 1.0 is ONLY plain **similarity to nearest
> tracks** in your own library — no aim, no re-flavouring, no map (the 2D map was killed: distance in ~50-D
> fakes similarity). The one surviving seed for LATER is a stand-alone **"compare these two specific tracks,
> say where they diverge"** pass — a concrete reference track, no cloud, no aim; it must go through the full
> cycle (spec → prove → matrix → test → audit) before any code, and is not scheduled. **Reference-album
> normalisation, when that future feature is built: normalise over YOUR library only** — importing someone
> else's album must never shift which of your own tracks read as nearest (Alexander, 2026-07-03).
>
> Below is the retained 0.9 DESIGN (proven by `product-prover`, never built) kept for that future pass; it is
> NOT a 1.0 promise. Everything marked ⟨DECIDE⟩ is an open call. Edit history lives in `JOURNAL.md`.

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
  nearest-first selector** (§D.10.1) and a per-direction **web panel** (§D.10.2). See §D.10. (There is
  **no** 2-D/3-D constellation map — dropped 2026-06-26: we show the nearest centroid, not a flattened picture.)
- **the producer's read** — click your track and read, in words, how it sits against a direction.
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

**Reference marker.** The single explicit signal that a run is a reference — a `reference` flag (and the
*artist* name) written into the run's `run_meta.json` at analysis time. You set it by analysing with the
**`--reference` option** (optionally `--artist NAME`); that is the only thing that writes the flag, and it is
a deliberate user act, never inferred. It is what tells the storage layer
"this is someone else's music, keep it out of my library" (the ingest guard, §G G-INV-18). **Having no
Ableton project is NOT the marker** — you also analyse your own audio-only tracks (an mp3 bounce with no
`.als`), so `als: null` cannot distinguish a reference from your own work. Only the explicit `reference`
flag does. A run without the flag is treated as your own track. `tags: audio-only · D-INV-3 · G-INV-18`

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
development trends, the tonal palette, density, meter rate, repetition). **The fingerprint has N = 14
producer-facing axes (`fingerprints.py` AXES).** Invariant: a fully-measured pair shares all 14 axes, and
14 ≥ MIN_SHARED_AXES (10), so two complete runs are always comparable (confirmed by deed — the shipped 3-track
catalog produces working comparisons). `D-INV-20b` This is geometry: it grounds the
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

**The two surfaces — the «leans toward» line and the producer's read.** The «leans toward» line (§D.10) is the
glanceable handle: a catalog column + a Detailed plaque chip naming the nearest reference direction with a
colour closeness cue. The producer's read opens when you click your track: "leans toward Venetian Snares", the
in-zone/diverge read, "своё", each backed by its evidence. The producer's read is a *read* (observation), it
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

### D.6 How the coaching changes — re-flavouring (the payoff) — POST-1.0 (deferred, not a 1.0 promise)

> **POST-1.0 — CUT FROM 1.0 (FINAL — Alexander, s54, 2026-07-05). This supersedes the earlier ⟨pending⟩
> marker; the cut is DECIDED, not open.** The only input surface for aspiration mapping (the aim picker,
> ⟨DECIDE D-2⟩) was excised in 0.9.15, so re-flavouring, the aim glyph, and pinned-aimed entries have no way to
> be created. **1.0 §D ships as a DESCRIPTIVE mirror only** — nearest reference direction ("leans toward"), the
> per-facet centroid read, the web panel, and §F own-library — with no aspiration mapping and no re-flavouring.
> Everything in this §D.6, and the aim-dependent parts of §D.10.1, are **inert in 1.0 and must NOT read as 1.0
> promises**: the inert invariants are D-INV-4 / D-INV-13 / D-INV-15 / D-INV-17 / D-INV-18 and the aim-glyph
> parts of D-INV-28.
> **Why aim waits (kept, do NOT lose).** The 0.9.15 excision happened because the persisted-per-track aim
> (`localStorage`) auto-swapped the cards for the re-flavoured set and hid the centroid `#refRead` on reopen —
> the widget "looked broken." Any future rebuild's spine is a **"never looks broken on reopen"** rule: a
> restored aim is visibly labelled, never silently swapped; the centroid read never vanishes; composition
> across persistence/reopen × view × references-switch is proven before code. Post-1.0 idea to explore: a
> **minimal aim expressed IN the centroid read itself**, not a separate persisted picker.
> Design text below is preserved for that rebuild.

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

### D.6.1 — REMOVED 0.9.15 (see JOURNAL 2026-07-02)

_What it was:_ the in-widget aim picker (`#aimpanel`) and «toward X» panel — a `<select>` dropdown letting you pick a reference direction and see a ranked list of steps toward it (ordered by per-facet divergence toward the aim), persisted per-track in `localStorage`.

_Why removed (0.9.15):_ redundant while one offerable direction equals the measured lean; the persisted localStorage state also caused a visible regression on reopen (cards swapped for re-flavoured set, centroid `#refRead` hidden, widget looked broken). Decision: Alexander, s33.

_History lives in:_ JOURNAL 2026-07-02 (excision details) and CHANGELOG 0.9.15.

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
- ⟨DECIDE D-2⟩ **SETTLED 2026-07-01 (Alexander):** the aim is set **in the widget, from a dropdown**, and
  persists per-track in `localStorage` (same mechanism + file:// share-caution as `tc_view`, INV-41). Clearing
  it returns the track to plain coaching. The dropdown drives the new **aim panel** of prioritized steps
  (§D.6.1, D-INV-31/32/33/34). Not a file the user hand-edits; not a re-run.
  _(Feature REMOVED 0.9.15 → see §D.6.1 tombstone and JOURNAL 2026-07-02.)_
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
- D-24 (resolved) runner-up direction — **RESOLVED 2026-06-26 by listing, not tinting (§D.10.1, D-INV-27).** The
  earlier worry (a *tied* second under relative lean means the nearest does NOT stand apart, so a second tint
  in one cell is self-contradictory) dissolves once the surface is an **up-to-three nearest-first selector**:
  a list HAS an order to carry the ranking, exactly as §F does, so a 2nd/3rd direction is its own ordered,
  cued entry rather than a crammed second tint. No co-leaders tied-pair tint needed.
- ⟨DECIDE D-25⟩ does the **Simple** view also show the compact plaque chip, or does the chip stay
  Detailed-only while Simple keeps "leans toward X" as prose in the read? (recommend: Detailed-only chip;
  the up-to-three selector and the web panel are Detailed-only by §D.10.1/§D.10.2).
- D-29 (resolved) aimed direction outside the three nearest — **RESOLVED 2026-06-29 (Alexander).** Pin **only the
  single nearest of the aimed** ones, as an additive entry (it never displaces a nearer one), shown **even if it
  tints far** because a declared aim is intent, not filler; the other aimed directions live in the producer's read.
  At most one pinned aimed entry. `§D.10.1`
- D-30 (resolved) a web facet the measurement **contradicts** (or can't measure) — **RESOLVED 2026-06-30
  (Alexander): SHOW it, labeled** "web says · our tracks don't show it", sorted into the bottom tier of the web
  panel, never silently dropped. The teaching contrast (web suggested, measurement didn't bear it out) is the
  value he wants. Stays observation about the reference centroid, not a grade of your track (D-INV-1). `§D.10.2`
- ⟨DECIDE D-32⟩ where the **facet→signal map** lives and how it's curated — the table tying a web style phrase
  to a measured axis (★ direct) or a sound indirect signal (☆). It's authored, not learned; recommend a
  versioned in-repo table maintained like the other frozen constants, reviewed when a new ☆ tie is claimed.
  `§D.10.2`
- D-33, resolved 2026-07-01 then removed 0.9.15: the aim picker was kept single-select (multi-select = mix-all model was not restored); the feature was then excised entirely (see §D.6.1 tombstone). `§D.6.1`
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
the full producer's read. It appears in two places but is **ONE surface**: a **column on the catalog** (the library page) and a
**chip on the Detailed plaque** of a track's widget. Both draw the identical fact from the identical
computation; they are not two features, and not a second name for the producer's read. It is one of the **two catalog
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
distance (there is no map). So the catalog column, the plaque chip, and the producer's read can never disagree
about which direction is nearest: one geometry, drawn three ways. `D-INV-21`

**How it composes across the axes.**

- **The view ladder (the plaque chip).** The chip lives in the per-track widget, so it obeys quick ⊆ Simple ⊆
  Detailed. **Quick shows nothing** — reference is full-run-only (D-INV-20): a quick run has no fingerprint, so
  there is no nearest to name. **Detailed shows the chip.** Whether **Simple** also shows it is ⟨DECIDE D-25⟩:
  Simple already carries "leans toward X" as *prose inside the read* (§D.7), which is a different surface (the
  producer's read — authored words) from this glanceable chip. The chip and the read's prose are **not two names for
  one thing** — the chip is a glance handle, the read is the words; both cite the same leans-toward fact. The
  ladder stays monotonic: Detailed adds the chip without removing the Simple-level prose. `tags: view-ladder ·
  D-INV-20 · ⟨DECIDE D-25⟩`
- **The run mode (the catalog column).** The catalog is its own page (**a row per track — its newest
  version**, D-INV-35), governed by run MODE, not the per-track view ladder. A **full-run** version shows its
  leans-toward; a **quick-only** version's cell reads "full analysis only" — the canonical missing-by-mode
  case (D-INV-20, RC-INV-7): quick never promised reference, so the empty cell is silent, never an error and
  never blank-implying-"no direction". A catalog row reads the **newest version's most-complete run** (E.4);
  "full analysis only" shows only when that newest version has **no** full run at all — the cell is read from
  the newest version, never blended across older versions (older versions live only in the track's plaque, D-INV-35).
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
  hides the column and the chip together, and the switch never strands the line where you can't see or restore it. The switch is **one global persisted flag** that both the catalog page and a track's widget read, so hiding references on either page hides both — one flag, never a per-page toggle (D-16 resolved).
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
- **Catalog granularity — one row per track, its newest version.** The catalog lists **one row per track**,
  and that row is the track's **newest version** (by audio mtime / stamp — `library.group_versions` orders
  newest-first, so position 0 is newest). Older versions of the same track do **not** get their own catalog
  rows; they remain listed in that track's **per-track plaque** (the widget plaque already enumerates every
  version). This closes the earlier per-version double-row + amber "older analysis" confusion (Alexander
  2026-07-03): a two-version track is ONE scannable row in the library, and its history lives on its own page.
  **Decision (design A, Alexander 2026-07-03): the row is the newest version STRICTLY** — every catalog cell
  (signature, BPM/LUFS, reference lean, similar-in-library) is read from the newest version's most-complete
  run, never blended across versions; the version **delta** (BPM/LUFS change vs the immediately prior version)
  still renders so the row shows movement. This is consistent with E.4: "most-complete run" is scoped to the
  runs *within* a version, so newest-only loses no measurement that principle protects. The **Version** column
  shows the newest version's label; the `×N runs` chip counts runs within that newest version; the "older
  analysis" (stale tool-version) chip (INV-12) is orthogonal and unchanged. The page **subtitle counts tracks**
  (the rows shown), so the stated count matches what is on screen — never a version total larger than the
  visible rows. `D-INV-35`
- **The catalog speaks product words, never dev internals (Alexander 2026-07-01 — "это ПРОДАКШН для юзеров").**
  A row's label is the track's human title (humanised from the file name when no authored title exists); a raw
  run-folder slug never appears as visible text anywhere on the page. A run dir that broke the
  `<track>/<stamp>` naming convention shows "—" in the Date column — degraded gracefully, never the slug
  leaked as a date. `INV-43`

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
tinting** (D-24 resolved 2026-06-26): the surface shows the **up to three nearest directions as a
nearest-first selector** (§D.10.1, D-INV-27), so a second and third direction are their own clearly-ordered entries — not a self-contradictory second tint crammed into one cell. The old worry (a *tied*
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
entries. The runner-up is resolved by listing, not by tinting (D-24 resolved). `D-INV-27`

**Scope split — every §D surface is marked exactly one of SHIPS-1.0 / DEFERRED-post-1.0 (F1, s54).** The
descriptive rows need no aspiration mapping — only the measured fingerprints — so they SHIP in 1.0; the
aim-dependent rows are inert without the mapping input (⟨DECIDE D-2⟩, cut from 1.0 per §D.6) and are DEFERRED.

| §D surface | id | 1.0 | renders when | gated |
|---|---|---|---|---|
| Reference panel — the ONE container: shared selector + two nested disclosures (merged 2026-07-05, D-INV-36) | `#refPanel` | **SHIPS-1.0** | reference directions are defined for the track | yes — non-null `gated_by` |
| Centroid read — per-facet bars + "leans toward" (nested disclosure, open) | `#refRead` (inside `#refPanel`) | **SHIPS-1.0** | reference directions are defined for the track | yes — non-null `gated_by` |
| Web descriptor — "what the web says about ⟨artist⟩" (nested disclosure, open; follows the selector) | `#webPanel` (inside `#refPanel`) | **SHIPS-1.0** | the focused direction has web content | yes — non-null `gated_by` |
| Up-to-three nearest-direction selector (`.reftab` tabs) | top of `#refPanel` | **SHIPS-1.0** | ≥2 real leans (green/amber; 1 lean = no tab bar) | folded into the `#refPanel` gate |
| Similar in your own library (§F own-library) | catalog `.sib-chip` column | **SHIPS-1.0** | ≥1 own sibling track in the library | yes — via the catalog gate (`test_19_catalog_rows_and_hrefs`) + the D-INV-26 browser colour test (`.sib-chip`); it is a catalog COLUMN, not a standalone panel |
| Aim glyph · pinned-aimed entry · re-flavouring (§D.6) | — | **DEFERRED-post-1.0** | never in 1.0 (no mapping input) | no — not rendered, not gated |

**Property (F1 — the anti-regression net covers what ships).** Every SHIPS-1.0 §D surface has a `USER_SURFACES`
entry whose `gated_by` is **non-null** and asserts the surface POPULATED in a render where its "renders when"
condition holds — since the merge that is the container `#refPanel` AND its nested `#refRead`/`#webPanel`
(registered like the Evidence sub-panels). A build that HAS reference directions yet blanks any of them is a
RED gate, not a thing Alexander finds by eye. The DEFERRED rows carry no gate — they do not render in 1.0.
This closes the prior drift where `#refRead`/`#webPanel` rendered in a normal build but the gate marked them
`DEFERRED` / `gated_by: None`. `tags: scope-1.0-descriptive · F1 · INV-46 · D-INV-36 · ⟨DECIDE D-2⟩ cut per §D.6`

> **POST-1.0 — CUT FROM 1.0 (FINAL — Alexander, s54, 2026-07-05; supersedes the earlier ⟨pending⟩ marker).**
> The aim picker (⟨DECIDE D-2⟩) was excised in 0.9.15 (see §D.6.1 tombstone), so the aim glyph, the
> pinned-aimed-direction entry, and all re-flavouring have no input surface and cannot be created. They remain
> authored here so the composition is proven, but they are **inert in 1.0** and do NOT ship — the cut is
> decided (see §D.6 for the "never looks broken on reopen" rebuild spine). The DESCRIPTIVE rows below DO ship
> in 1.0 (see the per-surface ship/defer table in the scope split above).

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
- **Direction chips/tabs are neutral — nearest-first order carries the rank; only the active chip is highlighted.** Similarity is not normalizable to a meaningful 0–1 scale (Alexander 2026-07-02): a nearer chip could read amber while a farther one read green, which confused rather than informed. The ordering already carries all the closeness information needed: first tab = nearest direction, second = next nearest. Colour-coding the tabs by level added noise without meaning. The active tab is visually distinguished via its `.reftab.active` class (accent border, full opacity); inactive tabs are muted. The facet bars INSIDE each panel retain their green/amber/red colour (those are per-facet, meaningful divergence signals — untouched). `tags: D-INV-27`
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
  picker. Because every click is a jump, nothing on the list page can strand. **Click-to-focus is WIRED
  (2026-07-05, s59):** each direction link carries the track's own widget URL plus the one-shot entry pair —
  `?direction=⟨URL-encoded direction name⟩` and the existing `#detailed` one-shot view override (§B.15) — so
  the widget opens with the read panel visible and focused on that direction; the hand-off mechanics live
  below (URL entry-focus, D-INV-37). *(0.9 history: links rendered with a `#refRead` placeholder anchor.)*
  `tags: clickable-navigation · inline-stack · F-INV-4 · D-INV-37`
- **In the per-track producer's read — ONE reference panel, one selector, both disclosures follow (MERGED,
  Alexander 2026-07-05, his screenshot annotation).** The centroid read (§D.10.3) and the web notes (§D.10.2)
  live in **one container panel** (`#refPanel`, titled "You vs your closest match"), built like the Evidence
  drawer: the panel opens with the **up-to-three direction tabs** (only when ≥2 qualify — one direction means
  no tab bar), then **two nested disclosures, both open by default**: first the centroid read (`#refRead`),
  then the web notes (`#webPanel`). The tabs are the **single shared selector**: the read defaults to the
  **nearest**, and switching a tab re-targets **BOTH** nested disclosures — the per-facet bars AND the web
  notes — to that direction, client-side, in the embedded per-direction content. The two disclosures can
  **never show two different directions at once** (the shipped pre-merge widget did exactly that: bars on the
  selected direction, web notes stuck on the top match — the defect this merge kills). The tab is **ephemeral
  view state** (it changes no analysis, and does not persist across a reload — like the view ladder itself).
  The nested summaries: the centroid disclosure reads **"What the numbers show"** (static — the direction is
  named inside, in the "Leans toward ⟨Direction⟩" header); the web disclosure reads **"What the web says about
  ⟨artist⟩"** and its artist name follows the selector (§D.10.2). **Empty state:** with directions defined but
  nothing to compare, `#refPanel` renders a **NON-expandable stub plaque** — the panel look and title, a plain
  div with a one-line muted note, no arrow, no tabs, no nested disclosures, nothing to open (Alexander
  2026-07-05, s60: a silently absent panel read as a hole, and the earlier one-line `<details>` read as
  broken). The note names the reason in this surface's own words: none clearing the lean bar ⇒ **"no close
  direction yet"**; a run with no fingerprint (an old or partial full run) ⇒ **"no comparison data in this
  run"** — the stub replaces the pre-s60 silent absence for that case; no shared measured facets (degenerate)
  ⇒ **"can't compare yet"**. Never the siblings phrase "No similar tracks" (the pre-merge widget wrongly
  printed it here — fixed with the merge, the phrase is the §F/D-INV-22 vocabulary, never this surface's).
  The stub keeps the `#refPanel` id, so Simple hides it (INV-18/22) and the D-INV-37 entry reader stays
  inert on it. With no reference directions defined at all the panel is absent — the feature isn't in play,
  so there is no absence to announce (gate: `when-reference`); quick renders none of it. `D-INV-36` **The catalog → widget focus hand-off is a one-shot
  URL *entry* parameter, not persisted tab state (WIRED 2026-07-05, s59):** arriving from a catalog
  direction-link (`?direction=⟨name⟩` — the URL-encoded direction name, the SAME name the tab shows: one
  surface, one name), a full widget reads the parameter ONCE on load; if the reference panel renders, it
  activates that direction's tab — bars, web body and web summary artist all follow, through the same path
  a human click takes (D-INV-36b) — and scrolls the panel into view. The view arrives Detailed via the
  link's `#detailed` one-shot override (§B.15): the panel is Simple-hidden (INV-18/22), so entry MUST ride
  the override — which never writes the view store; and the parameter is never written back — clicking tabs
  afterwards leaves the URL alone (the tab stays ephemeral, D-INV-28). A name not among the shown directions
  (a stale or foreign link) **falls back to the nearest** — the default focus — and still opens and scrolls
  the panel; a widget with no reference panel (quick, or no directions defined, or the "no close direction
  yet" empty state) ignores the parameter entirely; an already-deposited older widget without the reader
  simply opens normally — the parameter is inert there, links degrade, never break. Narrow/touch: no new
  layout or gesture — entry reuses the click path `[default]`. *Non-goals:* no persisted tab state anywhere
  (URL or storage), no widget→catalog focus backpointer, no re-render of already-deposited widgets. *Success
  measure:* clicking a direction in the catalog opens that track's widget in Detailed with the reference
  panel in view and that direction's tab active (browser test + verified by deed on the real catalog).
  `D-INV-37` So "opens focused on that direction" is buildable across the page
  boundary without contradicting the not-in-URL rule — entry-focus on load ≠ tab persisted in the URL. On a
  recompute (D-INV-24) that drops the focused direction out of the shown list, the read **falls back to the
  nearest**; and if the recompute leaves **no direction clearing the lean bar at all**, the open reference read
  **collapses to the "no close direction yet" state** — tabs and the §D.10.3 per-facet bars are removed, the
  one-line prose read is retained, and it re-stamps — so an open panel never strands on a vanished direction
  and never shows empty tabs. `tags: ephemeral-view-state · url-entry-focus · no-strand · recompute-empties · D-INV-24 · D-INV-28 · D-INV-37`
- **The aim glyph rides the list.** A direction you've *aimed at* (D-INV-4) is marked with the aim glyph
  wherever it appears. Because aspiration is many-to-many, several directions can be aimed at; when **none of
  the aimed is among the shown nearest**, the surface pins **only the single nearest of the aimed ones** as an
  extra entry — shown **even if it tints far/red**, because a declared aim is intent, not filler, and the
  nearest↔aimed gap ("aimed SCSI-9 · but far from it") is exactly the useful thing to see. The other aimed
  directions live in the producer's read, not the catalog cell. So at most one pinned aimed entry (D-29
  resolved). `tags: D-INV-4 · intent-not-filler · D-29 resolved`

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

### D.10.2 The web panel and the ★ cross-validation mark — 0.9

**Beside the focused direction, a small plaque lists what the web told us about that direction's style — but
only the parts we can tie to measurement.** When the read is focused on a direction (§D.10.1), a compact
**bulleted plaque** shows style facets pulled from the web for that direction's artist (dense unresolving
harmony, wide stereo pads…). It is the visible face of the web-descriptor layer — **web suggests, measurement
decides** (D-INV-2). `D-INV-29`

**It is a READABLE, RICH panel — the side page's depth, folded into the widget (Alexander 2026-06-29/30 — "I
don't see the internet info anywhere" + "I hoped for more info").** The first cut showed only the 4 confirmed
★ lines; Alexander wants the fuller picture the side `reference_notes.html` already has (Image: artist blurb +
a full trait list, each badged). This brings that in: a **nested disclosure** ("What the web says about
⟨artist⟩") **inside the one reference panel (`#refPanel`, D-INV-36), sitting right after the centroid-read
disclosure** (§D.10.3 order), **open by default** *(supersedes the earlier "standalone panel, collapsed by
default" — Alexander 2026-07-05 merged the two reference panels into one, nested-open like the Evidence
sub-panels)*. Per artist of the focused direction it shows:
- **a one-line genre / era** + **a short prose blurb** of what the web says the artist's sound IS (e.g. "DeepChord —
  dub/ambient techno, Detroit; the second-wave Basic Channel sound, ambient-led, kick added last");
- **the FULL trait list, not only the confirmed ones** — each trait = a short readable phrase + the measured
  axis it ties to (or "—" if unmeasurable) + a **status badge**.

**Sorted by status, strongest evidence first (Alexander 2026-06-30 — "отсортировать по тому что показываем и по
тому что нашли и подтверждается").** The order is: (1) **★ measurement confirms** — the web trait our centroid
bears out; (2) **☆ soundly tied** — confirmed indirectly; (3) **"web says · our tracks don't show it"** — a web
trait our measurement does NOT bear out, or that our axes can't measure (the teaching contrast: web suggested,
measurement didn't find it). This **RESOLVES ⟨D-30⟩ in favour of show-labeled, not silent-drop** (Alexander
2026-06-30): the unconfirmed traits are SHOWN, clearly badged as web-only, never silently dropped — that
contrast is the value. It stays observation, never a grade about *your* track (D-INV-1): "our tracks don't show
it" describes the REFERENCE centroid vs the web claim, not your music. Within a tier the order is a stable key
(axis, then phrase) so it never flickers. `tags: rich-panel · sorted-by-status · ⟨D-30⟩-resolved · D-INV-29`

**One source feeds the panel AND the side page — never two truths.** The rich content (per direction: artist,
genre/era, blurb, and traits[{phrase, axis-or-null, tier: direct|indirect|none}]) lives in **one curated data
file** (`data/reference_web_notes.json`, superseding the phrase-only `facet_confirmation.json`): the widget
panel, the side `reference_notes.html`, AND the ★/☆ computation all read it, so they can never disagree. ★/☆ is
still a pure function of (this file's tier+axis, the direction's centroid, the epoch): direct+confirmed → ★,
indirect+agrees → ☆, none / contradicted / axis-not-measured → the "web says · our tracks don't show it" tier
(missing ≠ contradicted — both land in the honest bottom tier, neither auto-★, RC-INV-1). `tags: one-source ·
D-INV-2 · RC-INV-1`

**Header styled like its sibling drawers (Alexander 2026-06-30).** The panel's `<summary>` uses the **same
visual style as the other collapsibles** (the Evidence drawer, the catalog) — same weight, same disclosure
arrow — not a fainter, smaller heading; it reads as a peer drawer, not an afterthought. `tags: consistent-summary`

**The web notes FOLLOW the shared selector, for every shown direction (Alexander 2026-07-05 — the merge's
payoff; folds in the s47 "web-descriptor for all 3 nearest" feature).** The build embeds the web content
**per shown direction** (all ≤3 that qualify, from the one-source file), and switching a `#refPanel` tab swaps
the web disclosure's body AND its `<summary>` artist name to the focused direction — client-side, no re-run,
ephemeral like the tab itself (D-INV-28). The pre-merge widget rendered web notes only for the top match and
never re-targeted them (bars said DeepChord, web said SCSI-9 — Alexander's screenshot); that state is now
impossible by construction: one selector, both disclosures. A focused direction **with no web content hides
the web disclosure entirely while it is focused** (the §D.10.2 liveness rule composed across the selector —
absent, never a blank box implying "no style"); switching back to a direction with content brings it back.
`D-INV-36`

**One disclosure per direction**, with an **artist sub-header per artist inside it** for a multi-artist
direction (one collapse, artist sections within — never one box per artist, D-INV-2), never blended. The
**same ★/☆ appears both inline on the centroid bar and here** — one fact from two angles, kept on purpose: the
**bar's glyph** marks the facet you measurably share/diverge on, the **panel's glyph** marks the web *phrase*
measurement confirmed. `tags: web-panel · collapsible · read-order · one-disclosure-per-direction · D-INV-29`

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
- **"web says · our tracks don't show it" — the web claimed it but our measurement doesn't bear it out, or our
  axes can't measure it.** SHOWN, in the panel's bottom tier, plainly badged (⟨D-30⟩ resolved 2026-06-30:
  show-labeled, not silent-drop — the contrast "web suggested, measurement didn't find it" is the teaching
  value). It describes the reference centroid vs the web claim, never grades your track (D-INV-1). Contradicted
  and not-measurable both land here, distinct from a confirmed ★/☆ (missing ≠ contradicted, RC-INV-1).
  `tags: D-INV-2 · ⟨D-30⟩-resolved`

**The marks are compact — two glyphs and one footnote, never long per-row labels.** Each facet carries just
★ or ☆; a single footnote under the plaque explains both once (★ = web said, measurement confirms directly;
☆ = measurement doesn't show it head-on but it's unambiguously tied to what we measure). No per-row "web said ·
measured" tag strings — they read long and slow (Alexander 2026-06-29). `tags: compact-marking · D-INV-29`

**Approved readable layout (Alexander 2026-07-04 — variant A on real-data mockup, both amendments
accepted).** The panel body reads in this order: (1) **prose blurb first** — sets context before any
measurement verdicts; (2) **note box** (if present) — the coverage-confidence callout, left-bordered;
(3) **"YOUR MEASUREMENT BACKS THESE UP" section** — the ★/☆ confirmed traits, each as a glyph-led row
(★ or ☆ in a column, phrase beside it); no pill on each row — the glyph IS the mark; (4) **one muted
compact group line for web-only traits** — heading "Web describes these — your tracks don't bear them out"
followed by the web-only trait phrases as a `·`-separated inline run (not one pill per row — the old
repeated grey pills are the spec violation D-INV-29 forbids); (5) **sources links** — the list of source
`<a href>` links stays VISIBLE at the panel bottom (Alexander 2026-07-04 amendment: the v2 mockup had
dropped this; his call: keep it); (6) **one footnote legend** — a single line explaining ★/☆/· once:
"★ web-described, your measurement confirms it directly · ☆ indirectly but soundly tied · unmarked ·
= web-described, your measurement doesn't bear it out". This layout resolves the D-INV-29 contradiction
(shipped code emitted a long pill on EVERY row — exactly the long-per-row labels the spec forbids). All
content is preserved; only the layout changes. `tags: approved-layout-2026-07-04 · compact-marking · D-INV-29`

**Readability pass (Alexander 2026-07-05 — D-INV-29-typo).** Three fixes, in-panel scope only: (a) **brightness
hierarchy** — a section heading is NEVER dimmer than the body it heads; `.rn-section-label` /
`.tc-rn-sources-label` are `--ink` (were `--muted` sitting under `--ink` body — a brightness inversion the eye
reads as "the letters are louder than their own heading"); (b) **type scale** — the panel's fonts snap to the
widget's whole-number scale (section labels + footnote 11px, blurb/traits 13px, genre/realname/web-only/sources
12px), retiring the scattered 10 / 10.5 / 11.5 / 12.5 "fractional" sizes the font audit flagged — no widget-wide
type-token rollout (out of scope); (c) **source links** — each source reads as a link: an underline plus a
leading **chain-link icon** (the conventional link glyph, an inline SVG `svg.tc-rn-link-ico` coloured via
`currentColor`), so the sources block is unmistakably a list of clickable links, not muted prose. *(Refined
2026-07-05: the first cut used a ↗ arrow; Alexander read it as the wrong, ugly glyph and asked for the
conventional chain-link link icon.)*
`tags: readability-2026-07-05 · brightness-hierarchy · type-scale · D-INV-29-typo`

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

**No panel is a valid, silent state.** A web fetch that fails, times out, or finds **nothing at all** (no
blurb, no traits) leaves the panel **simply absent** for that direction — never a blank box implying "this
artist has no style", never a guess. (Superseded the earlier "absent if only un-tie-able claims": since
⟨D-30⟩ resolved to show-labeled, un-tie-able / unconfirmed claims now DO show, in the bottom "web says · our
tracks don't show it" tier — so the panel is absent ONLY when there is no web content whatsoever.) The states
stay honestly distinct: *no panel* (nothing fetched) ≠ *panel with only the bottom tier* (web described it,
measurement didn't bear it out) ≠ *panel with ☆* (tied indirectly) ≠ *panel with ★* (directly confirmed).
`tags: D-INV-2 · liveness · ⟨D-30⟩-resolved`

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
lives: the **producer's read** (when you click your track) and the **Detailed** per-track widget, **last inside
the reference panel (after the centroid disclosure, §D.10.3), open by default** — nested-open like the Evidence
sub-panels (the 2026-07-05 merge), and collapsible when you don't want the web's view; it never displaces the
measured read above it. **Simple** keeps the prose read without the facet plaque (Simple hides the whole
`#refPanel`); **quick** shows nothing (no fingerprint, no reference, D-INV-20). The **catalog cell never carries
the plaque** — too dense for a glance; the cell stays name + cue, and the plaque opens with the read. It is
governed by the **one show/hide-references switch** (D-INV-23) like every reference surface. `tags: view-ladder ·
collapsible · D-INV-23 · D-INV-20 · D-INV-36`

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

**Where it sits in the read — the fixed order (Alexander 2026-06-29; merged into one panel 2026-07-05).** The
Detailed read runs top-to-bottom in this order, so the eye moves from your own track outward to the reference
and only then to the web: **(1) the producer's read** (the worded observation, §B.12) → **(2) tonal balance**
(the spectrum) → **(3) the reference panel** (`#refPanel`, D-INV-36) — ONE container holding the shared
direction selector, then **the centroid read** (this section's per-facet bars, first nested disclosure) →
**the web notes** (§D.10.2, second nested disclosure, what the web says about the direction's artist). The
outward order is unchanged by the merge: the centroid read still comes **after** tonal balance and **before**
the web plaque, which stays the last and most external layer — the merge changed the packaging (two top-level
panels → one panel, two nested-open disclosures), never the reading order. `tags: read-order · D-INV-30 ·
D-INV-29 · D-INV-36`

**What it shows (Detailed, against the focused direction).**
- **Per-facet comparison — your value vs the centroid, axis by axis.** For each producer facet (a fingerprint
  axis), a small signed bar places the direction's centroid at zero and **your track as an offset** (more /
  less), z-normalised so axes are comparable. You read where you overlap and where you part — "denser, but
  darker and narrower than DeepChord" — dimension by dimension, never collapsed into one number. `D-INV-30`
- **Ordered most-similar first — the "ёлочка".** The facets where you already match the direction (small,
  centred, green bars) lead at the top, and divergence grows downward, so the list reads as a tapering tree:
  what overlaps first, where you part last. `tags: most-similar-first`
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

**No visible collapsible ever opens onto NOTHING — completeness is composed across the render-config axis, not
just within `full` (A0, Fable audit 2026-07-03).** A container whose sub-panels all self-hide for lack of data
(e.g. the evidence drawer on a quick run, which structurally has no stems / no .als) must hide ITSELF, never
render as an open panel with only its summary inside. The rule holds at every rung a widget can render —
quick, full-Simple, full-Detailed — because a gate that only ever builds `full` fixtures is blind to the other
configs (exactly how the empty quick-mode evidence drawer shipped). `INV-47`

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
comparison, shown as "not measured"). E-1 (resolved) **RESOLVED — flag-and-re-run, manual; auto-trigger rejected**
(a Demucs/transcription re-run is expensive and surprising — the user pulls the trigger). `RC-INV-10`

### E.5 Decisions (settled 2026-06-25, Alexander)

- **E-1 — SETTLED:** a partial run is a technical error → flag "incomplete run — re-run", manual re-run,
  no auto-trigger, no imputation (RC-INV-10). Missing-by-mode (quick has no stems) is not an error.
- **E-2 — SETTLED:** `MIN_SHARED_AXES` = **10**. Below 10 shared measured axes a pair is not comparable
  (RC-INV-5a) — guards against too little DATA (quick vs full), not against dissimilar music.

## G. Where things live on disk — output locations, the library, and cleanup (1.0)

Every analysis writes files: separated stems, web-preview audio, result JSONs, the built widget. Until now those
landed **inside the user's Ableton project folder** (a `track-coach-output/` dir next to the audio). Alexander
flagged that as both ugly and unsafe for 1.0: it clutters the project folder, and a user tidying their Ableton
project can delete the analysis by accident. This section moves all output to a personal home under `$HOME`,
keyed per project, and adds a safe way to clean up — without ever touching the user's own files. It is the one
place that says where things live, so the analyzer, the library, and the catalog all agree. `tags: RC-INV-9 · D-INV-14`

### G.0 The pieces, named once

- **Output root** — the single top directory under which *all* track-coach output lives. Default
  `~/.track-coach/`. Everything below is inside it.
- **Project / track** — one piece of music the user is working on, across all its rendered versions over time.
  Its identity is a single **slug** (see G-INV-2), and that slug is the unit that owns a history of runs. There
  is one slug per track — no separate "project id" and "track slug"; they are the same thing.
- **Runs base** — `~/.track-coach/projects/`. Holds the shared `index.json` (the run history, keyed by slug)
  and one subdir per slug. (Code calls this the run dir's *base*; `--base` overrides it.)
- **Run dir** — one analysis run, at `<runs base>/<slug>/<version>__<stamp>/`. Holds the run's stems,
  `stems_web/`, `mix_web/`, `result_*.json`, `run_meta.json`, and the built `analysis_widget_*.html`. This is
  **scratch**: large, regenerable, safe to prune.
- **The library** — the durable deposit at `~/.track-coach/library/`: the catalogued widgets (HTML copied at
  deposit time) plus its own `index.json`/the catalog page. This is the **keep** half — it survives cleanup.
- **`src_run_dir`** — the absolute path to the run a library member was built from, stored in the library
  index at deposit, and read back to open the original widget, play its preview audio, and compute similarity.
- **Deposit** — copying a finished run's widget HTML into the library. It happens **automatically** at the end
  of every successful `build`, unless `--no-deposit` is passed; it is not a separate manual step. `G-INV-17`

**Reference runs are never deposited into the library.** A run whose `run_meta.json` carries the reference
marker (§D.3, an explicit `reference` flag) is kept out of the library index (`~/.track-coach/library/index.json`)
entirely: auto-deposit at the end of a `build` is skipped for it, exactly as if `--no-deposit` had been passed,
and an explicit `deposit` of a reference run is refused rather than silently written. This is the enforcement,
at the deposit boundary, of the rule that other people's music never enters your catalog or signatures
(D-INV-3, D-INV-7) — without this guard the reference albums you analyse to build directions leak in beside
your own tracks. `G-INV-18`

⟨DECIDE G-3⟩ Where do reference runs go *instead* — a separate reference catalog with its own index, or simply
nowhere (kept out of the library, their fingerprints living only as precomputed direction centroids)? This pass
takes the second: references stay out of the library; the separate reference-catalog surface (its own tab, §D)
is a later pass. Revisit when that tab is built.

**A reference run's dir is protected from cleanup even though it is not a library member.** Because a reference
is never deposited (G-INV-18), it never joins gc's set of library-referenced run dirs — so a naive gc would see
it as an orphan and prune it. That would delete the raw per-stem fingerprints that `gen_reference_directions.py`
reads to rebuild the direction centroids, so the next time you re-run the albums the cloud silently shrinks or
collapses. Therefore the reference marker makes a run dir **gc-exempt**, exactly as being library-referenced
does: gc keeps it, never lists it as orphan. Your references are as safe as your library. `G-INV-19`

**The migrate banner counts library members only.** A reference run is never a member (G-INV-18), so it is
never counted — the "N tracks have analysis data in project folders" number always means *your* tracks whose
data lives outside `$HOME`, never someone else's reference album. `G-INV-16b`

### G.4 One-off cleanup of pre-marker references

**References analysed before the marker existed must be removed from the library by a one-off migration.** The
guard (G-INV-18) is going-forward only: reference albums deposited before the `reference` flag existed carry no
marker in their `run_meta.json`, so nothing distinguishes them by flag. The one-off cleanup identifies them by
their **source-album run-dir path** (an explicit set of the known reference albums, e.g. the DeepChord / SCSI-9 /
Venetian Snares folders under `Downloads/`) — not by the marker — and drops exactly those entries from
`library/index.json`. It is **backup-first** (the index is copied aside before any write) and all-or-clean-report
like every destructive command (G-INV-8/G-INV-11): it reports what it would remove, and removes nothing until
applied. The reference run dirs themselves stay on disk (G-INV-19 keeps them for centroid regen); only the
library *entries* are removed. `G-INV-20`

### G.1 Output never lands in the user's project folder

**By default, track-coach writes nothing into the Ableton project folder — all output goes under `$HOME`.**
The default runs base is `~/.track-coach/projects/`, and a track's runs live at
`~/.track-coach/projects/<slug>/<version>__<stamp>/`. The folder beside the user's `.als`/audio stays clean, and
the analysis can't be lost to a folder tidy-up. The existing `--base` flag still overrides the base for advanced
use and tests, but the *default* is the safe one (this is the behaviour change — the old default put output in a
`track-coach-output/` dir beside the audio). `G-INV-1`

**One track = one slug, so a track's versions keep one continuous history.** Identity is the slug
`slugify(audio file name)` (run_dir.py): it drops a **bracketed** version tag like `[v2]`/`(v0.6.2)` and
sanitises the rest to word chars, **case preserved**. So `Mix [v2].wav` and `Mix [v3].wav` both reduce to slug
`Mix` and share one history; the version label lives in the run-dir's `<version>__<stamp>` name, not the slug.
(This is the *real, shipped* rule — identity is the audio name, not the `.als` stem. Known limit: a **bare**
suffix like `Mix_v3.wav` is *not* stripped, so it forms its own slug unless the user groups versions with a
bracketed tag or `--track-version`.) Every version that shares a slug resolves to the same
`~/.track-coach/projects/<slug>/`, and the shared `projects/index.json` accrues the run history across those
versions (which the version-history / sibling-narrative features rely on). `G-INV-2`

**Collision: two genuinely different tracks that slug to the same name get disambiguated, never co-mingled.**
Because the runs base is now shared across every project (it used to be per-Ableton-folder), two unrelated
tracks that reduce to the same slug (e.g. both named `Untitled.wav`) would otherwise land in one slug dir with
one mixed history. On a new run whose slug already exists, the tool compares the incoming source identity
against the one stored for that slug; if they differ it uses `<slug>-2` (then `-3`, …) and warns the user,
rather than mixing two tracks' histories. The source identity is stored in `run_meta.json`/the index for this
check. `G-INV-2b`

**Source identity is als-AGNOSTIC — it is the audio's full path, never the `.als` path.** Adding an `.als` to a
previously audio-only track (same audio) must group as a **new version under the same track**, not fork a
second one. Keying identity on the `.als` path broke exactly this (the s47 `-2` catalog-fork bug): a track first
analysed audio-only, then re-analysed with `--als`, forked into `<slug>-2` because the two identities differed.
Identity is therefore the audio full path on both sides of the compare; an old run whose stored `source_identity`
was an als path still matches by its stored `audio_path`. (Audio *path*, not audio *bytes/sha*: successive
versions of one track differ in bytes by design, so a content hash would wrongly fork every new version.)
`G-INV-2c`

**The path shape `base / slug / version__stamp` is preserved; only the base moves.** Code that walks up from a
run dir to its base or `index.json` (`parent.parent`) keeps working unchanged — only the *base* moves from the
audio's folder to `$HOME`. The `index.json` sits at the runs base (shared across slugs), exactly as it sat at
the old per-folder base. `G-INV-3`

### G.2 What moves and what stays put

**Existing pre-1.0 runs are never moved or deleted automatically — relocation is going-forward only.** Runs
already on disk inside Ableton folders stay where they are unless the user runs `migrate` (G-INV-16); the
library index keeps pointing at them by their stored `src_run_dir`, so their catalog links and preview players
keep working. Only *new* analyses land under `$HOME` by default. `G-INV-4`

**An optional `migrate` command consolidates pre-1.0 runs under `$HOME`.** `migrate` physically moves run dirs
that live outside the output root (in old Ableton folders) into `~/.track-coach/projects/<slug>/` and rewrites
the matching library `src_run_dir` pointers, so everything ends up in one clean place. Like all destructive
commands it is **dry-run by default** (G-INV-8): a bare `migrate` reports exactly what it *would* move and
rewrite; it moves nothing until `--apply`. It is all-or-clean-report (G-INV-11): a member's HTML copy, its
`src_run_dir`, and the moved files stay consistent, or nothing is changed. `G-INV-16`

**A stored `src_run_dir` is honoured wherever it points.** Every reader of `src_run_dir` (the catalog open-link,
the preview player, the similarity fingerprint) treats it as an absolute path that may live under the old
Ableton folder *or* the new `$HOME` base — it never assumes a base or reconstructs the path. So old and new runs
coexist in one catalog without special-casing. `G-INV-6`

**When a `src_run_dir` is gone, the catalog falls back to the library's own HTML copy.** The deposited HTML copy
inside `library/` exists precisely so the open-link never dies: if `src_run_dir` is unreachable (pruned, or its
old Ableton folder deleted by the user), the catalog opens the library copy instead of a broken link, and the
preview player and similarity show *"analysis data not available — re-analyse to restore"* rather than failing
silently. `G-INV-14`

**The library stays at `~/.track-coach/library/`.** The durable deposit home does not move (it was already under
`$HOME`); only the transient run dirs relocate. `G-INV-5`

### G.3 Reset & gc — cleaning up safely

The project accumulates scratch over time (old run dirs, separated stems, `data/*_progress.md` working notes,
superseded versions). A `gc` / `reset` command prunes it — but cleanup near a user's music files demands hard
safety rails.

**Cleanup never touches the user's own files.** A reset/gc operates **only** under the *configured output root*
(`~/.track-coach/` by default, or whatever `--base` resolves to) — never under an Ableton project folder, source
audio, or `.als` that lies outside it. The safe boundary follows the configured root rather than a hardcoded
path, so the rule stays enforceable when `--base` is used: gc refuses to delete anything not under the root it
was given. (The user's only remaining responsibility is not pointing `--base` at their own music folder and then
running gc there.) `G-INV-7`

**Destructive cleanup is dry-run by default.** Any command that would delete shows exactly what it *would*
remove (paths, counts, reclaimed size) and removes nothing until the user confirms with an explicit flag
(e.g. `--apply`/`--force`). A bare invocation is always safe to run. `G-INV-8`

**The library is durable; run dirs are scratch.** gc prunes run dirs, stems, web-preview audio, and superseded
intermediate output; it **never** removes a deposited library member (a catalogued widget + its index entry)
without an explicit, separate force. The default `gc` can leave the library wholly intact. `G-INV-9`

**gc keeps referenced runs by default, and names all three losses before pruning one.** A library member's
preview audio, its original widget, *and* its similarity data (`result_*.json`) all live in its `src_run_dir`.
So gc, by default, **keeps** run dirs still referenced by a library member. When the user explicitly overrides
that, the warning names every casualty — not just "preview/audio": for each affected catalog row, *preview audio
goes silent · the open-link falls back to the library's HTML copy (G-INV-14) · the track becomes "can't compare"
in the cloud/siblings (§D/§F) until re-analysed.* Understating it to "you just lose the audio" would be a silent
loss of comparability. `G-INV-10`

**gc also protects the best *undeposited* run.** The most-complete run for a track (the one §E.4/RC-INV-9 reads
from) may never have been deposited — e.g. a scratch re-run done to get transcription on more stems. G-INV-10's
keep-guard only covers *referenced* runs, so this one is invisible to it. gc therefore preserves, for each
slug, the run RC-INV-9 would select; if the user forces it anyway, the dry-run names it: *"the current best run
for ⟨track⟩ — pruning downgrades coaching to ⟨N⟩ fewer axes."* `G-INV-15`

**Cleanup is all-or-clean-report, including the index.** A reset/gc either completes and reports precisely what
it removed and how much space it reclaimed, or it aborts having removed nothing — it never leaves a half-deleted
run dir that would read as a partial/incomplete run (§E). Because the shared `index.json` can drift from disk for
any reason (a crash mid-prune, a folder the user deleted by hand), RC-INV-9 does **not** trust index membership
alone: it checks the selected run dir actually exists on disk before reading it, and skips index entries whose
run dir is gone. `G-INV-11`

### G.4 How it composes

**With the `src_run_dir` readers (§D.10 / §F similarity, the catalog open-link, the preview player).** Because
old runs aren't moved (G-INV-4) and paths are honoured as-stored (G-INV-6), relocating the default root changes
nothing for already-deposited members; only freshly analysed tracks resolve under `$HOME`. A gc that prunes a
referenced run is the one interaction that can break a reader — handled by G-INV-10's keep-by-default + warning.

**With the per-track history in `index.json`.** Because identity is stable (G-INV-2), all of a track's versions
share one history — *except* a track analysed both before and after the move, whose history splits across the
old per-folder `index.json` and the new shared one. On the first post-move run for such a track, the tool
**seeds** the new `~/.track-coach/projects/index.json` from the old one so the history stays one continuous file
(rather than presenting the split as a gap or a reset). The old index is found at the named pre-1.0 path —
`<audio_parent>/track-coach-output/index.json` (the exact location the old default wrote to) — reachable from
the run's audio/`.als` path; if it isn't there, the tool discloses the split instead of guessing. Seeding also
keeps the §D.3/D-INV-14 content-hash honest: the hash is computed over the merged index, so pre-move run IDs are
included and a placement recomputes correctly when those runs change. `G-INV-12`

**With §E run completeness.** Relocation and gc never change a measurement's *measured / missing* state: a
pruned run is simply absent (not a "missing measurement" to flag), and a relocated run carries the same manifest
it always had. Cleanup operates on whole runs, never on individual measurements, so §E's per-axis honesty is
untouched. `G-INV-13`

### G.5 Decisions made (Alexander, 2026-06-30)

These were the open ⟨DECIDE⟩ points; all are now settled and folded into the invariants above.

- **G-1 — identity.** Identity = `slugify(audio file name)` with version tags stripped (the real, shipped rule),
  **not** the `.als` stem. Version-stripping already groups a track's versions into one history without needing
  the `.als`. Same-slug collision between two genuinely different tracks is handled by source-identity
  disambiguation (`-2`/`-3` + warn), G-INV-2/G-INV-2b — not left as a "rare" risk.
- **G-2 — pre-1.0 runs.** Build the optional `migrate` (G-INV-16), and run it on Alexander's three existing
  library tracks so everything consolidates under `$HOME`. Relocation stays going-forward-only by default;
  `migrate` is the explicit, dry-run-first way to bring the old ones over.
- **G-3 — pruning a referenced run.** Keep-by-default and warn (G-INV-10); the warning names all three losses
  (preview, open-link fallback, comparability).
- **G-4 — split history.** Seed the new shared index from the old per-folder one on the first post-move run, from
  the named pre-1.0 path `<audio_parent>/track-coach-output/index.json`; disclose the split only if it isn't
  found (G-INV-12).

## H. Commands, library management & cleanup (1.0)

The command surface a user actually types, plus the safe-cleanup commands. All destructive verbs obey §G's
rails (dry-run by default G-INV-8; only under the configured output root G-INV-7; keep referenced + best
undeposited runs G-INV-10/15; all-or-clean-report G-INV-11). Written human-first; `tags` are prover/matrix
handles. `tags: §G`

### H.0 The command surface, named once

What exists today (real, shipped): `analyze` (measure → result JSON + stems), `build` (rebuild a run's widget +
auto-deposit), `migrate` (consolidate pre-1.0 runs under $HOME, §G G-INV-16), and on the library: `list`,
`deposit`, `catalog`, `clean`. The 1.0 additions below fill the gaps Alexander named: real remove, scratch
`gc`, explicit version pruning, an Ableton-tail sweep, a `backup`/`restore` safety net, and the two-rung
`reset` / `hard reset` wipe.

**The data tiers, named once.** Everything under the output root falls in one of four tiers, and the cleanup
verbs are defined against them: the **keep** tier (`library/` — catalogued deposits, §G G-INV-5); the
**scratch** tier (`projects/` — run dirs, stems, previews, indexes; regenerable by re-analysis, §G G.0);
the **references** tier (`explore/` — the reference corpus the user accumulates for §D); and the **backups**
tier (`backups/<stamp>/` — snapshots made by `backup`). A few **loose** files may also sit at the root (a
resume script, config). "Curated" work = keep + references; "scratch" = the regenerable tier. The cleanup
ladder (H-INV-11) is defined entirely in terms of these tiers.

### H.1 Listing & removing — managing what's in the library

**`list` shows every track and its versions.** One line per track with its versions/stamps, so the user can see
what the library holds before removing anything. (Exists; `library list`.) `H-INV-1`

**`remove` prunes a chosen track or a single version — never silently.** Removing names exactly what goes
(which catalog rows, which widget copies, whether the backing run dir is also deleted) and asks/`--apply`
before doing it. Removing one version of a track leaves the others and the track's history intact; removing a
whole track takes all its versions. The library index and catalog are rewritten in one step (no half state,
G-INV-11). Auto-deposit stays the default ingest (H-INV-7) — `remove` is the counterpart for taking things
out. `H-INV-2`

### H.2 Cleanup — gc, version pruning, Ableton-sweep, backup/restore, reset & hard reset

**`gc` prunes scratch, never the keep-half.** It removes orphaned/old run dirs, separated stems, and superseded
intermediate output under the output root — keeping every deposited member's referenced run and the
most-complete undeposited run per track (§G G-INV-9/10/15). Dry-run by default; `--apply` to act. `H-INV-3`

**Old versions are kept by default; pruning them is a separate, explicit, dry-run-first verb.** Per Alexander
(s31): the library keeps ALL versions and ALL run results as a feature (any version opens from the per-track
plaque). gc must NOT drop versions automatically. A distinct `prune-versions` (e.g. "keep newest N per track")
exists only as an explicit command, shows what it would drop, and never runs as part of routine gc. `H-INV-4`

**An Ableton-tail sweep removes only truly-orphaned leftovers, and only after showing them.** After `migrate`,
old `track-coach-output/` folders in Ableton projects can hold a dangling `latest` symlink and a stale
`index.json` — but they may ALSO still hold real undeposited/older run data (verified by deed s31: those
folders held whole extra runs, not just empty tails). The sweep therefore distinguishes *empty / dangling-only*
tails (safe to delete) from *folders that still contain real runs* (listed, never auto-deleted), and shows
everything in dry-run before any removal. It operates outside the output root by design, so it requires an
explicit target/confirm and never touches non-track-coach files (the user's audio/`.als`). `H-INV-5`

**`backup` snapshots the curated work — additive, never destructive.** A `backup` copies the **keep** and
**references** tiers (`library/` + `explore/`) plus any config into a timestamped `backups/<stamp>/` snapshot,
and never deletes or moves anything — running it again only adds another snapshot. Like an Ableton project
backup it captures the *curated* work, not the regenerable renders: the `projects/` scratch (stems, previews,
run JSONs) is excluded by default because re-analysis rebuilds it; `--full` adds the scratch tier for a
complete disk image. `backup --list` shows existing snapshots with their dates and sizes. A backup is
**all-or-clean-report** (like G-INV-11): it either completes and marks the snapshot good, or it discards the
partial — a half-copied snapshot is never left for `restore`/`reset` to trust. Stamps are unique to the second;
a `backup` never writes into an existing snapshot dir — on a same-stamp collision it suffixes (`<stamp>-2`).
Snapshots live under the output root but are neither orphaned run dirs nor superseded output, so no cleanup
verb descends into `backups/` — `gc` scans only `projects/`, and only `hard reset` removes snapshots (so a
`--full` snapshot's embedded run-dir copies are never seen by `gc` as prunable orphans). `H-INV-8`

**`restore` is backup's inverse, and never clobbers silently.** `restore <stamp|latest>` brings a chosen
snapshot's `library/` + `explore/` back into place. It is dry-run by default (G-INV-8): a bare `restore`
reports exactly what it would overwrite or add, and writes nothing until `--apply`. When restoring would
overwrite existing keep/reference data it says so and — unless `--force` — first takes a safety `backup` of the
current state, so a restore is itself undoable. Round-trip holds: restoring a snapshot reproduces exactly the
tiers `backup` captured (H-INV-8). Because a non-`--full` snapshot omits the scratch tier, a restore names the
same loss G-INV-10 does: the restored library members' `src_run_dir` point into a `projects/` that wasn't
captured, so previews go silent, opens fall back to the library HTML copy (G-INV-14), and comparability (§D/§F)
is dead until re-analysis — a `--full` snapshot restores those too. A restored index is honoured as-stored
(G-INV-6): if the disk layout moved since the snapshot (e.g. a `migrate` ran after it), the pointers may need a
re-`migrate` or re-analysis, with the G-INV-14 fallback keeping opens alive meanwhile. `H-INV-9`

**`reset` wipes the working state but keeps the safety net.** A `reset` clears the **keep**, **scratch**, and
**references** tiers (`library/` + `projects/` + `explore/`) and the known loose track-coach files at the root
(the resume script, config) — everything the user actively works with — but **keeps `backups/`**, and
**auto-creates a safety backup first** (unless `--no-backup`). It removes nothing until that safety backup has
completed successfully (H-INV-8): a failed or partial backup aborts the wipe, so `reset` can never destroy the
curated work without a good snapshot behind it. What the safety backup recovers is the **curated** work
(keep + references) via `restore`; the scratch tier is not snapshotted and rebuilds by re-analysis — so
"recoverable" means the library and references come back, not that stems/previews are restored (they re-render).
`reset` demands an explicit confirm (`--yes-wipe-everything`, not merely `--apply`), states plainly that source
`.als`/audio are untouched and the analyses rebuild by re-running, and reports exactly what it removed and
reclaimed. It stays all-or-clean-report (G-INV-11). When `--no-backup` is combined with no existing snapshot
covering the curated tiers, `reset` warns that the curated work will be unrecoverable and requires the extra
acknowledgement (as `hard reset` does), since that combination is as irreversible as a `hard reset` for the
curated data. It is the dogfood path Alexander uses to verify cleanup end-to-end before re-accumulating
versions. `H-INV-6`

**`hard reset` is the only irreversible verb — it removes everything, backups included.** Where `reset` keeps
the safety net, `hard reset` clears the *entire* output root — keep, scratch, references, **and** `backups/` —
leaving a bare `~/.track-coach/`. It makes no safety backup (there would be nowhere recoverable to put it) and
so demands the strongest confirm: both `--yes-wipe-everything` and an explicit `--including-backups`
(equivalently `reset --hard`), and it names that the backups themselves will be destroyed before acting. Like
every rung it is dry-run by default: a bare `hard reset` (no flags) lists everything it would remove, backups
included, before either confirm flag is given. After a `hard reset`, nothing on disk recovers the prior state
except re-analysing the source audio/`.als`. This
settles the earlier open 'truly-full flag' question: the truly-full wipe is `hard reset`. `H-INV-10`

**The cleanup verbs form one reversibility ladder; only the last rung is irreversible.** Read from safe to
final: `backup` (additive) → `gc` / `prune-versions` / `remove` (prune scratch or a named member; the keep
tier and best runs survive, §G G-INV-9/10/15) → `reset` (wipe the working state, but a fresh safety backup +
`backups/` remain, so `restore` recovers it) → `hard reset` (remove everything, backups included). Every rung
above `hard reset` is recoverable — the data is either regenerable scratch or sits in a snapshot; `hard reset`
is the single point of no return, which is why it alone carries the double confirm. All rungs obey §G's rails:
dry-run by default (G-INV-8), never outside the configured output root (G-INV-7), all-or-clean-report
(G-INV-11). `H-INV-11`

**Confirmation is graduated to match how much a verb can destroy — one predictable pattern per risk tier.**
So a user never has to recall a per-command flag: additive verbs (`backup`, `deposit`, `catalog`) need no
confirm; anything that prunes a member or scratch (`gc`, `remove`, `prune-versions`, `restore`, `clean`) is
**dry-run by default and acts on `--apply`**; wiping the working state (`reset`) is dry-run by default and acts
on the louder `--yes-wipe-everything`; and the catastrophic wipe (`hard reset`) additionally requires
`--including-backups`. A bare invocation of any destructive verb is always a safe preview. Within the prune
tier, `clean` is **legacy** — `remove` (drop a track or one version) and `prune-versions` (keep newest N) are
the preferred, clearly-named verbs; `clean` still works and now takes `--apply` like the rest (its old `--yes`
remains a silent alias) so the whole tier reads one way. `H-INV-12`

**Ingest stays automatic; the user manages the exits.** A successful `build` auto-deposits (§G G-INV-17); the
user never has to remember to save. The management verbs (`backup`, `restore`, `remove`, `gc`, `prune-versions`,
`reset`, `hard reset`) are the deliberate, dry-run-guarded ways to snapshot, recover, or take things back out.
`H-INV-7`

### H.3 Open

- ⟨DECIDE H-1⟩ `prune-versions` default keep-count N (suggest: prompt, no silent default — keep-all stands until
  the user names N).
- ⟨DECIDE H-2⟩ does `remove` of a version also delete its run dir by default, or only the library entry (run dir
  left for gc)? Lean: only the library entry; gc reclaims the run dir later.
- H-3 (resolved) RESOLVED (Alexander, 2026-07-01) — the 'truly-full' wipe is a distinct `hard reset` that also
  removes `backups/` (H-INV-10); plain `reset` keeps the safety net (H-INV-6). Backups capture the curated tiers
  only (keep + references), scratch excluded unless `--full` (H-INV-8).

## I. The visual design system — tokens & components (1.0, 2026-07-02, Alexander's design session)

**Why this exists.** The widget CSS kept drifting: the same visual role lived as several raw hex
values, radii were ad-hoc (6/8/9/11/12), three near-identical segmented controls were maintained
separately, and the catalog palette had silently forked from the widget. Alexander ran a design
session on claude.ai/design (project `track-coach`, `aae67990-…`) and produced a settled decision
record — the implementable form is `docs/design/DESIGN_SESSION_2026-07-02.md` (v3). This section is
the prover-ready spec of that system; the design doc is its human narrative, and the claude.ai/design
project is its browsable component library. One role = one token = one name.

### I.0 Single token source (root of the drift)
- **Entity: the token set.** The canonical values are the WIDGET `:root` (`build_widget.py`), NOT
  the catalog. The catalog (`catalog.py PALETTE`) had drifted on two roles — `ink` #e8ecf6 (widget
  #e8ecf5) and `line` #2a3142 (widget #262c3c).
- **DS-INV-1 (one source):** every UI role has ONE value, defined once, used by both the widget and
  the catalog. Canon = the widget values. The catalog re-declares the SAME values (it is a separate
  offline HTML file, so it carries its own copy, but the copy must be byte-equal on shared roles).
- **DS-INV-2 (no fork):** a test asserts the catalog's shared roles equal the widget's (no re-drift).

### I.1 Colour
- **Neutrals** `--bg #0c0e14 · --panel #141822 · --panel2 #1b2030 · --line #262c3c · --ink #e8ecf5 ·
  --muted #8b94a8` and the **brand accent** `--wob #a78bfa` — unchanged.
- **State triple** `--good #46d39a · --warn #ffb454 · --bad #ff6b6b`.
- **`--bright #ffd166`** — KEPT as its own UI token (role = "highlight/attention"; yellow ≠ amber).
  Its UI uses are chart-attention marks (the ★ climax marker, meter-change lines, the reference
  overlay dashes) + the run-mode "quick" badge. It is NOT merged into `--warn`.
- **Text ladder (DS-INV-3):** the ~8 near-white raw hexes collapse to a 3-rung ladder by an EXPLICIT
  per-hex map (no judgment at edit time): `--ink #e8ecf5` ← #eef1f8, #cfd6e6, #cdd5e6 (brightest) ·
  `--ink-dim #aeb6c8` ← #c3cbdc, #aeb6c8, #aab3c7, #a0a8bc (mid) · `--muted #8b94a8` ← #8b93a7
  (dimmest). 8 → 3. `--ink-dim` is a NEW token — add it to the widget `:root` AND the catalog copy.
- **Reds (DS-INV-4):** UI-red → `--bad`; the magma/data reds stay in the gradient (below).
- **Colour drift → tokens (DS-INV-5):** `#6fdfb8 → --good` · `#ffb13f` (reference star) `→ --warn`.
  (⟨DECIDE DS-4⟩ RECONCILED s43: the category backgrounds are NOT the dim `#3a4060/#2e3a52/#3a3040/#3a2832`
  this line originally assumed — those hexes do not exist in the code. The real category backgrounds are
  saturated CATEGORY-IDENTITY colours `_CAT_COLORS` = Mix `#5b6472` / Balance `#7a6cab` / Character `#c08a3e`
  (`build_widget.py:68`, applied inline). They are the same KIND of thing as the stem colours (DS-INV-7b) —
  a categorical group, LEFT as literals; deriving them from `--panel2/--line` would destroy the colour-coding.)
- **rec-card severity (DS-INV-6):** the left stripe encodes severity `good / warn / bad` (ADD the
  `bad`/red variant). `--wob` is the neutral/brand accent, never an alarm level.
- **Data-viz colours are OUTSIDE the UI palette and are LEFT UNTOUCHED — TWO sets:**
  - **DS-INV-7a (colormap):** the arc/frequency colours are a magma/viridis perceptual gradient
    (#4cc9f0 … #fcfdbf #8c2981 #3b0f70). NOT tokenised.
  - **DS-INV-7b (categorical stems):** the stem colours are fixed categories —
    `kick #ff5d73 · bass #a78bfa · drums #4cc9f0 · hats #5ad1c2 · chord #46d39a · lead #ffd166 ·
    other #8b94a8`. Documented as a plaque group, left as raw literals.
  - **DS-INV-7c (the dedup guard — critical; keyed by LOCATION, not hex value):** some stem literals
    share a hex with a UI token (bass=--wob, chord=--good, other=--muted, lead=#ffd166, kick pink-red
    near --bad) — they are byte-identical strings, so a value-based test cannot tell an allowed stem
    literal from a forbidden UI raw hex. The guard therefore keys off WHERE the hex sits: the
    whitelisted data-viz sites are the stem/family/drum colour arrays (`FAM`/`FCOL`/`DRCOL`/`COMP`),
    canvas `ctx.fillStyle/strokeStyle`, colormap steps, and the favicon `<svg>`. The guard scans ONLY
    CSS-rule / style-attribute / `:root` text and fails on a raw hex THERE that equals a token value.
    The "exact-dupe → var(--token)" pass MUST NOT rewrite the data-viz literals — doing so would
    falsely couple a data category to a UI role and could collide two stems (e.g. hats #5ad1c2 vs
    drums #4cc9f0 must stay distinct; kick #ff5d73 must not become --bad).

### I.2 Layout & grid (new tokens)
- **Container widths:** `--w-prose 640px` (text/advice) · `--w-content 1120px` (main column) ·
  `--w-full 100%` (ribbons/graphs).
- **DS-INV-8 (grid by width, not breakpoints):** the card grid is
  `grid-template-columns: repeat(auto-fill, minmax(<min>px, 1fr))` — columns emerge from
  `floor((width+gap)/(minCard+gap))`, no media queries; `<min>` is chosen from the desired column
  count at the target window. Fluid sizes use `clamp()`; a component in variable-width slots uses a
  container query, not media. **This REPLACES the s34 `#recsPanel` container-query recs grid — the
  existing `test_headless_render` recs column-count assertions are UPDATED to the new expected counts,
  not held constant (this is a deliberate layout change, not a restyle). The recs cap stays 2 columns
  (a rec card wants a readable line length; `<min>` picked so a ~1120px content column yields 2).**
- **Spacing split (DS-INV-9) — PANEL-RHYTHM SLICE BUILT s57; broad normalisation still POST-1.0.**
  The system is two roles — `--gap 8/12/16` (within a group) and `--rhythm 28/44` (between sections).
  **Built (s57, Alexander's design-system values):** the two role tokens exist (`--gap:16px`,
  `--rhythm:28px`) and drive the PANEL spacing — every top-level `.tc-panel` carries `margin-bottom:var(--rhythm)`
  (between sections), while the sub-panels nested inside `#evidence` take `margin-bottom:var(--gap)`
  (within the group). This makes the **inter-panel gap strictly larger than the intra-panel gap**, fixing
  the earlier inversion (measured 24px between top-level panels < 30px between sub-panels — the reverse of
  correct hierarchy; Alexander's 2026-07-05 review). The old per-id overrides that caused it
  (`#webPanel{margin:10px 0 0}`, `#evidence,#catalog{margin:24px 0 0}` — both zeroed the bottom margin)
  are removed. **Still POST-1.0 (deferred):** the BROADER normalisation of the ~13 remaining raw `gap:`
  literals (2–20 px) inside components to the three-value scale — that stays a design/taste pass (which of
  5/6/7 px becomes 8 px is Alexander's call), not done here. `tags: panel-rhythm-built-s57 · post-1.0-broad · design-call · F5`

### I.3 Motion (new tokens)
- `--dur-fast 120ms` (hover, highlight, small colour change) · `--dur-base 180ms` (appear, state
  change, expand) · `--ease ease-out` (no springs).
- **DS-INV-10:** components use these tokens, not the scattered `.12s/.15s` literals.

### I.4 State ladder (one, for buttons / segments / fields)
- The interactive states form ONE ladder: `rest` (muted text / thin border) → `hover` (text→`--ink`,
  or accent fills `--wob`; `--dur-fast`) → `focus` (ring `box-shadow: 0 0 0 3px` of `--wob` at ~.4α —
  via `color-mix(in srgb, var(--wob) 40%, transparent)`, NOT a raw rgba, so the guard stays honest)
  → `active` (`translateY(1px)`) → `selected` (fill `--wob`, text `var(--bg)`, bold) → `disabled`
  (`opacity:.45; cursor:not-allowed`).
- **DS-INV-11:** every interactive control (buttons, segmented control, the search field) draws from
  this same ladder — no per-component bespoke hover/selected colours.

### I.5 Radii (scale of 4)
- **DS-INV-12:** every `border-radius` is one of `--radius 10 · --radius-lg 14 · --radius-xl 18 ·
  --radius-pill 20`. The ad-hoc 6/8/9/11/12 snap in (12→14, 6/8/9/11→10 or the nearest rung). No
  `--radius-xs`; the 4px bars are decoration, exempt.

### I.6 Segmented control (one, not three)
- **Entity: the segmented control.** `.viewtoggle` and `.reftabs` merge into ONE component `.seg`.
  (RECONCILED s43: the original text named THREE — `.seg`/`.viewtoggle`/`.reftabs` — but `.seg` did not
  exist in the code; there were only two controls. The shared class is now named `.seg`. Shipped 0.9.18.)
- **DS-INV-13:** container `border:1px solid --line; border-radius:--radius; overflow:hidden`;
  buttons `padding:9px 14px`; `rest` = transparent bg + text `--muted`; `hover` → `--ink`;
  transition `--dur-fast`. Both former controls render from this ONE class.
  **`selected` = CALM (Alexander 2026-07-02, REVERSED after seeing it rendered):** the old subtle
  `--panel2` lift + `--ink` text, SAME weight — NOT a `--wob` fill, NO contrast inversion, NO sudden bold.
  Rationale: the loud `--wob` fill (the earlier design-session value) clashed with the calm-by-default
  aesthetic; the invert + bold jarred. The win kept from the merge is structural (one class for both
  controls); the look stays the old calm one. Browser test asserts the calm selected look.

### I.7 Per-component contracts (all 10)
Each component draws ONLY from the tokens above (all §7 taste calls decided in the design doc v3):
1. **buttons** — `.pbtn` accent, `.pmini/.backlink/.copen` ghost, `.cplay` round (stays 50%); state
   ladder; radii → `--radius`.
2. **chips** — `.pill` → `--radius-pill`; `.chip-level` close/mid/far = good/warn/bad; `.chip-char`
   → `--radius`; `color-mix` tints kept; static (no hover).
3. **collapsible-panel `.tc-panel`** — radius 18 → `--radius-xl`, nested 12 → `--radius-lg`; ▸/▾
   marker = closed/open on `--wob`; nested background `rgba(0,0,0,.12)`. **Expansion animates via
   `grid-template-rows: 0fr → 1fr` (CSS cannot transition `height:auto`), `--dur-base` — NOT a raw
   `height` transition (that no-ops and the native jump persists).** Persistence rule: a panel
   RESTORED open on reopen renders expanded with NO first-frame zero-height (the animate-from-0 must
   only run on a user toggle, not on initial restore).
4. **panel** — `.panel/.panel2` → `--radius-lg`; backgrounds `--panel/--panel2`; kicker `--wob`.
5. **player-transport** — `.pbtn/.pmini` as buttons; `.ptime` tabular-nums `--muted`; `.seekbar`
   track `--panel2` + fill `--wob`, thumb `--wob` + ring; `.pstem` mute.on `--bad` / solo.on `--good`.
6. **rec-card** — left stripe severity (DS-INV-6); `--radius-lg`; stripe 3px. (RECONCILED s43: the red/bad
   stripe already exists — `.rec.crit → --bad`; the three code levels are `crit → --bad`, `do → --good`,
   `concept → --bright` yellow. ⟨DECIDE DS-3⟩: keep the third level `--bright` yellow, or move it to `--warn` amber?)
7. **reference-bar** — `.reftabs` → the one segmented control (`.seg`, shipped 0.9.18); `.refread-cat`
   backgrounds are the categorical `_CAT_COLORS` (⟨DECIDE DS-4⟩ — left as identity colours, NOT panel-derived);
   star #ffb13f → `--warn`, chip #6fdfb8 → `--good`, halfstar → `--muted`.
8. **search** — `#q` focus (state ladder); `.seg` → the segmented control; `.count` `--muted`.
9. **view-toggle** — `.viewtoggle` → the segmented control; `.viewhint` `--muted`.
10. **vitals** — `.vitals` → `--radius-lg`; `.vval` warn/bad/good; `.vlabel`+`.srcmeta` `--muted`,
    `.srcmeta b` → `--ink`; `::before` separators on `--line`.

### I.8 Typography — audited, weights held for Alexander
- The scale exists (`--fs-kicker 10.5 · --fs-1..6 = 12/13/14/15/20/28`) but components drift: weights
  `620`/`650` (off 400/500/600/700), heading sizes `21`/`22` (off scale), fractional `13.5/12.5/11.5`.
- **DS-INV-14 (mechanical snaps):** fractional sizes fold into `--fs-1..4`; the audit runs the same
  grep-and-count as colour.
- **⟨DECIDE DS-1⟩ (Alexander's call — the sole open taste item):** which weight goes where (snap 620/650
  → 600 or 700?) and whether h1 21/22 snaps to `--fs-5 20` or gets a dedicated heading token. Audit +
  safe snaps land now; the weight placement waits for him.

### I.9 Machine-checked invariants (all at ≥ browser-rendered level per the test method)
- No UI-CSS raw hex duplicates a token (DS-INV-7c guard, stem/colormap whitelisted).
- Catalog shared roles == widget roles (DS-INV-2).
- Every `border-radius` ∈ the 4-rung scale (DS-INV-12).
- Exactly ONE segmented-control class, used by all three former controls (DS-INV-13).
- The `--bright` UI uses render (climax ★, meter marks, ref overlay, quick badge) — unchanged pixels.
- rec-card renders a `bad`/red stripe for a bad-severity card (DS-INV-6).

### I.10 Composition across the axes
- **× view (Simple/Detailed/quick):** the tokens are view-independent, but the components they style
  are gated (e.g. `#stemlanes`/`#seqKey` Detailed-only, `#refPanel` Detailed-only — its nested
  `#refRead`/`#webPanel` hidden with it, D-INV-36 — the view-toggle hidden on quick → `.viewhint`). The refactor must not change any view-VISIBILITY rule — the existing
  view-ladder visibility browser tests pass UNCHANGED. (Distinct from the recs COLUMN-COUNT tests,
  which DO change per DS-INV-8 — visibility is held, layout counts are updated.)
- **× persistence/reopen:** the `.tc-panel` open/closed state and the remembered global view survive a
  reopen; the animated-height change (I.7 #3) must not break the persisted-open render (a panel
  restored open shows expanded, no first-frame collapse).
- **× viewport:** the grid (DS-INV-8) yields column counts by width with no media-query cliff; the
  segmented control and cards stay within `--w-content`. The §D reference panel (`#refPanel`), its nested
  read (`#refRead`), web notes (`#webPanel`) and the up-to-three tab selector (`.reftab`) also stay within the viewport when
  narrow — no horizontal overflow, no internal h-scroll, no tab-row spill (pass-3 composition s56;
  pinned browser-level, `test_headless_render::RefReadSurfacesRendered::test_ref_panels_stay_within_viewport_when_narrow`).

### I.11 Open decisions
- **⟨DECIDE DS-1⟩** — §I.8 typography weight placement (above). The only open taste call.
- **⟨DECIDE DS-2⟩** — catalog `_SIM_COL` (`#2e9e5b/#d8932a/#c2503d`) is a SEPARATE, darker
  similarity-column palette, not the `--good/--warn/--bad` tokens. The design doc did not cover it.
  Lean: LEAVE it (a deliberate muted table palette), do not force it onto the state tokens — but flag
  to Alexander whether he wants the catalog table to use the same state colours as the widget.
- **⟨DECIDE DS-3⟩** (s43) — the rec-card THIRD severity level (`.rec.concept`) is currently `--bright`
  (yellow), while the state triple is good/warn/bad. Keep it yellow (attention role, distinct from the
  amber warn) or move it to `--warn` amber? Not changed overnight — Alexander's taste call.
- **⟨DECIDE DS-4⟩** (s43, RECONCILED) — the category backgrounds (`_CAT_COLORS` Mix/Balance/Character) are
  categorical identity colours, LEFT as literals (like stems). Confirm this is right, or does Alexander want
  them re-derived from panels? Lean: LEAVE (they colour-code the categories).

## C. (RESOLVED) Increment-1 inputs that needed Alexander's domain call
All three original blocking ⟨DECIDE⟩ inputs are settled and shipped: (1) the dB floors — empty/don't-parse
`STEM_EMPTY_FLOOR_DB` = −55, colour floor `STEM_COLOUR_FLOOR_DB` = −60 (§B.2); (2) the musical definition
of **Drop** — strictly-lower predecessor, `LIFT` = 0.12, sustained-high = "Main" (§B.2, CR-5); (3) which
stems count as significant for repetition — `significant_stems()` gate (§B.3, CR-6). The method (write SPEC
→ product-prover → derive matrix/tests → fix code, bug → spec → test → code) is now the standing process,
not a one-time setup. Remaining ⟨DECIDE⟩ points are per-feature tuning thresholds, flagged inline above.

## Glossary (plain-language definitions; expand it whenever a term needed explaining)
- **red on the band strip** = high energy shown on the per-stem band strip.
- **"stale" / outdated catalog row (INV-12)** = the widget that row links to was built on an OLDER analyzer
  version than the one installed now (e.g. the row's widget is v0.6.2 but the tool is v0.9.1), so it may be
  missing newer analysis (e.g. the reference read). It is NOT about the music being old — only the analysis.
  **UI clarity fix (Alexander 2026-06-30 — "I didn't get what stale is"):** don't show the bare word "stale";
  show a plain, self-explaining marker WITH the version, e.g. **"older analysis · v0.6.2 → re-analyse"**, so
  the meaning + the fix are visible without hovering. The bare-jargon chip was the confusion. `INV-12`
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
