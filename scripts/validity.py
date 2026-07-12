#!/usr/bin/env python3
"""Run validity — a run is complete or it does not exist (SPEC §E, RC-INV-13/13a/13d).

A run is VALID when every signal its mode promises for the material the track actually contains
carries a real value. "Material actually contains" is read from the §A significance gate
(`build_widget.significant_stems`): a stem the gate calls present must have measured its axes; a
stem the gate calls absent (near-silent) contributes a valid "not present" reading, never a gap.

This module owns only the DECISION (valid / not, and which promised-present signals are unmeasured).
Acting on it — refusing to render/deposit, auto-redo, the re-validate pass — lives in the build
orchestrator and the library, which call `validity()` here. Pure read; edits nothing.
"""
from __future__ import annotations

import math

import fingerprints as FP
import completeness as CP

# Axis → the significance-gate source that must be present for the axis to be REQUIRED (RC-INV-13d).
# The five mix axes have no stem source — the mix is always present, so they are always required.
_MIX = {"tempo", "dynamics", "stereo", "density", "energy_build"}
# Stem-sourced axes: the stem whose significance gates the axis. Two collective sources:
#   "_any"  — ≥1 significant stem (brightness reads every stem's bands).
#   "_lead" — ≥1 of guitar/vocals/piano significant (lead_share pools the three). [default]
_STEM_SOURCE = {
    "brightness": "_any",
    "drums_share": "drums",
    "bass_share": "bass", "bass_sustain": "bass",
    "other_share": "other", "pad_sustain": "other", "pad_notes": "other", "pad_bright": "other",
    "lead_share": "_lead",
}
_LEAD_STEMS = ("guitar", "vocals", "piano")


def significant(run_dir) -> set:
    """The stems the §A gate reads as present for this run. Empty when there is no masking (quick)."""
    mk = FP._jload(str(run_dir) + "/result_masking.json")
    if not mk:
        return set()
    import build_widget as BW  # lazy: BW imports fingerprints, so import it here to avoid a cycle
    return set(BW.significant_stems(mk))


def present_axes(run_dir, mode: str = "full") -> set:
    """The axes this run's rung PROMISES whose source part the gate reads as present (RC-INV-13d).

    A gate-absent part's axes are dropped here, BEFORE validity is judged, so a track that genuinely
    lacks a part (a near-silent bass) stays complete instead of being bricked into a redo."""
    promised = FP.PROMISED_BY_MODE.get(mode, FP.PROMISED_BY_MODE["full"])
    if mode == "quick":
        return set(promised)  # quick promises only mix axes, and the mix is always present
    sig = significant(run_dir)
    out = set()
    for ax in promised:
        if ax in _MIX:
            out.add(ax)  # the mix is always present
            continue
        src = _STEM_SOURCE.get(ax)
        if src == "_any":
            if sig:
                out.add(ax)
        elif src == "_lead":
            if sig & set(_LEAD_STEMS):
                out.add(ax)
        elif src in sig:
            out.add(ax)
    return out


def validity(run_dir, mode: str = "full"):
    """RC-INV-13: (is_valid, unmeasured_reads) for this run.

    Invalid iff any promised-and-present signal was left unmeasured (a broken measurement). The
    returned reads are the plain producer names of those unmeasured present signals — what a redo
    must recover. A run whose only gaps are gate-absent parts is valid (unmeasured_reads empty).

    A run with no `result_core.json` carries no analysis to judge (an empty fixture, a run that never
    measured anything) — this gate leaves it alone and reports valid; that is a different failure,
    not an incomplete measurement."""
    if not FP._jload(str(run_dir) + "/result_core.json"):
        return True, []
    present = present_axes(run_dir, mode)
    measured = FP.measured_axes(run_dir)
    unmeasured = present - measured
    reads = [FP.AXIS_READS.get(a, a.replace("_", " ")) for a in sorted(unmeasured)]
    return (len(unmeasured) == 0), reads


def is_valid(run_dir, mode: str = "full") -> bool:
    return validity(run_dir, mode)[0]
