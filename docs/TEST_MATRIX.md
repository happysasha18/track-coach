# track-coach — SPEC + TEST MATRIX (source of truth)

This one document is both the **spec** (what the product must do & why) and the **test matrix** (that
spec projected into a checkable grid). Same truth, two altitudes: the prose head is the spec; the grids
are the spec made enumerable; the invariants are the cross-cutting rules a flat grid can't see. Tests
trace to it. Written/updated FIRST; code follows.

> **Bug-found protocol:** bug → ① fix/clarify the matrix cell or invariant → ② failing test, proven
> red-on-bug → ③ fix code. Code chases the matrix.
> **Change protocol:** add/change/remove any element ⇒ update this doc in the same change + decide which
> test(s) change. No partial/hybrid tests.

---

## §1 — Entities & glossary
- **run** — one analysis of one audio file, in its own dated dir (`<base>/<track>/<stamp>/`). Holds
  `result_*.json`, `narrative.md`, web audio (`stems_web/` and/or `mix_web/`), and a rendered widget.
- **mode** — `full` (Demucs stems + per-stem analysis) or `quick` (mix only, no stems).
- **view** — `simple` | `detailed`, a client-side toggle that reveals the deep (stem) layer. **full-only.**
- **surface** — **S1 widget** (one run's page, `build_widget.py`) or **S2 catalog** (the library index,
  `catalog.py`).
- **scene / structure bar** — named, lettered segments of the track; same letter = a returning part.
- **stem** — a Demucs-separated instrument layer (drums/bass/other/vocals/guitar/piano).
- **web mix** — `mix_web/mix.m4a`, a compressed single-file mix; the S2 preview-player source.
- **deposit** — a copy of a run's widget into the library + an `index.json` entry pointing back at the
  ORIGINAL run dir (`src_run_dir`/`src_widget`).

## §2 — States & transitions
States: **mode** {full, quick} × **view** {simple, detailed} (view is full-only ⇒ quick is one state)
× **.als present** {yes, no} (only changes the Evidence drawer's arrangement/automation/stem-map).
Effective: **F-S** (full+simple), **F-D** (full+detailed), **Q** (quick, no view).

Transitions:
- **toggle** (full only): S→D reveals the deep layer (stem lanes, Evidence drawer, global recs);
  D→S hides it. Opens calm (Simple) unless URL hash `#full`/`#detailed`.
- **navigate** S2→S1: a catalog title link opens that run's CURRENT widget; a play button previews the
  run's web mix in place (no navigation).

## §3 — INVARIANTS (hold in EVERY state; each owns a test)
The layer a flat grid misses — these catch cross-state bugs (e.g. INV-7 = the KI-1 class).

| # | Invariant | Owning test |
|---|---|---|
| INV-1 | The Producer's read never emits a literal leading `#`; every `#…`/`##…`/`###…` line is a heading; body after a heading is a `<p>`, never swallowed. | `test_widget_render::ProducerReadRendersServerSide` |
| INV-2 | The read is rendered SERVER-SIDE; `#readBody` ships filled iff a narrative exists, else the panel is hidden. | `…::ProducerReadRendersServerSide`, `test_widget_contract` |
| INV-3 | **Quick has no Simple/Detailed toggle** — a hint sits in its place; the toggle JS bails on quick so the body never enters `.simple` ⇒ evidence drawer + ALL recs visible. | `…::QuickHasNoToggleButAHint` |
| INV-4 | The Track Story graph opens at the **calm 4-lane** set in quick and full-simple; full-detailed = 5 (+modulation). Lane height constant ⇒ area ∝ count. | `…::PerViewLaneSets`, `…::QuickHasNoToggleButAHint::…four_lane` |
| INV-5 | The structure bar is **contiguous** (no gaps), has **no adjacent same-letter slivers**, spans 0..dur, and **preserves non-adjacent recurrence** (A/B/A). | `…::StructureBarIsTidy` |
| INV-6 | The structure bar / story is **identical full vs quick** for the same data (a track property, not a mode). | `…::StructureBarIsTidy::test_structure_bar_is_mode_independent` |
| INV-7 | A full run yields a per-stem player; quick yields a mix player; no audio ⇒ NO player (never an empty shell). | `…::PlayerIsWired`, `…::QuickRunGivesAMixPlayer` |
| INV-8 | An S2 row plays the ORIGINAL run's web mix when present; no mix ⇒ no control (graceful), never a dead button. | `test_catalog::CatalogRowPlayer` |
| INV-9 | The S2 preview scrubber rides the TIME-axis ribbon only (playhead `y2=RIB_H`), never the frequency strip. | `test_catalog::CatalogRowPlayer` |
| INV-10 | S2 column count is fixed (play/scrub live inside the existing track/signature cells) ⇒ responsive column-shedding is stable. | `test_catalog::ResponsiveTable` |
| INV-11 | The in-widget cross-version panel (`#catalog`) carries exactly the build's catalog and hides iff there are no tracks; empty/orphan build ⇒ hidden, not a false panel. | `test_widget_render::CrossVersionPanelData` |
| INV-12 | A catalog row whose linked widget is built on an OLDER `TC_VERSION` **and whose filename encodes a version** is flagged 'stale'. (Scope hole: unparseable filename ⇒ not flagged — KI-7.) | `test_catalog::StaleWidgetFlag` |
| INV-13 | `_fmt_date` formats `YYYY-MM-DD_HHMM` and never crashes on odd/multi-underscore stamps. | `test_catalog::FmtDate` |
| INV-14 | At most ONE catalog preview plays at a time — starting a row stops any other (one shared `cur` + an unconditional `stop()` before `a.play()`). | `test_catalog::CatalogRowPlayer` |
| INV-15 | A deposit either targets the run's real track slug or aborts without writing a partial/junk entry. | _gap → KI-6_ |
| INV-16 | Arrangement/automation panels render iff `.als` data exists — never as empty shells. | _gap → KI-8_ |
| INV-17 | The catalog is a LOCAL index: BOTH `open→` (`_open_href`) and play (`_mix_uri_for`) resolve to an absolute `file://` rooted in the ORIGINAL run dir. Portability scope = local filesystem, NOT GitHub Pages. | `test_catalog::CatalogIsLocalIndex` |

## §4 — Surfaces & layers
- **S1 widget** (`build_widget.py`): **L-py** server template + substitutions (`__MODEBADGE__`,
  `__VIEWTOGGLE__`, `__READBODY__`, …) and the Python helpers (`_read_html`, `_coalesce_scenes`);
  **L-js** client fill from embedded `D`/`T`.
- **S2 catalog** (`catalog.py` + pure `library.py`): one server-rendered table; **L-js** for
  filter/sort + the row preview player.

## §5 — S1 widget: element grid (show? per state · how · layer)
`✓`=visible `—`=hidden `n/a`=not produced.

| Element (id) | F-S | F-D | Q | How · layer |
|---|:--:|:--:|:--:|---|
| `modeBadge` | ✓ | ✓ | ✓ | green "Full analysis" / amber "Quick read" · L-py |
| `modeNote` (quick explainer) | — | — | ✓ | one muted line · L-py |
| `viewToggle` | toggle | toggle | **hint** | full: Simple/Detailed; quick: `.viewhint` text, no buttons · L-py |
| `vitals` / `verdict` | ✓ | ✓ | ✓ | spec row · calm headline · L-js |
| Track Story `story` | ✓ (4) | ✓ (5) | ✓ (4) | INV-4 · L-js |
| └ structure bar (scenes) | ✓ | ✓ | ✓ | INV-5/6; leads need stems (full) · L-py `_coalesce_scenes` + L-js |
| player transport | ✓ | ✓ | ✓ | play/seek/time · L-js |
| `stemlanes`+`seqKey` | — | ✓ | n/a | detailed + full only · L-js |
| `recs` | timecoded | all | all | INV-3 · L-js + CSS |
| `readPanel`/`readBody` | ✓ | ✓ | ✓ | INV-1/2 · **L-py** |
| `tonalPanel` | ✓ | ✓ | ✓ | always · L-js |
| `evidence` (arr/auto/map/rhythm/notes) | — | ✓ | ✓ (always) | full-detailed; in quick always shown (no `.simple`); arr/auto need .als, map/rhythm/notes need stems · L-js |
| `#catalog` cross-version panel | ✓ | ✓ | ✓ | INV-11 · L-js |
| footer `TC_VERSION` | ✓ | ✓ | ✓ | L-py |

## §6 — S2 catalog: element grid
| Element | full row | quick row | How · layer |
|---|:--:|:--:|---|
| title link `a.ttl` | ✓ | ✓ | → CURRENT original widget (`_open_href`); INV-12 · catalog.py |
| play button `.cplay` + scrubber | ✓‡ | ✓‡ | INV-8/9; ‡ only when web mix exists · catalog.py + L-js |
| signature `c-sig` | ✓ | ✓ | ribbon (time) over 9-band tonal strip (freq) · catalog.py |
| spec cols / `mode` pill / `modeseg` filter / search / responsive / footer ver | ✓ | ✓ | INV-10 · catalog.py |

## §7 — Cross-page links (same run, two surfaces)
mode badge (S1) ↔ mode pill (S2) same word+colour · title link opens the matching-badge widget ·
Track Story arc (S1) ↔ signature ribbon (S2) same source · S1 player ↔ S2 one-button preview (same mix).

## §8 — Coverage status
- **INV-11 — CLOSED.** `CrossVersionPanelData` pins the `D.catalog` passthrough + the hide-when-empty
  guard.
- **INV-12 — CLOSED (option a).** The catalog now flags a row whose linked widget version ≠ current
  `TC_VERSION` with a 'stale' chip (`_stale_chip`, parsed from the widget filename — no schema change),
  pinned by `StaleWidgetFlag`. So staleness is visible at a glance instead of silently opening an old
  widget. (Option b — an integration test that every deposit == `TC_VERSION` — is deferred to fixtures,
  Phase 5.) Every invariant INV-1…INV-13 now has an owning test.

## §9 — Known issues
- **KI-1 (INV-12) + KI-2 (INV-11) — ROOT CAUSE FOUND, resolved operationally.** Both came from showing/
  building the WRONG artifacts, not a product bug: catalog linked to **stale 0.7.5** widgets (KI-1), and a
  widget I built off an **orphan run dir** got an empty `D.catalog` so its version panel hid itself (KI-2).
  Fixed by re-rendering the CORRECT run dirs to 0.7.6 via real `build` (verified: both deposited widgets
  now 0.7.6, quick=hint/full=toggle, server-side read, `D.catalog`=2 tracks, no junk entry). Remaining:
  the INV-11/12 GUARDS (§8) so staleness can't recur silently.
- **KI-3 — `_fmt_date` crash — FIXED + tested** (INV-13). Junk "track-coach-output" entry cleaned.

**Prover findings (product-prover, 2026-06-20) — queued, fix in order (don't jump ahead):**
- **KI-4 (F1) — RESOLVED (a): catalog is a LOCAL index, pinned by INV-17.** The finding's premise was
  WRONG against the code: title links are NOT relative — `_open_href` has emitted an absolute `file://`
  into the original run dir since **0.7.3** (`git 746e1af`), deliberately (stems/mix sit beside the
  original; the deposited library copy is stem-less ⇒ its player is dead). So the play button's absolute
  `file://` is *consistent* with open→, not a bug beside it. Decision **(a) local-only**: declared +
  test-enforced (INV-17 = both links absolute `file://` in the SAME run dir). NOT a Pages/publishable
  artifact. Re-open as (b) — copy web mix + re-home stems relatively — only if the library is ever
  published. → owns INV-8 portability scope.
- **KI-5 (F2, INV-14) — RESOLVED (session 11).** Exclusive playback (one row at a time) now has a
  guard: `test_catalog::CatalogRowPlayer::test_exclusive_playback_one_row_at_a_time` asserts the
  rendered JS ships (1) exactly ONE shared `let cur=null` and (2) `if(cur&&cur.audio===a){ stop();
  return; } stop(); a.play(` — i.e. an unconditional `stop()` before play. A refactor to per-row
  state or a dropped `stop()` now turns the suite RED instead of silently going all-play-at-once.
- **KI-6 (F4, INV-15) — `build`/deposit has no atomicity rule.** A build off a wrong-shaped run dir made a
  junk track + a half-failed catalog regen (the KI-1 saga). Validate the run-dir shape
  (`<base>/<track>/<stamp>`) before depositing; reject malformed, don't write partial. Add a test.
- **KI-7 (F3) — INV-12 stale-flag hole:** unparseable widget filename ⇒ never flagged (the very case you
  most want caught). Fix together with INV-12 option-b: store `TC_VERSION` in the index entry at deposit
  time so the check stops depending on the filename. (Defer to Phase 5 fixtures.)
- **KI-8 (F5, INV-16) — `.als` axis declared but unpinned;** quick+.als unmodeled. Add a §5 grid row +
  invariant: arrangement/automation render iff `.als` data exists, never empty shells.
- **Ops (F4-prover):** a dead play button gives no feedback — disable it + tooltip "preview unavailable".

- **Process:** every demo I OPEN must be a real, COMPLETE `build` render (playbook + memory). Two partial
  hand-fed renders this session read as real bugs.
