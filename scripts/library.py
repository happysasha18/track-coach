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
from __future__ import annotations
import argparse, json, os, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path


# ── pure helpers (tested) ──────────────────────────────────────────────────────────────
def library_root() -> Path:
    env = os.environ.get("TRACK_COACH_LIBRARY")
    return Path(env).expanduser() if env else Path.home() / ".track-coach" / "library"


def output_root() -> Path:
    """The configured output root (`~/.track-coach/`). Parent of library/ and projects/.

    Override with TRACK_COACH_ROOT env var (used in tests to avoid touching the real root).
    G-INV-7: reset/gc must never touch anything outside this root.
    """
    env = os.environ.get("TRACK_COACH_ROOT")
    if env:
        return Path(env).expanduser()
    # Default: derive from library_root's parent (~/.track-coach)
    return library_root().parent


def sanitize(s: str) -> str:
    """Filesystem-safe token: keep word chars, dash, dot; collapse the rest to '-'."""
    s = (s or "").strip()
    s = re.sub(r"[^\w.\-]+", "-", s, flags=re.UNICODE).strip("-")
    return s or "untitled"


def canonical_widget_name(track: str, version: str, stamp: str) -> str:
    """`<track>__<version>__<stamp>.html` — stable, collision-resistant, sortable."""
    return f"{sanitize(track)}__{sanitize(version or 'v0')}__{sanitize(stamp or 'na')}.html"


class DepositError(ValueError):
    """A deposit was refused because the run dir is malformed (INV-15). Subclasses ValueError so
    existing callers that catch ValueError still handle it; raised BEFORE any write so a bad run
    dir never leaves a partial widget copy or a junk index entry behind."""


class BackupError(RuntimeError):
    """A backup failed or was partial. Raised by _do_backup() so callers can abort safely.
    H-INV-8: a failed backup leaves no partial snapshot."""


_STAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}_\d{4}")  # the dated run-folder shape, e.g. 2026-06-18_0748


def looks_like_output_sentinel(slug: str) -> bool:
    """True when `slug` is NOT a real track name but an output root or a stamp grabbed as a track —
    the KI-1 junk-entry shape. PURE. A well-shaped run dir is `<base>/<track>/<stamp>`; depositing one
    level too shallow makes the track resolve to `track-coach-output` / `*-output` / a dated stamp."""
    s = (slug or "").strip()
    if not s or s.lower() in {"track-coach-output", "output"} or s.lower().endswith("-output"):
        return True
    return bool(_STAMP_RE.fullmatch(s))


def version_from_widget(widget_path) -> str | None:
    """The TC_VERSION the widget was built on, read from its embedded payload (`"version":"X.Y.Z"`).
    Filename-INDEPENDENT (INV-12 option-b / KI-7) so a stale link is caught even when the widget file
    has no version in its name. None when the file is unreadable or carries no version. Touches the FS."""
    try:
        text = Path(widget_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r'"version"\s*:\s*"(\d+\.\d+\.\d+)"', text)
    return m.group(1) if m else None


def analysis_version_from_widget(widget_path) -> int | None:
    """The TC_ANALYSIS_VERSION the widget was built on, read from its embedded payload
    (`"analysis_version": N`). This is what the stale check (INV-12) compares. None when the file is
    unreadable or carries no analysis version — a widget deposited before analysis-version stamping.
    Touches the FS."""
    try:
        text = Path(widget_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r'"analysis_version"\s*:\s*(\d+)', text)
    return int(m.group(1)) if m else None


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


def newest_reps(entries) -> dict:
    """Dict slug -> the rep entry of the track's NEWEST version (D-INV-35). The catalog shows one
    row per track (its newest version), so every cell — including the lean/sibling fingerprint — is
    read from this entry, never blended across older versions. PURE (builds on group_versions)."""
    return {track: vers[0]["rep"] for track, vers in group_versions(entries).items()}


# ── index io ───────────────────────────────────────────────────────────────────────────
def load_index(root: Path) -> dict:
    p = root / "index.json"
    if p.exists():
        try:
            d = json.loads(p.read_text())
            # Normalize: entries must be dicts. A stray string (legacy slug from an older
            # run-init that appended a plain slug instead of a metadata dict) is coerced to a
            # minimal dict so every downstream caller sees a uniform type. Using {"widget": s}
            # preserves the original string rather than silently discarding it.
            raw = d.get("entries", [])
            d["entries"] = [e if isinstance(e, dict) else {"widget": str(e)} for e in raw]
            return d
        except ValueError:
            pass
    return {"entries": []}


def save_index(root: Path, idx: dict):
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2))


ALIASES_FILE = "aliases.json"


def load_aliases(root: Path) -> dict:
    """Read the same-song alias map ``{alias_slug: canonical_slug}`` from ``<root>/aliases.json``.

    A user records that two tracks are the SAME song under different filenames (so the catalog shows
    them as one). Returns {} when the file is absent or unreadable — aliasing is purely additive."""
    p = Path(root) / ALIASES_FILE
    try:
        data = json.loads(p.read_text())
        m = data.get("aliases", data) if isinstance(data, dict) else {}
        return {str(k): str(v) for k, v in m.items() if k and v and str(k) != str(v)}
    except (OSError, ValueError):
        return {}


def save_aliases(root: Path, aliases: dict):
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / ALIASES_FILE).write_text(
        json.dumps({"aliases": {str(k): str(v) for k, v in aliases.items()}},
                   ensure_ascii=False, indent=2))


def resolve_alias(slug: str, aliases: dict) -> str:
    """Follow ``slug`` through the alias map to its canonical name. Cycle- and depth-safe: a loop or
    a chain longer than the map returns the last slug reached rather than spinning."""
    seen = set()
    cur = slug
    for _ in range(len(aliases) + 1):
        nxt = aliases.get(cur)
        if not nxt or nxt == cur or nxt in seen:
            break
        seen.add(cur)
        cur = nxt
    return cur


def canonicalize_entries(entries: list, aliases: dict) -> list:
    """Return a shallow-copied entry list with each ``track`` rewritten to its canonical slug
    (RC/same-song merge). PURE — never mutates the input entries. With an empty map it is a copy.

    Grouping (``group_versions``/``newest_reps``) keys off ``track``, so canonicalising BEFORE
    grouping collapses two filename identities into one catalog row; their distinct bounces remain
    separate versions under that one row."""
    if not aliases:
        return list(entries)
    out = []
    for e in entries:
        if isinstance(e, dict) and e.get("track"):
            can = resolve_alias(e["track"], aliases)
            if can != e["track"]:
                e = {**e, "track": can}
        out.append(e)
    return out


def forget_run(root: Path, src_run_dir) -> int:
    """Drop every library entry deposited from ``src_run_dir`` (delete its widget file too) and
    rewrite the index. Returns the count removed.

    Used when a run is superseded: an invalid run that has just been re-measured and re-deposited
    as a fresh complete run must cease to exist (RC-INV-13) — otherwise the old, incomplete deposit
    lingers in the catalog and the validity gate keeps flagging it. Matches by resolved path so a
    slug that drifted between analysis versions (the folder name changed) is still forgotten."""
    src = str(Path(src_run_dir).resolve())
    idx = load_index(root)
    wdir = root / "widgets"
    keep, removed = [], 0
    for e in idx.get("entries", []):
        sd = e.get("src_run_dir", "")
        if sd and str(Path(sd).resolve()) == src:
            f = wdir / e.get("widget", "")
            if e.get("widget") and f.exists():
                f.unlink()
            removed += 1
        else:
            keep.append(e)
    if removed:
        idx["entries"] = keep
        save_index(root, idx)
    return removed


def upsert(entries, entry):
    """Replace an entry with the same widget filename, else append. Returns the list.

    Non-dict items (legacy string slugs from earlier builds that pre-date the full-metadata
    format) are dropped: a bare str has no `widget` key and cannot represent a real entry."""
    out = [e for e in entries if isinstance(e, dict) and e.get("widget") != entry["widget"]]
    out.append(entry)
    return out


# ── operations ──────────────────────────────────────────────────────────────────────────
def deposit(root: Path, *, run_dir: Path, widget_path: Path, track: str, version: str,
            stamp: str, verdict=None, mode="full", extra: dict = None, tc_version: str = None,
            tc_analysis_version: int = None) -> dict:
    """Copy a built widget into the library and record it. Best-effort; returns the entry.

    `extra` carries the catalog fields (metrics/arc/tags/audio_sha from `run_metrics`)."""
    if looks_like_output_sentinel(track):  # INV-15: refuse junk BEFORE any write (atomic)
        raise DepositError(
            f"refusing to deposit: resolved track '{track}' is not a real track (looks like an "
            f"output root or a dated stamp). Expected a run dir shaped <base>/<track>/<stamp>; "
            f"pass a real run dir or set meta.track.")
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
    if tc_version:  # the build's TC_VERSION, kept as the recognizable build stamp on the row (INV-12)
        entry["tc_version"] = tc_version
    if tc_analysis_version is not None:  # the build's analysis version — what the stale check compares (INV-12)
        entry["tc_analysis_version"] = int(tc_analysis_version)
    if extra:
        entry.update(extra)
    idx = load_index(root)
    idx["entries"] = upsert(idx["entries"], entry)
    save_index(root, idx)
    return entry


def deposit_from_run(run_dir, widget_path, meta: dict) -> dict:
    """Convenience wrapper used by track_analyzer: pull fields from run_meta + result_core.json."""
    if meta.get("reference"):
        raise DepositError(
            "refusing to deposit: run is a reference (G-INV-18) — "
            "references never enter the library")
    if meta.get("synthetic"):
        raise DepositError(
            "refusing to deposit: run is synthetic/smoke (G-INV-21) — "
            "fixture runs never enter the library")
    run_dir = Path(run_dir)
    import validity as _validity  # lazy: avoids a load-order cycle (validity → build_widget → …)
    _ok, _unmeasured = _validity.validity(run_dir, meta.get("mode", "full"))
    if not _ok:
        raise DepositError(
            "refusing to deposit: run is incomplete (RC-INV-13) — unmeasured signals: "
            f"{', '.join(_unmeasured)}; complete the run (revalidate --apply) before it enters the library")
    core = {}
    cp = run_dir / "result_core.json"
    if cp.exists():
        try:
            core = json.loads(cp.read_text())
        except ValueError:
            core = {}
    extra = run_metrics(core, meta)
    tcv = meta.get("tc_version") or version_from_widget(widget_path)  # filename-independent (KI-7)
    av = meta.get("tc_analysis_version")
    if av is None:
        av = analysis_version_from_widget(widget_path)  # read it from the built payload
    return deposit(library_root(), run_dir=run_dir, widget_path=Path(widget_path),
                   track=meta.get("track") or run_dir.parent.name,
                   version=meta.get("track_version") or "",
                   stamp=run_dir.name,  # the dated folder = a stable, sortable stamp
                   verdict=meta.get("verdict"), mode=meta.get("mode", "full"), extra=extra,
                   tc_version=tcv, tc_analysis_version=av)


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
    if not any([args.all, args.older_than is not None, args.keep_per_track is not None,
                args.missing]):
        sys.exit("clean: pick at least one of --all / --older-than / --keep-per-track / --missing")
    act = args.apply or args.yes  # --apply is canonical; --yes is a silent back-compat alias
    keep, remove = clean_plan(
        idx["entries"], exists=lambda e: (wdir / e["widget"]).exists(),
        older_than_days=args.older_than, keep_per_track=args.keep_per_track,
        track=args.track, missing=args.missing, all_=args.all)
    if not remove:
        print("nothing to clean.")
        return
    for e in remove:
        print(f"{'would remove' if not act else 'remove'}: {e['track']} · {e.get('stamp','?')} ({e['widget']})")
    if not act:
        print(f"({len(remove)} entr{'y' if len(remove)==1 else 'ies'} would be removed — pass --apply to act)")
        return
    for e in remove:
        f = wdir / e["widget"]
        if f.exists():
            f.unlink()
    idx["entries"] = keep
    save_index(root, idx)
    print(f"removed {len(remove)}; {len(keep)} left.")


def migrate_plan(root: Path, output_root: Path) -> list:
    """Return a plan list for members whose src_run_dir lives outside ``output_root``.

    Each plan item is a dict: {entry, src (Path), dst (Path), slug (str)}.
    Dry-run safe — reads the index but changes nothing.  G-INV-16.
    """
    root = Path(root)
    output_root = Path(output_root)
    idx = load_index(root)
    plan = []
    for e in idx.get("entries", []):
        if not isinstance(e, dict):
            continue
        sd = e.get("src_run_dir", "")
        if not sd:
            continue
        src = Path(sd)
        try:
            src.relative_to(output_root)
            continue  # already inside the output root — nothing to do
        except ValueError:
            pass
        slug = e.get("track", "")
        if not slug:
            continue
        # Destination: <output_root>/projects/<slug>/<run_folder_name>
        dst = output_root / "projects" / slug / src.name
        plan.append({"entry": e, "src": src, "dst": dst, "slug": slug})
    return plan


def migrate_apply(root: Path, output_root: Path) -> list:
    """Move run dirs outside the output root into ``<output_root>/projects/<slug>/`` and rewrite
    the library index.  The index is only rewritten AFTER all moves succeed (G-INV-16
    all-or-clean-report).

    Returns the list of moved plan items (same shape as ``migrate_plan``).
    Raises ``RuntimeError`` on the first move failure; already-moved dirs are left in place but
    the index is NOT updated for the failed member.
    """
    plan = migrate_plan(root, output_root)
    if not plan:
        return []

    moved = []
    for item in plan:
        src, dst = item["src"], item["dst"]
        if not src.exists():
            raise RuntimeError(
                f"migrate: source run dir not found on disk (already moved?): {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved.append(item)

    # All moves succeeded — rewrite the index atomically (single write).
    root = Path(root)
    idx = load_index(root)
    new_sdr = {str(item["src"]): str(item["dst"]) for item in moved}
    for e in idx.get("entries", []):
        if isinstance(e, dict):
            sd = e.get("src_run_dir", "")
            if sd in new_sdr:
                e["src_run_dir"] = new_sdr[sd]
    save_index(root, idx)
    return moved


# ── size utilities ────────────────────────────────────────────────────────────────────────

def _dir_size(p: Path) -> int:
    """Sum of all non-symlink file sizes under p, recursively. Touches the FS."""
    total = 0
    try:
        for f in p.rglob("*"):
            if f.is_file() and not f.is_symlink():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"  # pragma: no cover


# ── gc: prune scratch, keep referenced + best-undeposited (H-INV-3) ─────────────────────

def _count_result_files(run_dir: Path) -> int:
    """Count result_*.json files in a run dir (completeness proxy for RC-INV-9)."""
    return len(list(run_dir.glob("result_*.json")))


def _best_undeposited_run(slug_dir: Path, referenced: set) -> "Path | None":
    """Return the most-complete run dir under slug_dir that is NOT referenced in the library.

    'Most complete' = most result_*.json files; tiebreak = newest name (lexicographic).
    Returns None if slug_dir has no undeposited runs.
    G-INV-15 / RC-INV-9.
    """
    best, best_key = None, (-1, "")
    for item in slug_dir.iterdir():
        if item.name == "latest" or item.is_symlink():
            continue
        if not item.is_dir():
            continue
        if str(item) in referenced or str(item.resolve()) in referenced:
            continue
        n = _count_result_files(item)
        k = (n, item.name)
        if k > best_key:
            best_key = k
            best = item
    return best


def gc_plan(projects_dir: Path, lib_root: Path) -> dict:
    """Classify run dirs under projects_dir as orphan vs keep.

    Returns {
        'orphan': [Path, …],          # can be pruned (not referenced, not best undeposited)
        'keep_referenced': [Path, …], # referenced by a library member (G-INV-10)
        'keep_best': [Path, …],       # best undeposited per slug (G-INV-15)
    }

    Only scans run dirs under projects_dir; library members that live OUTSIDE projects_dir
    (pre-migration) are noted in referenced but not touched. G-INV-7.
    """
    projects_dir = Path(projects_dir)
    idx = load_index(lib_root)
    # Collect referenced run dirs from library index (raw string + resolved)
    referenced: set = set()
    for e in idx.get("entries", []):
        if isinstance(e, dict) and e.get("src_run_dir"):
            sd = e["src_run_dir"]
            referenced.add(sd)
            try:
                referenced.add(str(Path(sd).resolve()))
            except OSError:
                pass

    result: dict = {"orphan": [], "keep_referenced": [], "keep_best": []}
    if not projects_dir.exists():
        return result

    for slug_dir in sorted(projects_dir.iterdir()):
        if not slug_dir.is_dir() or slug_dir.is_symlink():
            continue
        best = _best_undeposited_run(slug_dir, referenced)
        for run_dir in sorted(slug_dir.iterdir()):
            if run_dir.name == "latest" or run_dir.is_symlink():
                continue
            if not run_dir.is_dir():
                continue
            rd_str = str(run_dir)
            rd_res = str(run_dir.resolve())
            is_ref = rd_str in referenced or rd_res in referenced
            is_best = (best is not None and
                       (run_dir == best or run_dir.resolve() == best.resolve()))
            if is_ref:
                result["keep_referenced"].append(run_dir)
            elif is_best:
                result["keep_best"].append(run_dir)
            else:
                # G-INV-19: a run dir carrying run_meta.json{reference:true} is NEVER an orphan
                try:
                    rmp = run_dir / "run_meta.json"
                    is_reference_run = rmp.exists() and json.loads(rmp.read_text()).get("reference")
                except (OSError, ValueError):
                    is_reference_run = False
                if is_reference_run:
                    result["keep_referenced"].append(run_dir)
                else:
                    result["orphan"].append(run_dir)
    return result


# ── Ableton-tail sweep (H-INV-5) ─────────────────────────────────────────────────────────

def _slug_dir_has_real_runs(slug_dir: Path) -> bool:
    """True if slug_dir contains at least one real (non-symlink) run subdirectory.

    'Safe' slug dirs contain only dangling symlinks and index.json — no real run dirs.
    H-INV-5.
    """
    for item in slug_dir.iterdir():
        if item.name == "index.json":
            continue
        if item.is_symlink():
            continue  # dangling or live symlink — not a real run dir itself
        if item.is_dir():
            return True
    return False


def ableton_tail_scan(tco_dirs: list) -> dict:
    """Classify slug dirs within track-coach-output/ directories.

    Returns {
        'safe': [(tco_dir, slug_dir), …],      # empty/dangling-only — safe to remove
        'real_runs': [(tco_dir, slug_dir), …], # has real run content — NEVER auto-delete
        'missing': [tco_dir, …],               # tco_dir does not exist on disk
    }
    H-INV-5: distinguishes safe tails from slug dirs with real runs.
    """
    result: dict = {"safe": [], "real_runs": [], "missing": []}
    for tco_dir in tco_dirs:
        tco_dir = Path(tco_dir)
        if not tco_dir.exists():
            result["missing"].append(tco_dir)
            continue
        for slug_dir in sorted(tco_dir.iterdir()):
            if not slug_dir.is_dir() or slug_dir.is_symlink():
                continue
            if _slug_dir_has_real_runs(slug_dir):
                result["real_runs"].append((tco_dir, slug_dir))
            else:
                result["safe"].append((tco_dir, slug_dir))
    return result


def _tco_dirs_from_library(lib_root: Path, oroot: Path) -> list:
    """Discover track-coach-output/ dirs from pre-migration library members.

    A pre-migration src_run_dir lives OUTSIDE oroot.
    The tco_dir = src_run_dir.parent.parent (slug dir's parent = tco dir).
    H-INV-5.
    """
    idx = load_index(lib_root)
    seen: set = set()
    result: list = []
    for e in idx.get("entries", []):
        if not isinstance(e, dict):
            continue
        sd = e.get("src_run_dir", "")
        if not sd:
            continue
        src = Path(sd)
        try:
            src.relative_to(oroot)
            continue  # inside output root — skip
        except ValueError:
            pass
        tco = src.parent.parent
        key = str(tco)
        if key not in seen:
            seen.add(key)
            result.append(tco)
    return result


# ── remove: drop a track or one version from the library (H-INV-2) ─────────────────────

def remove_plan(entries: list, track: str, version: "str | None" = None) -> tuple:
    """Decide which library entries to remove for a track (and optional version). PURE.

    - version=None → remove ALL entries for that track
    - version=<str> → remove only entries whose stamp or version field matches

    Returns (keep, to_remove). Run dirs are NOT deleted (gc reclaims them). H-INV-2.
    """
    keep: list = []
    to_remove: list = []
    for e in entries:
        if not isinstance(e, dict):
            keep.append(e)
            continue
        if e.get("track") != track:
            keep.append(e)
            continue
        if version is None:
            to_remove.append(e)
        elif e.get("stamp") == version or e.get("version") == version:
            to_remove.append(e)
        else:
            keep.append(e)
    return keep, to_remove


# ── prune-versions: explicit old-version pruning (H-INV-4) ───────────────────────────────

def prune_versions_plan(entries: list, keep_n: int) -> tuple:
    """Keep only the newest N audio versions per track; return (keep, to_drop). PURE.

    A 'version' is a distinct audio_sha group (same logic as group_versions).
    All entries in a dropped version group are dropped together.
    keep_n=0 → drops all versions for every track.
    Caller must always supply keep_n (no silent default). H-INV-4.

    Returns (keep, to_drop).
    """
    if keep_n < 0:
        raise ValueError(f"keep_n must be >= 0, got {keep_n}")
    by_track: dict = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        by_track.setdefault(e.get("track", "?"), []).append(e)

    to_drop_ids: set = set()
    for track_name, es in by_track.items():
        # Group by audio_sha (mirrors group_versions)
        by_sha: dict = {}
        for e in es:
            key = e.get("audio_sha") or e.get("widget", "")
            by_sha.setdefault(key, []).append(e)
        # Sort versions oldest→newest
        versions: list = []
        for sha, grp in by_sha.items():
            rep = max(grp, key=lambda e: (e.get("stamp", ""), e.get("deposited_at", "")))
            okey = rep.get("audio_mtime") or rep.get("stamp", "")
            versions.append({"sha": sha, "entries": grp, "okey": okey})
        versions.sort(key=lambda v: (v["okey"] == "", v["okey"]))  # oldest first; unknowns last
        # Keep the newest keep_n versions; drop the rest
        keep_shas = {v["sha"] for v in versions[-keep_n:]} if keep_n > 0 else set()
        for v in versions:
            if v["sha"] not in keep_shas:
                for e in v["entries"]:
                    to_drop_ids.add(id(e))

    keep = [e for e in entries if id(e) not in to_drop_ids]
    to_drop = [e for e in entries if id(e) in to_drop_ids]
    return keep, to_drop


# ── shared catalog regen helper ───────────────────────────────────────────────────────────

def _regen_catalog():
    """Try to regenerate the catalog HTML after a library change. Best-effort."""
    try:
        import catalog  # noqa: PLC0415
        out = catalog.build_catalog()
        print(f"  catalog regenerated: {out}", file=sys.stderr)
    except Exception as exc:
        print(f"  (catalog regen skipped: {exc})", file=sys.stderr)


# ── backup / restore helpers (H-INV-8) ────────────────────────────────────────────────────

# Tiers wiped by reset (keep + scratch + references), and known loose root files.
_RESET_TIERS = ("library", "projects", "explore")
_RESET_LOOSE_FILES = ("resume_autopilot.sh", "config.json")


def _backup_stamp(base: Path) -> str:
    """Return a unique snapshot stamp for the given output root (unique to the second).
    On collision, appends -2, -3, … H-INV-8.
    """
    backups_dir = base / "backups"
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if not (backups_dir / stamp).exists():
        return stamp
    for n in range(2, 10000):
        candidate = f"{stamp}-{n}"
        if not (backups_dir / candidate).exists():
            return candidate
    raise RuntimeError("backup: could not generate unique stamp after 10000 tries")  # pragma: no cover


def _has_valid_backup(base: Path) -> bool:
    """True if at least one complete backup snapshot exists under base/backups/. H-INV-6."""
    backups_dir = base / "backups"
    if not backups_dir.exists():
        return False
    try:
        for snap in backups_dir.iterdir():
            if snap.is_dir() and (snap / ".backup_ok").exists():
                return True
    except OSError:
        pass
    return False


def _do_backup(base: Path, full: bool = False) -> Path:
    """Copy curated tiers (library/ + explore/ [+ config]) into a fresh backups/<stamp>/ snapshot.

    Atomic: copies into a _tmp_<stamp>/ dir, then renames into place; any failure cleans up the
    temp dir and raises BackupError (no partial snapshot ever remains). H-INV-8.

    Returns the Path of the created snapshot on success.
    """
    sources = []
    for tier in ("library", "explore"):
        d = base / tier
        if d.exists():
            sources.append(d)
    config_f = base / "config.json"
    if config_f.exists():
        sources.append(config_f)
    if full:
        d = base / "projects"
        if d.exists():
            sources.append(d)

    stamp = _backup_stamp(base)
    backups_dir = base / "backups"
    dest = backups_dir / stamp
    tmp_dest = backups_dir / f"_tmp_{stamp}"

    backups_dir.mkdir(parents=True, exist_ok=True)
    try:
        tmp_dest.mkdir(parents=True, exist_ok=True)
        for src in sources:
            if src.is_dir():
                shutil.copytree(src, tmp_dest / src.name)
            else:
                shutil.copy2(src, tmp_dest / src.name)
        (tmp_dest / ".backup_ok").write_text("ok")
        tmp_dest.rename(dest)
    except Exception as exc:
        if tmp_dest.exists():
            shutil.rmtree(tmp_dest, ignore_errors=True)
        raise BackupError(f"backup failed: {exc}") from exc

    return dest


# ── backup command (H-INV-8) ──────────────────────────────────────────────────────────────

def _cmd_backup(args):
    """Snapshot curated tiers into backups/<stamp>/. Additive; never destructive. H-INV-8."""
    base = Path(args.base).expanduser().resolve() if getattr(args, "base", None) else output_root()

    if getattr(args, "list", False):
        backups_dir = base / "backups"
        if not backups_dir.exists():
            print("backup: no snapshots yet.")
            return
        snaps = sorted(
            [d for d in backups_dir.iterdir()
             if d.is_dir() and (d / ".backup_ok").exists()]
        )
        if not snaps:
            print("backup: no complete snapshots yet.")
            return
        print(f"backup: {len(snaps)} snapshot(s) under {backups_dir}:")
        for s in snaps:
            print(f"  {s.name}  ({_fmt_size(_dir_size(s))})")
        return

    full = getattr(args, "full", False)
    try:
        dest = _do_backup(base, full=full)
        label = " (full)" if full else ""
        print(f"backup{label}: snapshot created at {dest}  ({_fmt_size(_dir_size(dest))})")
    except BackupError as exc:
        sys.exit(str(exc))


# ── restore command (H-INV-9) ─────────────────────────────────────────────────────────────

def _cmd_restore(args):
    """Restore a snapshot's library/ + explore/ back to the output root. H-INV-9.

    Dry-run by default (G-INV-8); --apply to act. Takes a safety backup of current state
    unless --force.
    """
    base = Path(args.base).expanduser().resolve() if getattr(args, "base", None) else output_root()
    backups_dir = base / "backups"

    if not backups_dir.exists():
        sys.exit("restore: no backups/ dir found. Nothing to restore.")

    stamp = getattr(args, "stamp", "latest") or "latest"
    if stamp == "latest":
        snaps = sorted(
            [s for s in backups_dir.iterdir()
             if s.is_dir() and (s / ".backup_ok").exists()]
        )
        if not snaps:
            sys.exit("restore: no valid snapshots found.")
        snap_dir = snaps[-1]
    else:
        snap_dir = backups_dir / stamp
        if not snap_dir.exists():
            sys.exit(f"restore: snapshot {stamp!r} not found under {backups_dir}.")
        if not (snap_dir / ".backup_ok").exists():
            sys.exit(f"restore: snapshot {stamp!r} is incomplete (may be partial).")

    # Determine restore plan
    is_full = (snap_dir / "projects").exists()
    tiers_to_restore = [src for src in (snap_dir / "library", snap_dir / "explore")
                        if src.exists()]

    if not tiers_to_restore:
        print(f"restore: snapshot {snap_dir.name} contains no curated tiers to restore.")
        return

    # Describe what would happen
    overwritten = [base / src.name for src in tiers_to_restore if (base / src.name).exists()]
    added = [base / src.name for src in tiers_to_restore if not (base / src.name).exists()]

    print(f"restore: snapshot {snap_dir.name}")
    for d in overwritten:
        print(f"  overwrite: {d}")
    for d in added:
        print(f"  add: {d}")

    if not is_full:
        print("  WARNING: this is a non-full snapshot — previews will go silent, opens fall back "
              "to the library HTML copy, and comparability is dead until re-analysis (H-INV-9).")

    apply_ = getattr(args, "apply", False)
    force_ = getattr(args, "force", False)

    if not apply_:
        print("(dry-run — pass --apply to restore)")
        return

    # Safety backup of current state before overwriting, unless --force
    if overwritten and not force_:
        print("  taking safety backup of current state before overwriting...")
        try:
            safety = _do_backup(base)
            print(f"  safety backup: {safety}")
        except BackupError as exc:
            sys.exit(f"restore: safety backup failed — {exc}. Nothing restored.")

    # Perform the restore (G-INV-7: only under the configured root, which snap_dir is)
    for src in tiers_to_restore:
        dest = base / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    print(f"restore: done — {snap_dir.name} → {base}")


# ── reset (H-INV-6) ──────────────────────────────────────────────────────────────────────

def _cmd_reset(args):
    """Wipe the working state (keep + scratch + references + loose files). Keeps backups/.

    Auto-creates a safety backup first (unless --no-backup). Aborts if safety backup fails
    (H-INV-8). Dry-run unless --yes-wipe-everything. H-INV-6.
    """
    base = Path(args.base).expanduser().resolve() if getattr(args, "base", None) else output_root()

    tier_dirs = [base / t for t in _RESET_TIERS if (base / t).exists()]
    loose_files = [base / f for f in _RESET_LOOSE_FILES if (base / f).exists()]
    targets = tier_dirs + loose_files

    if not targets:
        print(f"reset: nothing under {base} — already clean.")
        return

    total = sum(_dir_size(d) if d.is_dir() else d.stat().st_size for d in targets)

    print(f"reset would remove under {base}:")
    for d in targets:
        sz = _dir_size(d) if d.is_dir() else d.stat().st_size
        print(f"  {d}  ({_fmt_size(sz)})")
    print(f"  Total: {_fmt_size(total)}")
    print("  Source .als/audio files are UNTOUCHED. Re-analyse to rebuild.")
    print("  backups/ is KEPT — use `restore` to recover curated work.")

    if not getattr(args, "yes_wipe_everything", False):
        print("(dry-run — pass --yes-wipe-everything to actually wipe)")
        return

    no_backup = getattr(args, "no_backup", False)
    i_understand = getattr(args, "i_understand", False)

    if not no_backup:
        # Auto-safety backup first — abort the entire reset if it fails (H-INV-6)
        print("  creating safety backup before wiping...")
        try:
            safety_snap = _do_backup(base)
            print(f"  safety backup: {safety_snap}")
        except BackupError as exc:
            sys.exit(f"reset: safety backup FAILED — {exc}. Nothing removed (H-INV-6).")
    else:
        # --no-backup: require --i-understand when there is no existing snapshot (H-INV-6)
        if not _has_valid_backup(base) and not i_understand:
            sys.exit(
                "reset --no-backup: no existing snapshot covers the curated work.\n"
                "This wipe is as irreversible as hard-reset for your library + references.\n"
                "Pass --i-understand to proceed anyway."
            )
        print("  (--no-backup: skipping safety backup)")

    # G-INV-7: paranoid root-boundary check before any deletion
    removed = []
    for d in targets:
        try:
            d.relative_to(base)
        except ValueError:
            sys.exit(f"reset: refusing to delete {d} — outside output root {base}")
        if d.is_dir():
            shutil.rmtree(d)
        else:
            d.unlink()
        removed.append(d)

    total_removed = sum(_dir_size(d) if d.exists() else 0 for d in removed)
    print(f"reset: removed {[str(d) for d in removed]}")


# ── hard-reset (H-INV-10) ────────────────────────────────────────────────────────────────

def _cmd_hard_reset(args):
    """Wipe the ENTIRE output root including backups/. Dry-run by default.

    Requires BOTH --yes-wipe-everything AND --including-backups to act.
    No safety backup (there is nowhere to put one). H-INV-10.
    """
    base = Path(args.base).expanduser().resolve() if getattr(args, "base", None) else output_root()

    if not base.exists():
        print(f"hard-reset: {base} does not exist — nothing to do.")
        return

    try:
        contents = sorted(base.iterdir())
    except OSError:
        contents = []

    if not contents:
        print(f"hard-reset: {base} is already empty.")
        return

    total = sum(_dir_size(d) if d.is_dir() else d.stat().st_size for d in contents)

    print(f"hard-reset would remove EVERYTHING under {base}:")
    for d in contents:
        sz = _dir_size(d) if d.is_dir() else d.stat().st_size
        print(f"  {d}  ({_fmt_size(sz)})")
    print(f"  Total: {_fmt_size(total)}")
    print("  THIS INCLUDES ALL BACKUPS — there is no recovery after this.")

    yes_wipe = getattr(args, "yes_wipe_everything", False)
    incl_backups = getattr(args, "including_backups", False)

    if not yes_wipe or not incl_backups:
        print("(dry-run — pass BOTH --yes-wipe-everything AND --including-backups to actually wipe)")
        return

    # G-INV-7: paranoid root-boundary check
    for d in contents:
        try:
            d.relative_to(base)
        except ValueError:
            sys.exit(f"hard-reset: refusing to delete {d} — outside output root {base}")
        if d.is_dir():
            shutil.rmtree(d)
        else:
            d.unlink()

    print(f"hard-reset: output root {base} cleared — all data destroyed including backups.")


# ── gc (H-INV-3) + Ableton-tail mode (H-INV-5) ───────────────────────────────────────────

def _cmd_gc(args):
    """Prune orphaned run dirs (gc) or Ableton tco tail dirs (--ableton-tails)."""
    if args.ableton_tails:
        _gc_ableton_tails(args)
        return

    base = Path(args.base).expanduser().resolve() if args.base else output_root()
    projects_dir = base / "projects"
    lib_root = library_root()

    plan = gc_plan(projects_dir, lib_root)
    orphans = plan["orphan"]

    if not orphans:
        print("gc: nothing to prune — no orphaned run dirs found.")
        if plan["keep_referenced"]:
            print(f"  (keeping {len(plan['keep_referenced'])} referenced run(s))")
        if plan["keep_best"]:
            print(f"  (keeping {len(plan['keep_best'])} best-undeposited run(s))")
        return

    total_sz = sum(_dir_size(p) for p in orphans)
    verb = "removing" if args.apply else "would remove"
    print(f"gc {verb} {len(orphans)} orphaned run dir(s) ({_fmt_size(total_sz)}):")
    for p in orphans:
        print(f"  {p}  ({_fmt_size(_dir_size(p))})")
    if plan["keep_referenced"]:
        print(f"  keeping {len(plan['keep_referenced'])} referenced run(s) (library members, G-INV-10)")
    if plan["keep_best"]:
        print(f"  keeping {len(plan['keep_best'])} best-undeposited run(s) per slug (G-INV-15)")

    if not args.apply:
        print("(dry-run — pass --apply to prune)")
        return

    # G-INV-7: paranoid check — only delete under our output root
    for p in orphans:
        try:
            p.relative_to(base)
        except ValueError:
            sys.exit(f"gc: refusing to delete {p} — outside output root {base}")
        shutil.rmtree(p)
    print(f"gc: removed {len(orphans)} orphaned run dir(s), reclaimed {_fmt_size(total_sz)}.")


def _gc_ableton_tails(args):
    """H-INV-5: sweep track-coach-output/ tails outside the output root."""
    if args.scan_dir:
        tco_dirs = [Path(args.scan_dir).expanduser().resolve()]
    else:
        oroot = Path(args.base).expanduser().resolve() if args.base else output_root()
        tco_dirs = _tco_dirs_from_library(library_root(), oroot)

    if not tco_dirs:
        print("gc --ableton-tails: no track-coach-output/ dirs found to scan.")
        return

    scan = ableton_tail_scan(tco_dirs)

    for tco, slug in scan["real_runs"]:
        print(f"  KEEP (has real runs): {slug}")
    verb = "remove" if args.apply else "would remove"
    for tco, slug in scan["safe"]:
        print(f"  {verb} (empty/dangling only): {slug}")
    for tco in scan["missing"]:
        print(f"  (not found on disk): {tco}")

    if not scan["safe"]:
        print("gc --ableton-tails: nothing safe to remove.")
        return
    if not args.apply:
        print(f"({len(scan['safe'])} safe slug dir(s) — pass --apply to remove)")
        return

    for _, slug in scan["safe"]:
        shutil.rmtree(slug)
    print(f"gc --ableton-tails: removed {len(scan['safe'])} safe slug dir(s).")


# ── remove (H-INV-2) ──────────────────────────────────────────────────────────────────────

def _cmd_remove(args):
    """Remove a track (or one version) from the library. Dry-run by default. H-INV-2."""
    root = library_root()
    idx = load_index(root)
    wdir = root / "widgets"
    track = args.track
    version = args.version if hasattr(args, "version") else None

    keep, to_remove = remove_plan(idx["entries"], track, version)

    if not to_remove:
        desc = f"version={version!r}" if version else "any version"
        print(f"remove: nothing found for track={track!r} ({desc})")
        return

    verb = "removing" if args.apply else "would remove"
    vdesc = f" version {version!r}" if version else " (all versions)"
    print(f"remove {verb} {len(to_remove)} entr{'y' if len(to_remove)==1 else 'ies'}"
          f" for {track!r}{vdesc}:")
    for e in to_remove:
        wf = wdir / e["widget"]
        ex = "exists" if wf.exists() else "missing"
        print(f"  · {e.get('stamp','?'):<18} {e.get('mode','?'):<5} widget={e['widget']} [{ex}]")
    print("  (run dirs NOT deleted — run `gc` afterwards to reclaim scratch)")

    if not args.apply:
        print("(dry-run — pass --apply to remove)")
        return

    # Delete widget files + rewrite index in one step (G-INV-11)
    for e in to_remove:
        wf = wdir / e["widget"]
        if wf.exists():
            wf.unlink()
    idx["entries"] = keep
    save_index(root, idx)
    print(f"removed {len(to_remove)} entr{'y' if len(to_remove)==1 else 'ies'}; {len(keep)} left.")
    _regen_catalog()


# ── prune-versions (H-INV-4) ─────────────────────────────────────────────────────────────

def _cmd_prune_versions(args):
    """Keep only the newest N versions per track. Dry-run by default; --apply acts. H-INV-4."""
    root = library_root()
    idx = load_index(root)
    entries = idx["entries"]

    # No --keep → show current counts, do nothing (H-INV-4: no silent default)
    if args.keep is None:
        versions = group_versions([e for e in entries if isinstance(e, dict)])
        if not versions:
            print("library is empty.")
            return
        print("Current versions per track (newest first; pass --keep N to prune):")
        for track, vs in sorted(versions.items()):
            print(f"  {track}: {len(vs)} version(s) — {', '.join(v['label'] for v in vs)}")
        return

    keep_n = args.keep
    if keep_n < 0:
        sys.exit("prune-versions: --keep must be >= 0")

    keep, to_drop = prune_versions_plan(entries, keep_n)

    if not to_drop:
        print(f"prune-versions: nothing to drop (all tracks already <= {keep_n} version(s)).")
        return

    wdir = root / "widgets"
    verb = "dropping" if args.apply else "would drop"
    print(f"prune-versions {verb} {len(to_drop)} entr{'y' if len(to_drop)==1 else 'ies'}"
          f" (keeping newest {keep_n} version(s) per track):")
    for e in to_drop:
        wf = wdir / e["widget"]
        ex = "exists" if wf.exists() else "missing"
        print(f"  · {e.get('track','?'):<22} stamp={e.get('stamp','?'):<18} [{ex}]")
    print("  (run dirs NOT deleted — run `gc` afterwards to reclaim scratch)")

    if not args.apply:
        print(f"(dry-run — pass --apply to prune)")
        return

    # Delete widget files, rewrite index, regen catalog — all in one step (G-INV-11)
    for e in to_drop:
        wf = wdir / e["widget"]
        if wf.exists():
            wf.unlink()
    idx["entries"] = keep
    save_index(root, idx)
    print(f"pruned {len(to_drop)} entr{'y' if len(to_drop)==1 else 'ies'}; {len(keep)} left.")
    _regen_catalog()


def _cmd_dereference(args):
    """Drop library entries whose src_run_dir is under a reference-album path. Dry-run by default. G-INV-20.

    Never deletes run dirs on disk. Only modifies the library index.
    --apply: backs up index.json to index.json.bak-<UTC-timestamp> before writing.
    """
    root = library_root()
    album_paths = args.album_path or []
    if not album_paths:
        sys.exit("dereference: at least one --album-path is required")

    idx = load_index(root)
    to_keep = []
    to_drop = []
    for e in idx["entries"]:
        if not isinstance(e, dict):
            to_keep.append(e)
            continue
        src = e.get("src_run_dir", "")
        if any(ap in src for ap in album_paths):
            to_drop.append(e)
        else:
            to_keep.append(e)

    if not to_drop:
        print("dereference: no matching entries found.")
        return

    verb = "would drop" if not args.apply else "dropping"
    for e in to_drop:
        print(f"  {verb}: {e.get('track', '?')} · {e.get('stamp', '?')} "
              f"(src: {e.get('src_run_dir', '?')})")

    if not args.apply:
        print(f"(dry-run — {len(to_drop)} entr{'y' if len(to_drop) == 1 else 'ies'} "
              f"would be dropped — pass --apply to act)")
        return

    # Back up index before modifying (G-INV-20: always back up on --apply)
    idx_path = root / "index.json"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak_path = root / f"index.json.bak-{ts}"
    shutil.copy2(idx_path, bak_path)
    print(f"  backed up index to {bak_path.name}")

    idx["entries"] = to_keep
    save_index(root, idx)
    print(f"dereference: dropped {len(to_drop)} entr{'y' if len(to_drop) == 1 else 'ies'}; "
          f"{len(to_keep)} left. Run dirs on disk are untouched (use `gc` to reclaim).")


def _known_tracks(root: Path) -> set:
    return {e.get("track") for e in load_index(root).get("entries", [])
            if isinstance(e, dict) and e.get("track")}


def _cmd_alias(args):
    """Record that two tracks are the SAME song under different filenames, so the catalog shows them
    as ONE row (their bounces merge as versions). Stored in aliases.json; reversible with --remove.

    `--merge SLUG --into CANON` aliases SLUG → CANON. `--list` prints the map. `--remove SLUG` drops
    an alias. A merge rebuilds the catalog so the effect is immediate (turnkey)."""
    root = library_root()
    aliases = load_aliases(root)

    if args.list:
        if not aliases:
            print("no aliases set — every track is its own catalog row.")
            return
        print(f"{len(aliases)} alias(es):")
        for a, c in sorted(aliases.items()):
            print(f"  {a}  →  {c}")
        return

    if args.remove:
        if args.remove not in aliases:
            print(f"alias: '{args.remove}' is not aliased — nothing to remove.")
            return
        target = aliases.pop(args.remove)
        save_aliases(root, aliases)
        print(f"alias: removed {args.remove} → {target}; it is its own catalog row again.")
        import catalog
        catalog.build_catalog()
        return

    # --merge SLUG --into CANON
    slug, canon = args.merge, args.into
    if not slug or not canon:
        sys.exit("alias: --merge SLUG --into CANON (both required); or --list / --remove SLUG")
    canon = resolve_alias(canon, aliases)  # if CANON is itself an alias, point at the true canonical
    if slug == canon:
        sys.exit(f"alias: '{slug}' and '{canon}' resolve to the same track — nothing to merge.")
    known = _known_tracks(root)
    for s in (slug, canon):
        if s not in known:
            print(f"alias: warning — '{s}' is not a track in the library index "
                  f"(known: {', '.join(sorted(known)) or 'none'}).", file=sys.stderr)
    # Guard a cycle: CANON must not resolve back through SLUG.
    probe = dict(aliases); probe[slug] = canon
    if resolve_alias(canon, probe) == slug:
        sys.exit(f"alias: refusing to merge — {slug} → {canon} would form a cycle.")
    aliases[slug] = canon
    save_aliases(root, aliases)
    print(f"alias: {slug} → {canon}; they now share ONE catalog row (bounces become versions). "
          f"Undo with `alias --remove {slug}`.")
    import catalog
    catalog.build_catalog()


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
    c = sub.add_parser("clean", help="prune library entries (legacy — prefer `remove` / `prune-versions`)")
    c.add_argument("--all", action="store_true")
    c.add_argument("--older-than", type=float, default=None, metavar="DAYS")
    c.add_argument("--keep-per-track", type=int, default=None, metavar="N")
    c.add_argument("--track", default=None)
    c.add_argument("--missing", action="store_true", help="drop entries whose widget file is gone")
    c.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    c.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)  # back-compat alias for --apply
    c.add_argument("--dry-run", action="store_true", help="preview only (redundant; dry-run is the default)")
    c.set_defaults(func=_cmd_clean)
    # reset (H-INV-6)
    # backup (H-INV-8)
    bk = sub.add_parser("backup",
                         help="snapshot curated tiers (library/ + explore/) — additive, never destructive")
    bk.add_argument("--base", default=None, help="output root (default: ~/.track-coach)")
    bk.add_argument("--full", action="store_true",
                    help="also include projects/ scratch tier (full disk image)")
    bk.add_argument("--list", action="store_true", dest="list",
                    help="list existing snapshots with dates and sizes")
    bk.set_defaults(func=_cmd_backup)
    # restore (H-INV-9)
    rs = sub.add_parser("restore",
                         help="restore a snapshot's library/ + explore/ (dry-run by default)")
    rs.add_argument("stamp", nargs="?", default="latest",
                    help="snapshot stamp to restore, or 'latest' (default: latest)")
    rs.add_argument("--base", default=None, help="output root (default: ~/.track-coach)")
    rs.add_argument("--apply", action="store_true",
                    help="actually restore (dry-run without this flag)")
    rs.add_argument("--force", action="store_true",
                    help="skip safety backup before overwriting current state")
    rs.set_defaults(func=_cmd_restore)
    # reset (H-INV-6) — revised: also wipes explore/ + loose files; auto-backup first
    rst = sub.add_parser("reset",
                          help="wipe working state (library/+projects/+explore/) keeping backups/ (dry-run by default)")
    rst.add_argument("--base", default=None, help="output root to wipe (default: ~/.track-coach)")
    rst.add_argument("--yes-wipe-everything", action="store_true", dest="yes_wipe_everything",
                     help="actually wipe — required; a bare reset is always a dry-run")
    rst.add_argument("--no-backup", action="store_true", dest="no_backup",
                     help="skip auto-safety backup (requires --i-understand when no snapshot exists)")
    rst.add_argument("--i-understand", action="store_true", dest="i_understand",
                     help="acknowledge unrecoverable wipe when --no-backup and no snapshot exists")
    rst.set_defaults(func=_cmd_reset)
    # hard-reset (H-INV-10)
    hr = sub.add_parser("hard-reset",
                         help="wipe ENTIRE output root including backups/ (dry-run by default; "
                              "requires BOTH --yes-wipe-everything AND --including-backups)")
    hr.add_argument("--base", default=None, help="output root (default: ~/.track-coach)")
    hr.add_argument("--yes-wipe-everything", action="store_true", dest="yes_wipe_everything",
                    help="first confirm (dry-run without it)")
    hr.add_argument("--including-backups", action="store_true", dest="including_backups",
                    help="second confirm: explicitly acknowledge backups will be destroyed")
    hr.set_defaults(func=_cmd_hard_reset)
    # gc (H-INV-3 / H-INV-5)
    g = sub.add_parser("gc", help="prune orphaned run dirs under the output root (dry-run by default)")
    g.add_argument("--base", default=None, help="output root (default: ~/.track-coach)")
    g.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    g.add_argument("--ableton-tails", action="store_true", dest="ableton_tails",
                   help="sweep track-coach-output/ tails outside the output root (H-INV-5)")
    g.add_argument("--scan-dir", default=None, dest="scan_dir",
                   help="explicit track-coach-output/ dir to scan (default: auto from library index)")
    g.set_defaults(func=_cmd_gc)
    # remove (H-INV-2)
    rm = sub.add_parser("remove", help="remove a track (or one version) from the library")
    rm.add_argument("track", help="track name (as shown by `library list`)")
    rm.add_argument("version", nargs="?", default=None,
                    help="version stamp or label (omit to remove all versions)")
    rm.add_argument("--apply", action="store_true", help="actually remove (default: dry-run)")
    rm.set_defaults(func=_cmd_remove)
    # prune-versions (H-INV-4)
    pv = sub.add_parser("prune-versions",
                        help="keep only the newest N versions per track (dry-run by default)")
    pv.add_argument("--keep", type=int, default=None, metavar="N",
                    help="versions to keep per track (omit to inspect; no silent default)")
    pv.add_argument("--apply", action="store_true", help="actually prune (default: dry-run)")
    pv.set_defaults(func=_cmd_prune_versions)
    # dereference (G-INV-20)
    dr = sub.add_parser("dereference",
                        help="drop library entries whose src_run_dir is under a reference-album path "
                             "(G-INV-20, dry-run by default — never deletes run dirs on disk)")
    dr.add_argument("--album-path", dest="album_path", action="append", default=None,
                    metavar="PATH",
                    help="path substring to match against src_run_dir (repeatable)")
    dr.add_argument("--apply", action="store_true",
                    help="actually drop entries after backing up index.json (default: dry-run)")
    dr.set_defaults(func=_cmd_dereference)

    al = sub.add_parser("alias",
                        help="mark two tracks as the SAME song under different filenames → one catalog row")
    al.add_argument("--merge", default=None, metavar="SLUG",
                    help="the track slug to fold into another (its filename identity)")
    al.add_argument("--into", default=None, metavar="CANON",
                    help="the canonical track slug SLUG should merge into")
    al.add_argument("--remove", default=None, metavar="SLUG", help="drop the alias for SLUG")
    al.add_argument("--list", action="store_true", help="list the current same-song aliases")
    al.set_defaults(func=_cmd_alias)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
