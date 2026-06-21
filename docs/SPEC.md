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

## C. What I need from Sasha to derive the matrix + tests
The ⟨DECIDE⟩ points above — especially: (1) the dB floor(s) for "empty / don't-parse" and "no colour";
(2) the musical definition of **Drop** (and the name for sustained-loud non-lifts); (3) which stems are
"significant" for repetition. With those, I run product-prover on this SPEC, then derive the §-grids +
tests, then fix the code (bug → spec → test → code).

## Glossary (his words ↔ internal)
"красное" = high energy shown on the per-stem band strip · "дроп" = a `Drop`-named scene · "пустой стем"
= a stem below the validity floor · "синты, не вокал" = the Demucs label ≠ the mapped identity.
