#!/usr/bin/env python3
"""similarity_columns.py — the PURE geometry behind the two catalog-tail similarity columns
(SPEC §D.10 the reference line, 0.9  +  §F similar-in-your-own-library, 1.0).

This is the logic layer only — no filesystem, no HTML. The catalog/widget render calls these and
paints the result (green/amber/red, D-INV-26). It rides `completeness.py` so *missing* and
*not-comparable* are handled the one honest way (RC-INV-1/5a/5b), never imputed.

Two readings, both on the full-dimensional fingerprint, straight-line / axis-count-fair (D-INV-21,
⟨DECIDE D-17⟩ = straight-line):

  leans_toward(track, directions)  -> Lean | None      (§D.10; relative lean, D-28)
  nearest_own(track_id, library)   -> [Sibling, …]      (§F; library-distribution buckets, D-27)

Closeness is a coarse level — "close" / "mid" / "far" — which the render maps to green / amber / red.
It is NEVER a number on the surface (D-INV-25). Reasons:
  - reference cue = RELATIVE lean: how far the nearest direction stands apart from the track's others
    (an own track sits OUTSIDE the album clusters it reaches toward, so absolute depth read "far" for
    all — D-28). With no directions at all there is nothing to lean toward -> None.
  - own cue = closeness against the library's OWN pairwise distribution (terciles, D-27). Default lists
    close/mid siblings; "far" appears only as a last resort (never empty when a sibling exists, F-INV-1).
"""
from __future__ import annotations
from collections import namedtuple
import statistics as _st

import completeness as C

# Relative-lean thresholds (reference column) — the sketch values Alexander approved by eye 2026-06-25.
SEP_CLOSE = 0.60     # nearest stands clearly apart from the pack -> "close"
SEP_MID = 0.25       # a mild lean -> "mid"; below -> "far" (no real lean)

CLOSE, MID, FAR = "close", "mid", "far"

Lean = namedtuple("Lean", "direction level runner n_shared")      # runner: str | None
Sibling = namedtuple("Sibling", "track level n_shared")


def _lean_level(scored):
    """Relative lean from ascending [(dist, name, n), …]: how far the nearest stands apart from the rest.
    1 direction -> MID (a lean, but nothing to be relative to). ≥2 -> sep = (d2-d1)/(dlast-d1)."""
    if len(scored) == 1:
        return MID
    span = scored[-1][0] - scored[0][0]
    if span <= 1e-9:
        return FAR                                  # all directions equidistant — no real lean
    sep = (scored[1][0] - scored[0][0]) / span
    return CLOSE if sep >= SEP_CLOSE else (MID if sep >= SEP_MID else FAR)


def leans_toward(track, directions, min_shared=C.MIN_SHARED_AXES):
    """§D.10. `directions` = {name: centroid_fingerprint} (build centroids with completeness.centroid).
    Returns a Lean, or None when there is no comparable direction at all ("no direction yet" — never a
    fabricated nearest, D-INV-21). Not-comparable directions are skipped by completeness.nearest (RC-INV-5a)."""
    scored = C.nearest(track, directions, min_shared)        # ascending, axis-count-fair, skips not-comparable
    if not scored:
        return None
    level = _lean_level(scored)
    # runner-up DEFERRED (⟨DECIDE D-24⟩ re-opened, by deed s25): under relative lean a "tied second" means a
    # WEAK single lean (the nearest doesn't stand apart), so "runner = also close" is self-contradictory.
    # v1 ships a single direction; revisit a co-leaders display later. Field kept (always None) for shape.
    return Lean(scored[0][1], level, None, scored[0][2])


def leans_toward_topk(track, directions, k=3, min_shared=C.MIN_SHARED_AXES):
    """§D.10.1. Up to k Lean objects, nearest-first, ONLY CLOSE or MID directions (never FAR).

    Returns [] when no direction qualifies — surface shows 'no close direction yet'.
    Never pads to k with weak/far filler (D-INV-27).

    Level per entry: the gap from d[i] to d[i+1], divided by the FULL span d[-1]−d[0], using
    the same SEP_CLOSE / SEP_MID thresholds as _lean_level (D-INV-26). The last direction in the
    scored list (nothing further to compare against) gets MID, matching the single-direction rule.
    Collection stops at the first FAR: if direction i doesn't stand apart from direction i+1,
    nothing further qualifies either (the gap only gets smaller in relative terms).

    Ties are broken by direction name for deterministic ordering (D-INV-27 / deterministic-order).
    """
    scored = C.nearest(track, directions, min_shared)        # ascending, axis-count-fair
    if not scored:
        return []
    # Deterministic secondary sort by name so equal-distance directions always list in the same order.
    scored = sorted(scored, key=lambda t: (t[0], t[1]))
    n = len(scored)
    total_span = scored[-1][0] - scored[0][0]
    result = []
    for i in range(min(k, n)):
        if i == n - 1:
            level = MID                                      # last remaining: lean, nothing to compare to
        elif total_span <= 1e-9:
            # All directions equidistant (including the two-direction tie case) — no real lean.
            break
        else:
            sep = (scored[i + 1][0] - scored[i][0]) / total_span
            level = CLOSE if sep >= SEP_CLOSE else (MID if sep >= SEP_MID else FAR)
        if level == FAR:
            break                                            # nearest doesn't stand apart → none qualify
        result.append(Lean(scored[i][1], level, None, scored[i][2]))
    return result


def _own_buckets(track_id, library, min_shared):
    """Distances from `track_id` to every OTHER comparable library track, ascending, with the
    library-wide tercile cuts used to bucket them (D-27 basis)."""
    fp = library[track_id]
    dists = []
    for tid, other in library.items():
        if tid == track_id:
            continue                                         # never its own neighbour (F-INV-2)
        d, n = C.per_axis_distance(fp, other, min_shared)
        if d is not None:                                    # drop not-comparable (F-INV-6)
            dists.append((d, tid, n))
    dists.sort(key=lambda t: t[0])
    # tercile cuts over the WHOLE library's pairwise distribution (so buckets mean the same across rows)
    allpairs = sorted(
        d for i, a in enumerate(library) for b in list(library)[i + 1:]
        for d in (C.per_axis_distance(library[a], library[b], min_shared)[0],) if d is not None
    )
    return dists, allpairs


def _own_level(d, allpairs):
    if not allpairs:
        return MID
    p33 = allpairs[max(0, len(allpairs) // 3 - 1)]
    p66 = allpairs[min(len(allpairs) - 1, 2 * len(allpairs) // 3)]
    return CLOSE if d <= p33 else (MID if d <= p66 else FAR)


def nearest_own(track_id, library, min_shared=C.MIN_SHARED_AXES, cap=3):
    """§F. `library` = {track_id: fingerprint}. Returns up to `cap` Siblings, nearest-first.
    Default = the close/mid ones; if NONE qualify, the single nearest is returned tinted FAR as a
    last resort (never empty when another comparable track exists, F-INV-1). Empty only when there is
    no other comparable track at all ("no comparison yet", F-INV-7)."""
    dists, allpairs = _own_buckets(track_id, library, min_shared)
    if not dists:
        return []                                            # no other placeable track (F-INV-7)
    leveled = [Sibling(tid, _own_level(d, allpairs), n) for d, tid, n in dists]
    keep = [s for s in leveled if s.level in (CLOSE, MID)][:cap]
    if not keep:
        nearest = dists[0]
        keep = [Sibling(nearest[1], FAR, nearest[2])]        # last resort, honestly tinted far
    return keep
