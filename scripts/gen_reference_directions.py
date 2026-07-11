#!/usr/bin/env python3
"""gen_reference_directions.py — one-off generator for data/reference_directions.json.

Reads raw fingerprints from 3 reference albums + 3 own tracks, z-normalizes over all
tracks together (same pipeline as reference_explorer.py), builds per-direction centroids,
and saves them to data/reference_directions.json alongside the normalization parameters
so that catalog.py can z-normalize own-track fingerprints at build time.

Run once (or whenever the reference albums are re-run):
    python3 scripts/gen_reference_directions.py

Output:
    data/reference_directions.json = {
        "DeepChord":       {axis: z_val, ...},
        "Venetian Snares": {...},
        "SCSI-9":          {...},
        "_norm":           {"mu": {...}, "sd": {...}}
    }
"""
from __future__ import annotations
import glob
import json
import math
import os
import sys
from pathlib import Path

# -- resolve siblings from the scripts/ dir
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from fingerprints import fingerprint_from_run_dir, AXES
import completeness as C


H = os.path.expanduser


def _jload(p: str):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


# ---- run selection: prefer sustain-present, then max note-files, then newest ----
# (mirrors reference_explorer.py best_run exactly)
def best_run(track_dir: str) -> str | None:
    best = None
    bk = (-1, -1, "")
    for mk in glob.glob(glob.escape(track_dir) + "/*/result_masking.json"):
        rd = os.path.dirname(mk)
        if os.path.basename(rd) == "latest":
            continue
        m = _jload(mk)
        sus = 1 if (m and "sustain" in m and any(v is not None for v in m["sustain"].values())) else 0
        nf = len(glob.glob(glob.escape(rd) + "/result_notes_*.json"))
        k = (sus, nf, os.path.basename(rd))
        if k > bk:
            bk = k
            best = rd
    return best


def album_runs(root: str) -> dict:
    """Return {track_name: best_run_dir} for every analysed track under root."""
    out = {}
    for td in sorted(glob.glob(glob.escape(root) + "/*")):
        if os.path.isdir(td) and os.path.basename(td) != "index.json":
            rd = best_run(td)
            if rd:
                out[os.path.basename(td)] = rd
    return out


# ---- reference album roots ----
# Relocated 2026-07-12 out of ~/Downloads into the tool's home so the analysis
# output no longer sits inside the download folders (migration-2026-07-12 dump).
DL = H("~/.track-coach/migrated-2026-07-12/Downloads")
DEEP = DL + "/DeepChord - Auratones [2017](Soma Quality Recordings SOMA CD117 UK)/split/reenc/track-coach-output"
CUB  = DL + "/Venetian Snares - Cubist Reggae - (2011)/track-coach-output"
SCSI = DL + "/SCSI-9 - The Line Of Nine (2006)/track-coach-output"

# Display names for each direction (used as JSON keys)
DIR_DISPLAY = {
    "DeepChord": "DeepChord",
    "Venetian":  "Venetian Snares",
    "SCSI-9":    "SCSI-9",
}
DIR_ROOTS = {
    "DeepChord": DEEP,
    "Venetian":  CUB,
    "SCSI-9":    SCSI,
}


def main():
    # ---- collect fingerprints ----
    tracks = []   # (group, raw_fp)

    # Own tracks from library
    lib_idx = _jload(H("~/.track-coach/library/index.json"))
    for e in (lib_idx or {}).get("entries", []):
        src = e.get("src_run_dir", "")
        if not src:
            continue
        fp = fingerprint_from_run_dir(src)
        if fp:
            tracks.append(("HIS", fp))
            print(f"  [HIS]       {e.get('track', '?')[:40]}")
        else:
            print(f"  [HIS SKIP]  {e.get('track', '?')[:40]} — no masking/core JSON")

    # Reference tracks
    for group, root in DIR_ROOTS.items():
        if not os.path.isdir(root):
            print(f"  WARNING: {group} root not found: {root}")
            continue
        runs = album_runs(root)
        for name, rd in runs.items():
            fp = fingerprint_from_run_dir(rd)
            if fp:
                tracks.append((group, fp))
            else:
                print(f"  [SKIP] {group} / {name} — no masking/core JSON")

    print(f"\nLoaded {len(tracks)} fingerprints "
          f"({sum(1 for g, _ in tracks if g=='HIS')} own + "
          f"{sum(1 for g, _ in tracks if g!='HIS')} reference)")

    if len(tracks) < 3:
        print("ERROR: too few tracks to build normalization. Abort.")
        sys.exit(1)

    # ---- z-normalize (same logic as reference_explorer.py) ----
    all_fps = [fp for _, fp in tracks]

    def col(k):
        return [fp[k] for fp in all_fps
                if fp.get(k) is not None
                and not (isinstance(fp.get(k), float) and math.isnan(fp[k]))]

    mu = {k: (sum(col(k)) / len(col(k)) if col(k) else 0.0) for k in AXES}
    sd = {k: ((sum((x - mu[k]) ** 2 for x in col(k)) / len(col(k))) ** 0.5 or 1.0)
          if col(k) else 1.0
          for k in AXES}

    def znorm(fp: dict) -> dict:
        out = {}
        for k in AXES:
            v = fp.get(k)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                out[k] = None           # completeness-safe; JSON can't carry nan
            else:
                out[k] = (v - mu[k]) / sd[k]
        return out

    # ---- compute direction centroids (z-normalized) ----
    # group z-normalized fingerprints by direction
    dir_members: dict[str, list[dict]] = {}
    for group, fp in tracks:
        if group == "HIS":
            continue
        display = DIR_DISPLAY[group]
        dir_members.setdefault(display, []).append(znorm(fp))

    dirs_out = {}
    for display, members in dir_members.items():
        if not members:
            print(f"WARNING: no members for {display}")
            continue
        dirs_out[display] = C.centroid(members)
        print(f"  {display}: centroid from {len(members)} tracks, "
              f"{len([k for k, v in dirs_out[display].items() if v is not None])} measured axes")

    # ---- also report own tracks in z-space (for verification) ----
    print("\nOwn-track z-fingerprints (tempo / pad_sustain / pad_notes for spot-check):")
    lib_idx2 = _jload(H("~/.track-coach/library/index.json"))
    for e in (lib_idx2 or {}).get("entries", []):
        src = e.get("src_run_dir", "")
        fp = fingerprint_from_run_dir(src) if src else None
        if fp:
            zfp = znorm(fp)
            def _fmt(v): return f"{v:.2f}" if isinstance(v, float) else "None"
            print(f"  {e.get('track','?')[:40]:40} "
                  f"tempo_z={_fmt(zfp.get('tempo'))}  "
                  f"pad_sus_z={_fmt(zfp.get('pad_sustain'))}  "
                  f"pad_notes_z={_fmt(zfp.get('pad_notes'))}")

    # ---- save ----
    out_data = {**dirs_out, "_norm": {"mu": mu, "sd": sd}}

    # JSON doesn't support nan; missing axes are already None from znorm(); convert mu/sd floats
    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        if isinstance(obj, float) and math.isnan(obj):
            return None
        return obj

    out_data = clean(out_data)

    out_file = SCRIPTS.parent / "data" / "reference_directions.json"
    out_file.parent.mkdir(exist_ok=True)
    out_file.write_text(json.dumps(out_data, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_file}")


if __name__ == "__main__":
    main()
