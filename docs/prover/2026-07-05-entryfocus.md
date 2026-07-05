# Prover record — URL entry-focus wiring (D-INV-37), CROSS-LINK mode — 2026-07-05 (s59)

Previous record `2026-07-05-q5merge.md`: no unfolded must-fix rows (Q5-12 named THIS feature as the
out-of-scope hook — this landing closes it). Scope here: the new cross-page hand-off (catalog
direction-link → widget entry reader) against the named existing surfaces — the catalog lean cell
(D-INV-28), the merged reference panel + selector (D-INV-36 a–f), the view ladder / on-open precedence
(§B.15, INV-31), the Simple hide-set (INV-18/22), the completeness registry (INV-46).

| # | Finding | Verdict | Folded / rejected |
|---|---|---|---|
| EF-1 | Query-before-hash seam: the link now carries `?direction=…#detailed`; the shipped view reader must not choke on the query. VERIFIED in code: `resolveView(location.hash, …)` reads ONLY `location.hash` (`build_widget.py:3433`, substring match on "detail"/"simple") — the query never reaches it. | holds | verified by grep+read, no change needed |
| EF-2 | Single-direction case: with 1 shown direction there is NO tab bar and NO selector JS — but the spec promise (panel in view, Detailed) must still hold. Spec sentence covers it ("if the reference panel renders … falls back to the nearest"); the entry reader must therefore be emitted whenever the panel renders with ≥1 shown direction, not only when tabs exist. | must-fix (spec→code shape) | folded — reader emitted with the panel, independent of tab count; matrix row at browser level |
| EF-3 | Empty state ("no close direction yet"): no tabs, no bars — parameter must be ignored (no scroll, no focus). Spec states it explicitly. | holds | folded into spec sentence + negative-side matrix row |
| EF-4 | Old-widget degradation: deposited widgets without the reader get an inert `?direction` + honoured `#detailed` (shipped since §B.15). Note: the OLD `#refRead` anchor was actually broken for Simple-remembered users (anchor into a CSS-hidden panel) — the new scheme strictly improves the class. | holds | spec states "links degrade, never break" |
| EF-5 | Ephemeral-tab fence (D-INV-28): after entry, tab clicks must not write the URL. The view toggle DOES rewrite the hash via `replaceState` (JOB-2, shipped) — it preserves `location.search`, so `?direction` lingers inertly; a reload is a NEW entry and re-focuses — consistent with "one-shot per load". No contradiction with the not-in-URL rule (that rule is about TAB state; the view hash is §B.15's own shipped behaviour). | holds | noted; no change |
| EF-6 | Store fence (§B.15): entry must not write `tc_view` (hash-override path already never does — existing rows discharge the fence). | holds | fence discharged via existing §B.15/INV-31 rows |
| EF-7 | Registry (INV-46): no new panel id — behaviour only, no registry entry; bounds guardrail satisfied by D-INV-37. | holds | — |
| EF-8 | Direction-name identity: the SAME display name on both pages (one surface, one name); URL-encoded with `quote()` / decoded with `decodeURIComponent`. Names with spaces ("Venetian Snares") covered by an explicit test row. | holds | matrix row includes a spaced name |

Open ⟨DECIDE⟩ touched by these surfaces: none (DS-3/DS-4 untouched). No unfolded must-fix remains.

## Architecture lens (step 4, same session)

- D-INV-37 writer fact → N20 (`catalog.py` `_lean_cell:247`, pin from live grep); reader fact → N17
  (`render_reference_read:2655`, pin from live grep). One owner per fact — no double-ownership.
- Seam named in BOTH node rows: N20 writes `?direction=⟨enc name⟩#detailed`, N17 reads; format owned by
  SPEC D-INV-37. No node without spec backing; no speculative node added.
- EF-1's VERIFY closed: `resolveView(location.hash,…)` at `build_widget.py:3433` reads only the hash.

## MINOR-gate delta note (1.1.0 → 1.2.0)

The full 3-pass preventive audit ran TODAY for the 1.0 gate (`2026-07-05.md`, `-pass2.md`, `-pass3.md`);
this MINOR rides a delta walk on top of it (same precedent as 1.1.0's q5merge record): the delta touches
only the D-INV-28/36/37 seams — all walked above in CROSS-LINK; the matrix rows are derived (writer +
reader, negative sides present); composition across the VIEW axis is covered by the composed full-widget
test (entry pair ⇒ NOT `.simple`), the VIEWPORT axis is unchanged (no new layout — §I.10's existing
narrow-guard already runs on `#refPanel`), and the interaction reuses the D-INV-36b click path rather
than adding a second switching mechanism. No structural rewrite ⇒ no fresh FULL pass required.
