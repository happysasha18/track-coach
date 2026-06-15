#!/usr/bin/env python3
"""
build_widget.py — Generate a complete, self-contained HTML analysis widget.

Language is NOT special-cased per locale. The code ships ONE canonical text set
(English) as templates. Any other language is supported identically by passing a
translated strings file:

  python build_widget.py --dump-strings > strings.json   # get the schema
  # translate the values in strings.json into the target language, then:
  python build_widget.py ... --strings strings.json

Partial translations are fine — missing keys fall back to English.

Sections produced (one offline HTML file):
  1. Header + metric cards
  2. Arrangement chart (energy / brightness / density / wobble over time)
  3. Stem frequency map (per-stem 6-band heatmap, masking markers, empty-stem flag)
  4. Masking summary cards
  5. Recommendations (dynamics / dramaturgy / storytelling, anchored to timecodes)

Usage:
  python build_widget.py --core result_core.json --detail result_detail.json
                         [--masking result_masking.json] [--als result_als.json]
                         [--out analysis_widget.html] [--title "Track v0.6.2"]
                         [--strings strings.json] [--dump-strings]
"""
import sys, argparse, json, math, copy
from pathlib import Path

TC_VERSION = "0.5.10"   # Track Coach analyzer version (early/unstable; bump as it matures)

BAND_ORDER = ["sub", "low", "low_mid", "mid", "hi_mid", "air"]
BAND_LABEL = {  # frequency ranges — language-neutral, never translated
    "sub": "Sub 20–80", "low": "Low 80–250", "low_mid": "LowMid 250–600",
    "mid": "Mid 600–2k", "hi_mid": "HiMid 2–8k", "air": "Air 8–20k",
}

# ── Canonical text (English). Templates use str.format placeholders. ────────────
# To localise, dump this with --dump-strings, translate the values, pass --strings.
STRINGS = {
    "ui": {
        "subtitle": "deep mode",
        "arc_title": "Arrangement map",
        "arc_hint": "Energy / brightness / density / wobble over time. Grey bars = section boundaries. Hover for a shared cursor.",
        "arr_title": "Arrangement — from the project (.als)",
        "arr_hint": "Ground truth, not a guess: which real project tracks actually play, and when — MIDI and audio. Solid blocks = MIDI (brightness = note density); thin strips = audio clips. Labelled lines = locators, aligned to the audio. This is what separation can only approximate.",
        "arr_none": "No project loaded, or no render offset given — the arrangement can't be aligned to the audio.",
        "arr_aligned": "aligned: project {off} → audio 0:00",
        "auto_title": "Automation — project intention",
        "auto_hint": "Real automation envelopes from the project (filter, gain, pitch, sends…), aligned to the audio. Each curve is scaled to its own range. Compare with Energy / Brightness above: where a curve flattens but the sound keeps moving — or moves while the sound sits still — intention and result disagree.",
        "auto_none": "No moving automation found in the rendered window.",
        "map_title": "Stem ↔ project — does separation match reality?",
        "map_hint": "Each Demucs stem checked against the real project tracks by timing (when its loudness rises vs. when each part plays). “Near-silent” = the stem really is empty. “Has signal · no clean match” means there IS audio here — it just overlaps other parts too much to pin to one track (not lost). Only trust a stem for EQ when it matches one part.",
        "map_clear": "matches “{fam}”", "map_mixed": "blends parts", "map_weak": "no clear match",
        "map_nomatch": "has signal · no clean match", "map_empty": "near-silent",
        "cues_title": "Callouts on the timeline — tap a triangle above, or an item here",
        "map_model": "Model fit: {model}", "map_export": "Most reliable: export group stems from Ableton",
        "rhy_title": "Rhythm & separation quality",
        "rhy_hint": "Per stem: how busy it is (hits/sec), how tightly it sits on the grid (ms off the nearest 1/16), and the off-beat share. Below: whether the stems add back up to the mix, and which stems bleed into each other.",
        "rhy_rate": "{r} hits/s", "rhy_tight": "{ms} ms off-grid", "rhy_sync": "{p}% off-beat",
        "rhy_sep": "Separation confidence", "rhy_leak": "Leakage (stems rising & falling together)",
        "rhy_noleak": "No significant bleed between stems.",
        "note_title": "Transcribed notes — “{label}”",
        "note_hint": "Pitches pulled straight from the audio of this stem (basic-pitch), not from the project. Each bar is one note: position = time, height = pitch, brightness = how loud. Range {lo}–{hi}, {n} notes.",
        "drum_title": "Drum breakdown — kick / snare / hat",
        "drum_hint": "Every hit in the drums stem, classified by spectral shape (not separated into audio). Bar height = hits per window. Kicks {k} · snares {s} · hats {h}.",
        "stem_title": "Stem frequency map",
        "stem_hint": "Each separated stem's spectrum across 6 bands over time. Colour = level (dB). The green strip above each stem shows WHEN it's actually playing (bright = playing, dark = silent). During playback the playing stem's name lights up green. Red marks on top = masking windows.",
        "stem_empty": "⚠ Stem(s) “{stems}” are nearly empty — separation found little material there. Anything involving them is uninformative.",
        "mask_title": "Masking — summary",
        "mask_hint": "How often, and by how much, the bass covers another part in a frequency band. Only real overlaps are shown — a part that's simply silent there isn't counted.",
        "mask_none": "no conflicts found",
        "mask_windows": "{fw}/{tw} windows · avg {diff} dB",
        "read_title": "Producer's read",
        "story_title": "Track story — the shape at a glance",
        "form_label": "Form — same colour = the same part returns",
        "story_hint": "One map. Top: scenes (named, repeat letters A·B·A). Then the POWER curve (a blend of loudness+busy-ness+brightness) with its peak ★ and key moments. Below it the same curve DECOMPOSED into the lanes that drive it — energy (loudness), brightness (treble), density (how busy), modulation (how fast it pulses/throbs per second), stereo width. Bottom: which families play. Press play, click anywhere to jump.",
        "recs_title": "Recommendations",
        "recs_hint": "The few things that stood out, most important first. Red = worth fixing · green = working / do it · yellow = a creative choice. A ⏱ tag means it's tied to a moment in the track — click it to jump there; the rest apply to the whole mix.",
        "legend_crit": "worth fixing",
        "legend_do": "working / actionable",
        "legend_concept": "creative choice",
        "play_title": "Stem player — hear what you see",
        "play_hint": "Play the separated stems together, in sync with every chart above. Mute/solo each part; click any timeline to jump there. The white line is the playhead.",
        "play_play": "▶ Play", "play_pause": "❚❚ Pause", "play_mute": "mute", "play_solo": "solo",
        "play_note": "Each lane is one separated part (htdemucs_6s splits into drums · bass · other · vocals · guitar · piano). A lane can look empty when that instrument isn't really in the track — here piano is near-silent, so you effectively see fewer than six. Lanes are drawn fine-grained (~0.25 s), so you see detail inside every bar, not one block per 4 seconds. Press play; click any lane to jump there. Legend below.",
        "hover": "hover over the chart…",
        "scale_quiet": "quiet −90 dB",
        "scale_loud": "loud −6 dB",
        "presence_label": "green strip = playing",
        "presence_silent": "silent",
        "presence_playing": "playing",
        "presence_active": "{p}% active",
        "footer": "Track Coach v{ver} · data embedded in this file · works offline",
    },
    # metric cards: label + sub + the tag variants chosen by the data
    # Each card: a short verdict + a plain detail line WITH units, and a `help`
    # sentence (shown on hover) saying what it measures, the unit, and the range.
    # Cards are grouped under a heading via `grp`. Two meta-groups by NATURE of the
    # metric (user's framing): "over" = a shape across the track (a trajectory — these
    # are the one-glance verdict for the matching Track Story lane); "now" = a single
    # whole-track characterisation (no time axis — a snapshot of the finished mix).
    "card_groups": {"over": "How it changes across the track",
                    "now": "Overall character (whole track)"},
    "card_groups_hint": {"over": "Each of these is the one-line verdict for a lane in Track Story above — the lane shows the shape, the card shows the conclusion.",
                         "now": "These have no time axis — they describe the finished mix as a whole."},
    "cards": {
        "loudness":   {"label": "Loudness", "grp": "over", "flat": "stays even", "moves": "rises & falls",
                       "det": "trend {et:+.2f} (−1…+1)",
                       "help": "Does the overall level build across the track? Measured as the trend of loudness over time, −1 (fades) to +1 (builds); near 0 means flat."},
        "brightness": {"label": "Brightness", "grp": "over", "tag": "gets brighter",
                       "det": "trend {bt:+.2f} (−1…+1)",
                       "help": "Does the sound get brighter (more treble) over time? Trend of high-frequency content, −1 (darker) to +1 (brighter)."},
        "density":    {"label": "Busy-ness", "grp": "over", "flat": "steady", "moves": "fills up",
                       "det": "trend {dt:+.2f} (−1…+1)",
                       "help": "Does the arrangement fill up (more layers/events) over time? Trend of how busy it is, −1 (thins out) to +1 (fills up)."},
        "wobble":     {"label": "Modulation", "grp": "over", "steady": "steady", "moves": "speeds up",
                       "det": "{ws}→{we} pulses/sec",
                       "help": "“Modulation speed” = how many times per second the sound pulses or throbs — the rate of any repeating movement: a sidechain pump, tremolo, gate, LFO or filter wobble. 2 pulses/sec = it swells twice a second. Read straight from the audio. e.g. 1.5→1.8 means it pulses ~1.5×/sec at the start and ~1.8×/sec by the end. Genre-neutral — it's about movement, not a specific effect."},
        "endpoint":   {"label": "Journey", "grp": "over", "loop": "loops back", "diff": "goes somewhere",
                       "det": "end≈intro {ec:.2f} (0…1)",
                       "help": "How similar the ending sounds to the intro. 0 = totally different, 1 = identical; above ~0.95 the track feels looped, not resolved. (A start-vs-end comparison across the whole arc.)"},
        "swing":      {"label": "Groove", "grp": "now", "swung": "loose, human", "tight": "tight",
                       "det": "{sw} ms off the grid",
                       "help": "How far the hits sit from the exact grid, in milliseconds. ~0 ms = locked/mechanical; >30 ms = noticeably swung, human feel."},
        "tonality":   {"label": "Texture", "grp": "now", "tag": "melodic + drums",
                       "det": "tone vs noise mix",
                       "help": "The balance of pitched/tonal material vs noisy/percussive material across the track."},
        "crest":      {"label": "Punch", "grp": "now", "tag": "moderate",
                       "det": "peaks kept vs squashed",
                       "help": "Crest factor: how much the peaks stand above the average level. High = punchy/dynamic; low = compressed/squashed."},
    },
    # recommendations: header / title / body templates, plus inline fragments.
    # Each rec carries a `fix`: the crisp, concrete option(s) to try — rendered as a
    # highlighted "→ Try" line so the action is visible, not buried in the paragraph.
    # The body explains WHY/what; the fix says WHAT TO DO (often 2 options, "… — or …").
    "recs": {
        "long_section": {
            "header": "Structure · {a}–{b}",
            "title": "One part runs for almost half the track",
            "body": "The chunk <b>{a}–{b}</b> is <b>{frac:.0f}%</b> of the track with no change at all. "
                    "The listener gets tired of waiting. Put a couple of events inside it (drop or add a layer, "
                    "open a filter, change the pattern) — e.g. around <b>{t1}</b> and <b>{t2}</b>.",
            "fix": "Drop or add a layer at <b>{t1}</b> and <b>{t2}</b> — or sweep a filter / switch the pattern there so the part evolves."},
        "energy_flat": {
            "header": "Dynamics · loudness barely moves",
            "title": "No overall rise and fall",
            "body": "Loudest at <b>{peak}</b>, quietest at <b>{valley}</b>, but the level stays flat overall. "
                    "For real dynamics you need a clear drop before the biggest moment — strip it back to bass and "
                    "atmosphere, so the return hits. Contrast makes the climax, not loudness itself.",
            "fix": "Carve a clear drop (bass + atmosphere only) just before <b>{peak}</b> — or automate a build into it. Contrast, not raw level."},
        "brightness": {
            "header": "Development · the track opens up in tone",
            "title": "Only brightness rises — it carries the whole story",
            "body": "From start to end the sound gets brighter (more highs). It's the one line that actually develops — "
                    "loudness and density stay put. Lean into it on purpose: let a filter open toward the climax, and make "
                    "the brightest moment (<b>{bp}</b>) line up with the biggest one.",
            "fix": "Open a filter intentionally toward the climax and align the brightest point (<b>{bp}</b>) with the energy peak."},
        "endpoint": {
            "header": "Ending · the end sounds like the start",
            "title": "The track returns to where it began",
            "body": "The finale is almost indistinguishable from the intro — the track feels looped. Fine for a hypnotic "
                    "groove, but it gives no sense of a journey. If you want the ending to land, either finish on a "
                    "stripped-back outro (cut almost everything, leave one or two elements) or transform the main theme by "
                    "the end so it's audibly “after the journey”, not the same loop.",
            "fix": "Finish on a stripped-back outro (leave 1–2 elements) — or transform the main theme by the end so it reads as 'after the journey'."},
        "wobble": {
            "header": "Movement · modulation stays put",
            "title": "The modulation speed barely changes across the track",
            "body": "The modulation holds a roughly constant speed: <b>{ws:.1f} → {we:.1f}</b> times per second.{note} "
                    "If you want a stronger sense of movement, let it actually evolve — e.g. accelerate toward the "
                    "climax (from {ws:.1f} to a faster rate). That builds tension and keeps the ear engaged.",
            "fix": "Automate the modulation rate to accelerate into the climax (from {ws:.1f}/s upward) — or deepen it in the final section."},
        "wobble_spike": " It jumped to <b>{wmax:.1f}/s</b> once, at <b>{t}</b>, then dropped straight back.",
        "climax": {
            "header": "Climax · {peak}",
            "title": "The main peak arrives late",
            "body": "The biggest moment is at <b>{peak}</b>, about {pos:.0f}% in. The peak usually sits around 70% so there's "
                    "room for a comedown and an ending afterwards. Right now the track ends almost immediately after. Decide: "
                    "move the climax a little earlier and let the track breathe, or keep it a deliberate late drop.",
            "fix": "Move the climax to ~70% and add a comedown after it — or keep it late on purpose as a hard final drop."},
        "swing": {
            "header": "Groove · swing {sw:.0f} ms",
            "title": "Hits sit noticeably off the straight grid",
            "body": "Swing of {sw:.0f} ms means the notes aren't locked to the grid — they're shifted by {sw:.0f} ms, so the "
                    "groove clearly “swings”, sounds human rather than machine. Great for live, hip-hop, organic material. "
                    "If this is straight techno and the drums should be dead-tight, pull them closer to the grid (~25–30 ms).",
            "fix": "Keep it if you want a human feel. For dead-tight techno, pull the drums toward the grid (~25–30 ms)."},
        "truepeak_clip": {
            "header": "Master · true peak {tp:+.1f} dBTP",
            "title": "The master peaks over 0 — inter-sample clipping",
            "body": "True peak hits <b>{tp:+.1f} dBTP</b> (measured 4× oversampled). Above 0 dBTP the signal clips when it's "
                    "converted to MP3/AAC or played through a D/A — distortion you can't hear on the raw file but listeners will. "
                    "Leave about <b>−1 dBTP</b> of headroom on the master.",
            "fix": "Put a true-peak limiter / brickwall ceiling at <b>−1.0 dBTP</b> on the master — or pull the master fader down ~{drop:.1f} dB."},
        "tonal_resonance": {
            "header": "Tone · {band} Hz stands out",
            "title": "One frequency band sticks out from the rest",
            "body": "Across the whole track the <b>{band} Hz</b> region sits about <b>{dev:+.1f} dB</b> "
                    "against its neighbours — a {kind}. {flavour} It colours the whole mix because it's "
                    "there constantly, not just on one hit.",
            "fix": "{action} around <b>{band} Hz</b> on the master (a wide, gentle {dir} of ~{amt:.0f} dB) and A/B it."},
        "squashed": {
            "header": "Master · dynamic range DR {dr:.0f}",
            "title": "The mix is heavily limited — little dynamic range left",
            "body": "Peak-to-RMS is only <b>{dr:.0f} dB</b> — the loud and quiet parts sit almost at the same level, so the "
                    "track sounds flat and fatiguing, with no punch on the transients. This usually means the limiter / clipper "
                    "is working too hard.",
            "fix": "Back off the limiter / master clipper so transients breathe (aim DR ≥ ~8) — or lower the input into it and let the loudest hits poke through."},
        "empty_stem": {
            "header": "Separation · stem “{stems}” is empty",
            "title": "Separation found almost nothing in this stem",
            "body": "The separator found almost no material for “{stems}”. Often this isn't the track's fault: the model is "
                    "trained on live bands (drums / bass-guitar / vocals / other) and dumps synth bass into “{carrier}”. "
                    "Worth re-running with a model that has more stems (htdemucs_6s adds guitar and piano).",
            "fix": "Re-run separation with htdemucs_6s — or, if you have the project, export the group stem instead of trusting this one."},
        "masking_real": {
            "header": "Frequencies · bass competes with mids",
            "title": "Around 250–600 Hz the bass is louder than the melody at times",
            "body": "{lines}. Where it bothers you, carve a small dip in the bass in that range or separate them in time. "
                    "Where the mid instrument is simply silent, that's not a conflict — leave it.",
            "fix": "Carve a small 250–600 Hz dip in the bass — or sidechain/duck it under the melody so they don't fight."},
        "masking_line": "bass covers “{mid}” in {pct:.0f}% of spots",
        "masking_clean": {
            "header": "Low end · clean",
            "title": "The bass doesn't clash with anything",
            "body": "The bass doesn't cover the melody (250–600 Hz) or the kick (sub 20–80 Hz). If the mix sounds muddy, "
                    "the cause isn't bass-vs-mids clash.",
            "fix": "Nothing to fix here. If it still sounds muddy, look at reverb/saturation or low-mid buildup in other parts."},
        "low_carrier": {
            "header": "Low end · where it actually lives",
            "title": "The low end is held by “{carrier}”, not “bass”",
            "body": "All the low-frequency energy sits in “{carrier}”. Do your low-end EQ, sidechain (ducking under the "
                    "kick) and weight automation on “{carrier}” — that's your real foundation.",
            "fix": "Do low-end EQ and kick-sidechain on “{carrier}”, not on the bass stem."},
        "breakdown": {
            "header": "Dynamics · breakdown at {t}",
            "title": "Drums and low end drop out at {lst}",
            "body": "The drums clearly pull back here — a real breakdown, a dip before the return.{only} It sits at ~{pos:.0f}% "
                    "in, so the track does breathe once. Push it: make the entry/exit more contrasted, or add a second, deeper "
                    "dip right before the final section so the climax can breathe.",
            "fix": "Sharpen the entry/exit contrast — or add a second, deeper breakdown right before the final drop."},
        "breakdown_only": " And it's the only one in the whole track.",
        "late_entry": {
            "header": "Event · {t}",
            "title": "A new element enters right at the end",
            "body": "Stem “{st}” is silent for almost the whole track and only appears at <b>{t}</b>. If it's a lead, vocal "
                    "or sample, that's a strong accent for the finale. Right now it flies in just before the hard cut: bring it "
                    "in a little earlier and let it play out, so it reads as a resolution, not a stray tail.",
            "fix": "Bring “{st}” in a bit earlier than <b>{t}</b> and let it play out, so it lands as a resolution rather than a stray tail."},
        # ── from the project + per-stem layers (B/C/G) ──
        "intention_result": {
            "header": "Intention vs result · {param}",
            "title": "The filter stops opening, but the track keeps getting brighter",
            "body": "Your “{param}” automation flattens out around <b>{a_end}</b>, yet the measured brightness keeps climbing "
                    "until <b>{b_peak}</b>. So the ear hears the track still opening up after the automation has stopped moving — "
                    "intention and result drift apart. If that rising brightness is wanted, extend the automation to <b>{b_peak}</b> "
                    "so it's deliberate; if not, something else (a layer, reverb, distortion) is adding the highs — check there.",
            "fix": "Extend the “{param}” automation to <b>{b_peak}</b> to own the rise — or hunt the unintended brightness (a layer, reverb, distortion)."},
        "sep_incomplete": {
            "header": "Separation · stems don't add up",
            "title": "The stems don't reconstruct the full mix",
            "body": "Summing every stem leaves a <b>{db} dB</b> residual against the original — a lot of the track isn't captured "
                    "by any single stem. Read the per-stem panels as approximate here, not exact. If you have the project, export "
                    "group stems from Ableton instead — those are complete by construction.",
            "fix": "Export group stems from Ableton for exact analysis — treat the separated stems as approximate."},
        "bass_groupstem": {
            "header": "Low end · use the project bass group, not the stem",
            "title": "The separated bass doesn't map to one project part",
            "body": "The bass stem has real signal, but its timing overlaps other parts so separation can't isolate it cleanly. "
                    "That means EQ/sidechain decisions based on that stem will be off — not because the bass is missing, but "
                    "because it's blended. Do your low-end work on the project's bass group (solo <b>Grp Bass</b> in Ableton and "
                    "export it) — that's the real low end, not a guess.",
            "fix": "Solo & export <b>Grp Bass</b> in Ableton and do low-end EQ/sidechain there — not on the separated bass stem."},
    },
}

# which colour class each recommendation uses
REC_CLASS = {
    "long_section": "crit", "energy_flat": "crit", "endpoint": "crit", "empty_stem": "crit",
    "intention_result": "crit", "sep_incomplete": "crit", "truepeak_clip": "crit",
    "wobble": "concept", "swing": "concept", "late_entry": "concept",
    "bass_groupstem": "do", "squashed": "do", "tonal_resonance": "do",
}


def deep_merge(base, override):
    """Recursively merge override into a copy of base (override wins; missing keys keep base)."""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def fmt_t(s):
    if s is None or s < 0:
        return "0:00"
    return f"{int(s // 60)}:{int(round(s % 60)):02d}"


def stem_broadband_db(masking, stem):
    bands = masking["band_rms_db"][stem]
    n = masking["total_windows"]
    out = []
    for i in range(n):
        p = sum(10 ** (bands[b][i] / 10.0) for b in BAND_ORDER if b in bands)
        out.append(round(10 * math.log10(p) if p > 0 else -120.0, 1))
    return out


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def peak_idx(arr):
    return max(range(len(arr)), key=lambda i: arr[i]) if arr else 0


def valley_idx(arr):
    return min(range(len(arr)), key=lambda i: arr[i]) if arr else 0


def loud_level(arr):
    """Representative level when the stem IS playing (85th percentile of bins).
    Intermittent stems (a bassline that hits some beats) have a very low median
    but are not empty — judge 'empty' by how loud they get, not the median."""
    if not arr:
        return None
    a = sorted(arr)
    return a[int(0.85 * (len(a) - 1))]


def build_recommendations(core, detail, masking, S, als_overlay=None, stemmap=None, rhythm=None):
    R = S["recs"]
    recs = []
    dur = core["duration_s"]
    tb = core["time_bins"]
    bounds = core.get("section_bounds_s", [])

    def add(key, _t=None, **kw):
        # _t = numeric anchor time (s) so the rec can be pinned on the timeline; None = global advice.
        tpl = R[key]
        cls = REC_CLASS.get(key, "do")
        fix = tpl.get("fix", "")
        recs.append((cls, tpl["header"].format(**kw), tpl["title"].format(**kw),
                     tpl["body"].format(**kw), fix.format(**kw) if fix else "",
                     round(_t, 2) if _t is not None else None))

    if len(bounds) >= 2:
        edges = bounds + [dur]
        segs = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
        a, b = max(segs, key=lambda s: s[1] - s[0])
        frac = (b - a) / dur
        if frac > 0.33:
            t1, t2 = a + (b - a) / 3, a + 2 * (b - a) / 3
            add("long_section", _t=t1, a=fmt_t(a), b=fmt_t(b), frac=frac * 100, t1=fmt_t(t1), t2=fmt_t(t2))

    et = core.get("energy_trend")
    energy = core.get("energy", [])
    if et is not None and abs(et) < 0.12 and energy:
        add("energy_flat", peak=fmt_t(tb[peak_idx(energy)]), valley=fmt_t(tb[valley_idx(energy)]))

    bt = core.get("brightness_trend")
    if bt is not None and bt > 0.25:
        other = max(abs(core.get("energy_trend", 0)), abs(core.get("density_trend", 0)))
        if bt > 1.6 * max(other, 1e-6):
            bpt = tb[peak_idx(core.get("brightness", [0]))]
            add("brightness", _t=bpt, bp=fmt_t(bpt))

    ec = core.get("endpoint_cosine")
    if ec is not None and ec > 0.95:
        add("endpoint", _t=dur)

    ws, we = core.get("wobble_rate_start_hz"), core.get("wobble_rate_end_hz")
    warr = core.get("wobble_rate", [])
    if ws is not None and we is not None and we < ws * 1.4:
        wmax = max(warr) if warr else we
        note = R["wobble_spike"].format(t=fmt_t(tb[peak_idx(warr)]), wmax=wmax) if (warr and wmax > ws * 1.8) else ""
        add("wobble", ws=ws, we=we, note=note)

    if energy:
        pkt = tb[peak_idx(energy)]
        pos = pkt / dur
        if pos > 0.75:
            add("climax", _t=pkt, peak=fmt_t(pkt), pos=pos * 100)

    sw = detail.get("swing_global_ms")
    if sw is not None and sw > 30:
        add("swing", sw=sw)

    # ── mastering vitals → actionable recs (true-peak clipping, over-limiting) ──
    vit = core.get("vitals", {})
    tp = vit.get("true_peak_db")
    if tp is not None and tp > 0.0:
        add("truepeak_clip", tp=tp, drop=tp + 1.0)   # drop to reach −1 dBTP ceiling
    dr = vit.get("dynamic_range_db")
    if dr is not None and dr < 6.0:
        add("squashed", dr=dr)

    # tonal balance — flag the single most out-of-line band (resonance or hole).
    tbal = core.get("tonal_balance", [])
    if tbal:
        worst = max(tbal, key=lambda b: abs(b.get("dev_db", 0)))
        dev = worst.get("dev_db", 0)
        if abs(dev) >= 4.0:
            hot = dev > 0
            band = worst["band"]
            # low bands → "boxy/muddy"; high bands → "harsh"; holes → "dull/thin"
            low = any(band.startswith(p) for p in ("20", "60", "120", "250"))
            flavour = (("That usually reads as boxy or muddy." if low else "That usually reads as harsh or fatiguing.")
                       if hot else ("That can leave the mix sounding dull or thin." if not low else "The low end may feel hollow there."))
            add("tonal_resonance", band=band, dev=dev,
                kind=("resonance / build-up" if hot else "dip / hole"), flavour=flavour,
                action=("Dip" if hot else "Lift"), dir=("cut" if hot else "boost"),
                amt=min(4.0, abs(dev) * 0.6))

    if masking:
        empties = [st for st in masking.get("stems_analysed", [])
                   if (loud_level(stem_broadband_db(masking, st)) or -120) < -55]

        def loudest_in(band):
            best, bestv = None, -999
            for st in masking.get("stems_analysed", []):
                v = median(masking["band_rms_db"][st].get(band, [-120]))
                if v is not None and v > bestv:
                    best, bestv = st, v
            return best
        sub_carrier = loudest_in("sub")

        # NOTE: separation-quality findings (empty/smeared stems, residual, untrustworthy
        # bass) are NOT surfaced as recommendations — they're tool artefacts, not music
        # advice, and aren't actionable for the producer. They live in the "Stem ↔ project"
        # and "rhythm & separation" panels as honest caveats instead.

        real = [(z.split("__")[-1], s) for z, s in masking.get("masking_summary", {}).items()
                if s["pct_masked"] > 0 and z.split("__")[-1] not in empties]
        if real:
            lines = "; ".join(R["masking_line"].format(mid=mid, pct=s["pct_masked"]) for mid, s in real)
            add("masking_real", lines=lines)
        elif not empties:
            add("masking_clean")

        tb_m = masking["time_bins"]
        nb = masking["total_windows"]
        bbs = {st: stem_broadband_db(masking, st) for st in masking.get("stems_analysed", [])}

        drum = "drums" if "drums" in bbs else sub_carrier
        if drum and drum in bbs:
            arr = bbs[drum]
            thr = (median(arr) or -120) - 12
            idx = [i for i in range(nb) if arr[i] < thr]
            groups = []
            if idx:
                s = p = idx[0]
                for i in idx[1:]:
                    if tb_m[i] - tb_m[p] > 8:
                        groups.append((tb_m[s], tb_m[p]))
                        s = i
                    p = i
                groups.append((tb_m[s], tb_m[p]))
            breaks = [(a, b) for a, b in groups if b < dur - 6 and (b - a) >= 8]
            if breaks:
                lst = ", ".join(f"{fmt_t(a)}–{fmt_t(b)}" for a, b in breaks)
                only = R["breakdown_only"] if len(breaks) == 1 else ""
                add("breakdown", _t=breaks[0][0], t=fmt_t(breaks[0][0]), lst=lst,
                    pos=breaks[0][0] / dur * 100, only=only)

        for st in bbs:
            arr = bbs[st]
            mmed = median(arr) or -120
            li = peak_idx(arr)
            if mmed < -55 and arr[li] > mmed + 20 and tb_m[li] > 0.8 * dur:
                add("late_entry", _t=tb_m[li], st=st, t=fmt_t(tb_m[li]))
                break

    # ── Intention vs result: a filter/cutoff automation vs the measured brightness ──
    bright = core.get("brightness", [])
    autos = (als_overlay or {}).get("automations", []) if als_overlay else []
    if bright and autos:
        def val_at(pts, t):                      # step lookup of an envelope value
            v = pts[0][1]
            for p in pts:
                if p[0] <= t:
                    v = p[1]
                else:
                    break
            return v
        cut = next((a for a in autos
                    if any(k in a["label"].lower() for k in ("cutoff", "filter", "freq"))), None)
        if cut and len(cut["pts"]) >= 2:
            t70 = 0.7 * dur
            a_late = val_at(cut["pts"], dur) - val_at(cut["pts"], t70)   # automation move in last 30%
            span = max(1e-9, cut["vmax"] - cut["vmin"])
            i70 = max(0, min(len(bright) - 1, int(0.7 * (len(bright) - 1))))
            b_late = bright[-1] - bright[i70]
            bpk = peak_idx(bright)
            # automation flat/closing in the tail, but brightness still clearly climbing
            if a_late <= 0.05 * span and b_late > 0.06 and tb[bpk] > t70:
                add("intention_result", _t=cut["pts"][-1][0], param=cut["label"],
                    a_end=fmt_t(cut["pts"][-1][0]), b_peak=fmt_t(tb[bpk]))

    return recs


def build_cards(core, detail, S):
    C = S["cards"]
    et, bt, dt = core.get("energy_trend", 0), core.get("brightness_trend", 0), core.get("density_trend", 0)
    ec = core.get("endpoint_cosine", 0)
    ws, we = core.get("wobble_rate_start_hz", 0), core.get("wobble_rate_end_hz", 0)
    sw = detail.get("swing_global_ms", 0)

    # Plain-language magnitude instead of a raw −1…+1 number ("clearly brighter", not "+0.41").
    def mag(v, up, down, flat):
        a = abs(v)
        if a < 0.12:
            return flat
        d = up if v > 0 else down
        if a < 0.30:
            return f"{d} a little"
        if a < 0.60:
            return f"clearly {d}"
        return f"{d} a lot"

    end_det = ("≈ same as the intro" if ec > 0.95 else
               "echoes the intro" if ec > 0.85 else "ends somewhere new")
    wob_det = (f"~{ws:.1f}/sec, steady" if we < ws * 1.4 else f"{ws:.1f}→{we:.1f}/sec, speeds up")

    def card(key, verdict, det, color):
        c = C[key]
        return (c["label"], verdict, det, color, c.get("help", ""), c.get("grp", ""))

    return [
        card("loudness", C["loudness"]["flat"] if abs(et) < 0.12 else C["loudness"]["moves"],
             mag(et, "builds", "fades", "stays flat"), "warn" if abs(et) < 0.12 else "good"),
        card("brightness", C["brightness"]["tag"],
             mag(bt, "brighter", "darker", "tone holds"), "good"),
        card("density", C["density"]["flat"] if abs(dt) < 0.12 else C["density"]["moves"],
             mag(dt, "fills up", "thins out", "steady"), "warn" if abs(dt) < 0.12 else "good"),
        card("endpoint", C["endpoint"]["loop"] if ec > 0.95 else C["endpoint"]["diff"],
             end_det, "warn" if ec > 0.95 else "good"),
        card("wobble", C["wobble"]["steady"] if we < ws * 1.4 else C["wobble"]["moves"],
             wob_det, "warn" if we < ws * 1.4 else "good"),
        card("swing", C["swing"]["swung"] if sw > 30 else C["swing"]["tight"],
             f"{sw:.0f} ms off-grid", "warn" if sw > 30 else "good"),
        card("tonality", C["tonality"]["tag"], C["tonality"]["det"], "good"),
        card("crest", C["crest"]["tag"], C["crest"]["det"], "good"),
    ]


# Instrument families for colouring the arrangement Gantt. Order = display order.
ALS_FAMILIES = [
    ("kick",  "#ff5d73", ("kick", "808", "core kit")),
    ("bass",  "#a78bfa", ("bass", "rumble", "sub", "reese", "wobble")),
    ("drums", "#4cc9f0", ("drum", "snr", "snare", "amen", "tom", "perc", "clap")),
    ("hats",  "#5ad1c2", ("hh", "hat", "hi-hat", "shaker", "cymbal", "ride")),
    ("chord", "#46d39a", ("chord", "chrd", "tone", "pad", "key")),
    ("lead",  "#ffd166", ("lead", "operator", "granulator", "drift", "instrument", "rack", "arp", "pluck", "vox", "vocal")),
]


def als_family(name):
    n = name.lower()
    for fam, col, keys in ALS_FAMILIES:
        if any(k in n for k in keys):
            return fam, col
    return "other", "#8b94a8"


def build_als_overlay(als, offset_s, dur):
    """Ground-truth arrangement from the project, aligned to the rendered audio.

    offset_s is the project time (in seconds) where the render starts — usually a
    locator. It is NEVER guessed: callers pass it explicitly (CLI --als-offset-s).
    With no offset we cannot align clips to the audio, so the arrangement is omitted.
    """
    if not als:
        return None
    bpm = als.get("bpm")

    # Locators that fall inside the rendered window, expressed in audio time.
    markers = []
    if offset_s is not None:
        seen = set()
        for m in als.get("markers", []):
            t = m["time_s"] - offset_s
            if -0.5 <= t <= dur + 0.5:
                key = (round(t, 1), m["name"])
                if key not in seen:
                    seen.add(key)
                    markers.append({"name": m["name"], "t": round(max(0.0, min(dur, t)), 2)})
        markers.sort(key=lambda x: x["t"])

    # Per-track clip activity, clipped to the rendered window (audio time).
    # Both MIDI tracks (note_count = density) AND audio tracks (clip activity).
    lanes = []
    automations = []
    if offset_s is not None:
        fam_order = {f[0]: i for i, f in enumerate([*ALS_FAMILIES, ("other", "", ())])}

        def clip_intervals(clips, count_key):
            ivs, tot = [], 0
            for c in clips:
                s, e = c["start_s"] - offset_s, c.get("end_s")
                e = (e - offset_s) if e is not None else s
                if e > 0 and s < dur:
                    a, b = max(0.0, s), min(dur, e)
                    if b - a > 0.05:
                        n = c.get(count_key, 0)
                        ivs.append([round(a, 2), round(b, 2), n])
                        tot += n
            return ivs, tot

        for t in als.get("tracks", []):
            fam, col = als_family(t["name"])
            mivs, notes = clip_intervals(t.get("midi_clips", []), "note_count")
            if mivs:
                lanes.append({"name": t["name"], "fam": fam, "col": col, "kind": "midi",
                              "intervals": mivs, "notes": notes})
            aivs, _ = clip_intervals(t.get("audio_clips", []), "x")
            if aivs:
                lanes.append({"name": t["name"], "fam": fam, "col": col, "kind": "audio",
                              "intervals": aivs, "notes": len(aivs)})
        # MIDI first, then audio within each family; busiest on top
        lanes.sort(key=lambda L: (fam_order.get(L["fam"], 99), 0 if L["kind"] == "midi" else 1, -L["notes"]))

        # ── Automation envelopes inside the window (the "intention" layer) ──────
        # Prefer expressive params (filter/gain/pitch) over the many send throws,
        # keep only ones that actually move, and cap the count so the panel reads.
        PRIORITY = ("filter", "cutoff", "freq", "gain", "pitch", "morph", "drive", "volume")
        cand = []
        for t in als.get("tracks", []):
            for au in t.get("automations", []):
                if not au.get("varies"):
                    continue
                pts = [[round(e["time_s"] - offset_s, 2), e["value"]]
                       for e in au.get("events", []) if -1 <= e["time_s"] - offset_s <= dur + 1]
                pts = [[max(0.0, min(dur, p[0])), p[1]] for p in pts]
                if len(pts) < 2:
                    continue
                vmin = min(p[1] for p in pts)
                vmax = max(p[1] for p in pts)
                if vmax - vmin < 1e-6:
                    continue
                label = f"{t['name']} · {au.get('param', 'param')}"
                pl = (au.get("param", "") + au.get("device", "")).lower()
                pri = 0 if any(k in pl for k in PRIORITY) else 1
                cand.append({"label": label, "fam": als_family(t["name"])[1],
                             "vmin": vmin, "vmax": vmax, "span": vmax - vmin,
                             "pts": pts, "pri": pri, "n": len(pts)})
        cand.sort(key=lambda c: (c["pri"], -c["n"]))
        automations = cand[:8]

    return {"bpm": bpm, "offset_s": offset_s, "markers": markers, "lanes": lanes,
            "automations": automations,
            "track_count": als.get("track_count"), "midi_notes": als.get("total_midi_notes"),
            "audio_clips": als.get("total_audio_clips")}


def _mm(a):
    """Min-max normalise a list to 0..1."""
    a = [float(x) for x in (a or [])]
    if not a:
        return []
    lo, hi = min(a), max(a)
    return [(x - lo) / (hi - lo) if hi > lo else 0.0 for x in a]


def _merge_iv(ivs):
    ivs = sorted([list(x[:2]) for x in ivs])
    out = []
    for a, b in ivs:
        if out and a <= out[-1][1] + 0.01:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def build_story(core, als_overlay):
    """Synthesise the high-level 'Track Story': scenes (named + pattern letter),
    one intensity/power curve, key moments, and a compact family-presence texture.
    Combines audio arcs (energy/density/brightness) with the project arrangement."""
    dur = core["duration_s"]
    tb = core["time_bins"]
    n = len(tb)
    if not n:
        return None
    e, d, b = _mm(core.get("energy", [])), _mm(core.get("density", [])), _mm(core.get("brightness", []))
    inten = _mm([0.5 * (e[i] if i < len(e) else 0) + 0.3 * (d[i] if i < len(d) else 0)
                 + 0.2 * (b[i] if i < len(b) else 0) for i in range(n)])
    climax_i = max(range(n), key=lambda i: inten[i])

    # family presence (merged intervals per instrument family) from the arrangement
    fam_iv = {}
    if als_overlay and als_overlay.get("lanes"):
        for L in als_overlay["lanes"]:
            fam_iv.setdefault(L["fam"], []).extend([[iv[0], iv[1]] for iv in L["intervals"]])
        fam_iv = {f: _merge_iv(v) for f, v in fam_iv.items()}
    FAM_ORDER = ["kick", "bass", "drums", "hats", "chord", "lead", "other"]
    FAM_COL = {f[0]: f[1] for f in ALS_FAMILIES}
    FAM_COL["other"] = "#8b94a8"
    families = [{"name": f, "col": FAM_COL.get(f, "#8b94a8"), "intervals": fam_iv[f]}
                for f in FAM_ORDER if f in fam_iv]

    def fams_active(t0, t1):
        span = max(1e-9, t1 - t0)
        on = set()
        for f, ivs in fam_iv.items():
            cov = sum(max(0.0, min(b2, t1) - max(a2, t0)) for a2, b2 in ivs)
            if cov / span > 0.4:
                on.add(f)
        return on

    # scenes from section boundaries; classify by intensity + arrangement
    bounds = [x for x in core.get("section_bounds_s", []) if 0 < x < dur]
    edges = sorted(set([0.0] + [round(x, 2) for x in bounds] + [round(dur, 2)]))
    segs = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1) if edges[i + 1] - edges[i] > 2]

    def seg_inten(a, b2):
        idx = [i for i in range(n) if a <= tb[i] < b2]
        return sum(inten[i] for i in idx) / len(idx) if idx else 0.0
    seg_t = [seg_inten(a, b2) for a, b2 in segs]
    mx = max(seg_t) if seg_t else 1.0

    scenes = []
    sigs = {}          # signature → letter, for pattern detection (A/B/A)
    letters = "ABCDEFGH"
    dropn = 0
    for i, (a, b2) in enumerate(segs):
        ti = seg_t[i]
        tier = ti / mx if mx > 0 else 0.0
        prev = seg_t[i - 1] if i > 0 else None
        nxt = seg_t[i + 1] if i < len(segs) - 1 else None
        if i == 0 and tier < 0.55:
            name = "Intro"
        elif i == len(segs) - 1 and tier < 0.6:
            name = "Outro"
        elif tier >= 0.8:
            dropn += 1
            name = "Drop" if dropn == 1 else f"Drop {dropn}"
        elif prev is not None and nxt is not None and ti < prev and ti < nxt and tier < 0.55:
            name = "Breakdown"
        elif nxt is not None and nxt > ti + 0.05 and tier < 0.8:
            name = "Build"
        else:
            name = "Section"
        # pattern letter: same active-family set + similar intensity tier ⇒ same element
        sig = (frozenset(fams_active(a, b2)), round(tier * 3))   # 4 intensity buckets
        if sig not in sigs:
            sigs[sig] = letters[len(sigs)] if len(sigs) < len(letters) else "·"
        scenes.append({"name": name, "t0": round(a, 2), "t1": round(b2, 2),
                       "tier": round(tier, 3), "letter": sigs[sig]})

    # key moments (hooks / turning points), deduped by proximity
    moments = [{"t": round(tb[climax_i], 2), "label": "Climax", "kind": "climax"}]
    # biggest intensity jump = a drop / entrance
    if n > 4:
        win = max(1, n // 20)
        jumps = [(inten[min(n - 1, i + win)] - inten[i], i) for i in range(n - win)]
        dj, ji = max(jumps) if jumps else (0, 0)
        if dj > 0.35:
            moments.append({"t": round(tb[min(n - 1, ji + win)], 2), "label": "Drop", "kind": "drop"})
    # breakdown: deepest dip in the middle, clearly low
    mid = [i for i in range(n) if 0.2 * dur < tb[i] < 0.85 * dur]
    if mid:
        bi = min(mid, key=lambda i: inten[i])
        if inten[bi] < 0.35:
            moments.append({"t": round(tb[bi], 2), "label": "Breakdown", "kind": "break"})
    # first entry of a lead/melodic family = a hook
    for f in ("lead", "chord"):
        if f in fam_iv and fam_iv[f]:
            t0 = fam_iv[f][0][0]
            if t0 > 0.05 * dur:
                moments.append({"t": round(t0, 2), "label": f"{f} in", "kind": "entry"})
                break
    # dedupe moments within 8s, keep first
    moments.sort(key=lambda m: m["t"])
    dedup = []
    for m in moments:
        if not dedup or m["t"] - dedup[-1]["t"] > 8:
            dedup.append(m)

    # component lanes: the meta power curve decomposed + extra character dims.
    # energy/density/brightness feed the power curve; modulation + stereo are character.
    src = {"energy": core.get("energy", []), "brightness": core.get("brightness", []),
           "density": core.get("density", []), "modulation": _mm(core.get("wobble_rate", [])),
           "stereo": _mm(core.get("stereo_width", []))}
    COMP = [("energy", "Energy", "#ff5d73"), ("brightness", "Brightness", "#ffd166"),
            ("density", "Density", "#4cc9f0"), ("modulation", "Modulation", "#a78bfa"),
            ("stereo", "Stereo width", "#5ad1c2")]
    # one-word verdict per lane — the conclusion lives ON the shape (replaces the
    # old over-time cards). Direction from the measured trend; near 0 = flat/steady.
    def _verdict(up, down, flat, val, thr=0.12):
        return up if val > thr else down if val < -thr else flat
    wr_s = core.get("wobble_rate_start_hz", 0.0); wr_e = core.get("wobble_rate_end_hz", 0.0)
    mod_dir = (wr_e - wr_s) / max(0.5, abs(wr_s) + abs(wr_e))
    VERD = {
        "energy":     _verdict("builds", "fades", "stays even", core.get("energy_trend", 0)),
        "brightness": _verdict("gets brighter", "gets darker", "steady", core.get("brightness_trend", 0)),
        "density":    _verdict("fills up", "thins out", "steady", core.get("density_trend", 0)),
        "modulation": _verdict("speeds up", "slows down", "steady", mod_dir),
        "stereo":     _verdict("widens", "narrows", "steady", core.get("stereo_width_trend", 0)),
    }
    components = [{"key": k, "label": l, "col": c, "verdict": VERD.get(k, ""),
                   "vals": [round(float(x), 3) for x in _mm(src[k])], "in_power": k in ("energy", "density", "brightness")}
                  for k, l, c in COMP if any(src[k])]

    return {"dur": round(dur, 2), "bins": [round(float(x), 2) for x in tb],
            "intensity": [round(float(x), 3) for x in inten],
            "climax_t": round(tb[climax_i], 2),
            "scenes": scenes, "moments": dedup, "families": families,
            "components": components}


def build_html(core, detail, masking, als, out_path, title, S, als_offset_s=None, stemmap=None,
               rhythm=None, notes=None, drums=None, audio_stems_rel=None, presence_threshold=0.3,
               narrative_md=None, selfsim=None):
    dur = core["duration_s"]
    tb = core["time_bins"]

    arc_lanes = [
        ("energy", "Energy", "#ff5d73", core.get("energy", []), 1),
        ("brightness", "Brightness", "#ffd166", core.get("brightness", []), 1),
        ("density", "Density", "#4cc9f0", core.get("density", []), 1),
        ("wobble_rate", "Wobble Hz", "#a78bfa", core.get("wobble_rate", []), 5),
    ]

    stem_block = None
    masking_cards = []
    flag_times = []
    if masking:
        stems = masking.get("stems_analysed", [])
        heat = {st: {b: masking["band_rms_db"][st].get(b, [-120] * masking["total_windows"]) for b in BAND_ORDER}
                for st in stems}
        empties = [st for st in stems if (loud_level(stem_broadband_db(masking, st)) or -120) < -55]
        bb = {st: stem_broadband_db(masking, st) for st in stems}  # broadband dB per bin → "is it playing"
        stem_block = {"stems": stems, "bands": BAND_ORDER, "band_labels": BAND_LABEL,
                      "heat": heat, "bb": bb, "time_bins": masking["time_bins"],
                      "viz": masking.get("viz"), "empties": empties}
        BAND_HZ = {"sub": "20–80 Hz", "low": "80–250 Hz", "low_mid": "250–600 Hz",
                   "mid": "600 Hz–2 kHz", "hi_mid": "2–8 kHz", "air": "8–20 kHz"}
        for zone, s in masking.get("masking_summary", {}).items():
            if s["pct_masked"] <= 0:
                continue
            band = zone.split("__")[0]
            mid = zone.split("__")[-1]
            # Skip if the "covered" part is essentially silent in that band — a big
            # dB gap against silence is not a real clash, just an absent instrument.
            mid_band = masking["band_rms_db"].get(mid, {}).get(band, [])
            if (loud_level(mid_band) or -120) < -55:
                continue
            label = f"Bass vs {mid} · {BAND_HZ.get(band, band)}"
            masking_cards.append((label, s["pct_masked"], s["mean_diff_db"], s["flagged_windows"], s["total_windows"]))
        for zone, flags in masking.get("masking_flags", {}).items():
            for f in flags:
                flag_times.append(f["time_s"])

    als_overlay = build_als_overlay(als, als_offset_s, dur)
    story = build_story(core, als_overlay)

    # Per-section LEAD: which melodic part dominates each self-similarity segment.
    # Answers the user's "some parts one melodic instrument leads, others another".
    # PREFER the .als (v0.5.9): the project's own melodic tracks (Violin1, Lead, Pad…) with
    # their MIDI/clip activity are the real ground truth — Demucs often lumps every melodic
    # part into one "other" stem, which can't tell a violin from a lead. Fall back to the
    # Demucs stems (minus drums/bass) only when there's no .als. Attached to Form segments.
    ss_segs = (selfsim or {}).get("segments", [])
    MELODIC_FAMS = ("chord", "lead", "other")
    als_lanes = [L for L in (als_overlay or {}).get("lanes", []) if L.get("fam") in MELODIC_FAMS]
    if ss_segs and als_lanes:
        for seg in ss_segs:
            best, bestv = None, 0.0
            for L in als_lanes:
                act = 0.0
                for iv in L.get("intervals", []):
                    a, b, n = iv[0], iv[1], (iv[2] if len(iv) > 2 else 1)
                    ov = min(seg["t1"], b) - max(seg["t0"], a)
                    if ov > 0:                       # overlap × note/clip density
                        act += ov * (n / max(0.1, b - a))
                if act > bestv:
                    best, bestv = L["name"], act
            if best is not None and bestv > 0:
                seg["lead"] = best
    elif ss_segs and masking:
        mtb = masking.get("time_bins", [])
        melodic = [st for st in masking.get("stems_analysed", []) if st not in ("drums", "bass")]
        bb = {st: stem_broadband_db(masking, st) for st in melodic}
        for seg in ss_segs:
            idx = [i for i, t in enumerate(mtb) if seg["t0"] <= t < seg["t1"]]
            if not idx:
                continue
            best, bestv = None, -999.0
            for st in melodic:
                vals = [bb[st][i] for i in idx if i < len(bb[st])]
                lin = [10 ** (v / 10.0) for v in vals if v > -119]
                mean_db = 10 * math.log10(sum(lin) / len(lin)) if lin else -120.0
                if mean_db > bestv:
                    best, bestv = st, mean_db
            if best is not None and bestv > -45:   # above near-silence
                seg["lead"] = best
    recs = build_recommendations(core, detail, masking, S,
                                 als_overlay=als_overlay, stemmap=stemmap, rhythm=rhythm)
    # Most important first: fix (crit) → actionable (do) → creative choice (concept).
    _rank = {"crit": 0, "do": 1, "concept": 2}
    recs.sort(key=lambda r: _rank.get(r[0], 3))   # tuple: (cls, when, head, body, fix, t)

    player = None
    if audio_stems_rel:
        rel = audio_stems_rel.rstrip("/")
        adir = Path(out_path).parent / rel
        # Prefer the actual files on disk (compressed .m4a/.mp3/.ogg over raw .wav).
        # Every playable stem on disk becomes a lane (e.g. all 6 of htdemucs_6s),
        # not just the ones the masking pass analysed. Analysed ones come first
        # (they carry the richest data); any extra files follow.
        EXT_PREF = (".m4a", ".mp3", ".ogg", ".opus", ".wav", ".flac")
        disk = sorted({p.stem for p in adir.glob("*") if p.suffix.lower() in EXT_PREF})
        analysed = (masking.get("stems_analysed") if masking else None) or []
        names = [n for n in analysed if n in disk] + [n for n in disk if n not in analysed]
        srcs = []
        for n in names:
            hit = next((f"{rel}/{n}{e}" for e in EXT_PREF if (adir / f"{n}{e}").exists()), None)
            if hit:
                srcs.append({"name": n, "src": hit})
        if srcs:
            player = {"srcs": srcs}

    payload = {
        "dur": dur, "tempo": core.get("tempo"), "bins": tb,
        "sections": core.get("section_bounds_s", []),
        "arc": [{"key": k, "label": l, "col": c, "vals": v, "max": m} for k, l, c, v, m in arc_lanes],
        "vitals": {**core.get("vitals", {}),
                   **({"time_sig": als.get("time_signature"),
                       "time_sig_changes": als.get("time_sig_changes", [])} if als else {})},
        "selfsim": (selfsim or {}).get("segments", []),
        "tonal_balance": core.get("tonal_balance", []),
        "stem": stem_block,
        "mcards": [{"label": z, "pct": p, "diff": d, "fw": fw, "tw": tw} for z, p, d, fw, tw in masking_cards],
        "flags": flag_times,
        "recs": [{"cls": c, "when": w, "h": h, "p": p, "fix": fx, "t": t} for c, w, h, p, fx, t in recs],
        "als": als_overlay,
        "stemmap": stemmap,
        "rhythm": rhythm,
        "notes": notes,
        "drums": drums,
        "player": player,
        "presence_threshold": presence_threshold,
        "narrative": narrative_md,
        "story": story,
        "version": TC_VERSION,
        "t": S["ui"],
    }
    title = title or f'{core.get("tempo","?")} BPM · {dur:.0f}s'
    html = TEMPLATE.replace("__TITLE__", _esc(title)).replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"Widget saved: {out_path}  (Track Coach v{TC_VERSION})")
    print(f"  arc lanes: {len(arc_lanes)}  stems: {len((masking or {}).get('stems_analysed', []))}  recs: {len(recs)}")


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


TEMPLATE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Track Coach · __TITLE__</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230c0e14'/><rect x='6' y='14' width='4' height='12' rx='1.6' fill='%23a78bfa'/><rect x='13' y='7' width='4' height='19' rx='1.6' fill='%234cc9f0'/><rect x='20' y='11' width='4' height='15' rx='1.6' fill='%23ffd166'/></svg>">
<style>
:root{--bg:#0c0e14;--panel:#141822;--panel2:#1b2030;--ink:#e8ecf5;--muted:#8b94a8;
 --line:#262c3c;--good:#46d39a;--warn:#ffb454;--bad:#ff6b6b;--bright:#ffd166;--wob:#a78bfa}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#161b2b,var(--bg) 60%);
 color:var(--ink);font:14px/1.5 -apple-system,"SF Pro Display",Inter,Segoe UI,sans-serif;padding:28px}
.wrap{max-width:1120px;margin:0 auto}
h1{font-size:22px;margin:0 0 2px;font-weight:650}
.sub{color:var(--muted);font-size:13px;margin-bottom:22px}
/* VITALS strip — one scannable row of measured spec numbers. */
.vitals{display:flex;flex-wrap:wrap;gap:0;background:var(--panel);border:1px solid var(--line);
 border-radius:14px;padding:4px 6px;margin-bottom:22px;align-items:stretch}
.vitals .vit{display:flex;flex-direction:column;gap:2px;padding:9px 18px;position:relative;flex:1 0 auto}
.vitals .vit+.vit::before{content:"";position:absolute;left:0;top:18%;height:64%;width:1px;background:var(--line)}
.vitals .vlabel{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.7px}
.vitals .vval{font-size:16px;font-weight:650;color:var(--ink);white-space:nowrap}
.vitals .vval small{font-size:11px;color:var(--muted);font-weight:500;margin-left:3px}
.vitals .vval.warn{color:var(--warn)}.vitals .vval.bad{color:var(--bad)}.vitals .vval.good{color:var(--good)}
.vitals .vit[title]{cursor:help}
@media(max-width:760px){.vitals .vit{flex:1 0 33%}.vitals .vit:nth-child(3n+1)::before{display:none}}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.card .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.7px}
.card .v{font-size:16px;font-weight:650;margin-top:6px}
.card .v.good{color:var(--good)}.card .v.warn{color:var(--warn)}.card .v.bad{color:var(--bad)}
.card .cs{font-size:11px;color:var(--muted);margin-top:4px}
.card .ic{color:var(--muted);font-size:10px;opacity:.7}
.card[title]{cursor:help}
.cardhdr{grid-column:1/-1;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.8px;font-weight:700;margin:6px 2px 0}
.cardhdrhint{display:block;text-transform:none;letter-spacing:0;font-weight:400;font-size:11.5px;color:var(--muted);opacity:.85;margin-top:3px}
.formlabel{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.7px;font-weight:700;margin:2px 0 3px}
#formWrap canvas{width:100%;display:block}
.read{border-left:3px solid var(--wob)}
.read #readBody{font-size:14px;line-height:1.65;color:#dce3f2;max-width:820px}
.read #readBody p{margin:0 0 10px}
.read #readBody strong{color:#fff}
.read #readBody h3{font-size:13px;color:var(--bright);margin:14px 0 4px;font-weight:650}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;margin-top:8px;font-weight:600}
.tag.good{background:rgba(70,211,154,.14);color:var(--good)}
.tag.warn{background:rgba(255,180,84,.14);color:var(--warn)}
.tag.bad{background:rgba(255,107,107,.14);color:var(--bad)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:20px;margin-bottom:22px}
.panel h2{font-size:15px;margin:0 0 4px;font-weight:620}
.panel .hint{color:var(--muted);font-size:12px;margin:0 0 16px}
.legend{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:10px;font-size:12px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px}
canvas{width:100%;display:block;border-radius:10px;cursor:crosshair}
.readout{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px;font-size:12.5px;color:var(--muted);
 background:var(--panel2);border-radius:10px;padding:10px 14px;min-height:20px}
.readout b{color:var(--ink);font-weight:600}
.mgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.mcard{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.mcard .z{font-size:12px;color:var(--muted)}.mcard .pct{font-size:20px;font-weight:650;margin-top:3px}
.recs{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:760px){.recs{grid-template-columns:1fr}}
.rec{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--wob);border-radius:12px;padding:14px 16px}
.rec.crit{border-left-color:var(--bad)}.rec.do{border-left-color:var(--good)}.rec.concept{border-left-color:var(--bright)}
.rec h3{margin:0 0 6px;font-size:13.5px;font-weight:640}
.rec .when{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.3px;padding:2px 8px;border-radius:20px;margin-bottom:7px;vertical-align:middle}
.rec .when.tbound{color:var(--bright);background:rgba(255,209,102,.12);border:1px solid rgba(255,209,102,.3)}
.rec .when.glob{color:var(--muted);background:transparent;border:1px solid var(--line)}
.rec.tb{cursor:pointer}
.rec[data-t]:hover{border-color:var(--muted)}
.rec[data-t]:hover .when.tbound{background:rgba(255,209,102,.2)}
.rec p{margin:6px 0 0;font-size:12.8px;color:#cfd6e6}.rec p b{color:#fff}
.rec p.fix{margin-top:9px;padding:7px 10px;background:rgba(70,211,154,.09);border-radius:8px;color:#dfe7d8}
.rec p.fix b{color:#eafff2}
.fixlab{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.4px;color:var(--good);margin-right:6px;text-transform:uppercase}
.empty-note{color:var(--bad);font-size:12px;margin:0 0 12px;font-weight:600}
.foot{color:var(--muted);font-size:11.5px;margin-top:8px;text-align:center}
.scale{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted);margin-top:8px}
.scalebar{height:10px;width:160px;border-radius:5px;background:linear-gradient(90deg,#000004,#3b0f70,#8c2981,#de4968,#fe9f6d,#fcfdbf)}
.presbar{height:10px;width:120px;border-radius:5px;background:linear-gradient(90deg,rgba(70,211,154,.06),rgba(70,211,154,1))}
.ptop{display:flex;align-items:center;gap:14px;margin-bottom:12px}
/* Play = accent-outline, not a loud solid block — matches how --wob is used elsewhere
   (thin accent lines on read/rec/cue), fills in on hover. Smaller than before. */
.pbtn{background:var(--panel2);color:var(--wob);border:1px solid var(--wob);border-radius:9px;padding:7px 15px;font-weight:700;font-size:13px;cursor:pointer;transition:background .15s,color .15s}
.pbtn:hover{background:var(--wob);color:#0c0e14}
.pbtn.pmini{padding:7px 10px;background:var(--panel2);color:var(--muted);border:1px solid var(--line);font-size:13px}
.pbtn.pmini:hover{background:var(--panel2);color:var(--ink)}
.ptime{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13px}
/* timeline callouts ("comments"): triangle cues over the scenes + a duplicated list below */
#storyCues{margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:760px){#storyCues{grid-template-columns:1fr}}
#storyCues .cue{display:flex;gap:10px;align-items:flex-start;background:var(--panel2);
 border:1px solid var(--line);border-left:3px solid var(--wob);border-radius:10px;padding:10px 12px;cursor:pointer;transition:background .15s}
#storyCues .cue:hover,#storyCues .cue.flash{background:rgba(167,139,250,.12)}
#storyCues .cue.crit{border-left-color:var(--bad)}#storyCues .cue.do{border-left-color:var(--good)}#storyCues .cue.concept{border-left-color:var(--bright)}
#storyCues .cuelet{flex:none;width:20px;height:20px;border-radius:6px;background:var(--wob);color:#0c0e14;
 font-weight:800;font-size:11px;text-align:center;line-height:20px;text-transform:uppercase}
#storyCues .cue.crit .cuelet{background:var(--bad)}#storyCues .cue.do .cuelet{background:var(--good)}#storyCues .cue.concept .cuelet{background:var(--bright)}
#storyCues .cuebody{flex:1;min-width:0}
#storyCues .cuewhen{font-size:10.5px;color:var(--muted);font-weight:600;letter-spacing:.3px}
#storyCues .cueh{font-size:12.8px;font-weight:640;margin:2px 0 0}
#storyCues .cuep{font-size:12px;color:#cfd6e6;margin:4px 0 0}
.cueshdr{grid-column:1/-1;font-size:11px;color:var(--muted);font-weight:600;letter-spacing:.4px;text-transform:uppercase;margin-top:2px}
.ctip{position:fixed;z-index:60;pointer-events:none;display:none;background:rgba(12,14,20,.96);
 border:1px solid var(--line);border-radius:9px;padding:7px 11px;font-size:12.5px;color:var(--ink);
 line-height:1.55;max-width:260px;box-shadow:0 6px 20px rgba(0,0,0,.45)}
.ctip b{font-weight:650}.ctip .tdim{color:var(--muted)}
.pstems{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.pstem{display:flex;align-items:center;gap:8px;background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.pstem .nm{flex:1;font-size:12.5px;font-weight:600}
.pstem button{background:transparent;border:1px solid var(--line);color:var(--muted);border-radius:6px;font-size:10.5px;padding:3px 7px;cursor:pointer;font-weight:600}
.pstem button.on{color:#0c0e14}
.pstem button.mute.on{background:var(--bad);border-color:var(--bad)}
.pstem button.solo.on{background:var(--good);border-color:var(--good)}
.ltog{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.ltog .lbl{font-size:11px;color:var(--muted);margin-right:2px}
.ltog button{background:var(--panel2);border:1px solid var(--line);color:var(--muted);
 border-radius:8px;font-size:11px;padding:4px 10px;cursor:pointer;font-weight:600}
.ltog button.on{background:var(--wob);border-color:var(--wob);color:#0c0e14}
/* sequencer legend: explains height=loudness, colour=frequency, M/S, weak */
.seqkey{display:flex;flex-wrap:wrap;align-items:center;gap:7px 16px;margin-top:10px;
 font-size:11px;color:var(--muted);line-height:1.5}
.seqkey b{color:var(--ink);font-weight:600}
.seqkey .sw{display:inline-block;width:46px;height:9px;border-radius:3px;vertical-align:middle;margin-right:5px}
.seqkey .chip{display:inline-flex;align-items:center}
.seqkey .ms{display:inline-block;min-width:13px;height:13px;line-height:13px;text-align:center;
 border-radius:3px;font-size:8px;font-weight:700;color:#0c0e14;margin-right:4px}
/* collapsed "evidence & detail" drawer for the power-user panels */
.more{margin:22px 0 0;border-top:1px solid var(--line);padding-top:6px}
.more>summary{cursor:pointer;list-style:none;color:var(--muted);font-size:13px;font-weight:600;
 padding:10px 2px;user-select:none}
.more>summary::-webkit-details-marker{display:none}
.more>summary::before{content:"▸ ";color:var(--accent,#a78bfa)}
.more[open]>summary::before{content:"▾ "}
.more[open]>summary{color:var(--ink)}
</style></head><body><div class="wrap">
<div class="ctip" id="ctip"></div>
<h1 id="title"></h1><div class="sub" id="sub"></div>

<!-- VITALS — the credible spec-sheet, read in one glance, builds trust.
     Single authoritative numbers about the finished mix (no time axis). -->
<div class="vitals" id="vitals"></div>

<!-- 1. VISUAL FIRST: Track Story + player/sequencer is the centrepiece & the proof. -->
<div class="panel" id="storyPanel">
 <h2 id="storyTitle"></h2><p class="hint" id="storyHint"></p>
 <div id="formWrap" style="display:none"><div class="formlabel" id="formLabel"></div>
  <canvas id="formlane" height="40" style="cursor:pointer"></canvas></div>
 <canvas id="story" height="300"></canvas>
 <div id="playerControls">
  <canvas id="stemlanes" height="200" style="margin-top:12px;cursor:pointer"></canvas>
  <div class="ptop" style="margin-top:10px">
   <button class="pbtn pmini" id="rewBtn" title="Back to start">&#9198;</button>
   <button class="pbtn" id="playBtn"></button>
   <span class="ptime" id="playTime">0:00 / 0:00</span>
  </div>
  <div class="seqkey" id="seqKey"></div>
  <p class="hint" id="playNote" style="margin:10px 0 0"></p>
  <div id="playAudios" style="display:none"></div>
 </div>
 <div id="storyCues"></div>
</div>

<!-- 2. THE READ: the diagnosis in prose, sits under the visual. -->
<div class="panel read" id="readPanel" style="display:none">
 <h2 id="readTitle"></h2>
 <div id="readBody"></div>
</div>

<!-- 3. RECOMMENDATIONS: what to change. Some are time-bound (a moment in the
     track), some are global — shown visually, not just by a click. -->
<div class="panel" id="recsPanel">
 <h2 id="recsTitle"></h2><p class="hint" id="recsHint"></p>
 <div class="legend" id="recLegend" style="margin-bottom:14px"></div>
 <div class="recs" id="recs"></div>
</div>

<details class="more" id="evidence">
 <summary>Evidence &amp; detail — tonal balance, the project arrangement, stem↔track map, rhythm and transcribed notes (click to open)</summary>

 <div class="panel" id="tonalPanel">
  <h2>Tonal balance — average spectrum of the mix</h2>
  <p class="hint">Each bar is one octave band's level across the whole track (0 dB = loudest band). A band that sticks out from its neighbours is a resonance (boxy/harsh); a dip is a hole (dull/thin).</p>
  <canvas id="tonal" height="170"></canvas>
 </div>

 <div class="panel" id="arrPanel">
  <h2 id="arrTitle"></h2><p class="hint" id="arrHint"></p>
  <div class="legend" id="arrLegend"></div>
  <canvas id="arr" height="300"></canvas>
  <div class="readout" id="arrReadout"></div>
 </div>

 <div class="panel" id="mapPanel">
  <h2 id="mapTitle"></h2><p class="hint" id="mapHint"></p>
  <div class="mgrid" id="mapRows"></div>
  <div id="mapNotes" style="margin-top:14px"></div>
 </div>

 <div class="panel" id="rhyPanel">
  <h2 id="rhyTitle"></h2><p class="hint" id="rhyHint"></p>
  <div class="mgrid" id="rhyRows"></div>
  <div id="rhySep" style="margin-top:14px"></div>
 </div>

 <div class="panel" id="notePanel">
  <h2 id="noteTitle"></h2><p class="hint" id="noteHint"></p>
  <canvas id="note" height="260"></canvas>
  <div class="readout" id="noteReadout"></div>
 </div>
</details>

<div class="foot" id="foot"></div>
</div>
<script>
const D=__PAYLOAD__, T=D.t;
const fmtT=s=>(s<0?"0:00":Math.floor(s/60)+":"+String(Math.round(s%60)).padStart(2,"0"));
// Timeline callouts ("comments"): the located recommendations, in time order, each
// given a letter (a,b,c…). The same list drives the triangle cues over the scenes,
// the list under the story, and the letter badges in "Start here" — one shared identity.
const CUELET="abcdefghijklmnopqrstuvwxyz";
const CUES=(D.recs||[]).map((r,i)=>({r,i})).filter(o=>o.r.t!=null)
  .sort((a,b)=>a.r.t-b.r.t).map((o,k)=>({r:o.r,idx:o.i,t:+o.r.t,letter:CUELET[k]||"•",cls:o.r.cls||""}));
const cueByIdx={};CUES.forEach(c=>{cueByIdx[c.idx]=c;});
function flashCue(letter){const el=document.querySelector('#storyCues .cue[data-let="'+letter+'"]');
 if(!el)return;el.classList.add("flash");el.scrollIntoView({behavior:"smooth",block:"center"});
 setTimeout(()=>el.classList.remove("flash"),1400);}
document.getElementById("title").textContent="Track Coach · "+document.title.replace("Track Coach · ","");
document.getElementById("sub").textContent=`${fmtT(D.dur)} · ${D.tempo} BPM · ${T.subtitle}`;
if(D.narrative){
 const esc=s=>s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
 const inline=s=>esc(s).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/\*(.+?)\*/g,"<em>$1</em>");
 const html=D.narrative.split(/\n{2,}/).map(blk=>{const t=blk.trim();if(!t)return"";
  if(t.startsWith("### "))return `<h3>${inline(t.slice(4))}</h3>`;
  if(t.startsWith("## "))return `<h3>${inline(t.slice(3))}</h3>`;
  return `<p>${inline(t).replace(/\n/g,"<br>")}</p>`;}).join("");
 document.getElementById("readTitle").textContent=T.read_title;
 document.getElementById("readBody").innerHTML=html;
 document.getElementById("readPanel").style.display="";
}
document.getElementById("arrTitle").textContent=T.arr_title;
document.getElementById("arrReadout").textContent=T.hover;
document.getElementById("recsTitle").textContent=T.recs_title;
document.getElementById("recsHint").textContent=T.recs_hint;
document.getElementById("recLegend").innerHTML=
 `<span><i style="background:var(--bad)"></i>${T.legend_crit}</span>`+
 `<span><i style="background:var(--good)"></i>${T.legend_do}</span>`+
 `<span><i style="background:var(--bright)"></i>${T.legend_concept}</span>`;
document.getElementById("foot").textContent=(T.footer||"").replace("{ver}",D.version||"");
// sequencer legend — what the lane drawing actually encodes (two dimensions + controls)
(function(){const el=document.getElementById("seqKey");if(!el)return;
 const stk="linear-gradient(0deg,rgb(255,78,80) 0 34%,rgb(76,214,140) 34% 67%,rgb(80,168,255) 67% 100%)";
 el.innerHTML=
  `<span class="chip"><span class="sw" style="background:${stk}"></span><b>Stacked layers</b>&nbsp;= `+
   `<b style="color:rgb(255,78,80)">bass</b> / <b style="color:rgb(76,214,140)">mids</b> / <b style="color:rgb(80,168,255)">highs</b>, bottom→top. `+
   `Taller band = more energy there; several tall at once = they hit together.</span>`+
  `<span class="chip"><b>≈&nbsp;name</b>&nbsp;= which project track this stem sounds like (only when we're confident)</span>`;
})();
// canvases inside the collapsed <details> have 0 width until it opens — re-run every
// resize() handler on first open so the arrangement / notes charts draw at full width.
(function(){const ev=document.getElementById("evidence");if(!ev)return;
 ev.addEventListener("toggle",()=>{if(ev.open)window.dispatchEvent(new Event("resize"));});})();

// VITALS strip — the credible spec-sheet at the top. Single measured numbers
// about the finished mix; some get a warn/bad colour when they cross a known
// threshold (e.g. true peak over 0 dBTP = inter-sample clipping).
(function(){const el=document.getElementById("vitals");const V=D.vitals||{};if(!el||!Object.keys(V).length){if(el)el.style.display="none";return;}
 const items=[];
 const push=(label,val,cls,tip)=>{if(val==null||val==="")return;items.push({label,val,cls:cls||"",tip:tip||""});};
 const fmtDur=s=>{s=Math.round(s);return Math.floor(s/60)+":"+String(s%60).padStart(2,"0");};
 push("Tempo",(V.tempo_bpm!=null?V.tempo_bpm+" <small>BPM</small>":null),"","Detected from the audio. May differ ±1–2 from the project tempo.");
 push("Key",V.key+(V.key_conf!=null?` <small>conf ${V.key_conf}</small>`:""),"","Estimated key/scale (Krumhansl-Schmuckler on chroma). A confidence near 0 means ambiguous/atonal.");
 push("Length",(V.duration_s!=null?fmtDur(V.duration_s):null),"","Track length.");
 const tsc=(V.time_sig_changes||[]).length;
 push("Metre",(V.time_sig?V.time_sig+(tsc>1?` <small>+${tsc-1} change${tsc>2?"s":""}</small>`:""):null),
   "","Time signature from the project. "+(tsc>1?"It changes mid-track — see the marks on the timeline.":"Constant across the track."));
 push("Loudness",(V.lufs!=null?V.lufs+" <small>LUFS</small>":null),(V.lufs!=null&&V.lufs>-7?"warn":""),"Integrated loudness (ITU-R BS.1770). Streaming targets ~ −14 LUFS; club/loud masters −7…−9.");
 push("True peak",(V.true_peak_db!=null?(V.true_peak_db>0?"+":"")+V.true_peak_db+" <small>dBTP</small>":null),(V.true_peak_db!=null&&V.true_peak_db>0?"bad":(V.true_peak_db!=null&&V.true_peak_db>-1?"warn":"")),"Inter-sample peak (4× oversampled). Above 0 dBTP risks clipping on conversion/codecs — leave ~ −1 dBTP headroom.");
 push("Dynamics",(V.dynamic_range_db!=null?"DR "+V.dynamic_range_db:null),(V.dynamic_range_db!=null&&V.dynamic_range_db<6?"warn":""),"Peak-to-RMS (crest) of the whole mix in dB. Higher = punchy/dynamic; under ~6 = heavily limited/squashed.");
 push("Stereo",(V.stereo_width!=null?"width "+V.stereo_width:null),"","Side / (mid+side) energy. 0 = mono/centred, toward 1 = wide.");
 push("Phase",(V.phase_corr!=null?(V.phase_corr>0?"+":"")+V.phase_corr:null),
   (V.phase_corr!=null&&V.phase_corr<0?"bad":(V.phase_corr!=null&&V.phase_corr<0.3?"warn":"")),
   "L/R correlation (mono-compatibility). +1 = mono-safe, ~0.3–0.7 = healthy wide, near 0 = very wide, BELOW 0 = out of phase — the low end can cancel/vanish on a mono club system. Check anything under ~0.3.");
 el.innerHTML=items.map(it=>`<div class="vit" title="${it.tip.replace(/"/g,'&quot;')}"><span class="vlabel">${it.label}</span><span class="vval ${it.cls}">${it.val}</span></div>`).join("");
})();
// Located recs link to the timeline by CLICK (seek + scroll to the story), not by a
// numbered pin on the curve — the pins read as if every rec were an equal standalone tip,
// which they aren't. The single actionable list lives here in "Start here".
// Time-bound recs (r.t != null) carry a ⏱ clock chip with the timecode and are
// clickable (jump). Global recs get a quiet "whole track" chip — the distinction
// is visual, not just behavioural.
document.getElementById("recs").innerHTML=D.recs.map((r,i)=>{
 const tb=r.t!=null;
 const jump=tb?` data-t="${r.t}" style="cursor:pointer" title="Jump to ${r.when}"`:"";
 const fix=r.fix?`<p class="fix"><span class="fixlab">→ Try</span> ${r.fix}</p>`:"";
 const cue=cueByIdx[i];const tag=cue?`<b style="color:var(--ink);text-transform:uppercase">${cue.letter}</b> `:"";
 const chip=tb?`<span class="when tbound">⏱ ${r.when}</span>`:`<span class="when glob">whole track</span>`;
 return `<div class="rec ${r.cls}${tb?' tb':''}"${jump}>${tag}${chip}<h3>${r.h}</h3><p>${r.p}</p>${fix}</div>`;}).join("")||"<p class='hint'>—</p>";
document.getElementById("recs").querySelectorAll(".rec[data-t]").forEach(el=>
 el.onclick=()=>{const t=+el.dataset.t;if(window.__seek)window.__seek(t);
  document.getElementById("storyPanel").scrollIntoView({behavior:"smooth",block:"start"});});

const getCss=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
// floating tooltip that follows the cursor over a chart (replaces the fixed bottom readout)
const _tip=document.getElementById("ctip");
function showTip(e,html){_tip.innerHTML=html;_tip.style.display="block";
 const pad=14,w=_tip.offsetWidth,h=_tip.offsetHeight;
 let x=e.clientX+pad,y=e.clientY+pad;
 if(x+w>innerWidth-8)x=e.clientX-w-pad;if(y+h>innerHeight-8)y=e.clientY-h-pad;
 _tip.style.left=Math.max(8,x)+"px";_tip.style.top=Math.max(8,y)+"px";}
function hideTip(){_tip.style.display="none";}
const ALS=D.als;
const PH=[];          // playhead redraw callbacks, one per timeline canvas (Part E)
window.__seek=null;   // set by the player; canvases call it on click to jump
// Shared locator overlay: faint vertical lines + labels at the top, from the .als markers.
function drawLocators(ctx,xOf,top,bot,labelY){
 if(!ALS||!ALS.markers||!ALS.markers.length)return;
 ctx.save();
 ALS.markers.forEach(m=>{const x=xOf(m.t);
  ctx.strokeStyle="rgba(120,200,255,.28)";ctx.lineWidth=1;ctx.setLineDash([3,3]);
  ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,bot);ctx.stroke();
  if(labelY!=null){ctx.setLineDash([]);ctx.fillStyle="rgba(120,200,255,.85)";
   ctx.font="600 9px sans-serif";ctx.textAlign="center";ctx.fillText(m.name,x,labelY);}});
 ctx.setLineDash([]);ctx.restore();
}

// ── Track Story: scenes + power curve + moments + family texture (the hero map) ──
(function(){
 const ST=D.story,P=document.getElementById("storyPanel");
 if(!ST||!ST.bins||!ST.bins.length){P.style.display="none";return;}
 document.getElementById("storyTitle").textContent=T.story_title;
 document.getElementById("storyHint").textContent=T.story_hint;
 const cv=document.getElementById("story"),ctx=cv.getContext("2d");
 const PADL=70,PADR=14,PADT=30,PADB=22,RIB=24,MOM=18,CUR=112,rowH=12,gap=8;
 // colour for a callout cue/triangle by its rec class (crit/do/concept)
 const cueCol=cls=>cls==="crit"?getCss("--bad"):cls==="do"?getCss("--good"):cls==="concept"?getCss("--bright"):getCss("--wob");
 const fams=ST.families||[],nf=fams.length,bins=ST.bins,iv=ST.intensity,nb=bins.length;
 const comps=ST.components||[],ncomp=comps.length,compLaneH=20;
 const curveTop=PADT+RIB+MOM,compTop=curveTop+CUR+10,famBot=()=>famTop+nf*rowH;
 let famTop=compTop+ncomp*compLaneH+gap;
 let W,H;const xOf=t=>PADL+(t/ST.dur)*(W-PADL-PADR);
 const SC=[[0,38,50,74],[0.5,63,111,158],[0.8,224,137,74],[1,255,93,115]];
 const tcol=v=>{v=Math.max(0,Math.min(1,v));for(let i=0;i<SC.length-1;i++){const a=SC[i],b=SC[i+1];
  if(v<=b[0]){const f=(v-a[0])/((b[0]-a[0])||1);return `rgb(${a[1]+(b[1]-a[1])*f|0},${a[2]+(b[2]-a[2])*f|0},${a[3]+(b[3]-a[3])*f|0})`;}}return "rgb(255,93,115)";};
 const imax=Math.max.apply(null,iv);
 function resize(){W=cv.clientWidth;famTop=compTop+ncomp*compLaneH+gap;H=famTop+nf*rowH+PADB;cv.style.height=H+"px";
  cv.width=W*devicePixelRatio;cv.height=H*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);draw();}
 function draw(hx){ctx.clearRect(0,0,W,H);
  ST.scenes.forEach(s=>{const x0=xOf(s.t0),x1=xOf(s.t1);ctx.globalAlpha=.85;ctx.fillStyle=tcol(s.tier);ctx.fillRect(x0,PADT,Math.max(1,x1-x0-1),RIB);ctx.globalAlpha=1;
   if(x1-x0>44){ctx.fillStyle="rgba(255,255,255,.95)";ctx.font="600 11px sans-serif";ctx.textAlign="left";ctx.fillText(s.letter+"  "+s.name,x0+6,PADT+16);}});
  // callout cues: downward triangles over the scenes (a,b,c…), click to read below. Touch-friendly.
  CUES.forEach(c=>{const x=xOf(c.t),col=cueCol(c.cls),ct=8,cb=23;
   ctx.fillStyle=col;ctx.beginPath();ctx.moveTo(x-8,ct);ctx.lineTo(x+8,ct);ctx.lineTo(x,cb);ctx.closePath();ctx.fill();
   ctx.fillStyle="#0c0e14";ctx.font="800 10px sans-serif";ctx.textAlign="center";ctx.textBaseline="middle";
   ctx.fillText(c.letter.toUpperCase(),x,ct+6);ctx.textBaseline="alphabetic";});
  ctx.beginPath();bins.forEach((t,j)=>{const x=xOf(t),y=curveTop+CUR-iv[j]*CUR;j?ctx.lineTo(x,y):ctx.moveTo(x,y);});
  ctx.lineTo(xOf(bins[nb-1]),curveTop+CUR);ctx.lineTo(xOf(bins[0]),curveTop+CUR);ctx.closePath();
  const g=ctx.createLinearGradient(0,curveTop,0,curveTop+CUR);g.addColorStop(0,"#a78bfa66");g.addColorStop(1,"#a78bfa08");ctx.fillStyle=g;ctx.fill();
  ctx.beginPath();bins.forEach((t,j)=>{const x=xOf(t),y=curveTop+CUR-iv[j]*CUR;j?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.strokeStyle="#a78bfa";ctx.lineWidth=2;ctx.stroke();
  const cx=xOf(ST.climax_t),cy=curveTop+CUR-imax*CUR;ctx.fillStyle="#ffd166";ctx.font="15px sans-serif";ctx.textAlign="center";ctx.fillText("★",cx,cy-2);
  (ST.moments||[]).forEach(m=>{const x=xOf(m.t);ctx.strokeStyle="rgba(255,255,255,.22)";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,PADT+RIB);ctx.lineTo(x,famTop);ctx.stroke();
   ctx.fillStyle="#cfd6e6";ctx.font="10px sans-serif";ctx.textAlign="center";ctx.fillText("◆ "+m.label,x,PADT+RIB+13);});
  // component lanes — the power curve decomposed + character dims
  comps.forEach((c,ci)=>{const y0=compTop+ci*compLaneH;
   ctx.fillStyle=getCss("--muted");ctx.font="9px sans-serif";ctx.textAlign="right";ctx.fillText(c.label,PADL-8,y0+compLaneH/2+3);
   ctx.strokeStyle=getCss("--line");ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(PADL,y0+compLaneH-2);ctx.lineTo(W-PADR,y0+compLaneH-2);ctx.stroke();ctx.globalAlpha=1;
   ctx.strokeStyle=c.col;ctx.lineWidth=1.3;ctx.beginPath();
   c.vals.forEach((v,j)=>{const x=xOf(bins[j]),yy=y0+compLaneH-2-v*(compLaneH-4);j?ctx.lineTo(x,yy):ctx.moveTo(x,yy);});ctx.stroke();
   // verdict word at the right edge — the over-time conclusion lives ON the lane.
   // Drawn on a small dark pill so it stays legible over the curve's right end.
   if(c.verdict){ctx.font="600 9.5px sans-serif";const tw=ctx.measureText(c.verdict).width;
    const px=W-PADR-tw-7,py=y0+compLaneH/2;
    ctx.fillStyle="rgba(12,14,20,.82)";if(ctx.roundRect){ctx.beginPath();ctx.roundRect(px-4,py-7,tw+8,14,4);ctx.fill();}else{ctx.fillRect(px-4,py-7,tw+8,14);}
    ctx.fillStyle=c.col;ctx.textAlign="left";ctx.textBaseline="middle";
    ctx.fillText(c.verdict,px,py);ctx.textBaseline="alphabetic";}});
  fams.forEach((f,i)=>{const y=famTop+i*rowH;ctx.fillStyle=getCss("--muted");ctx.font="600 10px sans-serif";ctx.textAlign="right";ctx.fillText(f.name,PADL-8,y+9);
   f.intervals.forEach(p=>{ctx.fillStyle=f.col+"cc";ctx.fillRect(xOf(p[0]),y+2,Math.max(1.5,xOf(p[1])-xOf(p[0])),rowH-4);});});
  drawLocators(ctx,xOf,PADT,famBot(),11);
  // time-signature changes (from the .als) — labelled marks where the metre switches.
  // Skips the initial signature; nothing drawn when the metre is constant.
  const TSC=(D.vitals&&D.vitals.time_sig_changes)||[];
  if(TSC.length>1)TSC.slice(1).forEach(c=>{const x=xOf(c.time_s);
   ctx.strokeStyle="#ffd166";ctx.lineWidth=1;ctx.setLineDash([2,2]);ctx.beginPath();ctx.moveTo(x,PADT);ctx.lineTo(x,famBot());ctx.stroke();ctx.setLineDash([]);
   ctx.fillStyle="#ffd166";ctx.font="700 9px sans-serif";ctx.textAlign="center";ctx.fillText(c.sig,x,famBot()+10);});
  ctx.fillStyle=getCss("--muted");ctx.font="10px sans-serif";ctx.textAlign="center";for(let t=0;t<=ST.dur;t+=60)ctx.fillText(fmtT(t),xOf(t),H-7);
  if(hx!=null){ctx.strokeStyle="rgba(255,255,255,.6)";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(hx,PADT);ctx.lineTo(hx,famBot());ctx.stroke();}}
 // find a callout cue under the cursor (the triangle band sits just above the scenes)
 function cueAt(mx,my){if(my<4||my>26)return null;let best=null,bd=11;
  CUES.forEach(c=>{const d=Math.abs(mx-xOf(c.t));if(d<bd){bd=d;best=c;}});return best;}
 cv.addEventListener("mousemove",e=>{const r=cv.getBoundingClientRect();const mx=e.clientX-r.left,my=e.clientY-r.top;
  const cue=cueAt(mx,my);cv.style.cursor=cue?"pointer":"default";
  const t=Math.max(0,Math.min(ST.dur,(mx-PADL)/(W-PADL-PADR)*ST.dur));draw(xOf(t));
  if(cue){showTip(e,`<b>${cue.letter.toUpperCase()} · ${cue.r.when}</b><br>${cue.r.h}<br><span class="tdim">click to read below</span>`);return;}
  const sc=ST.scenes.find(s=>t>=s.t0&&t<s.t1);const on=fams.filter(f=>f.intervals.some(p=>t>=p[0]&&t<=p[1])).map(f=>f.name);
  showTip(e,`<b>${fmtT(t)}</b>`+(sc?` · <b>${sc.letter} ${sc.name}</b>`:"")+(on.length?`<br><span class="tdim">playing: ${on.join(", ")}</span>`:""));});
 cv.addEventListener("mouseleave",()=>{draw();hideTip();cv.style.cursor="default";});
 cv.addEventListener("click",e=>{const r=cv.getBoundingClientRect();const mx=e.clientX-r.left,my=e.clientY-r.top;
  const cue=cueAt(mx,my);
  if(cue){if(window.__seek)window.__seek(cue.t);flashCue(cue.letter);return;}
  const t=Math.max(0,Math.min(ST.dur,(mx-PADL)/(W-PADL-PADR)*ST.dur));if(window.__seek)window.__seek(t);});
 PH.push(t=>draw(xOf(t)));
 // duplicated list of the same callouts, under the player — touch-friendly, no hover needed
 (function(){const box=document.getElementById("storyCues");if(!box)return;
  if(!CUES.length){box.style.display="none";return;}
  box.innerHTML=`<div class="cueshdr">${T.cues_title||"Callouts on the timeline — tap a triangle above, or an item here"}</div>`+
   CUES.map(c=>{const fx=c.r.fix?`<div class="cuep" style="color:#dfe7d8">→ ${c.r.fix}</div>`:"";
    return `<div class="cue ${c.cls}" data-let="${c.letter}" data-t="${c.t}">`+
     `<div class="cuelet">${c.letter}</div><div class="cuebody">`+
     `<div class="cuewhen">${c.r.when}</div><div class="cueh">${c.r.h}</div>`+
     `<div class="cuep">${c.r.p}</div>${fx}</div></div>`;}).join("");
  box.querySelectorAll(".cue").forEach(el=>el.onclick=()=>{const t=+el.dataset.t;
   if(window.__seek)window.__seek(t);document.getElementById("storyPanel").scrollIntoView({behavior:"smooth",block:"start"});});})();
 window.addEventListener("resize",resize);resize();
})();

// ── Form / repeats lane: audio self-similarity (chroma/MFCC → Laplacian segmentation).
// Coloured blocks per section; SAME colour + SAME letter = the same musical material
// coming back (a reprise), not just "something changed". Aligned to the story scale.
(function(){
 const SS=D.selfsim||[],wrap=document.getElementById("formWrap");
 if(!wrap||SS.length<2){if(wrap)wrap.style.display="none";return;}
 wrap.style.display="block";
 const cv=document.getElementById("formlane"),ctx=cv.getContext("2d");
 const PADL=70,PADR=14;const dur=D.dur||SS[SS.length-1].t1;
 // stable colour per letter; repeated letters reuse the same hue → repeats look alike
 const PAL=["#5b8cff","#46d39a","#ffb454","#c77dff","#5ad1c2","#ff6b9d"];
 const letters=[...new Set(SS.map(s=>s.letter))];
 const colOf=L=>PAL[letters.indexOf(L)%PAL.length];
 const reps=new Set();{const seen={};SS.forEach(s=>{if(seen[s.letter])reps.add(s.letter);seen[s.letter]=1;});}
 // Lead is only worth showing if it actually VARIES between sections. When Demucs lumps
 // every melodic part into one stem ("other" everywhere), a uniform "lead: other" is noise.
 const leadVaries=new Set(SS.map(s=>s.lead).filter(Boolean)).size>1;
 const nrep=reps.size;
 document.getElementById("formLabel").textContent=(T.form_label||"Form — same colour = the same part returns")
   +(nrep?`  (↻ ${[...reps].join(", ")} repeat)`:"  (no repeats detected)");
 let W=0,H=40,hx=null;
 const xOf=t=>PADL+(t/dur)*(W-PADL-PADR);
 function draw(px){ctx.clearRect(0,0,W,H);
  SS.forEach(s=>{const x0=xOf(s.t0),x1=xOf(s.t1),w=Math.max(2,x1-x0-1),rep=reps.has(s.letter),c=colOf(s.letter);
   ctx.fillStyle=c+(rep?"":"99");ctx.fillRect(x0,6,w,H-12);
   if(rep){ctx.strokeStyle=c;ctx.lineWidth=1.5;ctx.strokeRect(x0+.5,6.5,w-1,H-13);}
   if(w>13){const cx=(x0+x1)/2;ctx.fillStyle="#0c0e14";ctx.textAlign="center";ctx.textBaseline="middle";
    if(s.lead&&leadVaries&&w>52){ctx.font="800 11px sans-serif";ctx.fillText(s.letter,cx,H/2-5);
     ctx.font="700 9px sans-serif";ctx.fillText("lead: "+s.lead,cx,H/2+7);}
    else{ctx.font="800 11px sans-serif";ctx.fillText(s.letter,cx,H/2);}ctx.textBaseline="alphabetic";}});
  if(px!=null){ctx.strokeStyle="rgba(255,255,255,.7)";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(px,2);ctx.lineTo(px,H-2);ctx.stroke();}}
 function resize(){W=cv.clientWidth||cv.parentNode.clientWidth;cv.width=W;cv.height=H;draw(hx);}
 cv.addEventListener("mousemove",e=>{const r=cv.getBoundingClientRect(),mx=e.clientX-r.left;
  const t=Math.max(0,Math.min(dur,(mx-PADL)/(W-PADL-PADR)*dur));const s=SS.find(s=>t>=s.t0&&t<s.t1);
  if(s)showTip(e,`<b>Part ${s.letter}</b> · ${fmtT(s.t0)}–${fmtT(s.t1)}`+(s.lead&&leadVaries?` · <span class="tdim">lead: ${s.lead}</span>`:"")+(reps.has(s.letter)?`<br><span class="tdim">this material returns elsewhere</span>`:""));});
 cv.addEventListener("mouseleave",hideTip);
 cv.addEventListener("click",e=>{const r=cv.getBoundingClientRect(),mx=e.clientX-r.left;
  const t=Math.max(0,Math.min(dur,(mx-PADL)/(W-PADL-PADR)*dur));if(window.__seek)window.__seek(t);});
 PH.push(t=>{hx=xOf(t);draw(hx);});
 window.addEventListener("resize",resize);resize();
})();

// ── Tonal balance: average mix spectrum per octave band, with deviation flags. ──
(function(){
 const TB=D.tonal_balance||[],P=document.getElementById("tonalPanel");
 if(!P||TB.length<3){if(P)P.style.display="none";return;}
 const cv=document.getElementById("tonal"),ctx=cv.getContext("2d");
 let W=0,H=170;const PADL=8,PADR=8,PADB=34,PADT=12;
 function draw(){W=cv.clientWidth;cv.width=W*devicePixelRatio;cv.height=H*devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);ctx.clearRect(0,0,W,H);
  const n=TB.length,gap=8,bw=(W-PADL-PADR-gap*(n-1))/n;
  const lo=Math.min(...TB.map(b=>b.rel_db));const span=Math.max(8,-lo);
  const yOf=db=>PADT+(-db/span)*(H-PADT-PADB);
  // baseline (0 dB = loudest band)
  ctx.strokeStyle=getCss("--line");ctx.beginPath();ctx.moveTo(PADL,yOf(0));ctx.lineTo(W-PADR,yOf(0));ctx.stroke();
  TB.forEach((b,i)=>{const x=PADL+i*(bw+gap),y=yOf(b.rel_db),hot=Math.abs(b.dev_db)>=4;
   // colour by frequency region (low red → mid green → high blue), brighter if flagged
   const t=i/(n-1);const c=t<.5?[255-(t*2)*(255-76),78+(t*2)*(214-78),80+(t*2)*(140-80)]
                              :[76-((t-.5)*2)*(76-80),214-((t-.5)*2)*(214-168),140+((t-.5)*2)*(255-140)];
   ctx.globalAlpha=hot?1:.55;ctx.fillStyle="rgb("+(c[0]|0)+","+(c[1]|0)+","+(c[2]|0)+")";
   ctx.fillRect(x,y,bw,yOf(lo)-y+0.5);ctx.globalAlpha=1;
   if(hot){ctx.fillStyle=b.dev_db>0?getCss("--bad"):getCss("--warn");ctx.font="700 10px sans-serif";ctx.textAlign="center";
    ctx.fillText((b.dev_db>0?"+":"")+b.dev_db,x+bw/2,y-3);}
   ctx.fillStyle=getCss("--muted");ctx.font="9px sans-serif";ctx.textAlign="center";ctx.fillText(b.band,x+bw/2,H-19);});
  ctx.fillStyle=getCss("--muted");ctx.font="9px sans-serif";ctx.textAlign="center";ctx.fillText("Hz",W/2,H-6);}
 // canvas in a collapsed <details> has 0 width until opened → redraw on open + resize
 window.addEventListener("resize",draw);
 const ev=document.getElementById("evidence");if(ev)ev.addEventListener("toggle",()=>{if(ev.open)draw();});
 draw();
})();


(function(){
 const A=ALS,P=document.getElementById("arrPanel");
 if(!A||!A.lanes||!A.lanes.length){P.style.display="none";return;}
 document.getElementById("arrHint").textContent=T.arr_hint+
  (A.offset_s!=null?"  ("+T.arr_aligned.replace("{off}",fmtT(A.offset_s))+")":"");
 // legend: families actually present, in display order
 const FAM=[["kick","#ff5d73"],["bass","#a78bfa"],["drums","#4cc9f0"],["hats","#5ad1c2"],["chord","#46d39a"],["lead","#ffd166"],["other","#8b94a8"]];
 const present=new Set(A.lanes.map(l=>l.fam));
 document.getElementById("arrLegend").innerHTML=FAM.filter(f=>present.has(f[0]))
  .map(f=>`<span><i style="background:${f[1]}"></i>${f[0]}</span>`).join("");
 // peak note-density (notes/sec) across all clips, for brightness scaling
 let dmax=0;A.lanes.forEach(l=>l.intervals.forEach(iv=>{const d=iv[2]/Math.max(.2,iv[1]-iv[0]);if(d>dmax)dmax=d;}));
 const cv=document.getElementById("arr"),ctx=cv.getContext("2d");
 const PADL=128,PADR=14,PADT=16,PADB=24,rowGap=3;const n=A.lanes.length;
 let W,H,rowH;const xOf=t=>PADL+(t/D.dur)*(W-PADL-PADR);
 function resize(){W=cv.clientWidth;rowH=11;H=PADT+PADB+n*(rowH+rowGap);cv.style.height=H+"px";
  cv.width=W*devicePixelRatio;cv.height=H*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);draw();}
 function draw(hx){ctx.clearRect(0,0,W,H);
  A.lanes.forEach((l,i)=>{const y=PADT+i*(rowH+rowGap);
   ctx.fillStyle=getCss("--muted");ctx.font="600 10px sans-serif";ctx.textAlign="right";
   ctx.fillText(l.name.length>20?l.name.slice(0,19)+"…":l.name,PADL-8,y+rowH-2);
   const audio=l.kind==="audio";
   l.intervals.forEach(iv=>{const x0=xOf(iv[0]),x1=xOf(iv[1]),w=Math.max(1.5,x1-x0);
    if(audio){ // audio clips: thinner centred strip, fixed tone
     ctx.fillStyle=l.col+"73";ctx.fillRect(x0,y+rowH*0.25,w,rowH*0.5);
    }else{     // MIDI: full-height block, brightness = note density
     const dens=iv[2]/Math.max(.2,iv[1]-iv[0]);const a=(.35+.65*(dmax?dens/dmax:0)).toFixed(2);
     ctx.fillStyle=l.col+Math.round(a*255).toString(16).padStart(2,"0");ctx.fillRect(x0,y,w,rowH);}});});
  drawLocators(ctx,xOf,PADT-4,H-PADB,9);
  ctx.fillStyle=getCss("--muted");ctx.font="10px sans-serif";ctx.textAlign="center";
  for(let t=0;t<=D.dur;t+=60)ctx.fillText(fmtT(t),xOf(t),H-8);
  if(hx!=null){ctx.strokeStyle="rgba(255,255,255,.5)";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(hx,PADT-4);ctx.lineTo(hx,H-PADB);ctx.stroke();}}
 cv.addEventListener("mousemove",e=>{const r=cv.getBoundingClientRect();
  const t=Math.max(0,Math.min(D.dur,(e.clientX-r.left-PADL)/(W-PADL-PADR)*D.dur));draw(xOf(t));
  const on=A.lanes.filter(l=>l.intervals.some(iv=>t>=iv[0]&&t<=iv[1])).map(l=>l.name);
  document.getElementById("arrReadout").innerHTML=`<span><b>${fmtT(t)}</b></span>`+
   (on.length?`<span>playing: <b>${on.join(", ")}</b></span>`:`<span>—</span>`);});
 cv.addEventListener("mouseleave",()=>{draw();document.getElementById("arrReadout").textContent=T.hover;});
 cv.addEventListener("click",e=>{const r=cv.getBoundingClientRect();const t=Math.max(0,Math.min(D.dur,(e.clientX-r.left-PADL)/(W-PADL-PADR)*D.dur));if(window.__seek)window.__seek(t);});
 PH.push(t=>draw(xOf(t)));
 window.addEventListener("resize",resize);resize();
})();

// Automation small-multiples + stem frequency heatmap panels were cut in the declutter
// (v0.5.2): the sequencer under Track Story now carries frequency-as-colour, and raw
// automation curves weren't actionable. Their data still rides in the payload, unused.

(function(){
 const M=D.stemmap,P=document.getElementById("mapPanel");
 if(!M||!M.stems){P.style.display="none";return;}
 document.getElementById("mapTitle").textContent=T.map_title;
 document.getElementById("mapHint").textContent=T.map_hint;
 const FCOL={kick:"#ff5d73",bass:"#a78bfa",drums:"#4cc9f0",hats:"#5ad1c2",chord:"#46d39a",lead:"#ffd166",other:"#8b94a8"};
 const VC={clear:"good",mixed:"warn",nomatch:"warn",empty:"bad"};
 const HEAD={clear:d=>T.map_clear.replace("{fam}",d.best_family),mixed:()=>T.map_mixed,
             nomatch:()=>(T.map_nomatch||"has signal · no clean match"),empty:()=>(T.map_empty||"near-silent")};
 const rows=Object.entries(M.stems).map(([name,d])=>{
  const vcls=VC[d.verdict]||"warn";
  const head=(HEAD[d.verdict]||HEAD.nomatch)(d);
  const bars=d.family_matches.slice(0,3).map(m=>{
   const w=Math.max(0,Math.min(100,m.r*100));
   return `<div style="display:flex;align-items:center;gap:6px;margin-top:3px;font-size:11px">
     <span style="width:38px;color:var(--muted)">${m.family}</span>
     <div style="flex:1;height:6px;background:var(--line);border-radius:3px;overflow:hidden">
       <div style="height:100%;width:${w}%;background:${FCOL[m.family]||"#888"}"></div></div>
     <span style="width:34px;text-align:right;color:var(--muted)">${m.r.toFixed(2)}</span></div>`;}).join("");
  return `<div class="mcard"><div style="display:flex;justify-content:space-between;align-items:baseline">
    <div class="z" style="font-size:13px;color:var(--ink);font-weight:600">${name}</div>
    <span class="tag ${vcls}" style="margin-top:0">${head}</span></div>
    ${bars}<div class="z" style="margin-top:8px;color:#aeb6c8">${d.verdict_text}</div></div>`;}).join("");
 document.getElementById("mapRows").innerHTML=rows;
 let notes="";
 if(M.export_suggestion)notes+=`<div class="rec do"><div class="when">PROJECT LOADED</div>
   <h3>${T.map_export}</h3><p>${M.export_suggestion}</p></div>`;
 if(M.model_recommendation)notes+=`<div class="rec concept" style="margin-top:12px"><div class="when">SEPARATION</div>
   <h3>${T.map_model.replace("{model}",M.model_recommendation)}</h3><p>${M.model_why}</p></div>`;
 document.getElementById("mapNotes").innerHTML=notes;
})();

(function(){
 const R=D.rhythm,P=document.getElementById("rhyPanel");
 if(!R||!R.rhythm){P.style.display="none";return;}
 document.getElementById("rhyTitle").textContent=T.rhy_title;
 document.getElementById("rhyHint").textContent=T.rhy_hint;
 // inline sparkline (SVG) of onset density over time
 const spark=(arr,col)=>{const w=150,h=24,n=arr.length,mx=Math.max(1,...arr);
  const pts=arr.map((v,i)=>`${(i/(n-1)*w).toFixed(1)},${(h-v/mx*(h-2)-1).toFixed(1)}`).join(" ");
  return `<svg width="${w}" height="${h}" style="display:block;margin-top:6px">
   <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.5"/></svg>`;};
 const FCOL={drums:"#4cc9f0",bass:"#a78bfa",other:"#ffd166",vocals:"#ff9ec7",guitar:"#5ad1c2",piano:"#46d39a"};
 document.getElementById("rhyRows").innerHTML=Object.entries(R.rhythm).map(([s,d])=>{
  const col=FCOL[s]||"#8b94a8";
  const tight=d.offgrid_ms!=null?T.rhy_tight.replace("{ms}",d.offgrid_ms):"—";
  const sync=d.syncopation_pct!=null?T.rhy_sync.replace("{p}",d.syncopation_pct):"—";
  return `<div class="mcard"><div class="z" style="font-size:13px;color:var(--ink);font-weight:600">${s}</div>
   <div class="pct" style="color:${col};font-size:18px">${T.rhy_rate.replace("{r}",d.onset_rate)}</div>
   <div class="z">${tight} · ${sync}</div>${spark(d.onset_density,col)}</div>`;}).join("");
 const sep=R.separation||{};let html="";
 const rdb=sep.reconstruction_error_db;
 const rcls=rdb==null?"warn":rdb<-25?"do":rdb<-12?"concept":"crit";
 html+=`<div class="rec ${rcls}"><div class="when">${T.rhy_sep}</div>
   <h3>${rdb!=null?rdb+" dB residual":"—"}</h3><p>${sep.reconstruction_text||""}</p></div>`;
 const leaks=(sep.leakage||[]).filter(l=>l.r>=0.2);
 const lbody=leaks.length?leaks.map(l=>`${l.a} ↔ ${l.b}: <b>${l.r.toFixed(2)}</b>`).join(" · "):T.rhy_noleak;
 html+=`<div class="rec ${leaks.length?"concept":"do"}" style="margin-top:12px"><div class="when">${T.rhy_leak}</div>
   <p style="margin-top:2px">${lbody}</p></div>`;
 document.getElementById("rhySep").innerHTML=html;
})();

// Drum-breakdown panel cut in the declutter (v0.5.2): kick/snare/hat now live INSIDE
// the drums lane of the sequencer (kick at the bottom). D.drums still feeds that lane.

// ── Part D: transcribed-notes piano roll ──
(function(){
 const N=D.notes,P=document.getElementById("notePanel");
 if(!N||!N.notes||!N.notes.length){P.style.display="none";return;}
 const lo=N.pitch_min,hi=N.pitch_max,span=Math.max(1,hi-lo);
 document.getElementById("noteTitle").textContent=T.note_title.replace("{label}",N.label);
 document.getElementById("noteHint").textContent=T.note_hint
  .replace("{label}",N.label).replace("{lo}",noteName(lo)).replace("{hi}",noteName(hi)).replace("{n}",N.n_notes);
 function noteName(p){const NM=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];return NM[((p%12)+12)%12]+(Math.floor(p/12)-1);}
 const cv=document.getElementById("note"),ctx=cv.getContext("2d");
 const PADL=46,PADR=14,PADT=10,PADB=22;let W,H;const xOf=t=>PADL+(t/D.dur)*(W-PADL-PADR);
 const yOf=p=>PADT+(1-(p-lo)/span)*(H-PADT-PADB);
 function resize(){W=cv.clientWidth;H=cv.clientHeight;cv.width=W*devicePixelRatio;cv.height=H*devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);draw();}
 function draw(hx){ctx.clearRect(0,0,W,H);
  // octave gridlines (C notes)
  ctx.strokeStyle=getCss("--line");ctx.lineWidth=1;ctx.fillStyle=getCss("--muted");ctx.font="9px sans-serif";ctx.textAlign="right";
  for(let p=Math.ceil(lo/12)*12;p<=hi;p+=12){const y=yOf(p);ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(PADL,y);ctx.lineTo(W-PADR,y);ctx.stroke();ctx.globalAlpha=1;ctx.fillText(noteName(p),PADL-6,y+3);}
  const rh=Math.max(2,(H-PADT-PADB)/span*0.9);
  N.notes.forEach(n=>{const x=xOf(n.t),w=Math.max(1.5,xOf(n.t+n.dur)-x),y=yOf(n.pitch)-rh/2;
   const a=(0.4+0.6*Math.min(1,n.amp)).toFixed(2);ctx.fillStyle=`rgba(167,139,250,${a})`;ctx.fillRect(x,y,w,rh);});
  drawLocators(ctx,xOf,PADT,H-PADB,null);
  ctx.fillStyle=getCss("--muted");ctx.font="10px sans-serif";ctx.textAlign="center";
  for(let t=0;t<=D.dur;t+=60)ctx.fillText(fmtT(t),xOf(t),H-7);
  if(hx!=null){ctx.strokeStyle="rgba(255,255,255,.5)";ctx.beginPath();ctx.moveTo(hx,PADT);ctx.lineTo(hx,H-PADB);ctx.stroke();}}
 cv.addEventListener("mousemove",e=>{const r=cv.getBoundingClientRect();
  const t=Math.max(0,Math.min(D.dur,(e.clientX-r.left-PADL)/(W-PADL-PADR)*D.dur));draw(xOf(t));
  const here=N.notes.filter(n=>t>=n.t&&t<=n.t+n.dur).map(n=>n.name);
  document.getElementById("noteReadout").innerHTML=`<span><b>${fmtT(t)}</b></span>`+
   (here.length?`<span>sounding: <b>${[...new Set(here)].join(", ")}</b></span>`:`<span>—</span>`);});
 cv.addEventListener("mouseleave",()=>{draw();document.getElementById("noteReadout").textContent=T.hover;});
 cv.addEventListener("click",e=>{const r=cv.getBoundingClientRect();const t=Math.max(0,Math.min(D.dur,(e.clientX-r.left-PADL)/(W-PADL-PADR)*D.dur));if(window.__seek)window.__seek(t);});
 PH.push(t=>draw(xOf(t)));
 window.addEventListener("resize",resize);resize();
})();

// ── Part E: synced stem player ──
(function(){
 const PL=D.player,P=document.getElementById("playerControls");
 if(!PL||!PL.srcs||!PL.srcs.length){if(P)P.style.display="none";return;}
 document.getElementById("playNote").textContent=T.play_note;
 const wrap=document.getElementById("playAudios");
 const auds=PL.srcs.map(s=>{const a=new Audio();a.src=s.src;a.preload="auto";wrap.appendChild(a);
  return {name:s.name,a:a,mute:false,solo:false};});
 const master=auds[0].a;
 const btn=document.getElementById("playBtn"),tEl=document.getElementById("playTime");
 btn.textContent=T.play_play;
 const dur=()=>master.duration||D.dur;
 function gains(){const anySolo=auds.some(s=>s.solo);
  auds.forEach(s=>{s.a.muted=anySolo?!s.solo:s.mute;});drawL(lxOf(window.__pht||0));}  // keep the playhead put
 // ── sequencer lanes: one playable lane per stem, with mute/solo + envelope ──
 // Each lane bridges the Demucs stem to the real project part (from the stem map),
 // so the eye (arrangement = project groups) and the ear (these stems) stay connected.
 const FAMCOL={kick:"#ff5d73",bass:"#a78bfa",drums:"#4cc9f0",hats:"#5ad1c2",
               chord:"#46d39a",lead:"#ffd166",other:"#8b94a8"};
 const SM=D.stem,MAP=D.stemmap&&D.stemmap.stems;
 function bridge(name){const sm=MAP&&MAP[name];if(!sm)return{txt:"",col:null};
  if(sm.verdict==="empty")return{txt:"near-silent",col:null};   // Demucs put little here
  // Only show a project-part guess when the map is actually confident — no more wrong labels.
  if(sm.verdict==="clear"&&sm.best_family)return{txt:"≈ "+sm.best_family,col:FAMCOL[sm.best_family]||null};
  return{txt:"",col:null};}
 const BANDS=(SM&&SM.bands)||["sub","low","low_mid","mid","hi_mid","air"];
 const VIZ=SM&&SM.viz;   // fine-resolution drawing grid (~0.25 s), if present
 function normEnv(a,bins){const v=a.filter(x=>x>-119);
  const lo=v.length?Math.min.apply(null,v):-60,hi=v.length?Math.max.apply(null,v):0;
  const rng=Math.max(6,hi-lo);return{vals:a.map(x=>Math.max(0,Math.min(1,(x-lo)/rng))),bins:bins};}
 function volEnv(name){
  if(VIZ&&VIZ.bb&&VIZ.bb[name])return normEnv(VIZ.bb[name],VIZ.bins);   // fine
  if(SM&&SM.bb&&SM.bb[name]&&SM.time_bins)return normEnv(SM.bb[name],SM.time_bins); // 4 s
  if(MAP&&MAP[name]&&MAP[name].env)return{vals:MAP[name].env,bins:D.stemmap.bins};
  return null;}
 const lin=db=>(db==null||db<=-119)?0:Math.pow(10,db/10);  // dB → linear power
 // Traktor-style: colour each slice of the waveform by its FREQUENCY content
 // (bass→warm red, mids→green, highs→blue), height by LOUDNESS. Two dimensions at once.
 const FBANDS={low:["sub","low"],mid:["low_mid","mid"],high:["hi_mid","air"]};
 // anchor hues for the 3 frequency groups (Traktor-style: warm lows → green mids → blue highs).
 // Balanced mixes land on the intermediates — low+mid≈orange, mid+high≈teal, low+high≈violet —
 // so the waveform reads as a continuous spectrum, not just 3 flat colours. See the legend.
 const FCOL={low:[255,78,80],mid:[76,214,140],high:[80,168,255]};
 function mixCol(e){      // e={low,mid,high} energies → sharpened [r,g,b]
  let tot=e.low+e.mid+e.high;if(tot<=0)return [120,130,150];
  // raise weights to a power so the dominant band's hue stays vivid instead of greying out
  let wl=Math.pow(e.low/tot,1.6),wm=Math.pow(e.mid/tot,1.6),wh=Math.pow(e.high/tot,1.6);
  const s=wl+wm+wh||1;wl/=s;wm/=s;wh/=s;
  return [(wl*FCOL.low[0]+wm*FCOL.mid[0]+wh*FCOL.high[0])|0,
          (wl*FCOL.low[1]+wm*FCOL.mid[1]+wh*FCOL.high[1])|0,
          (wl*FCOL.low[2]+wm*FCOL.mid[2]+wh*FCOL.high[2])|0];}
 function freqColors(name){            // [r,g,b] per bin, or null when no band data
  if(VIZ&&VIZ.band&&VIZ.band[name]){const B=VIZ.band[name];      // fine 3-group grid
   return VIZ.bins.map((_,j)=>mixCol({low:lin(B.low[j]),mid:lin(B.mid[j]),high:lin(B.high[j])}));}
  const H=SM&&SM.heat&&SM.heat[name],tb=SM&&SM.time_bins;if(!H||!tb)return null;   // 4 s
  return tb.map((_,j)=>{const e={};for(const g in FBANDS)e[g]=FBANDS[g].reduce((a,b)=>a+lin(H[b]?H[b][j]:-120),0);
   return mixCol(e);});}
 // STACKED bands (user's "area chart" idea): per bin, the LINEAR energy in low/mid/high so
 // the lane can draw them as 3 stacked layers — you see when several bands are strong AT ONCE
 // (kick + snare together), which a single blended colour hides. Returns [{low,mid,high}] per bin.
 function bandFracs(name){
  if(VIZ&&VIZ.band&&VIZ.band[name]){const B=VIZ.band[name];
   return VIZ.bins.map((_,j)=>({low:lin(B.low[j]),mid:lin(B.mid[j]),high:lin(B.high[j])}));}
  const H=SM&&SM.heat&&SM.heat[name],tb=SM&&SM.time_bins;if(!H||!tb)return null;
  return tb.map((_,j)=>{const e={};for(const g in FBANDS)e[g]=FBANDS[g].reduce((a,b)=>a+lin(H[b]?H[b][j]:-120),0);return e;});}
 // the drums lane is special: kick/snare/hat hit-density (Part D), not one curve
 const DR=(D.drums&&D.drums.density&&D.drums.bins)?D.drums:null;
 const DRCOL={kick:"#ff5d73",snare:"#ffd166",hat:"#5ad1c2"},DRK=["kick","snare","hat"];
 const lanes=auds.map(s=>{const br=bridge(s.name),isdrum=(s.name==="drums"&&!!DR);
  return{s:s,name:s.name,br:br,col:br.col||"#a78bfa",drum:isdrum,
         env:isdrum?null:volEnv(s.name),fc:isdrum?null:freqColors(s.name),bands:isdrum?null:bandFracs(s.name)};});
 const lcv=document.getElementById("stemlanes"),lx=lcv.getContext("2d");
 const PADL=70,PADR=14,laneH=30,laneGap=5,LPT=4,LPB=18;
 let LW,LH;const lxOf=t=>PADL+(t/dur())*(LW-PADL-PADR);
 // variable lane heights (drums lane is taller, to fit 3 hit-density curves)
 function layout(){let y=LPT;lanes.forEach(L=>{L.h=L.drum?laneH*2+laneGap:laneH;L.y=y;y+=L.h+laneGap;});return y-laneGap;}
 const drMax=DR?Math.max(1e-9,Math.max.apply(null,DRK.reduce((a,k)=>a.concat(DR.density[k]||[0]),[]))):1;
 const trunc=s=>{lx.font="600 9.5px sans-serif";if(lx.measureText(s).width<=47)return s;
  while(s.length>1&&lx.measureText(s+"…").width>47)s=s.slice(0,-1);return s+"…";};
 function box(x,y,on,col,letter){lx.fillStyle=on?col:"rgba(255,255,255,.04)";
  lx.strokeStyle=on?col:getCss("--line");lx.lineWidth=1;lx.beginPath();
  if(lx.roundRect)lx.roundRect(x,y,12,12,3);else lx.rect(x,y,12,12);lx.fill();lx.stroke();
  lx.fillStyle=on?"#0c0e14":getCss("--muted");lx.font="700 8px sans-serif";lx.textAlign="center";
  lx.fillText(letter,x+6,y+9);lx.textAlign="left";}
 // kick at the BOTTOM, snare middle, hats on top — reads like low→high frequency.
 function drawDrum(L,active){const rows=L.h/3;
  DRK.forEach((k,ki)=>{const d=DR.density[k];if(!d)return;
   const base=L.y+L.h-2-ki*rows,HH=rows-2;   // ki: 0=kick(bottom) … 2=hat(top)
   lx.globalAlpha=active?.85:.22;lx.fillStyle=DRCOL[k];lx.beginPath();lx.moveTo(lxOf(DR.bins[0]),base);
   d.forEach((v,j)=>{lx.lineTo(lxOf(DR.bins[j]),base-Math.min(1,v/drMax)*HH);});
   lx.lineTo(lxOf(DR.bins[d.length-1]),base);lx.closePath();lx.fill();
   lx.globalAlpha=active?.95:.5;lx.fillStyle=DRCOL[k];lx.font="700 9px sans-serif";lx.textAlign="right";
   lx.fillText(k,PADL-6,base-HH/2+3);lx.textAlign="left";});lx.globalAlpha=1;}  // labels in the gutter, off the wave
 const STK=["low","mid","high"];   // bottom→top, low(red) under mid(green) under high(blue)
 function drawWave(L,active){const E=L.env,base=L.y+L.h-2,Hh=L.h-6,n=E.vals.length;
  if(L.bands){ // STACKED low/mid/high (area chart): total height = loudness, split by band share.
   // Each band's height = loudness × its share of the energy. Tall red+green together = kick+snare at once.
   lx.globalAlpha=active?.9:.2;
   const top=L.bands.map((b,j)=>{const tot=(b.low+b.mid+b.high)||1,h=E.vals[Math.min(j,n-1)]*Hh;
    return {x:lxOf(E.bins[Math.min(j,E.bins.length-1)]),low:h*b.low/tot,mid:h*b.mid/tot,high:h*b.high/tot};});
   STK.forEach((band,bi)=>{const c=FCOL[band];lx.fillStyle="rgb("+c[0]+","+c[1]+","+c[2]+")";lx.beginPath();
    const belowOf=j=>{let s=0;for(let b=0;b<bi;b++)s+=top[j][STK[b]];return s;};
    for(let j=0;j<top.length;j++){const yTop=base-belowOf(j)-top[j][band];j?lx.lineTo(top[j].x,yTop):lx.moveTo(top[j].x,yTop);} // top edge →
    for(let j=top.length-1;j>=0;j--)lx.lineTo(top[j].x,base-belowOf(j));                                                     // bottom edge ←
    lx.closePath();lx.fill();});
   lx.globalAlpha=1;
  }else{ // no per-band data (e.g. guitar/piano) → solid family colour
   lx.beginPath();lx.moveTo(PADL,base);E.vals.forEach((v,j)=>{lx.lineTo(lxOf(E.bins[j]),base-v*Hh);});
   lx.lineTo(lxOf(E.bins[E.bins.length-1]),base);lx.closePath();
   lx.globalAlpha=active?.5:.16;lx.fillStyle=L.col;lx.fill();
   lx.globalAlpha=active?1:.3;lx.strokeStyle=L.col;lx.lineWidth=1;lx.stroke();lx.globalAlpha=1;}}
 function drawL(hx){if(!LW)return;lx.clearRect(0,0,LW,LH);
  const anySolo=auds.some(a=>a.solo);
  lanes.forEach(L=>{const active=anySolo?L.s.solo:!L.s.mute;
   lx.fillStyle="rgba(255,255,255,.02)";lx.fillRect(PADL,L.y,LW-PADL-PADR,L.h);
   box(3,L.y+3,L.s.mute,"#ff6b6b","M");box(3,L.y+L.h-15,L.s.solo,"#46d39a","S");
   lx.globalAlpha=active?1:.45;lx.fillStyle=active?getCss("--ink"):getCss("--muted");
   lx.font="600 9.5px sans-serif";lx.textAlign="left";if(!L.drum)lx.fillText(trunc(L.name),19,L.y+L.h/2+3);lx.globalAlpha=1;
   if(L.drum){drawDrum(L,active);}
   else if(L.env){drawWave(L,active);}
   if(L.br.txt&&!L.drum){lx.globalAlpha=active?.8:.4;lx.fillStyle=L.br.col||getCss("--muted");
    lx.font="8px sans-serif";lx.textAlign="left";lx.fillText(L.br.txt,PADL+4,L.y+9);lx.globalAlpha=1;}});
  drawLocators(lx,lxOf,LPT,LH-LPB,null);
  lx.fillStyle=getCss("--muted");lx.font="10px sans-serif";lx.textAlign="center";
  for(let t=0;t<=dur();t+=60)lx.fillText(fmtT(t),lxOf(t),LH-5);
  if(hx!=null){lx.strokeStyle="rgba(255,255,255,.6)";lx.lineWidth=1;lx.beginPath();lx.moveTo(hx,LPT);lx.lineTo(hx,LH-LPB);lx.stroke();}}
 function lresize(){LW=lcv.clientWidth;LH=layout()+LPB;lcv.style.height=LH+"px";
  lcv.width=LW*devicePixelRatio;lcv.height=LH*devicePixelRatio;lx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);drawL();}
 lcv.addEventListener("click",e=>{const r=lcv.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;
  for(let i=0;i<lanes.length;i++){const L=lanes[i];
   if(x>=3&&x<=15){if(y>=L.y+3&&y<=L.y+15){L.s.mute=!L.s.mute;gains();return;}
    if(y>=L.y+L.h-15&&y<=L.y+L.h-3){L.s.solo=!L.s.solo;gains();return;}}}
  if(x>=PADL)seekTo(Math.max(0,Math.min(dur(),(x-PADL)/(LW-PADL-PADR)*dur())));});  // gutter clicks don't seek to 0
 window.addEventListener("resize",lresize);
 PH.push(t=>drawL(lxOf(t)));
 function paint(t){window.__pht=t;
  tEl.textContent=fmtT(t)+" / "+fmtT(dur());PH.forEach(f=>f(t));}
 function loop(){if(!master.paused){paint(master.currentTime);requestAnimationFrame(loop);}}
 function play(){auds.forEach(s=>{s.a.currentTime=master.currentTime;});
  Promise.all(auds.map(s=>s.a.play())).catch(()=>{});
  btn.textContent=T.play_pause;requestAnimationFrame(loop);}
 function pause(){auds.forEach(s=>s.a.pause());btn.textContent=T.play_play;}
 btn.onclick=()=>{master.paused?play():pause();};
 const rew=document.getElementById("rewBtn");if(rew)rew.onclick=()=>seekTo(0);  // Ableton-style back-to-start
 function seekTo(t){t=Math.max(0,Math.min(dur(),t));auds.forEach(s=>{s.a.currentTime=t;});paint(t);}
 window.__seek=t=>{seekTo(t);};   // charts/lanes call this on click; the playhead line IS the seek UI
 master.addEventListener("ended",pause);
 master.addEventListener("loadedmetadata",()=>{paint(0);lresize();});
 paint(0);lresize();
})();
</script></body></html>"""


def main():
    p = argparse.ArgumentParser(description="track-coach: build interactive HTML widget")
    p.add_argument("--core")
    p.add_argument("--detail")
    p.add_argument("--masking", default=None)
    p.add_argument("--als", default=None)
    p.add_argument("--stemmap", default=None, help="result_stemmap.json from map_stems.py (Part B)")
    p.add_argument("--rhythm", default=None, help="result_rhythm.json from rhythm_quality.py (Part C)")
    p.add_argument("--notes", default=None, help="result_notes.json from transcribe.py (Part D)")
    p.add_argument("--drums-breakdown", default=None, help="result_drums.json from drum_breakdown.py (Part D)")
    p.add_argument("--selfsim", default=None, help="result_selfsim.json from self_similarity.py (repeats/form)")
    p.add_argument("--audio-stems-rel", default=None,
                   help="directory (relative to the output HTML) holding the stem .wav files, "
                        "e.g. 'stems_6s'. Enables the in-page stem player (Part E).")
    p.add_argument("--presence-threshold", type=float, default=0.3,
                   help="0..1 cutoff on each stem's normalised loudness for the 'playing' "
                        "presence strip and active-%% readout (default 0.3). Not hardcoded.")
    p.add_argument("--narrative", default=None,
                   help="markdown/plain-text file with the agent-written 'Producer's read'. "
                        "Rendered as the top panel, above the charts.")
    p.add_argument("--als-offset-s", type=float, default=None,
                   help="project time (seconds) where the rendered audio starts — usually a locator. "
                        "Required to align the .als arrangement to the audio. NEVER guessed: if the picture "
                        "doesn't line up, ask the user which locator the render starts from.")
    p.add_argument("--out", default="analysis_widget.html")
    p.add_argument("--title", default=None)
    p.add_argument("--strings", default=None, help="JSON file overriding the English text (any language)")
    p.add_argument("--dump-strings", action="store_true", help="print the canonical English strings JSON and exit")
    args = p.parse_args()

    if args.dump_strings:
        print(json.dumps(STRINGS, ensure_ascii=False, indent=2))
        return

    if not args.core or not args.detail:
        p.error("--core and --detail are required (unless --dump-strings)")

    S = STRINGS
    if args.strings:
        S = deep_merge(STRINGS, json.loads(Path(args.strings).read_text()))

    core = json.loads(Path(args.core).read_text())
    detail = json.loads(Path(args.detail).read_text())
    masking = json.loads(Path(args.masking).read_text()) if args.masking else None
    als = json.loads(Path(args.als).read_text()) if args.als else None
    if als and args.als_offset_s is None:
        print("NOTE: --als given but --als-offset-s not set. The project arrangement can't be aligned "
              "to the audio without it, so the arrangement layer is omitted. Re-run with "
              "--als-offset-s <seconds> (the project time where the render starts, usually a locator).")
    stemmap = json.loads(Path(args.stemmap).read_text()) if args.stemmap else None
    rhythm = json.loads(Path(args.rhythm).read_text()) if args.rhythm else None
    notes = json.loads(Path(args.notes).read_text()) if args.notes else None
    drums = json.loads(Path(args.drums_breakdown).read_text()) if args.drums_breakdown else None
    selfsim = json.loads(Path(args.selfsim).read_text()) if args.selfsim else None
    narrative_md = Path(args.narrative).read_text(encoding="utf-8") if args.narrative else None
    build_html(core, detail, masking, als, args.out, args.title, S,
               als_offset_s=args.als_offset_s, stemmap=stemmap, rhythm=rhythm, notes=notes, drums=drums,
               audio_stems_rel=args.audio_stems_rel, presence_threshold=args.presence_threshold,
               narrative_md=narrative_md, selfsim=selfsim)


if __name__ == "__main__":
    main()
