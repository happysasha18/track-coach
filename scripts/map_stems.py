#!/usr/bin/env python3
"""
map_stems.py — Part B: connect Demucs stems to the real project tracks.

Demucs guesses 4–6 stems trained on live bands. The project (.als) is the ground
truth. This script answers: which real project tracks does each separated stem
actually correspond to? It does that WITHOUT trusting names — purely by how the
loudness of a stem rises and falls over time vs. when each project track plays.

Method:
  • For each Demucs stem: RMS loudness envelope, binned to WIN-second windows.
  • For each project track: an "activity" envelope on the same grid, from its MIDI
    clips (note density per window), aligned to the audio via --als-offset-s.
  • Tracks are grouped into instrument families (kick/bass/drums/hats/chord/lead).
  • Pearson correlation between each stem envelope and each family/track envelope.
    High correlation ⇒ that stem is carrying that part. Low everywhere ⇒ the stem
    is leakage or the part wasn't isolated.

Also emits:
  • model_recommendation — which Demucs model fits this project's instrumentation.
  • export_suggestion — when a project is present, exporting Ableton group stems
    beats any blind separation.

Offset is NEVER guessed; pass --als-offset-s (project seconds where render starts).

Usage:
  python map_stems.py --stems-dir stems_6s --als result_als.json \
      --als-offset-s 432.68 [--out result_stemmap.json]
"""
import sys, argparse, json
from pathlib import Path
import numpy as np
import librosa
sys.path.insert(0, str(Path(__file__).parent))
from _common import make_bins, bin_series, frames_to_time, norm, write_json, WIN, HOP, SR

# Same families/colours as the widget, kept in sync intentionally.
FAMILIES = [
    ("kick",  ("kick", "808", "core kit")),
    ("bass",  ("bass", "rumble", "sub", "reese", "wobble")),
    ("drums", ("drum", "snr", "snare", "amen", "tom", "perc", "clap")),
    ("hats",  ("hh", "hat", "hi-hat", "shaker", "cymbal", "ride")),
    ("chord", ("chord", "chrd", "tone", "pad", "key")),
    ("lead",  ("lead", "operator", "granulator", "drift", "instrument", "rack",
               "arp", "pluck", "vox", "vocal")),
]


def family_of(name):
    n = name.lower()
    for fam, keys in FAMILIES:
        if any(k in n for k in keys):
            return fam
    return "other"


def stem_envelope(path, nb):
    """RMS loudness of a stem, binned to nb WIN-second windows (linear, 0..1 norm),
    plus the stem's mean loudness in dB (so we can tell 'has signal' from 'silent')."""
    y, _ = librosa.load(path, sr=SR, mono=True)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    t = frames_to_time(rms)
    env = bin_series(t, rms, nb)
    # mean POWER → dB: physically honest 'how much is in this stem at all'.
    mean_pow = float(np.mean(np.maximum(rms, 0.0) ** 2)) if len(rms) else 0.0
    energy_db = 10.0 * np.log10(max(mean_pow, 1e-12))
    return env, energy_db


def track_activity(track, offset, dur, nb):
    """Per-window activity envelope for one project track, in audio time.
    Uses BOTH MIDI clips (note density) and AUDIO clips (presence) — audio-clip
    tracks were previously invisible, which biased the family rollup badly."""
    env = np.zeros(nb)
    for c in track.get("midi_clips", []):
        a, b = c["start_s"] - offset, c["end_s"] - offset
        if b <= 0 or a >= dur:
            continue
        a, b = max(0.0, a), min(dur, b)
        dens = c.get("note_count", 0) / max(0.2, b - a)  # notes per second
        i0, i1 = int(a // WIN), int(min(nb - 1, b // WIN))
        for i in range(i0, i1 + 1):
            env[i] += dens
    for c in track.get("audio_clips", []):
        a, b = c["start_s"] - offset, c["end_s"] - offset
        if b <= 0 or a >= dur:
            continue
        a, b = max(0.0, a), min(dur, b)
        i0, i1 = int(a // WIN), int(min(nb - 1, b // WIN))
        for i in range(i0, i1 + 1):     # audio clip = "this part is sounding" (presence)
            env[i] += 1.0
    return env


def pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if np.std(a) < 1e-9 or np.std(b) < 1e-9:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def verdict(best_fam, best_r, second_r, rel_db, best_track=None):
    """Honest verdict. 'Lost/empty' is decided by ENERGY (is there signal at all?),
    NOT by correlation. Low correlation on a stem that clearly has audio just means
    we can't line its timing up with a single project part — common in electronic
    music where everything plays in the same sections. We never claim a family
    unless the match is genuinely strong AND clearly ahead of the runner-up."""
    # 1) Is there actually signal in this stem?  (energy relative to the loudest stem)
    # Conservative: broadband RMS under-reports narrowband/sub stems, so only the truly
    # negligible (<-28 dB ≈ 0.15% power) is called empty. A quiet-but-real bass is NOT lost.
    if rel_db < -28:
        return "empty", None, ("This stem is near-silent — Demucs put almost nothing here "
                               f"({rel_db:+.0f} dB vs the loudest stem).")
    # 2) Strong, unambiguous match to one family.
    if best_r >= 0.40 and (best_r - second_r) >= 0.12:
        return "clear", best_fam, f"Tracks the “{best_fam}” family closely ({best_r:+.2f})."
    # 3) Follows several parts at once (overlapping arrangement).
    if best_r >= 0.30:
        return "mixed", None, (f"Has clear signal, but its timing follows several project parts at once "
                               f"(top {best_r:+.2f}). Parts overlap too much to pin one down.")
    # 4) Has audio, but no clean timing match — NOT 'lost'.
    hint = f" Closest single track: “{best_track}”." if best_track else ""
    return "nomatch", None, ("Has clear signal, but its timing doesn't line up cleanly with any one "
                             "project part (best {0:+.2f}).{1}".format(best_r, hint))


def recommend_model(families_present):
    has = lambda f: f in families_present
    melodic = sum(1 for f in ("chord", "lead") if has(f))
    if melodic >= 1:
        return ("htdemucs_6s",
                "Project has melodic/harmonic parts (chords, leads). htdemucs_6s adds "
                "guitar and piano stems, so more of that material lands in its own stem "
                "instead of being dumped into 'other'.")
    return ("htdemucs",
            "Project is mostly drums + bass. The standard 4-stem htdemucs is enough; "
            "the extra 6s stems would stay near-empty.")


def main():
    p = argparse.ArgumentParser(description="track-coach: map Demucs stems to project tracks (Part B)")
    p.add_argument("--stems-dir", required=True, help="directory with separated *.wav stems")
    p.add_argument("--als", required=True)
    p.add_argument("--als-offset-s", type=float, required=True,
                   help="project seconds where the render starts (usually a locator). NEVER guessed.")
    p.add_argument("--out", default="result_stemmap.json")
    args = p.parse_args()

    als = json.loads(Path(args.als).read_text())
    offset = args.als_offset_s

    stem_paths = sorted(Path(args.stems_dir).glob("*.wav"))
    if not stem_paths:
        print(f"ERROR: no .wav stems in {args.stems_dir}")
        sys.exit(1)

    # Duration from the longest stem; build the shared time grid.
    dur = 0.0
    for sp in stem_paths:
        dur = max(dur, librosa.get_duration(path=str(sp)))
    nb, tb = make_bins(dur)
    print(f"Grid: {nb} windows × {WIN}s  (dur {dur:.1f}s)")

    # Stem envelopes + per-stem energy (to tell 'silent' from 'present').
    stem_env = {}
    stem_db = {}
    for sp in stem_paths:
        print(f"  envelope: {sp.name}")
        env, edb = stem_envelope(str(sp), nb)
        stem_env[sp.stem] = env
        stem_db[sp.stem] = edb
    max_db = max(stem_db.values()) if stem_db else 0.0

    # Project track + family activity envelopes (audio time).
    track_env = {}
    fam_members = {}
    for t in als.get("tracks", []):
        env = track_activity(t, offset, dur, nb)
        if env.sum() <= 0:
            continue
        nm = t["name"]
        track_env[nm] = env
        fam_members.setdefault(family_of(nm), []).append(nm)
    fam_env = {f: np.sum([track_env[m] for m in members], axis=0)
               for f, members in fam_members.items()}
    families_present = set(fam_env.keys())

    # Correlate each stem against families (primary) and tracks (detail).
    stems_out = {}
    for sname, senv in stem_env.items():
        fam_scores = sorted(((f, round(pearson(senv, e), 3)) for f, e in fam_env.items()),
                            key=lambda x: -x[1])
        trk_scores = sorted(((nm, round(pearson(senv, e), 3)) for nm, e in track_env.items()),
                            key=lambda x: -x[1])[:4]
        best_r = fam_scores[0][1] if fam_scores else 0.0
        second_r = fam_scores[1][1] if len(fam_scores) > 1 else 0.0
        best_fam = fam_scores[0][0] if fam_scores else None
        best_track = trk_scores[0][0] if trk_scores else None
        rel_db = round(stem_db.get(sname, -120) - max_db, 1)
        vcode, claim_fam, vtext = verdict(best_fam, best_r, second_r, rel_db, best_track)
        stems_out[sname] = {
            "env": [round(float(x), 4) for x in norm(senv)],
            "family_matches": [{"family": f, "r": r} for f, r in fam_scores],
            "track_matches": [{"track": nm, "r": r} for nm, r in trk_scores],
            "energy_rel_db": rel_db,           # how loud vs the loudest stem (0 = loudest)
            # Only claim a family when the match is genuinely strong + unambiguous.
            "best_family": claim_fam,
            "best_r": best_r,
            "verdict": vcode, "verdict_text": vtext,
        }

    model, model_why = recommend_model(families_present)
    out = {
        "offset_s": offset, "duration_s": round(dur, 1), "bins": [round(float(x), 1) for x in tb],
        "families_present": sorted(families_present),
        "family_members": fam_members,
        "stems": stems_out,
        "model_recommendation": model, "model_why": model_why,
        "export_suggestion":
            "A project is loaded, so the most reliable stems aren't separated at all: in "
            "Ableton, solo each group (Grp Bass, Grp Kick, Grp Snr, …) and export it. Those "
            "group bounces are perfect by construction — use them instead of Demucs guesses "
            "for any per-part EQ or sidechain decisions.",
    }
    write_json(out, args.out)

    print("\n── Stem ↔ project mapping ──")
    for s, d in stems_out.items():
        fm = ", ".join(f"{m['family']} {m['r']:+.2f}" for m in d["family_matches"][:3])
        print(f"  {s:8s} → {d['best_family'] or '—':6s} ({d['verdict']})  [{fm}]")
    print(f"\nModel: {model} — {model_why}")


if __name__ == "__main__":
    main()
