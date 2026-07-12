#!/usr/bin/env python3
"""
parse_als.py — Extract compositional structure from an Ableton Live .als project.

.als is a gzip-compressed XML file. This script extracts:
  - Tracks: name, type (Audio/MIDI/Group/Return/Master), instrument/device chain
  - Plugins: VST/AU names per track
  - MIDI patterns: note data (pitch, time, duration, velocity) per MIDI track
  - Automations: which parameter, which track, envelope shape, time range
  - Sidechain routing: who sidechains whom
  - Tempo, time signature, markers/locators
  - Send routing

Output: result_als.json

Usage:
  python parse_als.py <project.als> [--out result_als.json]
"""
import sys, argparse, gzip, json
from pathlib import Path
import xml.etree.ElementTree as ET

# ── Time-signature enum decoder ───────────────────────────────────────────────
def _decode_ts_enum(value: int) -> str:
    """Decode Ableton Live's time-signature enum integer → 'num/den'.

    Ableton stores arrangement metre changes as EnumEvent automation on the
    MainTrack's TimeSignature parameter.  The encoding is:
        value = log2(den) * 99 + (num - 1)
    so den_idx = value // 99, num = (value % 99) + 1, den = 2**den_idx.

    Verified against real-project ground truth:
        201 → 4/4,  309 → 13/8,  404 → 9/16.
    """
    den_idx = value // 99
    num = (value % 99) + 1
    den = 1 << den_idx   # 2**den_idx
    return f"{num}/{den}"


# MIDI pitch → note name
NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def midi_to_note(n):
    n = int(n)
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"


def get(el, path, attr="Value", default=None):
    """Safe attribute getter with dotted path."""
    try:
        for tag in path.split("/"):
            el = el.find(tag)
            if el is None:
                return default
        return el.get(attr, default)
    except Exception:
        return default


def parse_device_chain(chain_el):
    """Extract instrument and effect names from a DeviceChain."""
    devices = []
    if chain_el is None:
        return devices
    # instruments: InstrumentBranch
    for branch in chain_el.findall(".//InstrumentBranch"):
        for dev in branch:
            name = dev.get("UserName") or dev.tag
            devices.append({"role": "instrument", "name": name, "type": dev.tag})
    # devices / effects
    for branch in chain_el.findall(".//DeviceBranch"):
        for dev in branch:
            name = dev.get("UserName") or dev.tag
            devices.append({"role": "effect", "name": name, "type": dev.tag})
    # flat device list (simpler projects)
    for chain_child in chain_el:
        if chain_child.tag in ("Devices",):
            for dev in chain_child:
                name = dev.get("UserName") or dev.tag
                role = "instrument" if "Instrument" in dev.tag or dev.tag in (
                    "OriginalSimpler","MultiSampler","InstrumentGroupDevice","Operator",
                    "UltraAnalog","Tension","Collision","Mallet","Sampler","PluginDevice",
                    "AuPluginDevice","VstPluginDevice","Vst3PluginDevice",
                ) else "effect"
                devices.append({"role": role, "name": name, "type": dev.tag})
    return devices


def parse_midi_notes(clip_el):
    """Extract MIDI notes from a MidiClip element.

    In Ableton's format the pitch is stored on the parent <KeyTrack> as
    <MidiKey Value="..."/>, NOT on the MidiNoteEvent. The MidiNoteEvent's
    `NoteId` attribute is an event identifier, not a pitch — using it as the
    pitch (as the old code did) produced garbage note names. We read pitch
    from the KeyTrack and only fall back to a flat scan for clips that have
    no KeyTrack grouping.
    """
    notes = []
    key_tracks = clip_el.findall(".//KeyTrack")
    if key_tracks:
        for kt in key_tracks:
            mk = kt.find("MidiKey")
            pitch = int(mk.get("Value", 60)) if mk is not None else int(kt.get("MidiKey", 60))
            note_name = midi_to_note(pitch)
            for ev in kt.findall(".//MidiNoteEvent"):
                try:
                    notes.append({
                        "time":     round(float(ev.get("Time", 0)), 3),
                        "pitch":    pitch,
                        "note":     note_name,
                        "duration": round(float(ev.get("Duration", 0)), 3),
                        "velocity": int(float(ev.get("Velocity", 100))),
                    })
                except Exception:
                    pass
    else:
        # fallback: flat MidiNoteEvent list with an explicit Pitch attribute
        for ev in clip_el.findall(".//MidiNoteEvent"):
            try:
                pitch = int(ev.get("Pitch", 60))
                notes.append({
                    "time":     round(float(ev.get("Time", 0)), 3),
                    "pitch":    pitch,
                    "note":     midi_to_note(pitch),
                    "duration": round(float(ev.get("Duration", 0)), 3),
                    "velocity": int(float(ev.get("Velocity", 100))),
                })
            except Exception:
                pass
    return sorted(notes, key=lambda n: n["time"])


def parse_automation(auto_el, bpm):
    """Parse an AutomationEnvelope into time-series events (in seconds).

    Live 12 stores envelope breakpoints as <FloatEvent> (also <EnumEvent>/<BoolEvent>),
    NOT <AutomationEvent> — the old code looked for the wrong tag and always found
    zero. The very first point often has a huge negative Time (a sentinel meaning
    "value before the timeline starts"); we keep its value but clamp its time to 0.
    """
    events = []
    if auto_el is None or bpm <= 0:
        return events
    beat_to_s = 60.0 / bpm
    for tag in ("FloatEvent", "EnumEvent", "BoolEvent"):
        for ev in auto_el.findall(f".//{tag}"):
            try:
                beat = float(ev.get("Time", 0))
                raw = ev.get("Value", 0)
                val = 1.0 if raw == "true" else 0.0 if raw == "false" else float(raw)
                if beat < 0:           # sentinel initial value before t=0
                    beat = 0.0
                events.append({"time_s": round(beat * beat_to_s, 2),
                               "beat": round(beat, 3), "value": round(val, 4)})
            except Exception:
                pass
    return sorted(events, key=lambda e: e["time_s"])


def parse_als(als_path: str, out_path: str):
    path = Path(als_path)
    print(f"Parsing: {path.name}")

    # decompress
    try:
        with gzip.open(str(path), 'rb') as f:
            xml_bytes = f.read()
    except Exception as e:
        print(f"ERROR reading .als: {e}")
        sys.exit(1)

    root = ET.fromstring(xml_bytes)
    live_set = root.find("LiveSet") or root

    # Parent map (ElementTree has no parent pointers) — needed to tell arrangement
    # clips from session clips, and to name automation envelopes by their target.
    parent = {c: p for p in root.iter() for c in p}

    def ancestors(el):
        out = []
        while el in parent:
            el = parent[el]
            out.append(el)
        return out

    def in_arrangement(el):
        """True if the clip lives on the arrangement timeline, not a session slot."""
        return not any(a.tag == "ClipSlot" for a in ancestors(el))

    # AutomationTarget Id → (param name, device name). PointeeId on an envelope
    # points at one of these targets; the target's parent tag is the parameter
    # (e.g. "Freq", "Manual"), and the grandparent is usually the device.
    target_name = {}
    for at in root.iter("AutomationTarget"):
        tid = at.get("Id")
        if not tid:
            continue
        par = parent.get(at)
        param = par.tag if par is not None else "param"
        gp = parent.get(par) if par is not None else None
        device = gp.tag if gp is not None else ""
        target_name[tid] = (param, device)

    PARAM_PRETTY = {"Manual": "Volume/Value", "Freq": "Filter freq", "Frequency": "Filter freq",
                    "Cutoff": "Cutoff", "Gain": "Gain", "Pan": "Pan", "Morph": "Morph"}

    # ── Tempo ────────────────────────────────────────────────────────────────
    tempo_el = live_set.find(".//Tempo/Manual")
    bpm = float(tempo_el.get("Value", 120)) if tempo_el is not None else 120.0
    beat_to_s = 60.0 / bpm

    ts_num = get(live_set, "TimeSignature/TimeSignatures/RemoteableTimeSignature/Numerator") or "4"
    ts_den = get(live_set, "TimeSignature/TimeSignatures/RemoteableTimeSignature/Denominator") or "4"

    # ── Time-signature CHANGES across the arrangement ────────────────────────
    # Ableton stores arrangement metre changes as EnumEvent automation on the
    # MainTrack's TimeSignature parameter (PointeeId → AutomationTarget under
    # TimeSignature).  Per-clip RemoteableTimeSignature only holds clip-local
    # metre and does NOT carry arrangement-level changes — those live here.
    # Encoding: _decode_ts_enum(value) above.  Fall back to RemoteableTimeSignature
    # for older projects that have no MainTrack automation envelope.
    time_sig_changes = []
    _main_track = live_set.find(".//MainTrack")
    _ts_envelope = None
    if _main_track is not None:
        _ts_at = _main_track.find(".//TimeSignature/AutomationTarget")
        if _ts_at is not None:
            _ts_auto_id = _ts_at.get("Id")
            for _env in _main_track.findall(".//AutomationEnvelope"):
                _pid_el = _env.find("EnvelopeTarget/PointeeId")
                if _pid_el is not None and _pid_el.get("Value") == _ts_auto_id:
                    _ts_envelope = _env
                    break

    if _ts_envelope is not None:
        # Base (Manual) value → first entry at beat 0
        _ts_manual_el = _main_track.find(".//TimeSignature/Manual")
        _base_val = 201  # default 4/4
        if _ts_manual_el is not None:
            try:
                _base_val = int(_ts_manual_el.get("Value", 201))
            except (ValueError, TypeError):
                pass

        # Collect all non-negative-beat events; later event at same beat wins
        _beat_to_val: dict = {}
        for _ev in _ts_envelope.findall("Automation/Events/EnumEvent"):
            try:
                _b = float(_ev.get("Time", 0))
                _v = int(_ev.get("Value", _base_val))
            except (ValueError, TypeError):
                continue
            if _b < 0:
                continue  # pre-roll default value; skip
            _beat_to_val[round(_b, 3)] = _v

        # Prepend beat-0 entry with Manual value if no event exists there
        _all_beats = sorted(_beat_to_val)
        if not _all_beats or _all_beats[0] > 0:
            _beat_to_val[0.0] = _base_val
            _all_beats = [0.0] + _all_beats

        _last_sig = None
        for _b in _all_beats:
            _sig = _decode_ts_enum(_beat_to_val[_b])
            if _sig != _last_sig:
                time_sig_changes.append({
                    "beat": round(_b, 2),
                    "time_s": round(_b * beat_to_s, 2),
                    "sig": _sig,
                })
                _last_sig = _sig
    else:
        # Fallback for older projects: read per-clip RemoteableTimeSignature markers.
        # These only reflect the clip's local metre, not arrangement-wide changes.
        _ts_seen: set = set()
        for rts in root.iter("RemoteableTimeSignature"):
            n_el, d_el, t_el = rts.find("Numerator"), rts.find("Denominator"), rts.find("Time")
            if n_el is None or d_el is None:
                continue
            try:
                _b = float(t_el.get("Value", 0)) if t_el is not None else 0.0
            except Exception:
                _b = 0.0
            _ts_seen.add((round(max(0.0, _b), 3),
                          f"{n_el.get('Value', '4')}/{d_el.get('Value', '4')}"))
        _last = None
        for _b, _sig in sorted(_ts_seen):
            if _sig != _last:
                time_sig_changes.append({
                    "beat": round(_b, 2),
                    "time_s": round(_b * beat_to_s, 2),
                    "sig": _sig,
                })
                _last = _sig

    # ── Locators / Markers ───────────────────────────────────────────────────
    markers = []
    for loc in live_set.findall(".//Locators/Locators/Locator"):
        name = get(loc, "Name", "Value", "")
        beat = float(loc.find("Time").get("Value", 0)) if loc.find("Time") is not None else 0
        markers.append({"name": name, "beat": round(beat, 2), "time_s": round(beat * beat_to_s, 2)})

    # ── Tracks ───────────────────────────────────────────────────────────────
    tracks = []
    sidechain_pairs = []

    # NOTE: Ableton nests tracks under <Tracks>, but some exports place them
    # directly under LiveSet. Use .// to find them at any depth. Build the list
    # explicitly so the optional MasterTrack never collapses the whole list
    # (the previous `+ [...] if ... else []` had wrong operator precedence and
    # returned 0 tracks whenever there was no MasterTrack — i.e. almost always).
    track_containers = []
    for tag in ("AudioTrack", "MidiTrack", "GroupTrack", "ReturnTrack"):
        for t in live_set.findall(f".//{tag}"):
            if t not in track_containers:
                track_containers.append(t)
    master = live_set.find(".//MasterTrack")
    if master is not None:
        track_containers.append(master)

    for track_el in track_containers:
        if track_el is None:
            continue

        track_type = track_el.tag  # AudioTrack, MidiTrack, GroupTrack, ReturnTrack
        name_el = track_el.find("Name/EffectiveName")
        track_name = name_el.get("Value", track_el.tag) if name_el is not None else track_el.tag

        # colour
        color_el = track_el.find("ColorIndex")
        color_idx = int(color_el.get("Value", -1)) if color_el is not None else -1

        # device chain → instruments + effects
        chain_el = track_el.find("DeviceChain")
        devices = parse_device_chain(chain_el)

        def clip_span(clip_el):
            cs = clip_el.find("CurrentStart")
            ce = clip_el.find("CurrentEnd")
            nm = clip_el.find("Name")
            start = float(cs.get("Value", 0)) * beat_to_s if cs is not None else 0
            end = float(ce.get("Value", 0)) * beat_to_s if ce is not None else None
            name = nm.get("Value", "") if nm is not None else ""
            return name, start, end

        # MIDI clips (arrangement timeline only)
        midi_clips = []
        if track_type == "MidiTrack":
            for clip_el in track_el.findall(".//MidiClip"):
                if not in_arrangement(clip_el):
                    continue
                name, start, end = clip_span(clip_el)
                notes = parse_midi_notes(clip_el)
                midi_clips.append({
                    "name": name, "start_s": round(start, 2),
                    "end_s": round(end, 2) if end else None,
                    "note_count": len(notes),
                    "notes_summary": notes[:20],
                })

        # AUDIO clips (arrangement timeline only) — the audio-track arrangement,
        # which was previously ignored entirely.
        audio_clips = []
        if track_type == "AudioTrack":
            for clip_el in track_el.findall(".//AudioClip"):
                if not in_arrangement(clip_el):
                    continue
                name, start, end = clip_span(clip_el)
                if end and end > start:
                    audio_clips.append({"name": name, "start_s": round(start, 2),
                                        "end_s": round(end, 2)})

        # automations — resolve each envelope's target to a readable param/device name
        automations = []
        for auto_env in track_el.findall(".//AutomationEnvelope"):
            pid_el = auto_env.find("EnvelopeTarget/PointeeId")
            pid = pid_el.get("Value") if pid_el is not None else None
            param, device = target_name.get(pid, ("param", ""))
            param = PARAM_PRETTY.get(param, param)
            events = parse_automation(auto_env, bpm)
            if len(events) < 2:
                continue
            vals = [e["value"] for e in events]
            vmin, vmax = min(vals), max(vals)
            automations.append({
                "param": param, "device": device, "pointee_id": pid,
                "event_count": len(events),
                "time_range_s": [events[0]["time_s"], events[-1]["time_s"]],
                "value_range": [round(vmin, 3), round(vmax, 3)],
                "varies": (vmax - vmin) > 1e-6,
                "events": events,
            })

        # sidechain detection
        for sc in track_el.findall(".//Sidechain/AudioInputDevice"):
            source_id = get(sc, "AudioInputDevice", "Value")
            if source_id:
                sidechain_pairs.append({
                    "target_track": track_name,
                    "source_id": source_id,
                })
        # also check compressor sidechain
        for comp in track_el.findall(".//*[@UserName]"):
            uname = comp.get("UserName","").lower()
            if "sidechain" in uname or "compressor" in uname:
                sc_in = comp.find(".//Sidechain")
                if sc_in is not None:
                    src_name_el = sc_in.find(".//AudioInputDevice/Name")
                    src_name = src_name_el.get("Value","?") if src_name_el is not None else "?"
                    sidechain_pairs.append({
                        "target_track": track_name,
                        "source_track": src_name,
                        "device": comp.get("UserName","?"),
                    })

        tracks.append({
            "name": track_name,
            "type": track_type,
            "color_idx": color_idx,
            "devices": devices,
            "midi_clips": midi_clips,
            "audio_clips": audio_clips,
            "automations": automations,
        })

    # ── Summary ──────────────────────────────────────────────────────────────
    total_automations = sum(len(t["automations"]) for t in tracks)
    total_midi_notes = sum(
        sum(c["note_count"] for c in t["midi_clips"]) for t in tracks
    )
    total_audio_clips = sum(len(t["audio_clips"]) for t in tracks)

    out = {
        "als_file": path.name,
        "bpm": round(bpm, 2),
        "time_signature": f"{ts_num}/{ts_den}",
        "time_sig_changes": time_sig_changes,
        "markers": markers,
        "track_count": len(tracks),
        "total_automations": total_automations,
        "total_midi_notes": total_midi_notes,
        "total_audio_clips": total_audio_clips,
        "sidechain_pairs": sidechain_pairs,
        "tracks": tracks,
    }

    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {out_path}")

    # print summary
    print(f"\n── ALS summary ──")
    print(f"  BPM: {bpm}  Time sig: {ts_num}/{ts_den}"
          + (f"  ({len(time_sig_changes)} metre points: " + " → ".join(c["sig"] for c in time_sig_changes) + ")"
             if len(time_sig_changes) > 1 else "  (constant)"))
    print(f"  Tracks: {len(tracks)}  Automations: {total_automations}  MIDI notes: {total_midi_notes}  Audio clips: {total_audio_clips}")
    print(f"  Markers: {len(markers)}")
    if sidechain_pairs:
        print(f"  Sidechains detected: {len(sidechain_pairs)}")
        for sc in sidechain_pairs[:5]:
            print(f"    {sc.get('source_track','?')} → {sc['target_track']}")
    print()
    for t in tracks:
        devs = ", ".join(d["name"] for d in t["devices"][:3])
        autos = f"  {len(t['automations'])} auto" if t["automations"] else ""
        clips = f"  {len(t['midi_clips'])} clips" if t["midi_clips"] else ""
        print(f"  [{t['type'][:5]}] {t['name']:30s} {devs}{autos}{clips}")


def main():
    p = argparse.ArgumentParser(description="track-coach: parse Ableton .als project")
    p.add_argument("als", help="Path to .als file")
    p.add_argument("--out", default="result_als.json")
    args = p.parse_args()
    parse_als(args.als, args.out)


if __name__ == "__main__":
    main()
