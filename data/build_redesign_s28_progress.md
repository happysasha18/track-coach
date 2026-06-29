# s28 reference-read redesign — build progress

Steps completed so far:

STEP 0 (2026-06-30): Progress file created.
STEP 1 (2026-06-30): VIEW_LOGIC_START/END block added to build_widget.py with resolveView/safeGetView/safeSetView pure helpers; applyView() wired for on-load (resolveView only, no write) and toggle (applyView+safeSetView); quick-mode bail kept; module.exports for node tests added.
STEP 2 (2026-06-30): tonalPanel moved BEFORE __REFREAD__ in TEMPLATE; new order is producer read → tonal balance → reference read → web panel; comment updated to reflect §D.10.3 order.
STEP 3a (2026-06-30): "phrase" field added to all facet entries in data/facet_confirmation.json (2-4 word human descriptions faithfully derived from web_facets_draft.md).
STEP 3b (2026-06-30): _web_panel_html() helper added; CSS rule body.simple #webPanel added; render_reference_read() updated to append web panel after refRead div for the focused direction.
STEP 4a (2026-06-30): Node test ResolveViewLogic added to tests/test_player_logic.py; extracts VIEW_LOGIC_START/END block from rendered HTML and runs 6 resolveView precedence cases in node.
STEP 4b (2026-06-30): ReadOrderTonalBeforeRefRead class added to tests/test_widget_render.py; asserts tonalPanel present and CSS gates present in every render.
STEP 4c (2026-06-30): ReadOrderWithRefRead + WebPanelRendering classes added to tests/test_reference_read.py; assert tonal before refRead, refRead before web, panel collapsed, summary, artist header, phrase+glyph, absent when no marks.
STEP 5a (2026-06-30): INV-31 row added to TEST_MATRIX.md under new §B.15 section; D-INV-29 and D-INV-30 rows updated with notes about read order + web panel tests.
STEP 5b (2026-06-30): TC_VERSION bumped from "0.9.0" to "0.9.1" in build_widget.py line 31.
STEP 5c (2026-06-30): CHANGELOG.md updated — [0.9.1] entry added at top with Added (global remembered view, web says panel) and Changed (reference read re-ordered) bullets.
STEP 6 (2026-06-30): Full suite run — 469 tests, OK (skipped=2, no failures). Node tests (ResolveViewLogic: 6 cases + PlayerStateMachine: 6 cases) all green. Also updated test_view_ladder.py HIDE_SIMPLE expected set + DATA_ABSENT_IN_QUICK + grid, test_widget_contract.py gated set, and test_reference_read.py web_pos search to use id="webPanel" instead of CSS-comment-matching string.
