# Fable independent 1.0-readiness audit — 2026-07-03

Independent pass by Fable (fresh eyes, no shared session state with the primary agent). Method: run the
suite, render the REAL artifacts (quick / full-Simple / full-Detailed / catalog) from the real run dirs,
probe them in headless Chrome, and re-derive every claim from code + rendered DOM. Nothing below is taken
from Claude's docs on trust — every finding carries the command I ran and its output.

Baseline confirmed by deed:

```
$ PYTHONPATH=scripts python3 -m pytest tests/ -q
735 passed, 4 skipped in 186.52s
```

Skips (re-run with `-rs` + grep): 2 × `tests/test_reference_read.py:461,476` ("Lazy Sparks run dir not on
this machine") + 2 × `tests/test_widget_render.py:472,479` (`@unittest.skip("PROPOSED INV-29/INV-30 …")`).
The COUNT matches the gate list. The EXPLANATION of two of them does not — see Finding 2.

Real renders produced for this audit (all at v0.9.28, none overwrote deposited artifacts):

```
$ python3 scripts/render_run.py ~/.track-coach/projects/Total_Reboot_-_Wobble_Drift/Total_Reboot_Wobble_Drift_v0.6.2 --out /tmp/tc_audit/wobble_full.html
FULL render — all required inputs present
$ python3 scripts/render_run.py ~/.track-coach/projects/Total_Reboot_Fragile/2026-06-18_0819 --out /tmp/tc_audit/fragile_quick.html   # mode=quick per run_meta.json
$ python3 scripts/render_run.py ~/.track-coach/projects/Total_Reboot_Lazy_Sparks_edit2026/2026-07-01_1423 --out /tmp/tc_audit/lazy_full.html
$ TRACK_COACH_LIBRARY=/tmp/tc_audit/lib python3 -c "…catalog.build_catalog()"   # on a COPY of ~/.track-coach/library
```

---

## Finding 1 — HIGH. The "Leans toward" reference column IS shipped and shows FALSE copy on quick rows. Claude filed it as "not built / no live impact" — wrong.

**Spec** (docs/SPEC.md:1368-1369): quick-only rows in the reference column read **"full analysis only"**
(D-INV-20 / D-INV-22), "never blank-implies-none".

**Shipped code** (scripts/catalog.py:259, inside `_lean_cell`, wired at :374 via `e.get('_leans')`,
populated at :709 by `SC.leans_toward_topk`):

```python
if not leans:
    return '<td class="c-sim c-lean"><span class="sim-none">no similar tracks</span></td>'
```

There is NO quick branch; `grep -n "full analysis only" scripts/catalog.py` → no matches.

**Rendered reality** (headless-Chrome probe of the real catalog):

```
{"name": "▶Total Reboot — Fragile", … "9:quick", "10:no similar tracks", "11:—"}
{"name": "▶Lazy Sparks", "similar": "Venetian Snares", …}   ← live coloured direction link
```

The column renders on every row TODAY, with live direction links (Lazy → Venetian Snares → `#refRead`,
D-INV-28 implemented). For quick-only Fragile the cell asserts "no similar tracks" — a computed-looking
claim when in fact quick mode never computed similarity (no fingerprint). That is exactly the
filled-implies-computed failure the spec's "never blank-implies-none" clause exists to prevent, live on
the user's screen.

**Where Claude went wrong.** `docs/prover/2026-07-03-audit-pass1.md` reconciliation: "§D reference column
(D-INV-22/25) → marked NOT BUILT in the matrix, so findings on it are CONDITIONAL on ship"; F1 status:
"reference column itself is deferred/not-built, so no live user impact yet"; gate-list items #8/#10 both
lean on that premise. The premise is refuted by the rendered catalog and by catalog.py:374/:709. The
TEST_MATRIX:261 hedge ("cell text: not built") hides that a WRONG interim cell text is built and shipping.

**Fix**: one branch in `_lean_cell` (quick-only ⇒ "full analysis only") + a test row. Small, but it must
move from "deferred" to the pre-1.0 list — it is live false copy.

---

## Finding 2 — HIGH. The two "Lazy Sparks" skips are a STALE PATH, not missing data. Real-data coverage is silently disabled on the one machine that has the data.

tests/test_reference_read.py:458 pins:

```python
LAZY_RUN_DIR = … / "Total_Reboot_Lazy_Sparks_edit2026" / "2026-06-20_2100"
```

Disk (verified): `ls ~/.track-coach/projects/Total_Reboot_Lazy_Sparks_edit2026/` → `2026-07-01_1423`,
`latest`. The pinned dir does not exist → both tests skip forever, on every machine, including this one.

I ran the skipped assertions against the real dir:

```
$ python3 -c "… FP.fingerprint_from_run_dir('~/.track-coach/projects/Total_Reboot_Lazy_Sparks_edit2026/2026-07-01_1423') …"
dir exists: True
fingerprint: True
lean: Venetian Snares
Venetian in refread html: True | Leans toward: True
```

They PASS. The coverage exists; the tests just never run.

**Where Claude went wrong.** `data/audit_1.0_s50.md:26`: "The Lazy Sparks skips are due to absent real run
data on this machine" — false by deed. The gate list blesses the 4 skips as "the exact expected set". Two
of the four are a bug, not an expectation. The playbook rule is "green = zero failures AND the skip-set is
exactly the expected list" — a skip-set that contains a stale-path skip is not the expected list, it only
looks like it. This is precisely the "silent breakage" class the owner fears: the catalog displays
"Venetian Snares" for Lazy Sparks today, and the two tests that pin that exact user-visible fact to real
data have been off since the run dir was re-analysed.

**Fix**: resolve the run dir dynamically (the `latest` symlink is right there) or update the pin; the tests
go green immediately.

---

## Finding 3 — HIGH (mechanism). The coverage-matrix's central claim is CONFIRMED, and I constructed the live failure it predicts: in QUICK mode a visible collapsible opens to NOTHING and no test can catch it.

**Claim verified in code** (tests/test_completeness_gate.py): all four fixture builders pass `mode="full"`
(lines 334, 346-347, 403); `USER_SURFACES` lines 88-89 register `refRead`/`webPanel` as
`DEFERRED, gated_by: None`; `test_CONV_every_registry_entry_has_gate_test` explicitly `continue`s past
DEFERRED (line 1168-1169). The gate never builds a quick widget. `test_headless_render.py`'s only quick
browser test (`QuickModeRefReadAbsent`, :541) asserts ABSENCE of one element — no quick non-emptiness
anywhere. `test_view_ladder` checks quick presence/absence by regex on source, not rendered emptiness.

**The constructed case, in the REAL shipped-shape artifact** (probe of fragile_quick.html):

```
#evidence: DETAILS, visible: true, openHeight: 71px (= summary only)
  SUMMARY  "Evidence & detail — the project arrangement, automation, ste…"  visible
  #arrPanel  visible:false h:0     #autoPanel visible:false h:0
  #mapPanel  visible:false h:0     #rhyPanel  visible:false h:0
  #notePanel visible:false h:0
```

A quick-run user sees a collapsible promising "the project arrangement, automation, stem↔track map, rhythm
and transcribed notes", clicks it, and gets an empty box. Every test in the suite is green while this
renders. This is the completeness-gate philosophy's own red condition ("an opened `<details>` with no
body") escaping through the gate's mode="full"-only coverage.

**Bonus registry drift**: `USER_SURFACES` says refRead "appears ONLY when a reference aim is set; not
required in standard render". False. In the real Wobble FULL render, `#refRead` is ALWAYS emitted and
VISIBLE in Detailed with a placeholder-only body:

```
refRead: <summary>You vs your closest match</summary><p class="refread-hdr" …>No similar tracks</p>
vis: true, open: true
```

So the two "DEFERRED" surfaces are in the standard shipped render — visible, capable of being
placeholder-empty, and exempt from the gate by their registry label.

**Verdict on the coverage matrix (data/coverage_matrix_s50.md)**: accurate, including its own-fault
section. Its proposed fix (run the DOM-scan gate on Q/FS/FD; real gate methods for refRead/webPanel;
per-config empty-open-collapsible scan) is the right ROOT fix. What's wrong is that this fix did NOT make
the 1.0 gate list — see Finding 6.

---

## Finding 4 — CONFIRMED (Claude right). The web panel contradicts D-INV-29 exactly as the gate list says.

SPEC (docs/SPEC.md ~:1458-1461): "The marks are compact — two glyphs and one footnote, never long per-row
labels. … No per-row 'web said · measured' tag strings."

Rendered Lazy Sparks webPanel (probe of lazy_full.html, real reference data, 2713 chars):

```
"…organized chaos★ measurement confirms"
"Hyper-fast tempo — 180–200+ BPM, breakcore speed | web says; our tracks don’t show it"
"Odd time signatures (notably 7/4) … | not measurable with our axes"
```

Every trait row carries a long pill; the spec bans exactly that. Gate item #1 (layout-only fix, keep all
content — ⟨D-30⟩ mandates showing the bottom tier) is correctly diagnosed and correctly scoped. The mockup
approach is right; note it is design-only, nothing built yet, so 1.0 still gates on it.

---

## Finding 5 — CONFIRMED (Claude right). D-INV-35 (catalog = one row per track, newest version) is what the code does, on real data.

- Code: `library.newest_reps` (scripts/library.py:238-242) on top of `group_versions` (newest-first);
  render loop takes `groups[track][0]` (scripts/catalog.py:417-423); sim fingerprints read the newest rep
  (catalog.py:656-659) — no blending.
- By deed: real index has 5 entries (Shared Memories twice); rendered catalog has **4 rows**; the Shared
  Memories row is the 2026-07-03_1315 run, labelled v2, href to the newest widget, delta ▲1.0 vs prior:

```
{"rows": 4, "tracks": ["…Wobble Drift", "…Fragile", "Lazy Sparks", "…Shared Memories (2026 ve"]}
{"name": "▶Total Reboot — Shared Memories…", "href": "…/2026-07-03_1315/analysis_widget_v0.9.27.html",
 "cells": [… "1:v2…", "2:2026-07-03 13:15", …]}
```

- Tests exist and are honest: `test_catalog.py` NewestOnlyPerTrack (lines ~198-217: one `<tr>`,
  newest `data-version`/`data-bpm`, subtitle counts tracks) though the literal marker "D-INV-35" appears
  only in TEST_MATRIX:269, not in the test file — cosmetic.
- No empty cells / dead links found on the catalog page (probe returned `emptyCells: []`, `deadLinks: []`).
- Widget completeness on the real FULL render: all 12 panels populated in both Simple and Detailed (probe:
  no zero-height visible canvases, no visible sub-30-char non-canvas panels except refRead per Finding 3),
  backlink live (`file://~/.track-coach/library/index.html`).

---

## Finding 6 — MEDIUM. The 1.0 gate list omits its own biggest mechanism fix, and item #9 mislabels the two §D panels.

`data/audit_1.0_GATE_s50.md` items 1-11 contain NO item for "run the completeness gate across Q/FS/FD +
gate refRead/webPanel" — the fix the coverage matrix itself derives from the only mechanism-level hole
found this session. Item #9 asks only for two §5 grid rows "mark DEFERRED" — but per Finding 3 these
surfaces render in the standard Detailed artifact; labelling them DEFERRED in the grid would encode the
same false condition that let them escape the gate. The quick #evidence empty-open case (Finding 3) has no
gate-list item either.

## Finding 7 — MEDIUM. One catalog row contradicts itself in domain language.

The Wobble row shows, side by side: "Leans toward" cell = **"no similar tracks"** while the adjacent
"Similar in library" cell lists **Lazy Sparks, Shared Memories**. The widget's refRead uses the same phrase
("You vs your closest match → No similar tracks") for direction-absence. "Similar tracks" is being used for
two different product concepts (reference directions vs library siblings); on this row the same page says
"no similar tracks" and lists two similar tracks. Violates the one-surface-one-name and domain-language
standing rules; needs one distinct phrase for direction-absence (this also folds into Finding 1's copy fix).

## Minor findings

- **render_run.py labels a QUICK run "PARTIAL render"** ("als, notes, or narrative absent") — quick is by
  design without those; the operator-facing label conflates "quick as designed" with "broken full". Output
  seen live on the Fragile render.
- **The vitals row is outside the self-closing net.** Real render shows 9 slots (incl. "Phase"); the gate's
  required set (test_completeness_gate.py test_2) checks 8 — the DOM-scan convergence covers `tc-panel`
  details only, so a new vital (or a vital going "—") is not self-caught. Same pattern that produced the
  refRead escape, one tier smaller.
- **Deposited artifacts are stale vs 0.9.28** (rows show "older analysis · v0.9.24/v0.9.27 → re-analyse").
  Consistent with PUSH HELD + the re-render-on-push rule; the stale chip works. Not a bug — just confirm
  the bulk re-render actually happens at push time.

---

## Verdict

**(a) Is the completeness validation trustworthy?** For FULL-mode panels — yes, genuinely strong: the
rendered⊆registry⊆gated convergence is real (I read the probe-injection proof) and the real full artifact
probes clean. As a WHOLE-product guarantee — **no, not yet**: it is full-mode-only by construction, the two
§D surfaces that DO ship in the standard render are exempted under a false "DEFERRED" condition, quick mode
has zero rendered-emptiness coverage (live empty-open #evidence collapsible today), the vitals row is
outside the self-closing net, and two real-data tests are silently disabled by a stale path while the fact
they pin is on the user's screen. The gate's green currently proves less than it appears to.

**(b) Must-fix before 1.0, in order:**
1. D-INV-22 quick cell copy — replace the false "no similar tracks" with "full analysis only" (+ test).
   Live wrong copy; smallest fix, largest honesty gain. (Finding 1)
2. Un-stale the Lazy Sparks test path (use `latest`) — restores 2 real-data reference tests that pass
   today. (Finding 2)
3. Parametrize the completeness gate across Q/FS/FD, give refRead/webPanel real gate methods with true
   conditions, add the per-config empty-open-collapsible scan (fixes quick #evidence and closes the class).
   Promote this onto the gate list. (Findings 3, 6)
4. Web panel D-INV-29 layout fix, variant A, as designed — plus the side-page parity test (gate items 1+6).
   (Finding 4)
5. One phrase for direction-absence, distinct from "Similar in library"; sweep widget + catalog. (Finding 7)
6. The gate list's hygiene items stand: DS-INV-5 dup (#2), naming (#3), traceability rows + widened
   guardrail (#4/#5), grid rows for refRead/webPanel — but labelled SHIPPED-Detailed, not DEFERRED (#9).

**(c) Where Claude was right / wrong.**
RIGHT: suite baseline (735/4, count and skip identity); D-INV-35 fully — code, tests, and the real render
all agree, the change composes cleanly; the webPanel↔D-INV-29 contradiction and its layout-only scoping;
the coverage matrix — accurate to the line, including its self-diagnosis; the hygiene items #2-#5.
WRONG: (i) "reference column not built / no live user impact" — it is shipped and rendering false copy on a
quick row today, which demotes F1/#8/#10 from "deferred" to live; (ii) "Lazy Sparks skips = data absent on
this machine" and "the 4 skips are the exact expected set" — two are a stale path over data that is present
and passing; (iii) filing refRead/webPanel as DEFERRED in USER_SURFACES/#9 when they render in the standard
Detailed artifact; (iv) leaving the coverage matrix's own root fix (gate across Q/FS/FD) off the 1.0 gate
list it was synthesized alongside.

The overall shape is sound — the artifacts render whole in full mode, the newest-only catalog change is
clean, and the fix list is short and bounded. But the pattern across Findings 1-3 is one class: **claims
about what is NOT built / NOT present were asserted from documents instead of from the rendered artifact**,
and each such claim hid a live surface. The cure is the project's own rule applied to the audit itself:
verify by deed, on the shipped render, per config.
