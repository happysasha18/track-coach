#!/usr/bin/env python3
"""track-coach global library — one place that collects every rendered widget.

Each `build` deposits its offline HTML here (the widget is self-contained, so the library
archives just the HTML, never stems/audio/JSON). Lets you browse/prune analyses across tracks
without digging through per-project `track-coach-output/` folders.

Layout (root = $TRACK_COACH_LIBRARY or ~/.track-coach/library):
  <root>/widgets/<track>__<version>__<stamp>.html
  <root>/index.json   {"entries": [ {track, version, stamp, widget, verdict, mode,
                                      deposited_at, src_run_dir}, … ]}

CLI:
  library.py path
  library.py deposit --run-dir DIR [--widget FILE]
  library.py list [--track T] [--json]
  library.py clean [--all --yes] [--older-than DAYS] [--keep-per-track N] [--track T]
                   [--missing] [--yes] [--dry-run]

The naming + clean policy live in PURE functions (canonical_widget_name, clean_plan) so they're
unit-tested without touching the filesystem.
"""
import argparse, json, os, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path


# ── pure helpers (tested) ──────────────────────────────────────────────────────────────
def library_root() -> Path:
    env = os.environ.get("TRACK_COACH_LIBRARY")
    return Path(env).expanduser() if env else Path.home() / ".track-coach" / "library"


def sanitize(s: str) -> str:
    """Filesystem-safe token: keep word chars, dash, dot; collapse the rest to '-'."""
    s = (s or "").strip()
    s = re.sub(r"[^\w.\-]+", "-", s, flags=re.UNICODE).strip("-")
    return s or "untitled"


def canonical_widget_name(track: str, version: str, stamp: str) -> str:
    """`<track>__<version>__<stamp>.html` — stable, collision-resistant, sortable."""
    return f"{sanitize(track)}__{sanitize(version or 'v0')}__{sanitize(stamp or 'na')}.html"


def _age_days(deposited_at: str, now: datetime) -> float:
    try:
        dt = datetime.fromisoformat(deposited_at)
    except (ValueError, TypeError):
        return -1.0  # unknown age never matches an --older-than cutoff
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 86400.0


def clean_plan(entries, *, now=None, exists=None, older_than_days=None,
               keep_per_track=None, track=None, missing=False, all_=False):
    """Decide which library entries to remove. PURE — no filesystem.

    Scope: restricted to `track` when given, else all entries. Within scope an entry is removed if:
      • all_                         → everything in scope, or
      • older_than_days and older    → deposited more than N days ago, or
      • missing and not exists(e)    → its widget file is gone (exists() is injectable), or
      • keep_per_track=N             → it's beyond the newest N (by stamp) for its track.
    Returns (keep, remove), each a list preserving input order.
    """
    now = now or datetime.now(timezone.utc)
    exists = exists or (lambda e: True)
    in_scope = [e for e in entries if track is None or e.get("track") == track]
    rm = set()  # ids = position in `entries`
    idx = {id(e): i for i, e in enumerate(entries)}

    if all_:
        rm |= {idx[id(e)] for e in in_scope}
    else:
        if older_than_days is not None:
            rm |= {idx[id(e)] for e in in_scope
                   if _age_days(e.get("deposited_at", ""), now) > older_than_days}
        if missing:
            rm |= {idx[id(e)] for e in in_scope if not exists(e)}
        if keep_per_track is not None:
            by_track = {}
            for e in in_scope:
                by_track.setdefault(e.get("track"), []).append(e)
            for grp in by_track.values():
                grp_sorted = sorted(grp, key=lambda e: e.get("stamp", ""), reverse=True)
                for e in grp_sorted[keep_per_track:]:
                    rm.add(idx[id(e)])

    keep = [e for i, e in enumerate(entries) if i not in rm]
    remove = [e for i, e in enumerate(entries) if i in rm]
    return keep, remove


# ── catalog data: metrics, arc sparkline, version grouping (all PURE, tested) ────────────
def downsample_curve(arr, n=40):
    """Downsample a 0..1 curve to ~n points by bucket-averaging — the catalog's mini-arc. Pure."""
    vals = [float(x) for x in (arr or []) if isinstance(x, (int, float))]
    if not vals:
        return []
    if len(vals) <= n:
        return [round(v, 3) for v in vals]
    out = []
    for i in range(n):
        lo = i * len(vals) // n
        hi = max(lo + 1, (i + 1) * len(vals) // n)
        seg = vals[lo:hi]
        out.append(round(sum(seg) / len(seg), 3))
    return out


def run_metrics(core: dict, meta: dict) -> dict:
    """Catalog-facing fields for an index entry, from already-loaded core + run_meta. Pure.

    Pulls the spec numbers (bpm/key/lufs/dr/length), a downsampled energy arc (the mini-diagram),
    the agent/heuristic tags, the title, and the audio content hash (the version identity).

    Also stores the catalog ROW SIGNATURE: energy/brightness/density curves (downsampled to a common
    length so they align point-for-point in the row's spectral ribbon) + the 9-band `tonal_balance`
    (band, rel_db, dev_db) for the row's tonal strip. Old entries lacking these degrade to the
    ribbon-only / legacy `arc` sparkline in the catalog view (see catalog.signature_svg)."""
    core = core or {}
    meta = meta or {}
    v = core.get("vitals", {}) or {}
    return {
        "bpm": v.get("tempo_bpm") or core.get("tempo"),
        "key": v.get("key"),
        "lufs": v.get("lufs"),
        "dr": v.get("dynamic_range_db"),
        "length_s": v.get("duration_s") or core.get("duration_s"),
        "arc": downsample_curve(core.get("energy"), 40),
        # row signature — three curves at a shared length (ribbon: height=energy, colour=brightness,
        # weight=density) + the spectrum (tonal strip). ~48 pts keeps the SVG small but still shaped.
        "energy": downsample_curve(core.get("energy"), 48),
        "brightness": downsample_curve(core.get("brightness"), 48),
        "density": downsample_curve(core.get("density"), 48),
        "tonal_balance": [
            {"band": b.get("band"), "rel_db": b.get("rel_db"), "dev_db": b.get("dev_db")}
            for b in (core.get("tonal_balance") or []) if isinstance(b, dict)
        ],
        "energy_level": meta.get("energy_level"),
        "mood_tags": meta.get("mood_tags") or [],
        "style_tags": meta.get("style_tags") or [],
        "tags_source": meta.get("tags_source"),
        "title": meta.get("title"),
        "audio_sha": meta.get("audio_sha256"),
    }


def group_versions(entries: list) -> dict:
    """Group index entries into tracks → versions for the catalog. PURE — no filesystem.

    A "version" = a distinct audio bounce, keyed by `audio_sha` (entries lacking a hash fall back to
    their widget name, so each stands alone — backward-compatible). Runs that share a hash (e.g.
    quick→full, or a rebuild) collapse to the NEWEST run. Versions are numbered v1..vN oldest→newest
    (by `audio_mtime`, else `stamp`); an explicit entry `version` wins. Cross-version deltas
    (lufs/length_s/bpm) compare each version to the chronologically previous one. Returns
    {track: [version, … newest first]}, each version = {label, rep(entry), n_runs, sha, delta}.
    """
    by_track = {}
    for e in entries:
        by_track.setdefault(e.get("track", "?"), []).append(e)
    out = {}
    for track, es in by_track.items():
        by_sha = {}
        for e in es:
            by_sha.setdefault(e.get("audio_sha") or e.get("widget"), []).append(e)
        versions = []
        for sha, grp in by_sha.items():
            rep = max(grp, key=lambda e: (e.get("stamp", ""), e.get("deposited_at", "")))
            versions.append({"sha": sha, "rep": rep, "n_runs": len(grp),
                             "okey": rep.get("audio_mtime") or rep.get("stamp", "")})
        versions.sort(key=lambda x: (x["okey"] == "", x["okey"]))  # oldest first; unknowns last
        for i, ver in enumerate(versions):
            ver["label"] = ver["rep"].get("version") or f"v{i + 1}"
            ver["delta"] = {}
            if i > 0:
                cur, prev = ver["rep"], versions[i - 1]["rep"]
                for k in ("lufs", "length_s", "bpm"):
                    a, b = cur.get(k), prev.get(k)
                    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                        ver["delta"][k] = round(a - b, 2)
        versions.reverse()  # newest version first for display
        out[track] = versions
    return out


# ── index io ───────────────────────────────────────────────────────────────────────────
def load_index(root: Path) -> dict:
    p = root / "index.json"
    if p.exists():
        try:
            d = json.loads(p.read_text())
            d.setdefault("entries", [])
            return d
        except ValueError:
            pass
    return {"entries": []}


def save_index(root: Path, idx: dict):
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2))


def upsert(entries, entry):
    """Replace an entry with the same widget filename, else append. Returns the list."""
    out = [e for e in entries if e.get("widget") != entry["widget"]]
    out.append(entry)
    return out


# ── operations ──────────────────────────────────────────────────────────────────────────
def deposit(root: Path, *, run_dir: Path, widget_path: Path, track: str, version: str,
            stamp: str, verdict=None, mode="full", extra: dict = None) -> dict:
    """Copy a built widget into the library and record it. Best-effort; returns the entry.

    `extra` carries the catalog fields (metrics/arc/tags/audio_sha from `run_metrics`)."""
    root = Path(root)
    wdir = root / "widgets"
    wdir.mkdir(parents=True, exist_ok=True)
    name = canonical_widget_name(track, version, stamp)
    shutil.copy2(widget_path, wdir / name)
    entry = {"track": track, "version": version, "stamp": stamp, "widget": name,
             "verdict": verdict or "", "mode": mode,
             "deposited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "src_run_dir": str(run_dir),
             # the ORIGINAL widget filename in the run dir. The catalog opens THIS (its stems
             # live next to it), not the stem-less library copy — otherwise the player is dead.
             "src_widget": widget_path.name}
    if extra:
        entry.update(extra)
    idx = load_index(root)
    idx["entries"] = upsert(idx["entries"], entry)
    save_index(root, idx)
    return entry


def deposit_from_run(run_dir, widget_path, meta: dict) -> dict:
    """Convenience wrapper used by track_analyzer: pull fields from run_meta + result_core.json."""
    run_dir = Path(run_dir)
    core = {}
    cp = run_dir / "result_core.json"
    if cp.exists():
        try:
            core = json.loads(cp.read_text())
        except ValueError:
            core = {}
    extra = run_metrics(core, meta)
    return deposit(library_root(), run_dir=run_dir, widget_path=Path(widget_path),
                   track=meta.get("track") or run_dir.parent.name,
                   version=meta.get("track_version") or "",
                   stamp=run_dir.name,  # the dated folder = a stable, sortable stamp
                   verdict=meta.get("verdict"), mode=meta.get("mode", "full"), extra=extra)


# ── CLI ─────────────────────────────────────────────────────────────────────────────────
def _cmd_path(args):
    print(library_root())


def _cmd_deposit(args):
    run_dir = Path(args.run_dir).expanduser().resolve()
    meta = {}
    mp = run_dir / "run_meta.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text())
        except ValueError:
            meta = {}
    widget = Path(args.widget).expanduser() if args.widget else None
    if widget is None:
        cands = sorted(run_dir.glob("analysis_widget*.html"))
        if not cands:
            sys.exit(f"no widget html found in {run_dir}")
        widget = cands[-1]
    entry = deposit_from_run(run_dir, widget, meta)
    print(f"deposited: {library_root() / 'widgets' / entry['widget']}", file=sys.stderr)
    print(entry["widget"])


def _cmd_list(args):
    idx = load_index(library_root())
    entries = [e for e in idx["entries"] if not args.track or e.get("track") == args.track]
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return
    by_track = {}
    for e in entries:
        by_track.setdefault(e.get("track", "?"), []).append(e)
    if not by_track:
        print("(library empty)")
        return
    for track in sorted(by_track):
        runs = sorted(by_track[track], key=lambda e: e.get("stamp", ""), reverse=True)
        print(f"{track}  ({len(runs)})")
        for e in runs:
            v = (e.get("verdict") or "").strip().replace("\n", " ")
            v = (v[:70] + "…") if len(v) > 71 else v
            print(f"  · {e.get('stamp','?'):<16} {e.get('mode','?'):<5} {v}")


def _cmd_clean(args):
    root = library_root()
    idx = load_index(root)
    wdir = root / "widgets"
    if args.all and not args.yes:
        sys.exit("refusing --all without --yes")
    if not any([args.all, args.older_than is not None, args.keep_per_track is not None,
                args.missing]):
        sys.exit("clean: pick at least one of --all / --older-than / --keep-per-track / --missing")
    keep, remove = clean_plan(
        idx["entries"], exists=lambda e: (wdir / e["widget"]).exists(),
        older_than_days=args.older_than, keep_per_track=args.keep_per_track,
        track=args.track, missing=args.missing, all_=args.all)
    if not remove:
        print("nothing to clean.")
        return
    for e in remove:
        print(f"{'would remove' if args.dry_run else 'remove'}: {e['track']} · {e.get('stamp','?')} ({e['widget']})")
    if args.dry_run:
        print(f"({len(remove)} entr{'y' if len(remove)==1 else 'ies'} would be removed)")
        return
    if not args.yes:
        sys.exit(f"refusing to delete {len(remove)} without --yes (use --dry-run to preview)")
    for e in remove:
        f = wdir / e["widget"]
        if f.exists():
            f.unlink()
    idx["entries"] = keep
    save_index(root, idx)
    print(f"removed {len(remove)}; {len(keep)} left.")


def _cmd_catalog(args):
    """Delegate to catalog.py (the view layer) so `library.py catalog` just works."""
    import catalog
    print(catalog.build_catalog(open_browser=args.open))


def main():
    p = argparse.ArgumentParser(prog="library", description="track-coach global widget library")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("path", help="print the library root").set_defaults(func=_cmd_path)
    cat = sub.add_parser("catalog", help="regenerate the library index.html page")
    cat.add_argument("--open", action="store_true", help="open in a new browser window")
    cat.set_defaults(func=_cmd_catalog)
    d = sub.add_parser("deposit", help="copy a run's widget into the library")
    d.add_argument("--run-dir", required=True)
    d.add_argument("--widget", default=None, help="widget html (default: newest in run dir)")
    d.set_defaults(func=_cmd_deposit)
    l = sub.add_parser("list", help="list library entries")
    l.add_argument("--track", default=None)
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=_cmd_list)
    c = sub.add_parser("clean", help="prune library entries (and their widget files)")
    c.add_argument("--all", action="store_true")
    c.add_argument("--older-than", type=float, default=None, metavar="DAYS")
    c.add_argument("--keep-per-track", type=int, default=None, metavar="N")
    c.add_argument("--track", default=None)
    c.add_argument("--missing", action="store_true", help="drop entries whose widget file is gone")
    c.add_argument("--yes", action="store_true", help="actually delete (required for destructive)")
    c.add_argument("--dry-run", action="store_true", help="preview only")
    c.set_defaults(func=_cmd_clean)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
