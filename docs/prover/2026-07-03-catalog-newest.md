# Prover — CROSS-LINK: catalog newest-only per track (D-INV-35), 2026-07-03 (s50)

Mode: CROSS-LINK (surface add / behaviour change — the catalog granularity D-INV-35 against its named seams).
Not a FULL whole-spec prove (that is the 1.0 gate). Scope: the new "one row per track, newest version" rule
and every surface it touches.

Prior file check: `docs/prover/2026-07-02.md` — no unfolded must-fix rows carried forward that touch the
catalog granularity (that run was the "In short" panel removal). Nothing outstanding to reopen here.

## Seams examined

| # | Seam (surface × surface) | Finding | Verdict | Fold / action |
|---|---|---|---|---|
| 1 | Catalog row ↔ per-track plaque (older versions must survive) | Plaque (`build_widget.py:3259`, data from `run_dir.py:cmd_catalog`) enumerates ALL runs/versions per track from `index.json`; older versions removed from the catalog still appear there. Backpointer alive. | OK | none — recon confirmed; add a matrix row asserting a 2-version track's older version is in the plaque. |
| 2 | Catalog ↔ neighbour / own-track "scroll to that track's row" (D-INV line ~1365/1565, F click) | Was a row per version; now one row per track. The scroll-to-row JS must key on the **track slug** (`data-track`), not a version label, or a click could miss the (now single) row. | **RECONCILE** | step-3 check: confirm the scroll target uses `data-track`. If it keyed on version, fix. |
| 3 | Catalog ↔ similarity column §F (`_siblings`) — a listed neighbour links to a track's row | With newest-only, a sibling must resolve to a **track that has a visible (newest) row**. A sibling pointing at an older version with no row = a dead scroll. | **RECONCILE** | step-3 check: confirm `_siblings` targets are TRACK slugs (one per track), and the scroll lands on the newest row. |
| 4 | Catalog reference/completeness ↔ E.4 "most-complete run" | D-INV-35 reads the newest version's most-complete run; E.4 is scoped to runs WITHIN a version → no conflict. Recorded design A (strict newest) in D-INV-35. | OK | none. |
| 5 | Page subtitle count (`catalog.py:539`, `n_versions`) | Subtitle says "N versions across M tracks"; with newest-only, showing N>rows is misleading. D-INV-35 now requires subtitle counts TRACKS (rows shown). | **CODE** | matrix row + code: subtitle reflects rows shown. |
| 6 | Reference / "other people's" catalog (D-INV-3, separate catalog) | Does it reuse `render_catalog_html`? If yes, newest-only applies uniformly (fine — reference tracks are audio-only, typically single-version). | **RECONCILE** | step-3 check: does the reference catalog share the render path? Low risk. |
| 7 | Single-version track (the common case) | One version → one row, unchanged. Two-version → one row (newest). Empty library → empty state unchanged. | OK | matrix rows for 1-version / 2-version / empty. |
| 8 | Stale "older analysis" chip (INV-12, tool-version staleness) | Orthogonal to audio-version; unchanged. A newest row can still be tool-version-stale and show the chip. | OK | keep existing `StaleWidgetFlag` test; not in scope. |

## ⟨DECIDE⟩ touched
- **D-25 (Simple shows the plaque chip?)** — NOT touched by this change (plaque chip is per-track widget, not
  the catalog row). Left open, unchanged.
- No new ⟨DECIDE⟩ introduced. The strict-newest choice (design A) is RESOLVED and recorded in D-INV-35
  (the owner approved newest-only; strict-newest is the natural reading, surfaced in the ship report).

## Must-fix folded: none new (design was authored with the seams in view).
## Reconcile items handed to step 3: #2 (scroll key), #3 (sibling target), #6 (reference catalog render path).
## Code/matrix items: #5 (subtitle), + the newest-only row assertion itself.
