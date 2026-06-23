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
| INV-18 | The Evidence drawer is present and visible in EVERY view — Simple, Detailed, and quick (never CSS-hidden by `.simple`). Only its inner panels gate on data (arr/auto need `.als` — INV-16; map/rhythm/notes need stems). The Simple view hides ONLY `#stemlanes`/`#seqKey` (deep stem viz) and the non-timecoded `#recs`. | `test_widget_contract::SimpleViewGating` |
| INV-19 | **View ladder is monotonic: `quick ⊆ full-Simple ⊆ full-Detailed`.** For every element, if it is visible at a lower tier it is visible at every higher tier (a lower-but-not-higher visibility is a bug). The §5 grid is the enumerated source; the property must hold over ALL rows, so a NEW element can't re-introduce the inversion INV-3 fixed. | `test_view_ladder::LadderIsMonotonic` |
| INV-20 | **Cross-page mode agreement:** the S2 catalog mode pill (`.mode.{m}`) and the S1 widget mode badge (`.modebadge.{m}`) use the **same word** and the **same colour token** for the same mode (`full`→`--good`, `quick`→`--bright`). A run shown "Quick" in the catalog never opens a "Full" widget. | `test_catalog::CrossPageModeAgreement` |
| INV-21 | **No residual template placeholder.** The shipped S1 and S2 HTML contain zero `__[A-Z][A-Z0-9_]*__` tokens — every `__PLACEHOLDER__` the L-py template declares is substituted before the artifact reaches the producer. | `test_widget_contract::NoResidualPlaceholder`, `test_catalog::NoResidualPlaceholder` |
| INV-22 | **CSS gating contract = the ladder's mechanism.** Visibility tiers are realised by a single positive body class `simple` (and `quick`); **there is no `body.detailed` class** — Detailed is the absence of `.simple`, so it hides nothing and shows the full set. The Simple hide-set is exactly `{#stemlanes,#seqKey,#recs .rec:not([data-t])}`; quick withholds the same stem viz by DATA absence (no stems), not a CSS rule — both honour INV-19. | `test_view_ladder::CssGatingContract` |

### PROPOSED — per-stem measurements (SPEC §B.11, #2 advanced). Spec-first: NOT yet coded; each row names the test it WILL own (`bug→spec→test→code`).
| INV | Claim | Owning test (planned) |
|---|---|---|
| INV-23 | **Per-stem features are gated on significance (CR-2/CR-11).** A per-stem time-series (`result_core_<stem>.json`) is computed ONLY for `significant` stems; an empty/quiet stem yields no per-stem feature and no per-stem card. Reuses the §1 significance gate, not a fresh floor. | `test_per_stem::SignificanceGates` |
| INV-24 | **Usefulness gate = divergence from the REST of the track, not volume (CR-11, Sasha's core objection).** A per-stem card fires ONLY when the stem's curve (shape, normalized) diverges NOTABLY from the mix-MINUS-that-stem (trend-sign flip and/or low correlation past τ) — never the full mix, which contains the stem. A stem that tracks the rest → NO card. Each measure carries its own validity precondition. **Brightness is NOT a prescriptive measure at all (SPEC §B.11.1, Sasha 2026-06-22): brighter/darker-than-the-rest is not a defect the coach can judge — `PER_STEM_MEASURES = (energy, density)`; relative brightness is descriptive / a future viz.** | `test_per_stem::DivergenceGate`, `test_per_stem::BrightnessIsNotPrescriptive` |
| INV-27 | **Importance-scored, total-budgeted, diverse — no per-stem cap (Sasha 2026-06-22).** Per-stem AND composite candidates compete with existing recs in one pool ranked by importance; the widget shows the top up to a TOTAL budget near today's count, with a diversity rule so one stem can't hog the list. Cards may be COMPOSITE (combine stems / stem-vs-track), not one-per-stem; correlated measures (energy/density/loudness) collapse to one card. Importance is scored from OBJECTIVE properties — magnitude ≥ τ, persistence over a real span, specificity (named+timed), non-redundancy — so the system self-judges usefulness with NO per-track human approval; thresholds calibrated once on the 3 fixtures and frozen. The eval is a regression guard that the shown set meets those criteria, not an approval gate. | `test_per_stem::ScoreBudgetDiversity`, `eval_per_stem_usefulness` |
| INV-25 | **Placement honours the ladder.** Per-stem cards are Detailed-only by default; a card is promoted to Simple ONLY on a STRONG divergence (higher threshold). Any card visible in Simple is therefore also visible in Detailed (monotonic, INV-19). | `test_per_stem::PlacementLadder` |
| INV-26 | **Sort toggle reorders, never mutates.** The Detailed-only card-sort toggle switches the `#recs` order between by-urgency (`_rank`, default) and chronological (by `t`, matching the a/b/c cues); the SET of cards is identical in both orders — a pure presentation reorder, no add/drop. | `test_per_stem::SortToggleIsReorderOnly` |
| INV-28 | **Near-silent stems rank below louder ones (CR-11, Sasha 2026-06-22).** Each candidate's importance score is multiplied by a prominence weight (0..1) = how loud the stem is RELATIVE to the loudest significant stem, from the §1 `loud_level` (dB), NOT the self-normalized per-stem energy curve. A quiet part's card therefore sorts BELOW a loud part's at equal divergence — a soft down-rank, never a drop (it still wins a slot on strong-enough divergence). Default weight 1.0 leaves prior behaviour unchanged. | `test_per_stem::Prominence` |

### PROPOSED — source-file header symmetry & readability (Sasha 2026-06-22, NOT critical, NOT yet coded). The display path already wires both audio + .als (`build_widget.py:2276-2281`); these rows formalize the requirement + tripwire it so a future edit can't silently drop one or render an ugly long path.
| INV | Claim | Owning test (planned) |
|---|---|---|
| INV-29 | **Source-file symmetry: if the audio source is shown, the .als source is shown too.** The header `srcmeta` line lists what was analysed. Whenever an audio source is present and shown (`Audio: …`), and an `.als` project was part of the run, it MUST be shown alongside (`Project: …`) with the same treatment — never audio-only when a project exists. (`.als` absent ⇒ no Project bit, by INV-16 gating; this is about NOT dropping it when present.) | `test_widget_render::SourceFileSymmetry` |
| INV-30 | **Long source paths stay readable.** A long audio/`.als` path/filename must not overflow the line ugly: it wraps or middle-ellipsis-truncates with the full value available on hover (`title`), and the `srcmeta` row degrades gracefully on narrow widths. The current `.srcmeta{flex-wrap:wrap}` (`build_widget.py:1951`) wraps but does not truncate a single very-long token — the open work is the nice truncation/hover. | `test_widget_render::LongSourcePathReadable` |
| INV-31 | **Every advice card names where it came from (card evidence, SPEC §B.13, Sasha 2026-06-23).** Every entry in `D.recs` (the `#recs` "Start here" list — mix-level recs AND per-stem cards) carries a NON-EMPTY `based_on` line. It is plain language, never a bare metric identifier (`true_peak_db`); a single-signal (Tier-A) card may name one signal in words, a fused (Tier-B/C) card names the combination. Panel note cards (separation/rhythm/project) are out of scope this increment (F2). Machine-checkable part = non-empty + present on all `D.recs`; the plain-language/non-restating quality is authored. | `test_recs::CardEvidenceBasedOn` |
| INV-32 | **`development_mode(core)` is a deterministic, direction-carrying read of how the track develops (SPEC §B.12, Sasha 2026-06-23).** Pure helper over the four Pearson trends (`energy_/brightness_/density_/stereo_width_trend`, same [−1,1] unit). Returns each axis with `|trend| ≥ 0.12` as DOMINANT **with its sign** (louder/pulls-back, brightens/darkens, busier/thins, widens/tightens), and axes with `|trend| < 0.10` as idle-flag-eligible ONLY when ≥1 dominant axis exists. A track with NO dominant axis returns empty dominant + empty idle (the read then adds no development sentence — does not double-cover `energy_flat`). Calibrated by deed on the 3 library tracks. | `test_development_mode::DevelopmentMode` |
| INV-33 | **A seek preserves playback state — clicking a rec card / cue / chart while playing must NOT stop it (Sasha 2026-06-23, 0.8.28).** `seekTo(t)` captures `wasPlaying = !master.paused`, sets every stem's `currentTime`, paints the playhead, and if it was playing **resumes all stems together** (`auds.map(s=>s.a.play())`) — which also re-syncs them so a mid-play seek can't leave the stems phased. A seek while paused stays paused (it does not auto-start). Sits beside INV-14 (exclusive playback) as a player invariant. | `test_widget_render::PlayerIsWired::test_seek_keeps_playback_running` |
| INV-34 | **Card evidence NAVIGATION — clicking a timecoded card draws the eye to the moment on the graph (SPEC §B.13, 0.8.28).** A timecoded `#recs` card's click seeks the playhead to its moment AND scrolls `#storyPanel` into view AND briefly toggles a `pulse` class on the graph panel (a CSS attention pulse). The pulse is **CSS/DOM only — it must NOT modify the canvas draw** (the canvas is the fragile surface). The class auto-clears after the animation. Global (non-timecoded) cards don't navigate. | `test_widget_render::CardClickPulsesTheGraph` |

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
| `simple` | L-js toggle (`apply("simple")`) | `#stemlanes`, `#seqKey` → `display:none`; `#recs .rec:not([data-t])` → `display:none` |
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
