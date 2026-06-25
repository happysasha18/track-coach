# §D Reference/Compare — RESEARCH LOG (overnight exploration, started 2026-06-24 ~22:10 IDT)

> Resumable working log for the reference/compare exploration. **On wake: read this top-to-bottom, then
> continue from "NEXT / RESUME POINT".** Findings registered as we go so nothing is lost between wake-ups.
> Design home = memory [[track-coach-reference-representation]] + [[track-coach-web-descriptor-layer]].
> Prototype scripts live in /tmp (throwaway): fp_proto / map3 / popper / popviz / axisdig / sub_viz.

## The goal (Sasha's framing)
Measure everything to the max, compare his 3 tracks against the reference albums, read about the artists and
translate their described style into what we can actually measure (signals / axes / stems), register every
step, show. He's away — work autonomously, don't block on questions.

## Data on hand
- **His 3 tracks** (in the library `~/.track-coach/library/index.json`, quick-facets available):
  Wobble Drift (C#m, 143.6), Shared Memories (Em, 123), Lazy Sparks (G, 123).
- **Reference albums** (in ~/Downloads):
  - Venetian Snares — Cubist Reggae (4 mp3) — MEASURED quick-mode (no stems yet).
  - DeepChord — Auratones — ONE big FLAC + .cue → must split; being measured FULL mode.
  - SCSI-9 — The Line Of Nine — 9 FLAC (more downloading, ~30min) → being measured FULL mode.

## Findings registered so far

### F-1 — The 2-D map is the wrong surface; the read (per-facet bars) + manifold distance + angle is right.
Confirmed by deed. In ~50-D a 2-D scatter is pseudo-similarity. Representation = per-facet divergence bars
(the WHERE) + distance to the reference MANIFOLD (normalised by the manifold's own spread) + angle/cosine.
«Своё» = the orthogonal residual.

### F-2 — POPPER control PASSED (the measure discriminates), rough 15-facet quick basis.
Distance of his 3 tracks to the Cubist-Reggae surface vs VS's own internal spread (4.24 ± 0.54):
- **Wobble Drift 2.73 (z −2.78) — BELONGS, snuggest** (and it's the track he consciously aimed at VS ✓)
- **Shared Memories 3.35 (z −1.65) — belongs**
- **Lazy Sparks 5.47 (z +2.27) — OUTSIDE.** So it's not "everything belongs."

### F-3 — WHY Lazy is outside / what separates it (the axis-dig answers Sasha's lazy≈shared puzzle).
Lazy diverges from VS far more than Shared does on: **loopiness −9.2** (Lazy barely loops; VS/Shared do),
**timbre-return −7.1** (Lazy keeps evolving), **brightness-variation, energy-trend +2.9, #sections +2.1**.
Musically dead-on: Lazy genuinely develops; VS Cubist Reggae is glitchy-but-cyclic; Shared loops like them.
**Caveat:** those z's are inflated because VS spread on those axes is tiny (z explodes) — the manifold/
orthogonal-residual distance handles this better than raw per-axis z. Don't over-trust the −9 numbers.

### F-4 — Web → measurable axes (the web-descriptor layer; keep ONLY measurable+verifiable).
- **DeepChord / dub techno** (Rod Modell): minimal+repetitive → loopiness↑, low novelty; "faint white noise/
  pulsating noise" → tonal↔NOISE axis (HPSS, spectral flatness, a noise stem); "profound sense of space,
  delay/reverb, dub chords" → SPACE = stereo width + reverb-tail proxy (Sasha's "размеры"); "warm" → spectral
  tilt (low-mid↑). Hardware (MS-20/analog) → NOT measurable, dropped.
- **SCSI-9 / minimal-tech-house** (Kubikov/Miluytenko): "hypermelodic, wistful melodies" → melody-stem share +
  polyphony↑ (tonal↑); "techy beat / deep-house chords" → groove/swing + chord stabs; "kaleidoscopic dub
  effects" → space/width; "detailed" → density↑.
- **Venetian Snares / Cubist Reggae** (breakcore-IDM): chopped amen breaks → drum/percussion share↑ + onset
  density↑; "ruptured/glitchy" → INTERNAL novelty (mfcc variance / #sections), **NOT** endpoint-return
  (endpoint_cosine measures arc-returns-to-start, which VS still does ~0.99 — different thing!); odd time
  sigs → beat-irregularity (hard, partial).
- **The new candidate FACETS this yields** (mostly need FULL/stem mode): element balance (drums/melody/bass
  shares), tonal↔noise ratio, space/width + reverb-tail, onset density / groove / swing, internal novelty
  (not endpoint), spectral warmth/tilt. These are the producer-language axes Sasha wanted.

## What's running (verified 22:14)
- Junior `a295b1e9` (background): **DeepChord cue-split WORKED → 10 tracks** in `.../DeepChord …/split/`
  (01-Fog Hotel … 10-Azure). SCSI-9 track 1 (Teplyi Dym) full-analysed (stems out, Demucs on MPS ~17s/track).
  Working through the rest full mode. Junior narrates to /tmp/tc_batch_log.txt (ephemeral — ignore).
- **PERSISTENCE (Sasha's concern handled):** the real outputs land on DISK in persistent dirs, NOT my session:
  - SCSI-9: `~/Downloads/SCSI-9 - The Line Of Nine (2006)/track-coach-output/<track>/<stamp>/result_core.json`
  - DeepChord: `~/Downloads/DeepChord - Auratones …/track-coach-output/<track>/<stamp>/result_core.json`
  So even if my session ends mid-run, **recover everything by globbing those `track-coach-output/**/result_core.json`
  (skip `/latest/` symlinks — they double-count, learned that on Cubist Reggae).** No dependence on the junior's report.
- SendMessage to a running junior is NOT available here → can't redirect it; rely on disk-globbing instead.
  FUTURE juniors: instruct them to ALSO append run_dirs to a persistent file (Sasha's ask) since I can't message mid-run.

## UPDATE 2026-06-25 (post session-limit; context was bloated → wiped here)
- **SCSI-9: all 9 tracks measured full-mode** (stems on disk). ✓
- **DeepChord: 10/10 QUICK done (`deepchord_runs.txt`), but FULL failed on all 10** — cue-split FLACs have a
  broken seek table (`psf_fseek` in Demucs/soundfile). **FIX in flight:** junior `aaf9bb2f` re-encodes each via
  ffmpeg (`split/reenc/`) then full-analyses; SAME junior also re-runs the **4 Cubist Reggae** mp3s in full
  (for their stems). Appends to `~/.track-coach/explore/stemfix_runs.txt`. On resume: read that file + glob
  `split/reenc/track-coach-output` and the Cubist `track-coach-output` for the new full runs.
- **STEM-FACET PLUMBING NAILED (important):** per-stem `vitals.lufs` is **None** in 0.8.31 runs — do NOT use it.
  The real per-stem energy is in `result_masking.json → band_rms_db` (per stem × band, dB); the SAME file has
  `spectral_flatness` per stem (→ the tonal↔noise facet) + `spectral_centroid` + `sustain` + `spectrum`.
  So: element balance = sum linear(band_rms_db) per stem → drums/bass/melodic shares; tonal↔noise = flatness.
  masking.json exists for FULL runs only (SCSI ✓, his 3 ✓, DeepChord pending, Cubist quick→needs full re-run).
- **Element-balance partial result** (from the older runs where vitals.lufs happened to exist): **Lazy Sparks
  41/22/37 (drums/bass/melodic) — drum+melodic forward; Shared Memories 26/45/29 — BASS-dominant.** Wobble +
  SCSI returned empty under the lufs method → redo via masking.band_rms_db.
- Extractor stub: `~/.track-coach/explore/balance.py` (rewrite to read masking.band_rms_db, not vitals.lufs).

## UPDATE 2026-06-25 08:55 (session resumed after Sasha's /clear — NOTHING LOST)
- Sasha panicked that the /clear wiped the night's work. Verified by deed it did NOT: all outputs are on disk
  (SCSI-9 9/9 full ✓; DeepChord split 10/10 quick; DeepChord **reenc 01–06 full ✓**; Cubist 4× quick) + this
  log is intact. /clear only wiped the chat context, never the disk.
- The re-encode junior (`aaf9bb2f`) had DIED mid-run on **reenc/07** (last write 08:46, no live demucs procs).
- **RELAUNCHED** as background sonnet-worker `a132a4fb` to finish: DeepChord reenc **07–12** (ffmpeg re-encode
  → full) + the **4 Cubist** tracks in full. Appends each run_dir to `stemfix_runs.txt`. ~60–90 min.
- **09:01 — `a132a4fb` ALSO stalled** (sonnet-workers launch a track as a bg proc then "come to rest", can't
  sequence the next). It DID finish reenc 07+08 (masking present). Replaced the agent with a self-contained
  loop: **`~/.track-coach/explore/finish_batch.sh`** (nohup, pid-independent) — does reenc 09–12 + 4 Cubist
  full, idempotent (skips any track with a result_masking.json), `wait_idle` so no 2 Demucs at once, logs to
  `finish_batch_progress.txt` + appends run_dirs to `stemfix_runs.txt`. **On resume: check that progress file +
  glob masking.json; if the script died, just re-run it (idempotent).** State at handoff: reenc 01–08 full ✓,
  09 re-encoding.

## RESULT 2026-06-25 10:05 — ALL MEASURED + CROSS-ANALYSIS DONE → **0.9 = GO**
- **All 28 tracks full-measured**: his 3 (Shared re-run for spectral-field parity) + DeepChord 12 (reenc) +
  Venetian Cubist 4 + SCSI-9 9. Analyzer: `~/.track-coach/explore/analyze_references.py`
  (band_rms_db element-balance + band-derived brightness + flatness/sustain + core mix facets; 11-facet
  z-normed; producer-friendly names; **glob.escape needed — DeepChord album dir has `[2017]`**). Report:
  `~/.track-coach/explore/REFERENCE_ANALYSIS_REPORT.md`.
- **F-5 (NEW, validated by deed): the fingerprint self-clusters each reference album without labels**
  (DeepChord 07↔08 .94, SCSI 02↔04 .90, Venetian 01↔03 .79) — strongest proof it carries style. 3 directions
  mutually-negative cosine (Deep↔Vene −.60). His tracks place sensibly: **Wobble→Venetian/IDM .74**,
  **Lazy→SCSI dub .68**, **Shared→Venetian/between .46**. His tracks sit OUTSIDE the clouds (nearest = least
  far) — correct, he's not imitating. **Confirms F-1: read>map; settles ⟨D-12⟩ toward read-not-map.**
- **VERDICT: enough data to START 0.9.** Build on: reference catalog (28 fingerprints) + per-facet READ
  surface + D-10 re-flavour. First tuning: per-(track×axis) WEIGHTING + drop `tonal→noise` (≈0 for all, no
  signal in this pool). Aspiration mapping stays Sasha's to set (D-INV-4, all-vs-all gives the menu).
- Showed Sasha the summary in chat; full numbers in the report.

## F-6 (2026-06-25, Sasha's stem intuition VERIFIED BY DEED) — energy-weighting buries the identity pad
Sasha predicted Lazy/Shared should lean SCSI/DeepChord because "пэды как в deepchord, мелодика как в scsi".
**By DISTANCE (whole vector) they DO** (Lazy & Shared both nearest SCSI, DeepChord 2nd; only the single cosine
NN flagged Venetian for Shared — I overstated it first). Then the per-stem dump confirmed his deeper point:
the full run gave MORE than the 11-facet fingerprint used. Per-stem `other` (pad/chord stem):
- **Shared Memories other: sustain 0.95, 3365 notes** ≈ DeepChord Lagonda other (sustain 1.00, 2602 notes) and
  SCSI Teplyi other (0.99, 3192). The DeepChord-grade pad + SCSI-grade melodicism he predicted ARE in the data.
- BUT that pad is only ~5% of energy (bass 59% dominates) → my **energy-weighted** `sustained` facet washed it
  to 0.37 (reads staccato). And **note-transcription (result_notes_<stem>.json) is unused as a facet.**
**0.9 LESSON (first concrete tuning, do NOT apply yet — Sasha said too early):** character axes (pad/melodic/
sustain/tonal) must NOT be loudness-weighted — a quiet pad defines identity as much as a loud kick; add
per-stem **melodicism / note-density** as its own axis (data already on disk). This is the precise form of
Sasha's "вес на ось×трек" + the manifold framing in [[track-coach-reference-representation]].
- Sasha's ask for the deliverable: when ALL measurements land, produce a FULL analysis report (fingerprints +
  cross-similarity all-vs-all: his 3 tracks × 3 reference directions + per-facet bars) and a verdict —
  **is there enough data to START 0.9 (reference/compare)?** Monitoring liveness ~every 30 min.

## 🟢 0.9 KICKOFF — Sasha's 4 decisions (2026-06-25) + build plan  ← START HERE post-wipe
**Measurements ALL done (28 tracks full). Verdict GO. This is the build plan for 0.9 first step.**
Sasha's answers to the 4 design forks:
1. **MAP — prototype first, then decide.** Build BOTH a 2-D/3-D constellation map AND the readable per-facet
   surface on the real 28 tracks; he eyeballs, then we decide if the map stays. (Don't pre-drop it.)
2. **METRIC — both side by side.** Show simple (distance/cosine to direction centroid) AND manifold (distance
   to the affine hull the refs span, normalised by their internal spread) + cosine angle, next to each other;
   decide by eye/data which is truer.
3. **WEIGHTS — Sasha delegated the thinking to me. Design (records his 3 leads, fused):**
   - **Context-specific MEASURED weights** (his "internal signals" + "similarity in a given context"): per
     reference direction, axis weight = how much that axis SEPARATES the direction's cloud from all the rest
     (|centroid gap| / pooled spread per axis). "DeepChord-ness" auto-raises sustain/bass/dark because those
     are what set DeepChord apart. Per-direction (and extensible to per-track×axis for the manifold). Measured,
     no hand-tuning.
   - **Web-descriptors = CONFIRMATION layer, not the weight source** (his lead a): google artist → candidate
     character traits → check the measured weights independently raised those axes. Agree→trust, disagree→flag.
     Web suggests, measurement decides ([[track-coach-web-descriptor-layer]]).
   - **Under all: F-6 fix** — character axes (pad/melodic/sustain/tonal) computed UNWEIGHTED by loudness first.
   - Calibrate once on the library like the other frozen thresholds; not premature per-track tuning.
4. **FIRST SURFACE — a SEPARATE module + a sketch to LOOK at. DO NOT touch the existing coach widget/catalog
   page.** Sasha's instinct (correct): reference/compare is its OWN module ("reference explorer" — place my
   track among others / explore the space), distinct from the per-track coach read. They meet later only at the
   re-flavour payoff (re-order the coach's cards "in the style of X"). 0.9 step 1 = a standalone sketch, not
   wired into the coach.

**▶ BUILD (next session, cold-OK): a standalone `reference_explorer` SKETCH (new HTML, separate from the coach
   widget) on the 28 real fingerprints showing, side by side: per-facet bars · simple-metric vs manifold-metric ·
   a 2-D/3-D map. Character axes UNWEIGHTED by loudness + add per-stem note-density axis (F-6). Add the
   per-direction discriminative weights + web-descriptor confirmation as the weighting pass. Show Sasha to
   eyeball map-vs-read + simple-vs-manifold.** Then (only after he reacts): spec-author §D update → prove →
   matrix → code. Data + analyzer: `~/.track-coach/explore/analyze_references.py`, report
   `REFERENCE_ANALYSIS_REPORT.md`. Memory: [[track-coach-reference-representation]].

## NEXT / RESUME POINT (steps 0–7 below are SUPERSEDED — measurements done; see 0.9 KICKOFF above)
0. (NEW) Rewrite `balance.py` to use `result_masking.json:band_rms_db` for element balance + `spectral_flatness`
   for tonal↔noise. Confirm DeepChord junior `a64b98d0` finished (read `~/.track-coach/explore/deepchord_runs.txt`).
   Re-run the 4 Cubist Reggae tracks in FULL mode (they're quick-only → no masking.json → no stem facets yet).
1. Check junior `a295b1e9` result (run_dirs for DeepChord + SCSI-9). If done, note which tracks got full vs quick.
2. Grab any NEWLY-downloaded SCSI-9 Line-of-Nine tracks from ~/Downloads → analyze full (same as the rest).
3. Re-run the 4 Cubist Reggae tracks in FULL mode too (currently quick) so stem facets exist for them.
4. Build the stem-based producer facets (element balance, tonal↔noise, space/width, onset density) from the
   full-mode result jsons → extend the fingerprint beyond the 15 mix-level axes.
5. Recompute cross-similarity ALL-vs-ALL: his 3 tracks × 3 reference directions (Cubist Reggae / DeepChord /
   SCSI-9), manifold belonging + per-facet bars + angle. Let the data show which track aligns with which
   direction (Sasha will confirm the mapping later — never guessed).
6. Re-do the divergence viz with producer-friendly axis NAMES (not mfcc_cosine etc.), show in browser.
7. Update this log + the memory each step. Show Sasha a clean summary in the morning.

## Open (NON-blocking — for Sasha when back, do not wait on these)
- Which album is the intended reference for which track (aspiration mapping). Doing all-vs-all meanwhile.
- Per-(track×axis) weighting of the manifold (Sasha's refinement) — design later.
- Timestamp-every-message: doing manually; offered a hook, he said "делай как хочешь" — left manual for now.

## 🟢 BUILT 2026-06-25 (s24) — `reference_explorer` standalone sketch (0.9 step 1)
**The KICKOFF deliverable is built + shown.** New SEPARATE module (coach widget/catalog UNTOUCHED, per
Sasha's call #4): `~/.track-coach/explore/reference_explorer.py` → `reference_explorer.html` (23 KB, self-
contained, opened in Chrome). On the 28 real fingerprints, three surfaces side by side:
1. **the map** — PCA 2-D (PC1·PC2) + draggable 3-D. Variance held: **PC1 52% · PC2 32% · PC3 16%** → 2-D
   honest to 84% (better than feared, but still a shadow of 11-D; the on-page note states the exact %).
2. **simple vs manifold** — per his-track × direction: SIMPLE (dist + cos to centroid) next to MANIFOLD
   (in-hull · **off-hull residual ÷ cloud spread** · alignment angle°). Affine-hull basis via Gram-Schmidt,
   off-hull = the part of his sound the direction's own tracks can't reconstruct by mixing.
3. **the read** — per-facet z-bars (his bar + direction-mean ticks), the surface F-1 calls truest.

**F-6 baked in:** character axis `sustained` is now UNWEIGHTED (each stem votes equally) + NEW `note_density`
axis (notes/sec from result_notes_*.json; range **0–18.8**, cleanly separates dense SCSI from sparse DeepChord).
`tonal→noise` DROPPED (flatness ≈0 across pool, no signal). 11 facets total.

**F-7 (NEW, the sketch's first payoff — simple & manifold DISAGREE, by deed):**
- Lazy Sparks → simple **DeepChord**, manifold **DeepChord** (agree)
- Wobble Drift → simple **DeepChord**, manifold **DeepChord** (agree)
- **Shared Memories → simple SCSI-9, but manifold DeepChord — DISAGREE.** This is exactly the F-6 pad story:
  the energy-weighted view buried Shared's DeepChord-grade sustained pad; the off-hull manifold metric (which
  the F-6-fixed unweighted `sustained` feeds) pulls it back toward DeepChord. **So the two metrics genuinely
  diverge on a real track — the sketch earns its keep; this is the case for Sasha to eyeball.**
- **▶ NEXT after Sasha reacts:** his call on map-vs-read + simple-vs-manifold → then the per-direction
  discriminative WEIGHTS pass (|centroid gap|/pooled spread) + web-descriptor confirmation → spec-author §D
  update → prove → matrix → code. Do NOT apply weights yet (Sasha: too early until he eyeballs this).

### s24 REVIEW — Sasha's verdict on the sketch (settles ⟨D-12⟩ + the metric choice)
Showed the sketch; first pass was too jargony (rebuilt in plain Russian). Sasha's calls on v2:
- **DROP the map/3-D.** Projection distance is ambiguous ("ближе — но по какой оси?"). ⟨D-12⟩ → READ, not map. Confirms F-1.
- **DROP simple-vs-manifold.** The distinction didn't read; centroids are "самые полезные". Keep ONE diagram =
  per-facet read vs direction centroids, with a plain nearest-distance line (simple centroid distance only).
- **NEW ask — mark web-derived axes on the centroids** (★) so they read as "visually more valid" (measurement
  matched the artist's described style). Implemented: WEB_AXES per direction (F-4 sourced) → star on the
  centroid tick. Legend explains. 30 stars across the 3 directions.
- Final v3 (`reference_explorer.html`, no canvas, 27 KB): nearest-distance line + 11-facet read + web-stars +
  char·UW chips. Nearest by simple distance: Lazy→DeepChord 3.33 · Shared→SCSI-9 2.73 (DeepChord 2.94 close) ·
  Wobble→DeepChord 3.54.
- **▶ NEXT (Sasha's own teed-up step): per-direction DISCRIMINATIVE weights** — compute which facets *measurably*
  separate each direction most (|centroid gap|/pooled spread) and CHECK whether they coincide with the ★ web-axes
  (measurement vs description). Then spec-author §D → prove → matrix → code. Still not applying weights to scores
  yet — first just show the agreement/disagreement of measured-separators vs web-stars.

### s24 v4 — divergence read + per-stem axes (Sasha picked layout "расхождение от как-они")
Two more complaints fixed: (a) "почему всего 11?" — axes were all mix-level. (b) bars+stars in one row = clutter.
- **EXPANDED to 16 axes, grouped:** Микс(6) · Баланс ролей(4: барабаны/бас/синт-гармония=other/лиды=guitar+vox) ·
  Характер по стемам(6: бас+пэд+лид тянучесть/плотн.нот/яркость, all loudness-UNWEIGHTED F-6). Piano DROPPED
  (0.2% energy, leakage). Stem-label memory honoured: «синт/гармония»=other, «лиды»=guitar+vocals (Demucs approx).
- **ONE surface, divergence layout** (Sasha chose it from 3 previews): pick his-track + direction via 2 selects;
  centre line = THEIR sound (fixed at 50%), his dot offset by the per-axis gap, rows sorted by |gap| desc,
  verbal tag (совпал/чуть/ощутимо/заметно выше-ниже), raw "ты/они" numbers. ★ on the axis NAME (not floating) =
  web-confirmed for that direction. Tiny JS, no canvas, 13 KB.
- **New distances (16-axis):** Lazy→Venetian 4.59 · Shared→**DeepChord 3.75** (per-stem pad axes pull it there now —
  the F-6 pad identity surfacing once stems are axes) · Wobble→Venetian 4.29.
- **▶ NEXT (Sasha's teed-up step):** measured discriminative weights per direction (|centroid gap|/pooled spread)
  → compare with the ★ web-axes (measurement vs description, agree/disagree) → then spec-author §D → prove → matrix.
