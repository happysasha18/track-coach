# track-coach — ARCHITECTURE (node map for the test rework)

> **Why this file exists.** livespec E-5: the test matrix is "organized by **architecture node × spec
> fact** once the architecture doc exists." It didn't exist — the matrix was organized by SPEC section
> only, so we could not ask "is every architecture node tested, and at the right *level*?" This doc names
> the nodes so that question becomes answerable. Authored s52 (2026-07-04) as the foundation of the pre-1.0
> test-suite rework (ROADMAP row 4 / NEXT_STEPS §4).
>
> **How to read.** A *node* is one coherent code responsibility. Each node names: its job, the owning
> code (verified `file` — grep/ls s52), the SPEC facts it implements (verified headers), and the test
> file(s) that currently exercise it. The node→test mapping here is the AUTHORED expectation; the s52
> inventory (`data/test_coverage_inventory_s52.md`) is the measured reality it is reconciled against.
>
> **Pin freshness:** every `file:line` pin re-verified 2026-07-05 (s57 adoption pass, after the 1.0.2
> edits shifted `build_widget.py` — 7 pins corrected, 0 broken). Re-verify pins whenever a commit
> touches a pinned file; a drifted pin is a silent lie.
>
> **Test LEVELS (the axis the rework is really about).** From the s34 scheme, formalized:
> - **L0-DATA** — pure data/logic/filesystem, no HTML. Right level for measurement/persistence facts.
> - **L1-STRING** — assertIn/regex on the rendered HTML *text*. Cheap; blind to how a browser renders it.
> - **L2-NODE** — JS extracted from the widget and run in node (player/view logic). Right for JS behaviour.
> - **L3-BROWSER** — headless Chrome renders the real artifact; DOM + computed style asserted.
>
> **Level-correctness rule (CLAUDE.md + livespec):** any **visibility / layout / colour** fact MUST be
> tested at **L3-BROWSER**. The same fact tested only at L1-STRING is *covered-but-at-the-wrong-level* —
> a **level-gap** (s34 "HIGH risk"), and the class of hole that shipped the two visible bugs before s34.

---

## The 8 layers, top to bottom

```
 IN: audio file (+ optional Ableton .als)
  │
  ▼
 L1  SIGNAL ANALYSIS        audio → measurements            N1  N2  N3  N4  N5  N6
 L2  PROJECT PARSING        .als → arrangement/automation   N7
 L3  CREDIBILITY            measurements → guarded claims    N8
 L4  REFERENCE & SIMILARITY you vs a direction / your library N9 N10 N11
 L5  WIDGET RENDER          claims → interactive HTML        N12 N13 N14 N15 N16 N17
 L6  ORCHESTRATION          run a build end-to-end + gate it N18 N19
 L7  CATALOG & LIBRARY      persist runs, render the catalog N20 N21 N22
 L8  GUARDRAILS / INFRA     the nets that hold the above     N23 N24
  │
  ▼
 OUT: one deposited widget + the global catalog
```

---

## L1 — Signal analysis (audio → measurements)

| Node | Job | Owning code | SPEC facts | Current tests |
|---|---|---|---|---|
| **N1** | Core arc — energy/brightness/density curves, the "where does it get boring" plateau | `analyze_core.py`, `analyze_detail.py` | §A, §B.10 | test_credibility (arc facts), — |
| **N2** | Stem separation (Demucs) + web-playable stems | `separate.py`, `make_web_stems.py` | §A (stems) | (indirect via fixtures) |
| **N3** | Per-stem measurements — run the track tools on each stem (rhythm, self-sim, drums, notes) | `self_similarity.py`, `rhythm_quality.py`, `drum_breakdown.py`, `transcribe.py` | §B.11 | test_per_stem |
| **N4** | Frequency masking — name the exact cut spot, not the whole band | `masking.py` | §B.9 | test_credibility (masking) |
| **N5** | Stem → real-track character & the ONE plain label per stem | `map_stems.py` | §B.4–B.8 | test_credibility (labels) |
| **N6** | Fingerprints / self-similarity vectors | `fingerprints.py`, `self_similarity.py` | §A, §D.3 | test_similarity_columns (part) |

*Level expectation:* L0-DATA throughout — these produce numbers, no UI. A browser test here would be wrong.

## L2 — Project parsing

| Node | Job | Owning code | SPEC facts | Current tests |
|---|---|---|---|---|
| **N7** | Parse the `.als` — tracks, MIDI/audio clips, automation envelopes, locators, metre changes; pick the render offset | `parse_als.py` | §A (arrangement), §A-metre | test_parse_als, test_offset |

*Level expectation:* L0-DATA.

## L3 — Credibility (measurements → claims that never overreach)

| Node | Job | Owning code | SPEC facts | Current tests |
|---|---|---|---|---|
| **N8** | The credibility layer — never say more than the numbers support; name the PART not a template; freq-role from the analyzer; precise masking phrasing | `build_widget.py` claim assembly (`build_recommendations:1355`, `build_cards:1618`), `render_spec.py`, `track_analyzer.py` | §B.1–B.9 (CR-*/G-*) | test_credibility (93) |

*Level expectation:* mostly L0/L1 — the *claim strings* are data, but where a claim's **presence/absence per data-state** is a rendered fact it wants L1 at least, L3 where visibility depends on it.

## L4 — Reference & similarity

| Node | Job | Owning code | SPEC facts | Current tests |
|---|---|---|---|---|
| **N9** | Reference directions — the measured centroids you compare against | `gen_reference_directions.py` | §D.5, §D.10 | (data fixtures) |
| **N10** | Reference-notes DATA (curated web notes) + the standalone light-theme side-page that REUSES the N17 renderer — NOT the in-widget render itself (that is N17) | `build_reference_notes.py` (`build:198`), `data/reference_web_notes.json` | §D.10.2 side-page | test_reference_read, test_rich_panel |
| **N11** | Similar-in-your-own-library — the DJ column + click-to-scroll | `similarity_columns.py` | §F | test_similarity_columns |

*Level expectation:* N9 L0-DATA; N10/N11 are **rendered surfaces** → visibility/layout facts need **L3-BROWSER**.

## L5 — Widget render (claims → one interactive HTML) — `build_widget.py` (269 KB, the monster; sub-noded)

| Node | Job | Owning code | SPEC facts | Current tests |
|---|---|---|---|---|
| **N12** | Widget assembly & the element grid — which panel shows per view-state × data-state | `build_widget.py` `build_html:1983` (assembly), `build_story:1802` | §4/§5 | test_widget_render, test_widget_contract |
| **N13** | The synced player as a STATE MACHINE (play/seek/mute/solo, playhead) + CARD-CLICK NAVIGATION (s61): a card click seeks (when timecoded), opens closed ancestor `<details>`, scrolls the card's evidence-target panel into view and pulses IT (INV-48b/c/d/e); wiring stays scoped to `#recs .rec` (the map-panel note cards reuse the `.rec` class but are not recs — prover CN-8). SEAM with N15: the `ev` field in `D.recs` — N15 writes it, N13 reads it, format owned by SPEC INV-48a. + ARC→CARD BACKPOINTER (INV-49, 2026-07-05 late): a cue's click zone is its whole column on the arc canvas — `cueAt` is the one hit-test for band and column; a cue hit seeks to the cue's moment and lights its card via `flashRec`; away from cues the arc keeps plain click=seek. | `build_widget.py` `PLAYER_LOGIC:4071` (markers), card render `#recs`:3629, click wiring (post-gating block):4031, `cueAt`:3754, `flashRec`:3467 | §B.14, §B.13 INV-48b/c/d/e + INV-49a–d | test_player_logic (L2-NODE), test_headless_render (card nav + arc backpointer, L3) |
| **N14** | The view selector as remembered state (one global view, calm first use) | `build_widget.py` `VIEW_LOGIC:3432–3444` (markers) | §B.15 | test_view_ladder (L2-NODE) |
| **N15** | Card evidence ("based-on" line + the evidence-TARGET map: every rec key → the panel its evidence renders in, `REC_TARGET` beside `REC_BASED`, shipped as `ev` in `D.recs` — INV-48a) + the producer's read (artistic layer) | `build_widget.py` `build_cards:1639`, `build_recommendations:1375`, `REC_BASED:407`, `REC_TARGET:434`, `_read_html:2335` | §B.12, §B.13 incl. INV-48a | test_widget_render (part), test_credibility (REC_TARGET completeness) |
| **N16** | The visual design system — single token source, colour/layout/motion, 10 component contracts | `build_widget.py` CSS `<style>:2923`, `:root:2924` | §I (DS-INV-1..14) | test_design_tokens, test_headless_render |
| **N17** | In-widget reference panel display — since the D-INV-36 merge (s58) ONE container `#refPanel`: shared selector + nested centroid read + nested web notes (not the catalog); since s59 also the one-shot `?direction` ENTRY READER (D-INV-37 — reads the param once on load, activates the tab through the click path, scrolls the panel into view; never writes URL or store). SEAM with N20: the param format `?direction=⟨URL-encoded direction name⟩` — N20 writes it, N17 reads it, the format is owned by SPEC D-INV-37. | `build_widget.py` `_ref_read_html:2861`, `_refread_bars_html:2363`, `render_reference_read:2655`, `render_reference_notes:2457`, `_web_body_html:2583`; the entry reader is emitted with the panel inside `render_reference_read`, independent of tab count | §D.7, §D.10 display, D-INV-36, D-INV-37 (reader side) | test_reference_read, test_headless_render (incl. MergedReferencePanel, EntryFocus) |

*Level expectation:* N12/N16/N17 are **the** visibility/layout/colour nodes → **L3-BROWSER is mandatory**; L1-STRING here is the level-gap class. N13/N14 → L2-NODE (real JS). §I.9 already states "all at ≥ browser-rendered level."

## L6 — Orchestration (run a build end-to-end + gate completeness)

| Node | Job | Owning code | SPEC facts | Current tests |
|---|---|---|---|---|
| **N18** | Render pipeline — resolve inputs, run analysis, assemble the widget, register the run | `track_analyzer.py` (Runner/cmd_analyze), `render_run.py`, `render_spec.py`, `prerender_smoke.py` | pipeline, §E.4 | test_build_inputs, test_pipeline_plan, test_development_mode |
| **N19** | Run completeness — every measurement carries a state; a missing one is shown honestly, never faked | `completeness.py` | §E (RC-INV-1..12) | test_completeness |

*Level expectation:* N18 L0-DATA; N19 L0 for the state model, **L3-BROWSER** for "the widget shows the gap honestly."

## L7 — Catalog & library persistence

| Node | Job | Owning code | SPEC facts | Current tests |
|---|---|---|---|---|
| **N20** | The catalog page — one row per track (newest), signature ribbon, similarity columns, stale chip; direction links carry the one-shot entry pair `?direction=⟨enc name⟩#detailed` (writer side of the D-INV-37 seam — the reader is N17) | `catalog.py` (`_lean_cell:247`) | §6, §D10F, §F, D-INV-35, D-INV-37 (writer side) | test_catalog, test_catalog_columns |
| **N21** | Library CRUD — deposit, index.json, list/remove/prune, backup/restore, reset, gc, dereference | `library.py` | §G, §H | test_library, test_storage_relocation, test_cleanup |
| **N22** | Run-dir versioning — timestamped run folders, resume, catalog.json per run | `run_dir.py` | §G.0 | test_storage_relocation (part) |

*Level expectation:* N20 is a **rendered surface** → L3-BROWSER for its visibility/layout; N21/N22 L0-DATA (filesystem/persistence).

## L8 — Guardrails / infra (the nets that hold the rest)

| Node | Job | Owning code | SPEC facts | Current tests |
|---|---|---|---|---|
| **N23** | Guardrails — the whole-artifact completeness gate (every surface present + non-empty, composed across mode×view), spec-invariant traceability, the headless-Chrome harness | `guardrails.py`, `completeness.py`, `headless_check.py` | method gates, INV-GATE | test_completeness_gate, test_traceability, test_headless_render |
| **N24** | Common infra — shared helpers, env check, tag vocabulary | `_common.py`, `check_env.py`, `tags.py` | — | test_fixtures, test_tags |

*Level expectation:* N23 is the meta-net; its own tests must be honest (it is what catches the others).

---

## What this doc lets us finally ask (the rework questions)

1. **Every node has ≥1 owning test?** (a node with 0 tests is a bare hole.)
2. **Every rendered node (N10, N11, N12, N16, N17, N19-display, N20) has L3-BROWSER coverage of its
   visibility/layout facts** — or the STRING-only ones are the ranked level-gaps to lift.
3. **Every SPEC invariant projects to a matrix row pinned to the RIGHT level** (the 11 baselined
   ext-namespace gaps in NEXT_STEPS — DS-INV-4/9, G-INV-4/5/6/9/13/17, H-INV-7/11/12 — get real rows).
4. **Positive AND negative per fact** (livespec INV-6): every row states what the node does AND the
   regression it must never do.

The answers land in `data/test_coverage_inventory_s52.md` (measured) → reconciled here → ranked gap list.
