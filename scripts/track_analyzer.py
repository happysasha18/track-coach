#!/usr/bin/env python3
"""track-analyzer — the measure-and-render engine (the 0.6 architecture).

NAMING: the "coaching" (interpretation — what kind of track, what to change) is the SKILL's
job. This engine only measures and renders, deterministically, with no opinion — so it's the
*analyzer*, not the coach. "Track Coach" is the skill that drives it and writes the read.

WHY THIS EXISTS
---------------
The whole analysis used to be hand-driven by the agent through ~40 KB of step-by-step
prose in SKILL.md: create the run dir, run core, run detail, parse the .als, separate,
point masking/map_stems/rhythm/drums/web-stems at the SAME stems dir, build, catalog,
rebuild. Every bug this project ever shipped lived in those *seams* — the zsh word-split
on `$UV`, the `stems/` vs `stems_6s/` path mismatch that silently dropped the player.
Those are integration bugs, not analysis bugs: the scripts were always fine. So the fix
is to move the brittle orchestration DOWN into one deterministic entrypoint and leave the
agent doing what it's actually good at — reading the numbers and writing the Producer's read.

  track-analyzer analyze AUDIO [--als F --als-offset-s N] [--mode quick|full] ...
      run the deterministic pipeline (Steps 0c-4) and build a first widget.

  track-analyzer build --run-dir DIR [--verdict ... --narrative read.md] ...
      cheap rebuild (no recompute) that injects the agent's read + the catalog.
      The agent calls this AFTER writing narrative.md / picking a verdict.

Pure stdlib: runs under plain `python3`, instant, no deps. Every heavy step is shelled out
to `tc_uv.sh <profile> <script>` so dependency profiles (core/fast/deep/bp) stay isolated
and the run is shell-agnostic. A single `$STEMS` var feeds every deep step — the path-class
bug cannot recur. `--dry-run` prints the plan without running anything.
"""
import argparse, hashlib, json, os, re, shlex, subprocess, sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_DIR / "scripts"
TCUV = SCRIPTS / "tc_uv.sh"


def tc_version() -> str:
    """The canonical analyzer version (single source of truth in build_widget.py)."""
    try:
        m = re.search(r'TC_VERSION\s*=\s*"([^"]+)"', (SCRIPTS / "build_widget.py").read_text())
        return m.group(1) if m else "0"
    except OSError:
        return "0"


class Runner:
    """Runs (or, in dry-run, prints) pipeline steps. Fails loudly with the failing step."""

    def __init__(self, dry: bool):
        self.dry = dry

    def step(self, profile: str, script: str, *args: str):
        cmd = ["bash", str(TCUV), profile, str(SCRIPTS / script), *map(str, args)]
        self._run(cmd, f"{script} ({profile})")

    def plain(self, *args: str, capture: bool = False):
        cmd = ["python3", *map(str, args)]
        return self._run(cmd, "run_dir.py", capture=capture)

    def _run(self, cmd, label: str, capture: bool = False):
        if self.dry:
            print("  $ " + " ".join(shlex.quote(c) for c in cmd))
            return ""
        try:
            if capture:
                return subprocess.run(cmd, check=True, text=True,
                                      stdout=subprocess.PIPE).stdout
            subprocess.run(cmd, check=True)
            return ""
        except subprocess.CalledProcessError as e:
            sys.exit(f"\n✗ track-coach: step failed — {label} (exit {e.returncode}).\n"
                     f"  command: {' '.join(shlex.quote(c) for c in cmd)}")


# ── shared widget build (used by `analyze`'s first build and by `build`) ──────────────

def widget_name(track_version: str) -> str:
    # self-identifying filename; falls back to the analyzer version when no real track version
    return f"analysis_widget_{track_version or 'v' + tc_version()}.html"


def build_widget(rn: Runner, out_dir: Path, *, title, src_audio, src_als, track_version,
                 verdict, offset, strings, catalog, narrative, mode="full"):
    """Construct the build_widget call from whatever result files exist in out_dir.

    Mirrors SKILL.md's `[ -f result_X.json ] && --flag` logic so the widget degrades
    gracefully: a panel renders only when its data is present.
    """
    def have(name): return (out_dir / name).exists()
    args = ["--core", out_dir / "result_core.json",
            "--detail", out_dir / "result_detail.json",
            "--out", out_dir / widget_name(track_version)]
    if mode:                        args += ["--mode", mode]
    if title:                       args += ["--title", title]
    if src_audio:                   args += ["--src-audio", src_audio]
    if src_als:                     args += ["--src-als", src_als]
    if track_version:               args += ["--track-version", track_version]
    if verdict:                     args += ["--verdict", verdict]
    if have("result_masking.json"): args += ["--masking", out_dir / "result_masking.json"]
    if have("result_als.json"):     args += ["--als", out_dir / "result_als.json"]
    if offset is not None:          args += ["--als-offset-s", offset]
    if have("result_stemmap.json"): args += ["--stemmap", out_dir / "result_stemmap.json"]
    if have("result_rhythm.json"):  args += ["--rhythm", out_dir / "result_rhythm.json"]
    if have("result_notes_other.json"): args += ["--notes", out_dir / "result_notes_other.json"]
    if have("result_drums.json"):   args += ["--drums-breakdown", out_dir / "result_drums.json"]
    if have("result_selfsim.json"): args += ["--selfsim", out_dir / "result_selfsim.json"]
    if (out_dir / "stems_web").is_dir(): args += ["--audio-stems-rel", "stems_web"]
    elif (out_dir / "mix_web").is_dir(): args += ["--audio-mix-rel", "mix_web"]  # quick → single-mix player
    if strings:                     args += ["--strings", strings]
    if catalog:                     args += ["--catalog", catalog]
    try:  # the global library index → wires the always-present ← Library back button
        import library as _lib
        args += ["--back-href", (_lib.library_root() / "index.html").resolve().as_uri()]
    except Exception:
        pass
    nar = narrative or (out_dir / "narrative.md" if have("narrative.md") else None)
    if nar:                         args += ["--narrative", nar]
    rn.step("fast", "build_widget.py", *args)
    return out_dir / widget_name(track_version)


def add_catalog(rn: Runner, out_dir: Path) -> str:
    """run_dir catalog --self OUT -> path to catalog.json (last stdout line)."""
    out = rn.plain(SCRIPTS / "run_dir.py", "catalog", "--self", out_dir, capture=True)
    if rn.dry:
        return str(out_dir / "catalog.json")
    return out.strip().splitlines()[-1] if out.strip() else ""


# ── analyze: the deterministic pipeline (Steps 0c-4) ──────────────────────────────────

def cmd_analyze(args):
    rn = Runner(args.dry_run)
    audio = Path(args.audio).expanduser().resolve()
    if not args.dry_run and not audio.exists():
        sys.exit(f"audio not found: {audio}")
    als = Path(args.als).expanduser().resolve() if args.als else None
    offset = None if args.als_offset_s is None else str(args.als_offset_s)

    # Step 0c — versioned run dir (never overwrite). run_dir prints its path last.
    init = [SCRIPTS / "run_dir.py", "init", "--audio", audio, "--mode", args.mode]
    if als:               init += ["--als", als]
    if args.track_version: init += ["--track-version", args.track_version]
    if args.base:         init += ["--base", args.base]
    if args.dry_run:
        rn.plain(*init)
        out_dir = Path("<RUN_DIR>")
    else:
        out_dir = Path(rn.plain(*init, capture=True).strip().splitlines()[-1])
    print(f"\n▶ run dir: {out_dir}", file=sys.stderr)
    # Carry a prior hand-written Producer's read forward so re-analysing a track never silently
    # drops it (you can still overwrite narrative.md before `build`).
    if not args.dry_run:
        src = inherit_prior_read(out_dir)
        if src is not None:
            print(f"  · inherited narrative.md / title / verdict from {Path(src).name} "
                  f"(edit {out_dir/'narrative.md'} to update)", file=sys.stderr)

    def j(name): return out_dir / name

    # Step 1 — fast analysis (audio only)
    rn.step("core", "analyze_core.py", audio, "--out", j("result_core.json"))
    rn.step("fast", "analyze_detail.py", audio, "--out", j("result_detail.json"))
    # Step 2 — .als (if given)
    if als:
        rn.step("fast", "parse_als.py", als, "--out", j("result_als.json"))
        # Render offset = where (in project seconds) the audio starts. DEFAULT to the first
        # locator — that's the common case (e.g. Shared Memories starts at locator 1). Override
        # with --als-offset-s when the render starts elsewhere (e.g. Fragile started at locator 13).
        offset_source = "explicit" if offset is not None else None
        if offset is None and not args.dry_run:
            off, offset_source = default_render_offset(j("result_als.json"))
            if off is not None:
                offset = str(off)
                print(f"  · --als-offset-s not given → using the .als start ({off}s, via "
                      f"{offset_source}); pass --als-offset-s to override.", file=sys.stderr)
        # record the offset AND how it was found, so the run is self-documenting
        if offset is not None and not args.dry_run:
            _update_meta(out_dir, {"als_offset_s": float(offset), "als_offset_source": offset_source})
    # VERSION IDENTITY + DRAFT TAGS — content hash keys the catalog's "versions" (same audio = same
    # version, even across re-analyses); heuristic mood/style tags seed the catalog so a track is
    # never tagless. Both are best-effort and never block the measure. The agent overrides the tags
    # later via `build --mood-tags/--style-tags` (tags_source flips heuristic→agent).
    if not args.dry_run:
        _update_meta(out_dir, _audio_fingerprint(audio))
        try:
            import tags as _tags
            draft = _tags.derive_tags(json.loads(j("result_core.json").read_text()))
            _update_meta(out_dir, {"energy_level": draft["energy_level"],
                                   "mood_tags": draft["mood_tags"],
                                   "style_tags": draft["style_tags"],
                                   "tags_source": "heuristic"})
        except Exception as e:  # noqa: BLE001 — draft tags are a convenience, not a hard dep
            print(f"  · draft tags skipped: {e}", file=sys.stderr)

    # STRUCTURE — repeats/form (full mix; no stems/als needed; cheap, always run)
    rn.step("fast", "self_similarity.py", audio, "--out", j("result_selfsim.json"))

    if args.mode == "full":
        # Step 3 — Demucs. ONE stems dir feeds every later step (kills the path-class bug).
        stems = out_dir / ("stems_6s" if args.model.endswith("6s") else "stems")
        rn.step("deep", "separate.py", audio, "--model", args.model, "--out-dir", stems)
        manifest = stems / "stems_manifest.json"
        rn.step("fast", "masking.py", "--manifest", manifest, "--out", j("result_masking.json"))
        # B — stem<->project map: needs the .als AND the render offset (defaulted above)
        if als and offset is not None:
            rn.step("fast", "map_stems.py", "--stems-dir", stems, "--als", j("result_als.json"),
                    "--als-offset-s", offset, "--out", j("result_stemmap.json"))
        elif als and not args.dry_run:
            print("  · stem↔track map skipped: no locator to align the .als to the audio",
                  file=sys.stderr)
        # C — rhythm/separation quality (tempo from core unless overridden)
        bpm = args.bpm or _core_tempo(out_dir, args.dry_run)
        rhythm = ["--manifest", manifest, "--out", j("result_rhythm.json")]
        if bpm:
            rhythm += ["--tempo", str(bpm)]
        rn.step("fast", "rhythm_quality.py", *rhythm)
        # D — drum hits + (optional) note transcription
        rn.step("fast", "drum_breakdown.py", "--drums", stems / "drums.wav",
                "--out", j("result_drums.json"))
        if not args.skip_transcribe:
            rn.step("bp", "transcribe.py", "--stem", stems / "other.wav", "--label", "other",
                    "--out", j("result_notes_other.json"))
        # E — web stems: MANDATORY, makes the player + per-stem lanes appear
        rn.step("fast", "make_web_stems.py", "--stems-dir", stems, "--out-dir", out_dir / "stems_web")
    elif args.mode == "quick":
        # Quick has no Demucs stems, but it DOES have the mix — encode a compressed copy so the widget
        # still gets a single-track player (transport + seek; no per-stem mute/solo). Sasha 2026-06-20:
        # "плеер какая разница быстрый прогон?". No separation, so still fast.
        rn.step("fast", "make_web_stems.py", "--audio", audio, "--out-dir", out_dir / "mix_web")

    # MEASURING DONE — no render here. The widget is rendered ONCE, by `build`, AFTER the read.
    # Order is forced by the anti-hallucination design: measure → interpret → render. Building a
    # widget now (before the read) would just be thrown away on the rebuild, so we don't.
    print(f"\n✓ measured. run dir: {out_dir}", file=sys.stderr)
    print(json.dumps({"run_dir": str(out_dir), "mode": args.mode,
                      "als_offset_s": float(offset) if offset is not None else None},
                     ensure_ascii=False))
    if not args.dry_run:
        print("\nNext: read the result_*.json, write your Producer's read to "
              f"{out_dir/'narrative.md'},\nthen render it once:\n"
              f"  python3 {Path(__file__).name} build --run-dir {shlex.quote(str(out_dir))} "
              "--verdict \"…\"", file=sys.stderr)


def default_render_offset(als_json: Path):
    """Where (in project seconds) the render starts, best-effort, in priority order:
    1) the earliest locator; 2) if there are none, the earliest clip start (audio or MIDI).
    Returns (seconds, source) with source in {"first_locator","earliest_clip"}, or (None, None)."""
    try:
        d = json.loads(als_json.read_text())
    except (OSError, ValueError):
        return None, None
    locs = [m["time_s"] for m in d.get("markers", []) if isinstance(m.get("time_s"), (int, float))]
    if locs:
        return round(min(locs), 3), "first_locator"
    clips = [c["start_s"] for tr in d.get("tracks", [])
             for key in ("audio_clips", "midi_clips")
             for c in tr.get(key, []) if isinstance(c.get("start_s"), (int, float))]
    return (round(min(clips), 3), "earliest_clip") if clips else (None, None)


def _audio_fingerprint(audio: Path) -> dict:
    """Content hash + mtime/size of the source audio. The sha256 is the VERSION identity in the
    catalog: a different bounce ⇒ different hash ⇒ a new version; the same bounce re-analysed keeps
    the same version. mtime gives a human timestamp/sort. Best-effort (returns {} on error)."""
    h = hashlib.sha256()
    try:
        with open(audio, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        st = audio.stat()
        return {"audio_sha256": h.hexdigest(), "audio_mtime": int(st.st_mtime),
                "audio_size": st.st_size}
    except OSError:
        return {}


def _update_meta(out_dir: Path, fields: dict):
    """Persist resolved facts (e.g. the render offset) into run_meta.json so `build` reuses them."""
    mp = out_dir / "run_meta.json"
    try:
        meta = json.loads(mp.read_text()) if mp.exists() else {}
    except ValueError:
        meta = {}
    meta.update(fields)
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def resolve_build_inputs(meta: dict, run_dir, *, title=None, verdict=None, narrative=None):
    """Decide title / verdict / narrative for a (re)build. Pure & testable.

    Precedence per field: explicit flag > persisted run_meta > derived/auto. A bare `build`
    (no flags) must NEVER silently drop what a previous build set — that exact regression
    (title vanished, narrative vanished on rebuild) is what these rules + their tests guard.
      • title:     flag → meta['title'] → "<track> <version>" → None
      • verdict:   flag → meta['verdict'] → None
      • narrative: flag → <run_dir>/narrative.md if it exists → None
    """
    run_dir = Path(run_dir)
    rt = title or meta.get("title") or (
        f"{meta.get('track','')} {meta.get('track_version','')}".strip() or None)
    rv = verdict or meta.get("verdict")
    nar_default = run_dir / "narrative.md"
    nar = narrative or (str(nar_default) if nar_default.exists() else None)
    return {"title": rt, "verdict": rv, "narrative": nar}


def pick_inherit_source(run_dirs, current, has_narrative):
    """Pick the run dir to inherit a prior Producer's read from. Pure & testable.

    Run dirs are named by timestamp (`YYYY-MM-DD_HHMM`) so a lexical sort is chronological.
    Among siblings that actually have a narrative (per `has_narrative`), excluding `current`,
    return the most recent. None if there's nothing to inherit.
    """
    cur = Path(current).name
    cands = [d for d in run_dirs if Path(d).name != cur and has_narrative(d)]
    return max(cands, key=lambda d: Path(d).name) if cands else None


def inherit_prior_read(out_dir: Path):
    """Carry a hand-written Producer's read forward when re-analysing a track.

    A fresh `analyze` makes a NEW dated run dir; without this, the narrative.md / title / verdict
    a human wrote for an earlier run of the SAME track silently vanish from the new widget (the
    exact "producer view lost" bug). So: if the new run has no narrative, copy the most recent
    sibling's narrative.md, and seed title/verdict from its run_meta. Returns the source dir or None.
    """
    out_dir = Path(out_dir)
    track_dir = out_dir.parent
    if not track_dir.is_dir():
        return None
    sibs = [p for p in track_dir.iterdir() if p.is_dir()]
    src = pick_inherit_source(sibs, out_dir, lambda d: (Path(d) / "narrative.md").exists())
    if not src:
        return None
    src = Path(src)
    dst_nar = out_dir / "narrative.md"
    if not dst_nar.exists():
        dst_nar.write_text((src / "narrative.md").read_text(encoding="utf-8"), encoding="utf-8")
    pm = src / "run_meta.json"
    if pm.exists():
        try:
            pmeta = json.loads(pm.read_text())
        except ValueError:
            pmeta = {}
        seed = {k: pmeta[k] for k in ("title", "verdict") if pmeta.get(k)}
        # don't clobber anything the new run already set
        try:
            cur_meta = json.loads((out_dir / "run_meta.json").read_text())
        except (OSError, ValueError):
            cur_meta = {}
        seed = {k: v for k, v in seed.items() if not cur_meta.get(k)}
        if seed:
            _update_meta(out_dir, seed)
    return src


def _register_run(out_dir: Path, widget_file: str, verdict):
    """Record THIS run's widget filename + verdict into the base index.json, matching by run_dir.
    Must happen BEFORE the catalog is generated so the run shows up in its OWN 'All analyses' list
    (the catalog reads widget+verdict from the index). This is what lets us render only once."""
    idx_path = out_dir.parent.parent / "index.json"
    try:
        idx = json.loads(idx_path.read_text())
    except (OSError, ValueError):
        return
    changed = False
    for e in idx.get("runs", []):
        try:
            same = Path(e.get("run_dir", "")).resolve() == out_dir.resolve()
        except OSError:
            same = False
        if same:
            e["widget"] = widget_file
            if verdict:
                e["verdict"] = verdict
            changed = True
    if changed:
        idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2))


def _core_tempo(out_dir: Path, dry: bool):
    if dry:
        return None
    try:
        c = json.loads((out_dir / "result_core.json").read_text())
        return c.get("tempo") or c.get("vitals", {}).get("tempo_bpm")
    except (OSError, ValueError):
        return None


# ── build: cheap rebuild that injects the read + catalog (no recompute) ────────────────

def cmd_build(args):
    rn = Runner(args.dry_run)
    out_dir = Path(args.run_dir).expanduser().resolve()
    if not args.dry_run and not out_dir.exists():
        sys.exit(f"run dir not found: {out_dir}")
    meta = {}
    mp = out_dir / "run_meta.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text())
        except ValueError:
            meta = {}
    # title/verdict/narrative: reuse anything a previous build set (see resolve_build_inputs),
    # then write title/verdict back so they stay sticky across future bare rebuilds.
    r = resolve_build_inputs(meta, out_dir, title=args.title, verdict=args.verdict,
                             narrative=args.narrative)
    title, verdict, narrative = r["title"], r["verdict"], r["narrative"]
    if not args.dry_run:
        keep = {}
        if title:   keep["title"] = title
        if verdict: keep["verdict"] = verdict
        # Agent-authored tags override the heuristic draft (flips tags_source → agent). Comma-split,
        # trimmed; an explicit empty string clears that list. Only the given list is touched.
        if args.mood_tags is not None or args.style_tags is not None:
            if args.mood_tags is not None:
                keep["mood_tags"] = [t.strip() for t in args.mood_tags.split(",") if t.strip()]
            if args.style_tags is not None:
                keep["style_tags"] = [t.strip() for t in args.style_tags.split(",") if t.strip()]
            keep["tags_source"] = "agent"
        if keep:    _update_meta(out_dir, keep)
    src_audio = args.src_audio or meta.get("audio")
    src_als = args.src_als or meta.get("als")
    track_version = args.track_version or meta.get("track_version") or ""
    # offset: explicit flag > persisted run_meta > resolved from the .als (locator/clip)
    if args.als_offset_s is not None:
        offset, offset_source = args.als_offset_s, "explicit"
    elif meta.get("als_offset_s") is not None:
        offset, offset_source = meta["als_offset_s"], meta.get("als_offset_source")
    elif (out_dir / "result_als.json").exists():
        offset, offset_source = default_render_offset(out_dir / "result_als.json")
    else:
        offset, offset_source = None, None
    if offset is not None and not args.dry_run:
        _update_meta(out_dir, {"als_offset_s": float(offset), "als_offset_source": offset_source})
    offset = None if offset is None else str(offset)
    # register this run (widget filename + verdict) BEFORE the catalog, so it lists itself correctly
    if not args.dry_run:
        _register_run(out_dir, widget_name(track_version), verdict)
    cat = "" if args.no_catalog else add_catalog(rn, out_dir)
    widget = build_widget(rn, out_dir, title=title, src_audio=src_audio, src_als=src_als,
                          track_version=track_version, verdict=verdict, offset=offset,
                          strings=args.strings, catalog=cat,
                          narrative=narrative, mode=meta.get("mode", "full"))
    print(f"✓ rebuilt: {widget}", file=sys.stderr)
    # Deposit the rendered widget into the global library (best-effort; never fail the build).
    if not args.dry_run and not args.no_deposit:
        try:
            import library
            meta_now = json.loads((out_dir / "run_meta.json").read_text()) if (out_dir / "run_meta.json").exists() else meta
            entry = library.deposit_from_run(out_dir, widget, meta_now)
            print(f"  · library: {library.library_root() / 'widgets' / entry['widget']}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 — library is a convenience, not a hard dep
            print(f"  · library deposit skipped: {e}", file=sys.stderr)
        # Regenerate the global catalog page so it's always current (the front-end of the library).
        try:
            import catalog
            print(f"  · catalog: {catalog.build_catalog()}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 — catalog is a convenience, not a hard dep
            print(f"  · catalog skipped: {e}", file=sys.stderr)
    print(str(widget))


# ── cli ───────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="track-analyzer", description="track-analyzer engine (measure + render)")
    p.add_argument("--version", action="version", version=f"track-analyzer {tc_version()}")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="MEASURE: run the deterministic pipeline → result JSON + stems")
    a.add_argument("audio")
    a.add_argument("--als", default=None)
    a.add_argument("--als-offset-s", type=float, default=None,
                   help="project time (s) where the render starts (default: first locator / first clip)")
    a.add_argument("--mode", default="full", choices=["quick", "full"],
                   help="quick = fast analysis; single-mix player only (no Demucs stems → no per-stem "
                        "lanes/masking/section instrument labels); full = everything")
    a.add_argument("--model", default="htdemucs_6s", help="Demucs model (6s gives guitar+piano stems)")
    a.add_argument("--track-version", default=None, help="REAL version from the source name only; never invent")
    a.add_argument("--bpm", type=float, default=None, help="override tempo for rhythm (default: from core)")
    a.add_argument("--base", default=None, help="output base (default: <audio_dir>/track-coach-output)")
    a.add_argument("--skip-transcribe", action="store_true")
    a.add_argument("--dry-run", action="store_true", help="print the plan; run nothing")
    a.set_defaults(func=cmd_analyze)
    # NOTE: render-only flags (--title/--verdict/--src-audio/--strings) live on `build`, not here —
    # analyze only measures; the widget (and the read it carries) is rendered by `build`.

    b = sub.add_parser("build", help="rebuild the widget for an existing run (inject read + catalog)")
    b.add_argument("--run-dir", required=True)
    b.add_argument("--verdict", default=None)
    b.add_argument("--narrative", default=None, help="read file (default: <run-dir>/narrative.md if present)")
    b.add_argument("--title", default=None)
    b.add_argument("--mood-tags", default=None,
                   help="comma-separated mood tags (overrides the heuristic draft; '' clears)")
    b.add_argument("--style-tags", default=None,
                   help="comma-separated style/genre tags (overrides the heuristic draft; '' clears)")
    b.add_argument("--src-audio", default=None)
    b.add_argument("--src-als", default=None)
    b.add_argument("--track-version", default=None)
    b.add_argument("--als-offset-s", type=float, default=None)
    b.add_argument("--strings", default=None)
    b.add_argument("--no-catalog", action="store_true", help="skip the cross-version catalog")
    b.add_argument("--no-deposit", action="store_true", help="don't copy the widget into the global library")
    b.add_argument("--dry-run", action="store_true")
    b.set_defaults(func=cmd_build)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
