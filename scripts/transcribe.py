#!/usr/bin/env python3
"""
transcribe.py — Part D (notes): audio → MIDI notes for a melodic/bass stem.

Uses Spotify's basic-pitch to pull actual pitched notes out of a separated stem.
This is the trustworthy version of "show me the notes": the notes are heard in the
audio, not read from a project's loop source. Use it on stems that carry pitch
(bass, lead, the melodic "other"). Pointless on drums.

Output is a compact piano-roll the widget can draw: per note {t, dur, pitch, name}.

Usage:
  python transcribe.py --stem stems_6s/other.wav [--out result_notes.json]
                       [--label other] [--min-dur 0.06]
"""
import sys, argparse, json
from pathlib import Path

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_name(p):
    return f"{NOTE_NAMES[p % 12]}{p // 12 - 1}"


def main():
    ap = argparse.ArgumentParser(description="track-coach: transcribe a stem to notes (Part D)")
    ap.add_argument("--stem", required=True)
    ap.add_argument("--label", default=None, help="display label (default: stem filename)")
    ap.add_argument("--min-dur", type=float, default=0.05, help="drop notes shorter than this (s)")
    ap.add_argument("--out", default="result_notes.json")
    args = ap.parse_args()

    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    label = args.label or Path(args.stem).stem
    print(f"Transcribing {args.stem} (label: {label}) …")
    _, _, note_events = predict(args.stem, model_or_model_path=ICASSP_2022_MODEL_PATH)

    notes = []
    pitches = []
    for ev in note_events:
        start, end, pitch = ev[0], ev[1], int(ev[2])
        amp = float(ev[3]) if len(ev) > 3 else 1.0
        if end - start < args.min_dur:
            continue
        notes.append({"t": round(float(start), 3), "dur": round(float(end - start), 3),
                      "pitch": pitch, "name": midi_name(pitch), "amp": round(amp, 3)})
        pitches.append(pitch)
    notes.sort(key=lambda n: n["t"])

    out = {
        "label": label,
        "n_notes": len(notes),
        "pitch_min": min(pitches) if pitches else None,
        "pitch_max": max(pitches) if pitches else None,
        "notes": notes,
    }
    out_path = args.out
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"Saved: {out_path}  ({len(notes)} notes, "
          f"range {midi_name(out['pitch_min']) if pitches else '—'}–{midi_name(out['pitch_max']) if pitches else '—'})")


if __name__ == "__main__":
    main()
