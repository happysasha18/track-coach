# Pass 2 Worker Checkpoint
Date: 2026-07-05

## STATUS: done

---

## TASK 1 — Full test suite run

Command:
```
cd /Users/sashaabramovich/.claude/skills/track-coach && python3 -m pytest -q 2>&1 | tail -40
```

Raw output (last 40 lines):
```
........................................................................ [  9%]
........................................................................ [ 18%]
........................................................................ [ 28%]
........................................................................ [ 37%]
........................................................................ [ 47%]
........................................................................ [ 56%]
........................................................................ [ 65%]
........................................................................ [ 75%]
........................................................................ [ 84%]
........................................................................ [ 94%]
....................................ss.......                            [100%]
763 passed, 2 skipped in 211.71s (0:03:31)
```

Exit code: 0 (all green)

Result: **763 passed, 2 skipped, 0 failed**

No failures — `grep -E "FAILED|ERROR"` step not needed.

Skipped tests (from `python3 -m pytest -rs -q 2>&1 | grep -iE "SKIP"`):
```
SKIPPED [1] tests/test_widget_render.py:479: PROPOSED INV-30: long source path must wrap / middle-ellipsis + title-hover, not overflow
SKIPPED [1] tests/test_widget_render.py:472: PROPOSED INV-29: formalize source-file symmetry (audio shown ⇒ .als shown too)
763 passed, 2 skipped in 211.64s (0:03:31)
```

Both skips are PROPOSED invariants (INV-29, INV-30) — not yet accepted, intentionally skipped. Skip-set matches expected 2.

---

## TASK 2 — Matrix cross-reference: owning tests exist?

Grep command:
```
grep -oE 'test_[a-z_]+::[A-Za-z0-9_:]+' docs/TEST_MATRIX.md | sort -u
```

Raw extracted references (all unique file::Class and file::Class::method):
```
test_catalog::CatalogIsLocalIndex
test_catalog::CatalogNoDevSlugOnSurface
test_catalog::CatalogRowPlayer
test_catalog::CatalogRowPlayer::test_dead_play_button_gives_feedback
test_catalog::CatalogRowPlayer::test_exclusive_playback_one_row_at_a_time
test_catalog::CrossPageModeAgreement
test_catalog::DirectionLinkIsReal::test_direction_link_href_is_not_dead
test_catalog::FmtDate
test_catalog::LeanCellEmptyCopy
test_catalog::NewestOnlyPerTrack
test_catalog::NewestOnlyPerTrack::test_sibling_fingerprint_is_newest
test_catalog::NoResidualPlaceholder
test_catalog::ResponsiveTable
test_catalog::RunMetrics
test_catalog::StaleWidgetFlag
test_cleanup::AbletonTailScan::test_apply_removes_only_safe_leaves_real_runs
test_cleanup::AbletonTailScan::test_dry_run_reports_safe_and_real_correctly
test_cleanup::AbletonTailScan::test_missing_tco_dir_reported_as_missing
test_cleanup::AbletonTailScan::test_slug_dir_has_real_runs_positive
test_cleanup::BackupCommand::test_backup_additive_does_not_remove_existing_files
test_cleanup::BackupCommand::test_backup_atomic_no_partial_on_failure
test_cleanup::BackupCommand::test_backup_creates_snapshot_with_curated_tiers
test_cleanup::BackupCommand::test_backup_full_also_copies_projects
test_cleanup::BackupCommand::test_backup_list_prints_snapshots
test_cleanup::BackupCommand::test_backup_stamp_collision_gets_suffix
test_cleanup::GcAbletonTailsCommand::test_dry_run_does_not_remove
test_cleanup::GcCommand::test_apply_deletes_only_orphan
test_cleanup::GcCommand::test_dry_run_removes_nothing
test_cleanup::GcIgnoresBackups::test_gc_ignores_backups_dir
test_cleanup::GcKeepsReferenceRun::test_reference_run_dir_not_orphaned
test_cleanup::GcPlan::test_orphan_classified_correctly
test_cleanup::HardResetCommand::test_hard_reset_dry_run_by_default
test_cleanup::HardResetCommand::test_hard_reset_names_backups_in_dry_run
test_cleanup::HardResetCommand::test_hard_reset_requires_both_confirms
test_cleanup::HardResetCommand::test_hard_reset_wipes_everything_incl_backups
test_cleanup::PruneVersionsCommand::test_apply_does_not_delete_run_dirs
test_cleanup::PruneVersionsCommand::test_apply_keeps_only_newest
test_cleanup::PruneVersionsCommand::test_dry_run_removes_nothing
test_cleanup::PruneVersionsCommand::test_no_keep_flag_does_nothing
test_cleanup::PruneVersionsPlan::test_keep_1_drops_two_oldest
test_cleanup::RemoveCommand::test_dry_run_removes_nothing
test_cleanup::RemoveCommand::test_remove_does_not_delete_run_dir
test_cleanup::RemoveCommand::test_remove_one_version_leaves_others_and_updates_index
test_cleanup::RemoveCommand::test_remove_whole_track
test_cleanup::RemovePlan::test_remove_whole_track
test_cleanup::ResetApply::test_base_flag_overrides_root
test_cleanup::ResetApply::test_wipe_leaves_sibling_dir_untouched
test_cleanup::ResetApply::test_wipe_removes_projects_and_library
test_cleanup::ResetDryRun::test_dry_run_removes_nothing
test_cleanup::ResetRevisedCommand::test_reset_aborts_if_backup_fails
test_cleanup::ResetRevisedCommand::test_reset_auto_creates_safety_backup
test_cleanup::ResetRevisedCommand::test_reset_keeps_backups_dir
test_cleanup::ResetRevisedCommand::test_reset_no_backup_no_snapshot_requires_i_understand
test_cleanup::ResetRevisedCommand::test_reset_no_backup_with_existing_snapshot_does_not_require_i_understand
test_cleanup::ResetRevisedCommand::test_reset_no_backup_with_i_understand_wipes
test_cleanup::ResetRevisedCommand::test_reset_revised_wipes_explore_dir
test_cleanup::RestoreCommand::test_restore_degraded_warning_for_non_full_snapshot
test_cleanup::RestoreCommand::test_restore_dry_run_by_default
test_cleanup::RestoreCommand::test_restore_force_skips_safety_backup
test_cleanup::RestoreCommand::test_restore_latest_resolves_to_most_recent
test_cleanup::RestoreCommand::test_restore_round_trip
test_cleanup::RestoreCommand::test_restore_safety_backup_taken_before_overwrite
test_completeness::CentroidSkipsMissingMembers
test_completeness::CompareOverSharedAxesOnly
test_completeness::MissingIsNotZero
test_completeness::MissingIsNotZero::manifest
test_completeness::PartialRunIsAnError
test_completeness::RankingIsAxisCountFair
test_completeness::SharedAxisFloor::test_quick_vs_full_not_comparable
test_completeness::SignificanceHasUnknown
test_completeness::TooFewSharedIsNotComparable
test_completeness_gate::NoEmptyVisibleCollapsibleAcrossConfigs
test_completeness_gate::WholeArtifactCompletenessGate
test_completeness_gate::WholeArtifactCompletenessGate::test_21_auto_mute_approved_behavior
test_completeness_gate::WholeArtifactCompletenessGate::test_22_ref_read_absent_on_plain_full
test_completeness_gate::WholeArtifactCompletenessGate::test_22_ref_read_populated
test_completeness_gate::WholeArtifactCompletenessGate::test_23_web_panel_populated
test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_all_rendered_panels_are_registered
test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_every_registry_entry_has_gate_test
test_completeness_gate::WholeArtifactCompletenessGate::test_CONV_probe_scan_detects_unregistered
test_design_tokens::test_catalog_palette_matches_widget_root
test_design_tokens::test_ink_dim_token_defined
test_design_tokens::test_ladder_and_drift_tokenised_in_css
test_design_tokens::test_stem_and_canvas_literals_untouched
test_development_mode::DevelopmentMode
test_fixtures::GoldenRenderFromRealData
test_fixtures::GoldenRenderFromRealData::test_every_card_carries_a_based_on_line
test_headless_render::CatalogPageResponsive
test_headless_render::CatalogSemanticColourRendered
test_headless_render::DesignTokenColourRendered
test_headless_render::DesignTokenColourRendered::test_semantic_tokens_resolve_at_root_in_browser
test_headless_render::NearSilentStemIdentified
test_headless_render::NoRawStemNameOnAnySurface
test_headless_render::OmittedStemsAcknowledged
test_headless_render::QuickModeRefReadAbsent::test_refread_absent_in_quick_mode_rendered_dom
test_headless_render::RefReadBarsRendered::test_refread_bars_render_with_nonzero_width
test_headless_render::RefReadEvidenceMarksRendered::test_all_rendered_rows_have_nonzero_height
test_headless_render::RefReadEvidenceMarksRendered::test_star_marks_visible_in_detailed
test_headless_render::SimpleViewGatingBrowser::test_ref_panels_hidden_in_simple_visible_in_detailed
test_headless_render::SimpleViewGatingBrowser::test_stem_viz_hidden_in_simple_visible_in_detailed
test_headless_render::WebPanelReadableLayout
test_headless_render::WebPanelReadableLayout::test_sources_block_has_links
test_headless_render::WordingInvariants
test_library::CleanCommandConvention::test_apply_flag_actually_removes
test_library::CleanCommandConvention::test_dry_run_by_default_older_than
test_library::CleanCommandConvention::test_yes_flag_back_compat_still_removes
test_library::DepositAtomicity
test_library::ReferenceCleanup::test_dry_run_writes_nothing
test_library::ReferenceNotDeposited::test_banner_count_excludes_references
test_library::ReferenceNotDeposited::test_own_run_still_deposits
test_library::ReferenceNotDeposited::test_reference_run_refused
test_library::StoresBuildVersion
test_parse_als::FragileMeterChanges::test_beats_ascending
test_parse_als::FragileMeterChanges::test_order_9_16_then_13_8_then_4_4
test_parse_als::FragileMeterChanges::test_time_s_consistent_with_beat
test_parse_als::TimeSigDecoder::test_13_8
test_parse_als::TimeSigDecoder::test_4_4
test_parse_als::TimeSigDecoder::test_9_16
test_parse_als::TimeSigDecoder::test_roundtrip_various
test_per_stem::CandidateScore
test_per_stem::Divergence
test_per_stem::DivergenceCandidates
test_per_stem::PerStemCards
test_per_stem::Prominence
test_pipeline_plan::AutoDepositIsDefault::test_no_deposit_is_an_opt_out_flag
test_pipeline_plan::AutoDepositIsDefault::test_no_opt_in_deposit_flag
test_player_logic::PlayerStateMachine::test_mute_resolves_gains
test_player_logic::PlayerStateMachine::test_one_mode_at_a_time
test_player_logic::PlayerStateMachine::test_seek_clamps
test_player_logic::PlayerStateMachine::test_seek_preserves_transport_and_mix
test_player_logic::PlayerStateMachine::test_simple_resets_mix
test_player_logic::PlayerStateMachine::test_solo_resolves_gains
test_reference_read::CharLegend::test_char_legend_explains_the_chip
test_reference_read::ReadOrderWithRefRead
test_reference_read::ReferenceReadDetailedOnly::test_quick_mode_has_no_refread_block
test_reference_read::ReferenceReadMostSimilarFirst::test_divergence_grows_downward_most_divergent_is_last
test_reference_read::ReferenceReadTabSelector::test_nearest_tab_not_level_coloured
test_reference_read::WebPanelRendering
test_rich_panel::RenderReferenceNotesUnit
test_similarity_columns::LeansTowardCompleteness
test_similarity_columns::LeansTowardPicksNearestDirection
test_similarity_columns::RelativeLeanBuckets
test_similarity_columns::TopKBasics
test_storage_relocation::CatalogFallback::test_existing_src_run_dir_is_preferred
test_storage_relocation::CatalogFallback::test_open_href_falls_back_to_library_copy
test_storage_relocation::CmdCatalogHidesAbsentRows::test_absent_non_self_entry_is_hidden
test_storage_relocation::CmdCatalogHidesAbsentRows::test_counts_reflect_only_visible_rows
test_storage_relocation::CmdCatalogHidesAbsentRows::test_track_with_only_absent_runs_is_dropped
test_storage_relocation::CollisionDisambiguation::test_adding_als_reuses_slug
test_storage_relocation::CollisionDisambiguation::test_different_source_gets_slug_2
test_storage_relocation::CollisionDisambiguation::test_same_source_reuses_slug
test_storage_relocation::DiskPresenceCheck::test_library_index_entries_use_src_run_dir_key
test_storage_relocation::DiskPresenceCheck::test_missing_run_dir_is_skipped
test_storage_relocation::LibraryHomeStable::test_library_home_is_home_track_coach_library
test_storage_relocation::LibraryHomeStable::test_runs_base_override_does_not_move_library
test_storage_relocation::MigrateCommand::test_dry_run_changes_nothing
test_storage_relocation::MigrateWarning::test_banner_counts_outside_root_members
test_storage_relocation::RelocationDefault::test_base_flag_still_overrides
test_storage_relocation::RelocationDefault::test_default_base_is_home_projects
test_storage_relocation::RelocationDefault::test_run_dir_is_under_home_projects_when_no_base
test_storage_relocation::SeedFromOldIndex::test_old_index_entries_appear_in_new_index
test_view_ladder::CssGatingContract
test_view_ladder::LadderIsMonotonic
test_view_ladder::LadderIsMonotonic::test_grid_visibility_is_monotonic
test_widget_contract::CatalogPlaqueCSSContract
test_widget_contract::NoResidualPlaceholder
test_widget_contract::PanelsExist::test_producer_read_is_rendered_server_side_when_a_narrative_exists
test_widget_contract::SimpleViewGating
test_widget_render::AlsPanelsGateOnData
test_widget_render::CrossVersionPanelData
test_widget_render::NoDeadRefReadComment::test_refread_appears_exactly_once
test_widget_render::PlayerIsWired
test_widget_render::PlayerIsWired::test_card_click_pulses_the_graph
test_widget_render::PlayerIsWired::test_seek_keeps_playback_running
test_widget_render::ProducerReadRendersServerSide
test_widget_render::ReadOrderTonalBeforeRefRead::test_webpanel_css_gate_present
test_widget_render::SoloAndMuteAreMutuallyExclusive::test_simple_toggle_resets_the_mix
test_widget_render::SourceFileHeaderSymmetryAndReadability::test_long_source_path_readable
test_widget_render::SourceFileHeaderSymmetryAndReadability::test_source_file_symmetry
```

### File check — all 20 referenced files exist:
```
EXISTS: test_catalog.py
EXISTS: test_cleanup.py
EXISTS: test_completeness.py
EXISTS: test_completeness_gate.py
EXISTS: test_design_tokens.py
EXISTS: test_development_mode.py
EXISTS: test_fixtures.py
EXISTS: test_headless_render.py
EXISTS: test_library.py
EXISTS: test_parse_als.py
EXISTS: test_per_stem.py
EXISTS: test_pipeline_plan.py
EXISTS: test_player_logic.py
EXISTS: test_reference_read.py
EXISTS: test_rich_panel.py
EXISTS: test_similarity_columns.py
EXISTS: test_storage_relocation.py
EXISTS: test_view_ladder.py
EXISTS: test_widget_contract.py
EXISTS: test_widget_render.py
```

### Class-level check — all 103 class/func references resolve.

(Full RESOLVE list omitted for brevity — zero ORPHAN lines in that pass.)

### Method-level check — 1 orphan found:

```
ORPHAN: test_completeness::MissingIsNotZero::manifest
```

Proof (grep came up empty for `def manifest`):
```
$ grep -n "def manifest\|def test_manifest" tests/test_completeness.py
34:    def test_manifest_lists_only_measured_axes(self):
```

The matrix says `::manifest` but the actual method is `test_manifest_lists_only_measured_axes`. This is a naming mismatch in the matrix — the method exists under a longer name, but the matrix alias does not match any real pytest-discoverable node ID. It would fail if run as `pytest test_completeness::MissingIsNotZero::manifest`. The fact is confirmed: the class `MissingIsNotZero` exists at line 22; the method in question is at line 34.

Matrix row for this orphan (TEST_MATRIX.md line 209):
```
| RC-INV-2 | a run carries a completeness manifest; read it, not a sentinel | `test_completeness::MissingIsNotZero::manifest` ✓ |
```

### Summary table:

| Category | Count |
|---|---|
| Total unique file::Class refs checked | 103 |
| Resolved (class/func found) | 103 |
| Orphaned class/func | 0 |
| Total file::Class::method refs checked | ~110 |
| Resolved method refs | ~109 |
| Orphaned method refs | 1 (`test_completeness::MissingIsNotZero::manifest`) |

The single orphan is a matrix alias mismatch (the real method name is `test_manifest_lists_only_measured_axes`). The test itself runs and passes — only the matrix label is wrong.

---

## TASK 3 — Test file inventory

`ls -la tests/`:
```
total 1360
drwxr-xr-x  30 sashaabramovich  staff    960 Jul  5 14:01 .
drwx------  19 sashaabramovich  staff    608 Jul  5 15:35 ..
drwxr-xr-x  49 sashaabramovich  staff   1568 Jul  4 21:05 __pycache__
drwxr-xr-x   5 sashaabramovich  staff    160 Jun 20 16:00 fixtures
-rw-r--r--   1 sashaabramovich  staff   6653 Jun 22 16:39 test_build_inputs.py
-rw-r--r--   1 sashaabramovich  staff  39044 Jul  3 20:01 test_catalog.py
-rw-r--r--   1 sashaabramovich  staff   8625 Jul  3 20:07 test_catalog_columns.py
-rw-r--r--   1 sashaabramovich  staff  57308 Jul  2 14:22 test_cleanup.py
-rw-r--r--   1 sashaabramovich  staff   9094 Jun 25 15:16 test_completeness.py
-rw-r--r--   1 sashaabramovich  staff  75609 Jul  5 14:01 test_completeness_gate.py
-rw-r--r--   1 sashaabramovich  staff  74927 Jul  3 02:15 test_credibility.py
-rw-r--r--   1 sashaabramovich  staff   5903 Jul  2 23:41 test_design_tokens.py
-rw-r--r--   1 sashaabramovich  staff   4363 Jun 23 15:46 test_development_mode.py
-rw-r--r--   1 sashaabramovich  staff   7558 Jul  2 22:52 test_fixtures.py
-rw-r--r--   1 sashaabramovich  staff  71068 Jul  5 09:38 test_headless_render.py
-rw-r--r--   1 sashaabramovich  staff  24443 Jul  2 14:21 test_library.py
-rw-r--r--   1 sashaabramovich  staff   3078 Jun 18 08:15 test_offset.py
-rw-r--r--   1 sashaabramovich  staff   5565 Jul  2 18:07 test_parse_als.py
-rw-r--r--   1 sashaabramovich  staff  22585 Jul  1 19:07 test_per_stem.py
-rw-r--r--   1 sashaabramovich  staff  11039 Jul  5 09:46 test_pipeline_plan.py
-rw-r--r--   1 sashaabramovich  staff  10089 Jul  2 08:41 test_player_logic.py
-rw-r--r--   1 sashaabramovich  staff  54021 Jul  4 21:57 test_reference_read.py
-rw-r--r--   1 sashaabramovich  staff  18912 Jul  4 21:58 test_rich_panel.py
-rw-r--r--   1 sashaabramovich  staff  11559 Jun 29 16:26 test_similarity_columns.py
-rw-r--r--   1 sashaabramovich  staff  37238 Jul  5 09:46 test_storage_relocation.py
-rw-r--r--   1 sashaabramovich  staff   2951 Jun 19 15:18 test_tags.py
-rw-r--r--   1 sashaabramovich  staff  18649 Jul  5 09:50 test_traceability.py
-rw-r--r--   1 sashaabramovich  staff   8966 Jul  4 21:37 test_view_ladder.py
-rw-r--r--   1 sashaabramovich  staff  12459 Jul  4 21:38 test_widget_contract.py
-rw-r--r--   1 sashaabramovich  staff  38317 Jul  4 21:37 test_widget_render.py
```

`wc -l tests/*.py`:
```
     138 tests/test_build_inputs.py
     688 tests/test_catalog.py
     178 tests/test_catalog_columns.py
    1243 tests/test_cleanup.py
     193 tests/test_completeness.py
    1404 tests/test_completeness_gate.py
    1096 tests/test_credibility.py
     135 tests/test_design_tokens.py
      87 tests/test_development_mode.py
     135 tests/test_fixtures.py
    1284 tests/test_headless_render.py
     453 tests/test_library.py
      69 tests/test_offset.py
     147 tests/test_parse_als.py
     405 tests/test_per_stem.py
     220 tests/test_pipeline_plan.py
     201 tests/test_player_logic.py
    1056 tests/test_reference_read.py
     386 tests/test_rich_panel.py
     247 tests/test_similarity_columns.py
     739 tests/test_storage_relocation.py
      70 tests/test_tags.py
     382 tests/test_traceability.py
     161 tests/test_view_ladder.py
     211 tests/test_widget_contract.py
     628 tests/test_widget_render.py
   11956 total
```

`grep -rcE "def test_" tests/*.py | sort` (test method counts per file):
```
tests/test_build_inputs.py:16
tests/test_catalog.py:65
tests/test_catalog_columns.py:18
tests/test_cleanup.py:60
tests/test_completeness.py:22
tests/test_completeness_gate.py:42
tests/test_credibility.py:93
tests/test_design_tokens.py:9
tests/test_development_mode.py:7
tests/test_fixtures.py:9
tests/test_headless_render.py:51
tests/test_library.py:26
tests/test_offset.py:8
tests/test_parse_als.py:15
tests/test_per_stem.py:51
tests/test_pipeline_plan.py:20
tests/test_player_logic.py:12
tests/test_reference_read.py:70
tests/test_rich_panel.py:35
tests/test_similarity_columns.py:25
tests/test_storage_relocation.py:28
tests/test_tags.py:9
tests/test_traceability.py:6
tests/test_view_ladder.py:8
tests/test_widget_contract.py:16
tests/test_widget_render.py:44
```

Total test methods (sum of above): **766**
(Suite reports 763 passed + 2 skipped = 765 collected — the 1-method difference is likely a test method counted by grep that is skipped or in a base class not collected directly.)

26 test files, 11,956 lines total.

---

## STATUS: done
