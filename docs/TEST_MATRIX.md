# track-coach — TEST MATRIX (projection of SPEC.md; the SPEC is the source of truth)

> **Two invariant namespaces — don't conflate.** `INV-n` (bare) = §B per-stem + source-file-header invariants. `D-INV-n` = the §D reference layer. They overlap in number (both reach 27–30) but are different surfaces; always write the `D-` prefix for reference rows. (A grep in s28 mis-mapped D-INV-27..30 onto the bare INV-27..30 per-stem tests — hence this note.)

This matrix is SPEC.md projected into a checkable grid. Tests trace to it. The SPEC is the source of truth; this file is the enumerable projection. Written/updated in the same change as the code or spec.

> **Matrix-local codes (legitimate, don't re-flag).** Two kinds of row id live ONLY here, by design:
> (1) **sub-variant suffixes** (`DS-INV-3a/3b`, `D-INV-29-layout/-sources/-typo`) — one SPEC invariant
> projected into several separately-testable rows; the SPEC anchor is the parent id. (2) **implementation
> contracts** (`METRE-1..7`, `INV-GATE`, `INV-CSS-*`) — node-level mechanics (a decoder table, a CSS
> alignment root-cause, the completeness-gate mechanism itself) that SPEC covers as behaviour prose, not
> per-value codes. An audit finding "matrix id absent from SPEC" for these two kinds is EXPECTED.
> **Seam PAID (s58, 2026-07-05):** the bare `INV-nn` codes the s57 pass flagged (32, 36–40, 42–44, 47 —
> plus 35, same §B.14 list, missed by that scan) now carry trailing anchors in SPEC prose, and
> `test_traceability::test_every_active_bare_matrix_invariant_appears_in_spec` enforces the reverse
> direction (matrix→SPEC) from here on. The pre-anchor-convention legacy rows (INV-1…31 minus the
> already-anchored) are baselined in that test as acknowledged debt — pay one down by anchoring it in
> SPEC and pruning the baseline.

> **Bug-found protocol:** bug → ① fix/clarify the matrix cell or invariant → ② failing test, proven
> red-on-bug → ③ fix code. Code chases the matrix.
> **Change protocol:** add/change/remove any element ⇒ update this doc in the same change + decide which
> test(s) change. No partial/hybrid tests.

---

## Contents

- [§1 — Entities & glossary](#1--entities--glossary)
- [§2 — States & transitions](#2--states--transitions)
- [§3 — Invariants](#3--invariants-hold-in-every-state-each-owns-a-test)
- [§4 — Surfaces & layers](#4--surfaces--layers)
- [§5 — Widget element grid](#5--s1-widget-element-grid-show-per-view-state--data-state--how--layer)
- [§6 — Catalog element grid](#6--s2-catalog-element-grid)
- [§7 — Cross-page correspondences](#7--cross-page-correspondences-same-run-two-surfaces--each-row-is-an-invariant)
- [§E — Run completeness](#e--run-completeness--missing-measurements-spec-e--rc-inv-112)
- [§D10F — Catalog similarity columns](#d10f--catalog-similarity-columns-spec-d10--f--d-inv-2125-f-inv-18)
- [§8 — Coverage status](#8--coverage-status)
- [§9 — Known issues](#9--known-issues)
- [§G — Storage relocation](#g--storage-relocation-spec-g--g-inv-120)
- [§H — Commands, library & cleanup](#h--commands-library-management--cleanup-spec-h--h-inv-17)
- [§E-s31 — Bug fixes](#e-s31--bug-fixes-build-item-e)
- [§A-metre — Arrangement metre changes](#a-metre--arrangement-metre-changes-spec-a-metre-changes)
- [§I — Visual design system](#i--visual-design-system-spec-i--ds-inv-114)

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
  Drives: player lanes, per-stem player, stem-map / rhythm / notes, empty-stem caveat.
- **.als** {none, present} — drives ONLY the Evidence drawer's arrangement + automation panels.
- **web mix** {none, present} — drives the S1 single-track player (quick) and the S2 row preview.

A cell in §5 is `(element × view-state × data-state)`; an element that doesn't depend on a data-state
is constant across it.

Transitions:
- **toggle** (full only): S→D reveals the deep layer (player lanes, Evidence drawer, global recs);
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
| INV-10 | S2 column count is fixed (play/scrub live inside the existing track/signature cells) ⇒ responsive column-shedding is stable. | `test_catalog::ResponsiveTable`; **browser-level** `test_headless_render::CatalogPageResponsive` (computed `display:none` of cols 9–12 below 1100px + col 3 below 880px, real viewport widths) |
| INV-11 | The in-widget cross-version panel (`#catalog`) carries exactly the build's catalog and hides iff there are no tracks; empty/orphan build ⇒ hidden, not a false panel. | `test_widget_render::CrossVersionPanelData` |
| INV-12 | A catalog row whose linked widget is built on an OLDER ANALYSIS version (`TC_ANALYSIS_VERSION`) is flagged 'stale'; the tool version (`TC_VERSION`) is the build stamp only and takes no part in the verdict, so an infra/render release never flags a row. The analysis version is stored at deposit (`tc_analysis_version`, from the widget payload). A widget deposited before stamping carries only its tool version and is judged against `TC_ANALYSIS_BASELINE_TCV` (preserving today's verdict); unknown by every path ⇒ not flagged (don't cry wolf). | `test_catalog::StaleWidgetFlag`, `test_library::StoresBuildVersion` |
| INV-ANALYSIS-RERENDER | Raising `TC_ANALYSIS_VERSION` moves `TC_ANALYSIS_BASELINE_TCV` to the releasing tool version in lockstep, and every deposited widget is re-rendered (re-stamped) before that release; a render-only or infra release leaves the analysis version untouched. | `test_catalog::StaleWidgetFlag::test_version_constants_stay_consistent` |
| INV-13 | `_fmt_date` formats `YYYY-MM-DD_HHMM` and never crashes on odd/multi-underscore stamps. | `test_catalog::FmtDate` |
| INV-14 | At most ONE catalog preview plays at a time — starting a row stops any other (one shared `cur` + an unconditional `stop()` before `a.play()`). | `test_catalog::CatalogRowPlayer` |
| INV-15 | A deposit either targets the run's real track slug or aborts (raises `DepositError`) BEFORE any write — no partial widget copy / junk index entry. Junk slug = output root, `*-output`, or a dated stamp. | `test_library::DepositAtomicity` |
| INV-16 | Arrangement/automation panels render iff `.als` data exists — never as empty shells (no project ⇒ `D.als` null ⇒ each panel self-hides). Same gate in full and quick. | `test_widget_render::AlsPanelsGateOnData` |
| INV-17 | The catalog is a LOCAL index: BOTH `open→` (`_open_href`) and play (`_mix_uri_for`) resolve to an absolute `file://` rooted in the ORIGINAL run dir. Portability scope = local filesystem, NOT GitHub Pages. | `test_catalog::CatalogIsLocalIndex` |
| INV-18 | The Evidence drawer is present and visible in EVERY view — Simple, Detailed, and quick (never CSS-hidden by `.simple`). Only its inner panels gate on data (arr/auto need `.als` — INV-16; map/rhythm/notes need stems). The Simple view hides ONLY `#stemlanes`/`#seqKey` (deep stem viz), the non-timecoded `#recs`, and `#refPanel` (§D.10 the merged reference panel, Detailed-only — its nested `#refRead`/`#webPanel` hidden with it, D-INV-36). | `test_widget_contract::SimpleViewGating`; browser-level `test_headless_render::SimpleViewGatingBrowser::test_stem_viz_hidden_in_simple_visible_in_detailed`, `test_headless_render::SimpleViewGatingBrowser::test_ref_panels_hidden_in_simple_visible_in_detailed` |
| INV-19 | **View ladder is monotonic: `quick ⊆ full-Simple ⊆ full-Detailed`.** For every element, if it is visible at a lower tier it is visible at every higher tier (a lower-but-not-higher visibility is a bug). The §5 grid is the enumerated source; the property must hold over ALL rows, so a NEW element can't re-introduce the inversion INV-3 fixed. | `test_view_ladder::LadderIsMonotonic` |
| INV-20 | **Cross-page mode agreement:** the S2 catalog mode pill (`.mode.{m}`) and the S1 widget mode badge (`.modebadge.{m}`) use the **same word** and the **same colour token** for the same mode (`full`→`--good`, `quick`→`--bright`). A run shown "Quick" in the catalog never opens a "Full" widget. | `test_catalog::CrossPageModeAgreement` |
| INV-21 | **No residual template placeholder.** The shipped S1 and S2 HTML contain zero `__[A-Z][A-Z0-9_]*__` tokens — every `__PLACEHOLDER__` the L-py template declares is substituted before the artifact reaches the producer. | `test_widget_contract::NoResidualPlaceholder`, `test_catalog::NoResidualPlaceholder` |
| INV-22 | **CSS gating contract = the ladder's mechanism.** Visibility tiers are realised by a single positive body class `simple` (and `quick`); **there is no `body.detailed` class** — Detailed is the absence of `.simple`, so it hides nothing and shows the full set. The Simple hide-set is exactly `{#stemlanes,#seqKey,#recs .rec:not([data-t]),#refPanel,#recSort}` (the merged reference container — nested `#refRead`/`#webPanel` hide with it, D-INV-36; `#recSort` = the Detailed-only card-order toggle, INV-26); quick withholds the same stem viz by DATA absence (no stems), not a CSS rule — both honour INV-19. | `test_view_ladder::CssGatingContract`; browser-level `test_headless_render::SimpleViewGatingBrowser::test_stem_viz_hidden_in_simple_visible_in_detailed`, `test_headless_render::SimpleViewGatingBrowser::test_ref_panels_hidden_in_simple_visible_in_detailed` |
| INV-CSS-catrun | **`.catrun` uses `align-items:center` (not `baseline`)** so the right-hand plaque label ("you are here" / open link) sits vertically centred even when the verdict text wraps. `align-items:baseline` was the root cause of both off-centre labels and uneven row gaps. | `test_widget_contract::CatalogPlaqueCSSContract` |
| INV-GATE | **Whole-artifact completeness gate (s46, 2026-07-03).** A full widget render must have EVERY user-facing panel POPULATED and NON-EMPTY. 20 gate assertions across every user-facing surface: (1) header title non-empty; (2) vitals row — all 9 slots (Tempo, Key, Length, Loudness, True peak, Dynamics, Stereo, Phase, Metre when als present) — non-empty AND not placeholder "—" (Phase = L/R correlation, added to the net s50d — Fable found it outside the gate); (3) track-story arc canvas with non-zero dims AND drawn pixels; (4) player lanes — all stems in `window.__ns_state`, lane canvas height > 0; (5) recs — ≥1 card with non-empty title AND body; (6) producer's read (#readBody) > 40 chars, not whitespace-only, with authored h3 headings in full render; (7) tonal balance panel visible + canvas with drawn pixels; (8) evidence sub-panels — #evidence container present; #arrPanel, #autoPanel, #mapPanel, #rhyPanel, #notePanel each non-empty when backing data is present; (9) catalog backpointer — #backLink not hidden, href is a real `file://` URI; (10) footer — TC_VERSION + date in #srcmeta. **Extended (s46 consolidation):** (12) #sub BPM line + #srcmeta names BOTH audio AND .als file; (13) #modeBadge matches run mode; (14) #viewToggle has 2 buttons, exactly 1 active; (15) player audio count == lane count, all src non-empty; (16) play controls (#playBtn, #playTime, #seqKey, #playNote) non-empty; (17) timeline cue letters (data-let) on timecoded cards; (18) rec sub-parts: 'Based on' + '→ Try' + #recLegend non-empty; (19) #catBody ≥1 row with self row; (20) evidence readouts (#arrReadout, #autoReadout, #noteReadout, #mapNotes, #rhySep, #mapRows, #rhyRows) non-empty; (21) INV-45 auto-mute; **(22) #refRead (nested in #refPanel since the D-INV-36 merge) populated (F1, s54) — the centroid read renders with per-facet bars, NOT "No similar tracks", in a build that HAS reference directions (fixture `_build_full_widget_with_refs`: a run_dir fingerprint leaning toward the defined directions); (23) #webPanel (nested) populated — the web descriptor body is non-empty for the nearest direction; (24) #refPanel container populated — the one merged reference panel holds the shared `.reftab` selector (when ≥2 leans) and BOTH nested open disclosures in order (centroid read, then web notes).** Gate PROVES it catches emptiness: partial render (no als/notes/narrative) fails the assertions for those missing surfaces; the negative test test_22_ref_read_absent_on_plain_full (owning-test cell) proves the `when-reference` condition is real (no run_dir ⇒ #refPanel and its nested disclosures absent). CONVERGENCE (INV-46): DOM-scan + USER_SURFACES registry makes the gate self-closing. Level = **browser** (rendered-presence facts invisible to string tests). Fixture: SYNTHETIC. | `test_completeness_gate::WholeArtifactCompletenessGate`; `test_completeness_gate::WholeArtifactCompletenessGate::test_22_ref_read_populated`; `test_completeness_gate::WholeArtifactCompletenessGate::test_23_web_panel_populated`; `test_completeness_gate::WholeArtifactCompletenessGate::test_22_ref_read_absent_on_plain_full` |
| INV-47 | **Completeness composed across the render-config AXIS + no empty-open collapsible (A0, Fable audit 2026-07-03).** The whole-artifact gate (INV-GATE) builds only `mode="full"` fixtures, so a bug live only in another config passed green — Fable found a real one: a QUICK (mix-only) widget's `#evidence` collapsible was visible but opened to NOTHING (its 5 sub-panels self-hide on no data, but the outer container did not; 71px = summary + padding only). FIX: `build_widget.py` hides `#evidence` in QUICK mode — a quick run structurally has no stems/.als, hence no evidence, so the container is never shown empty; a full run always carries evidence, so its always-visible contract (INV-GATE) is untouched (verified: the full-widget gate + the headless view-ladder tests stay green). GUARD: a browser-level scan across {quick, full-Simple, full-Detailed} asserts **no VISIBLE, open `<details id>` has zero visible children besides its summary** (height lies — panel padding keeps a content-less container ~34px; the test is structural, not by height). Proven red-on-bug: the scan flagged `['evidence']` on the quick fixture before the fix, clean after. Level = **browser**. Fixture: SYNTHETIC (new `_build_quick_widget`). | `test_completeness_gate::NoEmptyVisibleCollapsibleAcrossConfigs` (test_quick / test_full_simple / test_full_detailed) |
| INV-51 | **The absence-acknowledgment class rule (SPEC §E.3, 2026-07-14 design-review fold).** One rule governs every absence-handling surface: a signal a rung never promises stays silent, while a signal the rung promises but a track leaves empty renders a plain acknowledgment in its place. It is a naming of the class the three shipped instances already obey — no dedicated code, so it is PROVEN by its instances rather than a row of its own: the near-silent stem lane acknowledges (INV-42), the reference-panel stub acknowledges and now names the missing signals (D-INV-36, `test_reference_read::ReferenceReadHeader::test_no_shared_facets_stub_names_missing_signals`), and the evidence drawer self-hides where stems/.als are never promised (INV-47); RC-INV-7 is this rule read along the run-mode axis. A future absence-handling surface inherits the rule and states which of silence or acknowledgment an absent signal earns. Level = **derived (documentation)**. | covered-by `test_headless_render::OmittedStemsAcknowledged` (INV-42) · `test_reference_read::ReferenceReadHeader::test_no_shared_facets_stub_names_missing_signals` (D-INV-36) · `test_completeness_gate::NoEmptyVisibleCollapsibleAcrossConfigs` (INV-47) |
| INV-45 | **Near-silent stem's lane auto-starts MUTED on first load (SPEC CR-2, APPROVED 2026-07-03).** A stem below `STEM_EMPTY_FLOOR_DB` (−55 dB broadband) is added to `D.stem.omitted`; the player JS (grep `startMuted` / `_nsOmit` in `build_widget.py`) sets `a.muted=true` for that stem's `<audio>` element on initial load, and the lane carries a `nearSilent` flag so the mute survives a view round-trip (INV-40 composition). This is approved behaviour: the lane carries no real content, so auto-muting avoids surprise silence on play. The lane remains VISIBLE and IDENTIFIED per CR-2 (visibility unaffected). The M/S buttons still work — the mute is initial-state only. Verified: `window.__ns_state[i].mute = true` for the near-silent stem, `false` for significant stems. Level = **browser**. | `test_completeness_gate::WholeArtifactCompletenessGate::test_21_auto_mute_approved_behavior` |
| INV-46 | **Surface registry + DOM-scan convergence (s46, 2026-07-03).** `USER_SURFACES` is the single source of truth for every user-facing panel. (a) Every `<details class="tc-panel" id="…">` in a rendered full widget must be in `USER_SURFACES` — the DOM-scan test fails naming any unregistered id. (b) Every non-DEFERRED registry entry must have a real gate test method — the registry-gated check fails if a method is missing. Together: `rendered ⊆ registry ⊆ gated ⟹ rendered ⊆ gated` (100% by construction). PROOF: `test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_probe_scan_detects_unregistered` injects a `__probe_unregistered` panel and verifies the scan catches it, then `test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_all_rendered_panels_are_registered` verifies the real widget is clean. `refPanel` (the merged container, D-INV-36) + its nested `refRead` / `webPanel` are the descriptive §D surfaces — registered like the Evidence sub-panels (nested tc-panels carry their own entries); condition `when-reference`, SHIP-1.0 per SPEC §D.10.1 scope-split; gated by the refs-fixture tests (F1, s54), no longer `DEFERRED`/`gated_by:None`. Only the aim/re-flavouring surfaces (no input in 1.0, SPEC §D.6) carry no registry entry. Level = **browser**. | `test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_probe_scan_detects_unregistered`; `test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_all_rendered_panels_are_registered`; `test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_every_registry_entry_has_gate_test` |

### Per-stem measurements   [SPEC §B.11]

Coded + tested in `tests/test_per_stem.py`, EXCEPT INV-25 (feature not built — still planned; INV-26 the sort toggle is now built, see `tests/test_rec_sort.py`). Owning tests reconciled to the REAL class names (the earlier "planned" names — `SignificanceGates`/`DivergenceGate`/`ScoreBudgetDiversity`/`PlacementLadder`/`SortToggleIsReorderOnly`/`eval_per_stem_usefulness` — never existed under those names; this is the fix).

| INV | Claim | Owning test (real, audited 2026-06-23) |
|---|---|---|
| INV-23 | **Per-stem features are gated on significance (CR-2/CR-11).** A per-stem time-series (`result_core_<stem>.json`) is computed ONLY for `significant` stems; an empty/quiet stem yields no per-stem feature and no per-stem card. Reuses the §1 significance gate, not a fresh floor. | `test_per_stem::DivergenceCandidates`, `PerStemCards`; the `significant_stems` gate itself in `test_credibility` (G1–G7) |
| INV-42 | **Omitted stems are ACKNOWLEDGED, not silently dropped (SPEC CR-2, docs/SPEC.md §1; regression fixed 2026-07-02).** htdemucs_6s always emits 6 stems; near-silent ones (below `STEM_EMPTY_FLOOR_DB`) are dropped from the heavy per-stem viz (INV-23) BUT the stem panel MUST name them — visible in the `#seqKey` legend as identified labels e.g. "stems low-mid (near-silent), mid (near-silent) omitted — too little material to read" — and shown as muted, labelled rows in the player lane grid — so a missing lane reads as a decision, not a bug. Detailed-only (the stem viz lives there). INV-23 tests the drop; **this tests the acknowledgment RENDERS** (the reverse-verify gate a string test + Fable missed). Level = **browser**. | `test_headless_render::OmittedStemsAcknowledged` |
| INV-44 | **Near-silent stems carry IDENTIFIED labels (INV-STEMNAME-NEARSILENT-ID, s46, SPEC §B.7 + CR-2).** Every near-silent stem's display name must be identified: the mapped .als project-track name when `stemmap` has a `clear` verdict, else a frequency-band word ("low" / "low-mid" / "mid" / "mid-high" / "high") derived from the stem's spectral centroid (5-way split with `_ns_band_from_centroid`) — always suffixed " (near-silent)". NEVER bare "near-silent". NEVER the raw Demucs family word. Two near-silent stems in the same widget may NOT have byte-identical labels (distinctness: collision → trailing " 1", " 2"). Near-silent stems APPEAR as muted, labelled rows in the player lane grid (CR-2 visibility — un-hidden in s46 after s45 regression). Near-silent stems are NOT placed in rhythm tiles. The omitted-stems note in `#seqKey` names each stem by its identified label ("stems X, Y omitted — too little material to read"). The stem-vs-project panel `fam_display["other"]` reads "everything else", not "the rest". The `play_note` intro has no nested `))` parenthetical. The reference bars carry a `.refread-axis` element with "lower · them · higher". Level = **browser** (these are rendered-text and visibility facts invisible to string tests). | `test_headless_render::NearSilentStemIdentified` (test_stem_display_has_identified_nearsilent_labels / test_nearsilent_labels_are_distinct / test_nearsilent_stems_appear_as_muted_lanes / test_nearsilent_stems_not_in_rhythm_tiles); `test_headless_render::NoRawStemNameOnAnySurface` (test_no_raw_stem_in_omitted_note / test_everything_else_not_the_rest_in_fam_display); `test_headless_render::WordingInvariants` (test_play_note_no_nested_parens / test_reference_bars_have_axis_labels) |
| INV-43 | **No dev-internal label on the catalog surface (turnkey, 2026-07-01).** The catalog page (S2) must never show a raw track/stamp folder-slug as VISIBLE text: the row label is the human title (`e.title`, humanized fallback), the old `.trk` raw-slug subtitle is REMOVED, and a run dir that broke the `<track>/<stamp>` convention (stamp = a folder-slug e.g. `Total_Reboot_Wobble_Drift_v0.6.2`) shows `—` in the Date column via `_display_date`, never the slug. `_fmt_date`'s pure passthrough (INV-13) is untouched — the guard is caller-side. Level = string (catalog-page render text); a browser-harness conversion lands with the catalog-page gate (Movement: catalog browser gate). | `test_catalog::CatalogNoDevSlugOnSurface` (methods test_is_date_shaped / test_display_date_slug_stamp_falls_back / test_render_shows_title_not_raw_slug) |
| INV-24 | **Usefulness gate = divergence from the REST of the track, not volume (CR-11, a core usefulness objection).** A per-stem card fires ONLY when the stem's curve (shape, normalized) diverges NOTABLY from the mix-MINUS-that-stem (trend-sign flip and/or low correlation past τ) — never the full mix, which contains the stem. A stem that tracks the rest → NO card. Each measure carries its own validity precondition. **Brightness is NOT a prescriptive measure at all (SPEC §B.11.1, 2026-06-22): brighter/darker-than-the-rest is not a defect the coach can judge — `PER_STEM_MEASURES = (energy, density)`; relative brightness is descriptive / a future viz.** | `test_per_stem::Divergence`, `DivergenceCandidates`, `BrightnessIsNotPrescriptive` |
| INV-27 | **Importance-scored, total-budgeted, diverse — no per-stem cap (2026-06-22).** Per-stem AND composite candidates compete with existing recs in one pool ranked by importance; the widget shows the top up to a TOTAL budget near today's count, with a diversity rule so one stem can't hog the list. Cards may be COMPOSITE (combine stems / stem-vs-track), not one-per-stem; correlated measures (energy/density/loudness) collapse to one card. Importance is scored from OBJECTIVE properties — magnitude ≥ τ, persistence over a real span, specificity (named+timed), non-redundancy — so the system self-judges usefulness with NO per-track human approval; thresholds calibrated once on the 3 fixtures and frozen. The eval is a regression guard that the shown set meets those criteria, not an approval gate. | `test_per_stem::CandidateScore`, `BudgetAndDiversity`, `CompositeCandidates`, `CollapseCorrelated` (the `eval_per_stem_usefulness` regression guard is NOT built — backlog) |
| INV-25 | **Placement honours the ladder.** Per-stem cards are Detailed-only by default; a card is promoted to Simple ONLY on a STRONG divergence (higher threshold). Any card visible in Simple is therefore also visible in Detailed (monotonic, INV-19). | **PLANNED — not built.** Per-stem cards are Detailed-only today; the Simple-promotion threshold is still ⟨DECIDE⟩. No test yet. |
| INV-26 | **Sort toggle reorders, never mutates.** The Detailed-only card-sort toggle switches the `#recs` order between by-urgency (`_rank`, default) and chronological (by `t`, matching the a/b/c cues); the SET of cards is identical in both orders — a pure presentation reorder, no add/drop — and it moves the EXISTING nodes (a card keeps its INV-48 click nav). The pure order helper `recSortOrder` is the shipped function (whole-track cards last, ties stable); the control is Detailed-only and hides when there is nothing to reorder. Levels: L0 (node) + DOM-string + browser. | `test_rec_sort::RecSortLogic::test_time_ascending_globals_last` (node), `test_rec_sort::RecSortShipped::test_detailed_only_gate` (control + gate + blocks ship), `test_rec_sort::RecSortReorderInChrome::test_control_visible_in_detailed`, `test_rec_sort::RecSortReorderInChrome::test_by_time_sorts_ascending` (headless) |
| INV-28 | **Near-silent stems rank below louder ones (CR-11, 2026-06-22).** Each candidate's importance score is multiplied by a prominence weight (0..1) = how loud the stem is RELATIVE to the loudest significant stem, from the §1 `loud_level` (dB), NOT the self-normalized per-stem energy curve. A quiet part's card therefore sorts BELOW a loud part's at equal divergence — a soft down-rank, never a drop (it still wins a slot on strong-enough divergence). Default weight 1.0 leaves prior behaviour unchanged. | `test_per_stem::Prominence` |

### PLANNED (not built) — source-file header symmetry & readability

Not critical. The display path already wires both audio + .als (`build_widget.py:2276-2281`); these rows formalize the requirement + tripwire it. Both owning tests EXIST but are `@unittest.skip`ped (the suite's 2 skips) until implemented.

| INV | Claim | Owning test (skipped — planned) |
|---|---|---|
| INV-29 | **Source-file symmetry: if the audio source is shown, the .als source is shown too.** The header `srcmeta` line lists what was analysed. Whenever an audio source is present and shown (`Audio: …`), and an `.als` project was part of the run, it MUST be shown alongside (`Project: …`) with the same treatment — never audio-only when a project exists. (`.als` absent ⇒ no Project bit, by INV-16 gating; this is about NOT dropping it when present.) | `test_widget_render::SourceFileHeaderSymmetryAndReadability::test_source_file_symmetry` |
| INV-30 | **Long source paths stay readable.** A long audio/`.als` path/filename must not overflow the line ugly: it ellipsis-truncates with the full value available on hover (`title`), and the `srcmeta` row still flex-wraps between bits on narrow widths. The `.srcmeta b` cell caps at `min(46ch,100%)` with `overflow:hidden;text-overflow:ellipsis;white-space:nowrap` and each filename carries a `title` hover (`build_widget.py`). | `test_widget_render::SourceFileHeaderSymmetryAndReadability::test_long_source_path_readable` |

### Card evidence, artistic read & player invariants   [SPEC §B.12–§B.13]

Shipped; coded + tested. Owning tests reconciled to real names.

| INV | Claim | Owning test (real, audited 2026-06-23) |
|---|---|---|
| INV-31 | **Every advice card names where it came from (card evidence, SPEC §B.13, 2026-06-23).** Every entry in `D.recs` (the `#recs` "Start here" list — mix-level recs AND per-stem cards) carries a NON-EMPTY `based_on` line. It is plain language, never a bare metric identifier (`true_peak_db`); a single-signal (Tier-A) card may name one signal in words, a fused (Tier-B/C) card names the combination. Panel note cards (separation/rhythm/project) are out of scope this increment (F2). Machine-checkable part = non-empty + present on all `D.recs`; the plain-language/non-restating quality is authored. The based-on names the RESULT + a simple unit, never the measurement METHOD (`4× oversampled`, `peak-to-RMS`, `self-similarity`) — 2026-07-02, guarded. | `test_fixtures::GoldenRenderFromRealData::test_every_card_carries_a_based_on_line`, `::test_based_on_avoids_technical_method_jargon`, `test_per_stem::PerStemCards` |
| INV-32 | **`development_mode(core)` is a deterministic, direction-carrying read of how the track develops (SPEC §B.12, 2026-06-23).** Pure helper over the four Pearson trends (`energy_/brightness_/density_/stereo_width_trend`, same [−1,1] unit). Returns each axis with `|trend| ≥ 0.12` as DOMINANT **with its sign** (louder/pulls-back, brightens/darkens, busier/thins, widens/tightens), and axes with `|trend| < 0.10` as idle-flag-eligible ONLY when ≥1 dominant axis exists. A track with NO dominant axis returns empty dominant + empty idle (the read then adds no development sentence — does not double-cover `energy_flat`). Calibrated by deed on the 3 library tracks. | `test_development_mode::DevelopmentMode` |
| INV-33 | **A seek preserves playback state — clicking a rec card / cue / chart while playing must NOT stop it (2026-06-23, 0.8.28).** `seekTo(t)` captures `wasPlaying = !master.paused`, sets every stem's `currentTime`, paints the playhead, and if it was playing **resumes all stems together** (`auds.map(s=>s.a.play())`) — which also re-syncs them so a mid-play seek can't leave the stems phased. A seek while paused stays paused (it does not auto-start). Sits beside INV-14 (exclusive playback) as a player invariant. | `test_widget_render::PlayerIsWired::test_seek_keeps_playback_running` |
| INV-34 | **The attention pulse is CSS/DOM only — it must NOT modify the canvas draw (SPEC §B.13, 0.8.28; target generalised by INV-48, s61).** A card click toggles a `pulse` class on the target PANEL (a CSS attention pulse); the class auto-clears after the animation; the canvas is the fragile surface and is never touched. One shared pulse style serves every target (`#storyPanel`-only CSS was the 0.8.28 shape; prover CN-1). WHERE the click navigates is INV-48's law below. | `test_widget_render::PlayerIsWired::test_card_click_pulses_the_graph` |
| INV-48a | **Every card carries its evidence target (SPEC §B.13, s61).** Every `D.recs` entry ships a non-empty `ev` naming the panel its based-on evidence renders in, drawn from the §B.13 map (`storyPanel`/`tonalPanel`/`vitals`/`rhyPanel`/`autoPanel`); every rec key with a `REC_BASED` entry has a `REC_TARGET` entry (same completeness rule as based-on, prover CN-3); per-stem cards carry `storyPanel`. Level: unit + golden real-data fixture. | `test_credibility::RecTargetCompleteness`, `test_fixtures::GoldenRenderFromRealData::test_every_card_carries_an_evidence_target` |
| INV-48b | **Click = seek (when timecoded) + reveal + pulse the TARGET (SPEC §B.13, s61).** In a real browser load: clicking the tonal-resonance card scrolls `#tonalPanel` into view and fires the `pulse` animation on IT (not on `#storyPanel`); a timecoded card still seeks first (INV-33 fence holds via the full suite). Wiring is scoped to `#recs .rec` — the map-panel note cards reuse the `.rec` class and must stay inert (prover CN-8). Level: **L3-BROWSER**. | `test_headless_render::CardEvidenceNav::test_click_pulses_the_cards_own_target`, `::test_map_panel_note_cards_stay_inert` |
| INV-48c | **A collapsed ancestor opens on the way (SPEC §B.13, s61).** Clicking a card whose target lives inside the closed "Evidence & detail" drawer (`#autoPanel`/`#rhyPanel`) sets `open` on every closed ancestor `<details>`; after the click the target panel is VISIBLE with non-zero height (the drawer's toggle listeners must have resized the canvases — prover CN-2); nothing is persisted. Level: **L3-BROWSER**. | `test_headless_render::CardEvidenceNav::test_collapsed_drawer_opens_and_target_has_height` |
| INV-48d | **A missing target degrades to today's behaviour (SPEC §B.13, s61).** In a build whose run lacks the target panel: a timecoded card keeps the 0.8.28 behaviour (seek + `#storyPanel` scroll + pulse); a global card renders NOT clickable — no pointer cursor, no jump title, no dead click. Level: **L3-BROWSER** on a fixture without the gated panels. | `test_headless_render::CardEvidenceNav::test_missing_target_falls_back_and_global_goes_inert` |
| INV-48e | **Global cards become clickable where their target is present (SPEC §B.13, s61).** A whole-track card with a present target carries `cursor:pointer` + a jump `title` (computed style, real load) and navigates on click without seeking; Simple never shows it (INV-22's existing hide row covers that side). Level: **L3-BROWSER**. | `test_headless_render::CardEvidenceNav::test_global_card_clickable_with_pointer_and_title` |
| INV-49a | **A cue's click zone is its whole column (SPEC §B.13 "the arc answers back", 2026-07-05 late).** In a real browser load, hovering the arc canvas DEEP below the triangle band (y ≈ 60% of the canvas) within the snap radius of a cue's moment turns the cursor to `pointer` and shows the cue tooltip (`#ctip` contains "click to read below"); the zone is found by SCANNING the deep horizontal for pointer segments, not by re-computing layout constants. Level: **L3-BROWSER**. | `test_headless_render::ArcBackpointer::test_cue_column_is_hoverable_full_height` |
| INV-49b | **Clicking the column does exactly what the triangle does (SPEC §B.13, 2026-07-05 late).** A click at the deep-y centre of a pointer segment seeks to the cue's moment (stubbed `__seek` fires) and lights the cue's card — a `#recs .rec[data-let]` gains the `flash` class and is scrolled into view. One hit-test serves band and column (the band case is the same code path). Level: **L3-BROWSER**. | `test_headless_render::ArcBackpointer::test_column_click_seeks_and_lights_the_card` |
| INV-49c | **Away from every cue the arc keeps plain click=seek (SPEC §B.13, 2026-07-05 late).** A deep-y click in a gap between pointer segments seeks (stubbed `__seek` fires) but lights NO card (no `.rec.flash`, no rec scrolled); a build with no timecoded cards has no pointer segments at deep y at all. Level: **L3-BROWSER**. | `test_headless_render::ArcBackpointer::test_click_between_cues_stays_plain_seek`, `::test_no_timecoded_cards_no_columns` |
| INV-49d | **The backpointer persists nothing (SPEC §B.13, 2026-07-05 late).** After column hover + click, `localStorage` holds no new key (`tc_view` unchanged) and the URL is unchanged. Level: **L3-BROWSER** (asserted inside the click probe). | `test_headless_render::ArcBackpointer::test_column_click_seeks_and_lights_the_card` (store/url asserts) |
| INV-50a | **Swing speaks in feel, on a named grid (SPEC §B.16, 2026-07-05 late).** A rendered widget whose detail carries `swing_global_ms` > 30 shows the swing card body with the tight-grid window ("25–30 ms") AND the feel phrase matching the measured band — gentle push [30,60) / hard human swing [60,90) / broken-beat (≥90); the canned "sounds human rather than machine" line is gone. Level: **DOM-text on the rendered widget** (three renders, one per band). | `test_widget_render::CardScalePhrases::test_swing_feel_matches_band` |
| INV-50b | **Dynamic range stands on a ladder (SPEC §B.16, 2026-07-05 late).** A rendered widget with DR < 6 shows the squashed card body carrying the ladder sentence ("6–8", "10 and up"). Level: **DOM-text on the rendered widget**. | `test_widget_render::CardScalePhrases::test_squashed_ladder_present` |
| INV-50c | **The tonal offset is translated to the ear (SPEC §B.16, 2026-07-05 late).** The tonal-resonance card body carries the perceived-loudness phrase matching the fixture's deviation: +9 → "about twice as loud", +6 → "half again as loud", +4 → "clearly audible bump"; mirrored wording for dips (−9 → "about half as loud", −6 → "noticeably recessed", −4 → "clearly audible dip"); the measured dB stays in the sentence beside the phrase. Level: **DOM-text on the rendered widget** (six renders, one per step/sign). | `test_widget_render::CardScalePhrases::test_tonal_phrase_matches_magnitude_and_sign` |

### Player state machine   [SPEC §B.14]

Coded + tested by EXECUTING the real shipped JS in node (not a Python mirror). The pure helpers (`pgains`/`toggleStem`/`seekResult`) are extracted between `__PLAYER_LOGIC_START__`/`__PLAYER_LOGIC_END__` markers in the rendered widget; the test pulls that block out of the HTML, runs it in node, and asserts the combinations the old string-match tests never reached.

| INV | Claim | Owning test (real) |
|---|---|---|
| INV-35 | **One mode at a time.** After ANY sequence of mute/solo toggles via `toggleStem`, the player is never in `(some stem muted) AND (some stem soloed)` at once — muting clears solos, soloing clears mutes (2026-06-21). | `test_player_logic::PlayerStateMachine::test_one_mode_at_a_time` |
| INV-36 | **Solo resolves gains.** When any stem is soloed, `pgains` makes the audible set EXACTLY the soloed stems (every non-soloed stem muted), regardless of individual mute flags. | `test_player_logic::PlayerStateMachine::test_solo_resolves_gains` |
| INV-37 | **Mute resolves gains.** When no stem is soloed, `pgains` makes audible(stem) = `!stem.mute`. | `test_player_logic::PlayerStateMachine::test_mute_resolves_gains` |
| INV-38 | **Seek preserves transport AND mix (the combination INV-33 generalises).** `seekResult(t,dur,wasPlaying)` reports resume iff `wasPlaying`, and seek does NOT touch any stem's `{mute,solo}` — so solo→seek-while-playing leaves the same one stem the only audible one AND keeps playing; seek-while-paused stays paused. | `test_player_logic::PlayerStateMachine::test_seek_preserves_transport_and_mix`, `test_widget_render::PlayerIsWired::test_seek_keeps_playback_running` |
| INV-39 | **Seek clamps.** `seekResult` always returns t ∈ [0, dur] — a negative / gutter / over-duration click never seeks out of range. | `test_player_logic::PlayerStateMachine::test_seek_clamps` |
| INV-40 | **Player composes with the VIEW axis — entering Simple resets the per-stem mix (SPEC §B.14 inv 6; found by deed 2026-06-23).** Solo/mute is a Detailed-only capability (the M/S controls live in `#stemlanes`, hidden in Simple, INV-18/22). Switching to Simple calls `resetMix` → every stem `{mute:false,solo:false}` → `pgains` all-audible, so a soloed/muted part is never left audible-but-invisible-and-unundoable. `resetMix(stems)` and the `apply("simple")` toggle wires `window.__resetMix`. **Composition with INV-45 RESOLVED (reopen 1.8.0):** `resetMix` clears user solo/mute but PRESERVES a near-silent lane's safety mute (each lane carries `nearSilent`; `resetMix` returns `{mute:!!nearSilent}`), so a Simple→Detailed round-trip never un-silences a near-silent lane — INV-45 (a safety default) wins for near-silent lanes, INV-40 still resets user solo/mute. | `test_player_logic::PlayerStateMachine::test_simple_resets_mix`, `::test_reset_mix_preserves_near_silent_mute`, `test_widget_render::SoloAndMuteAreMutuallyExclusive::test_simple_toggle_resets_the_mix` |

### View selector as remembered state   [SPEC §B.15]

Coded + tested. resolveView extracted between VIEW_LOGIC_START/END markers and run in node (same pattern as player logic).

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
| `simple` | L-js toggle (`apply("simple")`) | `#stemlanes`, `#seqKey` → `display:none`; `#recs .rec:not([data-t])` → `display:none`; `#refPanel` → `display:none` (nested `#refRead`/`#webPanel` hide with the container, D-INV-36) |
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
| `vitals` | ✓ | ✓ | ✓ | — | spec row · L-js |
<!-- REMOVED 2026-07-03 (s49): the `#verdict` "In short" headline panel. It repeated what the recs/cards say, added visual weight to the calm-first screen, and was never on earlier versions. The verdict TEXT lives on independently in the catalog/library listing (index.json → run_dir.py:289 / library.py:288), which is untouched. Removed: the widget div + JS render + CSS + `verdict_lead` string + gate test 11. -->

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
| `stale` chip | ‡ | ‡ | linked widget behind current analysis version | INV-12 · catalog.py |
| `modeseg` filter / search box | ✓ | ✓ | — | client filter/sort · L-js |
| responsive column-shed | ✓ | ✓ | — | fixed col count, progressive shed (INV-10) · catalog.py |
| footer version | ✓ | ✓ | — | catalog.py |

## §7 — Cross-page correspondences (same run, two surfaces) — each row is an invariant
A flat per-surface grid can't see drift BETWEEN the two pages; these are the cross-page rules.

| # | S1 widget source | S2 catalog source | rule | owning test |
|---|---|---|---|---|
| X1 | mode badge `.modebadge.{m}` | mode pill `.mode.{m}` | same word + same colour token (`full`→`--good`, `quick`→`--bright`) | INV-20 · `test_catalog::CrossPageModeAgreement` |
| X2 | the widget a title link opens | row title link `_open_href` | the link opens THAT run's CURRENT widget; stale ⇒ flagged, not silently old | INV-12/17 · `test_catalog::StaleWidgetFlag`, `CatalogIsLocalIndex` |
| X3 | Track Story arc (`story` curves) | signature ribbon `c-sig` | same underlying run curves (ribbon = downsample of the arc source) | `test_catalog::RunMetrics`, `test_catalog::SignatureSvg` |
| X4 | S1 player (per-stem / mix) | S2 one-button preview | both play the SAME run's web mix; absent mix ⇒ no control on either (INV-7/8) | `test_catalog::CatalogRowPlayer` |

## §E — Run completeness & missing measurements (SPEC §E → RC-INV-1…12)

The cross-cutting "partial run" rules, projected to a checkable grid. The canonical logic is one shared
module (`scripts/completeness.py`) so the coach, catalog, and §D all treat *missing* the same way; the
pure-logic invariants are unit-tested NOW, the surface-rendering ones land with the §D/manifest code.

| code | rule (1-line) | owning test / status |
|---|---|---|
| RC-INV-1 | missing (None/NaN) ≠ measured-zero; never collapse | `test_completeness::MissingIsNotZero` ✓ |
| RC-INV-2 | a run carries a completeness manifest; read it, not a sentinel | `test_completeness::MissingIsNotZero::test_manifest_lists_only_measured_axes` ✓ |
| RC-INV-3 | never impute missing→real value then show/compare | `test_completeness::CompareOverSharedAxesOnly` ✓ |
| RC-INV-4 | surface shows "not measured", omits the card (no evidence) | not built — lands with the per-facet/catalog render |
| RC-INV-5 | compare over BOTH-present axes only; never 0-gap/max-gap | `test_completeness::CompareOverSharedAxesOnly` ✓ |
| RC-INV-5a | < `MIN_SHARED_AXES` shared ⇒ "not comparable", not a 0 | `test_completeness::TooFewSharedIsNotComparable` ✓ |
| RC-INV-5b | rank directions by **per-axis** distance (axis-count-fair) | `test_completeness::RankingIsAxisCountFair` ✓ |
| RC-INV-6 | centroid per-axis over members that HAVE it; absent≠0 | `test_completeness::CentroidSkipsMissingMembers` ✓ |
| RC-INV-7 | missing-by-mode silent; missing-in-promised-surface shown | not built — composes with view ladder INV-18/22 |
| RC-INV-7a | the rung→promised-surface list is the single authority | not built — keys off §B.14/INV-18/22 |
| RC-INV-8 | same missing axis reads identically across coach/catalog/§D | not built — lands with the manifest render |
| RC-INV-9 | pick most-complete run; run-id in content-hash (D-INV-14) | rep-selection **BUILT** (reopen 1.8.0): ONE canonical most-complete-then-newest key `library._rep_sort_key` (entry completeness = `mode`, full ⊇ quick) shared by `group_versions`, `prune_versions_plan`, and `run_dir.newest_run` (result-file count on disk) — a full run outranks a later quick run of the same bounce; unifies the three formerly-disagreeing selectors — `test_library::RepSelection::test_full_beats_newer_quick`. run-id-in-content-hash (D-INV-14) half unchanged |
| RC-INV-10 | gap → re-measure, never impute; ⟨DECIDE E-1⟩ auto vs flag | partial-run logic **built+tested** — `test_completeness::PartialRunIsAnError`; UI re-measure command not built (backlog) |
| RC-INV-11 | significance has a third `unknown (not measured)` state | `test_completeness::SignificanceHasUnknown` ✓ |
| RC-INV-12 | one per-run completeness line "Measured N of M signals; absent in this track: ⟨reads⟩" so absence≠all-clear; reads the shared fingerprint manifest (RC-INV-8) over the rung's promised axes (`fingerprints.PROMISED_BY_MODE`, split from the one `AXES` list — quick=mix-level, full=all). NEG: a missing-by-mode axis (a per-stem axis on quick) is never counted as skipped; the line is in the muted based-on register, once per run, never one note per card. Level: L0-DATA (pure `run_completeness`) + L1-DOM (the line ships in the widget markup). | `test_completeness::RunCompleteness::test_full_complete_measures_all`, `::test_full_partial_lists_skipped_reads`, `::test_quick_promises_only_mix_axes`, `test_widget_render::CompletenessLineShipped::test_line_in_markup` |
| RC-INV-13 / RC-INV-13d | run validity DECISION + deposit gate — a run is complete iff every promised signal whose source part the significance gate reads present carries a real value; a gate-absent part is a valid "not present", never a gap; the mix-axis `0.0` imputation is removed so a failed detector reads missing; an invalid run is refused at deposit. NEG: a near-silent stem's axes never invalidate; a broken measurement (present stem, unmeasured axis) does; a run with no analysis to judge is not blocked. Level: L0-DATA. | `test_validity::RunValidity::test_complete_run_is_valid`, `::test_broken_run_is_invalid_and_names_the_gap`, `::test_gate_absent_part_stays_valid`, `::test_failed_mix_detector_invalidates`, `test_library::IncompleteRunNotDeposited::test_incomplete_run_refused`, `::test_complete_run_deposits` |
| RC-INV-13a / RC-INV-13b / RC-INV-13c | run-validity WIRING — a completion re-measures the stored audio `--only-this` (no re-trigger) and carries the read forward (13a); the completeness line reads "absent in this track" (13b); `revalidate` reports incomplete runs and by default a build completes them, `--only-this` opts out (13c). A completion resolves the source under `audio_path` (the key every real run writes; `audio` is a bare basename or absent), so an old run is not silently no-oped; when the source is unrecorded/gone it fails loud and `revalidate --apply` verifies each run became valid by deed, exiting non-zero if any stayed incomplete (a run is complete or the tool says it failed, never a silent partial). | `test_pipeline_plan::RunValidityOrchestration::test_incomplete_deposits_found`, `::test_complete_run_dry_plans_reanalyse_only_this`, `::test_complete_run_resolves_audio_path_key`, `::test_revalidate_apply_fails_loud_when_source_gone`, `::test_flags_exposed`, `test_widget_render::CompletenessLineShipped::test_line_in_markup` |
| RC-INV-13e | reference-run validity checked at direction-generation (a reference run never deposits, so the deposit gate does not reach it) — `gen_reference_directions._run_valid` judges each run at the point of use and excludes an incomplete one from the centroid, naming its unmeasured reads. NEG: a complete reference run passes; a dir with no analysis to judge is not spuriously skipped. Level: L0-DATA. | `test_pipeline_plan::RunValidityOrchestration::test_reference_run_validity_guard` |
| RC-INV-13f | an invalid run that terminally FAILED renders the honest "Analysis couldn't complete for this track." message + source hint, not the recoverable reload placeholder — the render guard reads run_meta.json analysis_state:"failed"; the analyzer stamps it at a terminal step failure and clears it on a fresh attempt. NEG: an invalid run WITHOUT the failed marker still shows "Analysing — reload when it's ready."; a valid run renders the full widget regardless of any marker. A run that failed BEFORE result_core.json was even written (the "core" step itself broke) still renders the same honest placeholder — main()'s CLI derives run_dir from `--core` and checks the failed marker BEFORE its own core-file read, instead of crashing with FileNotFoundError; NEG: a non-failed run with no core file (still mid-analysis, or no marker at all) still errors loud, since that's a genuine usage error, not something to paper over. The three placeholder strings (`status.incomplete`/`status.failed`/`status.failed_hint`) live in `STRINGS["status"]` and are overridable via `--strings`/dumped via `--dump-strings` like every other panel string. Level: L1-DOMTEXT (render) + L0-DATA (stamp). | `test_widget_render::FailedRunRendersHonestPlaceholder::test_failed_marker_renders_honest_message`, `::test_no_marker_still_shows_reload_placeholder`, `::test_valid_run_ignores_stale_failed_marker`, `test_widget_render::EarlyNoCoreFailureRendersPlaceholder::test_main_renders_placeholder_instead_of_crashing`, `::test_running_state_with_no_core_still_errors`, `test_widget_render::StatusStringsLocalisable::test_dump_strings_includes_status_block`, `::test_strings_override_reaches_failed_placeholder`, `test_pipeline_plan::AnalysisStateStamp::test_terminal_failure_stamps_failed_with_reason`, `::test_normal_completion_stamps_ok`, `::test_stale_failed_marker_cleared_by_fresh_success` |
| RC-INV-13g | the two under-rendered pages tell the producer where the run stands, not a bare status line. Both the failed placeholder and the in-progress placeholder render a "Got this far" step list (`_run_progress`) read from which `result_*.json` files the run's mode actually wrote — quick promises just the core step, full promises all seven (loudness/arc, stems, per-stem rhythm, note transcription, drum breakdown, self-similarity, plus arrangement/.als ONLY when result_als.json exists — an .als is optional input, never shown as "not reached"), each marked done (✓) or not-yet (—). The failed page additionally shows "What went wrong" — the caught `analysis_error` verbatim in a muted monospace line — under its existing next-step hint; the in-progress page shows the same step list under its "reload when it's ready" line and names no error, since none was caught. A run with nothing measured yet (or no `run_dir` to judge) shows "Nothing measured yet." in place of the list — best-effort, so a read error never blocks the placeholder from rendering. NEG: a valid run renders the full widget and shows neither the step list nor the error box. The three progress strings + the 7 step labels live in `STRINGS["progress"]` and are overridable via `--strings`/dumped via `--dump-strings` like every other panel string. Tail (1.7.4): both pages additionally name the **source file** — `_source_block_html` reads `run_meta.json`'s `audio_path` (fallback `audio`) via `_read_audio_path`, and renders a "Source file" block (basename in `.fname`, full path in a `user-select:all` `<code id="srcPath">`, plus a `#copyPath` button) as the FIRST detail block, ahead of "Got this far". A small inline `<script>` (only emitted when the block is present) copies the path via `navigator.clipboard.writeText`, falling back to a `Range`/`execCommand('copy')` selection when the async clipboard API is missing or rejects (the fallback is what keeps it working from a `file://` page) — on success the button label swaps to "Copied" for ~1.5s. DOES: a run whose `run_meta.json` carries `audio_path` shows "Source file", its basename, its full path, and `id="copyPath"`, ahead of "Got this far" in document order. NEG: a run with no recorded `audio_path`/`audio` omits the block entirely and still renders its status line without crashing. `source_heading`/`copy`/`copied` live in `STRINGS["progress"]` and are overridable via `--strings`. Level: L1-DOMTEXT. | `test_widget_render::ProgressBlockDisclosesRunStanding::test_failed_run_shows_progress_list_and_error`, `::test_incomplete_run_shows_progress_no_error_box`, `::test_no_core_failed_run_shows_nothing_measured`, `::test_strings_override_of_progress_heading_reaches_the_page`, `::test_valid_run_shows_neither_progress_phrase`, `::test_failed_run_names_source_file_and_copyable_path`, `::test_run_with_no_audio_path_omits_source_block`, `::test_strings_override_of_progress_copy_reaches_the_button` |

**Settled 2026-06-25:** E-1 = partial run is a technical error → flag "run incomplete, re-run"
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
half (in-zone/diverge/signature) and the **mapping/aim** input are deferred until the mapping input ⟨D-2⟩, and
the **references switch** + **reference-track ingestion** + **live web fetch** are separate not-built
surfaces. Not-built rows carry no owning-test citation (they name the surface they land with instead).
| code | rule (1-line) | owning test / status |
|---|---|---|
| D-INV-4 | The tool never guesses which direction a track aims at — the mapping is always yours, and many-to-many | not built — mapping input deferred ⟨D-2⟩ (aim feature excised 0.9.15). Level when built: node (mapping logic) + browser (aim glyph) |
| D-INV-5 | A track with no mapping is byte-for-byte as today (cards/read/player); the «leans toward» line + reference catalog are *additive* new surfaces, not a change to the widget | descriptive surface is additive + gated: `test_headless_render::SimpleViewGatingBrowser::test_ref_panels_hidden_in_simple_visible_in_detailed` (#refRead hidden in Simple, visible in Detailed — browser); `test_headless_render::QuickModeRefReadAbsent::test_refread_absent_in_quick_mode_rendered_dom` (#refRead absent in quick — browser); the no-mapping-mutation guarantee lands with the mapping input ⟨D-2⟩. Level: browser-render |
| D-INV-6 | The show/hide-references control is ONE named switch shared by the reference column + plaque chip; no view strands its state | **BUILT** (reopen 1.8.0): one named control `#refsToggle` on both surfaces (same label/JS/key); the widget hides `#refPanel` (the leans-toward plaque chip lives inside it), the catalog hides the `.c-lean` column; state read from localStorage on every load so it survives view flips + reopen. Control renders only when a reference surface is present — `test_references_switch::WidgetSwitch`, `::CatalogSwitch` |
| D-INV-7 | Reference tracks never enter your library's catalog/signatures; the switch only surfaces them through the reference column (audio-only) | not built — lands with reference-track ingestion; the §F own-library column is a *separate* surface, never under the references switch. Level when built: node (ingestion boundary) + render |
| D-INV-8 | Any web fetch completes, fails, or times out and the feature carries on — it never hangs the analysis or the render (liveness) | not built — live web fetch deferred ⟨DECIDE D-9⟩; the current `#webPanel` renders curated static notes (D-INV-29), so there is nothing to time out yet. Level when built: node (async/timeout harness) |
| D-INV-9 | A reference either yields a placeable fingerprint + read, or reports which signals it couldn't compute — never a half-finished silent state; a missing-axis reference is catalogued but NOT comparable, yet still contributes per-axis to its cloud centroid | **BUILT (node)** — `test_completeness::CompareOverSharedAxesOnly`, `::TooFewSharedIsNotComparable`, `::CentroidSkipsMissingMembers`, `::PartialRunIsAnError`; `test_similarity_columns::LeansTowardCompleteness` |
| D-INV-10 | Every character / mood / style / in-zone statement carries its real evidence — one signal or a combination; with none it is omitted, never shown (anchored read) | **BUILT (browser-render)** — `test_headless_render::RefReadEvidenceMarksRendered::test_star_marks_visible_in_detailed` (★/☆ marks visibly rendered in Detailed — browser); `test_headless_render::RefReadEvidenceMarksRendered::test_all_rendered_rows_have_nonzero_height` (no phantom hidden rows for missing axes — browser); also string-level: ReferenceReadRichLook (★ logic) + ReferenceReadOmitsMissingAxes (omission logic). The in-zone evidence half lands with the mapping verdict ⟨D-2⟩. Level: browser-render |
| D-INV-11 | The verdict is read in FULL dimensions and is authoritative; no lossy 2-D/3-D projection (the map was dropped); the «leans toward» line + read derive from the same full-dim fingerprint, so they can never disagree | **BUILT (node)** — `test_similarity_columns::LeansTowardPicksNearestDirection` (nearest by full-dim centroid, no map), `test_completeness::RankingIsAxisCountFair` (per-axis distance, not a projected/raw-sum marker). Cross-surface agreement render composes with D-INV-21 |
| D-INV-16 | signature and in-zone/diverge are computed only against CLOUD directions; a reduced direction (too few members for a zone) never produces a verdict, and a track aimed only at reduced directions has no signature | reduced-direction *nearest-by-member* is built (D-INV-21); the in-zone/diverge/signature **verdict** lands with the mapping input ⟨D-2⟩. Level when built: node (cloud-vs-reduced gating) |
| D-INV-18 | Adding and removing a member are symmetric: both recompute the direction's cloud + every dependent read and re-stamp; a threshold crossing reduces/appears the verdict; a read's stamp always matches the member count it was computed against | not built — member add/remove + re-stamp composes with the placement/epoch code (D-INV-12/14). Level when built: node (recompute symmetry + stamp/hash) |
| D-INV-19 | in-zone/diverge/signature is a pure function of the full-dim fingerprint (per-facet spread test); there is no projection to disagree — the full-dim verdict is the only one and is authoritative | per-facet full-dim decomposition built (render): `test_headless_render::RefReadBarsRendered::test_refread_bars_render_with_nonzero_width` (.refread-bar elements render with non-zero pixel width — browser); string-level: ReferenceReadBars (bar DOM structure) + ReferenceReadMostSimilarFirst::test_divergence_grows_downward_most_divergent_is_last (most-similar-first order); the in-zone/diverge **verdict** lands with the mapping input ⟨D-2⟩. Level: browser-render + node |
| D-INV-20 | Reference / compare is a FULL-run-only feature — quick mode is never referenceable; shown as "full analysis only", silent (RC-INV-7), never a partial-run error (RC-INV-10) | **BUILT** — `test_reference_read::ReferenceReadDetailedOnly::test_quick_mode_has_no_refread_block`, `test_completeness::SharedAxisFloor::test_quick_vs_full_not_comparable`. The catalog-cell "full analysis only" is a separate surface (D-INV-22, not built) |

### Reference line «leans toward» (SPEC §D.10)
| code | rule (1-line) | owning test / status |
|---|---|---|
| D-INV-21 | catalog column = plaque chip = producer's read's nearest — ONE full-dim geometry, never a 2-D marker distance (no map); the single nearest is chosen across ALL directions (clouds by centroid · reduced by nearest member), axis-count-fair (RC-INV-5b); no directions ⇒ "no direction yet", never a fabricated nearest | geometry NOW via `test_completeness::RankingIsAxisCountFair`; cross-surface agreement + empty-case render: not built — lands with §D render |
| D-INV-22 | quick-only version ⇒ cell "full analysis only" (silent, RC-INV-7); a full row with no close direction ⇒ "no close direction yet"; NEVER the siblings phrase "no similar tracks"; row reads the **newest** version's most-complete run (E.4, D-INV-35); never blank-implies-none | Empty-state copy **BUILT+tested** (Fable audit 2026-07-03 found the shipped `_lean_cell` wrongly emitted "no similar tracks" for every empty lean incl. quick) — `test_catalog::LeanCellEmptyCopy` (quick⇒"full analysis only", full-no-lean⇒"no close direction yet", "no similar tracks" never in the lean column). Row = newest version: **BUILT** (D-INV-35). Full inline lean STACK render still composes with §D ship. **Completeness three-way BUILT (reopen 1.8.0):** a full run missing an axis reads "can't compare — ⟨missing signals⟩" (`R_MISSING`), never a fabricated "no close direction yet" — `test_catalog::LeanCellCantCompare`, `test_similarity_columns::ReasonProbe`. **Presence gate BUILT (reopen 1.8.0):** the reference column is absent when no shown version produced a computed result (all-quick / no directions) — `test_catalog_columns::ColumnPresenceGate`, `::Ncols` (dynamic column count) |
| D-INV-23 | both placements under the ONE references switch; toggle hides/shows both; never strands | **BUILT** (reopen 1.8.0): ONE global persisted flag `tc_refs_hidden` (localStorage), the identical key + `refs-hidden` body hook on BOTH the catalog page and a track's widget, so hiding references on either hides both — not a per-page toggle — `test_references_switch::OneGlobalSharedSwitch` |
| D-INV-24 | recompute + re-stamp on library/epoch change; catalog never shows a stale "leans toward" | not built — composes with D-INV-12/14 placement code |
| D-INV-25 | never a NUMBER — no raw distance / score / rank / % / "match %"; only a direction name + a coarse cue | not built — assert rendered chip carries no numeric token at all |
| D-INV-26 | cue = coarse closeness shown by COLOUR only (green close / amber mid / red far) — no words, no number, not a grade (red=far, not worse). Reference basis = RELATIVE lean (D-28); §F basis = library distribution (D-27). §F red only as last resort. Reference runner-up DEFERRED (D-24) | geometry **BUILT+TESTED** `test_similarity_columns::RelativeLeanBuckets` + `NearestOwnRedIsLastResort`; colour render: not built — assert §D reference cell carries a greyscale-safe glyph tier (●●●/●●○/●○○) beside colour, §F uses nearest-first order, both carry a hover label; no numeric/word closeness token on any cell |
| D-INV-26 (browser) | The catalog closeness COLOUR renders, not just sits in the HTML text: a CLOSE lean's `.sim-dir` computes green `rgb(46,158,91)` (#2e9e5b), a MID lean computes amber `rgb(216,147,42)` (#d8932a), and a FAR `.sib-chip` computes red `rgb(194,80,61)` (#c2503d) through the real cascade. NEG: no cell falls back to the default anchor blue `rgb(0,0,238)` (a link-colour reset the hex string tests are blind to). Closes the B2-remainder catalog level-gap (s52) — the 6 `test_catalog_columns` colour tests were hex-in-HTML only. Level: L3-BROWSER. | `test_headless_render::CatalogSemanticColourRendered` (L3-BROWSER, s53) |
| D-INV-27 | **Up-to-three nearest directions as a nearest-first list, not a single name + crammed runner-up tint.** Lists up to the 3 nearest reference clouds that clear the lean bar, ranked nearest-first; order carries the rank; chips/tabs are NEUTRAL (no level colour — similarity not normalizable, 2026-07-02); only the active tab is highlighted; never pads to 3 with weak/far filler ("no close direction yet" instead). Descriptive (ships 0.9, no mapping needed); the aim glyph / pinned-aimed entry / re-flavouring are deferred until the mapping input ⟨D-2⟩. | `test_similarity_columns::TopKBasics` (built+tested); `test_reference_read::ReferenceReadTabSelector::test_nearest_tab_not_level_coloured` (built+tested) |
| D-INV-28 | **Every name is a navigation link; the read-panel direction tab is ephemeral, never a persisted selection.** Catalog: track→open, own sibling→scroll (F-INV-4), direction→open read focused. Read panel: tabs default to nearest and re-target the read+plaque — since the D-INV-36 merge the tabs are the ONE shared selector at the top of `#refPanel`, driving BOTH nested disclosures; tab is ephemeral (not written to the URL) — cross-page entry-focus is a one-shot URL param read once on load. On a recompute that drops the focused direction the read falls back to nearest; if it empties entirely the open panel collapses to "no close direction yet" (tabs+bars removed, prose kept), re-stamped. | read-panel tabs: built. Catalog click-to-focus wiring: **BUILT s59** (D-INV-37 rows below own the wiring facts). Recompute-empties: still design (recompute is a rebuild today — a new widget renders the new lean set; no live-recompute surface ships). |
| D-INV-29 | **The web panel shows only facets a curated facet→signal map ties to measurement; ★ = directly confirmed on the direction's centroid, ☆ = soundly indirect, contradicted = withheld.** Two glyphs + one footnote (never long per-row tags); judged on the cloud centroid (D-INV-21); per-artist, never blended; an absent web panel is a valid silent state; completeness-aware (a missing axis ⇒ not ★/☆, not shown). **Approved layout (2026-07-04 — variant A):** blurb first, then note box, then glyph-led confirmed rows under "Your measurement backs these up", then ONE muted dot-separated group under "Web describes these — your tracks don't bear them out" (NOT one pill per row), then visible sources list, then one footnote legend. The web panel is a readable NESTED-OPEN disclosure `#webPanel` inside the merged reference panel `#refPanel` (§D.10.2 — "What the web says about ⟨artist⟩"; the artist follows the shared selector, D-INV-36), last inside the panel (centroid read → web notes), which itself sits last in the read order (producer's read → tonal balance → reference panel). *(Supersedes the pre-merge "standalone collapsible, collapsed by default" — 2026-07-05.)* | `ReferenceReadRichLook` (built+tested); `test_reference_read::WebPanelRendering` (collapsed, summary, artist header, phrase+glyph, absent when no marks); `test_widget_render::ReadOrderTonalBeforeRefRead::test_webpanel_css_gate_present`; `test_rich_panel::RenderReferenceNotesUnit` (blurb, note, glyph-led confirmed rows, muted web-only group, sources, footnote) |
| D-INV-29-layout | **Approved readable layout — glyph-led confirmed rows, single muted web-only group, visible sources, footnote legend (D-INV-29 variant A, 2026-07-04).** Confirmed traits (★/☆) render as glyph-led rows with no trailing pill. Web-only/not-measurable traits collapse into ONE muted dot-separated group (not N pills). Sources list renders visible with ≥1 `<a href>`. One `.rn-footnote` legend present. Level: browser-render. | `test_headless_render::WebPanelReadableLayout` (browser: glyph-led confirmed rows; no per-row "WEB SAYS" pill; sources block with ≥1 `<a href>`; footnote legend present — asserted in Detailed view) |
| D-INV-29-typo (s57) | **Web-panel readability (2026-07-05): brightness hierarchy + type scale + source links.** (a) A section heading is NEVER dimmer than the body it heads — `#webPanel .rn-section-label` / `.tc-rn-sources-label` are `--ink` (were `--muted`, under `--ink` body — a brightness inversion). (b) The panel fonts are snapped to the widget's whole-number scale (section labels/footnote 11px, blurb/traits 13px, genre/realname/webonly/sources 12px — the scattered 10/10.5/11.5/12.5 "fractional" set the font audit flagged, in-panel scope only). (c) Each source reads as a LINK — `.tc-rn-sources a` carries an underline + a leading chain-link icon (inline `svg.tc-rn-link-ico`, coloured via `currentColor`; 2026-07-05 replaced the ↗ arrow — read as the wrong, ugly glyph — with the conventional link glyph). Level: **L3-BROWSER** (computed colour/decoration, invisible to string tests). | `test_headless_render::WebPanelReadableLayout::test_s57_section_headings_not_dimmer_than_body_and_sources_are_links` |
| D-INV-29-sources | **Sources links visible at #webPanel bottom.** When web notes carry a sources list, the `<a href>` source links render VISIBLE in the shipped panel — never hidden or dropped (2026-07-04 amendment: the v2 mockup had removed the sources block; the decision: keep it). Absence-case: panel with no sources list ⇒ no sources block (no broken empty list). Level: browser-render. | `test_headless_render::WebPanelReadableLayout::test_sources_block_has_links` |
| D-INV-35 | **Catalog = one row per TRACK, its NEWEST version** (design A, strict-newest, 2026-07-03). Older versions get NO catalog row — they live only in the per-track plaque (INV-11). Every catalog cell (signature / BPM / LUFS / date / lean / siblings) reads the newest version's most-complete run, never blended across versions; the version **delta** vs the prior version still renders; the `×N runs` chip counts runs within the newest version; the "older analysis" tool-stale chip (INV-12) is orthogonal. Subtitle counts **tracks** (rows shown), never a larger version total. | **BUILT (string, render-asserted)** — `test_catalog::NewestOnlyPerTrack` (2-version track → 1 `<tr>`; row carries newest `data-version`/`data-bpm`; older version absent as a row; subtitle counts tracks; single-version track unchanged). Older version survives in the plaque = `test_widget_render::CrossVersionPanelData` (INV-11). Lean/sibling fingerprint = newest via `_load_sim_data` newest-per-slug = `test_catalog::NewestOnlyPerTrack::test_sibling_fingerprint_is_newest` |
| D-INV-30 | **The reference read decomposes per-facet vs the direction's centroid — signed z-normalised bars, most-SIMILAR first (matched/green rows lead, divergence grows downward), no raw distance/score.** Detailed-only; reads against the focused direction tab, falls back on recompute; a missing facet is omitted, never drawn at zero. Fixed read order (§D.10.3, packaging merged 2026-07-05 D-INV-36): producer read → tonal balance (#tonalPanel) → reference panel (#refPanel: centroid read #refRead, then web notes #webPanel — nested, order preserved). | `ReferenceReadBars` (built+tested); `test_reference_read::ReferenceReadMostSimilarFirst::test_divergence_grows_downward_most_divergent_is_last`; `test_reference_read::ReadOrderWithRefRead` (tonalPanel < refRead < webPanel in rendered HTML, refRead/webPanel inside refPanel) |
| D-INV-36 | **ONE reference panel, one selector, both disclosures follow (the Q5 merge — 2026-07-05).** (a) `#refRead` + `#webPanel` live NESTED inside one container `<details class="tc-panel" id="refPanel" open>` titled "You vs your closest match", built like the Evidence drawer: shared `.reftab` selector at the top (only when ≥2 directions qualify; 1 ⇒ no tab bar), then the centroid-read disclosure ("What the numbers show"), then the web disclosure ("What the web says about ⟨artist⟩") — **both open by default**, order fixed (D-INV-30). (b) Switching a tab re-targets **BOTH** disclosures client-side — the per-facet bars AND the web body + its summary artist name — so the two can NEVER show two different directions at once (the pre-merge defect: bars on the selected direction, web stuck on the top match). (c) The build embeds web bodies for **every shown direction** that has web content (all ≤3, one-source file) — not only the nearest (folds in the s47 "web-descriptor for all 3" feature). (d) A focused direction with NO web content hides the web disclosure entirely while focused (liveness × selector — absent, never an empty-open box; INV-47 composed); switching back restores it. (e) Empty state (s60, 2026-07-05): directions defined but nothing to compare ⇒ a NON-expandable stub plaque — a plain div keeping the panel look, title and `#refPanel` id, one muted note, no arrow, no tabs, no nested disclosures. Note by reason: none close ⇒ "no close direction yet"; run with no fingerprint ⇒ "no comparison data in this run" (replaces the pre-s60 silent absence); no shared facets ⇒ "can't compare yet". NEVER the siblings phrase "No similar tracks" (pre-merge bug, D-INV-22 vocabulary leak). No directions defined at all ⇒ panel absent (`when-reference`). (f) Simple hides the container (its nested ids with it, INV-18/22); quick renders none of it. Level = **browser** (structure, interaction, computed visibility). Fixture: SYNTHETIC (refs fixture, all 3 directions with web notes + one no-web-content direction + an all-far build + an empty run dir). | `test_headless_render::MergedReferencePanel` (test_one_container_selector_and_two_nested_open_disclosures / test_tab_switch_retargets_both_bars_and_web / test_all_shown_directions_have_embedded_web_bodies / test_direction_without_web_content_hides_web_disclosure / test_empty_state_says_no_close_direction_yet / test_missing_fingerprint_renders_no_comparison_data_stub); `test_completeness_gate::WholeArtifactCompletenessGate::test_24_ref_panel_container_populated` |
| D-INV-37 (writer, N20) | **Catalog direction links carry the one-shot entry pair** — each `.sim-dir` href is the row's own widget URL + `?direction=⟨URL-encoded direction name⟩#detailed` (spaced names encoded, e.g. "Venetian Snares" → `Venetian%20Snares`); quick rows ("full analysis only") and no-close rows ("no close direction yet") carry no direction links (existing negative rows). Level: string on the REAL rendered catalog HTML. | `test_catalog::DirectionLinksCarryEntryPair` (href has `?direction=`+`#detailed`, encoded spaced name, no bare `#`, own-widget URL prefix) |
| D-INV-37 (reader, N17) | **One-shot `?direction` entry reader in the widget** (browser, real load with query+hash): (a) open `?direction=⟨2nd direction⟩#detailed` ⇒ that tab `.active`, its `.refpanel` bars visible, web body + summary artist follow (through the click path, D-INV-36), body NOT `.simple`, `#refPanel` scrolled into view (top within viewport); (b) unknown name ⇒ nearest (first) tab active, panel STILL scrolled into view; (c) no param ⇒ default state, NO scroll (page stays at top — regression fence on normal opens); (d) entry never writes `tc_view` (store fence, §B.15) and tab clicks after entry leave the URL search untouched (ephemeral fence, D-INV-28); (e) empty state ("no close direction yet") ⇒ param ignored, no scroll, no error. Level: **L3-BROWSER** (interaction + computed visibility + scroll geometry). Fixture: SYNTHETIC (the D-INV-36 refs fixture). | `test_headless_render::EntryFocus` (test_entry_param_focuses_named_tab_and_scrolls / test_unknown_direction_falls_back_to_nearest_still_scrolls / test_no_param_default_state_no_scroll / test_entry_writes_no_store_and_tab_click_keeps_url / test_empty_state_ignores_param) |

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
| F-INV-4 | click a neighbour ⇒ catalog scrolls to that row + highlights it; pure navigation, changes no analysis state | **BUILT** (reopen 1.8.0): each row carries a stable `#row-<slug>` anchor (`catalog._row_id`); a sibling chip is `href="#row-<slug>"` + `data-scroll-row`, and a `<tbody>` handler scrolls the row into view + pulses `row-pulse` — `test_catalog_nav` (string-level anchors + a browser-level scroll/highlight click) |
| F-INV-5 | quick-only version ⇒ "full analysis only" (silent, RC-INV-7), exactly like D-INV-22 | **BUILT** (reopen 1.8.0): `catalog._siblings_cell` reason-branch `R_QUICK` — `test_catalog::LeanCellEmptyCopy`, `test_similarity_columns::ReasonProbe` |
| F-INV-6 | a version missing a fingerprint axis: not listed AND not offered AS a neighbour; cell "can't compare — ⟨signals⟩" | geometry NOW (not-comparable via RC-INV-5a `TooFewSharedIsNotComparable`); render **BUILT** (reopen 1.8.0): `_siblings_cell` reason-branch `R_MISSING` interpolates the missing signal reads — `test_catalog::LeanCellCantCompare`, `test_similarity_columns::ReasonProbe` |
| F-INV-7 | with no other placeable own-track, the cell reads "no comparison yet", never an empty-looks-broken cell | **BUILT** (reopen 1.8.0): `_siblings_cell` default reason-branch `R_NO_COMPARISON` → "no comparison yet"; the own-library column is also gated absent for an all-quick library (`show_sib`) — `test_catalog_columns::SiblingCellRendering::test_no_siblings_shows_no_comparison_yet`, `::ColumnPresenceGate` |
| F-INV-8 | recompute + re-stamp on library/epoch change; never points at a deleted version (cascade like D-INV-13) | not built — composes with placement + deposit/clean |

**Geometry layer BUILT+TESTED 2026-06-25 (s25):** `scripts/similarity_columns.py` (`leans_toward` + `nearest_own`
over `completeness.py`) — pure logic, no render. `tests/test_similarity_columns.py` (15 tests, red-on-bug
proven: a fabricated nearest fails the no-directions→None test). Suite 375 green (+15), 0 regression. Covers the
geometry half of D-INV-21/26 + F-INV-1/2/6/7; the colour render + scroll-nav (D-INV-22/23/25, F-INV-4/5) land
with the §D/§F catalog code, asserted against the real artifact. **D-24 runner-up RE-OPENED + deferred** (a
tied second is a weak lean, not a close one — self-contradictory under relative lean).

**Settled 2026-06-25:** D-17 = straight-line. D-28 = reference cue is RELATIVE lean (not absolute
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
direction the §D producer's read cites for that track (D-INV-21) — one full-dim geometry, two surfaces (no map);
owning test lands with the §D render. The own-library column is NOT under the references switch (§F vs D-INV-23) — a switch-off
state hides the reference column but leaves the DJ column visible; owning test lands with the switch render.

## §8 — Coverage status

**▶ Pre-promotion coverage walk (s65, 2026-07-12).** Re-walked the checklist at the current suite after the
s65 closing batch (1.5.2–1.5.4). Mechanical cross-referencing is green and continuous — `test_traceability`
(7 checks) holds every anchor→row, row→test, and the SPEC↔matrix reverse map on every commit. This session's
new invariants all carry their rows and tests: **G-INV-21** (a synthetic/smoke run never deposits) +
**G-INV-22** (the migrate banner tells a track to move from a source that is gone), **RC-INV-12** (the
"Measured N of M signals" completeness line, retiring its "not built" tombstone), and **INV-29/INV-30** (the
header source line — symmetry + long-name readability), the latter two now LIVE (their PROPOSED skips
removed, SPEC anchors written in §B.13). Suite **832 passed / 0 skipped** on a machine with headless Chrome +
Node present; the only conditional skips left are the browser/runtime-gated `test_headless_render` /
Node rows, which skip only where that runtime is absent (machine-dependent, not a coverage hole). The four
rework-questions below (s56) still hold; no new node was added this batch (the changes landed in the existing
library (N21), catalog (N20), and widget-render nodes).

**▶ 1.0-gate coverage walk (s56, 2026-07-05 — pass 2 of the pre-1.0 audit; the block below this is the older
s12 status, kept as history).** Walked against the CURRENT invariant set (through the 24 `ARCHITECTURE.md`
nodes), answering the four rework-questions:
- **Q1 — every node has ≥1 owning test?** YES for 22/24. The two without a DIRECT test — N2 (Demucs
  separation) and N9 (reference directions) — are exercised indirectly via fixtures (a direct test would
  assert a mock, not the behaviour; they need real audio / a Demucs run). Not bare holes.
- **Q2 — every rendered node has L3-BROWSER for its visibility/layout facts?** YES. N10/N11/N12/N16/N17/N20 +
  N19-display all carry `test_headless_render` rows; the §D shipping surfaces (#refPanel + nested #refRead/#webPanel) are gated
  browser-level (F1, INV-GATE test_22/23). No visibility/layout fact sits at L1-STRING only.
- **Q3 — every SPEC invariant projects to a row at the RIGHT level?** YES. The 11 previously-baselined
  ext-namespace invariants (DS-INV-4/9, G-INV-4/5/6/9/13/17, H-INV-7/11/12) all now have exactly one row;
  the newer INV-42..47 + INV-GATE are rostered in §3 at browser level.
- **Q4 — positive AND negative per fact?** Held for the gate class (INV-GATE proves-it-catches-emptiness +
  the `test_completeness_gate::WholeArtifactCompletenessGate::test_22_ref_read_absent_on_plain_full` negative;
  INV-46 `test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_probe_scan_detects_unregistered`;
  INV-47 proven red-on-bug on the quick fixture).
- **Matrix→test existence:** every named owning-test resolves (s56 worker cross-ref of all 20 cited files;
  one stale label `MissingIsNotZero::manifest` → `::test_manifest_lists_only_measured_axes` fixed). Suite
  763/2 at that walk, skip-set then = {INV-29, INV-30} exactly (both LANDED s65 — see the s65 walk above; the
  suite now runs them, 832/0 on a Chrome+Node machine).
- **Two-family reminder still holds:** this INV grid does NOT enumerate the credibility G-guards (CR-*/G1–G21,
  `test_credibility`, SPEC §B.2–B.10) — a full "what's uncovered?" sweep reads BOTH.

**— older status (s12, 2026-06-23) —**
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
  Genuinely UNCOVERED / not built: **INV-25** (Simple-promotion), the
  `eval_per_stem_usefulness` regression guard. (**INV-29/INV-30** — source-file symmetry + long-path
  readability — LANDED s65, 2026-07-12: `.srcmeta b` ellipsis-truncates with a `title` hover; both tests live.)
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

## §G — Storage relocation (SPEC §G → G-INV-1…20)

Invariants added 2026-06-30 (s31). All owned by `tests/test_storage_relocation.py`.

| code | rule (1-line) | owning test / status |
|---|---|---|
| G-INV-1 | Default output base is `~/.track-coach/projects/`, NOT next to the audio file | `test_storage_relocation::RelocationDefault::test_default_base_is_home_projects` |
| G-INV-3 | `--base` flag still overrides the default; path shape `base/slug/stamp` preserved | `test_storage_relocation::RelocationDefault::test_base_flag_still_overrides` |
| G-INV-2 | One track = one slug; a track re-run reuses the same slug dir | `test_storage_relocation::CollisionDisambiguation::test_same_source_reuses_slug` |
| G-INV-2b | Two different audios that slug the same get `<slug>-2` (+warn), never co-mingled. Identity is the **audio full path** (als-agnostic), so this fork fires ONLY on a genuinely different audio, never on an added `.als`. | `test_storage_relocation::CollisionDisambiguation::test_different_source_gets_slug_2` |
| G-INV-2c | **Adding an `.als` to a previously audio-only track REUSES the same slug — never forks to `<slug>-2`.** Source identity is als-agnostic (audio path), so a later run of the same audio that now also passes `--als` groups as a new VERSION under the same track, not a new track. Also: an old run whose stored `source_identity` was an als path still matches by its stored `audio_path`. | `test_storage_relocation::CollisionDisambiguation::test_adding_als_reuses_slug`, `::test_als_added_matches_old_als_identity_run` |
| G-INV-12 | First post-move run seeds shared index from old per-folder index so history stays one file | `test_storage_relocation::SeedFromOldIndex::test_old_index_entries_appear_in_new_index` |
| G-INV-14 | Catalog open-link falls back to library HTML copy when `src_run_dir` is missing on disk | `test_storage_relocation::CatalogFallback::test_open_href_falls_back_to_library_copy` |
| G-INV-16 (warn) | Catalog page shows a banner counting members with `src_run_dir` outside the output root | `test_storage_relocation::MigrateWarning::test_banner_counts_outside_root_members` |
| G-INV-11 | Run-index selector skips entries whose run dir is missing on disk; only returns existing dirs | `test_storage_relocation::DiskPresenceCheck::test_missing_run_dir_is_skipped` |
| G-INV-11 / RC-INV-9 — plaque hide | `cmd_catalog` drops absent non-self widget rows from catalog.json; self row kept even without widget | `test_storage_relocation::CmdCatalogHidesAbsentRows::test_absent_non_self_entry_is_hidden`, `::test_self_entry_kept_even_without_widget_file` |
| G-INV-11 / RC-INV-9 — plaque counts | n_runs / n_tracks in catalog.json count only visible rows after absent rows are hidden | `test_storage_relocation::CmdCatalogHidesAbsentRows::test_counts_reflect_only_visible_rows` |
| G-INV-11 / RC-INV-9 — all-absent track | A track whose every run dir is absent is dropped from catalog.json entirely | `test_storage_relocation::CmdCatalogHidesAbsentRows::test_track_with_only_absent_runs_is_dropped` |
| G-INV-16 | `migrate` dry-run prints from→to plan and moves nothing; `--apply` moves + rewrites src_run_dir | `test_storage_relocation::MigrateCommand::test_dry_run_changes_nothing`, `::test_migrate_apply_moves_and_rewrites` |
| G-INV-16 / G-INV-11 (atomic) | `migrate --apply` is crash-consistent per member — the index entry is rewritten immediately after each move, so a mid-loop failure never leaves an already-moved member pointing at its stale source (BUILT reopen 1.8.0) | `test_storage_relocation::MigrateCommand::test_migrate_apply_partial_failure_persists_completed_moves` |
| G-INV-18 | A run whose `run_meta` has `reference: true` is refused by `deposit_from_run` (raises `DepositError` BEFORE any write) → never in `index.json`; one guard covers BOTH auto-deposit (`build`) and the CLI `deposit` (both route through `deposit_from_run`). | `test_library::ReferenceNotDeposited::test_reference_run_refused`, `::test_own_run_still_deposits` |
| G-INV-16b | Banner counts library members only → once references aren't members, the count excludes them (an index of own-only members counts own-only). | `test_library::ReferenceNotDeposited::test_banner_count_excludes_references` |
| G-INV-21 | A run whose `run_meta` has `synthetic: true` is refused by `deposit_from_run` (raises `DepositError` BEFORE any write) → never in `index.json`, exactly as a reference is; the marker is set by `--synthetic` OR auto-detected when the source path contains `tests/fixtures/`. NEG: an own run under a normal path still deposits; a real project path is never mistaken for a fixture. Level: L0-DATA. | `test_library::SyntheticNotDeposited::test_synthetic_run_refused`, `::test_own_run_still_deposits`, `test_pipeline_plan::SyntheticFixtureSourceGuarded::test_fixture_source_marks_synthetic`, `::test_normal_source_not_marked` |
| G-INV-23 | Same-song alias merge: `canonicalize_entries` folds an aliased track slug onto its canonical slug BEFORE `group_versions`, so two filename identities of one song collapse to ONE catalog row and their bounces stay as versions; `resolve_alias` is cycle/depth-safe; the CLI `alias --merge/--list/--remove` round-trips the map and refuses a self-merge or a cycle. NEG: an empty map is a pure copy (pipeline unchanged); the input entries are never mutated. Level: L0-DATA + L1-DOM (one-row catalog render) + CLI. | `test_alias::AliasMap::test_resolve_follows_chain`, `test_alias::AliasMap::test_resolve_is_cycle_safe`, `test_alias::AliasMap::test_canonicalize_is_pure`, `test_alias::AliasMergesGrouping::test_two_filenames_collapse_to_one_track_two_versions`, `test_alias::AliasMergesGrouping::test_catalog_renders_one_row`, `test_alias::AliasCli::test_merge_list_remove`, `test_alias::AliasCli::test_cycle_refused` |
| G-INV-22 | Migrate banner splits its members: a member whose `src_run_dir` still exists is counted "to move" (consolidate); a member whose `src_run_dir` is gone is counted separately as "missing source" (delete or re-analyse), never folded into the consolidate count. NEG: a vanished source is never shown as consolidatable; an existing project source is never shown as junk. Level: L1-DOM (banner text on a rendered catalog). | `test_storage_relocation::MigrateBannerMoveVsJunk::test_existing_source_counts_to_move`, `::test_missing_source_counts_as_junk`, `::test_render_shows_both_lines` |
| G-INV-20 | One-off reference cleanup: **dry-run default** reports what it would drop and writes nothing; `--apply` first backs up `index.json`, then removes exactly the entries whose `src_run_dir` is under a known reference-album path — own tracks and the reference run dirs on disk are untouched. | `test_library::ReferenceCleanup::test_dry_run_writes_nothing`, `::test_apply_backs_up_and_drops_only_references`, `::test_own_entries_and_run_dirs_untouched` |
| G-INV-4 | Pre-1.0 runs already on disk keep working and are never moved automatically — relocation is going-forward only; only NEW analyses land under `~/.track-coach/projects/`, and a bare `migrate` moves nothing (needs `--apply`). NEG: a new run does NOT stay beside the audio; an existing run is NOT relocated without `migrate --apply`. Level: L0-DATA (path + dry-run gate). Retires the s52 ext-namespace baseline id. | `test_storage_relocation::RelocationDefault::test_run_dir_is_under_home_projects_when_no_base`, `test_storage_relocation::MigrateCommand::test_dry_run_changes_nothing` |
| G-INV-5 | The durable library stays at `~/.track-coach/library/` — a sibling of `projects/` under the one output root; only the transient run dirs relocate. NEG: a runs `--base` override moves the run dir but must NOT move the library home. Level: L0-DATA (pure path). Retires the s52 baseline id. | `test_storage_relocation::LibraryHomeStable::test_library_home_is_home_track_coach_library`, `test_storage_relocation::LibraryHomeStable::test_runs_base_override_does_not_move_library` |
| G-INV-6 | A stored `src_run_dir` is honoured wherever it points (old Ableton folder OR the new `$HOME` base) — never re-based or reconstructed; old and new runs coexist in one catalog. NEG: a reader never overrides a present stored path with a reconstructed one. Level: L0-DATA. Retires the s52 baseline id. | `test_storage_relocation::CatalogFallback::test_existing_src_run_dir_is_preferred`, `test_storage_relocation::DiskPresenceCheck::test_library_index_entries_use_src_run_dir_key` |
| G-INV-9 | The default `gc` leaves the library wholly intact — it prunes only an orphan run dir and keeps every deposited member's referenced run; removing a library member needs a separate explicit force. NEG: a plain `gc --apply` never deletes a referenced (library-member) run. Level: L0-DATA. Retires the s52 baseline id. | `test_cleanup::GcCommand::test_apply_deletes_only_orphan` |
| G-INV-13 | Cleanup operates on WHOLE runs, never individual measurements — so §E's per-axis measured/missing state is untouched: a pruned run is simply absent, the surviving runs keep their manifest. NEG: removing one version leaves the other versions + the index entry intact (whole-run granularity, not per-measurement). Level: L0-DATA. Retires the s52 baseline id. | `test_cleanup::RemoveCommand::test_remove_one_version_leaves_others_and_updates_index`, `test_cleanup::GcCommand::test_apply_deletes_only_orphan` |
| G-INV-17 | A successful `build` auto-deposits into the global library — the DEFAULT ingest, not a manual step; the only opt-OUT is the explicit `--no-deposit` flag (there is no opt-IN `--deposit`). NEG: deposit is never opt-in; a non-reference own run deposits by default. Level: L0-DATA (CLI contract + the `not args.no_deposit` gate in `_cmd_build`). Retires the s52 baseline id. | `test_pipeline_plan::AutoDepositIsDefault::test_no_deposit_is_an_opt_out_flag`, `test_pipeline_plan::AutoDepositIsDefault::test_no_opt_in_deposit_flag`, `test_library::ReferenceNotDeposited::test_own_run_still_deposits` |

## §H — Commands, library management & cleanup (SPEC §H → H-INV-1..7)

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
| G-INV-19 + H-INV-3 | `gc` classify keeps a run dir whose `run_meta` marks it `reference: true` (never lists it orphan), the same as a library-referenced run — protects the fingerprints `gen_reference_directions.py` regenerates directions from. | `test_cleanup::GcKeepsReferenceRun::test_reference_run_dir_not_orphaned` |
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
| H-INV-9 (round-trip) | `backup` then `restore --apply` reproduces original `library/` + `explore/` **and `config.json`** (backup captured it; restore now copies it back, even for a config-only snapshot — BUILT reopen 1.8.0) | `test_cleanup::RestoreCommand::test_restore_round_trip` |
| H-INV-9 (latest) | `restore latest` resolves to the most-recent valid snapshot | `test_cleanup::RestoreCommand::test_restore_latest_resolves_to_most_recent` |
| H-INV-9 (safety-backup) | `restore --apply` auto-takes safety backup before overwriting current state | `test_cleanup::RestoreCommand::test_restore_safety_backup_taken_before_overwrite` |
| H-INV-9 (--force) | `restore --force` skips the auto safety backup | `test_cleanup::RestoreCommand::test_restore_force_skips_safety_backup` |
| H-INV-9 (degraded warning) | Non-full snapshot restore prints degraded-library warning (previews silent / opens fallback / no compare) | `test_cleanup::RestoreCommand::test_restore_degraded_warning_for_non_full_snapshot` |
| H-INV-10 (dry-run default) | Bare `hard-reset` lists what would be removed (including backups) and removes nothing | `test_cleanup::HardResetCommand::test_hard_reset_dry_run_by_default` |
| H-INV-10 (single confirm) | `hard-reset --yes-wipe-everything` alone (without `--including-backups`) does not act | `test_cleanup::HardResetCommand::test_hard_reset_requires_both_confirms` |
| H-INV-10 (double confirm) | `hard-reset --yes-wipe-everything --including-backups` wipes all tiers including `backups/` | `test_cleanup::HardResetCommand::test_hard_reset_wipes_everything_incl_backups` |
| H-INV-10 (names backups) | `hard-reset` dry-run output mentions backups will be destroyed | `test_cleanup::HardResetCommand::test_hard_reset_names_backups_in_dry_run` |
| H-INV-7 | Ingest stays automatic — a successful `build` auto-deposits (the default), and `remove` is the deliberate counterpart for taking things back out. NEG: deposit is never a manual opt-in; removing one version leaves the others + index intact. Level: L0-DATA. Retires the s52 ext-namespace baseline id. | `test_pipeline_plan::AutoDepositIsDefault::test_no_deposit_is_an_opt_out_flag`, `test_cleanup::RemoveCommand::test_remove_one_version_leaves_others_and_updates_index` |
| H-INV-11 | The cleanup verbs form one reversibility ladder defined over the tiers; only the last rung is irreversible — `reset` keeps `backups/` (recoverable via `restore`), while `hard-reset` is the single point of no return that also wipes `backups/`. NEG: a `reset` never removes `backups/`; only the double-confirmed `hard-reset` does. Level: L0-DATA. Retires the s52 baseline id. | `test_cleanup::ResetRevisedCommand::test_reset_keeps_backups_dir`, `test_cleanup::HardResetCommand::test_hard_reset_wipes_everything_incl_backups` |
| H-INV-12 | Confirmation is graduated to match how much a verb can destroy — the prune tier is dry-run by default and acts on `--apply`; legacy `clean` reads the same way (its old `--yes` kept only as a silent alias). NEG: a bare `clean` previews and removes nothing; `--apply` and the legacy `--yes` both remove. Level: L0-DATA. Retires the s52 baseline id. | `test_library::CleanCommandConvention::test_dry_run_by_default_older_than`, `test_library::CleanCommandConvention::test_apply_flag_actually_removes`, `test_library::CleanCommandConvention::test_yes_flag_back_compat_still_removes` |

## §E-s31 — Bug fixes (build item E)

Three targeted bugs fixed; each owns tests asserting the REAL rendered artifact.

| code | rule (1-line) | owning test / status |
|---|---|---|
| E-BUG-1 | **No dead commented-out refRead/webPanel block in the rendered widget.** `id="refRead"` and `id="webPanel"` each appear EXACTLY ONCE. Root cause: the HTML comment at the `__REFREAD__` slot referenced `__REFREAD__` by name, causing the template substitution to embed a full copy inside the `<!-- … -->` block. Fix: removed `__REFREAD__` from the comment text so only the live slot is substituted. | `test_widget_render::NoDeadRefReadComment::test_refread_appears_exactly_once`, `::test_webpanel_appears_exactly_once`, `::test_no_html_comment_contains_refread_id` |
| E-BUG-2 | **`char` chip has a visible legend explaining it = 'Character axis — assessed without loudness weighting'.** The chip appears on per-row items in the refRead bars (only a hover tooltip per item); a legend block at the bottom of the refRead panel provides the visible explanation. Investigation: legend was already present at `build_widget.py:2586` — no code change needed; test added as regression guard. | `test_reference_read::CharLegend::test_char_legend_explains_the_chip`, `::test_char_chip_has_tooltip` |
| E-BUG-3 | **Catalog 'leans toward' direction links navigate to the track's widget focused on the #refRead section (D-INV-28), not `href="#"`.** Fix: `_lean_cell` now accepts `widget_href`; emits `<widget_href>#refRead`; `_row` passes the resolved `href`. Fallback (no widget): `#refRead` in-page anchor (never bare `#`). | `test_catalog::DirectionLinkIsReal::test_direction_link_href_is_not_dead`, `::test_direction_link_points_to_refread_anchor`, `::test_rendered_catalog_direction_link_not_dead` |

## §A-metre — Arrangement metre changes (SPEC §A "metre changes")

Owned by `tests/test_parse_als.py`.

| code | rule (1-line) | owning test |
|---|---|---|
| METRE-1 | `_decode_ts_enum(201)` returns "4/4" | `test_parse_als::TimeSigDecoder::test_4_4` |
| METRE-2 | `_decode_ts_enum(309)` returns "13/8" | `test_parse_als::TimeSigDecoder::test_13_8` |
| METRE-3 | `_decode_ts_enum(404)` returns "9/16" | `test_parse_als::TimeSigDecoder::test_9_16` |
| METRE-4 | Decode/encode round-trip for 4/4, 3/4, 7/8, 9/16, 13/8, 6/8, 5/4, 11/16 | `test_parse_als::TimeSigDecoder::test_roundtrip_various` |
| METRE-5 | Parsing the committed synthetic .als yields `time_sig_changes` with 9/16, then 13/8, then 4/4 as ordered subsequence | `test_parse_als::MetreChangesFromAls::test_order_9_16_then_13_8_then_4_4` |
| METRE-6 | `time_sig_changes` beats are ascending | `test_parse_als::MetreChangesFromAls::test_beats_ascending` |
| METRE-7 | `time_sig_changes[*].time_s` ≈ beat × 60/bpm | `test_parse_als::MetreChangesFromAls::test_time_s_consistent_with_beat` |
| TEMPO-1 | The displayed tempo prefers the `.als` project tempo when present; audio-detection is the fallback (subharmonic-safe, e.g. 134 not 89) and also fills the vitals Tempo slot | `test_widget_contract::DisplayTempoPrefersAls` |
| TEMPO-2 | Arrangement tempo automation is parsed into `tempo_changes` [{beat, time_s, bpm}], deduped, seconds piecewise-integrated across the varying tempo; empty when the tempo is constant | `test_parse_als::TempoChangesFromAls` |
| TEMPO-3 | `tempo_changes` reach the widget vitals (so the timeline marks them) and the base tempo fills the Tempo slot | `test_widget_render::TempoChangesReachVitals` |

## §I — Visual design system (SPEC §I → DS-INV-1…14)

Movement 1 (landed): the single token source + colour ladder/drift. Guarded at source-of-shipped-CSS
level by `tests/test_design_tokens.py` (the CSS is emitted verbatim from `build_widget.TEMPLATE`).

| code | rule (1-line) | owning test / status |
|---|---|---|
| DS-INV-2 | Catalog PALETTE shared roles are byte-equal to the widget `:root` (no re-drift; `line`/`ink` re-synced). | `test_design_tokens::test_catalog_palette_matches_widget_root` |
| DS-INV-3a | `--ink-dim` is defined in the widget `:root` (and catalog copy). | `test_design_tokens::test_ink_dim_token_defined` |
| DS-INV-3b | The 8 near-white + 2 drift raw hexes (#eef1f8/#cfd6e6/#cdd5e6/#c3cbdc/#aab3c7/#a0a8bc/#8b93a7 + #ffb13f→warn, #6fdfb8→good) are tokenised in the CSS rules (token defs excepted). | `test_design_tokens::test_ladder_and_drift_tokenised_in_css` |
| DS-INV-7c | The guard is by LOCATION: stem-colour arrays + the canvas meter label keep their raw hex (data-viz untouched). | `test_design_tokens::test_stem_and_canvas_literals_untouched` |
| DS-INV-2/3 (browser) | The semantic tokens RENDER, not just exist in text: `--good/--warn/--bad` resolve at `:root` at runtime AND reach the elements that wear them — `.modebadge.full` and the confirmed `#webPanel .rn-trait-glyph` compute `rgb(70,211,154)` = --good. NEG: a resolved token is never '' (dropped) and the badge never falls back to default `rgb(0,0,0)` (cascade override). Closes the N16 level-gap (s52): design tokens were tested ALL-STRING, blind to a runtime colour break. | `test_headless_render::DesignTokenColourRendered` (L3-BROWSER, s52) |
| DS-INV-4 | The UI red role is the `--bad` token (defined + resolves at `:root`); the magma/data reds — stem/canvas literals like kick `#ff5d73` — stay RAW in the gradient, never tokenised. NEG: a data-viz red is never rewritten to `var(--bad)`. The UI-red *application* to a rec-card stripe lands later with DS-INV-6 (deferred). Level: L0-token (the mapping) — the runtime `--bad` resolution is proven at browser by DS-INV-2/3 (browser) above. Retires the s52 ext-namespace baseline id. | `test_design_tokens::test_stem_and_canvas_literals_untouched`, `test_headless_render::DesignTokenColourRendered::test_semantic_tokens_resolve_at_root_in_browser` |
| §I.10 ×viewport (§D refs) | The §D reference panel `#refPanel`, its nested read `#refRead`, web notes `#webPanel` and the up-to-three `.reftab` selector stay within the viewport when narrow — right edge inside the window, no internal horizontal scroll, no tab-row spill. Composes the §D reference surfaces across the **viewport** axis, which §I.10 previously named only for the recs grid + segmented control + cards (pass-3 composition, s56). The harness clamps the effective viewport to ~500 px min, so the guard asserts against the returned `innerWidth`. Level: **L3-BROWSER**. | `test_headless_render::RefReadSurfacesRendered::test_ref_panels_stay_within_viewport_when_narrow` |
| DS-INV-9 (panel slice) | spacing split — `--gap` (within a group) vs `--rhythm` (between sections). **PANEL-RHYTHM SLICE BUILT (s57, 2026-07-05):** `:root` defines `--gap:16px` + `--rhythm:28px`; every top-level `.tc-panel` uses `margin-bottom:var(--rhythm)`, sub-panels nested inside ANY container panel (`#evidence`, and `#refPanel` since the D-INV-36 merge — the rule is structural, not per-id) use `margin-bottom:var(--gap)`, so the **inter-panel gap is strictly LARGER than the intra-panel gap** (fixes the measured 24<30 inversion). Old per-id overrides (`#webPanel{margin:10px 0 0}`, `#evidence,#catalog{margin:24px 0 0}`) removed. Level: **L3-BROWSER** (measured `getBoundingClientRect` gaps, invisible to string tests). | `test_headless_render::PanelGapHierarchy::test_inter_panel_gap_exceeds_intra_panel_gap` (L3-BROWSER, s57) |

Deferred (next movement — surface named, not yet coded):
| code | rule (1-line) | lands with |
|---|---|---|
| DS-INV-6 | rec-card left stripe renders a `bad`/red variant for a bad-severity card. | §1 cont. — rec-card CSS (`build_widget.py` `.rec` block) + a browser test |
| DS-INV-5 | colour-drift hexes map to tokens: `#6fdfb8 → --good` · `#ffb13f` (reference star) `→ --warn` (matches SPEC §I DS-INV-5). Category IDENTITY backgrounds are NOT derived — they are `_CAT_COLORS` literals (Mix `#5b6472` / Balance `#7a6cab` / Character `#c08a3e`, `build_widget.py:68`), left as a categorical group like the stem colours (⟨DECIDE DS-4⟩ RECONCILED s43; the old `#3a40…` "derive from --panel2/--line" assumption was WRONG — those hexes don't exist). | §I design-tokens — `test_design_tokens` (shared-role token byte-equality) |
| DS-INV-12 | every `border-radius` ∈ {10,14,18,20}; 6/8/9/11/12 snap. | §5 radii pass + browser test |
| DS-INV-10 | motion tokens `--dur-fast/--dur-base/--ease` replace `.12s/.15s`. | §3 |
| DS-INV-11 | one state ladder (rest/hover/focus/active/selected/disabled). | §4 |
| DS-INV-13 | one segmented control from `.seg`/`.viewtoggle`/`.reftabs`; selected = `--wob` fill. | §6 + browser test (new selected look) |
| DS-INV-8 | recs grid `auto-fill minmax`, cap 2; REPLACES s34 container-query; column-count tests updated. | §2 — update `test_headless_render` recs rows |
| DS-INV-9 (broad) | The BROADER normalisation of the remaining ~13 raw `gap:` literals (2–20 px) inside components to the `8/12/16` scale stays **POST-1.0 (deferred, F5)** — a design/taste call (which of 5/6/7 px becomes 8 px is a taste decision), not done in the panel slice (the panel slice itself is BUILT — see its row in the live §I table above). | POST-1.0 §I.2 spacing-token design pass — normalise the remaining literals (a design/taste call), then a `test_design_tokens` guard |
| DS-INV-14 | typography fractional sizes fold into `--fs-1..4`; weights ⟨DECIDE DS-1⟩ still open. | §8 audit |
