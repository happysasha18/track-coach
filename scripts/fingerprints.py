#!/usr/bin/env python3
"""fingerprints.py — extract a 14-axis fingerprint dict from a run directory.

Axis extraction is lifted verbatim from ~/.track-coach/explore/reference_explorer.py
so that the values match the reference space used when building reference_directions.json.

Public API:
  fingerprint_from_run_dir(run_dir) -> dict | None
      Returns a 14-axis dict {axis: float}, or None when the run lacks the required files.
      Missing axes (nan / None) are carried through — completeness.py handles them correctly.

  normalize_fingerprint(fp, norm) -> dict
      Apply z-normalization to a raw fingerprint using norm = {"mu": {...}, "sd": {...}}.
      Missing axes (nan / None) stay missing; never imputed.

Pure filesystem reads only — no network, no heavy deps.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

# The 14 producer-facing axes (same order and keys as reference_explorer.py AXES).
AXES = [
    "tempo", "dynamics", "stereo", "brightness", "density", "energy_build",
    "drums_share", "bass_share", "other_share", "lead_share",
    "bass_sustain", "pad_sustain", "pad_notes", "pad_bright",
]

# RC-INV-12 / RC-INV-7a: which axes each rung PROMISES, derived from AXES (the one axis authority)
# so the completeness line can never disagree with the ladder. quick is the stemless run — it carries
# only the mix-level axes a run measures without Demucs stems; full promises every axis. The five
# mix-level axes come straight from result_core.json (no masking needed), so a quick run reports them.
MIX_AXES = ("tempo", "dynamics", "stereo", "density", "energy_build")
PROMISED_BY_MODE = {"quick": set(MIX_AXES), "full": set(AXES)}

# Axis key → the plain producer read it stands for, for the "skipped: …" tail of the completeness line.
AXIS_READS = {
    "tempo": "tempo", "dynamics": "dynamics", "stereo": "stereo width",
    "brightness": "brightness", "density": "density", "energy_build": "energy arc",
    "drums_share": "drum balance", "bass_share": "bass balance",
    "other_share": "harmonic balance", "lead_share": "lead balance",
    "bass_sustain": "bass sustain", "pad_sustain": "pad sustain",
    "pad_notes": "harmonic density", "pad_bright": "harmonic brightness",
}

# Frequency-band names and representative Hz, used for brightness calculation.
_BANDS = ["sub", "low", "low_mid", "mid", "hi_mid", "air"]
_BAND_HZ = {"sub": 40, "low": 110, "low_mid": 300, "mid": 800, "hi_mid": 3000, "air": 9000}


def _jload(p: str) -> dict | None:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def _stem_energy(brdb: dict, stem: str) -> float:
    """Total linear energy for one stem across all bands (mirrors reference_explorer stem_energy)."""
    bd = brdb.get(stem, {})
    total = 0.0
    n = 0
    for b in _BANDS:
        for v in bd.get(b, []):
            if v is not None and v > -90:
                total += 10 ** (v / 10)
                n += 1
    return total / n if n else 0.0


def _band_brightness(brdb: dict, stems: list) -> float:
    """Energy-weighted mean frequency (log10 Hz) across all stems
    (mirrors reference_explorer band_brightness)."""
    num = den = 0.0
    for s in stems:
        bd = brdb.get(s, {})
        for b in _BANDS:
            e = sum(10 ** (v / 10) for v in bd.get(b, []) if v is not None and v > -90)
            num += e * _BAND_HZ[b]
            den += e
    return math.log10(num / den) if den else float("nan")


def _notes_n(run_dir: str, stem: str) -> int:
    """Note count from result_notes_{stem}.json (mirrors reference_explorer notes_n)."""
    d = _jload(run_dir + f"/result_notes_{stem}.json")
    return (d or {}).get("n_notes", 0)


def _centroid_log(mk: dict, stem: str) -> float:
    """log10 of the spectral centroid for a stem (mirrors reference_explorer centroid_log)."""
    c = (mk.get("spectral_centroid") or {}).get(stem)
    return math.log10(c) if (c and c > 0) else float("nan")


def fingerprint_from_run_dir(run_dir) -> dict | None:
    """Return a 14-axis raw fingerprint dict for this run directory, or None if data is missing.

    The axis values and extraction logic are identical to reference_explorer.py's facets()
    function so that fingerprints are comparable with reference_directions.json centroids
    (which were built from the same extraction + z-normalization pipeline).

    Handles both string paths and Path objects. Returns None when result_masking.json or
    result_core.json cannot be read (e.g. quick runs, missing dirs, non-existent paths).
    """
    rd = str(run_dir)
    mk = _jload(rd + "/result_masking.json")
    core = _jload(rd + "/result_core.json")
    if not mk or not core:
        return None

    brdb = mk.get("band_rms_db", {})
    stems = mk.get("stems_analysed", [])
    su = mk.get("sustain", {})

    en = {s: _stem_energy(brdb, s) for s in stems}
    tot = sum(en.values()) or 1.0

    v = core.get("vitals", {})
    dur = v.get("duration_s") or mk.get("duration_s") or 1.0
    lead_e = sum(en.get(s, 0.0) for s in ("guitar", "vocals", "piano"))

    return {
        "tempo":       v.get("tempo_bpm") or 0.0,
        "dynamics":    v.get("dynamic_range_db", 0.0),
        "stereo":      core.get("stereo_width_mean", v.get("stereo_width", 0.0)) or 0.0,
        "brightness":  _band_brightness(brdb, stems),
        "density":     core.get("density_lv", 0.0) or 0.0,
        "energy_build": core.get("energy_trend", 0.0),
        "drums_share": 100.0 * en.get("drums", 0.0) / tot,
        "bass_share":  100.0 * en.get("bass", 0.0) / tot,
        "other_share": 100.0 * en.get("other", 0.0) / tot,
        "lead_share":  100.0 * lead_e / tot,
        "bass_sustain": su.get("bass", float("nan")),
        "pad_sustain":  su.get("other", float("nan")),
        "pad_notes":    _notes_n(rd, "other") / dur,
        "pad_bright":   _centroid_log(mk, "other"),
    }


def measured_axes(run_dir) -> set:
    """Axis names carrying a real measurement for this run — the single manifest RC-INV-8 shares.

    On a full run (core + masking) this is the full fingerprint's manifest. On a quick run there is
    no fingerprint (no masking), so only the mix-level axes are measurable; they are read straight
    from result_core.json. Returns an empty set when the run has no readable core."""
    import completeness as CP  # lazy: same scripts/ dir, avoids a load-order cycle
    fp = fingerprint_from_run_dir(run_dir)
    if fp is not None:
        return CP.manifest(fp)
    core = _jload(str(run_dir) + "/result_core.json")
    if not core:
        return set()
    v = core.get("vitals", {})
    mix = {
        "tempo": v.get("tempo_bpm"),
        "dynamics": v.get("dynamic_range_db"),
        "stereo": core.get("stereo_width_mean", v.get("stereo_width")),
        "density": core.get("density_lv"),
        "energy_build": core.get("energy_trend"),
    }
    return {k for k, val in mix.items() if not CP.is_missing(val)}


def run_completeness(run_dir, mode: str = "full"):
    """RC-INV-12: (n_measured, n_promised, skipped_reads) for this run's rung.

    ``skipped_reads`` are the plain read names (AXIS_READS) of promised axes that came back missing —
    the missing-within-a-promised-surface case (RC-INV-7). Axes a rung never promised (missing-by-mode)
    are not in ``promised``, so they never count as skipped."""
    import completeness as CP  # lazy
    promised = PROMISED_BY_MODE.get(mode, PROMISED_BY_MODE["full"])
    present = measured_axes(run_dir) & promised
    skipped = CP.incomplete_axes(present, promised)
    reads = [AXIS_READS.get(a, a.replace("_", " ")) for a in sorted(skipped)]
    return len(present), len(promised), reads


def normalize_fingerprint(fp: dict, norm: dict) -> dict:
    """Z-normalize a raw fingerprint using norm = {"mu": {...}, "sd": {...}}.

    Missing axes (None / nan) stay missing — completeness.is_missing() handles them.
    A missing sd defaults to 1.0 so the normalised value equals (v - mu).
    """
    mu = norm.get("mu", {})
    sd = norm.get("sd", {})
    out = {}
    for k, v in fp.items():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out[k] = float("nan")
        else:
            s = sd.get(k, 1.0) or 1.0
            out[k] = (v - mu.get(k, 0.0)) / s
    return out
