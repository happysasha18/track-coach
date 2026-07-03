#!/usr/bin/env python3
"""render_run.py — Full-render helper for a track-coach run directory.

WHY this exists:
  Rendering a widget by hand requires passing 15+ flags to build_widget.py and it's easy
  to silently omit an input — the panel then renders empty and nobody notices until
  Alexander looks at the artifact. This script takes ONE argument (a run-dir path),
  auto-discovers every input that exists in that dir, loudly warns about any user-facing
  input that is ABSENT, and refuses to call the result "full" when the most important
  panels (als, notes, narrative) are missing.

Usage:
  python render_run.py <run-dir>              renders → <run-dir>/analysis_widget_render.html
  python render_run.py <run-dir> --out PATH  renders to an explicit path
  python render_run.py <run-dir> --dry-run   prints what would be passed; no render

WARNING rules:
  Any user-facing panel whose backing data is absent is listed as a WARNING on stdout.
  PARTIAL label: any of als / notes / narrative absent → "PARTIAL render" is printed
  before the output path. A "full" render has all three.

Exit code: 0 even on PARTIAL (so CI pipelines can still test the widget), but the label
is printed so a human or test can detect it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

# ── User-facing panel registry ──────────────────────────────────────────────
# Each entry: (result_key, filename_or_glob, panel_name, counts_for_partial)
# A missing entry → WARNING; if counts_for_partial=True and it's absent → PARTIAL label.
PANEL_REGISTRY = [
    # key               file glob / name             panel name              partial?
    ("core",            "result_core.json",          "track story & vitals", False),
    ("detail",          "result_detail.json",        "vitals detail",        False),
    ("masking",         "result_masking.json",       "stem frequency map",   False),
    ("als",             "result_als.json",           "arrangement & automation panels",   True),
    ("stemmap",         "result_stemmap.json",       "stem ↔ project map",  False),
    ("rhythm",          "result_rhythm.json",        "rhythm & separation",  False),
    ("notes",           None,                        "transcribed notes",    True),   # discovered below
    ("drums",           "result_drums.json",         "drum breakdown",       False),
    ("selfsim",         "result_selfsim.json",       "self-similarity / structure", False),
    ("narrative",       "narrative.md",              "producer's read",      True),
    ("catalog",         "catalog.json",              "cross-version catalog", False),
    ("audio_stems_rel", "stems_web",                 "stem player lanes",    False),
    ("back_href",       None,                        "← Library backlink",  False),   # derived from library
]

# Stems that carry transcribed notes (tried in order; first hit wins).
NOTES_STEMS = ["other", "vocals", "guitar", "bass", "piano"]


def _discover_notes(run_dir: Path) -> Path | None:
    """Return the first result_notes_<stem>.json that exists."""
    for stem in NOTES_STEMS:
        p = run_dir / f"result_notes_{stem}.json"
        if p.exists():
            return p
    return None


def _discover_back_href() -> str | None:
    """Return file:// URI to the library index.html if it exists."""
    try:
        import library as _lib
        idx = (_lib.library_root() / "index.html").resolve()
        if idx.exists():
            return idx.as_uri()
    except Exception:
        pass
    return None


def discover_inputs(run_dir: Path) -> dict:
    """Auto-discover all inputs from a run directory.

    Returns a dict with keys matching PANEL_REGISTRY plus:
      - als_offset_s (float|None) from run_meta.json
      - title (str|None) from run_meta.json
      - analyzed_at (str|None) from run_meta.json
      - mode (str) from run_meta.json (default "full")
      - verdict (str|None) from run_meta.json
      - per_stem_selfsim (dict) auto-discovered
      - per_stem_notes (dict) auto-discovered
      - per_stem_core (dict) auto-discovered
    """
    found: dict = {}

    # run_meta.json — title, mode, als_offset_s, analyzed_at, verdict
    meta_path = run_dir / "run_meta.json"
    meta: dict = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            pass
    found["title"]       = meta.get("title") or meta.get("track")
    found["mode"]        = meta.get("mode", "full")
    found["als_offset_s"] = meta.get("als_offset_s")
    found["analyzed_at"] = meta.get("analyzed_at")
    found["verdict"]     = meta.get("verdict")
    found["src_audio"]   = meta.get("audio")
    found["src_als"]     = meta.get("als")

    # Panel files
    for key, fname, panel_name, _ in PANEL_REGISTRY:
        if key in ("notes", "back_href", "audio_stems_rel"):
            continue  # handled separately
        if fname is None:
            continue
        p = run_dir / fname
        if p.is_dir() or p.is_file():
            found[key] = p

    # stems_web directory
    sw = run_dir / "stems_web"
    if sw.is_dir() and any(sw.iterdir()):
        found["audio_stems_rel"] = "stems_web"
    else:
        # fall back to mix_web for a quick-mode player
        mw = run_dir / "mix_web"
        if mw.is_dir() and any(mw.iterdir()):
            found["audio_mix_rel"] = "mix_web"

    # notes — first stem that has a notes file
    notes_path = _discover_notes(run_dir)
    if notes_path:
        found["notes"] = notes_path

    # back_href — library index
    back = _discover_back_href()
    if back:
        found["back_href"] = back

    # per-stem result files (glob)
    pss = {}
    for p in run_dir.glob("result_selfsim_*.json"):
        key_part = p.stem.replace("result_selfsim_", "")
        try:
            pss[key_part] = json.loads(p.read_text())
        except Exception:
            pass
    found["per_stem_selfsim"] = pss

    psn = {}
    for p in run_dir.glob("result_notes_*.json"):
        key_part = p.stem.replace("result_notes_", "")
        try:
            psn[key_part] = json.loads(p.read_text())
        except Exception:
            pass
    found["per_stem_notes"] = psn

    psc = {}
    for p in run_dir.glob("result_core_*.json"):
        key_part = p.stem.replace("result_core_", "")
        try:
            psc[key_part] = json.loads(p.read_text())
        except Exception:
            pass
    found["per_stem_core"] = psc

    return found


def check_completeness(found: dict) -> tuple[list[str], bool]:
    """Return (warnings, is_partial).

    warnings: human-readable lines for each missing user-facing panel.
    is_partial: True if any of als / notes / narrative is absent.
    """
    warnings = []
    partial_missing = []

    for key, _fname, panel_name, counts_for_partial in PANEL_REGISTRY:
        present = key in found
        if not present:
            warnings.append(f"  WARNING: no {panel_name!r} data in this run dir — that panel will be empty")
            if counts_for_partial:
                partial_missing.append(panel_name)

    is_partial = bool(partial_missing)
    return warnings, is_partial


def render(run_dir: Path, out_path: Path, dry_run: bool = False) -> tuple[str, bool]:
    """Render the widget for a run directory.

    Returns (out_path_str, is_partial).
    Prints WARNINGs to stdout for every missing user-facing input.
    Prints 'PARTIAL render' before the output path if als/notes/narrative are absent.
    """
    import build_widget

    found = discover_inputs(run_dir)
    warnings, is_partial = check_completeness(found)

    print(f"render_run: {run_dir.name}")
    if warnings:
        print("\n".join(warnings))

    if is_partial:
        print("PARTIAL render — als, notes, or narrative absent; some panels will be empty")
    else:
        print("FULL render — all required inputs present")

    if dry_run:
        print("(dry-run: no file written)")
        return str(out_path), is_partial

    # Load JSON inputs
    def _load_json(key):
        p = found.get(key)
        if p is None:
            return None
        try:
            return json.loads(Path(p).read_text())
        except Exception as e:
            print(f"  WARNING: could not load {key} from {p}: {e}")
            return None

    core    = _load_json("core")
    detail  = _load_json("detail")
    masking = _load_json("masking")
    als     = _load_json("als")
    stemmap = _load_json("stemmap")
    rhythm  = _load_json("rhythm")
    notes   = _load_json("notes")
    drums   = _load_json("drums")
    selfsim = _load_json("selfsim")
    catalog = _load_json("catalog")

    if core is None:
        sys.exit("render_run: result_core.json is required but missing — cannot render")
    if detail is None:
        # build_html requires both; use empty detail if truly missing
        detail = {}

    narrative_md = None
    nar_path = found.get("narrative")
    if nar_path and Path(nar_path).exists():
        try:
            narrative_md = Path(nar_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"  WARNING: could not read narrative.md: {e}")

    from datetime import datetime
    meta = {
        "audio":        found.get("src_audio"),
        "als":          found.get("src_als"),
        "analyzed_at":  found.get("analyzed_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "built_at":     datetime.now().strftime("%Y-%m-%d"),
    }

    build_widget.build_html(
        core, detail, masking, als, str(out_path),
        found.get("title"), build_widget.STRINGS,
        als_offset_s=found.get("als_offset_s"),
        stemmap=stemmap,
        rhythm=rhythm,
        notes=notes,
        drums=drums,
        audio_stems_rel=found.get("audio_stems_rel"),
        audio_mix_rel=found.get("audio_mix_rel"),
        narrative_md=narrative_md,
        selfsim=selfsim,
        meta=meta,
        verdict=found.get("verdict"),
        catalog=catalog,
        mode=found.get("mode", "full"),
        back_href=found.get("back_href"),
        per_stem_selfsim=found.get("per_stem_selfsim") or {},
        per_stem_notes=found.get("per_stem_notes") or {},
        per_stem_core=found.get("per_stem_core") or {},
        run_dir=str(run_dir),
    )

    label = "PARTIAL" if is_partial else "FULL"
    print(f"{label}: {out_path}")
    return str(out_path), is_partial


def main():
    p = argparse.ArgumentParser(
        description="Full-render helper — auto-discovers all inputs in a run dir, warns on missing panels")
    p.add_argument("run_dir", help="path to a track-coach run directory")
    p.add_argument("--out", default=None,
                   help="output HTML path (default: <run-dir>/analysis_widget_render.html)")
    p.add_argument("--dry-run", action="store_true",
                   help="print discovered inputs and warnings without writing any file")
    args = p.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        sys.exit(f"render_run: not a directory: {run_dir}")

    out_path = Path(args.out).expanduser().resolve() if args.out else (
        run_dir / "analysis_widget_render.html")

    render(run_dir, out_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
