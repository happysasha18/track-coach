#!/usr/bin/env python3
"""track-coach global library — one place that collects every rendered widget.

Each `build` deposits its offline HTML here (the widget is self-contained, so the library
archives just the HTML, never stems/audio/JSON). Lets you browse/prune analyses across tracks
without digging through per-project `track-coach-output/` folders.

Layout (root = $TRACK_COACH_LIBRARY or ~/.track-coach/library):
  <root>/widgets/<track>__<version>__<stamp>.html
  <root>/index.json   {"entries": [ {track, version, stamp, widget, verdict, mode,
                                      deposited_at, src_run_dir}, … ]}

CLI (every destructive verb is dry-run by default; --apply acts):
  library.py path
  library.py catalog [--open]
  library.py deposit --run-dir DIR [--widget FILE]
  library.py list [--track T] [--json]
  library.py remove TRACK [VERSION] [--apply]
  library.py prune-versions [--keep N] [--apply]
  library.py clean [--all] [--older-than DAYS] [--keep-per-track N] [--track T] [--missing] [--apply]
  library.py migrate [--apply]        library.py dereference --album-path P… [--apply]
  library.py alias (--merge SLUG --into CANON | --list | --remove SLUG)
  library.py gc [--base DIR] [--ableton-tails [--scan-dir DIR]] [--apply]
  library.py backup [--full] [--base DIR] [--list]   library.py restore [STAMP] [--apply] [--force]
  library.py reset --yes-wipe-everything [--no-backup] [--i-understand]
  library.py hard-reset --yes-wipe-everything --including-backups
(clean's old --yes is a hidden back-compat alias for --apply.)

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
        # The source bounce's mtime — the PRIMARY version-order key (SPEC:1367 "by audio mtime /
        # stamp"). The analyzer stamps it into run_meta (_audio_fingerprint); without carrying it
        # onto the entry, prune/order silently fell back to the stamp = most-recently-ANALYSED, and
        # could delete the newest bounce while keeping an older one (audit root class 5).
        "audio_mtime": meta.get("audio_mtime"),
    }


def _rep_sort_key(e):
    """Single canonical most-complete-then-newest ordering for picking a version's rep (RC-INV-9:
    "reads from the most-complete run", "never blended"). Completeness metric per input type — a
    PURE index entry: its `mode` field (a "full" run is more complete than "quick", full ⊇ quick
    by design, both already passed the validity gate at deposit); a run dir on disk: its
    result_*.json file count (see _count_result_files, already how gc measures it)."""
    return (1 if e.get("mode") == "full" else 0, e.get("stamp", ""), e.get("deposited_at", ""))


def _version_order_key(rep) -> tuple:
    """Type-stable oldest→newest ordering key for a version's rep (SPEC:1367 "by audio mtime /
    stamp"). Returns ``(has_mtime, mtime_or_0, stamp)`` so a bounce WITH a stored ``audio_mtime``
    sorts by bounce time and a legacy bounce WITHOUT one falls back to its dated stamp — and an
    int mtime never gets compared against a str stamp (a library mixing the two would otherwise
    raise TypeError at the sort). Entries with no mtime sort as older (before the mtime-stamped
    ones); every real deposit carries at least a stamp, so a truly empty key is the fresh case."""
    m = rep.get("audio_mtime")
    has = isinstance(m, (int, float))
    return (1 if has else 0, m if has else 0, rep.get("stamp", ""))


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
            rep = max(grp, key=_rep_sort_key)
            versions.append({"sha": sha, "rep": rep, "n_runs": len(grp),
                             "okey": _version_order_key(rep)})
        versions.sort(key=lambda x: x["okey"])  # oldest→newest; type-stable (mtime, then stamp)
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
def _atomic_write_text(path, text: str):
    """Write `text` crash-consistently: dump to a sibling `<name>.tmp`, fsync, then
    os.replace onto the target. A kill at any instant leaves either the untouched old
    file or the complete new one — never a truncated file (G-INV-11: no half state).
    This is the ONE writer every index/marker save routes through so no store file can
    be torn by a mid-write kill (2026-07-16 audit root class 1)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_index(root: Path) -> dict:
    p = root / "index.json"
    if p.exists():
        text = p.read_text()
        if not text.strip():
            return {"entries": []}  # a zero-byte / whitespace file is the fresh-root case
        try:
            d = json.loads(text)
        except ValueError as exc:
            # A present-but-unparseable index is CORRUPT, not empty. Silently returning
            # {"entries": []} here was the data-loss root: the next save persisted the loss
            # and gc then reclaimed "unreferenced" run dirs. Refuse loudly instead so the
            # real catalog is never overwritten with empty (audit root class 1).
            sys.exit(
                f"library: index.json is corrupt and cannot be read ({exc}).\n"
                f"  {p}\n"
                f"Refusing every read/write so the catalog is not overwritten with an empty "
                f"one. Inspect or restore the file (library.py restore), then retry.")
        # Normalize: entries must be dicts. A stray string (legacy slug from an older
        # run-init that appended a plain slug instead of a metadata dict) is coerced to a
        # minimal dict so every downstream caller sees a uniform type. Using {"widget": s}
        # preserves the original string rather than silently discarding it.
        raw = d.get("entries", [])
        d["entries"] = [e if isinstance(e, dict) else {"widget": str(e)} for e in raw]
        return d
    return {"entries": []}


def save_index(root: Path, idx: dict):
    root.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(root / "index.json", json.dumps(idx, ensure_ascii=False, indent=2))


ALIASES_FILE = "aliases.json"


def load_aliases(root: Path) -> dict:
    """Read the same-song alias map ``{alias_slug: canonical_slug}`` from ``<root>/aliases.json``.

    A user records that two tracks are the SAME song under different filenames (so the catalog shows
    them as one). Returns {} when the file is absent or unreadable — aliasing is purely additive."""
    p = Path(root) / ALIASES_FILE
    if not p.exists():
        return {}  # no aliases set — silent, purely additive
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        # A present-but-unparseable aliases.json means a kill tore a mid-write save. Unlike
        # the index (destructive reads depend on it), aliasing is additive, so stay lenient —
        # but WARN naming the file, so lost same-song merges are visible rather than reading
        # as an ordinary "no aliases set" (audit root class 1).
        print(f"library: warning — {p} is unreadable; treating as no aliases "
              f"(same-song merges may be lost). Re-run `alias --merge` to restore them.",
              file=sys.stderr)
        return {}
    m = data.get("aliases", data) if isinstance(data, dict) else {}
    return {str(k): str(v) for k, v in m.items() if k and v and str(k) != str(v)}


def save_aliases(root: Path, aliases: dict):
    Path(root).mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        Path(root) / ALIASES_FILE,
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
    keep, to_unlink = [], []
    for e in idx.get("entries", []):
        sd = e.get("src_run_dir", "")
        if sd and str(Path(sd).resolve()) == src:
            if e.get("widget"):
                to_unlink.append(wdir / e["widget"])
        else:
            keep.append(e)
    if to_unlink:
        # Index-first (atomic), then unlink — a kill in between leaves a harmless orphan widget,
        # never a dangling index entry (G-INV-11).
        idx["entries"] = keep
        save_index(root, idx)
        for f in to_unlink:
            if f.exists():
                f.unlink()
    return len(to_unlink)


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
        # The build still renders an honest incomplete/failed page (RC-INV-13f); it is only held
        # OUT of the library. Do NOT point at `revalidate --apply` here: revalidate only re-measures
        # runs the library already holds, so it can never see this undeposited run (it would report
        # "all runs complete"). The redo that helps is a fresh `analyze` with inputs that let the
        # signal be measured — re-analysing the same audio with the same pipeline cannot.
        raise DepositError(
            "refusing to deposit: run is incomplete (RC-INV-13) — unmeasured signals: "
            f"{', '.join(_unmeasured)}. The widget renders as an honest incomplete page and is "
            f"held out of the library. Re-run `analyze` with inputs that let those signals be "
            f"measured, or accept the tool cannot read that part of this track.")
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
            # A present-but-unparseable run_meta.json fails CLOSED: it is where the reference
            # (G-INV-18) and synthetic (G-INV-21) refusal flags live, so coercing to {} let a
            # torn marker file slip someone else's track / a fixture run into the library. Refuse.
            sys.exit(f"deposit: run_meta.json is corrupt — refusing to deposit "
                     f"(the reference/synthetic markers cannot be read).\n  {mp}\n"
                     f"Fix or re-run `analyze` for this run, then deposit again.")
    widget = Path(args.widget).expanduser() if args.widget else None
    if widget is None:
        cands = sorted(run_dir.glob("analysis_widget*.html"))
        if not cands:
            sys.exit(f"no widget html found in {run_dir}")
        # Newest by mtime, not lexicographic: widget names embed a version (…_v0.10.1.html), and
        # "v0.10.1" < "v0.9.22" as strings would deposit the STALE build (audit root class 5).
        widget = max(cands, key=lambda p: p.stat().st_mtime)
    elif not widget.exists():
        # An explicit --widget that does not exist: fail with the command's clean one-line refusal
        # shape, not a raw FileNotFoundError traceback from shutil.copy2 downstream.
        sys.exit(f"deposit: widget not found: {widget}")
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
        # Distinguish a genuinely empty index from a filter that matched nothing — saying
        # "(library empty)" for a typo'd --track reads as "all deposits are lost".
        if args.track and load_index(library_root())["entries"]:
            print(f"list: no match for track {args.track!r} (the library has other tracks).")
        else:
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
    # --apply is canonical; --yes is a silent back-compat alias. An explicit --dry-run ALWAYS
    # wins: `clean --apply --dry-run` must preview, never delete (the flag was parsed but never
    # read before — a quiet over-deletion path for a destructive command).
    act = (args.apply or args.yes) and not getattr(args, "dry_run", False)
    keep, remove = clean_plan(
        idx["entries"], exists=lambda e: (wdir / e.get("widget", "")).exists(),
        older_than_days=args.older_than, keep_per_track=args.keep_per_track,
        track=args.track, missing=args.missing, all_=args.all)
    if not remove:
        print("nothing to clean.")
        return
    for e in remove:  # .get(): a legacy string entry has no 'track'/'widget' — never KeyError
        print(f"{'would remove' if not act else 'remove'}: "
              f"{e.get('track','?')} · {e.get('stamp','?')} ({e.get('widget','?')})")
    if not act:
        print(f"({len(remove)} entr{'y' if len(remove)==1 else 'ies'} would be removed — pass --apply to act)")
        return
    # Index-first (atomic), then unlink the now-unreferenced widgets — a kill in between leaves a
    # harmless orphan widget file, never a dangling index entry (G-INV-11).
    idx["entries"] = keep
    save_index(root, idx)
    for e in remove:
        w = e.get("widget")
        if w and (wdir / w).exists():
            (wdir / w).unlink()
    print(f"removed {len(remove)}; {len(keep)} left.")
    _regen_catalog()  # keep the visible catalog in step (G-INV-11), like remove/prune-versions


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
    the library index.  Crash-consistent PER MEMBER: each member's index entry is rewritten
    immediately after its own move succeeds, so index and disk agree at every step of the loop —
    a later member's failure can never leave an earlier, already-moved member's entry pointing at
    its stale (now-nonexistent) source (G-INV-16/G-INV-11 all-or-clean-report … or nothing is
    changed, applied per member rather than only at the end).

    Returns the list of moved plan items (same shape as ``migrate_plan``).
    Raises ``RuntimeError`` on the first move failure; already-moved dirs — and their index
    entries — are left in their new, consistent state; the failed member and anything after it
    in the plan is untouched.
    """
    plan = migrate_plan(root, output_root)
    if not plan:
        return []

    root = Path(root)
    moved = []
    for item in plan:
        src, dst = item["src"], item["dst"]
        if not src.exists():
            raise RuntimeError(
                f"migrate: source run dir not found on disk (already moved?): {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved.append(item)

        # Persist this member's new pointer right away — index and disk stay consistent even
        # if a later member's move raises.
        idx = load_index(root)
        for e in idx.get("entries", []):
            if isinstance(e, dict) and e.get("src_run_dir", "") == str(src):
                e["src_run_dir"] = str(dst)
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


def _entry_size(d: Path) -> int:
    """Size of a top-level output-root entry, symlink-SAFE — a symlink is sized by its own
    lstat, never by following it (a dangling link would raise). H-INV-10/11."""
    if d.is_symlink():
        try:
            return d.lstat().st_size
        except OSError:
            return 0
    return _dir_size(d) if d.is_dir() else d.stat().st_size


def _remove_entry(d: Path):
    """Delete a top-level entry symlink-SAFELY: unlink a symlink (never rmtree it and never
    follow it), rmtree a real dir, unlink a real file. A symlinked-in folder therefore has
    only its link removed, never its target's contents. H-INV-10/11."""
    if d.is_symlink():
        d.unlink()
    elif d.is_dir():
        shutil.rmtree(d)
    else:
        d.unlink()


# ── gc: prune scratch, keep referenced + best-undeposited (H-INV-3) ─────────────────────

def _count_result_files(run_dir: Path) -> int:
    """Count result_*.json files in a run dir (completeness proxy for RC-INV-9)."""
    return len(list(run_dir.glob("result_*.json")))


def _best_undeposited_run(slug_dir: Path, referenced: set) -> "Path | None":
    """Return the most-complete run dir under slug_dir that is NOT referenced in the library.

    'Most complete' = most result_*.json files; tiebreak = newest mtime — the SAME key
    run_dir.newest_run (the RC-INV-9 read selector) uses, so gc keeps exactly the run the read
    layer reads from. A name (lexicographic) tiebreak diverged: on equal counts gc could prune the
    very run coaching reads (G-INV-15).
    Returns None if slug_dir has no undeposited runs.
    G-INV-15 / RC-INV-9.
    """
    best, best_key = None, (-1, -1.0)
    for item in slug_dir.iterdir():
        if item.name == "latest" or item.is_symlink():
            continue
        if not item.is_dir():
            continue
        if str(item) in referenced or str(item.resolve()) in referenced:
            continue
        n = _count_result_files(item)
        try:
            mt = item.stat().st_mtime
        except OSError:
            mt = -1.0
        k = (n, mt)
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
    """True if slug_dir holds ANY real (non-symlink) content beyond index.json.

    'Safe' (deletable) slug dirs contain ONLY dangling symlinks and index.json. A loose
    regular file — a user's bounce, notes.txt — is real content too, so it disqualifies
    the dir from 'safe': the audit found this classifier only checked for child *dirs*,
    letting `rmtree` delete a slug dir that held a loose user file (H-INV-5: the sweep
    never touches non-track-coach files).
    """
    for item in slug_dir.iterdir():
        if item.name == "index.json":
            continue
        if item.is_symlink():
            continue  # dangling or live symlink — not real content itself
        return True   # any non-symlink file OR dir is real content → not safe
    return False


def _is_tco_shape(p) -> bool:
    """True when `p`'s basename is a track-coach output dir (`track-coach-output`).

    The Ableton-tail sweep must only ever touch a real output dir. The KI-1 shallow-deposit
    shape makes `src.parent.parent` land on the Ableton project folder itself; gating on this
    basename skips that folder so the destructive classifier never scans a user's own dir
    (H-INV-5). PURE."""
    return Path(p).name == "track-coach-output"


def ableton_tail_scan(tco_dirs: list) -> dict:
    """Classify slug dirs within track-coach-output/ directories.

    Returns {
        'safe': [(tco_dir, slug_dir), …],      # empty/dangling-only — safe to remove
        'real_runs': [(tco_dir, slug_dir), …], # has real run content — NEVER auto-delete
        'missing': [tco_dir, …],               # tco_dir does not exist on disk
        'skipped': [tco_dir, …],               # not a track-coach-output dir — never scanned
    }
    H-INV-5: distinguishes safe tails from slug dirs with real runs, and refuses to scan a
    target that is not itself a `track-coach-output/` dir (a malformed KI-1 index entry could
    otherwise point the sweep at an arbitrary user folder).
    """
    result: dict = {"safe": [], "real_runs": [], "missing": [], "skipped": []}
    for tco_dir in tco_dirs:
        tco_dir = Path(tco_dir)
        if not _is_tco_shape(tco_dir):
            result["skipped"].append(tco_dir)  # never scan a non-output dir (H-INV-5)
            continue
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

def remove_plan(entries: list, track: str, version: "str | None" = None,
                aliases: dict = None) -> tuple:
    """Decide which library entries to remove for a track (and optional version). PURE.

    - version=None → remove ALL entries for that track (its whole catalog row)
    - version=<str> → remove one version: a literal stamp/version match, else the synthesized
      label (v1..vN) the catalog and `prune-versions` show, resolved to its audio_sha group.

    Alias-aware: the requested track and every entry are resolved through ``aliases`` to their
    canonical slug, so `remove b` where a→b names exactly the ONE visible row b (a's folded
    bounces included) — H-INV-2 "names exactly what goes (which catalog rows)".

    Returns (keep, to_remove). Run dirs are NOT deleted (gc reclaims them). H-INV-2.
    """
    aliases = aliases or {}
    canon_req = resolve_alias(track or "", aliases)
    mine = [e for e in entries
            if isinstance(e, dict) and e.get("track")
            and resolve_alias(e["track"], aliases) == canon_req]
    if not mine:
        return list(entries), []
    if version is None:
        to_remove = mine
    else:
        lit = [e for e in mine if e.get("stamp") == version or e.get("version") == version]
        if lit:
            to_remove = lit
        else:
            # Resolve a synthesized version label (v1..vN, as shown by list/prune) to its bounce
            # group, so `remove "T" v2` drops all runs of that bounce, not "nothing found".
            vgroups = group_versions(canonicalize_entries(mine, aliases)).get(canon_req, [])
            want = next((v["sha"] for v in vgroups if v["label"] == version), None)
            to_remove = ([e for e in mine if (e.get("audio_sha") or e.get("widget")) == want]
                         if want else [])
    if not to_remove:
        return list(entries), []
    rid = {id(e) for e in to_remove}
    keep = [e for e in entries if id(e) not in rid]
    return keep, to_remove


# ── prune-versions: explicit old-version pruning (H-INV-4) ───────────────────────────────

def prune_versions_plan(entries: list, keep_n: int, aliases: dict = None) -> tuple:
    """Keep only the newest N audio versions per track; return (keep, to_drop). PURE.

    A 'version' is a distinct audio_sha group (same logic as group_versions).
    All entries in a dropped version group are dropped together.
    keep_n=0 → drops all versions for every track.
    Caller must always supply keep_n (no silent default). H-INV-4.

    Grouping is by the CANONICAL slug (``aliases``): a same-song merge (a→b, G-INV-23) folds both
    filenames onto one catalog row, so "keep newest N per track" must count per row, not per raw
    slug — otherwise it disagrees with what the user sees. Original entries are still the ones
    dropped (matched by id), so the merged bounces prune as one version stream.

    Returns (keep, to_drop).
    """
    if keep_n < 0:
        raise ValueError(f"keep_n must be >= 0, got {keep_n}")
    aliases = aliases or {}
    by_track: dict = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        canon = resolve_alias(e.get("track", "?"), aliases)
        by_track.setdefault(canon, []).append(e)

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
            rep = max(grp, key=_rep_sort_key)
            versions.append({"sha": sha, "entries": grp, "okey": _version_order_key(rep)})
        versions.sort(key=lambda v: v["okey"])  # oldest→newest; type-stable (mtime, then stamp)
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
    """True only if a complete snapshot actually PROTECTS the curated work present at `base`
    right now: it carries .backup_ok AND, for every curated tier that currently exists at base
    (library/, explore/), the snapshot contains that tier. An empty `.backup_ok`-only snapshot
    (a backup taken when the root was still empty) no longer disarms the reset --no-backup
    irreversibility guard for a since-populated library. H-INV-6."""
    backups_dir = base / "backups"
    if not backups_dir.exists():
        return False
    needed = [t for t in ("library", "explore") if (base / t).exists()]
    try:
        for snap in backups_dir.iterdir():
            if snap.name.startswith("_tmp_"):
                continue  # a killed backup's litter is never a trusted snapshot
            if not (snap.is_dir() and (snap / ".backup_ok").exists()):
                continue
            if all((snap / t).exists() for t in needed):
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
    # Sweep any `_tmp_*` litter a previously-killed backup left behind — it is never a trusted
    # snapshot, yet only hard-reset would otherwise ever reclaim it (backups/ is not swept).
    for stale in backups_dir.glob("_tmp_*"):
        shutil.rmtree(stale, ignore_errors=True)
    try:
        tmp_dest.mkdir(parents=True, exist_ok=True)
        for src in sources:
            if src.is_dir():
                shutil.copytree(src, tmp_dest / src.name)
            else:
                shutil.copy2(src, tmp_dest / src.name)
        tmp_dest.rename(dest)
        # Write the trust marker LAST, into the FINAL dir — after the rename. A kill before
        # this leaves an unmarked (untrusted, ignored) dir, never a trusted `_tmp_` snapshot
        # that would win `restore latest` (underscore sorts after every real stamp). H-INV-8.
        (dest / ".backup_ok").write_text("ok")
    except Exception as exc:
        shutil.rmtree(tmp_dest, ignore_errors=True)
        shutil.rmtree(dest, ignore_errors=True)
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
    # Refuse a no-op backup: nothing curated to capture means an empty `.backup_ok` snapshot
    # that falsely reads as "your work is backed up" (and, before the _has_valid_backup fix,
    # could disarm reset's irreversibility guard). Common cause: an unmounted/typo'd --base.
    has_any = (any((base / t).exists() for t in ("library", "explore"))
               or (base / "config.json").exists()
               or (full and (base / "projects").exists()))
    if not has_any:
        sys.exit(f"backup: nothing to back up under {base} "
                 f"(no library/, explore/, or config.json). Check the path (is --base mounted?).")
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
        # A stamp with path separators (or an absolute path) would escape backups/ and let
        # restore source tiers from an arbitrary directory that happens to carry .backup_ok.
        # Require a plain stamp that resolves to a direct child of backups/. H-INV-11/G-INV-7.
        if os.sep in stamp or (os.altsep and os.altsep in stamp) or Path(stamp).is_absolute():
            sys.exit(f"restore: invalid snapshot stamp {stamp!r} — pass a plain stamp under "
                     f"backups/ (use --base to point at a different root).")
        snap_dir = backups_dir / stamp
        try:
            snap_dir.resolve().relative_to(backups_dir.resolve())
        except ValueError:
            sys.exit(f"restore: snapshot {stamp!r} escapes {backups_dir} — refusing.")
        if not snap_dir.exists():
            sys.exit(f"restore: snapshot {stamp!r} not found under {backups_dir}.")
        if not (snap_dir / ".backup_ok").exists():
            sys.exit(f"restore: snapshot {stamp!r} is incomplete (may be partial).")

    # Determine restore plan. projects/ only exists in a --full snapshot, so including it as a
    # candidate leaves non-full behaviour unchanged while a --full restore round-trips the scratch
    # tier (stems, previews, run JSONs) the H-INV-9 promise covers — previously it was never
    # restored yet the degradation warning was skipped, telling the user the restore was complete.
    is_full = (snap_dir / "projects").exists()
    tiers_to_restore = [src for src in (snap_dir / "library", snap_dir / "explore",
                                        snap_dir / "projects")
                        if src.exists()]
    config_src = snap_dir / "config.json"
    has_config = config_src.exists()

    if not tiers_to_restore and not has_config:
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
    if has_config:
        config_dest = base / "config.json"
        action = "overwrite" if config_dest.exists() else "add"
        print(f"  {action}: {config_dest}")

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

    # H-INV-9: config.json is captured on backup — restore it too, even if it's the only thing
    # in the snapshot (a config-only restore must not be skipped by the tiers-only guard above).
    if has_config:
        shutil.copy2(config_src, base / "config.json")

    print(f"restore: done — {snap_dir.name} → {base}")
    # Rebuild the catalog so a non-full restore's opens fall back to the library HTML copy
    # (G-INV-14): the restored index.html was built when the snapshot's run dirs still existed and
    # carries no fallbacks, so without this its open/preview links dangle (H-INV-9).
    _regen_catalog()


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

    total = sum(_entry_size(d) for d in targets)

    print(f"reset would remove under {base}:")
    for d in targets:
        print(f"  {d}  ({_fmt_size(_entry_size(d))})")
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
        _remove_entry(d)  # symlink-safe: a symlinked-in dir loses only its link
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
    except OSError as exc:
        # An unreadable root (permission denied, or --base pointing at a regular file) must
        # surface, not be mistaken for 'already empty' — that would tell the user the wipe
        # target holds nothing when it was simply unreadable.
        sys.exit(f"hard-reset: cannot read {base}: {exc}")

    if not contents:
        print(f"hard-reset: {base} is already empty.")
        return

    total = sum(_entry_size(d) for d in contents)

    print(f"hard-reset would remove EVERYTHING under {base}:")
    for d in contents:
        print(f"  {d}  ({_fmt_size(_entry_size(d))})")
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
        _remove_entry(d)  # symlink-safe: unlink a symlink, never rmtree/follow it

    print(f"hard-reset: output root {base} cleared — all data destroyed including backups.")


# ── gc (H-INV-3) + Ableton-tail mode (H-INV-5) ───────────────────────────────────────────

def _cmd_gc(args):
    """Prune orphaned run dirs (gc) or Ableton tco tail dirs (--ableton-tails)."""
    if args.scan_dir and not args.ableton_tails:
        # --scan-dir only scopes the tail sweep; without --ableton-tails it was silently
        # ignored and the full default-root prune ran instead — a destructive action in a
        # location the user never named. Refuse rather than run the wrong prune.
        sys.exit("gc: --scan-dir requires --ableton-tails (it scopes the Ableton-tail sweep).")
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

    # G-INV-7 + G-INV-11: validate EVERY path is under the root BEFORE deleting any (so a
    # stray path aborts with nothing removed), then delete each guarded and report precisely
    # what went — all-or-clean-report, never a partial wipe with a bare traceback.
    for p in orphans:
        try:
            p.relative_to(base)
        except ValueError:
            sys.exit(f"gc: refusing to delete {p} — outside output root {base} (nothing removed).")
    removed, freed, failed = 0, 0, []
    for p in orphans:
        sz = _dir_size(p)
        try:
            shutil.rmtree(p)
            removed += 1
            freed += sz
        except OSError as exc:
            failed.append((p, exc))
    print(f"gc: removed {removed} of {len(orphans)} orphaned run dir(s), reclaimed {_fmt_size(freed)}.")
    if failed:
        for p, exc in failed:
            print(f"  FAILED to remove {p}: {exc}")
        sys.exit(f"gc: {len(failed)} run dir(s) could not be removed (see above).")


def _gc_ableton_tails(args):
    """H-INV-5: sweep track-coach-output/ tails outside the output root."""
    if args.scan_dir:
        target = Path(args.scan_dir).expanduser().resolve()
        if not _is_tco_shape(target):
            # Refuse an arbitrary user folder — the destructive classifier only ever runs on
            # a real `track-coach-output/` dir (H-INV-5), never on a careless --scan-dir.
            sys.exit(f"gc --ableton-tails: --scan-dir must point at a 'track-coach-output' dir, "
                     f"not {target} — refusing to scan an arbitrary folder (H-INV-5).")
        tco_dirs = [target]
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
        print(f"  {verb} (empty/dangling only): {slug}  ({_fmt_size(_dir_size(slug))})")
    for tco in scan["missing"]:
        print(f"  (not found on disk): {tco}")
    for tco in scan["skipped"]:
        print(f"  SKIP (not a track-coach-output dir): {tco}")

    if not scan["safe"]:
        print("gc --ableton-tails: nothing safe to remove.")
        return
    total_sz = sum(_dir_size(s) for _, s in scan["safe"])
    if not args.apply:
        print(f"({len(scan['safe'])} safe slug dir(s), {_fmt_size(total_sz)} — pass --apply to remove)")
        return

    # all-or-clean-report (G-INV-11): delete each guarded, report precisely what went.
    removed, freed, failed = 0, 0, []
    for _, slug in scan["safe"]:
        sz = _dir_size(slug)
        try:
            shutil.rmtree(slug)
            removed += 1
            freed += sz
        except OSError as exc:
            failed.append((slug, exc))
    print(f"gc --ableton-tails: removed {removed} of {len(scan['safe'])} safe slug dir(s), "
          f"reclaimed {_fmt_size(freed)}.")
    if failed:
        for slug, exc in failed:
            print(f"  FAILED to remove {slug}: {exc}")
        sys.exit(f"gc --ableton-tails: {len(failed)} slug dir(s) could not be removed.")


# ── remove (H-INV-2) ──────────────────────────────────────────────────────────────────────

def _cmd_remove(args):
    """Remove a track (or one version) from the library. Dry-run by default. H-INV-2."""
    root = library_root()
    idx = load_index(root)
    wdir = root / "widgets"
    track = args.track
    version = args.version if hasattr(args, "version") else None

    keep, to_remove = remove_plan(idx["entries"], track, version, load_aliases(root))

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

    # Rewrite the index FIRST (atomically), THEN unlink the now-unreferenced widgets (G-INV-11).
    # A kill between the two steps leaves a harmless orphan widget file, never a dangling index
    # entry pointing at a deleted widget.
    idx["entries"] = keep
    save_index(root, idx)
    for e in to_remove:
        wf = wdir / e["widget"]
        if wf.exists():
            wf.unlink()
    print(f"removed {len(to_remove)} entr{'y' if len(to_remove)==1 else 'ies'}; {len(keep)} left.")
    _regen_catalog()


# ── prune-versions (H-INV-4) ─────────────────────────────────────────────────────────────

def _cmd_prune_versions(args):
    """Keep only the newest N versions per track. Dry-run by default; --apply acts. H-INV-4."""
    root = library_root()
    idx = load_index(root)
    entries = idx["entries"]

    aliases = load_aliases(root)
    # No --keep → show current counts, do nothing (H-INV-4: no silent default). Canonicalise first
    # so the counts match the merged catalog rows (G-INV-23), same as prune_versions_plan groups.
    if args.keep is None:
        versions = group_versions(
            canonicalize_entries([e for e in entries if isinstance(e, dict)], aliases))
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

    keep, to_drop = prune_versions_plan(entries, keep_n, aliases)

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

    # Rewrite the index FIRST (atomically), THEN unlink widgets, THEN regen catalog — index-first
    # so a kill leaves a harmless orphan widget, not a dangling index entry (G-INV-11).
    idx["entries"] = keep
    save_index(root, idx)
    for e in to_drop:
        wf = wdir / e["widget"]
        if wf.exists():
            wf.unlink()
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
    if any(not (ap or "").strip() for ap in album_paths):
        # An empty value is a substring of EVERY src_run_dir → it would drop the whole index
        # (common cause: an unset shell variable expanding to ""). Refuse it.
        sys.exit("dereference: --album-path must be a non-empty path substring "
                 "(an empty value would match every entry).")

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

    # Index-first (atomic), then unlink each dropped entry's deposited widget HTML — same
    # crash-order as remove/prune-versions. Unlinking is what keeps other people's music out of
    # library/widgets/: those copies are invisible to every listing and to gc (which scans run
    # dirs, not the keep tier), so without this they orphan forever.
    idx["entries"] = to_keep
    save_index(root, idx)
    wdir = root / "widgets"
    for e in to_drop:
        w = e.get("widget")
        if w and (wdir / w).exists():
            (wdir / w).unlink()
    print(f"dereference: dropped {len(to_drop)} entr{'y' if len(to_drop) == 1 else 'ies'}; "
          f"{len(to_keep)} left. Run dirs on disk are untouched (use `gc` to reclaim).")
    _regen_catalog()  # rewrite the catalog so purged reference albums leave the visible page


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
    if slug in aliases and aliases[slug] != canon:
        # Re-merging an already-aliased slug used to repoint it silently (a→b became a→c), dropping
        # the earlier merge with no trace. Disclose the replaced target so the change is visible.
        print(f"alias: note — {slug} was aliased to {aliases[slug]!r}; replacing it with {canon!r}.",
              file=sys.stderr)
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
                         help="snapshot curated tiers (library/ + explore/ + config.json) — additive, never destructive")
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
