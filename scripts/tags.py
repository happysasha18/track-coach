#!/usr/bin/env python3
"""tags.py — heuristic mood/style DRAFT tags from the measured numbers.

These are a *draft*: cheap, deterministic, and grounded in real measurements, meant to seed the
catalog so a track is never tagless. The agent confirms/overrides them (stored explicitly in
run_meta → index.json), per the no-unreliable-as-fact rule — the heuristic never gets the last word.

Model: a valence–arousal map (the standard affective model DJ tools like Cyanite use).
  • arousal  ≈ how energetic — mean energy + tempo.
  • valence  ≈ how positive  — major/minor key + mean brightness.
The (arousal, valence) quadrant picks a small mood vocabulary; tempo + wobble give a style HINT
(genre is the agent's call — we only hint).

Pure stdlib, no deps. `derive_tags(core_dict)` is the entry point; unit-tested in tests/.
"""
from __future__ import annotations
import json
import statistics
import sys
from pathlib import Path


def _mean(seq, default=0.0):
    vals = [x for x in (seq or []) if isinstance(x, (int, float))]
    return statistics.fmean(vals) if vals else default


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def energy_level(core: dict) -> int:
    """A 1–10 energy level (Mixed In Key convention) from the mean energy curve."""
    e = _mean(core.get("energy"), 0.5)
    return int(max(1, min(10, round(e * 9) + 1)))


def _valence(core: dict) -> float:
    """0 = dark/negative, 1 = bright/positive. Minor/major key ± mean brightness."""
    key = str((core.get("vitals") or {}).get("key") or "").lower()
    v = 0.5
    if "minor" in key:
        v -= 0.22
    elif "major" in key:
        v += 0.22
    v += (_mean(core.get("brightness"), 0.5) - 0.5) * 0.5
    return _clamp(v)


def _arousal(core: dict) -> float:
    """0 = calm, 1 = intense. Mean energy (weighted) + tempo position 60→160 BPM."""
    e = _mean(core.get("energy"), 0.5)
    tempo = (core.get("vitals") or {}).get("tempo_bpm") or core.get("tempo") or 120.0
    tnorm = _clamp((tempo - 60.0) / 100.0)
    return _clamp(e * 0.6 + tnorm * 0.4)


def _mood(arousal: float, valence: float) -> list:
    """1–2 mood words from the valence–arousal quadrant (HI/MID/LO bands)."""
    a = "hi" if arousal >= 0.58 else ("lo" if arousal < 0.42 else "mid")
    v = "hi" if valence >= 0.58 else ("lo" if valence < 0.42 else "mid")
    table = {
        ("hi", "lo"): ["dark", "driving"], ("hi", "mid"): ["driving"], ("hi", "hi"): ["energetic", "uplifting"],
        ("mid", "lo"): ["moody"], ("mid", "mid"): ["steady"], ("mid", "hi"): ["warm"],
        ("lo", "lo"): ["melancholic"], ("lo", "mid"): ["mellow"], ("lo", "hi"): ["dreamy"],
    }
    return table[(a, v)]


def _style_hint(core: dict) -> list:
    """Tempo band + wobble → a coarse style HINT (the agent decides the real genre)."""
    tempo = (core.get("vitals") or {}).get("tempo_bpm") or core.get("tempo") or 0.0
    hints = []
    if tempo:
        if tempo <= 100:
            hints.append("downtempo")
        elif tempo <= 128:
            hints.append("house/club")
        elif tempo <= 150:
            hints.append("techno/uptempo")
        else:
            hints.append("fast/dnb-ish")
    if (core.get("wobble_rate_median_hz") or 0) >= 2.0:
        hints.append("bass/wobble")
    return hints


def derive_tags(core: dict) -> dict:
    """Heuristic draft. Returns {energy_level, mood_tags, style_tags, _model}.

    `_model` records the intermediate valence/arousal so the draft is auditable (and so the agent
    can see WHY a mood was picked before overriding it).
    """
    a, v = _arousal(core), _valence(core)
    return {
        "energy_level": energy_level(core),
        "mood_tags": _mood(a, v),
        "style_tags": _style_hint(core),
        "_model": {"arousal": round(a, 3), "valence": round(v, 3)},
    }


if __name__ == "__main__":
    # debug: tags.py result_core.json
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not src or not src.exists():
        sys.exit("usage: tags.py result_core.json")
    print(json.dumps(derive_tags(json.loads(src.read_text())), ensure_ascii=False, indent=2))
