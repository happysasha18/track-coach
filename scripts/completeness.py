#!/usr/bin/env python3
"""§E — run completeness & missing measurements (canonical, surface-agnostic).

One implementation of "what to do when a run is partial", shared by the coach (§A/§B), the catalog,
and the reference layer (§D), so a not-measured signal is never read or compared as a real zero.
Derived from docs/SPEC.md §E (RC-INV-1…12). The motivating bug: a partial run transcribed only the
`other` stem, so bass/lead note-counts came back 0 — meaning "not measured", not "no notes".

Pure functions, no third-party deps (matches the skill's style). A measurement is MISSING when it is
None or NaN; a measured 0.0 is NOT missing.
"""
import math

MISSING = None  # the value a fingerprint carries for an axis that wasn't measured (RC-INV-1)

# significance states (§A + RC-INV-11) — three, not two
SIGNIFICANT   = "significant"
INSIGNIFICANT = "insignificant"
UNKNOWN       = "unknown"          # gate inputs not measured — NEVER collapse into insignificant


def is_missing(v):
    """RC-INV-1: missing (None / NaN) is distinct from a measured zero."""
    return v is None or (isinstance(v, float) and math.isnan(v))


def manifest(fp):
    """RC-INV-2: the set of axes a fingerprint actually measured (its completeness manifest)."""
    return {k for k, v in fp.items() if not is_missing(v)}


def shared_axes(a, b):
    """RC-INV-5: axes present on BOTH sides — the only axes a pair may be compared on."""
    return manifest(a) & manifest(b)


def per_axis_distance(a, b, min_shared=1):
    """RC-INV-3/5/5a/5b: distance over shared axes ONLY, **per axis** (RMS) so it is comparable across
    pairs with different shared-axis counts. A missing axis is dropped — never a 0-gap or a max-gap.

    Returns (distance_per_axis, n_shared). distance is None when fewer than `min_shared` axes are
    shared (RC-INV-5a: "not comparable", never a fake 0)."""
    sh = shared_axes(a, b)
    if len(sh) < min_shared:
        return None, len(sh)                       # not comparable — caller shows "слишком мало общих"
    ss = sum((a[k] - b[k]) ** 2 for k in sh)
    return math.sqrt(ss / len(sh)), len(sh)        # per-axis RMS == axis-count-fair


def centroid(members):
    """RC-INV-6: per-axis mean over ONLY the members that have the axis; an axis no member has is
    absent (MISSING), never dragged to 0 by members that lack it."""
    out = {}
    axes = set()
    for m in members:
        axes |= manifest(m)
    for k in axes:
        vals = [m[k] for m in members if not is_missing(m.get(k))]
        out[k] = (sum(vals) / len(vals)) if vals else MISSING
    return out


def nearest(track, directions, min_shared=1):
    """RC-INV-5b: rank directions by axis-count-fair (per-axis) distance; a not-comparable direction is
    skipped, never scored 0. `directions` = {name: centroid_fingerprint}.
    Returns [(distance_per_axis, name, n_shared), …] ascending (nearest first)."""
    scored = []
    for name, cen in directions.items():
        d, n = per_axis_distance(track, cen, min_shared)
        if d is not None:
            scored.append((d, name, n))
    scored.sort(key=lambda t: t[0])
    return scored


def significance(loud_level, floor_db=-55.0):
    """RC-INV-11 (+ §A gate): a stem whose gate input wasn't measured is UNKNOWN, not INSIGNIFICANT.
    `loud_level` = 85th-pct broadband dB, or MISSING when the run didn't measure it."""
    if is_missing(loud_level):
        return UNKNOWN
    return SIGNIFICANT if loud_level >= floor_db else INSIGNIFICANT
