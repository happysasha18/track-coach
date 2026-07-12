#!/usr/bin/env python3
"""
eval_rec_specificity.py — measure NEXT_STEPS #2's hypothesis:
    "per-stem-derived recs are more INDIVIDUAL than the old fixed template."

For each track run dir that has the per-stem data (result_masking.json + result_rhythm.json +
result_selfsim_<stem>.json), build the recommendations TWICE on the SAME analysis:
  • TEMPLATE path  — character=None, repetition=None  (the old generic catalogue)
  • PER-STEM path  — character + repetition computed   (G16/G19/G20 named cards)
…then count specificity signals and compare. This is a measurement, not a behaviour change — its
"test" is the printed numbers (verified by deed on real tracks). Pure-python (no numpy): reuses the
numpy-free build_widget. Run: `python3 scripts/eval_rec_specificity.py [extra_run_dir …]`.

A card is counted as:
  • NAMED   — its text names a measured part label (bass/drums/mid/high/kick/lead/melody/chord/pad…)
  • TIMED   — it is anchored to a timeline moment (rec[5] is not None)
  • FREQ    — it names a precise frequency ("≈… Hz"/"≈… kHz") (the G19 contribution)
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_widget as bw

PART_WORDS = ("bass", "drums", "kick", "snare", "hat", "mid", "high", "low", "lead",
              "melody", "chord", "pad", "air")
FREQ_RE = re.compile(r"≈\s*[\d.]+\s*k?Hz")


def _discover(run):
    m = os.path.join(run, "result_masking.json")
    r = os.path.join(run, "result_rhythm.json")
    if not (os.path.isfile(m) and os.path.isfile(r)):
        return None
    # per-stem self-sim is OPTIONAL: only the G20 development card needs it (a recent pipeline step, so
    # older deposited runs lack it). The named/timed/freq metrics (G16/G19) need only masking + rhythm.
    pss = {}
    for f in glob.glob(os.path.join(run, "result_selfsim_*.json")):
        st = os.path.basename(f)[len("result_selfsim_"):-len(".json")]
        pss[st] = json.load(open(f))
    return {"masking": json.load(open(m)), "rhythm": json.load(open(r)), "pss": pss,
            "stemmap": _maybe(os.path.join(run, "result_stemmap.json"))}


def _maybe(p):
    return json.load(open(p)) if os.path.isfile(p) else None


def _metrics(recs):
    text = lambda r: (r[1] + " " + r[2] + " " + r[3] + " " + r[4]).lower()
    named = sum(1 for r in recs if any(w in text(r) for w in PART_WORDS))
    timed = sum(1 for r in recs if r[5] is not None)
    freq = sum(1 for r in recs if FREQ_RE.search(r[1] + r[2] + r[3] + r[4]))
    return {"total": len(recs), "named": named, "timed": timed, "freq": freq}


def _eval(name, d):
    m, rhythm, pss = d["masking"], d["rhythm"], d["pss"]
    core = {"duration_s": m.get("duration_s", 0.0),
            "time_bins": m.get("time_bins", []), "section_bounds_s": []}
    leak = bw.leakage_caveats(m, rhythm)
    character = bw.stem_character(m, rhythm, leak, None)
    repetition = bw.stem_repetition(pss, m)
    tmpl = bw.build_recommendations(core, {}, m, bw.STRINGS, stemmap=d["stemmap"], rhythm=rhythm)
    perstem = bw.build_recommendations(core, {}, m, bw.STRINGS, stemmap=d["stemmap"],
                                       rhythm=rhythm, character=character, repetition=repetition)
    return name, _metrics(tmpl), _metrics(perstem)


def _library_runs():
    """(label, run_dir) for the newest run of every track in the library output root that exists on disk.
    Product-fit: works on whatever the user has analysed, binds to no one's machine."""
    proj = Path.home() / ".track-coach" / "projects"
    out = []
    if not proj.is_dir():
        return out
    for td in sorted(proj.iterdir()):
        if not td.is_dir():
            continue
        rd = [p for p in td.iterdir() if p.is_dir() and p.name != "latest"]
        if rd:
            out.append((td.name, str(max(rd, key=lambda p: p.stat().st_mtime))))
    return out


def main(argv):
    # Explicit run dirs win; with none, scan the library output root for the newest run per track that
    # carries per-stem data. No personal defaults — this eval binds to no one's machine.
    runs = [(Path(a).name, a) for a in argv] if argv else _library_runs()

    rows = []
    for label, run in runs:
        d = _discover(run)
        if not d:
            continue
        rows.append(_eval(label, d))

    if not rows:
        print("no run dirs with per-stem data found")
        return 1

    print(f"\n{'track':28s} | {'path':8s} | total  named  timed  freq")
    print("-" * 70)
    for name, t, p in rows:
        short = name[:28]
        print(f"{short:28s} | {'template':8s} | {t['total']:5d}  {t['named']:5d}  {t['timed']:5d}  {t['freq']:5d}")
        print(f"{'':28s} | {'per-stem':8s} | {p['total']:5d}  {p['named']:5d}  {p['timed']:5d}  {p['freq']:5d}")
        print("-" * 70)

    # aggregate
    agg = lambda key, idx: sum(r[idx][key] for r in rows)
    print("\nAGGREGATE (all tracks):")
    for key in ("total", "named", "timed", "freq"):
        print(f"  {key:6s}: template {agg(key,1):3d}  →  per-stem {agg(key,2):3d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
