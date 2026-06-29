# Track-Coach State Verification — Session 28
_Written by sonnet-worker, 2026-06-29. Read-only — no code or docs changed._

---

## Step 1 — Test Suite

**Command that worked:**
```
cd /Users/sashaabramovich/.claude/skills/track-coach && \
uv run --python 3.11 --with pytest --with numpy==1.26.4 --with librosa==0.10.2 \
--with soundfile==0.12.1 --with audioread==3.0.1 --with scipy==1.13.1 \
--with scikit-learn==1.5.1 --with pyloudnorm==0.1.1 \
python -m pytest tests/ -q 2>&1 | tail -40
```

**Result (pytest summary line):**
```
449 passed, 2 skipped in 1.20s
```

**Failed tests:** NONE

**Skipped tests (2):**
- `test_widget_render::SourceFileHeaderSymmetryAndReadability::test_source_file_symmetry` (INV-29, explicitly skipped with @unittest.skip)
- `test_widget_render::SourceFileHeaderSymmetryAndReadability::test_long_source_path_readable` (INV-30, explicitly skipped with @unittest.skip)

Note: memory says "451 green" but actual run shows 449 passed + 2 skipped = 451 total — consistent.

---

## Step 2 — Version String Locations

**Canonical source-of-truth (SINGLE definition):**
- `scripts/build_widget.py:31` — `TC_VERSION = "0.8.34"`
  This is the ONE place to bump. Everything else reads from it.

**Places that read/echo TC_VERSION at runtime (not hardcoded strings):**
- `scripts/catalog.py:28` — `import build_widget` then uses `build_widget.TC_VERSION` at lines 281, 283, 492
- `scripts/library.py` — references `tc_version` as a field name (not the constant), reads via `version_from_widget()`
- `scripts/track_analyzer.py:39` — `tc_version()` function that greps `build_widget.py` for the string at runtime
- `scripts/build_widget.py:2094,2138` — uses `TC_VERSION` constant (same file, not a second definition)
- `SKILL.md:489` — shell: `grep -m1 'TC_VERSION =' "$SKILL_DIR/scripts/build_widget.py" | sed -E 's/.*"(.*)".*/\1/'` (reads at invocation time, not hardcoded)

**Hardcoded version number references (NOT the canonical constant):**
- `tests/test_library.py:118,120` — hardcoded `"0.7.6"` used as a fixture value (testing deposit behavior, not TC_VERSION itself; does NOT need bumping)
- `scripts/build_widget.py:31` — the canonical definition (already listed above)

**No other files hardcode "0.8.34"** — confirmed by grep. The number appears only once in the repo (the definition in build_widget.py).

**Summary for version bump:** Change exactly ONE line:
`scripts/build_widget.py:31` — `TC_VERSION = "0.8.34"` → new version

---

## Step 3 — Git State

**`git log --oneline -8`:**
```
9e5e231 feat(0.8.34): rich reference read — gradient bars, categories, words, ★/☆ from curated web map + URL view state
cf540b6 feat(0.8.33): up-to-3 nearest-direction selector — catalog column + widget tabs (§D.10.1)
5a0ea53 feat(0.9): first reference code — 2 catalog similarity columns + per-track reference read
5104b39 spec(0.9): §D.10.1 up-to-three nearest-direction list + §D.10.2 web plaque/★
9614128 spec(0.9): remove the dead 2-D reference map from §D; re-prove reference layer
d37abf4 feat: pure geometry for the two similarity columns (similarity_columns.py) + 15 tests
86763c0 spec: color-only closeness cue + reprove holes (neutral missing, a11y)
5e36cca spec: resolve column decisions — high/med/low closeness cue, straight-line, low-last-resort
```

**`git status --short`:**
```
(no output — working tree is clean)
```

**`git log origin/main..HEAD --oneline` (commits ahead of origin):**
```
9e5e231 feat(0.8.34): rich reference read — gradient bars, categories, words, ★/☆ from curated web map + URL view state
cf540b6 feat(0.8.33): up-to-3 nearest-direction selector — catalog column + widget tabs (§D.10.1)
5a0ea53 feat(0.9): first reference code — 2 catalog similarity columns + per-track reference read
5104b39 spec(0.9): §D.10.1 up-to-three nearest-direction list + §D.10.2 web plaque/★
```

**Status:** Working tree is clean. 4 commits ahead of origin/main, NOT pushed yet.

---

## Step 4 — D-INV-27..30 in TEST_MATRIX.md and tests/

### D-INV-27
**TEST_MATRIX.md:** Has a row at line 84. Text:
> "Importance-scored, total-budgeted, diverse — no per-stem cap (Alexander 2026-06-22). ... correlated measures (energy/density/loudness) collapse to one card. Importance is scored from OBJECTIVE properties..."
> Test refs: `test_per_stem::CandidateScore`, `BudgetAndDiversity`, `CompositeCandidates`, `CollapseCorrelated` (the `eval_per_stem_usefulness` regression guard is NOT built — backlog)

**tests/ dir:** The test classes exist and PASS:
- `tests/test_per_stem.py:47` — `class CandidateScore`
- `tests/test_per_stem.py:103` — `class BudgetAndDiversity`
- `tests/test_per_stem.py:135` — `class CompositeCandidates`
- `tests/test_per_stem.py:363` — `class CollapseCorrelated`
The string "D-INV-27" appears in test_similarity_columns.py at lines 198 and 209 (in a comment about topk semantics), NOT in test_per_stem.py itself, but the classes named in TEST_MATRIX exist and pass.

**Verdict: MATRIX ROW EXISTS, TESTS EXIST AND PASS (449 green includes these).** Exception: `eval_per_stem_usefulness` regression guard is explicitly listed as NOT built — still backlog.

### D-INV-28
**TEST_MATRIX.md:** Has a row at line 87. Text:
> "Near-silent stems rank below louder ones (CR-11, Alexander 2026-06-22). Each candidate's importance score is multiplied by a prominence weight..."
> Test refs: `test_per_stem::Prominence`

**tests/ dir:**
- `tests/test_per_stem.py:291` — `class Prominence` exists and passes.

**Verdict: MATRIX ROW EXISTS, TEST EXISTS AND PASSES.**

### D-INV-29
**TEST_MATRIX.md:** Has a row at line 92. Text:
> "Source-file symmetry: if the audio source is shown, the .als source is shown too."
> Test refs: `test_widget_render::SourceFileHeaderSymmetryAndReadability::test_source_file_symmetry` (skipped)

**tests/ dir:**
- `tests/test_widget_render.py:472-476` — `test_source_file_symmetry` exists but is `@unittest.skip("PROPOSED INV-29: formalize source-file symmetry ...")`

**Verdict: MATRIX ROW EXISTS, TEST EXISTS BUT IS SKIPPED (counted in the 2 skips).**

### D-INV-30
**TEST_MATRIX.md:** Has a row at line 93. Text:
> "Long source paths stay readable. A long audio/.als path/filename must not overflow the line ugly..."
> Test refs: `test_widget_render::SourceFileHeaderSymmetryAndReadability::test_long_source_path_readable` (skipped)

**tests/ dir:**
- `tests/test_widget_render.py:479-484` — `test_long_source_path_readable` exists but is `@unittest.skip("PROPOSED INV-30: long source path must wrap / middle-ellipsis + title-hover, not overflow")`

**Verdict: MATRIX ROW EXISTS, TEST EXISTS BUT IS SKIPPED (counted in the 2 skips).**

---

## Summary Table

| Step | Finding |
|------|---------|
| Tests | 449 passed, 2 skipped, 0 failed — clean. Skips are INV-29 and INV-30 (explicitly proposed/not-built). |
| Version | Canonical: `scripts/build_widget.py:31` only. One line to change for a bump. No other hardcoded 0.8.34 anywhere. |
| Git | Clean working tree. 4 commits ahead of origin/main (not pushed). Latest commit: 9e5e231 (0.8.34). |
| D-INV-27..30 | All 4 have matrix rows. INV-27 + INV-28 have passing tests. INV-29 + INV-30 have skeleton tests that are skipped (not-yet-built features). |

_File written: /Users/sashaabramovich/.claude/skills/track-coach/data/state_verify_s28.md_
