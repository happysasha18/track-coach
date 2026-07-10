# Cloud validation report — track-coach

Run: 2026-07-10 (cloud environment). Clone at `main` commit `b985afa`.
Environment: macOS (Darwin arm64, Apple Silicon) — NOT Linux as the task anticipated;
brew, uv, ffmpeg, gh, node all already present. Suite ran in the project's pinned
`uv` env (`uv run --python 3.11 --with-requirements requirements.txt`).

---

## Phase 1 — turnkey validation from zero

| Step | Result | Command | Key output |
|---|---|---|---|
| 1. Clone fresh | **PASS** | `git clone https://github.com/happysasha18/track-coach.git` | exit 0; `main` at `b985afa` |
| 2. `bash setup.sh` | **PASS** | `bash setup.sh` | brew OK, ffmpeg OK, uv 0.11.21 OK, python3 OK, npm OK; all uv caches warmed (fast/deep/basic-pitch); /tc + /tc-quick installed. Nothing failed — every dependency already present, no installs needed. |
| 3. Test suite | **PASS** | `uv run --python 3.11 --with-requirements requirements.txt --with pytest python3 -m pytest -q` | **799 passed, 2 skipped in 260.80s** (exit 0). The 2 skips are the suite's pinned skip-set. |
| 4. End-to-end pipeline (quick mode) on synthetic fixture | **PASS** | `analyze --mode quick tests/fixtures/synthetic/sine_220hz_1s.wav` then `build --run-dir ...` | analyze exit 0 -> run dir written; build exit 0 -> widget `analysis_widget_v1.4.1.html` (114 KB) rendered, deposited to library, and a **catalog entry created** in `~/.track-coach/library/index.html` (row present). |

**Phase 1 verdict: PASS.** Suite 799 passed / 2 skipped / 0 failures; the widget builds and a
catalog entry is created, turnkey, from a fresh clone.

> NOTE on step 4: this is a **PLUMBING / turnkey smoke test on a synthetic 220 Hz sine tone**,
> NOT a musical analysis. A 1-second pure tone yields degenerate measurements (tempo 0, no beats)
> and librosa emits expected `n_fft too large` warnings. What it proves is the pipeline plumbing:
> measure -> render -> deposit -> catalog, all exit 0, real files on disk. Nothing about the tone's
> musicality is asserted or implied.

---

## Phase 2 — "web-descriptor for all 3 nearest matches" (SPEC D.10.2)

**Finding: the feature is ALREADY SHIPPED on `main` — it is not deferred.** The task brief describes the
*pre-merge* state ("web-read data exists only for the first match"). That state was resolved by the
**2026-07-05 D-INV-36 "Q5 merge"**, which the SPEC and TEST_MATRIX both record as folding in the
s47 "web-descriptor for all 3 nearest" feature. Following the repo's own method (a "deferred feature"
is checked against the record before any build), the correct action was to VERIFY, not re-implement.

Evidence on `main` (`b985afa`):

- **SPEC D.10.2** (docs/SPEC.md:1666-1675): "The web notes FOLLOW the shared selector, for every shown
  direction (all <=3 that qualify) ... folds in the s47 'web-descriptor for all 3 nearest' feature."
- **Code** (`scripts/build_widget.py`, `render_reference_read`, lines ~2839-2872): loops over EVERY
  shown direction and builds a per-direction `<div class="webdir" data-artist=...>` body from
  `web_notes[direction]`; the client-side selector swaps both the bars and the web body + summary artist.
- **Data** (`data/reference_web_notes.json`): full web content (genre, blurb, trait list, sources) for
  all three shipped reference artists — DeepChord, Venetian Snares, SCSI-9.
- **Test** (`tests/test_headless_render.py::MergedReferencePanel`): 6 browser-level tests, incl.
  `test_all_shown_directions_have_embedded_web_bodies` (asserts web bodies for didx ["0","1","2"])
  and `test_tab_switch_retargets_both_bars_and_web` (each tab shows its own artist). Run in isolation:
  **6 passed in 10.57s**.

**Independent verification against the REAL shipped data** (not the test's synthetic fixture): rendered
`render_reference_read` with the actual `reference_web_notes.json` for all 3 directions leaning ->
3 distinct `webdir` bodies, 3 distinct artists, each carrying its own blurb + genre in its body region.
Result: **3 web bodies / 3 distinct artists / all blurbs present -> PASS.**

**Phase 2 verdict: feature already delivered and green on `main`; no new implementation needed.**
Branch `cloud/web-data-3-matches` created and carries this report only. Nothing was implemented because
there was nothing missing. `main` was never touched.

---

## What a human must decide

The Phase 2 task premise is stale — the "web-descriptor for all 3 nearest" feature already shipped in the
2026-07-05 D-INV-36 merge and is fully tested green. **Decision needed:** either (a) accept this as
verified-already-done and close, or (b) point me at the *actual* remaining gap if the intent was a
different, still-open extension (e.g. the deferred DECIDE D-31 "and YOUR track shares this confirmed
trait" per-your-track mark, or live web fetch DECIDE D-9 / D-INV-8 which the SPEC marks not-built).
