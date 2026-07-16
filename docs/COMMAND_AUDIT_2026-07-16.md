# track-coach — command audit (2026-07-16)

A Fable audit of every track-coach command: the CLI verbs (`library.py` ×14, `track_analyzer.py`
analyze/build, `run_dir.py` init/resume/catalog, `catalog.py` build) and the two skill commands
(`/tc`, `/tc-quick`). Each command was read against its code, SKILL.md, SPEC §G/§H, and its
invariants; every finding was then adversarially re-checked against the actual code before it counted.

**64 confirmed findings: 9 high · 30 medium · 25 low.** They collapse into a few root classes — fixing
each root clears many of the individual findings at once (the "fix the whole class" rule, not pointwise).

## The root classes (fix these, most collapse together)

### 1. Data-loss through non-atomic `index.json` + silent empty-library fallback 🔴
The single highest-value fix. `save_index` writes `index.json` in place (plain `write_text`, no
tmp-file + rename), and `load_index` catches a parse error and silently returns an EMPTY library. So a
kill mid-write corrupts the index, the next read shows an empty library, the next save persists the
loss — and then `gc` reclaims run dirs it thinks are unreferenced. The same non-atomic-write shape
also hits `aliases.json` and `run_meta.json`. **This one root drives findings across `deposit`,
`remove`, `clean`, `gc`, `build`, `run_dir init`, and `alias`.**
**Root fix:** an atomic write helper (write `.tmp`, `os.replace`) used by every index/marker write, and
`load_index` that FAILS LOUDLY (exits with the parse error) when the file exists but is corrupt, rather
than returning empty. One helper, one loud load, ~8 findings closed.

### 2. `gc` can delete the user's own files 🔴
The Ableton-tail sweep `rmtree`s a slug dir that holds only loose regular files (it only looks for
child *directories* when deciding "safe"), and it never checks its scan target is actually a
`track-coach-output/` dir — a malformed index entry or a careless `--scan-dir` points the destructive
classifier at an arbitrary user folder. This breaks H-INV-5 ("never touches non-track-coach files").
**Root fix:** treat ANY non-symlink entry other than `index.json` as disqualifying; require each scan
target's basename to be a known output-dir shape before touching it; add a loose-file test.

### 3. Both skill commands describe the deprecated pipeline 🔴
`commands/tc.md` and `commands/tc-quick.md` instruct the old hand-driven flow (`run_dir.py init` +
direct `build_widget.py`) that SKILL.md's one-command entrypoint explicitly forbids — while also saying
"Follow the skill exactly". On that path their promise "every build auto-deposits into the library and
rebuilds the catalog" is simply false (a silent no-op). `/tc-quick` also tells the agent to skip the
mix player the SPEC makes part of every quick run. **Root fix:** rewrite both command files onto the
SKILL.md one-command entrypoint; drop the false deposit/catalog claims or make them true on that path.

### 4. Destructive commands with a broken or missing guard 🔴🟠
Each is its own quick fix, same family (a preview/guard that does not hold):
- `clean --dry-run` is parsed but never read — `clean --apply --dry-run` deletes anyway. 🔴
- `reset --no-backup` accepts ANY `.backup_ok` snapshot including an empty one, so a populated library
  wipes unrecoverably without `--i-understand`. 🟠
- `restore <stamp>` joins the stamp onto `backups/` with no validation — a stamp with path separators
  escapes and restores from an arbitrary directory. 🟡
- `dereference --album-path "" --apply` matches every entry and empties the whole index. 🟡

### 5. Version / run selection correctness 🔴
- `prune-versions` orders by a dead `audio_mtime` key deposits never store, so "newest" silently means
  most-recently-*analysed* — it can delete the newest bounce and keep an older one.
- `run_dir resume` ignores slug-collision disambiguation and returns another track's newest run, so a
  quick→full upgrade co-mingles two tracks in one run dir (G-INV-2b: "never co-mingled").
- `restore` from a `--full` snapshot never restores the `projects/` scratch tier, breaking the H-INV-9
  round-trip, and suppresses the degradation warning as if it had.
- a bare `build`'s default backfill deletes a track's existing library entry before verifying the
  replacement deposit landed.

### 6. Catalog left stale after a mutation 🟠
`clean`, `dereference`, and `restore` mutate the index but do not regenerate the catalog (unlike their
siblings `remove`/`prune-versions`), leaving the visible Catalog page showing removed tracks with dead
links. One shared "rebuild catalog after a library mutation" step.

### 7. Doc-parity drift 🟡
A tail of undocumented or misdocumented flags/verbs: `--synthetic` documented on `build` but implemented
on `analyze`; `reset --hard` named in H-INV-10 but no such flag; `--title` omitted from the skill
commands' must-pass flags; several analyze/gc flags absent from SKILL.md. Cheap to reconcile once the
behaviour fixes above settle what the true surface is.

## Recommended order

1. **Root class 1 (atomic index + loud load)** — highest value, closes ~8 findings including data loss.
2. **Root class 2 (`gc` user-file guard)** — the one that can destroy files outside track-coach.
3. **Root class 3 (skill command files)** — the user-facing entry points are wrong today.
4. **Class 4 guards**, then **class 5 selection bugs**, then **6 (catalog rebuild)**, then **7 (docs)**.

Each is a code-vs-spec defect (the code diverges from a stated invariant), so each is derivable and
carries a red-first test. The full ranked list with per-finding evidence, failure scenario, and fix is
below.

## Full findings (ranked)


### 🔴 HIGH (9)

**[doc-parity] /tc and /tc-quick (skill commands)**  
Both skill commands instruct the deprecated hand-driven pipeline (run_dir.py init + direct build_widget.py) that SKILL.md's one-command entrypoint section explicitly forbids, while simultaneously saying 'Follow the skill exactly'.  
*Evidence:* commands/tc.md:15-21 ('Create the output folder with scripts/run_dir.py init --mode full', 'Pass --src-audio, --src-als ... to build_widget.py') and commands/tc-quick.md:10-18 ('analyze_core.py + analyze_detail.py', 'Build the widget with just --core and --detail') vs SKILL.md:39-42 ('is now ONE command. Do not hand-drive the individual steps below — they are the internals') and SKILL.md:71-72 ('invoke the pipeline through the entrypoint, not by pasting the step commands'). The sanctioned entrypoint is scripts/track_analyzer.py analyze/build (SKILL.md:52-64; track_analyzer.py:729-778), which neither command file mentions.  
*Fails when:* An agent triggered via /tc or /tc-quick reads the command file first, obeys its explicit step instructions, and hand-drives the internals — bypassing everything the track_analyzer entrypoint added (RC-INV-13f running/failed state stamping at track_analyzer.py:161-176, audio fingerprinting, draft tags, reference/synthetic markers at 219-224, narrative inheritance at 179-183).  
*Fix:* Rewrite both command files around the track_analyzer.py entrypoint: '/tc' = `track_analyzer.py analyze <AUDIO> [--als ...] --mode full` then `track_analyzer.py build --run-dir ... --title --verdict --mood-tags --style-tags`; '/tc-quick' = the same with `--mode quick`. Drop the run_dir.py/build_widget.py step instructions.

**[correctness] /tc and /tc-quick (skill commands)**  
The 'Library' paragraph in both commands promises 'Every build auto-deposits the widget into the global library and rebuilds the cross-version Catalog', but under the build_widget.py flow the commands instruct, no deposit or catalog rebuild ever happens — a silent no-op on the promised state change.  
*Evidence:* commands/tc.md:27-28 and commands/tc-quick.md:26-27 make the auto-deposit claim, while both files direct the build at build_widget.py (tc.md:21) / '--core and --detail' (tc-quick.md:16). Deposit and global-catalog regeneration live only in track_analyzer.py cmd_build (track_analyzer.py:559-572, `library.deposit_from_run` + `catalog.build_catalog()`); build_widget.py contains no call to deposit_from_run or build_catalog (grep returns nothing).  
*Fails when:* Agent follows tc.md verbatim: builds via build_widget.py, tells the user the run is in the library, offers `library.py catalog --open` — the catalog opens stale, missing the run just analysed. The deposit-boundary guards (G-INV-17 completeness, G-INV-18 reference, G-INV-21 synthetic, SPEC.md:2152/2160/2180) also never execute for the run.  
*Fix:* Point the commands' build step at `track_analyzer.py build --run-dir ...` (which deposits and regenerates the catalog), or state that deposit happens only via that entrypoint.

**[safety] library.py clean**  
The --dry-run flag is parsed but never read, so `clean --apply --dry-run` (or `--yes --dry-run`) actually deletes widgets and rewrites the index despite the explicit preview request.  
*Evidence:* scripts/library.py:1518 adds `c.add_argument("--dry-run", ...)` with help "preview only", but `_cmd_clean` (scripts/library.py:503-529) never references `args.dry_run` — line 510 computes `act = args.apply or args.yes` only. Reproduced: with a one-entry library, `library.py clean --all --apply --dry-run` printed "removed 1; 0 left.", unlinked the widget file, and emptied index.json.  
*Fails when:* A user takes an existing `clean --older-than 30 --apply` command and appends --dry-run to preview what it would do (exactly what the flag's help promises); the command deletes everything in scope instead of previewing. For a DESTRUCTIVE command this is a quiet over-deletion path.  
*Fix:* In _cmd_clean compute `act = (args.apply or args.yes) and not args.dry_run` — an explicit --dry-run must always win — or make --dry-run and --apply mutually exclusive via argparse (p.error on both).

**[safety] library.py deposit**  
Every deposit rewrites index.json non-atomically (plain write_text, no tmp+rename), and load_index silently resets a corrupt index to empty — so a kill mid-deposit can permanently erase the entire library catalog and then let gc delete previously-protected run dirs.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:285-287 save_index does `(root / "index.json").write_text(json.dumps(idx, ...))` with no temp-file/os.replace; deposit calls it at line 416 on every run (auto-deposit after every build, G-INV-17). library.py:280-282 load_index catches ValueError on a corrupt index and returns `{"entries": []}`. library.py:670-680 gc_plan builds its G-INV-10 'referenced' keep-set from that same load_index.  
*Fails when:* Process is killed (or disk fills) mid write_text during a routine deposit -> index.json is truncated. Next load_index silently returns an empty catalog; the next deposit saves an index containing only the new entry, making the loss permanent (all verdicts, src_run_dir pointers, tags, audio_sha gone; catalog empty). Worse: `library.py gc --apply` run after the truncation sees an empty referenced set and prunes every formerly-referenced run dir as an orphan — destroying stems/results the spec promises gc keeps (G-INV-9/10). This violates the crash-consistency expectation and the spirit of G-INV-11 (no half state).  
*Fix:* Make save_index atomic: write to `index.json.tmp` in the same dir, fsync, then os.replace onto index.json. Separately, make load_index fail loud (or fall back to a `.bak` written before each save) instead of silently coercing a corrupt index to `{"entries": []}` — at minimum print a warning and refuse destructive reads (gc/clean) on an unparseable index.

**[safety] library.py gc**  
The Ableton-tail sweep classifies a slug dir containing only loose regular files as 'safe' and rmtree's it, deleting user files H-INV-5 promises never to touch.  
*Evidence:* scripts/library.py:726-733 — _slug_dir_has_real_runs only returns True when a non-symlink DIRECTORY exists; loose files fall through invisibly. Its own docstring (line 723) says 'Safe' slug dirs contain ONLY dangling symlinks and index.json, and SPEC.md §H.2 H-INV-5 (~line 2409) promises the sweep 'never touches non-track-coach files (the user's audio/.als)'. The safe set is rmtree'd wholesale at library.py:1279-1280.  
*Fails when:* User drops a bounce ('mytrack-final.wav') or notes.txt into track-coach-output/<slug>/ which also holds a dangling latest symlink; `library.py gc --ableton-tails --apply` classifies the slug dir as empty/dangling-only and shutil.rmtree deletes the user's file with no listing of the file itself.  
*Fix:* In _slug_dir_has_real_runs (or a new classifier), treat ANY non-symlink entry other than index.json — file or dir — as disqualifying; only dirs whose real contents are exactly {index.json, dangling symlinks} are 'safe'. Add a test with a loose file in the slug dir.

**[correctness] library.py prune-versions**  
prune-versions orders versions by a dead 'audio_mtime' key that deposits never store, so 'newest' silently means most-recently-ANALYSED, and the command can delete the newest audio bounce while keeping an older one.  
*Evidence:* scripts/library.py:851 `okey = rep.get("audio_mtime") or rep.get("stamp", "")` — but the entry builder run_metrics (scripts/library.py:188-210) maps `audio_sha` from meta yet never maps `audio_mtime`, and deposit (scripts/library.py:401-413) adds nothing else, even though the analyzer computes it (scripts/track_analyzer.py:350 `"audio_mtime": int(st.st_mtime)`). SPEC.md:1367 promises ordering 'by audio mtime / stamp', and the tests fabricate entries WITH audio_mtime (tests/test_catalog.py:76), so the intended primary key exists everywhere except real deposited entries. Bonus latent crash: audio_mtime is an int while the stamp fallback is a str, so a library mixing entries with and without it would raise TypeError at the sort (library.py:853).  
*Fails when:* User bounces v2, analyses it, then re-runs analysis on the OLD v1 file (e.g. a rebuild or full-mode upgrade). v1's rep now carries the newest stamp, so `prune-versions --keep 1 --apply` sorts v1 as 'newest', keeps it, and permanently deletes every entry and widget of the actually-newest bounce v2.  
*Fix:* Store audio_mtime on the entry (add `"audio_mtime": meta.get("audio_mtime")` in run_metrics) and make the sort key type-stable (normalise to a comparable tuple, e.g. (has_mtime, mtime_or_0, stamp)) in both prune_versions_plan and group_versions so pruning and the catalog order by bounce time as SPEC.md:1367 states.

**[spec-parity] library.py restore**  
restore never restores the projects/ scratch tier from a --full snapshot, breaking the H-INV-9 round-trip promise, and it even suppresses the degradation warning for full snapshots as if projects/ were coming back.  
*Evidence:* library.py:1021-1023 — `is_full = (snap_dir / "projects").exists()` but `tiers_to_restore = [src for src in (snap_dir / "library", snap_dir / "explore") if src.exists()]` never includes projects/; the restore loop at 1066-1070 copies only those tiers, and `is_full` is used solely at 1045 to skip the WARNING. SPEC.md:2434-2438 (H-INV-9): "Round-trip holds: restoring a snapshot reproduces exactly the tiers backup captured … a --full snapshot restores those too." SKILL.md:863: "A --full snapshot restores those too." No test covers full-snapshot restore (tests/test_cleanup.py:815-952 has none).  
*Fails when:* `backup --full` → `reset --yes-wipe-everything` → `restore latest --apply`: projects/ (stems, previews, run JSONs) stays gone, previews are silent and reference-compare is dead — yet because is_full is true the WARNING at line 1045-1047 is skipped, so the output tells the user the restore was complete.  
*Fix:* Add `snap_dir / "projects"` to the tiers_to_restore candidates (it only exists in full snapshots, so non-full behaviour is unchanged); keep the warning keyed on is_full as now. Add a round-trip test for a --full snapshot.

**[correctness] run_dir.py init/resume/catalog**  
resume ignores the slug-collision disambiguation entirely: it resolves the plain slug and returns another track's newest run, so a quick-to-full upgrade co-mingles two tracks' data in one run dir (G-INV-2b: 'never co-mingled').  
*Evidence:* scripts/run_dir.py:309-312 — cmd_resume does `root = track_root(args, audio)` where track_root (run_dir.py:84-85) is just `base / slugify(audio.name)`; no source-identity check and no walk of the `-2`/`-3` slots that _resolve_slug (run_dir.py:181-204) creates. Reproduced: after `init a/My_Track.wav` (slug My_Track) and `init b/My_Track.wav` (slug My_Track-2), `resume --audio b/My_Track.wav` prints run_dir `.../projects/My_Track/2026-07-16_0909` — track A's run.  
*Fails when:* Two different tracks both named My_Track.wav; the second was correctly forked to My_Track-2 at init. The SKILL.md quick-to-full flow (SKILL.md:244-252) then runs `resume --audio <B>` to reuse cached JSON, gets track A's run dir, points OUT_DIR at it, and writes B's Demucs stems/masking into A's run — one run dir now holds two tracks' results, and the rebuilt widget mixes them.  
*Fix:* In cmd_resume, resolve the slug the same way init does: walk base_slug, base_slug-2, ... comparing _stored_identity(root) against str(audio.resolve()); return the matching root's newest run, and report 'no earlier run' when no slot's identity matches (an unreadable identity may keep the current lenient reuse).

**[safety] track_analyzer.py build (RENDER + deposit)**  
The backfill that a bare `build` runs by default deletes a track's existing library entry (index row + widget HTML in the keep tier) without ever verifying the replacement deposit landed.  
*Evidence:* scripts/track_analyzer.py:643 `subprocess.run(build_cmd)` — return code never checked; :649-655 then unconditionally calls `library.forget_run(...)` on the old run dir (library.py:362-364 also unlinks the deposited widget file). The comment at :644 asserts 'The fresh complete run has deposited' but nothing checks it: a nested build whose deposit is refused still exits 0, because cmd_build catches DepositError at :565-566 and merely prints 'library deposit skipped'. `_backfill_incomplete` (:659-668) does no verify-by-deed pass (only `cmd_revalidate` at :688-696 does). Triggered from cmd_build by default at :576-577.  
*Fails when:* Library holds a legacy incomplete deposit for track T (source audio intact). User runs a bare `build` on any other track → backfill re-analyzes T; the same detector again produces nothing, so the new run is still invalid → nested `build` renders the placeholder, deposit is refused (RC-INV-13), exits 0 → `forget_run` deletes T's index entry and its library widget HTML. T vanishes from the catalog with no replacement, and the outer build exits 0 with no failure summary — violating G-INV-11's all-or-clean-report and RC-INV-13a's 'never hidden silently'. Same outcome if the nested build crashes mid-render (nonzero exit unchecked).  
*Fix:* In `_complete_run`, check `subprocess.run(build_cmd).returncode == 0` AND confirm the new run actually deposited (re-run `validity`/look up the new run dir in the library index) before calling `forget_run`; on failure, keep the old entry and report the run as 'could not complete', mirroring cmd_revalidate's verify-by-deed. Have `_backfill_incomplete` re-check `_incomplete_deposits()` after the pass and print a 'could not complete N' summary like cmd_revalidate does.


### 🟠 MEDIUM (30)

**[spec-parity] /tc and /tc-quick (skill commands)**  
tc-quick.md tells the agent 'Do NOT run Demucs / stems / player' and to build from core+detail only, dropping the mix-mode player the SPEC defines as part of every quick run (§B.14).  
*Evidence:* commands/tc-quick.md:11-12 ('Do NOT run Demucs / stems / player / masking') and :16 (build with just --core and --detail) vs docs/SPEC.md:2742-2744 ('"quick" is a cheaper run (tc-quick, no Demucs stems) that produces a mix-mode player (one source, transport + seek ...) — §B.14') and SKILL.md:67-68/261-264. The entrypoint implements it: track_analyzer.py:293-296 encodes mix_web/mix.m4a in quick mode, and :110 auto-passes --audio-mix-rel mix_web to the build. The tc-quick recipe never runs make_web_stems.py and never passes --audio-mix-rel.  
*Fails when:* Quick widget ships without the transport/seek mix player the spec promises for quick runs; the shipped surface is below the spec bar and diverges from what a /tc-quick run via the entrypoint produces.  
*Fix:* Reword to 'no Demucs / per-stem player / masking — the mix still gets a single-track player (encoded automatically by the entrypoint)', and route the build through track_analyzer.py so mix_web + --audio-mix-rel happen.

**[spec-parity] catalog.py build**  
G-INV-14's promised degradation message is unimplemented: a FULL run whose src_run_dir is gone gets its similarity reasons forced to R_QUICK, so both similarity cells read "full analysis only" while the same row's Analysis chip says "full", and the preview player just disappears silently.  
*Evidence:* catalog.py:990-991 (`if is_quick or fp is None: e["_lean_reason"] ... = SC.R_QUICK`) and catalog.py:1002-1004 (`else: ... e["_sib_reason"] ... = SC.R_QUICK` for ANY entry without a fingerprint, including full runs); _lean_cell/_siblings_cell map R_QUICK to "full analysis only" (catalog.py:292-293, 327-328). docs/SPEC.md:2252-2256 (G-INV-14): "the preview player and similarity show 'analysis data not available — re-analyse to restore' rather than failing silently" — that phrase appears nowhere in scripts/ or tests/ (grep confirms zero hits). fingerprints.py:97-111 returns None for a missing dir, so this is exactly the gone-run-dir path.  
*Fails when:* User deletes an old Ableton project folder holding a deposited FULL run (the exact G-INV-14 scenario). Catalog rebuild: the row's open-link correctly falls back to the library copy, but the "Leans toward" and "Similar in library" cells say "full analysis only" — self-contradicting the row's own "full" mode chip and telling the user a full analysis would fix it when re-analysis is what's needed — and the play button is silently absent instead of the promised "analysis data not available — re-analyse to restore". If every track is in this state, the presence gate (R_QUICK not in _LEAN_RESULT_REASONS/_SIB_RESULT_REASONS, catalog.py:529-530) sheds both columns entirely, hiding the condition.  
*Fix:* In build_catalog's injection loop, distinguish the cases: mode==quick → R_QUICK; full run with fp None → a new reason (or reuse R_NO_DATA plus a dedicated cell phrase) that renders per G-INV-14 as "analysis data not available — re-analyse to restore" in both cells, and counts as a shown (non-shed) state; keep the sib branch symmetric. Add a test pinning the G-INV-14 phrase for a full entry whose src_run_dir does not exist.

**[correctness] catalog.py build**  
The migrate/missing banners count index ENTRIES (every deposited version/run) but the rendered sentence says "N tracks", so a track with several outside-root versions is counted multiple times and the banner over-states.  
*Evidence:* catalog.py:958-969 — the loop increments migrate_banner/missing_banner once per entry in `entries` (one entry per deposit, multiple per track); catalog.py:637 renders `f"{n_outside} track{'s'...}"`. docs/SPEC.md:2182-2184 (G-INV-16b) fixes the banner wording as "the 'N tracks have analysis data in project folders' number always means *your* tracks", and G-INV-22 (SPEC.md:2186-2191) says the split "keeps the banner honest".  
*Fails when:* One track analysed three times in its Ableton folder before migrate existed → three index entries with outside-root src_run_dir → banner reads "3 tracks have analysis data in project folders" over a catalog that visibly shows 1 such track. Same over-count for the missing-source banner.  
*Fix:* Count distinct tracks, not entries: accumulate `e.get("track")` into two sets (or count over library.newest_reps / group_versions members) and render the set sizes.

**[correctness] catalog.py build**  
build_catalog derives the output root as `root.parent` instead of calling `library.output_root()`, so with the documented `$TRACK_COACH_LIBRARY` override the G-INV-16/22 banner classification runs against the wrong base and every in-root run can be flagged as needing migrate (or outside runs never flagged).  
*Evidence:* catalog.py:938-940 (`output_root = root.parent`) feeding the `Path(sd).relative_to(output_root)` check at catalog.py:960-969. library.py:35-45 defines the canonical `output_root()` (honouring TRACK_COACH_ROOT, docstring: "G-INV-7"), and library.py:30-32 shows library_root is independently overridable; SKILL.md:87 documents the `$TRACK_COACH_LIBRARY` override to users.  
*Fails when:* User sets TRACK_COACH_LIBRARY=~/Dropbox/tc-library (documented override). Runs still land under ~/.track-coach/projects/ (library.output_root()). build_catalog computes output_root=~/Dropbox, so every entry's src_run_dir fails relative_to → all tracks counted → a permanent false "N tracks have analysis data in project folders — run migrate" banner; migrate then finds nothing to move. Conversely TRACK_COACH_LIBRARY=~/x/library with runs elsewhere under ~/x masks a real migrate case.  
*Fix:* Replace `output_root = root.parent` with `output_root = library.output_root()` (catalog.py:940), matching how the rest of the store resolves the root.

**[spec-parity] library.py alias**  
Alias canonicalization is applied only at catalog build, so once an alias exists the state-changing verbs (remove, prune-versions, list) operate on raw slugs and break H-INV-2's promise that remove 'names exactly what goes (which catalog rows)'.  
*Evidence:* scripts/catalog.py:936 is the ONLY call site of library.canonicalize_entries (grep over scripts/*.py). scripts/library.py:1294 (_cmd_remove) and :1332-1345 (_cmd_prune_versions) read idx['entries'] with no load_aliases/resolve_alias. SPEC.md:2391-2394 (H-INV-2: removing 'names exactly what goes (which catalog rows...)'); SPEC.md:1386-1388 (G-INV-23: aliased entries fold onto the canonical slug at catalog build).  
*Fails when:* User runs `alias --merge a --into b`, catalog shows ONE row 'b' whose versions include a's bounces. Then `remove b --apply` reports the track removed — but the catalog row 'b' persists, now rebuilt from a's entries (canonicalized a→b): the row the user just 'removed' is still on screen. Conversely `remove b <stamp-of-a's-bounce>` (a version visible under row b) prints 'nothing found'. `prune-versions --keep 3` keeps 3 per RAW slug, i.e. up to 6 versions under the one visible row.  
*Fix:* Make the library verbs alias-aware: in _cmd_remove (and remove_plan) resolve the requested track through the alias map and match entries whose CANONICAL slug equals it (or at minimum warn 'row b also contains entries aliased from a; they survive this removal — run `alias --remove a` first'); group prune-versions and list by canonical slug. Also drop or flag dangling aliases when their canonical track is removed.

**[safety] library.py backup**  
A hard kill (SIGKILL/power loss) mid-backup leaves backups/_tmp_<stamp>/ behind forever, and if the kill lands between the .backup_ok write and the rename, the leftover _tmp_ dir is a fully trusted snapshot that permanently wins `restore latest`.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:948-949 writes the trust marker INSIDE the temp dir before the rename ((tmp_dest / ".backup_ok").write_text("ok"); tmp_dest.rename(dest)); cleanup at lines 950-953 runs only on a Python exception, never on a kill. Nothing filters the `_tmp_` prefix: _has_valid_backup (lines 906-907), `backup --list` (lines 969-971), and `restore latest` (lines 1006-1012) all accept any dir with .backup_ok, and since "_" (0x5F) sorts after "9" (0x39), snaps[-1] at line 1012 picks `_tmp_<stamp>` over every real stamp — forever, since no verb descends into backups/ (SPEC.md:2426-2428: "only hard reset removes snapshots"). SPEC.md:2423-2424 promises "it either completes and marks the snapshot good, or it discards the partial"; SKILL.md:845 repeats "or it cleans up the partial" — neither holds for a kill, only for an exception.  
*Fails when:* kill -9 during the copytree loop -> backups/_tmp_<stamp>/ (no marker) persists forever; gc/reset never reclaim it, only hard-reset. Worse window: kill between line 948 and 949 -> backups/_tmp_<stamp>/.backup_ok exists -> `restore latest` restores from a dir named _tmp_, `backup --list` shows it, and every future `restore latest` keeps preferring it over newer real snapshots because underscore sorts last.  
*Fix:* Write .backup_ok AFTER the rename (into dest), or keep the marker-in-tmp but make every consumer skip names starting with `_tmp_` (in _has_valid_backup, `backup --list`, and restore's latest scan); additionally sweep stale `_tmp_*` dirs at the start of _do_backup so a killed run's litter is reclaimed on the next backup.

**[correctness] library.py backup**  
backup with zero sources (fresh root, or a mistyped/unmounted --base path) silently succeeds, creating an empty .backup_ok-marked snapshot and printing "snapshot created" — the user believes curated work is backed up when nothing was captured.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:922-933 builds `sources` only from paths that exist (library/, explore/, config.json, projects/) with no guard when the list ends up empty; lines 940-949 then mkdir backups/, write .backup_ok into an otherwise empty dir, and line 985 prints success. Line 962 accepts any --base (`Path(args.base).expanduser().resolve()`) without checking it exists. The empty snapshot then makes _has_valid_backup (lines 900-911) return True, which disarms reset's H-INV-6 `--no-backup` guard (lines 1125-1127) — SPEC.md:2452-2456 gates the unrecoverable wipe on "no existing snapshot", and an empty snapshot counts.  
*Fails when:* External drive not mounted: `library.py backup --base /Volumes/TC-Backups/tc` creates /Volumes/TC-Backups/tc/backups/<stamp>/.backup_ok on the local disk and reports success; the real library was never copied. Or on a typo'd base: the empty snapshot later lets `reset --yes-wipe-everything --no-backup` at that base skip --i-understand while nothing recoverable exists.  
*Fix:* In _cmd_backup (or _do_backup when called from the backup command), error out — or at minimum print a loud warning and skip snapshot creation — when `sources` is empty: "backup: nothing to back up under <base> (no library/, explore/, or config.json)". Optionally also require --base to already exist as a directory.

**[correctness] library.py clean**  
clean crashes with KeyError('track') on legacy string index entries, so `clean --all` and `clean --missing` abort entirely on any library containing one.  
*Evidence:* scripts/library.py:519 uses hard indexing `e['track']` in the removal-listing loop, but load_index (scripts/library.py:278) deliberately coerces legacy string entries to `{"widget": s}` with no 'track' key. Reproduced: an index with entries ["legacy-slug", {…valid…}] makes `clean --missing` traceback with KeyError: 'track' at line 519 (exit 1) before doing anything. Sibling handlers use `e.get('track','?')` (e.g. _cmd_prune_versions line 1362, _cmd_dereference line 1410).  
*Fails when:* A library that ever received a legacy slug entry (the exact case load_index's comment says exists) makes `clean --missing` — the documented recovery for index/disk drift — unusable: it crashes in the dry-run print loop, and no clean variant that selects the legacy entry can run.  
*Fix:* Line 519: use `e.get('track','?')` and `e.get('widget','?')` like the sibling commands (and guard the exists lambda at line 512 with `e.get('widget','')`).

**[consistency] library.py clean**  
clean --apply does not regenerate the catalog after mutating the index, unlike its sibling prune-tier verbs, leaving the global Catalog page showing removed tracks with dead widget links.  
*Evidence:* scripts/library.py:523-529 (_cmd_clean apply path) ends after save_index with no _regen_catalog() call; _cmd_remove (line 1323) and _cmd_prune_versions (line 1377) both call _regen_catalog() after the identical unlink+save_index sequence, with the comment "Delete widget files, rewrite index, regen catalog — all in one step (G-INV-11)". SPEC.md H-INV-12 (docs/SPEC.md:2478-2484) groups clean into the same prune tier so "the whole tier reads one way".  
*Fails when:* After `clean --older-than 90 --apply`, ~/.track-coach/library/index.html still lists the pruned tracks; clicking a row's widget link 404s (file was unlinked) until some later `build` or `remove` happens to rebuild the catalog.  
*Fix:* Add `_regen_catalog()` at the end of _cmd_clean's apply branch (after line 529's summary print), matching _cmd_remove/_cmd_prune_versions.

**[safety] library.py clean**  
The index rewrite in clean --apply is not crash-safe: save_index writes index.json in place (no tmp+rename), and a partially-written/corrupt index is silently read back as an EMPTY library, so a kill mid-clean can lose every entry's metadata, not just the pruned ones.  
*Evidence:* scripts/library.py:285-287 save_index does a direct `write_text` of the full JSON; scripts/library.py:280-282 load_index swallows ValueError on a corrupt file and returns {"entries": []}. _cmd_clean calls save_index at line 528 after already unlinking widget files (523-526). SPEC G-INV-11 (docs/SPEC.md:2302) requires cleanup to be "all-or-clean-report, including the index"; deposit, by contrast, is explicitly atomic (copies to _tmp then renames, scripts/library.py:917).  
*Fails when:* A kill/power-loss while save_index is writing during `clean --track X --apply` leaves a truncated index.json; the next `list`/`catalog`/`clean` loads it as empty and any subsequent save persists the empty state — all tracks' verdicts, tags, versions, and src_run_dir pointers are gone even though their widget files still sit in widgets/.  
*Fix:* Make save_index atomic (write to index.json.tmp in the same dir, fsync, os.replace); optionally have load_index refuse (or warn loudly) instead of silently returning an empty index on a parse error.

**[correctness] library.py deposit**  
The --widget default picks the lexicographically-last analysis_widget*.html, not the newest, despite the help text saying 'default: newest in run dir' — a two-digit version component makes it deposit a stale widget.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:473 `cands = sorted(run_dir.glob("analysis_widget*.html"))` then `widget = cands[-1]`; parser help at library.py:1504 says "widget html (default: newest in run dir)". Widget filenames embed a version, not a sortable stamp: track_analyzer.py:81 `f"analysis_widget_{track_version or 'v' + tc_version()}.html"`.  
*Fails when:* A run dir holds analysis_widget_v0.9.22.html (old build) and analysis_widget_v0.10.1.html (rebuild after upgrade) — or user labels v2 vs v10. Lexicographically "v0.10.1" < "v0.9.22", so a manual `library.py deposit --run-dir DIR` copies the STALE widget into the library, and deposit_from_run then reads tc_version/analysis_version from that stale payload (lines 445-448), so the catalog's INV-12 stale check is fed the wrong build version too.  
*Fix:* Pick by modification time: `widget = max(cands, key=lambda p: p.stat().st_mtime)` (or sort by mtime), matching the documented 'newest in run dir'.

**[spec-parity] library.py deposit**  
A corrupt run_meta.json fails OPEN past the reference/synthetic refusal gates: _cmd_deposit swallows the JSON error and proceeds with meta={}, so a reference or smoke run whose marker file is unreadable deposits silently — the exact outcome G-INV-18/G-INV-21 say must be a refusal.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:465-470 `if mp.exists(): try: meta = json.loads(...) except ValueError: meta = {}` — the reference/synthetic flags checked at lines 422-429 are read only from this meta. SPEC.md:2157 "an explicit `deposit` of a reference run is refused rather than silently written" (G-INV-18); SPEC.md:2175-2180 same for the synthetic marker (G-INV-21).  
*Fails when:* A reference-album run's run_meta.json is truncated (e.g. the analyzer was killed mid-write — its writes are not atomic either). `library.py deposit --run-dir <that run>` parses meta as {}, skips both refusal gates, passes validity (the results are complete), and deposits someone else's track into the library with track name taken from the folder — polluting the catalog and the similarity/fingerprint surfaces the gates exist to protect (D-INV-3/D-INV-7).  
*Fix:* In _cmd_deposit, treat an existing-but-unparseable run_meta.json as a refusal (sys.exit with a 'run_meta.json is corrupt — refusing to deposit; fix or re-run analyze' message) instead of coercing to {}. A missing file may stay permissive (pre-marker runs are spec-blessed as going-forward-only), but a present corrupt marker file must fail closed.

**[spec-parity] library.py dereference**  
dereference --apply rewrites index.json but never regenerates the catalog, leaving the visible catalog in a half state that still shows the reference albums the command just purged.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:1425-1428 ends the apply path after save_index() with no _regen_catalog() call, while siblings remove (line 1323) and prune-versions (line 1377) both call _regen_catalog() and prune-versions' comment (line 1369) cites 'rewrite index, regen catalog — all in one step (G-INV-11)'. docs/SPEC.md:2356-2357 (§G.6) requires dereference to be 'all-or-clean-report like every destructive command (G-INV-8/G-INV-11)', and §H.1 (H-INV-2) defines that rail as 'index and catalog are rewritten in one step (no half state)'.  
*Fails when:* User runs `library.py dereference --album-path .../DeepChord --apply`; index entries drop, but ~/.track-coach/library/index.html (the global Catalog the user opens) still lists the DeepChord rows — other people's music appears to remain in the library until some later build/remove/alias happens to rebuild the page.  
*Fix:* Call _regen_catalog() after save_index() in the --apply branch of _cmd_dereference, matching remove/prune-versions.

**[consistency] library.py dereference**  
dereference drops index entries but never deletes the deposited widget HTML copies, permanently orphaning other people's music inside library/widgets/ with no command left that can reclaim them.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:1425-1426 rewrites entries only; unlike remove (lines 1316-1319) and prune-versions (lines 1370-1373), it never unlinks wdir/e['widget']. Once the entries are gone, remove can't target them (it works off the index, line 1294), gc scans only projects_dir run dirs (lines 666-670), and clean --missing (line 1515) is the inverse check — nothing ever deletes those files. §G.6's stated purpose (docs/SPEC.md:2349-2359, backed by G-INV-18 at 2159-2160) is keeping other people's music out of the library.  
*Fails when:* After `dereference --apply` on the pre-marker DeepChord/SCSI-9 albums, dozens of reference-album widget HTML files stay in ~/.track-coach/library/widgets/ (the 'keep' tier) forever, invisible to every listing and cleanup verb.  
*Fix:* In the --apply branch, unlink wdir/e['widget'] for each dropped entry (same loop as remove/prune-versions) before rewriting the index; name the widget files in the dry-run preview too.

**[safety] library.py gc**  
The sweep never validates its scan targets are actually track-coach-output/ dirs — a malformed (KI-1-shaped) index entry or a careless --scan-dir points the destructive classifier at an arbitrary user folder.  
*Evidence:* scripts/library.py:784 — _tco_dirs_from_library computes `tco = src.parent.parent` with no check that tco.name is 'track-coach-output' (the KI-1 shallow-deposit shape documented at library.py:74-80 makes parent.parent land on the Ableton project folder itself); library.py:1252-1253 accepts any --scan-dir path with the same absence of shape validation. H-INV-5 (SPEC.md §H.2) claims the sweep 'never touches non-track-coach files'.  
*Fails when:* A pre-guard junk index entry has src_run_dir = <AbletonProject>/track-coach-output/<stamp> (one level shallow); parent.parent = <AbletonProject>. `gc --ableton-tails --apply` then iterates the user's Ableton project folder and, combined with the loose-file blindness above, rmtree's any child folder holding only files.  
*Fix:* Before scanning, require each candidate tco dir's basename to be 'track-coach-output' (or match the known output-dir shapes); skip and report non-conforming candidates. Apply the same check to --scan-dir, refusing with an error rather than scanning.

**[correctness] library.py gc**  
--scan-dir is silently ignored unless --ableton-tails is also given, so `gc --scan-dir X --apply` runs the full default-root prune the user never targeted.  
*Evidence:* scripts/library.py:1207 — _cmd_gc branches only on args.ableton_tails; args.scan_dir is read solely inside _gc_ableton_tails (line 1252). The parser (line 1568-1569) attaches --scan-dir to gc unconditionally and its help text does not state the dependency; SKILL.md:875 only ever shows it paired with --ableton-tails.  
*Fails when:* User runs `library.py gc --scan-dir ~/Music/Proj/track-coach-output --apply` intending the tail sweep; the flag is dropped, normal gc runs with --apply, and orphan run dirs under ~/.track-coach/projects are deleted — a destructive action in a location the user did not name.  
*Fix:* In _cmd_gc, error out when args.scan_dir is set without args.ableton_tails ('--scan-dir requires --ableton-tails'), or have --scan-dir imply the mode; note the dependency in the argparse help.

**[spec-parity] library.py gc**  
Neither apply loop is all-or-clean-report (G-INV-11): the G-INV-7 boundary check is interleaved with deletion, and an unhandled rmtree error mid-loop leaves a partially-pruned state with a traceback instead of a report of what was removed.  
*Evidence:* scripts/library.py:1241-1246 — the `p.relative_to(base)` check and `shutil.rmtree(p)` run inside one loop, so a failure on orphan N sys.exits after orphans 1..N-1 are already gone; any OSError from rmtree propagates uncaught. Same unguarded loop at 1279-1280 for --ableton-tails. SPEC.md §G.3 G-INV-11 (~line 2302): a gc 'either completes and reports precisely what it removed ... or it aborts having removed nothing'.  
*Fails when:* A permission error (or a run dir vanishing under a concurrent process) on the 3rd of 7 orphans raises mid-loop: 2 dirs are gone, 4 remain, rmtree may leave the 3rd half-deleted (which _count_result_files can then mis-rank as a thinner 'best' run), and the user gets a Python traceback with no statement of what was actually removed.  
*Fix:* Validate ALL orphan paths against the root before deleting any; wrap each rmtree in try/except and finish with a precise report ('removed M of N, failed on <path>: <err>'), exiting non-zero on partial completion.

**[correctness] library.py hard-reset**  
A symlink child of the output root crashes hard-reset: a broken symlink crashes even the bare dry-run, and a symlink-to-directory crashes the real wipe mid-deletion, leaving a half-wiped root with a raw traceback instead of a clean report.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:1173 `total = sum(_dir_size(d) if d.is_dir() else d.stat().st_size for d in contents)` — `d.stat()` follows symlinks, so a dangling symlink raises FileNotFoundError before any output is printed. /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:1195-1198 `if d.is_dir(): shutil.rmtree(d)` — `is_dir()` follows symlinks and `shutil.rmtree` raises `OSError: Cannot call rmtree on a symbolic link` (verified by direct test). Deletion iterates `sorted(base.iterdir())`, so `backups/` is deleted before a later-sorting symlink crashes.  
*Fails when:* User once symlinked a folder into ~/.track-coach (e.g. `ln -s /Volumes/ext/projects ~/.track-coach/projects`) or a snapshot left a dangling link. (a) `library.py hard-reset` with no flags — the promised always-safe preview (SKILL.md line 831, SPEC H-INV-10 'dry-run by default') — dies with a FileNotFoundError traceback. (b) With both confirm flags, the wipe deletes `backups/` and other early-sorting entries, then crashes on the symlink: the safety net is destroyed, the wipe is incomplete, and the exit is a traceback, violating the all-or-clean-report rail (G-INV-11, cited by H-INV-11 for every rung).  
*Fix:* Treat symlinks explicitly: use `d.is_symlink()` first and `d.unlink()` any symlink (never rmtree/never follow); use `d.stat(follow_symlinks=False)`/`d.lstat()` for sizing. Apply the same to _cmd_reset's identical loop (library.py:1140-1143) and to _dir_size.

**[spec-parity] library.py hard-reset**  
SPEC.md H-INV-10 promises `reset --hard` as an equivalent spelling of hard-reset, but no `--hard` flag exists on the reset parser — the documented invocation errors out.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/docs/SPEC.md:2462 'both `--yes-wipe-everything` and an explicit `--including-backups` (equivalently `reset --hard`)'. The reset subparser at /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:1542-1551 defines only --base/--yes-wipe-everything/--no-backup/--i-understand; grep for '--hard' finds no match anywhere in library.py or SKILL.md.  
*Fails when:* A user (or the skill agent) follows the spec and runs `library.py reset --hard --yes-wipe-everything` — argparse exits with 'unrecognized arguments: --hard'. Fail-safe direction, but the spec documents a command form that does not exist.  
*Fix:* Either delete the '(equivalently `reset --hard`)' clause from SPEC.md, or implement `--hard` on reset that requires --including-backups and dispatches to _cmd_hard_reset. Removing the spec clause is smaller and keeps one spelling per verb.

**[consistency] library.py prune-versions**  
prune-versions counts and prunes per RAW track slug while the catalog canonicalises same-song aliases before grouping (G-INV-23), so 'keep newest N per track' disagrees with the track rows the user actually sees.  
*Evidence:* scripts/catalog.py:936 canonicalises entries via `library.canonicalize_entries(entries, library.load_aliases(root))` before group_versions, per SPEC.md:1384-1390 / G-INV-23 (aliased identity folds onto its canonical slug, bounces become versions under ONE row). But _cmd_prune_versions never loads aliases: the inspect path (scripts/library.py:1336) calls group_versions on raw entries, and prune_versions_plan groups by raw `e.get("track")` (scripts/library.py:838).  
*Fails when:* Song aliased from slug B into slug A shows ONE catalog row with 3 versions (2 under A, 1 under B). User runs `prune-versions --keep 2 --apply` expecting the oldest of the 3 dropped; the plan sees two tracks (A: 2 versions, B: 1) and prints 'nothing to drop (all tracks already <= 2 version(s))' — a silent no-op contradicting the catalog. With --keep 1 it keeps 2 versions of the one song, one of which the catalog never shows as newest.  
*Fix:* In _cmd_prune_versions, canonicalise track names through load_aliases/resolve_alias for GROUPING (both the bare inspect view and prune_versions_plan) while still dropping the original entries — e.g. pass canonicalize_entries output to the plan but map back by id() to the real entries, mirroring how catalog.py:936 does it.

**[safety] library.py remove**  
remove --apply is not crash-consistent: widget files are unlinked before a non-atomic index rewrite, and a truncated index.json silently reads back as an EMPTY library, breaking H-INV-2's 'rewritten in one step (no half state, G-INV-11)' promise.  
*Evidence:* scripts/library.py:1315-1321 — comment claims 'Delete widget files + rewrite index in one step (G-INV-11)' but the code loops `wf.unlink()` per entry, THEN calls save_index. save_index (library.py:285-287) does a plain `(root / "index.json").write_text(...)` with no temp-file+rename. load_index (library.py:270-282) catches ValueError on corrupt JSON and falls back to `{"entries": []}` with no warning. SPEC.md:2391-2396 (H-INV-2) and SPEC.md:2302-2307 (G-INV-11) promise all-or-clean-report / no half state.  
*Fails when:* Kill the process mid-`remove --apply`: (a) after some unlinks but before save_index → index entries point at deleted widget copies (half state); (b) during write_text → index.json is truncated, the next `library list`/`catalog` silently shows an empty library, and the next save persists the loss; a follow-on `gc --apply` then sees no referenced runs and can reclaim real deposited run dirs.  
*Fix:* In save_index, write to index.json.tmp and os.replace() into place (atomic on the same filesystem). In _cmd_remove, rewrite the index FIRST, then unlink the now-unreferenced widget files (a leftover widget file is harmless; a dangling index entry is not). Make load_index refuse loudly (sys.exit with the parse error) instead of silently returning an empty library when index.json exists but is corrupt.

**[doc-parity] library.py remove**  
SKILL.md documents 'remove one version by stamp/label', but the synthetic v1/v2 labels the catalog and prune-versions show are never stored on entries, so remove-by-label reports 'nothing found' for the common auto-deposited case.  
*Evidence:* SKILL.md:901 — `library.py remove "Track Name" s1  # dry-run: remove one version by stamp/label`. remove_plan matches only `e.get("stamp") == version or e.get("version") == version` (scripts/library.py:813). Auto-deposit stores version="" (`version=meta.get("track_version") or ""`, library.py:451), and the labels users see are synthesized per-display: `ver["label"] = ver["rep"].get("version") or f"v{i + 1}"` (library.py:247), shown by prune-versions (library.py:1342) and the catalog.  
*Fails when:* User runs `library.py prune-versions`, sees 'MyTrack: 3 version(s) — v3, v2, v1', then runs `library.py remove "MyTrack" v2 --apply` per SKILL.md — output is 'remove: nothing found for track=\'MyTrack\' (version=\'v2\')' and the documented one-version removal is impossible except by raw stamp.  
*Fix:* In _cmd_remove (or remove_plan), when the literal stamp/version match is empty, resolve the argument through group_versions: match the requested label against each version's computed label and remove that version's whole audio_sha group. Alternatively, narrow SKILL.md:901 to 'by stamp (as shown by library list)' — but the group-resolving fix also makes 'remove one version' take all runs of that bounce, which is what H-INV-2 means by a version.

**[safety] library.py reset**  
The --no-backup irreversibility guard accepts ANY snapshot marked .backup_ok — including an empty one — so a populated library can be wiped unrecoverably without --i-understand.  
*Evidence:* library.py:900-911 `_has_valid_backup` returns True for any dir under backups/ containing `.backup_ok`, with no check that it holds library/ or explore/. library.py:922-933 `_do_backup` on a base with no library/explore/config still creates a snapshot containing only `.backup_ok` (sources list is empty). Guard used at library.py:1125. SPEC.md:2452-2455 (H-INV-6) requires the extra `--i-understand` when "no existing snapshot covering the curated tiers" exists.  
*Fails when:* User runs `backup` (or a reset that auto-backups) while ~/.track-coach is still empty → an empty `.backup_ok` snapshot is created. Weeks later, with a full library/ and explore/, they run `library.py reset --yes-wipe-everything --no-backup`: the guard at 1125 sees the empty snapshot as "valid", skips the --i-understand requirement, and destroys all curated work with nothing recoverable in backups/.  
*Fix:* Make `_has_valid_backup` (or a reset-specific variant) require that the snapshot actually contains the curated tiers present at the base right now (e.g. snapshot has library/ if base/library exists, same for explore/); additionally, have `_do_backup` refuse to create (or not mark ok) a snapshot with zero sources.

**[consistency] library.py restore**  
restore --apply never regenerates the catalog, unlike sibling library-mutating verbs (remove, prune-versions), so after a non-full restore the catalog's open links dangle instead of falling back to the library HTML copy that H-INV-9 promises.  
*Evidence:* library.py:1066-1077 — no _regen_catalog() call after the restore, while _cmd_remove (library.py:1323) and _cmd_prune_versions (library.py:1377) both call it after mutating the library. The G-INV-14 fallback href is injected only at catalog-build time (catalog.py:946-953: `if sd and not Path(sd).exists(): … e["_lib_href"] = lib_copy.as_uri()`), and the restored library/index.html was built when the snapshot's run dirs still existed, so it carries no fallbacks. SPEC.md:2436-2437 (H-INV-9): after a non-full restore "opens fall back to the library HTML copy (G-INV-14)".  
*Fails when:* restore latest --apply after a reset: the restored catalog page's open/preview links point at projects/ run dirs that no longer exist; clicking them fails outright instead of opening the library HTML copy, until some later remove/prune/catalog run happens to rebuild the page.  
*Fix:* Call _regen_catalog() after the restore completes (it is already best-effort and prints its own skip line on failure), matching remove and prune-versions.

**[correctness] run_dir.py init/resume/catalog**  
The G-INV-2b collision warning is never emitted: _resolve_slug builds the warn string but both return statements hard-code None, so cmd_init's `if warn:` is dead and the user is silently re-slugged.  
*Evidence:* scripts/run_dir.py:196-203 — `return candidate, None` on both exit paths while `warn = (f"  ⚠  slug '{candidate}' is used by a different track ...")` at 201-203 is assigned and discarded; cmd_init at 215-217 checks the always-None value. Reproduced: colliding `init b/My_Track.wav` created My_Track-2 with no warning on stderr. SPEC.md:2216 (G-INV-2b) promises it 'uses `<slug>-2` ... and warns the user'; tests/test_storage_relocation.py's CollisionDisambiguation class asserts the -2 dir but never the warning, so the suite misses it.  
*Fails when:* Two tracks slug to the same name; the second lands in My_Track-2 with zero notice, so the user (and the agent narrating the run) never learns the track was forked to a numbered slug — later confusion about which slug dir holds which track.  
*Fix:* Initialize `warn = None` before the loop and change both exits to `return candidate, warn` (the loop already overwrites warn on each collision hop); add a test asserting the stderr warning on collision.

**[safety] run_dir.py init/resume/catalog**  
index.json is written non-atomically and a corrupt/truncated index is silently reset to empty, so a crash mid-write makes the very next init replace the whole 'append-only, never overwritten' run history with a single entry.  
*Evidence:* scripts/run_dir.py:122-126 — on ValueError/OSError `idx = {"runs": []}` with no backup; run_dir.py:156 — `idx_path.write_text(...)` with no tmp+rename. Reproduced: truncated index.json (2 runs) + one `init` -> index.json now holds 1 run, history gone. Contradicts the module's own promise 'append-only history of every run' (run_dir.py:15) / 'honest history, never overwritten' (run_dir.py:114) and SKILL.md:230 'honest append-only history'. G-INV-11 (SPEC.md:2302-2307) makes readers tolerate drift, but nothing licenses destroying the file's contents.  
*Fails when:* A kill/power-loss during update_index's write_text leaves a truncated index.json; the next `init` parses it, fails, starts from `{"runs": []}`, and writes a one-entry index — every prior run vanishes from the history that the version catalog, sibling narratives, and D-INV-14 content-hash read.  
*Fix:* Write via a temp file in the same dir + os.replace (atomic), and on a parse failure rename the unreadable index aside (e.g. index.json.corrupt-<stamp>) and disclose on stderr before starting a fresh one, instead of silently zeroing.

**[spec-parity] track_analyzer.py analyze (MEASURE)**  
G-INV-21 documents the `--synthetic` flag on `build`, but the code implements it only on `analyze` — `build --synthetic` errors out, and the flag is documented nowhere the user/agent actually reads (SKILL.md never mentions it).  
*Evidence:* docs/SPEC.md:2176-2177 — "The marker is set two ways — the `--synthetic` flag on `build`, and automatically when the analysed source lives under the test fixtures tree"; scripts/track_analyzer.py:752-753 defines --synthetic on the `analyze` subparser only; the `build` subparser (track_analyzer.py:760-779) has no --synthetic argument.  
*Fails when:* A user testing with a synthetic clip that does NOT live under tests/fixtures/ follows the spec and runs `build --run-dir ... --synthetic` → argparse exits "unrecognized arguments: --synthetic". Having already run `analyze` without the flag (the spec never puts it there), their only spec-sanctioned marker path is broken; if they drop the flag to get the build through, the synthetic run auto-deposits into the real catalog — the exact outcome G-INV-21 exists to prevent.  
*Fix:* Align spec to code: reword G-INV-21 to "the `--synthetic` flag on `analyze`" (the marker is stamped at measure time, track_analyzer.py:222-224), and mention `analyze --synthetic` in SKILL.md beside the `--reference` paragraph. Alternatively also accept --synthetic on `build` (stamp run_meta before deposit) if a post-hoc marker is wanted.

**[safety] track_analyzer.py build (RENDER + deposit)**  
build's deposit path rewrites library/index.json non-atomically, and a truncated index is silently read back as empty — so a kill mid-deposit can wipe the whole catalog on the next deposit.  
*Evidence:* scripts/library.py:285-287 `save_index` does a plain `write_text` (truncate-then-write, no tmp+rename), called from `deposit` (:414-416) which cmd_build invokes via `deposit_from_run` (track_analyzer.py:563). scripts/library.py:268-283 `load_index` catches ValueError from a corrupt file with bare `pass` and returns `{"entries": []}`.  
*Fails when:* SIGKILL/power loss lands mid `write_text` during a build's auto-deposit → index.json is truncated JSON. Every subsequent `load_index` silently returns an empty entry list (catalog reads empty), and the very next build's deposit calls `save_index` with only its own entry — all prior library rows are permanently overwritten without any warning. The widget HTML files survive in library/widgets/ but every catalog row, verdict, tag, and src_run_dir pointer is gone. This is the durable keep tier (G-INV-5) with weaker crash-consistency than the spec demands of every destructive verb (G-INV-11 all-or-clean-report).  
*Fix:* In `save_index`, write to `index.json.tmp` then `os.replace` (atomic on POSIX). In `load_index`, stop swallowing ValueError silently — at minimum warn loudly and refuse to overwrite a corrupt index with a fresh one (rename the corrupt file aside first).

**[spec-parity] track_analyzer.py build (RENDER + deposit)**  
G-INV-17 promises 'a build whose run is invalid does not deposit; it redoes first' — build never redoes the current invalid run, and its refusal message points at `revalidate --apply`, which cannot see an undeposited run.  
*Evidence:* SPEC.md:2150-2152 (G-INV-17: '"Successful" now includes complete — a build whose run is invalid (RC-INV-13) does not deposit; it redoes first'). Code: cmd_build (track_analyzer.py:559-566) only catches the DepositError and prints 'library deposit skipped'; the default backfill (:576-577 → :659-668) completes only *deposited* incomplete runs — `_incomplete_deposits` (:589-603) iterates `library index entries`, so the just-built undeposited run is never in its set. The refusal message (library.py:434-436) says 'complete the run (revalidate --apply)', but `cmd_revalidate` (:671-697) also reads only `_incomplete_deposits`, so it can never complete an undeposited run either.  
*Fails when:* Fresh `analyze` leaves one gate-present signal unmeasured (a transcription detector produced nothing, exit 0) → `build --run-dir <it>` renders the placeholder, refuses deposit, exits 0, and redoes nothing. Following the printed advice, the user runs `revalidate --apply`, which reports 'all library runs are complete' — the invalid run is invisible to every promised auto-completion path and stays out of the library until the user manually re-runs `analyze` (also contradicting RC-INV-13a's 'redone once, automatically').  
*Fix:* In cmd_build, on an RC-INV-13 deposit refusal, run the bounded auto-redo for THIS run (the `_complete_run` machinery, once), or — if the shipped design intentionally leaves the redo to the user — fix both the spec sentence in G-INV-17 and the misleading `revalidate --apply` hint in library.py's refusal message.

**[doc-parity] track_analyzer.py build (RENDER + deposit)**  
commands/tc.md and tc-quick.md still describe the pre-1.0 hand-driven pipeline (run_dir.py init / resume, flags passed straight to build_widget.py), which SKILL.md explicitly forbids — and on that hand-driven path their 'Every build auto-deposits' claim is false.  
*Evidence:* commands/tc.md:14-21 ('Create the output folder with scripts/run_dir.py init --mode full', 'Pass --src-audio … to build_widget.py') and commands/tc-quick.md:14-24 ('Build the widget with just --core and --detail') vs SKILL.md:39-42 ('is now ONE command. Do not hand-drive the individual steps below') and SKILL.md:71-72 ('invoke the pipeline through the entrypoint, not by pasting the step commands'). tc.md:27 claims 'Every build auto-deposits the widget into the global library' — but deposit lives only in track_analyzer.py cmd_build (:558-572); invoking build_widget.py directly, as tc.md instructs, deposits nothing.  
*Fails when:* An agent following /tc literally drives run_dir.py + build_widget.py by hand, resurrecting exactly the seam bugs the entrypoint was built to kill (track_analyzer.py:10-17), skips the deposit-boundary guards (G-INV-17/18/21, RC-INV-13 validity), and never actually deposits — while telling the user the widget landed in the library.  
*Fix:* Rewrite tc.md/tc-quick.md to invoke `track_analyzer.py analyze --mode full|quick` + `build`, matching SKILL.md's entrypoint-only rule; drop the run_dir.py/build_widget.py step instructions (or mark them internals-reference).


### 🟡 LOW (25)

**[doc-parity] /tc and /tc-quick (skill commands)**  
Both commands enumerate the must-pass build flags but omit --title, which SKILL.md marks as ALWAYS required alongside --src-audio.  
*Evidence:* commands/tc.md:19-21 lists --src-audio/--src-als/--track-version/--verdict; commands/tc-quick.md:19-20 lists --src-audio/--track-version/--verdict; SKILL.md:530 ('ALWAYS pass --title (track name) and --src-audio') and the entrypoint render example SKILL.md:62-64 leads with --title.  
*Fails when:* An agent treating the command file's flag list as the complete contract builds an untitled widget ('Untitled track' fallback, build_widget.py:4958 shows the default) and an untitled catalog row.  
*Fix:* Add --title to the must-pass list in both command files (or fold into the entrypoint rewrite where the render example already shows it).

**[consistency] catalog.py build**  
The stale-analysis chip is styled `color:var(--warn)` but the catalog page never defines `--warn` (PALETTE has no warn key), so the INV-12 "older analysis" marker loses its warning colour and falls back to the inherited ink.  
*Evidence:* catalog.py:717 (`color:var(--warn)`) vs the :root block at catalog.py:660-661 which defines only bg/panel/panel2/line/ink/muted/wob/good/bad/bright, and PALETTE at catalog.py:65-71 (no "warn"). The widget canon defines `--warn:#ffb454` (build_widget.py:3501) — exactly the DS-INV-1/2 drift class the PALETTE comment (catalog.py:66-67) warns about.  
*Fails when:* Any catalog row with an older-analysis widget: the "older analysis · vX.Y.Z → re-analyse" chip renders its text in the default light ink (an unresolvable var() makes color compute to the inherited value) instead of the amber warn, leaving only the faint background tint to mark staleness.  
*Fix:* Add "warn": "#ffb454" to PALETTE and `--warn:{p['warn']}` to the :root block (or use the literal), and extend test_design_tokens.py to assert every var(--x) referenced in the catalog CSS is defined in its :root.

**[dead-code] catalog.py build**  
`_href_map` is built for every entry and threaded through _row into _siblings_cell, but _siblings_cell never reads its href_map parameter (sibling chips link to #row-<slug> anchors instead), so the map and its per-entry _open_href calls are dead work.  
*Evidence:* catalog.py:312 (signature `_siblings_cell(siblings, title_map, href_map, ...)` — body at 336-343 uses only title_map and _row_id), catalog.py:588+593 (`_href_map` built via _open_href for all entries), catalog.py:458 and 615-616 (threaded through). The F-INV-4 redesign (chips scroll in-page, catalog.py:317-320) superseded the widget-href use but the plumbing stayed.  
*Fails when:* No wrong output — wasted computation and a misleading signature suggesting sibling chips link to widgets (D-INV-28 says they must not).  
*Fix:* Drop the href_map parameter from _siblings_cell and _row, and remove the _href_map construction in render_catalog_html.

**[correctness] library.py alias**  
Re-merging an already-aliased slug silently overwrites the existing mapping — `aliases[slug] = canon` never checks `slug in aliases`, so a→b is repointed to a→c with no mention that the old merge was dropped.  
*Evidence:* scripts/library.py:1481 `aliases[slug] = canon` with no prior-mapping check; the success print at :1483-1484 names only the new mapping. Contrast the command's own care elsewhere (self-merge refused :1470-1471, cycle refused :1478-1480, unknown-track warned :1473-1476).  
*Fails when:* aliases.json holds a→b (a's bounces show under row b). User runs `alias --merge a --into c` (typo or forgotten earlier merge). Output says only 'alias: a → c'; row b silently loses a's versions and nothing tells the user the a→b merge was undone.  
*Fix:* Before line 1481: `if slug in aliases and aliases[slug] != canon: print(f"alias: note — replacing existing {slug} → {aliases[slug]}")` (or refuse and require `--remove` first, matching the command's guard-everything style).

**[safety] library.py alias**  
aliases.json is written non-atomically and a corrupt/truncated file is silently read as an empty map, so a kill mid-save makes every same-song merge vanish from the catalog with no error surfaced, and the next merge permanently overwrites the evidence.  
*Evidence:* scripts/library.py:307-311 save_aliases uses a bare write_text (no tmp+os.replace); :298-304 load_aliases catches (OSError, ValueError) and returns {} — a truncated JSON after a mid-write kill is indistinguishable from 'no aliases set' (:1446-1447 prints exactly that). No os.replace/tempfile anywhere in library.py (grep).  
*Fails when:* Machine dies during `alias --merge` while write_text is flushing aliases.json → file truncated. Next catalog build silently un-merges every previously merged pair; `alias --list` says 'no aliases set — every track is its own catalog row', reading as normal. The next `alias --merge` save_aliases overwrites the corrupt file with a one-entry map, losing the old merges for good.  
*Fix:* In save_aliases write to `aliases.json.tmp` then os.replace() (crash-consistent). In load_aliases, distinguish file-absent (return {} silently) from file-present-but-unparseable (print a one-line stderr warning naming the corrupt file) so lost merges are visible instead of silent.

**[doc-parity] library.py backup**  
SKILL.md's backup section says the snapshot copies "library/ and explore/" and never mentions that config.json is also captured, which the code does and the spec and restore both rely on.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/SKILL.md:837 ("Copies `library/` and `explore/` (your accumulated references)") and :840 ("snapshot curated tiers (library/ + explore/)") — same wording in the parser help at library.py:1523 — versus library.py:927-929 which appends base/config.json to sources, SPEC.md:2417-2418 ("plus any config"), and the restore handler's comment at library.py:1072 ("config.json is captured on backup — restore it too").  
*Fails when:* A reader of SKILL.md concludes config.json is not covered by backup and preserves it by hand (or is surprised when restore overwrites their current config.json from a snapshot they thought held only library/ + explore/).  
*Fix:* Amend SKILL.md lines 837/840 and the argparse help at library.py:1523 to name config.json alongside library/ + explore/ (e.g. "library/ + explore/ + config.json"), matching SPEC.md:2418.

**[correctness] library.py catalog/list/path (read-only trio)**  
`list --track T` with no matching track on a populated library prints "(library empty)" — a factually wrong message that hides the real cause (filter matched nothing).  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:484-493 — entries are filtered by --track first, then the empty-by_track branch prints "(library empty)" regardless of why it is empty. Reproduced: with a 1-entry index, `library.py list --track nosuchtrack` printed "(library empty)" (exit 0). Sibling `remove` handles the same case correctly at line 1298: "remove: nothing found for track='...'" — so this is also a consistency break with its sibling.  
*Fails when:* User has tracks in the library, typos a slug (`list --track Fragil`), and is told the library is empty — suggesting all deposits are lost, when the filter simply matched nothing.  
*Fix:* In _cmd_list, when args.track is set and the filtered list is empty, print a no-match message naming the track (mirroring _cmd_remove's "nothing found for track=..."), reserving "(library empty)" for a genuinely empty index.

**[doc-parity] library.py catalog/list/path (read-only trio)**  
The module docstring's CLI block omits the `catalog` subcommand entirely, and SKILL.md's library command block omits `list --json`, so both docs lag the shipped flag/verb surface of the read-only trio.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:13-18 lists only `path` / `deposit` / `list` / `clean` — no `catalog` (wired at line 1499, and the verb SKILL.md line 95 and SPEC §H.0 line 2373 both name); the same block still documents `clean` with `[--yes] [--dry-run]` and no `--apply`, though --apply is canonical per H-INV-12 (line 510, 1516-1518). SKILL.md line 94 shows `list [--track T]` without the shipped `--json` flag (library.py:1508, handler 485-487).  
*Fails when:* An agent or user reading the script's own usage header never learns `catalog` exists and drives `clean` with the deprecated `--yes`; a skill session wanting machine-readable listings re-parses the human table instead of using `--json`.  
*Fix:* Update the module docstring CLI block to include `catalog [--open]` and show `clean ... --apply` (keeping --yes noted as a back-compat alias), and add `[--json]` to the `list` line in SKILL.md's library block.

**[doc-parity] library.py clean**  
The module docstring's CLI usage for clean still advertises the deprecated --yes (listed twice) and omits --apply, contradicting SKILL.md/SPEC which make --apply canonical and --yes a silent, hidden alias.  
*Evidence:* scripts/library.py:17-18 shows `library.py clean [--all --yes] [--older-than DAYS] [--keep-per-track N] [--track T] [--missing] [--yes] [--dry-run]` — no --apply, --yes duplicated. SKILL.md:829 and docs/SPEC.md:2483 state clean "now takes --apply like the rest (its old --yes remains a silent alias)", and the parser hides --yes with argparse.SUPPRESS (scripts/library.py:1517).  
*Fails when:* A reader following the file's own header uses --yes as the primary confirm flag (invisible in --help), and never learns of --apply; the header also documents --dry-run which currently does nothing (finding 1).  
*Fix:* Update lines 17-18 to `clean [--all] [--older-than DAYS] [--keep-per-track N] [--track T] [--missing] [--apply]`, dropping the duplicate --yes and matching SKILL.md:96-97.

**[consistency] library.py deposit**  
An explicit --widget pointing at a missing file crashes with a raw FileNotFoundError traceback from shutil.copy2 instead of the clean sys.exit message every other deposit failure path produces.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:471 accepts args.widget with no existence check; library.py:400 `shutil.copy2(widget_path, wdir / name)` is the first touch. Contrast the glob path's clean error at line 475 (`sys.exit(f"no widget html found in {run_dir}")`) and the DepositError messages (lines 392-395, 423-436).  
*Fails when:* `library.py deposit --run-dir DIR --widget typo.html` -> after passing all gates, shutil.copy2 raises FileNotFoundError and the user gets a Python traceback rather than a one-line refusal; no bad state is left (the index write never runs), but the failure shape diverges from the command's siblings.  
*Fix:* In _cmd_deposit, after resolving the explicit widget path, `if not widget.exists(): sys.exit(f"widget not found: {widget}")` (or raise DepositError from deposit() before the copy).

**[safety] library.py dereference**  
An empty --album-path value matches every entry, so `dereference --album-path "" --apply` empties the entire library index; the guard only checks that the flag list is non-empty, not that values are.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:1388-1389 rejects only a missing flag ([''] is truthy), and line 1399 `any(ap in src ...)` is True for every entry when ap == '' (Python substring semantics). Mitigated by dry-run default and the index backup (lines 1418-1423), but the subparser help (line 1587-1588, 'under a reference-album path') undersells that matching is bare substring anywhere in the path.  
*Fails when:* A shell variable expands empty (`--album-path "$ALBUM"` with ALBUM unset) and the user re-runs with --apply after skimming a long preview: every entry in the library is dropped in one shot.  
*Fix:* Reject empty/whitespace-only --album-path values with the same sys.exit path as the missing-flag case; consider requiring a minimum path length or anchored (startswith on normalized path) matching.

**[dead-code] library.py dereference**  
The non-dict entry branch in _cmd_dereference is unreachable: load_index coerces every entry to a dict before the handler sees it.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:1395-1397 guards `if not isinstance(e, dict)`, but load_index (line 278) already normalizes: `d["entries"] = [e if isinstance(e, dict) else {"widget": str(e)} for e in raw]`, so no string entry survives to the loop.  
*Fix:* Drop the isinstance guard here (and in the sibling handlers sharing the idiom at lines 543/773/805/836) or keep one shared comment noting load_index guarantees dict entries.

**[spec-parity] library.py gc**  
gc's best-undeposited tiebreak (lexicographic name) diverges from the RC-INV-9 selector's tiebreak (mtime), so on equal result counts gc can prune the exact run the read layer selects — contradicting G-INV-15's promise.  
*Evidence:* scripts/library.py:637,650 — _best_undeposited_run keys on (result_count, item.name); scripts/run_dir.py:93-100 — newest_run (the RC-INV-9 selector) keys on (result_count, mtime). SPEC.md §G.3 G-INV-15 (~line 2294): 'gc therefore preserves, for each slug, the run RC-INV-9 would select'.  
*Fails when:* Slug has undeposited runs 2026-07-10_1200 (5 results, re-run yesterday so newest mtime) and 2026-07-12_0900 (5 results, older mtime). newest_run selects the first (mtime tiebreak); gc keeps the second (name tiebreak) and, on --apply, deletes the run RC-INV-9 was reading from, silently swapping which run's content backs coaching.  
*Fix:* Make _best_undeposited_run use the same tiebreak as run_dir.newest_run (result count, then mtime), or extract one shared selector both call.

**[doc-parity] library.py gc**  
gc's --base flag exists in code and is load-bearing in SPEC G-INV-7, but SKILL.md's gc section never mentions it.  
*Evidence:* scripts/library.py:1564 defines `--base` for gc; SPEC.md §G.3 G-INV-7 (~line 2267-2272) describes gc's behaviour 'when --base is used'; SKILL.md:867-878 (the gc section) lists only the four flag-less/--apply/--ableton-tails/--scan-dir invocations.  
*Fails when:* A user following SKILL.md as the command reference has no way to discover the documented-in-spec --base scoping.  
*Fix:* Add a `library.py gc --base DIR` line (with the G-INV-7 caveat about not pointing it at a music folder) to SKILL.md's gc section.

**[consistency] library.py gc**  
The --ableton-tails dry-run and apply reports omit reclaimed size, unlike sibling gc, falling short of G-INV-8's 'paths, counts, reclaimed size'.  
*Evidence:* scripts/library.py:1264-1281 — prints KEEP/remove paths and a count but no sizes; main gc prints per-dir and total sizes at 1226-1230, 1247. SPEC.md §G.3 G-INV-8 (~line 2274): a deleting command 'shows exactly what it would remove (paths, counts, reclaimed size)'.  
*Fails when:* User previewing `gc --ableton-tails` cannot judge what a removal reclaims or weigh a large 'safe' dir before confirming, unlike every sibling prune verb.  
*Fix:* Reuse _dir_size/_fmt_size in _gc_ableton_tails for per-dir and total sizes in both the dry-run listing and the final removal report.

**[correctness] library.py hard-reset**  
An unreadable output root is misreported as 'already empty' and hard-reset exits 0 — an OSError from iterdir is swallowed into an empty list.  
*Evidence:* /Users/sashaabramovich/.claude/skills/track-coach/scripts/library.py:1164-1171 — `except OSError: contents = []` followed by `if not contents: print(f"hard-reset: {base} is already empty.")`.  
*Fails when:* Permission-denied on ~/.track-coach (or --base pointing at a regular file, which raises NotADirectoryError, an OSError subclass): the command prints 'already empty' and returns success, so the user believes the wipe target holds nothing when it was simply unreadable.  
*Fix:* Let the OSError surface as `sys.exit(f"hard-reset: cannot read {base}: {exc}")` instead of mapping it to the empty case.

**[spec-parity] library.py reset**  
SPEC H-INV-10 names `reset --hard` as an equivalent invocation of the catastrophic wipe, but the reset subparser has no --hard flag, so the spec-documented command line fails with an argparse error.  
*Evidence:* SPEC.md:2461-2462: "demands the strongest confirm: both `--yes-wipe-everything` and an explicit `--including-backups` (equivalently `reset --hard`)". The reset parser at library.py:1542-1551 defines only --base, --yes-wipe-everything, --no-backup, --i-understand; grep for `--hard` in library.py returns nothing.  
*Fails when:* A user following the spec runs `library.py reset --hard` → argparse exits with "unrecognized arguments: --hard" (safe failure, but the spec-documented invocation does not exist).  
*Fix:* Either drop the "(equivalently `reset --hard`)" parenthetical from SPEC.md §H.2, or wire `reset --hard` to route to the hard-reset handler with the same double-confirm requirements.

**[correctness] library.py restore**  
The stamp argument is joined onto backups/ with no validation, so a stamp containing path separators (or an absolute path) escapes backups/ and restores from an arbitrary directory that happens to contain a .backup_ok file.  
*Evidence:* library.py:1014 — `snap_dir = backups_dir / stamp` with no separator/containment check (pathlib makes `backups_dir / "/abs/path"` equal `/abs/path`, and `../x` walks out of backups/); the only guard is the `.backup_ok` existence check at 1017. SPEC.md:2485 (H-INV-11/G-INV-7): cleanup verbs stay within the configured output root.  
*Fails when:* A user tab-completes or pastes a full snapshot path from a different root, e.g. `restore /Volumes/old-mac/.track-coach/backups/2026-06-01_120000 --apply` — restore silently sources tiers from outside the configured root and overwrites the current library with foreign data, with the plan output showing only the basename-like stamp.  
*Fix:* Reject stamps containing os.sep (or resolve snap_dir and require snap_dir.resolve().is_relative_to(backups_dir.resolve())), with a clear error telling the user to pass --base to point at a different root.

**[spec-parity] track_analyzer.py analyze (MEASURE)**  
The pipeline guard catches BaseException, so a Ctrl-C (KeyboardInterrupt) mid-analyze is stamped analysis_state:"failed" — an interruption labelled as terminal failure, against RC-INV-13f/E-4's rule that failure is distinct from interruption.  
*Evidence:* scripts/track_analyzer.py:301-307 — `except BaseException as e:` stamps {"analysis_state": "failed", "analysis_error": str(e)[:200]} before re-raising; str(KeyboardInterrupt()) is "" so the stored error is empty. docs/SPEC.md:1967-1968 — "A run merely interrupted ... keeps the recoverable status 'Analysing — reload when it's ready.'"; the failed marker is reserved for "a terminal step failure it cannot proceed past" (SPEC.md:1969-1972).  
*Fails when:* User Ctrl-C's a long full-mode analyze during Demucs. The run — which would complete fine on re-run — carries the failed marker, so its page renders "Analysis couldn't complete for this track. The source may be unreadable — check the file and re-run." (RC-INV-13f's honest-failure message) — a false diagnosis of the source file for a mere interruption; E-4 was settled precisely to kill the mirror-image false message.  
*Fix:* Re-raise KeyboardInterrupt (and bare SystemExit not originating from a step failure) without stamping "failed", leaving the run at the recoverable "running" state — e.g. `except KeyboardInterrupt: raise` before the BaseException handler.

**[correctness] track_analyzer.py analyze (MEASURE)**  
The --dry-run plan silently omits the map_stems step whenever --als is given without an explicit --als-offset-s (the documented default case) — the plan neither shows the step a real run would execute nor prints the "skipped" note.  
*Evidence:* scripts/track_analyzer.py:195 gates offset resolution on `not args.dry_run`, so offset stays None in dry-run; line 250 `if als and offset is not None:` then skips planning map_stems, and line 253 `elif als and not args.dry_run:` suppresses the skip-note in dry-run too. Verified empirically: `analyze fake.mp3 --als fake.als --dry-run` prints parse_als and separate but no map_stems line and no skip note; adding `--als-offset-s 5` makes map_stems appear. Contradicts the module contract (line 29: "`--dry-run` prints the plan without running anything") and the flag help (line 747: "print the plan; run nothing").  
*Fails when:* An agent or test verifying the pipeline via `analyze AUDIO --als PROJ --dry-run` (SKILL.md line 70: "Add --dry-run to print the plan") sees no stem↔project mapping step and concludes the map won't be produced — while a real run resolves the offset from the first locator (SKILL.md line 53) and does run it.  
*Fix:* In dry-run, print the map_stems step with a placeholder offset (e.g. '<FIRST_LOCATOR>') when als is given and no explicit offset, or at minimum print a plan note "map_stems: offset resolved from the .als at run time".

**[safety] track_analyzer.py analyze (MEASURE)**  
_update_meta rewrites run_meta.json non-atomically (in-place write_text, no temp+rename), and analyze calls it 4-7 times per run — a hard kill mid-write tears the file, which every reader then silently degrades to {}, losing audio_path/mode/analysis_state.  
*Evidence:* scripts/track_analyzer.py:356-364 — `mp.write_text(json.dumps(meta, ...))` with `except ValueError: meta = {}` on read; called at lines 167, 203, 209, 213, 221, 224, 300, 304. _complete_run (lines 616-621) reads audio_path from this file and, when it's gone, reports the source "unrecorded or gone — re-analyse it from the file by hand"; validity/_run_meta (582-585) likewise fall back to {}.  
*Fails when:* A kill -9 or OOM (RC-INV-13f's own named scenario) lands during one of the run_meta rewrites (e.g. the fingerprint/tags stamp under Demucs memory pressure). run_meta.json is left truncated: the run loses not just analysis_state (spec promises a hard-killed run "leaves the run at 'running'", SPEC.md:1983-1985) but the audio_path that run_dir.py init recorded — so the RC-INV-13c backfill can no longer complete the run automatically and the failed/in-progress page loses its source block (RC-INV-13g).  
*Fix:* Write atomically: dump to `run_meta.json.tmp` in the same dir and `os.replace()` over the original, so a kill at any instant leaves either the old or the new complete file.

**[doc-parity] track_analyzer.py analyze (MEASURE)**  
Three analyze flags — --bpm, --skip-transcribe, and --model — appear nowhere in SKILL.md or SPEC §H; the docs' analyze usage line lists only --als/--als-offset-s/--mode/--track-version.  
*Evidence:* scripts/track_analyzer.py:742-746 define --model (Demucs model choice), --bpm (tempo override for rhythm), --skip-transcribe; grep over SKILL.md, docs/SPEC.md, commands/, README.md finds no occurrence of --bpm or --skip-transcribe, and --model only inside SKILL.md's internal step reference (line 401, the hand-driven separate.py command, not the analyze entrypoint). SKILL.md:54-56 is the documented analyze surface.  
*Fails when:* A wrong core tempo read (the case --bpm exists for) or a need to skip basic-pitch leaves the agent hand-driving internal steps — exactly what SKILL.md lines 40-42 forbid — because the entrypoint's own override flags are undiscoverable from the docs.  
*Fix:* Add the three flags to SKILL.md's analyze usage block (one bracketed line: `[--bpm N] [--skip-transcribe] [--model NAME]`), and mention --bpm as the tempo-override escape hatch where SKILL.md discusses rhythm.

**[correctness] track_analyzer.py build (RENDER + deposit)**  
build's stdout contract (the rebuilt widget path) is contaminated by the default backfill: nested builds append other tracks' widget paths to stdout after the requested run's path.  
*Evidence:* track_analyzer.py:573 prints the widget path to stdout as the command's machine-readable result, then :576-577 runs `_backfill_incomplete()`, whose `_complete_run` at :643 launches a nested `build` via `subprocess.run(build_cmd)` with stdout inherited — that child hits its own :573 and prints ITS widget path into the parent's stdout. (The codebase itself relies on stdout contracts: `_complete_run` parses analyze's stdout JSON at :629-635.)  
*Fails when:* A script (or the skill) captures `build --run-dir X`'s stdout to open the widget and reads the last line: when the library held an incomplete run, the last line is the backfilled track's widget path, so the wrong widget opens/deposit is reported for the wrong file.  
*Fix:* Run the nested build with `capture_output=True` (relaying to stderr), or print the requested run's widget path after the backfill completes, so the parent's stdout stays exactly one path.

**[doc-parity] track_analyzer.py build (RENDER + deposit)**  
SKILL.md and the module docstring sell `build` as 'cheap … no recompute', but a bare build can by default launch full Demucs re-analysis of every incomplete library run; `--only-this` and `--no-catalog` are absent from SKILL.md.  
*Evidence:* track_analyzer.py:22-23 ('cheap rebuild (no recompute)') and SKILL.md:60 ('# 3) RENDER (cheap, one pass)') vs track_analyzer.py:576-577/:659-668 (default backfill re-measures incomplete deposits — Demucs). `grep -n 'only-this\|--no-catalog' SKILL.md` → no hits; SKILL.md's build example (:62-64) shows only --title/--verdict/--mood-tags/--style-tags (plus --no-deposit/--strings/--dry-run elsewhere).  
*Fails when:* The skill (or user) runs the documented 'cheap, one pass' render expecting seconds and gets a multi-minute Demucs pass over unrelated tracks, with no documented `--only-this` opt-out to reach for (the flag exists only in --help).  
*Fix:* Add one line to SKILL.md's step 3 and the module docstring: a bare build also tops up incomplete prior library runs (RC-INV-13c, can run Demucs); pass `--only-this` to render exactly this run; document `--no-catalog` alongside `--no-deposit`.

**[spec-parity] track_analyzer.py build (RENDER + deposit)**  
G-INV-21 states the synthetic marker is set by 'the --synthetic flag on build'; the flag actually lives on `analyze` — `build` has no --synthetic.  
*Evidence:* SPEC.md:2176-2178 ('The marker is set two ways — the `--synthetic` flag on `build`, and automatically when the analysed source lives under the test fixtures tree') vs track_analyzer.py:752-753 (--synthetic defined on the `analyze` subparser) and :760-779 (the `build` subparser defines no such flag; the marker is only read back from run_meta by deposit_from_run, library.py:426-429).  
*Fails when:* Someone implementing or testing against §G passes `build --synthetic --run-dir …` and gets an argparse error; conversely a spec-driven test of the deposit guard exercises the wrong subcommand. The guard itself works — the spec names the wrong host command.  
*Fix:* Fix the SPEC.md sentence to say 'the `--synthetic` flag on `analyze`' (matching G-INV-18's analyze-side `--reference`), or, if the marker should also be settable at render time, add the flag to the build subparser.
