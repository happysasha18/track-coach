# track-coach — TEST MATRIX (projection of SPEC.md; the SPEC is the source of truth)

> **Two invariant namespaces — don't conflate.** `INV-n` (bare) = §B per-stem + source-file-header invariants. `D-INV-n` = the §D reference layer. They overlap in number (both reach 27–30) but are different surfaces; always write the `D-` prefix for reference rows. (A grep in s28 mis-mapped D-INV-27..30 onto the bare INV-27..30 per-stem tests — hence this note.)

This matrix is SPEC.md projected into a checkable grid. Tests trace to it. The SPEC is the source of truth; this file is the enumerable projection. Written/updated in the same change as the code or spec.

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
The state space is **3-dimensional**: a view-state × the run's data-states. A flat (element × view)
grid hides the data axis, so it is named here and folded into §5.

**View axis** — **mode** {full, quick} × **view** {simple, detailed} (view is full-only ⇒ quick is one
state). Effective view-states: **F-S** (full+simple), **F-D** (full+detailed), **Q** (quick, no view).

**Data axis** (independent of view; each toggles whether an element has anything to show):
- **stems** {none, present, empty} — `none` = quick run (no separation); `present` = full run with real
  material; `empty` = full run where separation returned near-silence for a stem (the KI-1 class).
  Drives: stem lanes, per-stem player, stem-map / rhythm / notes, empty-stem caveat.
- **.als** {none, present} — drives ONLY the Evidence drawer's arrangement + automation panels.
- **web mix** {none, present} — drives the S1 single-track player (quick) and the S2 row preview.

A cell in §5 is `(element × view-state × data-state)`; an element that doesn't depend on a data-state
is constant across it.

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
| INV-2 | The read is rendered SERVER-SIDE; `#readBody` ships filled iff a narrative exists, else the panel is hidden. | `…::ProducerReadRendersServerSide`, `test_widget_contract::PanelsExist::test_producer_read_is_rendered_server_side_when_a_narrative_exists` |
| INV-3 | **Quick has no Simple/Detailed toggle** — a hint sits in its place; the toggle JS bails on quick. Quick is the LADDER FLOOR: it shows BRIEF recs (timecoded only, like the calm view) via `body.quick`, not all. Evidence is always visible (INV-18). | `…::QuickHasNoToggleButAHint` |
| INV-4 | The Track Story graph opens at the **calm 4-lane** set in quick and full-simple; full-detailed = 5 (+modulation). Lane height constant ⇒ area ∝ count. | `…::PerViewLaneSets`, `…::QuickHasNoToggleButAHint::…four_lane` |
| INV-5 | The structure bar is **contiguous** (no gaps), has **no adjacent same-letter slivers**, spans 0..dur, and **preserves non-adjacent recurrence** (A/B/A). | `…::StructureBarIsTidy` |
| INV-6 | The structure bar / story is **identical full vs quick** for the same data (a track property, not a mode). | `…::StructureBarIsTidy::test_structure_bar_is_mode_independent` |
| INV-7 | A full run yields a per-stem player; quick yields a mix player; no audio ⇒ NO player (never an empty shell). | `…::PlayerIsWired`, `…::QuickRunGivesAMixPlayer` |
| INV-8 | An S2 row plays the ORIGINAL run's web mix when present; no mix ⇒ no control (graceful), never a dead button. | `test_catalog::CatalogRowPlayer` |
| INV-9 | The S2 preview scrubber rides the TIME-axis ribbon only (playhead `y2=RIB_H`), never the frequency strip. | `test_catalog::CatalogRowPlayer` |
| INV-10 | S2 column count is fixed (play/scrub live inside the existing track/signature cells) ⇒ responsive column-shedding is stable. | `test_catalog::ResponsiveTable` |
| INV-11 | The in-widget cross-version panel (`#catalog`) carries exactly the build's catalog and hides iff there are no tracks; empty/orphan build ⇒ hidden, not a false panel. | `test_widget_render::CrossVersionPanelData` |
| INV-12 | A catalog row whose linked widget is built on an OLDER `TC_VERSION` is flagged 'stale'. The version is stored in the index entry at deposit time (`tc_version`, from the widget's embedded payload) so the check is filename-INDEPENDENT (option-b); old entries fall back to the filename, and a version that's unknown by both paths is not flagged (don't cry wolf). | `test_catalog::StaleWidgetFlag`, `test_library::StoresBuildVersion` |
| INV-13 | `_fmt_date` formats `YYYY-MM-DD_HHMM` and never crashes on odd/multi-underscore stamps. | `test_catalog::FmtDate` |
| INV-14 | At most ONE catalog preview plays at a time — starting a row stops any other (one shared `cur` + an unconditional `stop()` before `a.play()`). | `test_catalog::CatalogRowPlayer` |
| INV-15 | A deposit either targets the run's real track slug or aborts (raises `DepositError`) BEFORE any write — no partial widget copy / junk index entry. Junk slug = output root, `*-output`, or a dated stamp. | `test_library::DepositAtomicity` |
| INV-16 | Arrangement/automation panels render iff `.als` data exists — never as empty shells (no project ⇒ `D.als` null ⇒ each panel self-hides). Same gate in full and quick. | `test_widget_render::AlsPanelsGateOnData` |
| INV-17 | The catalog is a LOCAL index: BOTH `open→` (`_open_href`) and play (`_mix_uri_for`) resolve to an absolute `file://` rooted in the ORIGINAL run dir. Portability scope = local filesystem, NOT GitHub Pages. | `test_catalog::CatalogIsLocalIndex` |
| INV-18 | The Evidence drawer is present and visible in EVERY view — Simple, Detailed, and quick (never CSS-hidden by `.simple`). Only its inner panels gate on data (arr/auto need `.als` — INV-16; map/rhythm/notes need stems). The Simple view hides ONLY `#stemlanes`/`#seqKey` (deep stem viz), the non-timecoded `#recs`, `#refRead` (§D.10.3 Detailed-only), and `#webPanel` (§D.10.2 Detailed-only). | `test_widget_contract::SimpleViewGating` |
| INV-19 | **View ladder is monotonic: `quick ⊆ full-Simple ⊆ full-Detailed`.** For every element, if it is visible at a lower tier it is visible at every higher tier (a lower-but-not-higher visibility is a bug). The §5 grid is the enumerated source; the property must hold over ALL rows, so a NEW element can't re-introduce the inversion INV-3 fixed. | `test_view_ladder::LadderIsMonotonic` |
| INV-20 | **Cross-page mode agreement:** the S2 catalog mode pill (`.mode.{m}`) and the S1 widget mode badge (`.modebadge.{m}`) use the **same word** and the **same colour token** for the same mode (`full`→`--good`, `quick`→`--bright`). A run shown "Quick" in the catalog never opens a "Full" widget. | `test_catalog::CrossPageModeAgreement` |
| INV-21 | **No residual template placeholder.** The shipped S1 and S2 HTML contain zero `__[A-Z][A-Z0-9_]*__` tokens — every `__PLACEHOLDER__` the L-py template declares is substituted before the artifact reaches the producer. | `test_widget_contract::NoResidualPlaceholder`, `test_catalog::NoResidualPlaceholder` |
| INV-22 | **CSS gating contract = the ladder's mechanism.** Visibility tiers are realised by a single positive body class `simple` (and `quick`); **there is no `body.detailed` class** — Detailed is the absence of `.simple`, so it hides nothing and shows the full set. The Simple hide-set is exactly `{#stemlanes,#seqKey,#recs .rec:not([data-t]),#refRead,#webPanel}`; quick withholds the same stem viz by DATA absence (no stems), not a CSS rule — both honour INV-19. | `test_view_ladder::CssGatingContract` |
| INV-CSS-catrun | **`.catrun` uses `align-items:center` (not `baseline`)** so the right-hand plaque label ("you are here" / open link) sits vertically centred even when the verdict text wraps. `align-items:baseline` was the root cause of both off-centre labels and uneven row gaps. | `test_widget_contract::CatalogPlaqueCSSContract` |

### Per-stem measurements (SPEC §B.11, #2 advanced) — CODED + tested in `tests/test_per_stem.py`, EXCEPT INV-25/INV-26 (feature not built — still planned). Owning tests reconciled to the REAL class names 2026-06-23 (the earlier "planned" names — `SignificanceGates`/`DivergenceGate`/`ScoreBudgetDiversity`/`PlacementLadder`/`SortToggleIsReorderOnly`/`eval_per_stem_usefulness` — never existed under those names; this is the fix).
| INV | Claim | Owning test (real, audited 2026-06-23) |
|---|---|---|
| INV-23 | **Per-stem features are gated on significance (CR-2/CR-11).** A per-stem time-series (`result_core_<stem>.json`) is computed ONLY for `significant` stems; an empty/quiet stem yields no per-stem feature and no per-stem card. Reuses the §1 significance gate, not a fresh floor. | `test_per_stem::DivergenceCandidates`, `PerStemCards`; the `significant_stems` gate itself in `test_credibility` (G1–G7) |
| INV-24 | **Usefulness gate = divergence from the REST of the track, not volume (CR-11, Alexander's core objection).** A per-stem card fires ONLY when the stem's curve (shape, normalized) diverges NOTABLY from the mix-MINUS-that-stem (trend-sign flip and/or low correlation past τ) — never the full mix, which contains the stem. A stem that tracks the rest → NO card. Each measure carries its own validity precondition. **Brightness is NOT a prescriptive measure at all (SPEC §B.11.1, Alexander 2026-06-22): brighter/darker-than-the-rest is not a defect the coach can judge — `PER_STEM_MEASURES = (energy, density)`; relative brightness is descriptive / a future viz.** | `test_per_stem::Divergence`, `DivergenceCandidates`, `BrightnessIsNotPrescriptive` |
| INV-27 | **Importance-scored, total-budgeted, diverse — no per-stem cap (Alexander 2026-06-22).** Per-stem AND composite candidates compete with existing recs in one pool ranked by importance; the widget shows the top up to a TOTAL budget near today's count, with a diversity rule so one stem can't hog the list. Cards may be COMPOSITE (combine stems / stem-vs-track), not one-per-stem; correlated measures (energy/density/loudness) collapse to one card. Importance is scored from OBJECTIVE properties — magnitude ≥ τ, persistence over a real span, specificity (named+timed), non-redundancy — so the system self-judges usefulness with NO per-track human approval; thresholds calibrated once on the 3 fixtures and frozen. The eval is a regression guard that the shown set meets those criteria, not an approval gate. | `test_per_stem::CandidateScore`, `BudgetAndDiversity`, `CompositeCandidates`, `CollapseCorrelated` (the `eval_per_stem_usefulness` regression guard is NOT built — backlog) |
| INV-25 | **Placement honours the ladder.** Per-stem cards are Detailed-only by default; a card is promoted to Simple ONLY on a STRONG divergence (higher threshold). Any card visible in Simple is therefore also visible in Detailed (monotonic, INV-19). | **PLANNED — not built.** Per-stem cards are Detailed-only today; the Simple-promotion threshold is still ⟨DECIDE⟩. No test yet. |
| INV-26 | **Sort toggle reorders, never mutates.** The Detailed-only card-sort toggle switches the `#recs` order between by-urgency (`_rank`, default) and chronological (by `t`, matching the a/b/c cues); the SET of cards is identical in both orders — a pure presentation reorder, no add/drop. | **PLANNED — not built.** The Detailed-only urgency↔chronological sort toggle does not exist yet. No test. |
| INV-28 | **Near-silent stems rank below louder ones (CR-11, Alexander 2026-06-22).** Each candidate's importance score is multiplied by a prominence weight (0..1) = how loud the stem is RELATIVE to the loudest significant stem, from the §1 `loud_level` (dB), NOT the self-normalized per-stem energy curve. A quiet part's card therefore sorts BELOW a loud part's at equal divergence — a soft down-rank, never a drop (it still wins a slot on strong-enough divergence). Default weight 1.0 leaves prior behaviour unchanged. | `test_per_stem::Prominence` |

### PLANNED (not built) — source-file header symmetry & readability (Alexander 2026-06-22, NOT critical). The display path already wires both audio + .als (`build_widget.py:2276-2281`); these rows formalize the requirement + tripwire it. Both owning tests EXIST but are `@unittest.skip`ped (the suite's 2 skips) until implemented.
| INV | Claim | Owning test (skipped — planned) |
|---|---|---|
| INV-29 | **Source-file symmetry: if the audio source is shown, the .als source is shown too.** The header `srcmeta` line lists what was analysed. Whenever an audio source is present and shown (`Audio: …`), and an `.als` project was part of the run, it MUST be shown alongside (`Project: …`) with the same treatment — never audio-only when a project exists. (`.als` absent ⇒ no Project bit, by INV-16 gating; this is about NOT dropping it when present.) | `test_widget_render::SourceFileHeaderSymmetryAndReadability::test_source_file_symmetry` (skipped) |
| INV-30 | **Long source paths stay readable.** A long audio/`.als` path/filename must not overflow the line ugly: it wraps or middle-ellipsis-truncates with the full value available on hover (`title`), and the `srcmeta` row degrades gracefully on narrow widths. The current `.srcmeta{flex-wrap:wrap}` (`build_widget.py:1951`) wraps but does not truncate a single very-long token — the open work is the nice truncation/hover. | `test_widget_render::SourceFileHeaderSymmetryAndReadability::test_long_source_path_readable` (skipped) |

### Card evidence, artistic read & player invariants (SPEC §B.12/§B.13, shipped 0.8.27–0.8.29) — CODED + tested. Owning tests reconciled to real names 2026-06-23.
| INV | Claim | Owning test (real, audited 2026-06-23) |
|---|---|---|
| INV-31 | **Every advice card names where it came from (card evidence, SPEC §B.13, Alexander 2026-06-23).** Every entry in `D.recs` (the `#recs` "Start here" list — mix-level recs AND per-stem cards) carries a NON-EMPTY `based_on` line. It is plain language, never a bare metric identifier (`true_peak_db`); a single-signal (Tier-A) card may name one signal in words, a fused (Tier-B/C) card names the combination. Panel note cards (separation/rhythm/project) are out of scope this increment (F2). Machine-checkable part = non-empty + present on all `D.recs`; the plain-language/non-restating quality is authored. | `test_fixtures::GoldenRenderFromRealData::test_every_card_carries_a_based_on_line`, `test_per_stem::PerStemCards` |
| INV-32 | **`development_mode(core)` is a deterministic, direction-carrying read of how the track develops (SPEC §B.12, Alexander 2026-06-23).** Pure helper over the four Pearson trends (`energy_/brightness_/density_/stereo_width_trend`, same [−1,1] unit). Returns each axis with `|trend| ≥ 0.12` as DOMINANT **with its sign** (louder/pulls-back, brightens/darkens, busier/thins, widens/tightens), and axes with `|trend| < 0.10` as idle-flag-eligible ONLY when ≥1 dominant axis exists. A track with NO dominant axis returns empty dominant + empty idle (the read then adds no development sentence — does not double-cover `energy_flat`). Calibrated by deed on the 3 library tracks. | `test_development_mode::DevelopmentMode` |
| INV-33 | **A seek preserves playback state — clicking a rec card / cue / chart while playing must NOT stop it (Alexander 2026-06-23, 0.8.28).** `seekTo(t)` captures `wasPlaying = !master.paused`, sets every stem's `currentTime`, paints the playhead, and if it was playing **resumes all stems together** (`auds.map(s=>s.a.play())`) — which also re-syncs them so a mid-play seek can't leave the stems phased. A seek while paused stays paused (it does not auto-start). Sits beside INV-14 (exclusive playback) as a player invariant. | `test_widget_render::PlayerIsWired::test_seek_keeps_playback_running` |
| INV-34 | **Card evidence NAVIGATION — clicking a timecoded card draws the eye to the moment on the graph (SPEC §B.13, 0.8.28).** A timecoded `#recs` card's click seeks the playhead to its moment AND scrolls `#storyPanel` into view AND briefly toggles a `pulse` class on the graph panel (a CSS attention pulse). The pulse is **CSS/DOM only — it must NOT modify the canvas draw** (the canvas is the fragile surface). The class auto-clears after the animation. Global (non-timecoded) cards don't navigate. | `test_widget_render::PlayerIsWired::test_card_click_pulses_the_graph` |

### Player state machine (SPEC §B.14, 2026-06-23) — CODED + tested by EXECUTING the real shipped JS in node (not a Python mirror). The pure helpers (`pgains`/`toggleStem`/`seekResult`) are extracted between `__PLAYER_LOGIC_START__`/`__PLAYER_LOGIC_END__` markers in the rendered widget; the test pulls that block out of the HTML, runs it in node, and asserts the combinations the old string-match tests never reached.
| INV | Claim | Owning test (real) |
|---|---|---|
| INV-35 | **One mode at a time.** After ANY sequence of mute/solo toggles via `toggleStem`, the player is never in `(some stem muted) AND (some stem soloed)` at once — muting clears solos, soloing clears mutes (Alexander 2026-06-21). | `test_player_logic::PlayerStateMachine::test_one_mode_at_a_time` |
| INV-36 | **Solo resolves gains.** When any stem is soloed, `pgains` makes the audible set EXACTLY the soloed stems (every non-soloed stem muted), regardless of individual mute flags. | `test_player_logic::PlayerStateMachine::test_solo_resolves_gains` |
| INV-37 | **Mute resolves gains.** When no stem is soloed, `pgains` makes audible(stem) = `!stem.mute`. | `test_player_logic::PlayerStateMachine::test_mute_resolves_gains` |
| INV-38 | **Seek preserves transport AND mix (the combination INV-33 generalises).** `seekResult(t,dur,wasPlaying)` reports resume iff `wasPlaying`, and seek does NOT touch any stem's `{mute,solo}` — so solo→seek-while-playing leaves the same one stem the only audible one AND keeps playing; seek-while-paused stays paused. | `test_player_logic::PlayerStateMachine::test_seek_preserves_transport_and_mix`, `test_widget_render::PlayerIsWired::test_seek_keeps_playback_running` |
| INV-39 | **Seek clamps.** `seekResult` always returns t ∈ [0, dur] — a negative / gutter / over-duration click never seeks out of range. | `test_player_logic::PlayerStateMachine::test_seek_clamps` |
| INV-40 | **Player composes with the VIEW axis — entering Simple resets the per-stem mix (SPEC §B.14 inv 6; Alexander found by deed 2026-06-23).** Solo/mute is a Detailed-only capability (the M/S controls live in `#stemlanes`, hidden in Simple, INV-18/22). Switching to Simple calls `resetMix` → every stem `{mute:false,solo:false}` → `pgains` all-audible, so a soloed/muted part is never left audible-but-invisible-and-unundoable. `resetMix(stems)` is pure (all-false) and the `apply("simple")` toggle wires `window.__resetMix`. | `test_player_logic::PlayerStateMachine::test_simple_resets_mix`, `test_widget_render::SoloAndMuteAreMutuallyExclusive::test_simple_toggle_resets_the_mix` |

### View selector as remembered state (SPEC §B.15, 2026-06-29) — CODED + tested. resolveView extracted between VIEW_LOGIC_START/END markers and run in node (same pattern as player logic).
| INV | Claim | Owning test (real) |
|---|---|---|
| INV-41 | **Global remembered view (Simple/Detailed).** One localStorage-backed preference (`tc_view`), read on open by precedence URL-hash > stored > calm-first-use; only a toggle writes; read-on-load (no live cross-tab sync); degrade-safe (a store throw never breaks view init); ladder visibility (INV-18/22) unchanged — only which view opens. | node `resolveView` test + widget-render order/panel tests |

## §4 — Surfaces & layers
- **S1 widget** (`build_widget.py`): **L-py** server template + substitutions (`__MODEBADGE__`,
  `__VIEWTOGGLE__`, `__READBODY__`, …) and the Python helpers (`_read_html`, `_coalesce_scenes`);
  **L-js** client fill from embedded `D`/`T`.
- **S2 catalog** (`catalog.py` + pure `library.py`): one server-rendered table; **L-js** for
  filter/sort + the row preview player.

### §4b — Style layer (CSS visibility contract — the historically-fragile axis)
View gating is CSS, asserted on the RENDERED stylesheet (INV-22). Body classes set by L-py
(`__BODYCLASS__` = `"quick"` on a quick run, else empty) and L-js (toggle adds/removes `simple`).

| body class | who sets it | hides (selector → effect) |
|---|---|---|
| _(none)_ = **Detailed** | default for full (no `.simple`) | nothing — full element set visible |
| `simple` | L-js toggle (`apply("simple")`) | `#stemlanes`, `#seqKey` → `display:none`; `#recs .rec:not([data-t])` → `display:none`; `#refRead` → `display:none`; `#webPanel` → `display:none` |
| `quick` | L-py at render (`__BODYCLASS__`) | `#recs .rec:not([data-t])` → `display:none` (stem viz withheld by DATA absence, not CSS) |

Contract: **no `body.detailed` / `.detailed` selector exists** (Detailed = absence of `simple`). Adding
one is a new tier mechanism ⇒ update INV-22 + §5 first. The quick stem-viz hole (a quick run that
somehow emitted `#stemlanes` would not be CSS-hidden) is closed by data, not style — so if quick ever
gains stem data, INV-22/§5 must add a `body.quick #stemlanes` rule.

## §5 — S1 widget: element grid (show? per view-state × data-state · how · layer)
`✓`=visible `—`=hidden(CSS) `n/a`=not produced(data). The **data gate** column names the data-state an
element depends on (§2 data axis); where it says "—", visibility is view-only and constant across data.

| Element (id) | F-S | F-D | Q | data gate | How · layer |
|---|:--:|:--:|:--:|---|---|
| `modeBadge` | ✓ | ✓ | ✓ | — | green "Full analysis" / amber "Quick read" · L-py |
| `modeNote` (quick explainer) | — | — | ✓ | — | one muted line · L-py |
| `viewToggle` | toggle | toggle | **hint** | — | full: Simple/Detailed; quick: `.viewhint` text, no buttons · L-py |
| `vitals` / `verdict` | ✓ | ✓ | ✓ | — | spec row · calm headline · L-js |
| Track Story `story` | ✓ (4) | ✓ (5) | ✓ (4) | — | INV-4 · L-js |
| └ structure bar (scenes) | ✓ | ✓ | ✓ | scene leads need stems=present | INV-5/6; bare bar always, lead labels only full · L-py `_coalesce_scenes` + L-js |
| player transport | ✓ | ✓ | ✓ | needs web mix OR stems (else absent) | per-stem if stems=present, mix if web mix; no audio ⇒ no player (INV-7) · L-js |
| `stemlanes`+`seqKey` | — | ✓ | n/a | stems=present | hidden in Simple (CSS); quick has stems=none ⇒ not produced · L-js + CSS |
| `recs` | timecoded | all | timecoded | — | ladder INV-3/19: quick filters via `body.quick`, Simple via `body.simple` · L-js + CSS |
| `readPanel`/`readBody` | ✓ | ✓ | ✓ | hidden if no narrative (INV-2) | server-rendered; panel self-hides when empty · INV-1/2 · **L-py** |
| `tonalPanel` | ✓ | ✓ | ✓ | — | always · L-js |
| `evidence` drawer | ✓ | ✓ | ✓ | — | ALWAYS visible in every view (INV-18) · L-js |
| └ arr/auto panels | ✓ | ✓ | ✓ | .als=present | each self-hides with no `.als` (INV-16) · L-js |
| └ map/rhythm/notes panels | ✓ | ✓ | n/a | stems=present | self-hide without stems; quick=none · L-js |
| └ empty-stem caveat | ✓ | ✓ | n/a | stems=empty | shown only when a stem came back near-silent (KI-1 class) · L-js |
| `#catalog` cross-version panel | ✓ | ✓ | ✓ | hides if 0 tracks (INV-11) | INV-11 · L-js |
| footer `TC_VERSION` | ✓ | ✓ | ✓ | — | L-py |

> This grid is mirrored by the `GRID` dict in `test_view_ladder::LadderIsMonotonic::test_grid_visibility_is_monotonic`
> (the monotonicity property test). **Change both together** (change protocol). The companion checks in
> that file read CSS hide-sets off the rendered HTML and are drift-proof on their own.

## §6 — S2 catalog: element grid
| Element | full row | quick row | data gate | How · layer |
|---|:--:|:--:|---|---|
| title link `a.ttl` | ✓ | ✓ | — | → CURRENT original widget (`_open_href`); INV-12 · catalog.py |
| play button `.cplay` + scrubber | ✓‡ | ✓‡ | web mix=present | ‡ control omitted with no mix (INV-8); scrubber rides ribbon (INV-9) · catalog.py + L-js |
| signature `c-sig` | ✓ | ✓ | curves present (else dash) | ribbon (time) over 9-band tonal strip (freq) · catalog.py |
| spec cols (bpm/key/len/LUFS/…) | ✓ | ✓ | per-metric dash if absent | INV-13 date fmt · catalog.py |
| `mode` pill `.mode.{m}` | ✓ | ✓ | — | word+colour agree with S1 badge (INV-20) · catalog.py |
| `stale` chip | ‡ | ‡ | linked widget < TC_VERSION | INV-12 · catalog.py |
| `modeseg` filter / search box | ✓ | ✓ | — | client filter/sort · L-js |
| responsive column-shed | ✓ | ✓ | — | fixed col count, progressive shed (INV-10) · catalog.py |
| footer version | ✓ | ✓ | — | catalog.py |

## §7 — Cross-page correspondences (same run, two surfaces) — each row is an invariant
A flat per-surface grid can't see drift BETWEEN the two pages; these are the cross-page rules.

| # | S1 widget source | S2 catalog source | rule | owning test |
|---|---|---|---|---|
| X1 | mode badge `.modebadge.{m}` | mode pill `.mode.{m}` | same word + same colour token (`full`→`--good`, `quick`→`--bright`) | INV-20 · `test_catalog::CrossPageModeAgreement` |
| X2 | the widget a title link opens | row title link `_open_href` | the link opens THAT run's CURRENT widget; stale ⇒ flagged, not silently old | INV-12/17 · `test_catalog::StaleWidgetFlag`, `CatalogIsLocalIndex` |
| X3 | Track Story arc (`story` curves) | signature ribbon `c-sig` | same underlying run curves (ribbon = downsample of the arc source) | `test_catalog::RunMetrics`, `Signature` |
| X4 | S1 player (per-stem / mix) | S2 one-button preview | both play the SAME run's web mix; absent mix ⇒ no control on either (INV-7/8) | `test_catalog::CatalogRowPlayer` |

## §E — Run completeness & missing measurements (SPEC §E → RC-INV-1…12)

The cross-cutting "partial run" rules, projected to a checkable grid. The canonical logic is one shared
module (`scripts/completeness.py`) so the coach, catalog, and §D all treat *missing* the same way; the
pure-logic invariants are unit-tested NOW, the surface-rendering ones land with the §D/manifest code.

| code | rule (1-line) | owning test / status |
|---|---|---|
| RC-INV-1 | missing (None/NaN) ≠ measured-zero; never collapse | `test_completeness::MissingIsNotZero` ✓ |
| RC-INV-2 | a run carries a completeness manifest; read it, not a sentinel | `test_completeness::MissingIsNotZero::manifest` ✓ |
| RC-INV-3 | never impute missing→real value then show/compare | `test_completeness::CompareOverSharedAxesOnly` ✓ |
| RC-INV-4 | surface shows "not measured", omits the card (no evidence) | not built — lands with the per-facet/catalog render |
| RC-INV-5 | compare over BOTH-present axes only; never 0-gap/max-gap | `test_completeness::CompareOverSharedAxesOnly` ✓ |
| RC-INV-5a | < `MIN_SHARED_AXES` shared ⇒ "not comparable", not a 0 | `test_completeness::TooFewSharedIsNotComparable` ✓ |
| RC-INV-5b | rank directions by **per-axis** distance (axis-count-fair) | `test_completeness::RankingIsAxisCountFair` ✓ |
| RC-INV-6 | centroid per-axis over members that HAVE it; absent≠0 | `test_completeness::CentroidSkipsMissingMembers` ✓ |
| RC-INV-7 | missing-by-mode silent; missing-in-promised-surface shown | not built — composes with view ladder INV-18/22 |
| RC-INV-7a | the rung→promised-surface list is the single authority | not built — keys off §B.14/INV-18/22 |
| RC-INV-8 | same missing axis reads identically across coach/catalog/§D | not built — lands with the manifest render |
| RC-INV-9 | pick most-complete run; run-id in content-hash (D-INV-14) | not built — lands with run selection + §D placement |
| RC-INV-10 | gap → re-measure, never impute; ⟨DECIDE E-1⟩ auto vs flag | partial-run logic **built+tested** — `test_completeness::PartialRunIsAnError`; UI re-measure command not built (backlog) |
| RC-INV-11 | significance has a third `unknown (not measured)` state | `test_completeness::SignificanceHasUnknown` ✓ |
| RC-INV-12 | one per-run completeness line so absence≠all-clear | not built — lands with the coach render |

**Settled 2026-06-25 (Alexander):** E-1 = partial run is a technical error → flag "прогон неполный, перезапусти"
(manual, no auto, no imputation; `is_partial_failure`/`incomplete_axes`). E-2 = `MIN_SHARED_AXES` = **10**
(below it: not comparable; guards missing DATA not dissimilar music; `comparable`/`nearest` default to it).
22 logic tests, proven red-on-bug (inject impute-as-0 ⇒ 5 fail).

## §D10F — Catalog similarity columns (SPEC §D.10 + §F → D-INV-21…25, F-INV-1…8)

Two side-by-side catalog columns (+ a Detailed plaque chip for the reference one). The **geometry** rows
ride the already-shipped `completeness.py` (axis-count-fair nearest, RC-INV-5b) and are testable NOW; the
**surface-render** rows land with the §D/§F catalog+widget code (asserted against the REAL rendered
`index.html` / widget, never a source fragment — same discipline as §6/§7). Scope: reference column ships
**0.9**, the own-library DJ column ships **1.0**.

### §D core reference-layer invariants (SPEC §D.5 → D-INV-4…20)
Projection of the §D.5 safety/liveness block. Each row is honest about build state: the **descriptive**
half (leans-toward, per-facet read, completeness geometry) ships 0.9 and is testable NOW; the **verdict**
half (in-zone/diverge/«своё») and the **mapping/aim** input are deferred until the mapping input ⟨D-2⟩, and
the **references switch** + **reference-track ingestion** + **live web fetch** are separate not-built
surfaces. Not-built rows carry no owning-test citation (they name the surface they land with instead).
| code | rule (1-line) | owning test / status |
|---|---|---|
| D-INV-4 | The tool never guesses which direction a track aims at — the mapping is always yours, and many-to-many | not built — mapping input deferred ⟨D-2⟩ (aim feature excised 0.9.15). Level when built: node (mapping logic) + browser (aim glyph) |
| D-INV-5 | A track with no mapping is byte-for-byte as today (cards/read/player); the «leans toward» line + reference catalog are *additive* new surfaces, not a change to the widget | descriptive surface is additive + gated NOW: `test_reference_read::ReferenceReadDetailedOnly` (refRead absent without a run dir, hidden in Simple, none in quick); the no-mapping-mutation guarantee lands with the mapping input ⟨D-2⟩. Level: browser-render |
| D-INV-6 | The show/hide-references control is ONE named switch shared by the reference column + plaque chip; no view strands its state | not built — lands with the references switch (see D-INV-23). Level when built: browser (toggle state survives view flips + reopen, never strands) |
| D-INV-7 | Reference tracks never enter your library's catalog/signatures; the switch only surfaces them through the reference column (audio-only) | not built — lands with reference-track ingestion; the §F own-library column is a *separate* surface, never under the references switch. Level when built: node (ingestion boundary) + render |
| D-INV-8 | Any web fetch completes, fails, or times out and the feature carries on — it never hangs the analysis or the render (liveness) | not built — live web fetch deferred ⟨DECIDE D-9⟩; the current `#webPanel` renders curated static notes (D-INV-29), so there is nothing to time out yet. Level when built: node (async/timeout harness) |
| D-INV-9 | A reference either yields a placeable fingerprint + read, or reports which signals it couldn't compute — never a half-finished silent state; a missing-axis reference is catalogued but NOT comparable, yet still contributes per-axis to its cloud centroid | **BUILT (node)** — `test_completeness::CompareOverSharedAxesOnly`, `::TooFewSharedIsNotComparable`, `::CentroidSkipsMissingMembers`, `::PartialRunIsAnError`; `test_similarity_columns::LeansTowardCompleteness` |
| D-INV-10 | Every character / mood / style / in-zone statement carries its real evidence — one signal or a combination; with none it is omitted, never shown (anchored read) | **BUILT (browser-render)** — `test_reference_read::ReferenceReadRichLook` (★ only when the centroid confirms, no-star when contradicted or near-mean), `::ReferenceReadOmitsMissingAxes` (missing axis omitted, never drawn at zero). The in-zone evidence half lands with the mapping verdict ⟨D-2⟩ |
| D-INV-11 | The verdict is read in FULL dimensions and is authoritative; no lossy 2-D/3-D projection (the map was dropped); the «leans toward» line + read derive from the same full-dim fingerprint, so they can never disagree | **BUILT (node)** — `test_similarity_columns::LeansTowardPicksNearestDirection` (nearest by full-dim centroid, no map), `test_completeness::RankingIsAxisCountFair` (per-axis distance, not a projected/raw-sum marker). Cross-surface agreement render composes with D-INV-21 |
| D-INV-16 | «своё» and in-zone/diverge are computed only against CLOUD directions; a reduced direction (too few members for a zone) never produces a verdict, and a track aimed only at reduced directions has no «своё» | reduced-direction *nearest-by-member* is built (D-INV-21); the in-zone/diverge/«своё» **verdict** lands with the mapping input ⟨D-2⟩. Level when built: node (cloud-vs-reduced gating) |
| D-INV-18 | Adding and removing a member are symmetric: both recompute the direction's cloud + every dependent read and re-stamp; a threshold crossing reduces/appears the verdict; a read's stamp always matches the member count it was computed against | not built — member add/remove + re-stamp composes with the placement/epoch code (D-INV-12/14). Level when built: node (recompute symmetry + stamp/hash) |
| D-INV-19 | in-zone/diverge/«своё» is a pure function of the full-dim fingerprint (per-facet spread test); there is no projection to disagree — the full-dim verdict is the only one and is authoritative | per-facet full-dim decomposition built (render): `test_reference_read::ReferenceReadBars`, `::ReferenceReadMostDivergentFirst`; the in-zone/diverge **verdict** lands with the mapping input ⟨D-2⟩. Level: browser-render + node |
| D-INV-20 | Reference / compare is a FULL-run-only feature — quick mode is never referenceable; shown as "full analysis only", silent (RC-INV-7), never a partial-run error (RC-INV-10) | **BUILT** — `test_reference_read::ReferenceReadDetailedOnly::test_quick_mode_has_no_refread_block`, `test_completeness::SharedAxisFloor::test_quick_vs_full_not_comparable`. The catalog-cell "full analysis only" is a separate surface (D-INV-22, not built) |

### Reference line «leans toward» (SPEC §D.10)
| code | rule (1-line) | owning test / status |
|---|---|---|
| D-INV-21 | catalog column = plaque chip = read panel's nearest — ONE full-dim geometry, never a 2-D marker distance (no map); the single nearest is chosen across ALL directions (clouds by centroid · reduced by nearest member), axis-count-fair (RC-INV-5b); no directions ⇒ "no direction yet", never a fabricated nearest | geometry NOW via `test_completeness::RankingIsAxisCountFair`; cross-surface agreement + empty-case render: not built — lands with §D render |
| D-INV-22 | quick-only version ⇒ cell "full analysis only" (silent, RC-INV-7); row reads the version's most-complete run (E.4); never blank-implies-none | not built — lands with catalog render + run selection |
| D-INV-23 | both placements under the ONE references switch; toggle hides/shows both; never strands | not built — lands with the switch + catalog/widget render |
| D-INV-24 | recompute + re-stamp on library/epoch change; catalog never shows a stale "leans toward" | not built — composes with D-INV-12/14 placement code |
| D-INV-25 | never a NUMBER — no raw distance / score / rank / % / "match %"; only a direction name + a coarse cue | not built — assert rendered chip carries no numeric token at all |
| D-INV-26 | cue = coarse closeness shown by COLOUR only (green close / amber mid / red far) — no words, no number, not a grade (red=far, not worse). Reference basis = RELATIVE lean (D-28); §F basis = library distribution (D-27). §F red only as last resort. Reference runner-up DEFERRED (D-24) | geometry **BUILT+TESTED** `test_similarity_columns::RelativeLeanBuckets` + `NearestOwnRedIsLastResort`; colour render: not built — assert §D reference cell carries a greyscale-safe glyph tier (●●●/●●○/●○○) beside colour, §F uses nearest-first order, both carry a hover label; no numeric/word closeness token on any cell |
| D-INV-27 | **Up-to-three nearest directions as a nearest-first list, not a single name + crammed runner-up tint.** Lists up to the 3 nearest reference clouds that clear the lean bar, ranked nearest-first; order carries the rank, each entry tinted by its own gap-to-next colour cue; never pads to 3 with weak/far filler ("no close direction yet" instead). Descriptive (ships 0.9, no mapping needed); the aim glyph / pinned-aimed entry / re-flavouring are deferred until the mapping input ⟨D-2⟩. | `test_similarity_columns::TopKBasics` (built+tested) |
| D-INV-28 | **Every name is a navigation link; the read-panel direction tab is ephemeral, never a persisted selection.** Catalog: track→open, own sibling→scroll (F-INV-4), direction→open read focused. Read panel: tabs default to nearest and re-target the read+plaque; tab is ephemeral (not written to the URL) — cross-page entry-focus is a one-shot URL param read once on load. On a recompute that drops the focused direction the read falls back to nearest; if it empties entirely the open panel collapses to "no close direction yet" (tabs+bars removed, prose kept), re-stamped. | read-panel tabs: built. Catalog click-to-focus wiring + recompute-empties: **0.9.x design** (href placeholder in 0.9). By-ID test: TODO punch-list |
| D-INV-29 | **The web-style plaque shows only facets a curated facet→signal map ties to measurement; ★ = directly confirmed on the direction's centroid, ☆ = soundly indirect, contradicted = withheld.** Two glyphs + one footnote (never long per-row tags); judged on the cloud centroid (D-INV-21); per-artist, never blended; an absent plaque is a valid silent state; completeness-aware (a missing axis ⇒ not ★/☆, not shown). The plaque is now a readable collapsible `#webPanel` in the widget (§D.10.2 — "What the web says about ⟨artist⟩"), collapsed by default, last in the read order (producer read → tonal balance → centroid read → web panel). | `ReferenceReadRichLook` (built+tested); `test_reference_read::WebPanelRendering` (collapsed, summary, artist header, phrase+glyph, absent when no marks); `test_widget_render::ReadOrderTonalBeforeRefRead::test_webpanel_css_gate_present` |
| D-INV-30 | **The reference read decomposes per-facet vs the direction's centroid — signed z-normalised bars, most-divergent first, no raw distance/score.** Detailed-only; reads against the focused direction tab, falls back on recompute; a missing facet is omitted, never drawn at zero. Fixed read order (§D.10.3): producer read → tonal balance (#tonalPanel) → centroid read (#refRead) → web panel (#webPanel). | `ReferenceReadBars` (built+tested); `test_reference_read::ReadOrderWithRefRead` (tonalPanel < refRead < webPanel in rendered HTML) |

### The aim picker & «toward X» panel (SPEC §D.6.1) — REMOVED 0.9.15 (see JOURNAL 2026-07-02)
> The feature was excised entirely in 0.9.15. `tests/test_aim_panel.py` was deleted. Rows below are
> kept as history only — all "BUILT" claims are void; the cited tests do not exist.

| code | rule (1-line) | owning test / status |
|---|---|---|
| D-INV-31 | **The aim panel is one named collapsible surface `#aimpanel`, default-collapsed, distinct from the in-place read.** A `<details>` placed right after `#refRead`; lists prioritized ordered steps toward the selected aim. | REMOVED 0.9.15 — `test_aim_panel.py` deleted |
| D-INV-15 (stage-2) | **Card SET identical to plain view — re-flavour never adds, removes, hides, or changes the based-on evidence.** | REMOVED 0.9.15 — `test_aim_panel.py` deleted |
| D-INV-17 (stage-2) | **Divergence is a secondary sort key inside the urgency tier — diverging cards rise within crit/do/concept, not across them; option-notes on diverging cards; on-style marks on matching-style cards.** | REMOVED 0.9.15 — `test_aim_panel.py` deleted |
| D-INV-32 | **Build embeds, per offerable direction, the aim-panel steps + re-flavoured cards; the dropdown swaps client-side — no re-run, keyed on slug, "no aim" = baseline.** | REMOVED 0.9.15 — `test_aim_panel.py` deleted |
| D-INV-33 | **Composition across the selection states, no stranding.** | REMOVED 0.9.15 — `test_aim_panel.py` deleted |
| D-INV-34 | **Every step is a real finding, ordered by divergence-toward-aim, never invented; "already close" when nothing moves; cites based-on.** | REMOVED 0.9.15 — `test_aim_panel.py` deleted |

### Similar-in-your-own-library, the DJ column (SPEC §F)
| code | rule (1-line) | owning test / status |
|---|---|---|
| F-INV-1 | up to 3 nearest OWN tracks, axis-count-fair (RC-INV-5b), ranked; default = high/medium siblings; if none qualify, fall back to the single nearest **marked low** (last resort, never empty when another track exists); "no comparison yet" only when no other placeable track at all | geometry NOW (`completeness.nearest` + bucket gate + low-fallback); render: not built |
| F-INV-2 | a track is never its own neighbour; per-row display may be asymmetric (A lists B, B's top-3 need not list A) | geometry NOW (self excluded); render: not built |
| F-INV-3 | no score shown — names the neighbour tracks (+ optional in-zone cue), never a % or rank number | not built — assert rendered cell carries no numeric-score token |
| F-INV-4 | click a neighbour ⇒ catalog scrolls to that row + highlights it; pure navigation, changes no analysis state | not built — lands with catalog client-JS (node-exec like the player tests) |
| F-INV-5 | quick-only version ⇒ "full analysis only" (silent, RC-INV-7), exactly like D-INV-22 | not built — lands with catalog render |
| F-INV-6 | a version missing a fingerprint axis: not listed AND not offered AS a neighbour; cell "can't compare — ⟨signals⟩" | geometry NOW (not-comparable via RC-INV-5a `TooFewSharedIsNotComparable`); render: not built |
| F-INV-7 | with no other placeable own-track, the cell reads "no comparison yet", never an empty-looks-broken cell | not built — lands with catalog render |
| F-INV-8 | recompute + re-stamp on library/epoch change; never points at a deleted version (cascade like D-INV-13) | not built — composes with placement + deposit/clean |

**Geometry layer BUILT+TESTED 2026-06-25 (s25):** `scripts/similarity_columns.py` (`leans_toward` + `nearest_own`
over `completeness.py`) — pure logic, no render. `tests/test_similarity_columns.py` (15 tests, red-on-bug
proven: a fabricated nearest fails the no-directions→None test). Suite 375 green (+15), 0 regression. Covers the
geometry half of D-INV-21/26 + F-INV-1/2/6/7; the colour render + scroll-nav (D-INV-22/23/25, F-INV-4/5) land
with the §D/§F catalog code, asserted against the real artifact. **D-24 runner-up RE-OPENED + deferred** (a
tied second is a weak lean, not a close one — self-contradictory under relative lean).

**Settled 2026-06-25 (Alexander):** D-17 = straight-line. D-28 = reference cue is RELATIVE lean (not absolute
cloud-depth). Closeness shown by **colour only** — green/amber/red tint on the name, NO closeness words, no
number (color-only). D-24 = runner-up only when also green. F-3 = up to 3 green/amber; red only as a last
resort, never empty if a sibling exists. F-4 = own inherits straight-line. Visibility = shown if ≥1 track has
data, else absent. Both columns at the catalog tail, smaller font; **interface in English**. Open: D-27
(own-library bucket boundaries), F-1 (filtered-row scroll), F-2 (plaque presence), D-25 (Simple chip).
Verify-by-deed on the real library: relative lean tints Lazy→Venetian green, Shared→SCSI-9 amber,
Wobble→Venetian amber — no all-red deadness the absolute basis produced.

**Prove (2026-06-25, s25 re-prove of the two new surfaces) closed 2 composition holes:** (1) a not-measured /
not-comparable cell uses a NEUTRAL grey/dash, never the red "far" tint (red=measured-far, grey=no-measurement;
missing-as-value trap RC-INV-1 in colour form) — owning test lands with the colour render, assert
not-measured tint ∉ {green,amber,red}; (2) colour is never the sole channel — nearest-first order + a hover
label keep the cue readable in greyscale / for colour-blind readers (D-INV-26) — owning test: assert each
coloured cell carries an order rank + a title attr.

**Cross-page (extends §7).** The reference column's "leans toward X" on a catalog row names the SAME nearest
direction the §D read panel cites for that track (D-INV-21) — one full-dim geometry, two surfaces (no map);
owning test lands with the §D render. The own-library column is NOT under the references switch (§F vs D-INV-23) — a switch-off
state hides the reference column but leaves the DJ column visible; owning test lands with the switch render.

## §8 — Coverage status
- **INV-11 — CLOSED.** `CrossVersionPanelData` pins the `D.catalog` passthrough + the hide-when-empty
  guard.
- **INV-12 — CLOSED (option a).** The catalog now flags a row whose linked widget version ≠ current
  `TC_VERSION` with a 'stale' chip (`_stale_chip`, parsed from the widget filename — no schema change),
  pinned by `StaleWidgetFlag`. So staleness is visible at a glance instead of silently opening an old
  widget. (Option b — an integration test that every deposit == `TC_VERSION` — is deferred to fixtures,
  Phase 5.)
- **Traceability is now BIDIRECTIONAL (session 12).** Every invariant **INV-1…INV-22** has an owning
  test that exists and asserts it (audited by deed, s12), and each owning test back-references its own
  `INV-N` token so a grep finds the guard from the rule and vice-versa. INV-2's owner is named precisely
  (`test_widget_contract::PanelsExist::test_producer_read_is_rendered_server_side_when_a_narrative_exists`).
- **Completeness pass (session 12).** §2 gained the data axis (stems/.als/web-mix); §5 is now
  (element × view × data-state) with a `data gate` column; §4b adds the Style layer; §6 split into
  per-element rows; §7 is a cross-page invariant grid. New invariants: INV-19 (ladder monotonicity),
  INV-20 (cross-page mode), INV-21 (no residual placeholder), INV-22 (CSS gating contract).
- **Traceability re-audit (2026-06-23, cold-session maintenance).** The post-s12 invariants INV-23…INV-34
  were added with ASPIRATIONAL "owning test (planned)" names that never matched the real test classes —
  a grep from rule→guard failed for most of them. Reconciled this pass: INV-23/24/27/28 → the real
  `tests/test_per_stem.py` classes; INV-31 → `test_fixtures::GoldenRenderFromRealData` +
  `test_per_stem::PerStemCards`; INV-32 → `test_development_mode`; INV-33/INV-34 → `test_widget_render::PlayerIsWired`.
  Genuinely UNCOVERED / not built: **INV-25** (Simple-promotion), **INV-26** (sort toggle), the
  `eval_per_stem_usefulness` regression guard, and **INV-29/INV-30** (source-file symmetry, skipped tests).
- **Two test families, only one indexed here (by design).** This matrix indexes the UI-ladder / catalog /
  per-stem / artistic layers (INV-*). The credibility + character + masking + plateau work (CR-*/G1–G21,
  SPEC §B.2–B.10) is guarded by `tests/test_credibility.py`, which this INV grid does NOT enumerate — so a
  "what's uncovered?" sweep must read BOTH the INV grid here and the G-guards in SPEC §B.

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
- **KI-6 (F4, INV-15) — RESOLVED (session 11).** `deposit()` now refuses a malformed run dir BEFORE
  any write: `looks_like_output_sentinel(track)` rejects a resolved slug that's empty / an output root
  / `*-output` / a dated stamp (the too-shallow `<base>/<stamp>` case that made the KI-1 junk row),
  raising `DepositError` (a `ValueError` subclass) so the widget copy + index write never happen. The
  build wrapper already catches it → "library deposit skipped", build still completes, catalog regen
  runs off the clean index. Tests: `test_library::DepositAtomicity` (pure sentinel + an end-to-end
  abort-writes-nothing). NOTE: this validates the SLUG, not the literal `<base>/<track>/<stamp>` depth —
  an explicit `meta.track` with any folder name is still valid (the existing round-trip test relies on
  a `run`-named dir + explicit track), which is why the rule keys on the resolved track, not the path.
- **KI-7 (F3) — RESOLVED (session 11) via INV-12 option-b.** The stale check no longer depends on the
  filename: `deposit()` stores the build's `tc_version` (read from the widget's embedded `"version"`
  payload by `library.version_from_widget`, filename-independent) and `catalog._widget_version` prefers
  it, falling back to the filename only for pre-existing entries. So a versionless or musical-versioned
  filename (e.g. `analysis_widget.html` / `…_v2.html`) on an older build is now flagged. Tests:
  `test_library::StoresBuildVersion` + `test_catalog::StaleWidgetFlag` (stored-version stale cases).
- **KI-8 (F5, INV-16) — RESOLVED (session 11).** The `.als` axis is now pinned: §5 cites INV-16 on the
  evidence row, and `test_widget_render::AlsPanelsGateOnData` asserts that with no project `D.als` is
  null and BOTH panels self-hide (`P.style.display="none"`) — in full AND quick. The gate already lived
  in the panel init JS; this stops a refactor shipping a blank Arrangement/Automation shell. (Behaviour
  is client-side hide, matching the existing render; no server-side change ⇒ no version bump.)
- **Ops (F4-prover) — RESOLVED (session 11).** A preview that fails at view time (mix gone/moved since
  the catalog was built) no longer dies silently: the play handler's `.catch` and an audio `error`
  listener both call `dead()`, which disables the button + sets a "preview unavailable" tooltip +
  styles it `.cplay.dead`. Test: `test_catalog::CatalogRowPlayer::test_dead_play_button_gives_feedback`.
  (Changes the catalog RENDER output — see the version-bump note in JOURNAL.)

- **Process:** every demo I OPEN must be a real, COMPLETE `build` render (playbook + memory). Two partial
  hand-fed renders this session read as real bugs.

## §G — Storage relocation (SPEC §G → G-INV-1…17)

Invariants added 2026-06-30 (s31). All owned by `tests/test_storage_relocation.py`.

| code | rule (1-line) | owning test / status |
|---|---|---|
| G-INV-1 | Default output base is `~/.track-coach/projects/`, NOT next to the audio file | `test_storage_relocation::RelocationDefault::test_default_base_is_home_projects` |
| G-INV-3 | `--base` flag still overrides the default; path shape `base/slug/stamp` preserved | `test_storage_relocation::RelocationDefault::test_base_flag_still_overrides` |
| G-INV-2 | One track = one slug; a track re-run reuses the same slug dir | `test_storage_relocation::CollisionDisambiguation::test_same_source_reuses_slug` |
| G-INV-2b | Two different audios that slug the same get `<slug>-2` (+warn), never co-mingled | `test_storage_relocation::CollisionDisambiguation::test_different_source_gets_slug_2` |
| G-INV-12 | First post-move run seeds shared index from old per-folder index so history stays one file | `test_storage_relocation::SeedFromOldIndex::test_old_index_entries_appear_in_new_index` |
| G-INV-14 | Catalog open-link falls back to library HTML copy when `src_run_dir` is missing on disk | `test_storage_relocation::CatalogFallback::test_open_href_falls_back_to_library_copy` |
| G-INV-16 (warn) | Catalog page shows a banner counting members with `src_run_dir` outside the output root | `test_storage_relocation::MigrateWarning::test_banner_counts_outside_root_members` |
| G-INV-11 | Run-index selector skips entries whose run dir is missing on disk; only returns existing dirs | `test_storage_relocation::DiskPresenceCheck::test_missing_run_dir_is_skipped` |
| G-INV-11 / RC-INV-9 — plaque hide | `cmd_catalog` drops absent non-self widget rows from catalog.json; self row kept even without widget | `test_storage_relocation::CmdCatalogHidesAbsentRows::test_absent_non_self_entry_is_hidden`, `::test_self_entry_kept_even_without_widget_file` |
| G-INV-11 / RC-INV-9 — plaque counts | n_runs / n_tracks in catalog.json count only visible rows after absent rows are hidden | `test_storage_relocation::CmdCatalogHidesAbsentRows::test_counts_reflect_only_visible_rows` |
| G-INV-11 / RC-INV-9 — all-absent track | A track whose every run dir is absent is dropped from catalog.json entirely | `test_storage_relocation::CmdCatalogHidesAbsentRows::test_track_with_only_absent_runs_is_dropped` |
| G-INV-16 | `migrate` dry-run prints from→to plan and moves nothing; `--apply` moves + rewrites src_run_dir | `test_storage_relocation::MigrateCommand::test_dry_run_changes_nothing`, `::test_migrate_apply_moves_and_rewrites` |

## §H — Commands, library management & cleanup (SPEC §H → H-INV-1..7, 2026-07-01 s31)

All owned by `tests/test_cleanup.py`.

| code | rule (1-line) | owning test |
|---|---|---|
| H-INV-6 (dry-run) | Bare `reset` prints plan (paths + size + recovery note) and removes nothing | `test_cleanup::ResetDryRun::test_dry_run_removes_nothing`, `::test_dry_run_prints_plan` |
| H-INV-6 (apply) | `reset --yes-wipe-everything` removes projects/ + library/ under the output root | `test_cleanup::ResetApply::test_wipe_removes_projects_and_library` |
| G-INV-7 via H-INV-6 | reset never touches files outside the configured output root | `test_cleanup::ResetApply::test_wipe_leaves_sibling_dir_untouched` |
| H-INV-6 (--base) | `reset --base DIR` wipes a custom output root | `test_cleanup::ResetApply::test_base_flag_overrides_root` |
| H-INV-3 (plan) | `gc_plan` classifies runs as orphan / keep_referenced / keep_best | `test_cleanup::GcPlan::test_orphan_classified_correctly`, `::test_empty_projects_dir_returns_empty_plan` |
| H-INV-3 (dry-run) | `gc` without --apply lists orphans, removes nothing | `test_cleanup::GcCommand::test_dry_run_removes_nothing` |
| G-INV-10 + H-INV-3 | `gc --apply` deletes orphan but keeps referenced run (library member) | `test_cleanup::GcCommand::test_apply_deletes_only_orphan` |
| G-INV-15 + H-INV-3 | `gc --apply` keeps the best-undeposited run (most result files per slug) | `test_cleanup::GcCommand::test_apply_deletes_only_orphan` |
| H-INV-5 (classify) | `ableton_tail_scan` correctly classifies safe vs has-real-runs slug dirs | `test_cleanup::AbletonTailScan::test_dry_run_reports_safe_and_real_correctly` |
| H-INV-5 (apply) | Removing safe slug dirs leaves has-real-runs slug dirs intact | `test_cleanup::AbletonTailScan::test_apply_removes_only_safe_leaves_real_runs` |
| H-INV-5 (missing) | Missing tco dir reported in scan['missing'], no crash | `test_cleanup::AbletonTailScan::test_missing_tco_dir_reported_as_missing` |
| H-INV-5 (helpers) | `_slug_dir_has_real_runs` returns True for real subdir, False for dangling-symlink-only | `test_cleanup::AbletonTailScan::test_slug_dir_has_real_runs_positive`, `::test_slug_dir_has_real_runs_negative_dangling_symlink` |
| H-INV-5 (gc cmd) | `gc --ableton-tails --scan-dir` dry-run removes nothing; --apply removes only safe dirs | `test_cleanup::GcAbletonTailsCommand::test_dry_run_does_not_remove`, `::test_apply_removes_safe_dirs` |
| H-INV-2 (pure) | `remove_plan` removes whole track, or one version by stamp/label; others untouched | `test_cleanup::RemovePlan::test_remove_whole_track`, `::test_remove_one_version_by_stamp`, `::test_remove_one_version_by_version_label`, `::test_other_tracks_untouched`, `::test_no_match_returns_empty_remove` |
| H-INV-2 (dry-run) | `remove` without --apply deletes nothing | `test_cleanup::RemoveCommand::test_dry_run_removes_nothing` |
| H-INV-2 + G-INV-11 | `remove --apply` one version: widget deleted, other versions + index entry updated atomically | `test_cleanup::RemoveCommand::test_remove_one_version_leaves_others_and_updates_index` |
| H-INV-2 (all versions) | `remove --apply` (no version): all track widgets deleted, other tracks intact | `test_cleanup::RemoveCommand::test_remove_whole_track` |
| H-INV-2 / ⟨H-2⟩ | `remove` does NOT delete the backing run dir (only library entry + widget copy) | `test_cleanup::RemoveCommand::test_remove_does_not_delete_run_dir` |
| H-INV-4 (pure) | `prune_versions_plan`: keep newest N by sha group; older groups dropped together | `test_cleanup::PruneVersionsPlan::test_keep_1_drops_two_oldest`, `::test_keep_2_drops_oldest_only`, `::test_keep_n_ge_count_drops_nothing`, `::test_negative_keep_raises`, `::test_other_tracks_handled_independently`, `::test_same_sha_entries_are_dropped_together` |
| H-INV-4 (dry-run) | `prune-versions --keep N` without --apply removes nothing | `test_cleanup::PruneVersionsCommand::test_dry_run_removes_nothing` |
| H-INV-4 (apply) | `prune-versions --keep 1 --apply`: only newest widget + index entry remain | `test_cleanup::PruneVersionsCommand::test_apply_keeps_only_newest` |
| H-INV-4 (no default) | `prune-versions` with no --keep shows current versions, makes no changes | `test_cleanup::PruneVersionsCommand::test_no_keep_flag_does_nothing` |
| H-INV-4 / ⟨H-2⟩ | `prune-versions --apply` does NOT delete backing run dirs | `test_cleanup::PruneVersionsCommand::test_apply_does_not_delete_run_dirs` |
| H-INV-6 (revised — explore) | Revised `reset --yes-wipe-everything` also removes `explore/` (references tier) | `test_cleanup::ResetRevisedCommand::test_reset_revised_wipes_explore_dir` |
| H-INV-6 (revised — keeps backups) | `reset` keeps `backups/` even when wiping all working tiers | `test_cleanup::ResetRevisedCommand::test_reset_keeps_backups_dir` |
| H-INV-6 (auto-backup) | `reset --yes-wipe-everything` auto-takes safety backup before wiping (unless `--no-backup`) | `test_cleanup::ResetRevisedCommand::test_reset_auto_creates_safety_backup` |
| H-INV-6 (abort-on-fail) | If safety backup fails, `reset` aborts and removes nothing | `test_cleanup::ResetRevisedCommand::test_reset_aborts_if_backup_fails` |
| H-INV-6 (--no-backup guard) | `--no-backup` + no existing snapshot requires `--i-understand`; aborts without it | `test_cleanup::ResetRevisedCommand::test_reset_no_backup_no_snapshot_requires_i_understand` |
| H-INV-6 (--no-backup + --i-understand) | `--no-backup --i-understand` proceeds with wipe when no snapshot exists | `test_cleanup::ResetRevisedCommand::test_reset_no_backup_with_i_understand_wipes` |
| H-INV-6 (--no-backup + existing snap) | `--no-backup` + existing snapshot proceeds without `--i-understand` | `test_cleanup::ResetRevisedCommand::test_reset_no_backup_with_existing_snapshot_does_not_require_i_understand` |
| H-INV-8 (creates snapshot) | `backup` copies `library/` + `explore/` into `backups/<stamp>/` and marks it complete | `test_cleanup::BackupCommand::test_backup_creates_snapshot_with_curated_tiers` |
| H-INV-8 (additive) | Running `backup` twice adds a second snapshot; first is untouched | `test_cleanup::BackupCommand::test_backup_additive_does_not_remove_existing_files` |
| H-INV-8 (stamp collision) | Same-second stamp collision produces `<stamp>-2` suffix | `test_cleanup::BackupCommand::test_backup_stamp_collision_gets_suffix` |
| H-INV-8 (--full) | `backup --full` adds `projects/` tier to the snapshot | `test_cleanup::BackupCommand::test_backup_full_also_copies_projects` |
| H-INV-8 (--list) | `backup --list` prints existing snapshots | `test_cleanup::BackupCommand::test_backup_list_prints_snapshots` |
| H-INV-8 (atomic) | If copy fails mid-way, no partial `_tmp_` dir remains | `test_cleanup::BackupCommand::test_backup_atomic_no_partial_on_failure` |
| H-INV-8 (gc ignores backups) | `gc_plan` scans only `projects/`; dirs under `backups/` are never classified as orphans | `test_cleanup::GcIgnoresBackups::test_gc_ignores_backups_dir` |
| H-INV-9 (dry-run default) | Bare `restore` reports plan and writes nothing (G-INV-8) | `test_cleanup::RestoreCommand::test_restore_dry_run_by_default` |
| H-INV-9 (round-trip) | `backup` then `restore --apply` reproduces original `library/` + `explore/` | `test_cleanup::RestoreCommand::test_restore_round_trip` |
| H-INV-9 (latest) | `restore latest` resolves to the most-recent valid snapshot | `test_cleanup::RestoreCommand::test_restore_latest_resolves_to_most_recent` |
| H-INV-9 (safety-backup) | `restore --apply` auto-takes safety backup before overwriting current state | `test_cleanup::RestoreCommand::test_restore_safety_backup_taken_before_overwrite` |
| H-INV-9 (--force) | `restore --force` skips the auto safety backup | `test_cleanup::RestoreCommand::test_restore_force_skips_safety_backup` |
| H-INV-9 (degraded warning) | Non-full snapshot restore prints degraded-library warning (previews silent / opens fallback / no compare) | `test_cleanup::RestoreCommand::test_restore_degraded_warning_for_non_full_snapshot` |
| H-INV-10 (dry-run default) | Bare `hard-reset` lists what would be removed (including backups) and removes nothing | `test_cleanup::HardResetCommand::test_hard_reset_dry_run_by_default` |
| H-INV-10 (single confirm) | `hard-reset --yes-wipe-everything` alone (without `--including-backups`) does not act | `test_cleanup::HardResetCommand::test_hard_reset_requires_both_confirms` |
| H-INV-10 (double confirm) | `hard-reset --yes-wipe-everything --including-backups` wipes all tiers including `backups/` | `test_cleanup::HardResetCommand::test_hard_reset_wipes_everything_incl_backups` |
| H-INV-10 (names backups) | `hard-reset` dry-run output mentions backups will be destroyed | `test_cleanup::HardResetCommand::test_hard_reset_names_backups_in_dry_run` |

## §E-s31 — Bug fixes (build item E, 2026-06-30)

Three targeted bugs fixed; each owns tests asserting the REAL rendered artifact.

| code | rule (1-line) | owning test / status |
|---|---|---|
| E-BUG-1 | **No dead commented-out refRead/webPanel block in the rendered widget.** `id="refRead"` and `id="webPanel"` each appear EXACTLY ONCE. Root cause: the HTML comment at the `__REFREAD__` slot referenced `__REFREAD__` by name, causing the template substitution to embed a full copy inside the `<!-- … -->` block. Fix: removed `__REFREAD__` from the comment text so only the live slot is substituted. | `test_widget_render::NoDeadRefReadComment::test_refread_appears_exactly_once`, `::test_webpanel_appears_exactly_once`, `::test_no_html_comment_contains_refread_id` |
| E-BUG-2 | **`char` chip has a visible legend explaining it = 'Character axis — assessed without loudness weighting'.** The chip appears on per-row items in the refRead bars (only a hover tooltip per item); a legend block at the bottom of the refRead panel provides the visible explanation. Investigation: legend was already present at `build_widget.py:2586` — no code change needed; test added as regression guard. | `test_reference_read::CharLegend::test_char_legend_explains_the_chip`, `::test_char_chip_has_tooltip` |
| E-BUG-3 | **Catalog 'leans toward' direction links navigate to the track's widget focused on the #refRead section (D-INV-28), not `href="#"`.** Fix: `_lean_cell` now accepts `widget_href`; emits `<widget_href>#refRead`; `_row` passes the resolved `href`. Fallback (no widget): `#refRead` in-page anchor (never bare `#`). | `test_catalog::DirectionLinkIsReal::test_direction_link_href_is_not_dead`, `::test_direction_link_points_to_refread_anchor`, `::test_rendered_catalog_direction_link_not_dead` |
