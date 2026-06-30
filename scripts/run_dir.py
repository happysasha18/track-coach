#!/usr/bin/env python3
"""Versioned output folders for Track Coach — never overwrite a previous run.

The bug this fixes: every analysis used to land in the SAME folder (named only by
the track's version), so re-analysing the same track version clobbered the last run,
and the widget never showed WHICH file was analysed or WHEN.

Layout this enforces:

    <base>/                                  (default: ~/.track-coach/projects)
      <track-slug>/
        <version>__<YYYY-MM-DD_HHMM>/        one run — never reused
          result_*.json, stems*/, analysis_widget.html, run_meta.json
        latest -> <newest run>              (symlink, best-effort)
      index.json                            append-only history of every run

stdlib only — runs with plain `python3`, no uv / no deps, so it's instant and free.

Usage
-----
  # start a new run, print its absolute path on the LAST stdout line:
  python3 run_dir.py init --audio AUDIO [--als ALS] [--track-version v0.6.2]
                          [--mode quick|full] [--base DIR]

  # find the newest existing run for this audio and report what's already computed
  # (so a quick→full upgrade reuses cached JSON instead of recomputing everything):
  python3 run_dir.py resume --audio AUDIO [--base DIR]
"""
import argparse, json, os, re, sys
from datetime import datetime
from pathlib import Path

# result_*.json files keyed by the analysis stage that produced them — used by
# `resume` to tell the agent what can be reused vs what still needs computing.
STAGE_FILES = {
    "core": "result_core.json",
    "detail": "result_detail.json",
    "als": "result_als.json",
    "masking": "result_masking.json",
    "stemmap": "result_stemmap.json",
    "rhythm": "result_rhythm.json",
    "drums": "result_drums.json",
    "notes": "result_notes_other.json",
    "selfsim": "result_selfsim.json",
}


def slugify(name: str) -> str:
    """Track folder name from the audio filename: drop extension + [vX] tag, sanitise."""
    stem = Path(name).stem
    stem = re.sub(r"[\[\(]\s*v?[\d.]+\s*[\]\)]", "", stem, flags=re.I)  # strip [v0.6.2]
    stem = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_")
    return stem or "track"


def existing_runs(runs_list: list) -> list:
    """Filter an index runs-list to entries whose run dir exists on disk (G-INV-11 / RC-INV-9).

    Accepts either run_dir.py index entries (key ``run_dir``) or library index entries
    (key ``src_run_dir``).  Non-dict items (legacy string slugs) are silently skipped.
    Never trusts index membership alone — a crash, prune, or hand-delete can leave stale entries.
    """
    out = []
    for e in runs_list:
        if not isinstance(e, dict):
            continue
        rd = e.get("run_dir") or e.get("src_run_dir", "")
        if rd and Path(rd).exists():
            out.append(e)
    return out


def detect_version(name: str) -> str:
    m = re.search(r"v?(\d+\.\d+(?:\.\d+)?)", Path(name).stem)
    return ("v" + m.group(1)) if m else ""


def base_dir(args, audio: Path) -> Path:
    # G-INV-1: default is ~/.track-coach/projects/ — NOT next to the audio file.
    return Path(args.base).expanduser().resolve() if args.base \
        else (Path.home() / ".track-coach" / "projects")


def track_root(args, audio: Path) -> Path:
    return base_dir(args, audio) / slugify(audio.name)


def computed_stages(run_dir: Path):
    return [k for k, f in STAGE_FILES.items() if (run_dir / f).exists()]


def newest_run(root: Path):
    if not root.exists():
        return None
    runs = [p for p in root.iterdir() if p.is_dir() and p.name != "latest"]
    if not runs:
        return None
    return max(runs, key=lambda p: p.stat().st_mtime)


def update_symlink(root: Path, target: Path):
    link = root / "latest"
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target.name)  # relative — survives the folder being moved
    except OSError:
        pass  # symlinks can fail on some filesystems; the folder itself is the source of truth


def update_index(base: Path, slug: str, run_dir: Path, meta: dict, *, audio: Path = None):
    """Append this run to base/index.json — honest history, never overwritten.

    ``audio`` is used to locate a pre-1.0 index at
    ``<audio.parent>/track-coach-output/index.json`` and seed it into the new shared index
    on the first post-move run for this slug (G-INV-12).
    """
    idx_path = base / "index.json"
    idx = {"runs": []}
    if idx_path.exists():
        try:
            idx = json.loads(idx_path.read_text())
        except (ValueError, OSError):
            idx = {"runs": []}
    idx.setdefault("runs", [])

    # G-INV-12: seed from old per-folder index on the very first post-move run for this slug.
    if audio is not None:
        existing_slugs = {r.get("track") for r in idx["runs"] if isinstance(r, dict)}
        if slug not in existing_slugs:
            old_idx_path = audio.parent / "track-coach-output" / "index.json"
            if old_idx_path.exists():
                try:
                    old_data = json.loads(old_idx_path.read_text())
                    for r in old_data.get("runs", []):
                        if isinstance(r, dict) and r.get("track") == slug:
                            idx["runs"].append(r)
                except (ValueError, OSError):
                    pass  # can't read old index — disclose the split rather than crashing

    entry = {
        "track": slug,
        "version": meta.get("track_version", ""),
        "run_dir": str(run_dir),
        "analyzed_at": meta.get("analyzed_at"),
        "mode": meta.get("mode"),
        "audio": meta.get("audio"),
        "als": meta.get("als"),
        "source_identity": meta.get("source_identity", ""),
    }
    idx["runs"].append(entry)
    idx["latest"] = entry
    base.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2))


def _stored_identity(root: Path) -> "str | None":
    """Read source_identity from the most recent run in a slug dir.

    Falls back to ``als_path``/``audio_path`` from run_meta.json so old runs (without an
    explicit ``source_identity`` field) are still matched by their stored paths (G-INV-2b).
    Returns None when no run_meta.json is readable.
    """
    newest = newest_run(root)
    if newest is None:
        return None
    try:
        meta = json.loads((newest / "run_meta.json").read_text())
        return (meta.get("source_identity") or
                meta.get("als_path") or
                meta.get("audio_path"))
    except (ValueError, OSError):
        return None


def _resolve_slug(base: Path, audio: Path, als_path: "Path | None") -> tuple:
    """Return (slug, warn_msg_or_None) for this run, disambiguating same-name collisions.

    G-INV-2b: two different tracks that slug the same get ``<slug>-2`` (then -3, …) and a
    warning; same source (same audio/als path) reuses the existing slug.  Source identity is
    the als full path when provided, else the audio full path.
    """
    identity = str(als_path) if als_path else str(audio)
    base_slug = slugify(audio.name)
    candidate = base_slug
    n = 2
    while True:
        root = base / candidate
        if not root.exists():
            return candidate, None          # fresh slot — no collision
        stored = _stored_identity(root)
        if stored is None or stored == identity:
            return candidate, None          # same source or unreadable → reuse
        # Different stored identity → try the next numbered slot
        warn = (f"  ⚠  slug '{candidate}' is used by a different track "
                f"(stored: {stored!r}); using '{base_slug}-{n}'")
        candidate = f"{base_slug}-{n}"
        n += 1


def cmd_init(args):
    audio = Path(args.audio).expanduser().resolve()
    if not audio.exists():
        sys.exit(f"audio not found: {audio}")
    base = base_dir(args, audio)
    als = Path(args.als).expanduser().resolve() if args.als else None

    # G-INV-2/2b: resolve slug with collision-disambiguation
    slug, warn = _resolve_slug(base, audio, als)
    if warn:
        print(warn, file=sys.stderr)

    root = base / slug
    version = args.track_version or detect_version(audio.name)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    folder = (version + "__" + stamp) if version else stamp
    run_dir = root / folder
    # collision-proof even on the same minute
    n = 2
    while run_dir.exists():
        run_dir = root / (folder + f"-{n}")
        n += 1
    run_dir.mkdir(parents=True)

    # G-INV-2b: source_identity = als path if provided, else audio full path
    source_identity = str(als) if als else str(audio)
    meta = {
        "track": slug,
        "track_version": version,
        "audio": audio.name,
        "audio_path": str(audio),
        "als": als.name if als else None,
        "als_path": str(als) if als else None,
        "mode": args.mode,
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "run_dir": str(run_dir),
        "source_identity": source_identity,  # G-INV-2b: stable identity for collision check
    }
    (run_dir / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    update_symlink(root, run_dir)
    # Pass audio so update_index can seed from the old per-folder index (G-INV-12)
    update_index(base, slug, run_dir, meta, audio=audio)

    # human note on stderr, machine-readable path on the LAST stdout line
    print(f"New run folder (won't overwrite earlier runs):\n  {run_dir}", file=sys.stderr)
    print(run_dir)


def cmd_catalog(args):
    """Build catalog.json for the current run: every track + every version analysed,
    with each run's verdict and a RELATIVE link to that run's widget (so cross-links
    work when the whole track-coach-output/ tree is published to GitHub Pages).
    Verdicts come from index.json (build_widget writes them back after each build)."""
    self_dir = Path(args.self).expanduser().resolve()
    base = Path(args.base).expanduser().resolve() if args.base else self_dir.parent.parent
    idx_path = base / "index.json"
    runs = []
    if idx_path.exists():
        try:
            runs = json.loads(idx_path.read_text()).get("runs", [])
        except (ValueError, OSError):
            runs = []
    bytrack = {}
    self_track = None
    for e in runs:
        if not isinstance(e, dict):
            continue   # tolerate a legacy/malformed entry (e.g. a stray slug string from an old run)
        rd = Path(e.get("run_dir", "")).resolve()
        widget = e.get("widget", "analysis_widget.html")
        try:
            rel = os.path.relpath(rd / widget, start=self_dir)
        except ValueError:
            rel = str(rd / widget)
        is_self = (rd == self_dir)
        if is_self:
            self_track = e.get("track", "?")
        bytrack.setdefault(e.get("track", "?"), []).append({
            "version": e.get("version", ""), "date": e.get("analyzed_at"),
            "verdict": e.get("verdict", ""), "mode": e.get("mode", ""),
            "rel": rel, "self": is_self, "exists": (rd / widget).exists(),
        })
    tracks = []
    for t, rs in bytrack.items():
        rs.sort(key=lambda r: (r["date"] or ""), reverse=True)
        tracks.append({"track": t, "self": t == self_track, "runs": rs})
    tracks.sort(key=lambda x: (not x["self"], x["track"].lower()))
    cat = {"self_track": self_track, "tracks": tracks,
           "n_tracks": len(tracks), "n_runs": sum(len(t["runs"]) for t in tracks)}
    out = self_dir / "catalog.json"
    out.write_text(json.dumps(cat, ensure_ascii=False, indent=2))
    print(f"Catalog: {cat['n_runs']} run(s) across {cat['n_tracks']} track(s)", file=sys.stderr)
    print(str(out))


def cmd_resume(args):
    audio = Path(args.audio).expanduser().resolve()
    root = track_root(args, audio)
    run = newest_run(root)
    if not run:
        print(f"No earlier run found for this track under {root}", file=sys.stderr)
        print("")  # empty path → caller starts fresh with `init`
        return
    stages = computed_stages(run)
    missing = [k for k in STAGE_FILES if k not in stages]
    print(f"Latest run: {run}\n  already computed: {', '.join(stages) or 'none'}"
          f"\n  not yet present: {', '.join(missing) or 'none'}", file=sys.stderr)
    print(json.dumps({"run_dir": str(run), "computed": stages, "missing": missing}))


def main():
    p = argparse.ArgumentParser(description="Versioned Track Coach output folders.")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init", help="create a new timestamped run folder")
    pi.add_argument("--audio", required=True)
    pi.add_argument("--als", default=None)
    pi.add_argument("--track-version", default=None)
    pi.add_argument("--mode", default="full", choices=["quick", "full"])
    pi.add_argument("--base", default=None, help="output base dir (default: ~/.track-coach/projects)")
    pi.set_defaults(func=cmd_init)
    pr = sub.add_parser("resume", help="find the newest run for this track + what it already has")
    pr.add_argument("--audio", required=True)
    pr.add_argument("--base", default=None)
    pr.set_defaults(func=cmd_resume)
    pc = sub.add_parser("catalog", help="write catalog.json (all tracks/versions + verdicts + links) into the run")
    pc.add_argument("--self", required=True, help="the current run folder")
    pc.add_argument("--base", default=None)
    pc.set_defaults(func=cmd_catalog)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
