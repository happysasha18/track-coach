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
import sys, argparse, json, math, copy, re
from pathlib import Path

TC_VERSION = "1.6.1"  # Track Coach analyzer version — s66: the revalidate completion path is fixed — it resolved the source under the wrong key and silently no-oped on old runs, reported success over a still-partial library, and deposited a slug-drifted sibling instead of superseding; now it resolves `audio_path`, fails loud on a gone source, verifies by deed, and forgets the old deposit. Reference-run validity checked at direction-generation (RC-INV-13e). Analysis OUTPUT unchanged (footer stamp only), so nothing stales

# Staleness (INV-12) reads the ANALYSIS version, not TC_VERSION. TC_ANALYSIS_VERSION advances ONLY when a
# change alters what the analysis OUTPUTS — the content layers signal-analysis / project-parsing /
# credibility-claims / reference (ARCHITECTURE.md L1–L4). A render-only change (L5) or an infrastructure
# change (storage / catalog / guardrails / tooling / docs, L6–L8) leaves it untouched, so the library never
# goes stale for a change that did not touch the numbers.
TC_ANALYSIS_VERSION = 1
# The tool version of the current analysis generation. A widget deposited before analysis-version stamping
# carries only its tool version; its row is judged against THIS constant (INV-12 back-compat), which is
# frozen at the last full library re-render point so a later TC_VERSION bump can no longer move the verdict.
TC_ANALYSIS_BASELINE_TCV = "1.4.1"

# ── Reference read (§D.10.3) — axis labels + styling constants ──────────────────────────
_AXIS_LABELS = {
    "tempo":        "Tempo",
    "dynamics":     "Dynamic range",
    "stereo":       "Stereo width",
    "brightness":   "Brightness",
    "density":      "Density",
    "energy_build": "Energy build",
    "drums_share":  "Drums share",
    "bass_share":   "Bass share",
    "other_share":  "Synth / pad share",
    "lead_share":   "Lead share",
    "bass_sustain": "Bass sustain",
    "pad_sustain":  "Pad sustain",
    "pad_notes":    "Pad note rate",
    "pad_bright":   "Pad brightness",
}
# Axis → category chip (Mix / Balance / Character), matching the explorer groupings
_AXIS_CATEGORY = {
    "tempo":        "Mix",
    "dynamics":     "Mix",
    "stereo":       "Mix",
    "brightness":   "Mix",
    "density":      "Mix",
    "energy_build": "Mix",
    "drums_share":  "Balance",
    "bass_share":   "Balance",
    "other_share":  "Balance",
    "lead_share":   "Balance",
    "bass_sustain": "Character",
    "pad_sustain":  "Character",
    "pad_notes":    "Character",
    "pad_bright":   "Character",
}
_CHAR_AXES   = {"bass_sustain", "pad_sustain", "pad_notes", "pad_bright"}
_CAT_COLORS  = {"Mix": "#5b6472", "Balance": "#7a6cab", "Character": "#c08a3e"}
_REF_LEVEL_COLOR = {"close": "#2e9e5b", "mid": "#d8932a"}
_REF_MAX_Z       = 3.0         # z-offsets beyond this clip to full bar width
_REF_MAX_PCT     = 44          # max half-bar width in %


def _bar_color(offset_abs: float) -> str:
    """Gradient colour for a reference-read bar: green=close, amber=moderate, red=far."""
    if offset_abs < 0.6:
        return "#3ddc97"    # green — matched / close
    if offset_abs < 1.5:
        return "#e8b24a"    # amber — moderate
    return "#e0594f"        # red — far


def display_tempo(audio_tempo, als_tempo):
    """The tempo shown to the user, and where it came from.

    The producer sets the project tempo in the .als, so when an .als tempo is present it is
    authoritative. Audio-detection is the fallback and can lock onto a subharmonic — a 134 BPM
    breaks track reads as 89 (134 × 2/3) — so it never overrides a real project tempo.
    Returns (bpm, source) where source is "als" or "audio".
    """
    try:
        a = float(als_tempo) if als_tempo is not None else 0.0
    except (TypeError, ValueError):
        a = 0.0
    if a > 0:
        return (a, "als")
    return (audio_tempo, "audio")


def _words(offset: float) -> str:
    """Plain-English words for a signed z-offset from the direction centroid."""
    a = abs(offset)
    direction = "higher" if offset > 0 else "lower"
    if a < 0.4:
        return "matched"
    if a < 0.9:
        return f"a bit {direction}"
    if a < 1.6:
        return f"noticeably {direction}"
    return f"much {direction}"

BAND_ORDER = ["sub", "low", "low_mid", "mid", "hi_mid", "air"]
BAND_LABEL = {  # frequency ranges — language-neutral, never translated
    "sub": "Sub 20–80", "low": "Low 80–250", "low_mid": "LowMid 250–600",
    "mid": "Mid 600–2k", "hi_mid": "HiMid 2–8k", "air": "Air 8–20k",
}

# ── Credibility floors (SPEC docs/SPEC.md §B, CR-2/CR-3). "Don't cry wolf, don't paint silence."
# STEM_EMPTY_FLOOR_DB: a stem whose representative broadband level sits below this is INSIGNIFICANT —
#   too little material to read, so it is dropped from per-stem analysis (no per-stem viz computed).
# STEM_COLOUR_FLOOR_DB: the ABSOLUTE dB at which a per-stem band starts to read as "present" colour.
#   Per-stem viz scales against this fixed floor, NOT each stem's own max, so a quiet stem cannot
#   normalise its loudest band up to full colour (CR-3).
STEM_EMPTY_FLOOR_DB = -55.0
STEM_COLOUR_FLOOR_DB = -60.0

# ── Canonical text (English). Templates use str.format placeholders. ────────────
# To localise, dump this with --dump-strings, translate the values, pass --strings.
STRINGS = {
    "ui": {
        "subtitle": "",
        "subtitle_quick": "quick read",
        "mode_badge_full": "Full analysis",
        "mode_badge_quick": "Quick read",
        "quick_explainer": "Analysed from the mix only. A full run adds stem separation — the per-instrument player, masking, drum/note breakdown, and the section instrument labels on the structure bar.",
        "quick_view_hint": "Run a full analysis for stem-by-stem detail.",
        "play_note_mix": "Playing the full mix. Click anywhere on the chart to jump; the white line is the playhead. Run a full analysis for per-stem play / mute / solo.",
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
        "map_hint": "Each separated stem checked against the real project tracks by timing (when its loudness rises vs. when each part plays). “Near-silent” = the stem really is empty. “Has signal · no clean match” means there IS audio here — it just overlaps other parts too much to pin to one track (not lost). Only trust a stem for EQ when it matches one part.",
        "map_clear": "matches “{fam}”", "map_mixed": "blends parts", "map_weak": "no clear match",
        "map_nomatch": "has signal · no clean match", "map_empty": "near-silent",
        "cues_title": "Callouts on the timeline — tap a triangle above, or an item here",
        "map_model": "Model fit: {model}", "map_export": "Most reliable: export group stems from Ableton",
        "rhy_title": "Rhythm & separation quality",
        "rhy_hint": "Per stem: how busy it is (hits/sec), how tightly it sits on the grid (ms off the nearest 1/16), and the off-beat share. Below: whether the stems add back up to the mix, and which stems bleed into each other.",
        "rhy_rate": "{r} hits/s", "rhy_tight": "{ms} ms off-grid", "rhy_sync": "{p}% off-beat",
        "rhy_sep": "Separation confidence", "rhy_leak": "Leakage (stems rising & falling together)",
        "rhy_noleak": "No significant bleed between stems.",
        "rhy_bleed_title": "Likely bleed — don't read this as the stem's own",
        "rhy_bleed_line": "“{stem}” looks loudest in {band}, but “{source}” sits {gap} dB louder there and they rise & fall together — so that energy is most likely “{source}” bleeding into “{stem}”, not “{stem}” itself.",
        "note_title": "Transcribed notes — {label}",
        "note_hint": "Pitches read straight from the audio of this stem, not from the project. Each bar is one note: position = time, height = pitch, brightness = how loud. Range {lo}–{hi}, {n} notes.",
        "note_label_other": "the melodic layer (synths / keys / pads)",
        "note_hint_other": " This is the splitter's everything-else part — where the track's chords and lead lines live.",
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
        "story_hint": "One map. Top: the structure bar — named scenes (Intro/Build/Drop), each coloured by its musical part; same colour + same letter = that part RETURNS (e.g. A at the intro and again at the outro), outlined when it repeats. Then the POWER curve (a blend of loudness+busy-ness+brightness) with its peak ★ and key moments. Below it the same curve DECOMPOSED into the lanes that drive it — energy (loudness), brightness (treble), density (how busy), modulation (how fast it pulses/throbs per second), stereo width. Bottom: which families play. Press play, click anywhere to jump.",
        "recs_title": "Recommendations",
        "recs_hint": "The few things that stood out, most important first. Red = worth fixing · green = working / do it · yellow = a creative choice. Click a card to see the evidence behind it; a ⏱ tag means it's tied to a moment in the track — that click also jumps there. The rest apply to the whole mix.",
        "legend_crit": "worth fixing",
        "legend_do": "working — do it",
        "legend_concept": "creative choice",
        "play_title": "Stem player — hear what you see",
        "play_hint": "Play the separated stems together, in sync with every chart above. Mute/solo each part; click any timeline to jump there. The white line is the playhead.",
        "play_play": "▶ Play", "play_pause": "❚❚ Pause", "play_mute": "mute", "play_solo": "solo",
        "play_note": "Each lane is one separated part — drums, bass, and the melodic layers. A lane can look empty when that instrument isn't really in the track — parts with too little material to read are shown muted at the bottom. Lanes are drawn fine-grained (~0.25 s), so you see detail inside every bar, not one block per 4 seconds. Press play; click any lane to jump there. Legend below.",
        "hover": "hover over the chart…",
        "scale_quiet": "quiet −90 dB",
        "scale_loud": "loud −6 dB",
        "presence_label": "green strip = playing",
        "presence_silent": "silent",
        "presence_playing": "playing",
        "presence_active": "{p}% active",
        "footer": "Track Coach v{ver} · data embedded in this file · works offline",
        "view_simple": "Simple",
        "view_full": "Detailed",
        "view_aria": "Detail level",
        "back_to_library": "← Library",
        "src_audio": "Audio",
        "src_project": "Project",
        "src_analyzed": "Analyzed",
        "cat_title": "Library — every track & version",
        "cat_hint": "Your analysis library. Each run is kept in its own dated folder (nothing is overwritten) — open an earlier version to compare verdicts.",
        "cat_this_track": "This track",
        "cat_other_tracks": "Other tracks",
        "cat_open": "Open",
        "cat_current": "you are here",
        "cat_versions": "{n} version(s)",
        "cat_missing": "(widget file not found)",
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
                    "groove {feel} (a machine-tight groove stays within ~25–30 ms). Great for live, hip-hop, organic material. "
                    "If this is straight techno and the drums should be dead-tight, pull them closer to the grid.",
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
                    "against its neighbours — {rel} — a {kind}. {flavour} It colours the whole mix because it's "
                    "there constantly, not just on one hit.",
            "fix": "{action} around <b>{band} Hz</b> on the master (a wide, gentle {dir} of ~{amt:.0f} dB) and A/B it."},
        "squashed": {
            "header": "Master · dynamic range DR {dr:.0f}",
            "title": "The mix is heavily limited — little dynamic range left",
            "body": "Peak-to-RMS is only <b>{dr:.0f} dB</b> — the loud and quiet parts sit almost at the same level, so the "
                    "track sounds flat and fatiguing, with no punch on the transients. For scale: even loud club masters keep "
                    "around 6–8 dB of range; open, punchy mixes sit at 10 and up. This usually means the limiter / clipper "
                    "is working too hard.",
            "fix": "Back off the limiter / master clipper so transients breathe (aim DR ≥ ~8) — or lower the input into it and let the loudest hits poke through."},
        "empty_stem": {
            "header": "Separation · stem “{stems}” is empty",
            "title": "Separation found almost nothing in this stem",
            "body": "The separator found almost no material for “{stems}”. Often this isn't the track's fault: the model is "
                    "trained on live bands (drums / bass-guitar / vocals / other) and dumps synth bass into “{carrier}”. "
                    "Worth re-running with a model that has more stems (a 6-stem model adds guitar and piano).",
            "fix": "Re-run separation with a 6-stem model — or, if you have the project, export the group stem instead of trusting this one."},
        "masking_real": {
            "header": "Frequencies · bass competes with mids",
            "title": "Around 250–600 Hz the bass is louder than the melody at times",
            "body": "{lines}. Where it bothers you, carve a small dip in the bass in that range or separate them in time. "
                    "Where the mid instrument is simply silent, that's not a conflict — leave it.",
            "fix": "Carve a small 250–600 Hz dip in the bass — or sidechain/duck it under the melody so they don't fight."},
        "masking_line": "bass covers “{mid}” in {pct:.0f}% of spots",
        "masking_stem": {
            "header": "Frequencies · the {low_lbl} buries the {mid_lbl}",
            "title": "The {low_lbl} is louder than the {mid_lbl} {spot} ~{pct:.0f}% of the track",
            "body": "Worst around {worst_t}. Where it bothers you, carve a small dip in the {low_lbl} {notch}, "
                    "or move them apart in time. Where the {mid_lbl} {mid_v} simply silent there, that's not a clash.",
            "fix": "Notch the {low_lbl} {notch}, or duck it under the {mid_lbl} so they stop fighting."},
        "masking_clean": {
            "header": "Low end · clean",
            "title": "The bass doesn't clash with anything",
            "body": "The bass doesn't cover the melody (250–600 Hz) or the kick (sub 20–80 Hz). If the mix sounds muddy, "
                    "the cause isn't bass-vs-mids clash.",
            "fix": "Nothing to fix here. If it still sounds muddy, look at reverb/saturation or low-mid buildup in other parts."},
        "stem_evolves": {
            "header": "Development · what carries it vs what loops",
            "title": "The {evolver} keeps changing while {loopers} mostly loop",
            "body": "Across the track the {evolver} barely repeats — it's carrying the development — "
                    "while {loopers} loop more. That's often exactly what you want.",
            "fix": "If it ever feels static, the development is resting on one part ({evolver}) — vary a looping "
                   "one too ({loopers}): a filter sweep, a pattern change, or drop/add a layer."},
        "plateau": {
            "header": "Development · where new ideas stop",
            "title": "After {onset} nothing new is introduced — the last {tail_pct:.0f}% recombines earlier sections",
            "body": "Up to {onset} the track keeps adding sections ({n} in all); after that it reworks material "
                    "you've already heard, to the end. On a developing track that's often where attention drifts.",
            "fix": "If it should keep evolving, introduce a change around {onset} — a new element, a key/filter "
                   "move, a breakdown — so the back half isn't only recombination."},
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
            "body": "{part} is silent for almost the whole track and only appears at <b>{t}</b>. If it's a lead, vocal "
                    "or sample, that's a strong accent for the finale. Right now it flies in just before the hard cut: bring it "
                    "in a little earlier and let it play out, so it reads as a resolution, not a stray tail.",
            "fix": "Bring it in a bit earlier than <b>{t}</b> and let it play out, so it lands as a resolution rather than a stray tail."},
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
            "body": "A lot of the track isn't captured by any single separated part — the parts don't add back up to the original. "
                    "Read the per-stem panels as approximate here, not exact. If you have the project, export "
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

# §B.16 INV-50 — a number wears its scale. The step boundaries live HERE, once, beside the
# card maps: the swing feel bands and the tonal perceived-loudness steps (hot / dip mirrors).
# The phrases are chosen from the MEASUREMENT so the framing varies per track (the
# de-templating steer, signal_value_map.md).
SWING_FEEL_BANDS = (          # sw ms threshold → the feel phrase (INV-50a)
    (90.0, "is loose to the point of broken-beat"),
    (60.0, "swings hard — unmistakably human"),
    (30.0, "has a gentle human push off the grid"),
)
TONAL_SCALE_STEPS = (         # |dev| dB threshold → (resonance phrase, dip phrase) (INV-50c)
    (9.0, "about twice as loud as its neighbours, to the ear",
          "about half as loud as its neighbours, to the ear"),
    (6.0, "half again as loud as its neighbours, to the ear",
          "noticeably recessed against its neighbours"),
    (4.0, "a clearly audible bump", "a clearly audible dip"),
)

# which colour class each recommendation uses
REC_CLASS = {
    "long_section": "crit", "energy_flat": "crit", "endpoint": "crit", "empty_stem": "crit",
    "intention_result": "crit", "sep_incomplete": "crit", "truepeak_clip": "crit",
    "wobble": "concept", "swing": "concept", "late_entry": "concept", "stem_evolves": "concept",
    "plateau": "concept",
    "bass_groupstem": "do", "squashed": "do", "tonal_resonance": "do",
}

# Card evidence (SPEC §B.13 / INV-31, 2026-06-23) — the plain "where this came from" line per rec key.
# Names the SIGNAL in words (Tier-A: one number) or the COMBINATION (Tier-B/C: a fusion), NEVER a bare metric
# tag. Format fields are a subset of each rec's add(**kw). EVERY key that produces a `D.recs` card must have an
# entry (the invariant: every card carries a non-empty based-on). Per-stem cards build theirs in per_stem_cards.
REC_BASED = {
    "long_section":    "the song structure — one section runs {frac:.0f}% of the track unchanged.",
    "energy_flat":     "the loudness curve over time — it barely trends across the track.",
    "brightness":      "the brightness curve rising while loudness and density stay roughly flat.",
    "endpoint":        "the ending and the opening measured against each other — their spectra are nearly identical.",
    "wobble":          "the modulation-rate curve holding a near-constant speed start to end.",
    "climax":          "where the energy peak lands — about {pos:.0f}% through the track.",
    "swing":           "the drum timing against the grid — about {sw:.0f} ms off the straight beat.",
    "truepeak_clip":   "the master's true peak — {tp:+.1f} dB, just past the 0 dB ceiling.",
    "tonal_resonance": "the track's average spectrum — the {band} Hz band sits {dev:+.1f} dB off its neighbours.",
    "squashed":        "the master's dynamic range — only {dr:.0f} dB between the peaks and the average level.",
    "plateau":         "the song structure — no new section after {onset}; the last {tail_pct:.0f}% recombines.",
    "stem_evolves":    "per-part repetition — the {evolver} barely repeats while {loopers} loop.",
    "masking_stem":    "the separated parts' spectra overlapping — the {low_lbl} sits over the {mid_lbl} ~{pct:.0f}% of the track.",
    "masking_real":    "the bass and the mid parts overlapping in the 250–600 Hz region.",
    "masking_clean":   "the bass checked against the melody and the kick across the track — no overlap found.",
    "breakdown":       "a dip in overall energy at {t} — a breakdown in the arc.",
    "late_entry":      "a part whose level rises only near the end, at {t}.",
    "intention_result":"your “{param}” automation in the .als against the measured result — they part ways after {a_end}.",
}

# Card evidence NAVIGATION (SPEC §B.13 / INV-48a, s61) — the panel each card's click leads to: the place
# its based-on evidence actually RENDERS. The map is honest: a card with no dedicated visual panel keeps
# the story arc, because the player IS that evidence (seek to the worst moment, solo the named parts —
# the per-lane highlight stays deferred). Keys mirror REC_BASED (RecTargetCompleteness is the twin guard);
# per-stem cards set theirs in per_stem_cards. Values must stay inside EVIDENCE_TARGETS.
EVIDENCE_TARGETS = ("storyPanel", "tonalPanel", "vitals", "rhyPanel", "autoPanel")
REC_TARGET = {
    "long_section":    "storyPanel", "energy_flat":  "storyPanel", "brightness":   "storyPanel",
    "endpoint":        "storyPanel", "wobble":       "storyPanel", "climax":       "storyPanel",
    "plateau":         "storyPanel", "breakdown":    "storyPanel", "late_entry":   "storyPanel",
    "stem_evolves":    "storyPanel", "masking_stem": "storyPanel", "masking_real": "storyPanel",
    "masking_clean":   "storyPanel",
    "tonal_resonance": "tonalPanel",
    "truepeak_clip":   "vitals",     "squashed":     "vitals",
    "swing":           "rhyPanel",
    "intention_result":"autoPanel",
}

# §D.6 stage-2: maps each rec key to the FP axis it primarily reflects (for divergence/on-style calc).
# Keys absent from this dict produce no re-ordering / no option-note / no on-style mark.
REC_AXIS = {
    "energy_flat":      "energy_build",
    "brightness":       "brightness",
    "squashed":         "dynamics",
    "truepeak_clip":    "dynamics",
    "masking_stem":     "density",
    "masking_real":     "density",
    "breakdown":        "energy_build",
    "bass_groupstem":   "bass_share",
    "climax":           "energy_build",
    "plateau":          "energy_build",
    "long_section":     "energy_build",
    "tonal_resonance":  "brightness",
    "stem_evolves":     "density",
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


def fmt_hz(hz):
    """Human frequency label for a masking-cut spot: '≈380 Hz' / '≈1.2 kHz'. None → None (caller falls
    back to the coarse band range). Hz rounds to the nearest 10; kHz to one decimal."""
    if hz is None:
        return None
    if hz >= 1000:
        return f"≈{hz / 1000:.1f} kHz".replace(".0 kHz", " kHz")
    return f"≈{int(round(hz / 10.0) * 10)} Hz"


# ── PRECISE masking frequency (s14, idea a). The coarse masking band ("250–600 Hz") only flags
# THAT the bass buries a part; the per-stem spectra (already in the masking JSON: `spectrum` /
# `spectrum_freqs`) say WHERE inside the band they actually fight, so the rec can name a cut frequency
# ("≈380 Hz") instead of the whole band. The collision sits where the OVERLAP of the two peak-normalised
# spectra is greatest — min(masker,maskee) is large only where BOTH stems have energy there. We name a
# precise frequency ONLY when the buried part genuinely has energy at that bin (credibility: don't
# over-claim a spot the maskee isn't in); otherwise None and the caller keeps the coarse band range.
MASK_FREQ_MIN_LEVEL_DB = -24.0   # the maskee must sit within this of its own peak at the chosen bin
# (e) per-stem repetition surfacing (CR-6): fire the "what carries the development" card only when there's
# a real SPREAD — at least one part clearly evolves AND at least one clearly loops (else it's not insight).
EVOLVE_MAX_RECURRENCE = 0.25     # recurrence ≤ this ⇒ "keeps changing / carries the development"
LOOP_MIN_RECURRENCE   = 0.45     # recurrence ≥ this ⇒ "loops"
# numeric (low, high) Hz per analysis band — mirrors masking.BANDS (kept here so build stays numpy-free).
BAND_HZ = {"sub": (20, 80), "low": (80, 250), "low_mid": (250, 600),
           "mid": (600, 2000), "hi_mid": (2000, 8000), "air": (8000, 20000)}


def mask_collision_freq(masker_spec, maskee_spec, band, freqs):
    """Single frequency (Hz) where `masker_spec` most buries `maskee_spec` inside `band`=(low,high),
    or None when neither has real in-band energy. `masker_spec`/`maskee_spec` are peak-normalised dB
    aligned to `freqs` (the spectrum bin-centre frequencies). Pure-python — no numpy."""
    if not masker_spec or not maskee_spec or not freqs:
        return None
    lo, hi = band
    pairs = [(i, masker_spec[i], maskee_spec[i]) for i, f in enumerate(freqs)
             if lo <= f < hi and i < len(masker_spec) and i < len(maskee_spec)
             and masker_spec[i] is not None and maskee_spec[i] is not None]
    if not pairs:
        return None
    i, _, maskee_db = max(pairs, key=lambda p: min(p[1], p[2]))   # worst overlap = both loud here
    if maskee_db < MASK_FREQ_MIN_LEVEL_DB:                        # buried part barely present → don't over-claim
        return None
    return freqs[i]


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


# ── Per-stem measurements (SPEC §B.11 / CR-11) ─────────────────────────────────────────
# A stem only "speaks" when it diverges from the REST of the track (the mix MINUS itself —
# comparing to the full mix would compare a loud stem partly to itself, suppressing the very
# "it runs opposite the track" insight). Cards then earn a slot by an OBJECTIVE importance
# score (big · persistent · specific · non-redundant), so the system self-judges usefulness
# with no per-track human approval. Pure / numpy-free → unit-testable.

# A near-silent stem ranks BELOW the louder ones (2026-06-22): a quiet part diverging matters less
# than a loud one diverging, so its card score is scaled by how loud it is RELATIVE to the loudest stem.
PROMINENCE_SPAN_DB = 24.0       # provisional (A3, validated on Lazy 2026-06-23): dB below the loudest stem
                                # at which a part's weight hits the floor. On Lazy → drums 1.0 / bass 0.70 /
                                # other 0.44 / guitar 0.40(floor) across a −11.6…−27.2 dB span — quiet parts
                                # downranked, not dropped. Re-check on Shared/Wobble in Phase B.
PROMINENCE_FLOOR = 0.4          # provisional (A3) — minimum score weight for a relatively-quiet stem (guitar)


def stem_prominence(masking):
    """{stem: weight 0..1} = how loud each SIGNIFICANT stem is relative to the loudest one, for ranking
    per-stem cards (SPEC §B.11). Truly sub-floor stems never reach here (no core is written for them,
    CR-2); this orders the significant-but-quiet ones below the prominent parts. From the §1 `loud_level`
    (85th-pct broadband dB) — NOT the self-normalized per-stem energy curve, which peaks at 1 for every
    stem. Relative: weight = clamp(1 + (loud_db − loudest_db)/SPAN, FLOOR, 1). No masking → {} (every stem
    then defaults to full weight 1.0 downstream)."""
    sig = significant_stems(masking)
    if not sig:
        return {}
    lv = {st: (loud_level(stem_broadband_db(masking, st)) or -120.0) for st in sig}
    top = max(lv.values())
    return {st: max(PROMINENCE_FLOOR, min(1.0, 1.0 + (db - top) / PROMINENCE_SPAN_DB))
            for st, db in lv.items()}


def rest_curve(curves, target):
    """The comparison baseline for one stem = the per-bin mean of the OTHER stems' curves.
    `curves`: {stem: [value per time bin]}. None when there's no other stem to compare to."""
    others = [v for s, v in curves.items() if s != target and v]
    if not others:
        return None
    n = min(len(v) for v in others)
    return [sum(v[i] for v in others) / len(others) for i in range(n)]


def _pearson(a, b):
    """Pearson correlation of two sequences; None if undefined (a flat input, or < 2 points)."""
    n = min(len(a), len(b))
    if n < 2:
        return None
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    da, db = [x - ma for x in a], [x - mb for x in b]
    va, vb = sum(x * x for x in da), sum(x * x for x in db)
    if va <= 0 or vb <= 0:                 # a flat curve has no shape to correlate against
        return None
    return sum(x * y for x, y in zip(da, db)) / (va ** 0.5 * vb ** 0.5)


def divergence(stem, rest):
    """How differently a stem's curve moves vs the rest of the track, by SHAPE (scale-invariant).
    0 = same shape (or unmeasurable → don't cry wolf); 1 = exactly opposite. From correlation r:
    (1 − r) / 2."""
    r = _pearson(stem, rest)
    if r is None:
        return 0.0
    return max(0.0, min(1.0, (1.0 - r) / 2.0))


# importance weights — ⟨DECIDE⟩ defaults, to calibrate once on the 3 library tracks (SPEC §B.11)
SCORE_W = {"divergence": 0.5, "persistence": 0.25, "specificity": 0.25}


def candidate_score(*, divergence, persistence, specificity, redundancy, prominence=1.0):
    """Objective usefulness of a candidate card, 0..1 (SPEC §B.11 CR-11): a weighted blend of
    big · persistent · specific, KILLED by redundancy — a card that restates the mix scores ~0 — and
    SCALED by prominence (0..1) so a near-silent stem's card ranks below a loud one's at equal
    divergence (2026-06-22). prominence defaults to 1.0 → unweighted (back-compat)."""
    base = (SCORE_W["divergence"] * divergence
            + SCORE_W["persistence"] * persistence
            + SCORE_W["specificity"] * specificity)
    return max(0.0, min(1.0, base * (1.0 - redundancy) * prominence))


def _persistence(stem, rest):
    """Fraction of bins where the stem sits on the OPPOSITE side of its mean from the rest —
    i.e. how much of the track the divergence actually holds (not one blip). 0..1."""
    n = min(len(stem), len(rest))
    if n < 2:
        return 0.0
    ms, mr = sum(stem[:n]) / n, sum(rest[:n]) / n
    opp = sum(1 for i in range(n) if (stem[i] - ms) * (rest[i] - mr) < 0)
    return opp / n


DIVERGENCE_MIN = 0.35            # provisional τ (A3, validated on Lazy 2026-06-23): real divergences on Lazy
                                # split cleanly — bass/drums 0.16–0.25 (track the rest, excluded), guitar/
                                # other 0.40–0.55 (diverge, admitted) — so 0.35 sits mid-gap, robust. SPEC §B.11
# PRESCRIPTIVE per-stem measures — axes where a divergence from the rest reads as an actionable
# observation (a part fighting the energy arc / dropping out as everything lifts). BRIGHTNESS was
# REMOVED here (SPEC §B.11.1, 2026-06-22): a part being brighter/darker than the rest is not a
# defect — the coach can't know intent (a drum/synth burst may be wanted), so a prescriptive brightness
# card asserts a problem it can't justify. Relative brightness is descriptive / a future viz, not a card.
PER_STEM_MEASURES = ("energy", "density", "stereo_width")  # curves present in result_core_<stem>.json
CORRELATED_MEASURES = ("energy", "density")   # the activity/loudness pair — these two restate one another
                                # (a part that pulls back is usually quieter AND sparser), so they COLLAPSE
                                # into one card (collapse_correlated). Other axes (stereo width, …) are
                                # independent and each earn their own card. E2 2026-06-23, SPEC §B.11.
STEREO_MONO_FLOOR = 0.05        # below this mean stereo width a part is effectively MONO — it has no stereo
                                # image to read, so we suppress its "wider/narrower" card (A1 validity).


def stem_divergence_candidates(stem_cores, measures=PER_STEM_MEASURES, tau=DIVERGENCE_MIN, levels=None):
    """For each significant stem × measure, compare the stem's curve to the REST of the track and
    emit a SCORED candidate when it diverges past `tau` (SPEC §B.11). `stem_cores`: {stem: core_dict}.
    `levels`: optional {stem: prominence 0..1} (from `stem_prominence`) — a near-silent stem's score is
    scaled down so its card ranks below louder parts; default → full weight. Pure — composes rest_curve +
    divergence + _persistence + candidate_score. Sorted by score desc. (Specificity is the stem+measure
    name here; the timed anchor + redundancy/dedupe come when these join the rec pool.) Returns [] when
    nothing clears the bar — silence, not noise."""
    levels = levels or {}
    cands = []
    for measure in measures:
        curves = {s: c.get(measure) for s, c in stem_cores.items() if c.get(measure)}
        for stem, curve in curves.items():
            # per-measure validity (A1): a near-mono part has no stereo image to read → no width card
            if measure == "stereo_width" and \
               (stem_cores[stem].get("stereo_width_mean") or 0) < STEREO_MONO_FLOOR:
                continue
            rest = rest_curve(curves, stem)
            if not rest:
                continue
            d = divergence(curve, rest)
            if d < tau:
                continue
            score = candidate_score(divergence=d, persistence=_persistence(curve, rest),
                                    specificity=0.5, redundancy=0.0,
                                    prominence=levels.get(stem, 1.0))
            # which way the stem leans vs the rest (for wording): its whole-track trend, higher or lower
            direction = "up" if _trend(curve) >= _trend(rest) else "down"
            cands.append({"stem": stem, "measure": measure, "dir": direction,
                          "divergence": round(d, 3), "score": round(score, 3)})
    cands.sort(key=lambda c: -c["score"])
    return cands


def _trend(curve):
    """Normalized whole-track direction of a curve: (late third mean − early third mean) / range,
    clamped to [-1, 1]. 0 when flat or too short."""
    n = len(curve)
    if n < 2:
        return 0.0
    k = max(1, n // 3)
    early, late = sum(curve[:k]) / k, sum(curve[-k:]) / k
    rng = max(curve) - min(curve)
    if rng <= 0:
        return 0.0
    return max(-1.0, min(1.0, (late - early) / rng))


COMPOSITE_TREND_MIN = 0.3        # FROZEN (Phase B, 2026-06-23) — principled floor: a composite fires only
                                # when the MIX has a real directional build/breakdown. NONE of the 3 library
                                # tracks does (mix energy _trend: Lazy 0.195, Shared -0.002, Wobble -0.034),
                                # so composites are correctly SILENT on all 3 — validated as not-crying-wolf,
                                # NOT lowered to fire on a flat arc. Awaiting a building track to see one fire.
                                # Guarded by test_per_stem::CompositeTrendCalibration. SPEC §B.11


def composite_candidates(mix_core, stem_cores, tau=COMPOSITE_TREND_MIN, levels=None):
    """Cross-signal cards — a stem moving AGAINST the whole track (SPEC §B.11, a composite idea,
    e.g. "energy rises but the drums thin out"). Today's rule pairs the mix's energy direction with a
    stem's density direction; opposite + both past `tau` → a scored candidate. `levels`: optional
    {stem: prominence 0..1} so a near-silent stem's composite card ranks below louder parts. Pure. Extend
    with more pairings later. Returns candidates sorted by score desc."""
    levels = levels or {}
    out = []
    me = _trend(mix_core.get("energy") or [])
    for stem, c in stem_cores.items():
        sd = _trend(c.get("density") or [])
        if me >= tau and sd <= -tau:
            rel = "thins_as_track_builds"
        elif me <= -tau and sd >= tau:
            rel = "thickens_as_track_falls"
        else:
            continue
        strength = min(abs(me), abs(sd))
        score = candidate_score(divergence=strength, persistence=strength,
                                specificity=0.6, redundancy=0.0,
                                prominence=levels.get(stem, 1.0))
        out.append({"kind": "composite", "stem": stem, "relation": rel, "score": round(score, 3)})
    out.sort(key=lambda c: -c["score"])
    return out


def collapse_correlated(candidates, measure_order=CORRELATED_MEASURES):
    """Per PART, collapse the CORRELATED activity candidates so each part yields at most ONE activity card
    (SPEC §B.11 "Correlated measures collapse — SMART", 2026-06-22). Energy and density
    (`CORRELATED_MEASURES`) restate one another, so a part firing on both reads as a pile-up ("the mid —
    quieter" + "the mid — sparser"). Rule per stem, WITHIN that pair: SAME direction → keep the STRONGEST
    only; OPPOSITE directions (louder BUT sparser — a genuine contrast) → MERGE into ONE richer card
    carrying every (measure, dir) pair (ordered by `measure_order`). Candidates on OTHER axes (stereo
    width, …) are independent — they pass through as their own card (E2 2026-06-23), so a part can still
    show one activity card AND a stereo card (the per-stem cap bounds the total). COMPOSITE cards are a
    different KIND — passed through untouched. Pure; call BEFORE select_cards. A merged card carries
    `measures` (ordered list of (measure, dir)) in place of the single `measure`/`dir`; everything else
    keeps its original shape."""
    composites = [c for c in candidates if c.get("kind") == "composite"]
    correlated = set(measure_order)
    passthrough = [c for c in candidates                       # non-composite, non-correlated axes (stereo…)
                   if c.get("kind") != "composite" and c.get("measure") not in correlated]
    by_stem = {}
    for c in candidates:
        if c.get("kind") == "composite" or c.get("measure") not in correlated:
            continue
        by_stem.setdefault(c["stem"], []).append(c)
    rank = {m: i for i, m in enumerate(measure_order)}
    collapsed = []
    for stem, group in by_stem.items():
        if len(group) == 1:
            collapsed.append(group[0])
            continue
        if len({c["dir"] for c in group}) == 1:        # same direction → strongest only
            collapsed.append(max(group, key=lambda c: c["score"]))
        else:                                          # opposite → merge into one richer card
            ordered = sorted(group, key=lambda c: rank.get(c["measure"], len(rank)))
            collapsed.append({"stem": stem,
                              "measures": [(c["measure"], c["dir"]) for c in ordered],
                              "score": max(c["score"] for c in group)})
    collapsed += passthrough
    return composites + collapsed


def select_cards(candidates, budget, per_stem_cap=None):
    """Pick the top candidates by score up to a TOTAL `budget`, with a diversity rule so one stem
    can't hog the list: once a stem hits `per_stem_cap` it's held back WHILE other stems still have
    candidates, then any leftover budget is filled ignoring the cap (so we never show fewer than we
    could). Deterministic (SPEC §B.11). Returns the chosen candidates in score order."""
    if budget <= 0 or not candidates:
        return []
    order = sorted(range(len(candidates)), key=lambda i: -candidates[i]["score"])
    chosen, counts = [], {}
    for i in order:                                   # pass 1 — respect the per-stem cap
        if len(chosen) >= budget:
            break
        s = candidates[i]["stem"]
        if per_stem_cap and counts.get(s, 0) >= per_stem_cap:
            continue
        chosen.append(i)
        counts[s] = counts.get(s, 0) + 1
    for i in order:                                   # pass 2 — fill leftover budget, cap ignored
        if len(chosen) >= budget:
            break
        if i not in chosen:
            chosen.append(i)
    return [candidates[i] for i in chosen]


_MEASURE_WORDS = {                       # adjectives (number-neutral): (higher-vs-rest, lower-vs-rest)
    "energy":       ("louder", "quieter"),
    "brightness":   ("brighter", "darker"),
    "density":      ("busier", "sparser"),
    "stereo_width": ("wider", "narrower"),
    "dynamics":     ("more dynamic", "more compressed"),
}

DYNAMICS_DEV_DB = 6.0           # min |dB| a part's dynamic range must sit off the REST's mean to read as an
                                # outlier (E2 2026-06-23, provisional — on the 3 library tracks the clear
                                # cases sit 6–12 dB off: Lazy drums −6.6, Shared vocals +8.7, Wobble drums
                                # −11.9; smaller gaps are mix balance, not a story). SPEC §B.11.
DYNAMICS_DEV_SPAN_DB = 12.0     # |dev| mapped to a 0..1 divergence for scoring (12 dB off → full weight)


def stem_dynamics_candidates(stem_cores, tau_db=DYNAMICS_DEV_DB, levels=None):
    """Per-part DYNAMIC RANGE outlier (E2 — a SCALAR axis, not a curve). Compares each part's
    `vitals.dynamic_range_db` to the MEAN of the other parts; a deviation past `tau_db` becomes a scored
    candidate — lower = "more compressed" (squashed against the rest), higher = "more dynamic". Reuses the
    DR already in `result_core_<stem>.json` (no re-run). `levels` (prominence) ranks a near-silent part
    below loud ones, as elsewhere. Pure; returns candidates sorted by score desc."""
    levels = levels or {}
    drs = {s: (c.get("vitals") or {}).get("dynamic_range_db") for s, c in stem_cores.items()}
    drs = {s: v for s, v in drs.items() if isinstance(v, (int, float))}
    out = []
    for stem, v in drs.items():
        others = [drs[o] for o in drs if o != stem]
        if not others:
            continue
        dev = v - sum(others) / len(others)
        if abs(dev) < tau_db:
            continue
        mag = min(1.0, abs(dev) / DYNAMICS_DEV_SPAN_DB)
        score = candidate_score(divergence=mag, persistence=mag, specificity=0.5,
                                redundancy=0.0, prominence=levels.get(stem, 1.0))
        out.append({"stem": stem, "measure": "dynamics", "dir": "up" if dev > 0 else "down",
                    "divergence": round(mag, 3), "score": round(score, 3)})
    out.sort(key=lambda c: -c["score"])
    return out

_COMPOSITE_WORDS = {                      # stem-vs-whole-track relation → (head phrase, why)
    "thins_as_track_builds":
        ("thins out while the rest of the track builds",
         "As the track gains energy this part gets sparser — it pulls back exactly where everything else "
         "lifts. A deliberate space, or a layer that should grow with the drop?"),
    "thickens_as_track_falls":
        ("fills in while the rest of the track drops back",
         "This part gets busier just as the track pulls back — it pushes forward where everything else "
         "makes room. A deliberate hand-off, or worth a second listen?"),
}


def per_stem_cards(per_stem_core, mix_core=None, character=None, levels=None, budget=4, per_stem_cap=2):
    """Turn the selected per-stem candidates into worded advice cards — rec tuples
    `(cls, when, head, body, fix, t, based_on, axis)`. Two kinds compete in ONE budget: per-stem DIVERGENCE (a stem runs
    against the rest) and COMPOSITE (a stem moves against the whole track, needs `mix_core`). Detailed-only
    by default = no timecode `t` (Simple hides non-timecoded recs, INV-18). `levels` (from `stem_prominence`)
    ranks a near-silent part's cards below the louder parts. Names the PART via its character label, never
    the raw Demucs stem (memory track-coach-stem-labels). Empty input → []. SPEC §B.11."""
    if not per_stem_core:
        return []
    cands = stem_divergence_candidates(per_stem_core, levels=levels)
    if mix_core:
        cands = cands + composite_candidates(mix_core, per_stem_core, levels=levels)
    cands = cands + stem_dynamics_candidates(per_stem_core, levels=levels)   # scalar DR axis (E2)
    cands = collapse_correlated(cands)        # collapse the activity pair; other axes stay independent
    chosen = select_cards(cands, budget=budget, per_stem_cap=per_stem_cap)

    def part(stem):
        lbl = ((character or {}).get(stem, {}) or {}).get("label")
        return lbl or "a part"

    out = []
    for c in chosen:
        p = part(c["stem"])
        if c.get("kind") == "composite":
            worded = _COMPOSITE_WORDS.get(c["relation"])
            if not worded:
                continue
            phrase, why = worded
            based = f"the {p} read against the whole-track arc (a cross-signal move)."   # §B.13
            out.append(("concept", f"Layers · the {p}", f"The {p} {phrase}", why, "", None, based, None,
                        "storyPanel"))   # §B.13 INV-48a — a per-stem card's evidence is the player's lanes
            continue
        if "measures" in c:                   # merged opposite-direction card ("louder but sparser")
            adjs = []
            measures = []
            for measure, dr in c["measures"]:
                w = _MEASURE_WORDS.get(measure)
                if w:
                    adjs.append(w[0] if dr == "up" else w[1])
                    measures.append(measure)
            if not adjs:
                continue
            adj = " but ".join(adjs)
            based = (f"the {_poss(p)} " + _join_and(_human_measure(m) for m in measures)
                     + " measured against the other parts.")   # §B.13
        else:
            words = _MEASURE_WORDS.get(c["measure"])
            if not words:
                continue
            adj = words[0] if c["dir"] == "up" else words[1]
            based = f"the {_poss(p)} {_human_measure(c['measure'])} measured against the other parts."   # §B.13
        out.append(("concept", f"Layers · the {p}",
                    f"The {p} — {adj} than the rest of the track",
                    f"For much of the track this part runs {adj} than everything else, pulling against "
                    f"the mix. A deliberate contrast, or worth a second listen.",
                    "", None, based, None,
                    "storyPanel"))   # §B.13 INV-48a — a per-stem card's evidence is the player's lanes
    return out


def significant_stems(masking):
    """The stems with enough material to read as real content (SPEC CR-2/CR-6/CR-7). The inverse of
    the 'empty' floor: a stem whose representative broadband level (loud_level = 85th-pct of when it
    plays) sits below STEM_EMPTY_FLOOR_DB is INSIGNIFICANT — Demucs barely filled it (Lazy_Sparks
    vocals −92 dB / piano −88 dB), so analysing it would be reading noise. Per-stem analysis MUST be
    gated through this so we never present a number from a silent stem as fact, and so any future
    per-stem self-similarity (CR-6) runs only on real material. Returns names in masking order."""
    if not masking:
        return []
    return [st for st in masking.get("stems_analysed", [])
            if (loud_level(stem_broadband_db(masking, st)) or -120) >= STEM_EMPTY_FLOOR_DB]


# ── Near-silent stem identification (INV-STEMNAME-NEARSILENT-ID, s46) ──────────────────────────────
# A near-silent stem carries an IDENTIFIED label — the mapped .als track name when the stemmap has a
# clear match, else a 5-way frequency-band word derived from the stem's own spectral centroid (or its
# loudest band when centroid is absent). Always suffixed " (near-silent)". Never bare "near-silent",
# never the raw Demucs family word. Two near-silent stems in the same widget must have distinct labels.

# 5-way band thresholds for near-silent labels — finer than the 3-way LOW/MID/HIGH in stem_character
# so two empty stems in different sub-ranges can still have distinct words (e.g. low-mid vs mid).
_NS_BAND_THRESHOLDS = [
    (200.0,   "low"),
    (600.0,   "low-mid"),
    (2000.0,  "mid"),
    (5000.0,  "mid-high"),
    (float("inf"), "high"),
]

_NS_BAND_KEY_MAP = {
    "sub": "low", "low": "low", "low_mid": "low-mid",
    "mid": "mid", "hi_mid": "mid-high", "air": "high",
}


def _ns_band_from_centroid(hz):
    """Map a spectral centroid (Hz) → 5-way band word for a near-silent label."""
    for threshold, word in _NS_BAND_THRESHOLDS:
        if hz < threshold:
            return word
    return "high"


def _ns_band_from_band_rms(masking, st):
    """Dominant band word from band_rms_db medians when centroid is absent. Deterministic tiebreak:
    first BAND_ORDER element wins when all bands are equal (both-silent case)."""
    bb = (masking.get("band_rms_db") or {}).get(st, {})
    best_band, best_val = None, -9999.0
    for b in BAND_ORDER:
        vals = bb.get(b) or []
        if vals:
            m = median(vals)
            if m > best_val:
                best_val = m
                best_band = b
    return _NS_BAND_KEY_MAP.get(best_band, "mid") if best_band else "mid"


def _ns_raw_label(st, masking, stemmap):
    """Raw base word for a near-silent stem — either the mapped .als track name (stemmap clear match)
    or a frequency-band word (centroid → 5-way split → fallback to band_rms_db). No qualifier yet."""
    if stemmap:
        sm = ((stemmap or {}).get("stems", {}) or {}).get(st, {}) or {}
        if sm.get("verdict") == "clear":
            matches = sm.get("track_matches") or []
            if matches and (matches[0] or {}).get("track"):
                return matches[0]["track"]
    cen = (masking.get("spectral_centroid") or {}).get(st)
    if cen is not None:
        return _ns_band_from_centroid(float(cen))
    return _ns_band_from_band_rms(masking, st)


def _nearsilent_display_map(omitted_stems, masking, stemmap):
    """Build {stem: identified_label + ' (near-silent)'} for all near-silent stems, ensuring
    INV-STEMNAME-NEARSILENT-ID: every label is identified (not bare 'near-silent') AND distinct.
    Disambiguation: if two stems get the same base word, suffix ' 1', ' 2', … (sorted alphabetically
    on the stems for determinism). A trailing-number suffix is the SPEC-permitted 'trailing distinguisher'."""
    raw = {}
    for st in sorted(omitted_stems):  # sorted for determinism
        raw[st] = _ns_raw_label(st, masking, stemmap)

    # Group by raw word — find collisions
    by_word = {}
    for st, word in raw.items():
        by_word.setdefault(word, []).append(st)

    result = {}
    for word, stems in by_word.items():
        if len(stems) == 1:
            result[stems[0]] = word + " (near-silent)"
        else:
            for idx, st in enumerate(stems, 1):
                result[st] = f"{word} {idx} (near-silent)"

    return result


LEAK_CORR_MIN = 0.2     # min loudness-correlation to call two stems "bleeding" into each other
LEAK_LOUDER_DB = 10.0   # a band's carrier must be at least this much louder to claim a stem's
                        # dominant band is really that carrier bleeding in (conservative — protects
                        # the genuine low-end carrier, which is only a few dB above its neighbours).


def leakage_caveats(masking, rhythm):
    """Bands whose energy is plausibly BLEED from a louder, correlated neighbour, not the stem's own
    content (SPEC CR-4). Conservative + identity-agnostic: for each SIGNIFICANT stem we check ONLY its
    single loudest band — the colour a viewer reads as that stem's content. If a DIFFERENT stem carries
    that band (is loudest in it across the mix), sits ≥ LEAK_LOUDER_DB louder there, AND rises/falls WITH
    this stem (loudness correlation r ≥ LEAK_CORR_MIN), the band is flagged as likely that carrier's
    bleed. We CAVEAT, never suppress (CR-4a: bleed is time-varying, so don't delete the band — just warn
    against attributing it). A naive 'any louder correlated neighbour' rule over-flags (a loud broadband
    stem becomes the culprit for everything), so we deliberately take only the dominant band + a wide
    margin. Returns a list of caveat dicts (empty when separation is clean)."""
    if not masking or not rhythm:
        return []
    leaks = (rhythm.get("separation") or {}).get("leakage") or []
    rmap = {}
    for d in leaks:
        rmap[(d["a"], d["b"])] = d["r"]
        rmap[(d["b"], d["a"])] = d["r"]
    stems = masking.get("stems_analysed", [])
    if not stems:
        return []
    bm = {st: {b: (median(masking["band_rms_db"][st].get(b, [-120])) or -120) for b in BAND_ORDER}
          for st in stems}
    carrier = {b: max(stems, key=lambda s: bm[s][b]) for b in BAND_ORDER}
    out = []
    for st in significant_stems(masking):
        b = max(BAND_ORDER, key=lambda bb: bm[st][bb])   # the stem's dominant band
        c = carrier[b]
        if c == st:
            continue                                     # the stem owns its dominant band → no bleed
        r = rmap.get((st, c), 0.0)
        if bm[c][b] >= bm[st][b] + LEAK_LOUDER_DB and r >= LEAK_CORR_MIN:
            out.append({"stem": st, "band": b, "band_label": BAND_LABEL.get(b, b), "source": c,
                        "stem_db": round(bm[st][b], 1), "source_db": round(bm[c][b], 1),
                        "gap_db": round(bm[c][b] - bm[st][b], 1), "r": round(r, 2)})
    return out


def stem_repetition(per_stem_selfsim, masking):
    """Per-SIGNIFICANT-stem repetition, read from each stem's OWN self-similarity (SPEC CR-6: "this part
    returns" must be grounded in the stem's real recurring material, not only the mix). Gated through
    significant_stems() so a near-silent stem is never read for repetition (CR-2 + the G7 contract).
    `recurrence` ∈ 0..1: 0 = every section distinct (the part keeps evolving), →1 = the same few sections
    recur. `top_count` = how many times the most-recurring section appears (a returning hook/motif).
    Returns [] when there's no per-stem data yet (the pipeline computes it only for significant stems)."""
    if not per_stem_selfsim:
        return []
    sig = set(significant_stems(masking)) if masking else set(per_stem_selfsim)
    out = []
    for st in per_stem_selfsim:
        if st not in sig:
            continue                                   # never read repetition off an insignificant stem
        segs = (per_stem_selfsim[st] or {}).get("segments", [])
        n = len(segs)
        if n < 2:
            continue
        labels = per_stem_selfsim[st].get("n_labels") or len({s.get("letter") for s in segs})
        counts = {}
        for s in segs:
            counts[s.get("letter")] = counts.get(s.get("letter"), 0) + 1
        top_letter = max(counts, key=counts.get)
        out.append({"stem": st, "segments": n, "labels": labels,
                    "recurrence": round(1 - labels / n, 2),
                    "top_letter": top_letter, "top_count": counts[top_letter]})
    return out


# ── "Where does it get boring?" (2026-06-22): for an EVOLVING track, the point after which it stops
# introducing new material and only recombines sections you've already heard. Honest + measured from the
# self-sim segment letters (same letter = a section that returns); NOT a value judgement — the rec frames it
# as "no new material from here", with the action left to the producer. Gated so it never fires on a track
# that doesn't develop in the first place, nor when new ideas keep arriving to the end.
MIN_DEV_SECTIONS = 3      # need ≥3 DISTINCT sections introduced for "stops developing" to mean anything
PLATEAU_MIN_FRAC = 0.30   # the no-new-material tail must be ≥30% of the track to be worth a word


def development_plateau(selfsim, dur):
    """Onset (s) after which an evolving track introduces NO new section, or None. Reads the self-sim
    segments: the onset = the END of the last segment that introduces a new letter; everything after only
    recurs. Returns {onset_s, tail_frac, n_sections} when the track develops (≥MIN_DEV_SECTIONS distinct
    sections) AND the no-new tail is ≥PLATEAU_MIN_FRAC; else None (doesn't develop / never plateaus)."""
    segs = (selfsim or {}).get("segments", [])
    if len(segs) < MIN_DEV_SECTIONS or not dur:
        return None
    seen, last_new_end = set(), 0.0
    for s in sorted(segs, key=lambda s: s.get("t0", 0.0)):
        L = s.get("letter")
        if L not in seen:
            seen.add(L)
            last_new_end = s.get("t1", s.get("t0", 0.0))   # end of the segment that introduced this section
    if len(seen) < MIN_DEV_SECTIONS:
        return None
    tail_frac = (dur - last_new_end) / dur
    if tail_frac < PLATEAU_MIN_FRAC:
        return None                                        # new material arrives late enough → not a plateau
    return {"onset_s": round(last_new_end, 1), "tail_frac": round(tail_frac, 2), "n_sections": len(seen)}


ONSET_PERCUSSIVE = 3.0   # onsets/sec at/above which a stem reads as percussive (transient-driven), else sustained

# ── G13: split the honest "tonal" umbrella → melody / lead / chord / pad / noise (2026-06-21) ──
# All four are ⟨DECIDE⟩ defaults to tune on the 3 library tracks (see docs/SPEC.md §B.4); every one is a
# threshold on a MEASURED quantity (polyphony, loudness, note length, spectral flatness) — no vocabulary,
# no ML prompts (these were rejected). Each resulting label is `approx`.
POLY_FRAC_MONO_MAX = 0.20  # poly_frac (share of sounding-time with ≥2 notes) below this ⇒ MONOPHONIC
FLATNESS_NOISE_MIN = 0.30  # energy-weighted spectral flatness at/above this ⇒ broadband NOISE, no clear pitch.
                           # INERT on real harmonic stems (their flatness is ~0.000–0.003) — the `noise`
                           # bucket is DEFERRED until a calibrated/relative measure; kept so it never fires
                           # a wrong label rather than claiming noise we can't detect (verify-by-deed 2026-06-21).
PAD_SUSTAIN_MIN    = 0.7   # G13 pad-vs-chord: a polyphonic tonal stem whose envelope CONTINUITY (masking
                           # `sustain`) is at/above this drones → "pad"; below ⇒ rhythmic "chord" stabs.
                           # Calibrated on real stems (a drone-pad reads ~0.88, a chord/arp ~0.49 — see
                           # JOURNAL 2026-06-21). Replaces the broken note-length proxy. Tune as more tracks land.
HP_DROP_DB         = 15.0  # G14: a sustained stem that LOSES at least this much loudness when high-passed
                           # (sub+low ignored) is a genuine low carrier → "bass". Relative drop, not an
                           # absolute floor: a loud bass keeps a residue above the empty-floor yet still
                           # drops ~22–27 dB; non-bass stems drop 0–8 dB (verify-by-deed, 2 tracks).

HP_BANDS = ("low_mid", "mid", "hi_mid", "air")   # what survives a ~250 Hz high-pass (sub+low removed)

# G18 (s14): per-stem spectral CENTROID thresholds for freq-role (preferred over the high-pass when the
# masking carries `spectral_centroid`). A bass/sub sits below LOW; air/cymbals/very-bright above HIGH;
# everything between is "mid". Deed (Lazy_Sparks): bass 117, drums 203, guitar 1007, other 942 Hz.
LOW_CENTROID_HZ    = 250.0
HIGH_CENTROID_HZ   = 3500.0


def _comb_db(vals):
    """Combine per-band dB levels into one broadband dB (power sum). Bands at/below the −119 sentinel are
    treated as silence. Returns −120.0 when nothing is present."""
    p = sum(10 ** (v / 10.0) for v in vals if v is not None and v > -119)
    return round(10 * math.log10(p), 1) if p > 0 else -120.0


def polyphony(notes):
    """Share of a stem's SOUNDING time during which ≥2 transcribed notes overlap (0..1). A monophonic
    line (melody/lead) plays ~one note at a time → ~0; stacked chords/pads → high. Deterministic interval
    sweep over the basic-pitch note events; returns None when there's nothing to measure (so the caller
    keeps the honest "tonal" umbrella rather than inventing a verdict from no data — CR-1)."""
    evs = [(float(n["t"]), float(n["t"]) + float(n["dur"])) for n in (notes or [])
           if n.get("dur", 0) and float(n["dur"]) > 0]
    if not evs:
        return None
    pts = sorted([(s, 1) for s, _ in evs] + [(e, -1) for _, e in evs])
    sounding = poly = 0.0
    depth = 0
    prev = pts[0][0]
    for t, d in pts:
        span = t - prev
        if depth >= 1:
            sounding += span
        if depth >= 2:
            poly += span
        depth += d
        prev = t
    return round(poly / sounding, 3) if sounding > 0 else None




def stem_character(masking, rhythm, leakage=None, per_stem_notes=None):
    """A DETERMINISTIC, honest CHARACTER label per SIGNIFICANT stem, from measured features only — so the
    same track always yields the same labels (a hard requirement: no per-run renaming). We describe
    what the SOUND is, never assert which instrument/synth made it (Demucs labels are approximations;
    [[track-coach-stem-labels]]). Measured axes:
      • frequency role — low / mid / high. Percussive stems: which third (by loud-level) carries the energy.
        Sustained stems (G14): "low/bass" ONLY if HIGH-PASSING (dropping sub+low) strips
        ≥ HP_DROP_DB of loudness — so a bass collapses but a mid stem with bled-in low (guitar) keeps its
        real mid content and is NOT mislabeled 'bass'. Sidesteps the bleed question, so CR-4 stays UI-only.
      • temporal character — percussive (onset_rate ≥ ONSET_PERCUSSIVE) vs sustained.
      • G13 — for the mid·sustained case (the old honest 'tonal' umbrella), split into lead/melody/chord/
        pad/noise from polyphony (basic-pitch notes, `per_stem_notes`), per-stem spectral flatness
        (`masking.spectral_flatness`), relative loudness and mean note length. See docs/SPEC.md §B.4.
    Returns {stem: {label, role, percussive, confidence}}. confidence 'clear' for the trusted low end
    (bass/drums), 'approx' otherwise. confidence is no longer shown as a "≈" in the UI (s14): one
    plain label per stem, and the uncertain mid umbrella shows its base role ("mid"/"high"), never "tonal"."""
    if not masking:
        return {}
    rmap = (rhythm or {}).get("rhythm", {}) if rhythm else {}
    flat_map = masking.get("spectral_flatness") or {}
    sustain_map = masking.get("sustain") or {}
    notes_map = per_stem_notes or {}
    GROUP = {"low": ("sub", "low"), "mid": ("low_mid", "mid"), "high": ("hi_mid", "air")}
    LABEL = {                                            # (role, percussive) → (short label, confidence)
        ("low", True): ("kick", "clear"),  ("low", False): ("bass", "clear"),
        ("mid", True): ("perc", "approx"), ("mid", False): ("mid", "approx"),
        ("high", True): ("hats", "approx"), ("high", False): ("high", "approx"),
    }
    # A design call (2026-06-21 s14, docs/SPEC.md §B.7): TRUST the stem for the reliable low-end families
    # instead of re-deriving (and sometimes DEMOTING) them. Demucs separates bass & drums cleanly and
    # We read the low end reliably — so a `bass` stem is "bass" (we do NOT run it through
    # the G14 high-pass, which on a synth bass with mid harmonics wrongly fell to "tonal"), and a `drums`
    # stem is "drums" (NOT reduced to "kick"). Only these two exact families are trusted by name; every
    # other (electronic) stem name stays untrusted and is read by measurement ([[track-coach-stem-labels]]).
    TRUSTED = {"bass": ("bass", "low", False), "drums": ("drums", "low", True)}
    # `leakage` is accepted for signature stability but no longer feeds the ROLE: G14 (high-pass drop)
    # makes the bass-vs-mid call without arguing whether a low band is bleed, so CR-4 stays UI-only.
    out = {}
    mono = {}    # st -> loud_level (dB); resolved into lead (loudest) vs melody after the loop
    for st in significant_stems(masking):
        if st in TRUSTED:                                # trust bass/drums by identity — no demotion
            lab, role, perc = TRUSTED[st]
            out[st] = {"label": lab, "role": role, "percussive": perc, "confidence": "clear"}
            continue
        # Per-band level = loud_level (85th pct of when it plays), NOT median: an intermittent stem (a
        # bassline that hits some beats) reads as ~silence at the median in every band (verify-by-deed
        # 2026-06-21), which makes any freq-role noise. Judge by the LOUD content (significant_stems' stat).
        bm = {b: (loud_level(masking["band_rms_db"][st].get(b, [-120])) or -120) for b in BAND_ORDER}
        onset = (rmap.get(st) or {}).get("onset_rate")
        _n = notes_map.get(st, {})
        pf = polyphony(_n.get("notes") if isinstance(_n, dict) else _n)
        # G15: a stem counts as PERCUSSION only if it's transient AND not pitched. `pf is not None` means
        # basic-pitch transcribed real notes → the stem carries pitch, so it's tonal even when rhythmic
        # (a stabby pad/arp or a choppy vocal). Without notes (pf is None) we fall back to onset alone, so
        # drums (no transcription) stay percussive and nothing regresses when notes are absent.
        pitched = pf is not None
        percussive = (onset is not None and onset >= ONSET_PERCUSSIVE) and not pitched
        if percussive:
            grp = {g: _comb_db([bm[b] for b in bands]) for g, bands in GROUP.items()}
            role = max(grp, key=grp.get)                 # kick (low) / perc (mid) / hats (high) — G12 onset path
        else:
            cen = (masking.get("spectral_centroid") or {}).get(st)
            if cen is not None:
                # G18 (s14, the per-stem frequency analyzer): the spectral CENTROID — where the stem's
                # energy actually sits — is a robust freq-role signal that replaces the crude 6-band high-pass
                # (which mislabeled a synth bass). Bass sits low (~120 Hz), pads/leads mid (~1 kHz), air/
                # cymbals high (> HIGH_CENTROID_HZ). Verified by deed: bass 117 Hz, guitar 1007 Hz.
                role = "low" if cen < LOW_CENTROID_HZ else ("high" if cen > HIGH_CENTROID_HZ else "mid")
            else:
                # Fallback (pre-0.8.14 masking with no centroid): G14 high-pass drop — a sustained stem is a
                # genuine low carrier only if HIGH-PASSING it (dropping sub+low) strips ≥ HP_DROP_DB of its
                # loudness (relative drop, not an absolute residue floor).
                full = _comb_db([bm[b] for b in BAND_ORDER])
                hp = _comb_db([bm[b] for b in HP_BANDS])
                if full - hp >= HP_DROP_DB:
                    role = "low"
                else:
                    role = "high" if _comb_db([bm["hi_mid"], bm["air"]]) > _comb_db([bm["low_mid"], bm["mid"]]) else "mid"
        label, conf = LABEL[(role, percussive)]
        # G13: refine ONLY the mid·sustained umbrella; every other G12 label is unchanged.
        if role == "mid" and not percussive:
            flat = flat_map.get(st)
            if flat is not None and flat >= FLATNESS_NOISE_MIN:
                label = "noise"                          # broadband, no clear pitch to call melody vs chord
            elif pf is None:
                label = "mid"                            # no transcribed notes → show the base role, not jargon (s14)
            elif pf < POLY_FRAC_MONO_MAX:                # monophonic line: lead vs melody decided by loudness below
                mono[st] = loud_level(stem_broadband_db(masking, st)) or -120
                label = "melody"                         # provisional; promoted to "lead" if it's the loudest
            else:                                        # polyphonic: held pad vs rhythmic chord stabs
                sus = sustain_map.get(st)                 # envelope continuity (masking); drone ≥ PAD_SUSTAIN_MIN
                label = "pad" if (sus is not None and sus >= PAD_SUSTAIN_MIN) else "chord"
        out[st] = {"label": label, "role": role, "percussive": percussive, "confidence": conf}
    # The SINGLE most prominent monophonic line is the LEAD; any other mono lines stay "melody". (Was:
    # everyone within LEAD_MARGIN_DB of the loudest → produced TWO "lead"s on real data, 2026-06-21.)
    # Loudness is the weakest signal of the set, so this stays `approx`; deterministic via stem order on ties.
    if mono:
        out[max(mono, key=mono.get)]["label"] = "lead"
    return out


# ── Development-mode read (SPEC §B.12, 2026-06-23) — which FORM the track develops in. Feeds the
# Producer's READ (an OBSERVATION, not a card): "grows by loud + bright; stereo & density sit idle". The four
# trends are all `_common.trend` = Pearson corr of the curve with its time index, in [−1,1], SAME unit
# (direction/monotonicity, not magnitude) — so one threshold is valid across all four (prover F4, 2026-06-23).
DEV_DOMINANT = 0.12   # |trend| ≥ this ⇒ the track develops by this axis (calibrated by deed on the 3 tracks)
DEV_IDLE     = 0.10   # |trend| < this ⇒ the axis sits idle (flaggable only when something else dominates)
# axis label · core key · rising-word · falling-word (the read needs the DIRECTION, not just the axis — any
# axis can be dominant while moving DOWN, so we never say "grows by brightness" on a darkening track, F1).
_DEV_AXES = (
    ("energy",       "energy_trend",       "gets louder",      "pulls back"),
    ("brightness",   "brightness_trend",   "brightens",        "darkens"),
    ("density",      "density_trend",      "gets busier",      "thins out"),
    ("stereo width", "stereo_width_trend", "widens the image", "tightens the image"),
)


def development_mode(core):
    """Which FORM the track develops in (SPEC §B.12 / INV-32). Pure + deterministic.
    Returns {"dominant": [{"axis","trend","dir","phrase"}...sorted by |trend| desc], "idle": [axis...]}.
    • dominant = axes with |trend| ≥ DEV_DOMINANT, each carrying its DIRECTION (sign → phrase).
    • idle = axes with |trend| < DEV_IDLE, returned ONLY when ≥1 axis is dominant.
    • flat track (no dominant axis) → empty dominant AND empty idle: the read then adds NO development
      sentence (it must not double-cover the `energy_flat` card)."""
    if not core:
        return {"dominant": [], "idle": []}
    dom, idle = [], []
    for axis, key, up, down in _DEV_AXES:
        tr = core.get(key)
        if tr is None:
            continue
        mag = abs(tr)
        if mag >= DEV_DOMINANT:
            dom.append({"axis": axis, "trend": round(tr, 3),
                        "dir": "up" if tr > 0 else "down",
                        "phrase": up if tr > 0 else down})
        elif mag < DEV_IDLE:
            idle.append(axis)
    if not dom:
        return {"dominant": [], "idle": []}
    dom.sort(key=lambda d: -abs(d["trend"]))
    return {"dominant": dom, "idle": idle}


def _poss(name):
    """Possessive that reads right when the part ends in 's': drums → drums', lead → lead's."""
    return name + ("'" if name.endswith("s") else "'s")


def _human_measure(m):
    """Measure key → plain words for the based-on line (stereo_width → 'stereo width')."""
    return m.replace("_", " ")


def _join_and(items):
    """['a','b','c'] → 'a, b and c'; [] → ''."""
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _development_html(core):
    """SPEC §B.12 — the development-mode OBSERVATION as a subtle line at the top of the Producer's read.
    COMPUTED (the build owns it) so it's consistent across tracks and can't be forgotten — never also
    hand-write it in the narrative. Names each dominant axis WITH its direction; flags the idle axes as
    an unused option, never a defect. Empty string on a flat track (the read then says nothing about
    development, deferring to the `energy_flat` card)."""
    dm = development_mode(core)
    if not dm["dominant"]:
        return ""
    sent = "Across the track it " + _join_and(d["phrase"] for d in dm["dominant"])
    if dm["idle"]:
        one = len(dm["idle"]) == 1
        verb = "stays" if one else "stay"
        noun = "an axis" if one else "axes"
        sent += " — but " + _join_and(dm["idle"]) + f" {verb} almost still, {noun} you're not yet using"
    return ('<p class="readdev"><span class="devlab">How it develops</span> '
            + _esc(sent) + ".</p>")


def build_recommendations(core, detail, masking, S, als_overlay=None, stemmap=None, rhythm=None, character=None, repetition=None, selfsim=None):
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
        based = REC_BASED.get(key, "").format(**kw)   # SPEC §B.13 — where this card came from (plain)
        axis = REC_AXIS.get(key)                      # §D.6 stage-2: FP axis for divergence/on-style calc
        ev = REC_TARGET.get(key, "storyPanel")        # §B.13 INV-48a — the panel the click leads to
        recs.append((cls, tpl["header"].format(**kw), tpl["title"].format(**kw),
                     tpl["body"].format(**kw), fix.format(**kw) if fix else "",
                     round(_t, 2) if _t is not None else None, based, axis, ev))

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

    # "Where does it get boring?" — for an evolving track, the onset after which no new section is
    # introduced. Measured from the self-sim letters; gated so it only fires when the track actually develops.
    plat = development_plateau(selfsim, dur)
    if plat:
        add("plateau", _t=plat["onset_s"], onset=fmt_t(plat["onset_s"]),
            tail_pct=plat["tail_frac"] * 100, n=plat["n_sections"])

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
        feel = next(ph for thr, ph in SWING_FEEL_BANDS if sw >= thr)
        add("swing", sw=sw, feel=feel)

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
            rel = next((h if hot else d) for thr, h, d in TONAL_SCALE_STEPS if abs(dev) >= thr)
            add("tonal_resonance", band=band, dev=dev, rel=rel,
                kind=("resonance / build-up" if hot else "dip / hole"), flavour=flavour,
                action=("Dip" if hot else "Lift"), dir=("cut" if hot else "boost"),
                amt=min(4.0, abs(dev) * 0.6))

    if masking:
        empties = [st for st in masking.get("stems_analysed", [])
                   if (loud_level(stem_broadband_db(masking, st)) or -120) < STEM_EMPTY_FLOOR_DB]

        def loudest_in(band):
            best, bestv = None, -999
            for st in masking.get("stems_analysed", []):
                v = median(masking["band_rms_db"][st].get(band, [-120]))
                if v is not None and v > bestv:
                    best, bestv = st, v
            return best
        sub_carrier = loudest_in("sub")

        # G17 (SPEC §B.6) — name a stem in a rec by its measured character, else its CLEARLY-mapped
        # real project track, else a neutral phrase. NEVER the raw Demucs family name
        # ([[track-coach-stem-labels]]). Used by late_entry, where the stem is near-silent so a G16
        # character label is usually absent and we must fall through to the stemmap / neutral.
        def _part_name(st):
            lbl = ((character or {}).get(st, {}) or {}).get("label")
            if lbl:
                return "A part ({})".format(lbl)
            sm = ((stemmap or {}).get("stems", {}) or {}).get(st, {}) or {}
            if sm.get("verdict") == "clear":
                trk = (sm.get("track_matches") or [{}])[0].get("track")
                if trk:
                    return "“{}”".format(trk)
            return "A new element"

        # NOTE: separation-quality findings (empty/smeared stems, residual, untrustworthy
        # bass) are NOT surfaced as recommendations — they're tool artefacts, not music
        # advice, and aren't actionable for the producer. They live in the "Stem ↔ project"
        # and "rhythm & separation" panels as honest caveats instead.

        # G16 — INDIVIDUAL masking recs: one card per masked SIGNIFICANT stem, naming both parts by their
        # measured character (never the raw Demucs name [[track-coach-stem-labels]]), the band's frequency
        # range, the % masked, and the worst moment. Falls back to the old generic card when we don't have
        # stem characters (no masking+rhythm → can't name the parts honestly).
        BAND_RANGE = {"sub": "20–80 Hz", "low": "80–250 Hz", "low_mid": "250–600 Hz",
                      "mid": "600 Hz–2 kHz", "hi_mid": "2–6 kHz", "air": "6–16 kHz"}

        def _lbl(st):
            return ((character or {}).get(st, {}) or {}).get("label") or "a part"

        def _verb(lbl):
            """Verb form for '{lbl} {_verb(lbl)} silent' — plural labels (drums, hats) take 'are'."""
            return "are" if lbl in ("drums", "hats") else "is"
        real = [(z, s) for z, s in masking.get("masking_summary", {}).items()
                if s["pct_masked"] > 0 and z.split("__")[-1] not in empties]
        if real and character:
            for zone, s in real:
                band, mid = zone.split("__")[0], zone.split("__")[-1]
                flags = masking.get("masking_flags", {}).get(zone, [])
                low_stem = flags[0]["low_stem"] if flags else "bass"
                worst = max(flags, key=lambda f: f["diff_db"]) if flags else None
                # s14 idea (a): name the PRECISE collision frequency when the spectra pinpoint it; else
                # keep the coarse band range. `spot` = where in the title; `notch` = the cut target.
                band_lbl = BAND_RANGE.get(band, band)
                spec = masking.get("spectrum") or {}
                freqs = masking.get("spectrum_freqs")
                mask_hz = mask_collision_freq(spec.get(low_stem), spec.get(mid),
                                              BAND_HZ.get(band, (0, 0)), freqs)
                hz = fmt_hz(mask_hz)
                spot  = "around <b>{}</b> (in {})".format(hz, band_lbl) if hz else "around <b>{}</b>".format(band_lbl)
                notch = "around <b>{}</b>".format(hz or band_lbl)
                add("masking_stem", _t=(worst["time_s"] if worst else None),
                    low_lbl=_lbl(low_stem), mid_lbl=_lbl(mid), mid_v=_verb(_lbl(mid)),
                    spot=spot, notch=notch, pct=s["pct_masked"],
                    worst_t=fmt_t(worst["time_s"]) if worst else "—")
        elif real:                                          # no characters → old generic line
            lines = "; ".join(R["masking_line"].format(mid="a part", pct=s["pct_masked"]) for z, s in real)
            add("masking_real", lines=lines)
        elif not empties:
            add("masking_clean")

        # (e) per-stem repetition → WORDS (CR-6, 0.8.18): contrast the part that EVOLVES (low recurrence,
        # carrying the development) with the ones that LOOP. Recurrence is measured per stem from its OWN
        # self-similarity; we name parts by their character label, never the raw Demucs name (hard req
        # [[track-coach-stem-labels]]) — so a stem without a label is skipped. Fires only on a real spread.
        def _has_lbl(st):
            return bool(((character or {}).get(st, {}) or {}).get("label"))

        def _and_join(labels):
            # DEDUPE by label, preserving order: two stems can share a character label ("mid"), and
            # "the mid, the mid and the drums" is the salad removed in §B.7 — collapse to "the mid".
            seen, xs = set(), []
            for l in labels:
                if l not in seen:
                    seen.add(l)
                    xs.append("the " + l)
            return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]

        rep = [r for r in (repetition or []) if r["stem"] not in empties and _has_lbl(r["stem"])]
        if character and len(rep) >= 2:
            evolvers = [r for r in rep if r["recurrence"] <= EVOLVE_MAX_RECURRENCE]
            loopers  = [r for r in rep if r["recurrence"] >= LOOP_MIN_RECURRENCE]
            if evolvers and loopers:
                ev = min(evolvers, key=lambda r: r["recurrence"])
                add("stem_evolves",
                    evolver=_lbl(ev["stem"]),
                    loopers=_and_join([_lbl(r["stem"]) for r in loopers]),
                    evo_r="{:.2f}".format(ev["recurrence"]),
                    loop_r="{:.2f}".format(min(r["recurrence"] for r in loopers)))

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
            # G17/CR-1 ("don't paint silence"): the ENTERING PEAK must clear the real-content floor,
            # else this is a near-silent separation artifact (Lazy_Sparks vocals: peak −61 dB, verdict
            # 'empty'), not a musical event. Peak-based, not loud_level: a genuine late accent is silent
            # most of the track so its 85th-pct is low — only the peak proves it's real.
            if (mmed < STEM_EMPTY_FLOOR_DB and arr[li] > mmed + 20 and tb_m[li] > 0.8 * dur
                    and arr[li] >= STEM_EMPTY_FLOOR_DB):
                add("late_entry", _t=tb_m[li], part=_part_name(st), t=fmt_t(tb_m[li]))
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


def _selfsim_stable(selfsim):
    """CR-5c: only trust the self-similarity segmentation as the structure SOURCE when it carries
    enough distinct material — ≥3 segments AND ≥2 recurrence labels. A quiet/uniform track that
    over- or under-segments falls back to the coarse section bar instead."""
    if not selfsim:
        return False
    segs = selfsim.get("segments", [])
    return len(segs) >= 3 and selfsim.get("n_labels", len({s.get("letter") for s in segs})) >= 2


def build_story(core, als_overlay, seg_bounds=None):
    """Synthesise the high-level 'Track Story': scenes (named + pattern letter),
    one intensity/power curve, key moments, and a compact family-presence texture.
    Combines audio arcs (energy/density/brightness) with the project arrangement.

    seg_bounds: internal segment boundaries (s) to cut scenes on. When given (the self-sim
    segmentation, CR-5a) the structure follows the music's real recurrence, not the coarse
    agglomerative `section_bounds_s` that flattened Lazy_Sparks' C E C E C into one blob."""
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

    # scenes from segment boundaries; classify by intensity + arrangement. Prefer the self-sim
    # boundaries (seg_bounds, CR-5a) when supplied; else fall back to the coarse section bar.
    src_bounds = seg_bounds if seg_bounds is not None else core.get("section_bounds_s", [])
    bounds = [x for x in src_bounds if 0 < x < dur]
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
    LIFT = 0.12        # how much LOWER the preceding section must sit (in tier) for a high section
                       # to count as a Drop — the required "a dip before the lift" (CR-5).
    for i, (a, b2) in enumerate(segs):
        ti = seg_t[i]
        tier = ti / mx if mx > 0 else 0.0
        prev = seg_t[i - 1] if i > 0 else None
        nxt = seg_t[i + 1] if i < len(segs) - 1 else None
        prev_tier = (prev / mx) if (prev is not None and mx > 0) else None
        if i == 0 and tier < 0.55:
            name = "Intro"
        elif i == len(segs) - 1 and tier < 0.6:
            name = "Outro"
        elif tier >= 0.8 and prev_tier is not None and prev_tier <= tier - LIFT:
            # a high section that ENTERS after a lower one — the bass drops IN. Numbered AFTER
            # _coalesce_scenes (build_html) so merges can't leave a gap like "Drop, Drop 3" (CR-5).
            name = "Drop"
        elif tier >= 0.8:
            # sustained-high without a preceding dip: loud, but not a drop. ⟨DECIDE settled⟩ → "Main".
            name = "Main"
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


def _coalesce_scenes(scenes, dur):
    """Tidy the structure bar: merge adjacent scenes that share a letter (the same musical part
    continuing — the selfsim letter-remap, or build_story dropping sub-2s segments, can shatter one
    part into slivers and leave gaps), close any gaps, and span the whole track 0..dur. Clean tracks
    (no adjacent same-letter, no gaps) pass through with only the end-snap. Mode-independent: the bar
    is built identically for full and quick, so this changes neither relative to the other."""
    if not scenes:
        return scenes
    sc = sorted((dict(s) for s in scenes), key=lambda s: s.get("t0", 0.0))
    out = [sc[0]]
    for s in sc[1:]:
        prev = out[-1]
        if s.get("letter") == prev.get("letter"):
            # same part continuing → swallow into prev (bridging any gap); keep the longer span's name
            if (s["t1"] - s["t0"]) > (prev["t1"] - prev["t0"]):
                prev["name"] = s.get("name", prev.get("name"))
                prev["tier"] = s.get("tier", prev.get("tier"))
            prev["t1"] = max(prev["t1"], s["t1"])
            if s.get("lead") and not prev.get("lead"):
                prev["lead"] = s["lead"]
        else:
            s["t0"] = prev["t1"]                       # close any gap → contiguous bar
            if s["t1"] > s["t0"] + 0.01:
                out.append(s)
            else:                                       # sliver fully inside prev → fold in
                prev["t1"] = max(prev["t1"], s["t1"])
    out[0]["t0"] = 0.0                                  # fill the ends so the bar spans the track
    out[-1]["t1"] = round(float(dur), 2)
    for s in out:
        s["t0"], s["t1"] = round(s["t0"], 2), round(s["t1"], 2)
    return out


def build_html(core, detail, masking, als, out_path, title, S, als_offset_s=None, stemmap=None,
               rhythm=None, notes=None, drums=None, audio_stems_rel=None, presence_threshold=0.3,
               narrative_md=None, selfsim=None, meta=None, verdict=None, catalog=None, mode="full",
               back_href=None, audio_mix_rel=None, per_stem_selfsim=None, per_stem_notes=None,
               per_stem_core=None, run_dir=None):
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
        analysed = masking.get("stems_analysed", [])
        # CR-2: insignificant (near-silent) stems are DROPPED from per-stem analysis — no heat/bb/viz
        # computed for them (saves compute, and a silent stem must never paint full-colour). They are
        # named in `omitted` so the missing rows read as a decision, not a bug (prover P7).
        stems = significant_stems(masking)
        omitted = [st for st in analysed if st not in stems]
        heat = {st: {b: masking["band_rms_db"][st].get(b, [-120] * masking["total_windows"]) for b in BAND_ORDER}
                for st in stems}
        bb = {st: stem_broadband_db(masking, st) for st in stems}  # broadband dB per bin → "is it playing"
        viz = masking.get("viz")
        if viz and omitted:                       # strip omitted stems from the fine drawing grid too
            viz = dict(viz)
            for key in ("bb", "band"):
                if isinstance(viz.get(key), dict):
                    viz[key] = {k: v for k, v in viz[key].items() if k not in omitted}
        # per-stem frequency analyzer (0.8.14): forward the spectral centroid + log-freq spectrum profile
        # for the significant stems so a future per-stem SPECTRUM VIZ has its data in the payload. Additive
        # — nothing draws it yet (the canvas draw is the next step, to be added with visual verification).
        spectrum = {st: masking["spectrum"][st] for st in stems
                    if (masking.get("spectrum") or {}).get(st)}
        centroid = {st: masking["spectral_centroid"][st] for st in stems
                    if (masking.get("spectral_centroid") or {}).get(st) is not None}
        stem_block = {"stems": stems, "bands": BAND_ORDER, "band_labels": BAND_LABEL,
                      "heat": heat, "bb": bb, "time_bins": masking["time_bins"],
                      "viz": viz, "empties": omitted, "omitted": omitted,
                      "colour_floor_db": STEM_COLOUR_FLOOR_DB,
                      "spectrum": spectrum, "spectrum_freqs": masking.get("spectrum_freqs"),
                      "centroid": centroid}
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
            if (loud_level(mid_band) or -120) < STEM_EMPTY_FLOOR_DB:
                continue
            label = f"Bass vs {mid} · {BAND_HZ.get(band, band)}"
            masking_cards.append((label, s["pct_masked"], s["mean_diff_db"], s["flagged_windows"], s["total_windows"]))
        for zone, flags in masking.get("masking_flags", {}).items():
            for f in flags:
                flag_times.append(f["time_s"])

    als_overlay = build_als_overlay(als, als_offset_s, dur)
    # CR-5a: cut scenes on the self-similarity boundaries when that segmentation is trustworthy
    # (≥3 segments, ≥2 labels — _selfsim_stable); else fall back to the coarse section bar.
    ss_bounds = None
    if _selfsim_stable(selfsim):
        ss_bounds = [s["t0"] for s in selfsim["segments"] if s.get("t0", 0) > 0]
    story = build_story(core, als_overlay, seg_bounds=ss_bounds)

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

    # ── ONE structure bar (0.6.1): collapse the two clashing rows into one. The named
    # scenes (Intro/Build/Drop, from arrangement boundaries) become the only bar; each
    # is COLOURED + LETTERED by the self-similarity recurrence cluster that dominates it
    # (max time-overlap). A returning motif therefore shares one letter+colour across,
    # e.g., intro & outro — a single A/B/C scheme instead of two. Lead instrument comes
    # from the same dominant cluster. Falls back to the scene's own family/intensity
    # letter (and no lead) when there's no self-similarity data.
    if story and story.get("scenes") and ss_segs:
        for sc in story["scenes"]:
            best, bestov = None, 0.0
            for seg in ss_segs:
                ov = min(sc["t1"], seg["t1"]) - max(sc["t0"], seg["t0"])
                if ov > bestov:
                    best, bestov = seg, ov
            if best is not None:
                sc["letter"] = best.get("letter", sc["letter"])
                if best.get("lead"):
                    sc["lead"] = best["lead"]

    # Tidy the structure bar AFTER the letter remap: merge adjacent same-letter scenes and close gaps
    # so one continuous part doesn't show as a row of slivers with holes (worst on rough tracks — e.g.
    # four consecutive 'D' slivers + a dropped sub-2s segment). Mode-independent; clean tracks unchanged.
    if story and story.get("scenes"):
        story["scenes"] = _coalesce_scenes(story["scenes"], dur)
        # Number the Drops NOW — after coalescing — so the count is gap-free (CR-5/G6). Numbering in
        # build_story (before merges) caused "Drop, Drop 3, Drop 5" when a middle drop was swallowed.
        drops = [sc for sc in story["scenes"] if sc.get("name") == "Drop"]
        if len(drops) > 1:
            for k, sc in enumerate(drops, 1):
                sc["name"] = "Drop" if k == 1 else f"Drop {k}"

    _leak = leakage_caveats(masking, rhythm)   # CR-4; also feeds (g) stem_character (exclude bled bands)
    _character = stem_character(masking, rhythm, _leak, per_stem_notes)  # computed once; reused by recs (G16) + payload
    # INV-STEMNAME-ALL (0.9.22): one display name per stem, resolved ONCE here, threaded into every surface.
    # Significant stems get their character label; near-silent (omitted) → IDENTIFIED label (INV-STEMNAME-NEARSILENT-ID,
    # s46): mapped .als track name OR frequency-band word + " (near-silent)". Never bare "near-silent".
    # Never raw Demucs family word. Distinct labels enforced. Missing stems → "a part".
    _analysed_for_display = masking.get("stems_analysed", []) if masking else []
    _omitted_for_display = set(
        st for st in _analysed_for_display
        if st not in significant_stems(masking)
    ) if masking else set()
    # Compute identified near-silent labels once, with distinctness guarantee.
    _nearsilent_labels = (_nearsilent_display_map(_omitted_for_display, masking, stemmap)
                          if _omitted_for_display else {})
    _display = {
        st: ((_character.get(st, {}) or {}).get("label") or
             (_nearsilent_labels.get(st) or "a part"))
        for st in _analysed_for_display
    }
    _fam_display = {
        "other": "everything else", "kick": "kick", "bass": "bass", "drums": "drums",
        "hats": "hats", "chord": "chords", "lead": "lead", "perc": "perc",
    }
    # Post-process arc structure bar lead labels: the no-.als path sets seg["lead"] to the raw stem name
    # (line ~2007); apply the display map now that _display is built. The .als path uses real track names
    # (not raw stem names), so they are safe — they won't appear as keys in _display.
    if _display and ss_segs:
        for _seg in ss_segs:
            if _seg.get("lead") and _seg["lead"] in _display:
                _seg["lead"] = _display[_seg["lead"]]
    if _display and story and story.get("scenes"):
        for _sc in story["scenes"]:
            if _sc.get("lead") and _sc["lead"] in _display:
                _sc["lead"] = _display[_sc["lead"]]
    _repetition = stem_repetition(per_stem_selfsim, masking)  # CR-6; reused by the (e) dev-vs-loop rec + payload
    recs = build_recommendations(core, detail, masking, S,
                                 als_overlay=als_overlay, stemmap=stemmap, rhythm=rhythm,
                                 character=_character, repetition=_repetition, selfsim=selfsim)
    # §B.11: per-stem "moves against the track" cards join the pool (Detailed-only — no timecode).
    # `core` feeds composite (stem-vs-track) cards; `levels` ranks a near-silent part below louder ones.
    recs += per_stem_cards(per_stem_core, core, character=_character,
                           levels=stem_prominence(masking))
    # Most important first: fix (crit) → actionable (do) → creative choice (concept).
    _rank = {"crit": 0, "do": 1, "concept": 2}
    recs.sort(key=lambda r: _rank.get(r[0], 3))   # tuple: (cls, when, head, body, fix, t, based, axis, ev)

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
        in_disk = [n for n in analysed if n in disk]
        # Lane / player order: real content on top, near-silent (omitted) stems sink to the BOTTOM
        # (s37) — an empty lane in the middle reads as a gap; grouped at the end it reads as
        # "these are the empty ones". Stable within each group; falls back to analysed order with no masking.
        if masking:
            sig = set(significant_stems(masking))
            in_disk = [n for n in in_disk if n in sig] + [n for n in in_disk if n not in sig]
        names = in_disk + [n for n in disk if n not in analysed]
        srcs = []
        for n in names:
            hit = next((f"{rel}/{n}{e}" for e in EXT_PREF if (adir / f"{n}{e}").exists()), None)
            if hit:
                srcs.append({"name": n, "src": hit})
        if srcs:
            player = {"srcs": srcs}
    # Quick runs have no Demucs stems, but they DO have the mix — give them a single-track player
    # (transport + seek, no per-stem mute/solo). The widget reads player.kind=="mix" and skips the
    # player lane grid. (2026-06-20: quick mode still gets a player.)
    if player is None and audio_mix_rel:
        rel = audio_mix_rel.rstrip("/")
        adir = Path(out_path).parent / rel
        EXT_PREF = (".m4a", ".mp3", ".ogg", ".opus", ".wav", ".flac")
        hit = next((f"{rel}/mix{e}" for e in EXT_PREF if (adir / f"mix{e}").exists()), None)
        if not hit:  # accept any single audio file in the dir as the mix
            files = sorted(p for p in adir.glob("*") if p.suffix.lower() in EXT_PREF)
            hit = f"{rel}/{files[0].name}" if files else None
        if hit:
            player = {"srcs": [{"name": "mix", "src": hit}], "kind": "mix"}

    # Displayed tempo: the .als project tempo is authoritative when present; audio-detection is the
    # fallback (it can lock onto a subharmonic). This also fills the vitals Tempo slot when the core
    # analysis left vitals.tempo_bpm empty.
    _disp_tempo, _tempo_src = display_tempo(core.get("tempo"), als.get("bpm") if als else None)
    payload = {
        "dur": dur, "tempo": _disp_tempo, "tempo_src": _tempo_src, "bins": tb,
        "sections": core.get("section_bounds_s", []),
        "arc": [{"key": k, "label": l, "col": c, "vals": v, "max": m} for k, l, c, v, m in arc_lanes],
        "vitals": {**core.get("vitals", {}), "tempo_bpm": _disp_tempo,
                   **({"time_sig": als.get("time_signature"),
                       "time_sig_changes": als.get("time_sig_changes", []),
                       "tempo_changes": als.get("tempo_changes", [])} if als else {})},
        "selfsim": (selfsim or {}).get("segments", []),
        "tonal_balance": core.get("tonal_balance", []),
        "stem": stem_block,
        "mcards": [{"label": z, "pct": p, "diff": d, "fw": fw, "tw": tw} for z, p, d, fw, tw in masking_cards],
        "flags": flag_times,
        "recs": [{"cls": c, "when": w, "h": h, "p": p, "fix": fx, "t": t, "based": b, "ev": e}
                 for c, w, h, p, fx, t, b, _ax, e in recs],
        "als": als_overlay,
        "stemmap": stemmap,
        "rhythm": rhythm,
        "leakage_caveats": _leak,                             # CR-4: bands that are likely a louder neighbour's bleed
        "stem_character": _character,  # (g)/G13: deterministic character label per significant stem (computed above)
        "stem_display": _display,    # INV-STEMNAME-ALL: one display name per stem (significant→label, near-silent→identified label + "(near-silent)", else→"a part")
        "fam_display": _fam_display, # INV-STEMNAME-ALL: producer label per family key (used in mapPanel family bars)
        "stem_repetition": _repetition,  # CR-6: per-significant-stem repetition (computed once above, reused by the (e) rec)
        "notes": notes,
        "drums": drums,
        "player": player,
        "presence_threshold": presence_threshold,
        "story": story,
        "mode": mode,
        "version": TC_VERSION,
        "analysis_version": TC_ANALYSIS_VERSION,  # INV-12 keys staleness off THIS, not the tool version
        "meta": meta or {},
        "verdict": _verdict_text(verdict, narrative_md),
        "catalog": catalog or None,
        "backHref": back_href or None,  # absolute file:// to the library index → the ← Library button
        "t": S["ui"],
    }
    # A track's name comes from the caller (track_analyzer derives it from the audio file).
    # NEVER invent a name from tempo/duration — those live in the vitals strip + subtitle and
    # read as a broken title here (2026-06-22: that's the BPM appearing where the track name belongs).
    title = title or "Untitled track"
    # Run-mode badge + (quick-only) explainer, rendered SERVER-SIDE from `mode` so it's deterministic
    # in the HTML (testable, no JS needed): quick = amber "Quick read" + a line on what full adds;
    # full = green "Full analysis". (2026-06-20: the badge must be visible on the page.)
    _ui = S.get("ui", {})
    _q = (mode == "quick")
    _badge_txt = _ui.get("mode_badge_quick", "Quick read") if _q else _ui.get("mode_badge_full", "Full analysis")
    badge_html = f'<span class="modebadge {"quick" if _q else "full"}" id="modeBadge">{_esc(_badge_txt)}</span>'
    quick_note = f'<p class="modenote" id="modeNote">{_esc(_ui.get("quick_explainer", ""))}</p>' if _q else ""
    note_html = quick_note + _completeness_line_html(run_dir, mode)  # RC-INV-12, both modes
    # Producer's read — rendered to HTML here (server-side) so it ships in the markup, not built by JS.
    read_body = _read_html(narrative_md)
    # SPEC §B.12 — lead the read with the computed "how it develops" observation. It's a standalone
    # observation, so it shows even when there's no authored narrative (a Demucs run with no read still
    # gets this one real line); a flat track with no narrative leaves both empty → the panel hides.
    read_body = _development_html(core) + read_body
    read_title = _esc(_ui.get("read_title", "")) if read_body else ""
    read_panel_style = " open" if read_body else ' style="display:none"'
    # View toggle: full gets the (JS-wired) Simple/Detailed control; quick gets a hint in its place,
    # and the toggle JS bails on quick so the body never enters Simple → evidence + recs stay visible.
    view_toggle = (f'<div class="viewhint" id="viewToggle">{_esc(_ui.get("quick_view_hint", ""))}</div>'
                   if _q else '<div class="viewtoggle seg" id="viewToggle"></div>')
    # §D.10.3 — reference read: Detailed-only; skipped for quick (no fingerprint) and when run_dir absent.
    ref_read_html = _ref_read_html(run_dir) if not _q else ""
    html = (TEMPLATE.replace("__TITLE__", _esc(title))
            .replace("__BODYCLASS__", "quick" if _q else "")
            .replace("__MODEBADGE__", badge_html)
            .replace("__MODENOTE__", note_html)
            .replace("__VIEWTOGGLE__", view_toggle)
            .replace("__READTITLE__", read_title)
            .replace("__READPANELSTYLE__", read_panel_style)
            .replace("__READBODY__", read_body)
            .replace("__REFREAD__", ref_read_html)
            .replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False)))
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"Widget saved: {out_path}  (Track Coach v{TC_VERSION})")
    print(f"  arc lanes: {len(arc_lanes)}  stems: {len((masking or {}).get('stems_analysed', []))}  recs: {len(recs)}")


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _completeness_line_html(run_dir, mode):
    """RC-INV-12: one run-level line — "Measured N of M signals; skipped: …" — so a widget with few
    cards isn't misread as all-clear. It reads the shared fingerprint manifest (RC-INV-8) over the
    axes the run's rung promises (fingerprints.PROMISED_BY_MODE), in the muted based-on register.
    Missing-by-mode axes aren't promised, so they never show as skipped (RC-INV-7)."""
    if not run_dir:
        return ""
    try:
        import fingerprints as FP
        import validity as V
        promised = FP.PROMISED_BY_MODE.get(mode, FP.PROMISED_BY_MODE["full"])
        present = V.present_axes(run_dir, mode)
        measured = FP.measured_axes(run_dir)
        m = len(promised)
        n = len(present & measured)
        absent = sorted(promised - present)  # signals genuinely not in this track (RC-INV-13b)
        reads = [FP.AXIS_READS.get(a, a.replace("_", " ")) for a in absent]
    except Exception:  # noqa: BLE001 — the disclosure line is best-effort, never blocks the render
        return ""
    if m <= 0:
        return ""
    tail = f"; absent in this track: {_esc(_join_and(reads))}" if reads else ""
    return (f'<p class="completeness" id="completeness">'
            f'<span class="complab">Measured</span> {n} of {m} signals{tail}.</p>')


def _verdict_text(verdict, narrative_md):
    """The 1–2 sentence headline for the calm/Simple view. Prefer an explicit
    --verdict; otherwise fall back to the first real sentence(s) of the Producer's
    read so the Simple view is never empty when a narrative exists."""
    if verdict and verdict.strip():
        return verdict.strip()
    if not narrative_md:
        return ""
    for blk in narrative_md.split("\n\n"):
        t = blk.strip()
        if not t or t.startswith("#"):
            continue
        t = " ".join(t.split())
        # first one or two sentences, capped so the calm view stays calm
        parts = re.split(r"(?<=[.!?])\s+", t)
        out = " ".join(parts[:2]).strip()
        return out[:320]
    return ""


def _read_html(narrative_md):
    """Render the Producer's read (a small markdown subset) to HTML **server-side**, so `#readBody`
    is a real, testable artifact in the shipped file — no client-side parsing. This MIRRORS the old
    JS mini-parser (headings → <h3>, **bold**, *italic*, '- '/'* ' bullets, soft-wrap collapse) and
    FIXES two things that JS got wrong on quick reads (B1, session 10):
      • it never handled a top-level '# ' heading → a quick narrative starting '# Title' rendered the
        literal '#' as muted body text;
      • a block whose first line was a heading but whose body followed on a SINGLE newline dumped the
        whole body inside the <h3>. Here a heading is ONLY its first line; the rest becomes a <p>.
    Well-formed reads (headings on their own blank-line-separated block) render byte-identically."""
    if not narrative_md:
        return ""

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def inline(s):
        s = esc(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        return s

    def para(s):                      # soft wraps → space; a real '  \n' hard break → <br>
        s = inline(s)
        s = re.sub(r" {2,}\n", "<br>", s)
        return s.replace("\n", " ")

    def block(t):
        t = t.strip()
        if not t:
            return ""
        first, _, rest = t.partition("\n")
        m = re.match(r"^(#{1,6})\s+(.*)$", first)
        if m:                          # ANY heading level → <h3>; trailing lines fold into a <p>
            return f"<h3>{inline(m.group(2).strip())}</h3>" + (block(rest) if rest.strip() else "")
        if re.match(r"^\s*[-*]\s+", t):
            items = []
            for ln in t.split("\n"):
                mm = re.match(r"^\s*[-*]\s+(.*)$", ln)
                if mm:
                    items.append(mm.group(1))
                elif items:
                    items[-1] += "\n" + ln
            return "<ul>" + "".join(f"<li>{para(it)}</li>" for it in items) + "</ul>"
        return f"<p>{para(t)}</p>"

    return "".join(block(b) for b in re.split(r"\n{2,}", narrative_md))


def _refread_bars_html(track_z, centroid_z, conf_entries=None, confirm_z=0.4):
    """Compute per-facet bar rows HTML for one direction centroid. Pure. Returns (rows_html, summary)
    or ('', '') when no shared measured axes exist (RC-INV-1).

    conf_entries: list of {axis, expect: high|low, tier: direct|indirect} for the current
    direction (from facet_confirmation.json). When provided, rows earn ★ (direct, confirmed)
    or ☆ (indirect, confirmed); contradicted/near-mean axes get no mark. confirm_z is the
    minimum |centroid_z| to count as confirmed (default 0.4 per D-INV-24)."""
    import fingerprints as FP

    offsets = []
    for axis in FP.AXES:
        tv = track_z.get(axis)
        cv = centroid_z.get(axis)
        if tv is None or cv is None:
            continue
        try:
            if math.isnan(float(tv)) or math.isnan(float(cv)):
                continue
        except (TypeError, ValueError):
            continue
        offsets.append((axis, float(tv) - float(cv)))

    if not offsets:
        return "", ""

    # Most-SIMILAR first (smallest |offset| at top) — the bars taper into a triangle: matched/green rows
    # lead and divergence grows downward (2026-07-02, reverses the old most-divergent-first order).
    offsets.sort(key=lambda t: abs(t[1]))

    # Summary: closest = the leading (smallest-|offset|) rows; furthest = the trailing (largest).
    n = len(offsets)
    n_ext = min(3, max(1, (n + 2) // 4))   # 1 for tiny, 2 for mid, 3 for full fingerprints
    closest_labels  = [_AXIS_LABELS.get(ax, ax) for ax, _ in offsets[:n_ext]]
    furthest_labels = [_AXIS_LABELS.get(ax, ax) for ax, _ in reversed(offsets[-n_ext:])]
    summary = (f"Closest on: {' · '.join(closest_labels)}"
               f" · Furthest on: {' · '.join(furthest_labels)}")

    # Build ★/☆ map from curated confirmation entries for this direction.
    # star_map[axis] → 'star' (★, direct) | 'half' (☆, indirect) | absent (no mark)
    star_map = {}
    if conf_entries:
        for entry in conf_entries:
            axis   = entry.get("axis")
            expect = entry.get("expect")
            tier   = entry.get("tier")
            if not axis or not expect or not tier:
                continue
            cz = float(centroid_z.get(axis, 0.0))
            agrees = (expect == "high" and cz >= confirm_z) or (expect == "low" and cz <= -confirm_z)
            if agrees:
                star_map[axis] = "star" if tier == "direct" else "half"
            # else: contradicted or near mean → no mark (D-INV-24)

    rows_html = []
    for axis, offset in offsets:
        label = _AXIS_LABELS.get(axis, axis)
        cat   = _AXIS_CATEGORY.get(axis, "")
        cat_color = _CAT_COLORS.get(cat, "#5b6472")

        pct       = min(abs(offset) / _REF_MAX_Z, 1.0) * _REF_MAX_PCT
        bar_left  = 50.0 if offset >= 0 else 50.0 - pct
        bar_width = pct
        bar_color = _bar_color(abs(offset))
        words     = _words(offset)

        # ★/☆ inside the label span (child spans so the outer text-only regex still captures the label)
        mark = star_map.get(axis)
        star_html = ""
        if mark == "star":
            star_html = '<span class="refread-star" title="Web-described trait, confirmed directly by measurement">★</span>'
        elif mark == "half":
            star_html = '<span class="refread-star refread-halfstar" title="Web-described trait, indirectly confirmed by measurement">☆</span>'

        char_chip_html = ('<span class="refread-chip" title="Character axis — assessed without loudness weighting">char</span>'
                          if axis in _CHAR_AXES else "")

        # data-confirmed keeps class="refread-row" intact so existing count tests aren't broken
        confirmed_attr = ' data-confirmed="1"' if mark else ""

        rows_html.append(
            f'<div class="refread-row"{confirmed_attr}>'
            f'<span class="refread-cat" style="background:{cat_color}">{_esc(cat)}</span>'
            f'<span class="refread-label">{_esc(label)}{star_html}{char_chip_html}</span>'
            f'<div class="refread-barwrap">'
            f'<div class="refread-center"></div>'
            f'<div class="refread-bar" style="left:{bar_left:.1f}%;width:{max(bar_width, 0.5):.1f}%;background:{bar_color}"></div>'
            f'</div>'
            f'<span class="refread-words">{_esc(words)}</span>'
            f'</div>'
        )
    return ''.join(rows_html), summary


def render_reference_notes(artist_entry):
    """§D.10.2 one-source shared renderer — emits semantic HTML for one artist entry.

    Approved layout (2026-07-04, variant A):
      1. Artist header (name + real name)
      2. Genre / era line
      3. Prose blurb (context first, before measurement verdicts)
      4. Note box (coverage-confidence callout, left-border)
      5. "YOUR MEASUREMENT BACKS THESE UP" — glyph-led rows for direct/indirect tiers
         Each row: <span class="rn-trait-glyph">★</span> phrase  (no trailing pill)
      6. "Web describes these — your tracks don't bear them out" — ONE muted group,
         web-only and not-measurable traits as a dot-separated inline run (not N pills)
      7. Sources list — visible <a href> links (2026-07-04 amendment: keep visible)
      8. Footnote legend (.rn-footnote) explaining ★/☆/·

    Tiers from reference_web_notes.json:
      direct         → ★ glyph in confirmed section
      indirect       → ☆ glyph in confirmed section
      web-only       → · dot in the muted web-only group
      not-measurable → · dot in the muted web-only group
      none (legacy)  → · dot in the muted web-only group

    Returns markup only; theme (dark / light) applied by CSS on tc-rn-* classes.
    Used by both the in-widget panel (dark theme) and the side-page generator (light theme).
    """
    artist    = artist_entry.get("artist", "")
    real_name = artist_entry.get("real_name", "")
    genre_era = artist_entry.get("genre_era", "")
    note      = artist_entry.get("note") or ""
    blurb     = artist_entry.get("blurb", "")
    traits    = artist_entry.get("traits", [])
    sources   = artist_entry.get("sources", [])

    # 1. Header: artist name + real name (muted)
    rn_html = (f' <span class="tc-rn-realname">({_esc(real_name)})</span>'
               if real_name else "")
    head_html = f'<div class="tc-rn-head"><span class="tc-rn-artist">{_esc(artist)}</span>{rn_html}</div>'

    # 2. Genre / era line
    genre_html = (f'<p class="tc-rn-genre">{_esc(genre_era)}</p>'
                  if genre_era else "")

    # 3. Prose blurb (FIRST — context before verdicts, variant A)
    blurb_html = f'<p class="tc-rn-blurb">{_esc(blurb)}</p>' if blurb else ""

    # 4. Note: album-variance callout (left-border)
    note_html = (f'<div class="tc-rn-note"><strong>Note:</strong> {_esc(note)}</div>'
                 if note else "")

    # 5 + 6. Trait sections — split into confirmed (★/☆) and web-only groups
    _TIER_RANK = {"direct": 0, "indirect": 1, "web-only": 2, "not-measurable": 3}
    confirmed_rows = []   # ★/☆ glyph-led rows
    webonly_phrases = []  # dot-separated muted group

    if traits:
        sorted_traits = sorted(traits, key=lambda t: _TIER_RANK.get(t.get("tier", "none"), 2))
        for t in sorted_traits:
            tier  = t.get("tier", "none")
            title = t.get("title") or t.get("phrase", "")
            if tier == "direct":
                confirmed_rows.append(
                    f'<li class="rn-trait-row">'
                    f'<span class="rn-trait-glyph">★</span>'
                    f'<span class="rn-trait-text">{_esc(title)}</span>'
                    f'</li>'
                )
            elif tier == "indirect":
                confirmed_rows.append(
                    f'<li class="rn-trait-row">'
                    f'<span class="rn-trait-glyph rn-trait-glyph-indirect">☆</span>'
                    f'<span class="rn-trait-text">{_esc(title)}</span>'
                    f'</li>'
                )
            else:   # web-only, not-measurable, none (legacy)
                webonly_phrases.append(_esc(title))

    confirmed_html = ""
    if confirmed_rows:
        confirmed_html = (
            '<p class="rn-section-label">Your measurement backs these up</p>'
            f'<ul class="rn-confirmed-list">{"".join(confirmed_rows)}</ul>'
        )

    webonly_html = ""
    if webonly_phrases:
        group_text = " · ".join(webonly_phrases)
        webonly_html = (
            '<p class="rn-section-label rn-webonly-label">'
            'Web describes these'
            '<span class="rn-webonly-qualifier"> — your tracks don\'t bear them out</span>'
            '</p>'
            f'<p class="rn-webonly-group">{group_text}</p>'
        )

    # 7. Sources list (visible at panel bottom — 2026-07-04 amendment)
    sources_html = ""
    if sources:
        # Conventional chain-link glyph (inline SVG, currentColor) — reads unmistakably as a link.
        # 2026-07-05: replaced the earlier ↗ arrow, which read as the wrong/ugly icon.
        link_ico = ('<svg class="tc-rn-link-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                    '<path d="M9 15l6-6"/><path d="M11 6l1-1a4 4 0 0 1 6 6l-1 1"/>'
                    '<path d="M13 18l-1 1a4 4 0 0 1-6-6l1-1"/></svg>')
        links = "".join(
            f'<li><a href="{_esc(s["url"])}" target="_blank">{link_ico}{_esc(s["label"])}</a></li>'
            for s in sources
        )
        sources_html = (
            '<p class="tc-rn-sources-label">Sources</p>'
            f'<ul class="tc-rn-sources">{links}</ul>'
        )

    # 8. Footnote legend (one line explaining ★/☆/·)
    footnote_html = (
        '<p class="rn-footnote">'
        '★ web-described, your measurement confirms it directly'
        ' · ☆ indirectly but soundly tied'
        ' · unmarked · = web-described, your measurement doesn\'t bear it out'
        '</p>'
    )

    return (head_html + genre_html + blurb_html + note_html
            + confirmed_html + webonly_html
            + sources_html + footnote_html)


def _web_body_html(direction_name, conf_entries, centroid_z, confirm_z=0.4, web_data=None):
    """§D.10.2 — one direction's web-notes BODY ('what the web says about <artist>').

    Since the D-INV-36 merge (s58) the `<details id="webPanel">` wrapper is built ONCE by
    `render_reference_read`, nested inside the merged `#refPanel` with one body per shown
    direction — the web notes follow the shared selector. This builds a per-direction body
    only; '' when the direction has no web content at all (§D.10.2 liveness — the web
    disclosure is then hidden while that direction is focused, never an empty-open box).

    Two rendering modes:

    Rich mode (web_data is a dict with keys artist / genre_era / blurb / traits):
      Genre/era line, prose blurb, and ALL traits sorted into three tiers:
      (1) ★ direct+confirmed, (2) ☆ indirect+confirmed,
      (3) 'web says · our tracks don't show it' (none-tier, contradicted, or axis unmeasured).
      Within each tier: stable sort by (axis, phrase).

    Simple mode (web_data is None, uses conf_entries list):
      Only confirmed (★/☆) traits — backward-compatible with facet_confirmation.json.
      '' when no facet earns a mark.
    """
    if web_data and isinstance(web_data, dict):
        # ── Rich mode (reference_web_notes.json source) ──────────────────────────────────
        # Body is built by the shared one-source renderer (also used by build_reference_notes.py).
        # Theme (dark here, light for the side page) is applied by CSS on tc-rn-* classes.
        blurb  = web_data.get("blurb", "")
        traits = web_data.get("traits", [])
        if not traits and not blurb:
            return ""                                   # no web content → body absent (§D.10.2)
        return render_reference_notes(web_data)

    # ── Simple mode (backward-compat: only confirmed ★/☆ traits from conf_entries) ─────────
    if not conf_entries or not centroid_z:
        return ""
    rows = []
    for entry in conf_entries:
        axis   = entry.get("axis")
        expect = entry.get("expect")
        tier   = entry.get("tier")
        phrase = entry.get("phrase", "")
        if not axis or not expect or not tier:
            continue
        cz = centroid_z.get(axis)
        if cz is None:
            continue
        try:
            cz = float(cz)
            if math.isnan(cz):
                continue
        except (TypeError, ValueError):
            continue
        agrees = (expect == "high" and cz >= confirm_z) or (expect == "low" and cz <= -confirm_z)
        if not agrees:
            continue
        glyph      = "★" if tier == "direct" else "☆"
        axis_label = _AXIS_LABELS.get(axis, axis)
        display_phrase = phrase if phrase else axis_label
        rows.append(
            f'<li class="web-facet-row">{_esc(display_phrase)} — {_esc(axis_label)} {glyph}</li>'
        )
    if not rows:
        return ""
    return (
        f'<p class="web-artist-hdr">{_esc(direction_name)}</p>'
        f'<ul class="web-facets">{"".join(rows)}</ul>'
        f'<p class="web-note">'
        f'★ web-described, confirmed by measurement · '
        f'☆ web-described, soundly tied to measurement'
        f'</p>'
    )


def _ref_stub_html(note):
    """D-INV-36e — the reference panel's NON-expandable empty-state stub. When there is nothing
    to compare (no close direction, or the run carries no comparison data), the plaque keeps its
    place and title but is a plain div — no arrow, nothing to open (2026-07-05: a
    silently absent panel read as a hole; a one-line expandable panel read as broken). Keeps the
    #refPanel id so Simple hides it (INV-18/22) and the D-INV-37 entry reader stays inert
    (no .refpanel inside)."""
    return (
        '<div class="tc-panel refstub" id="refPanel">'
        '<span class="refstub-title">You vs your closest match</span>'
        f'<span class="refstub-note">{_esc(note)}</span>'
        '</div>'
    )


def render_reference_read(track_raw_fp, directions, norm, confirmation=None, confirm_z=0.4,
                          web_notes=None):
    """§D.10.1 / §D.10.3 — pure-ish reference-read HTML block with up-to-3 direction tab selector.

    Takes a raw (un-normalised) fingerprint, the directions dict {name: centroid_z_fp},
    and the z-norm params {"mu":{}, "sd":{}}. Returns the complete #refPanel HTML;
    '' only when track_raw_fp or directions are absent (feature not in play). When
    directions exist but nothing qualifies — all FAR, or no shared measured axes —
    it returns the NON-expandable empty-state stub instead of vanishing (D-INV-36e:
    nothing honest to *show* per SPEC §D.10.1, but the absence itself is said aloud).
    No I/O; all data supplied by the caller. Detailed-only via CSS (body.simple #refRead).

    confirmation: optional dict {dir_name: [{axis, expect, tier}, …]} for bar ★/☆ marks.
    When supplied, rows earn ★ (direct, centroid agrees) or ☆ (indirect, centroid agrees);
    contradicted / near-mean axes get no mark. confirm_z is the minimum |centroid z| to confirm.

    web_notes: optional dict {dir_name: {artist, genre_era, blurb, traits:[…]}} from
    reference_web_notes.json. Drives the rich §D.10.2 web panel (blurb + sorted full trait list).
    When supplied and confirmation is None, direct/indirect traits are also extracted from
    web_notes to derive the bar ★/☆ marks (one-source principle, §D.10.2).

    When 1 direction qualifies: single header, no tab bar (monotonic ladder: 1 tab = no tabs).
    When 2–3 qualify: tab buttons (nearest-first, each coloured by its own level), default = nearest.
    JS switches panels client-side — ephemeral view state, no analysis recompute (D-INV-28).
    """
    # One-source principle: if web_notes supplied but no explicit confirmation, derive it.
    if web_notes and confirmation is None:
        confirmation = {}
        for dn, wd in web_notes.items():
            if isinstance(wd, dict):
                entries = [t for t in wd.get("traits", [])
                           if t.get("tier") in ("direct", "indirect")]
                if entries:
                    confirmation[dn] = entries
    import fingerprints as FP          # same scripts/ dir; lazy to avoid hard dep at import time
    import similarity_columns as SC

    if not track_raw_fp or not directions:
        return ""

    # Z-normalise the track using the same norm used to build the centroids
    track_z = FP.normalize_fingerprint(track_raw_fp, norm)

    # Up to 3 qualifying directions, nearest-first, CLOSE/MID only (§D.10.1)
    leans = SC.leans_toward_topk(track_z, directions)

    if not leans:
        # Empty state (D-INV-36e): directions defined, none clears the lean bar — the NON-expandable
        # stub plaque, no tabs, no nested disclosures. NEVER the §F siblings phrase "No similar
        # tracks" (D-INV-22 vocabulary — the pre-merge bug this branch shipped).
        return _ref_stub_html("no close direction yet — none of your reference artists "
                              "sits close to this track")

    # Build one content panel per qualifying direction. `shown` keeps the rendered leans with
    # CONTIGUOUS indices, so tabs / bars / web bodies can never disagree about which didx is
    # which direction (a skipped no-shared-axes direction used to leave a hole).
    shown = []                                             # [(lean, rows_html, summary), …]
    for lean in leans:
        centroid_z  = directions[lean.direction]
        conf_entries = (confirmation or {}).get(lean.direction, [])
        rows_html, summary = _refread_bars_html(track_z, centroid_z,
                                                conf_entries=conf_entries,
                                                confirm_z=confirm_z)
        if not rows_html:
            continue                                        # no shared measured axes — skip this direction
        shown.append((lean, rows_html, summary))

    if not shown:
        # All directions had no shared measured axes (degenerate) — still say so (D-INV-36e).
        return _ref_stub_html("can't compare yet — this run and your reference artists "
                              "share no measured facets")

    panels_html = []
    for i, (lean, rows_html, summary) in enumerate(shown):
        hidden = ' style="display:none"' if i > 0 else ""
        # Axis orientation label: "lower · them · higher" sits above the bars so the reader knows
        # which side of the center line means "I'm lower than the direction" vs "higher". Matches the
        # visual: bars grow right (above the direction) or left (below). One label, above all rows.
        axis_lbl = (
            '<div class="refread-axis">'
            '<span>lower</span>'
            '<span>· them ·</span>'
            '<span>higher</span>'
            '</div>'
        )
        panels_html.append(
            f'<div class="refpanel" data-didx="{i}"{hidden}>'
            f'<p class="refread-hdr">Leans toward'
            f' <strong style="color:var(--wob)">{_esc(lean.direction)}</strong></p>'
            f'<p class="refread-summary">{_esc(summary)}</p>'
            f'{axis_lbl}'
            f'<div class="refread-bars">{rows_html}</div>'
            f'</div>'
        )

    # Tab buttons: only rendered when ≥2 panels (1 qualifying direction → no tab bar).
    # Since the D-INV-36 merge the tabs are the ONE shared selector at the top of #refPanel,
    # driving BOTH nested disclosures (bars + web notes).
    # Chips are neutral — no level colour. Nearest-first order carries the rank.
    # Only the active chip is distinguished (via .reftab.active CSS — accent border, full opacity).
    tabs_html = ""
    if len(shown) > 1:
        btns = ""
        for i, (lean, _, _) in enumerate(shown):
            active = ' class="reftab active"' if i == 0 else ' class="reftab"'
            btns += (f'<button{active} data-didx="{i}">'
                     f'{_esc(lean.direction)}</button>')
        tabs_html = f'<div class="reftabs seg">{btns}</div>'

    # Legend — explains ★/☆ and the char chip. Always shown when the block renders.
    legend_html = (
        '<div class="refread-legend">'
        '<span><b>★</b> The web describes this as the artist\'s signature — and our measurement of their tracks confirms it directly.</span>'
        '<span><b>☆</b> The web describes it — our measurement confirms it indirectly but soundly.</span>'
        '<span>(no mark) A normal facet — not a web-described signature.</span>'
        '<span><span class="refread-chip">char</span> Character axis — assessed without loudness weighting (a quiet pad equals a loud kick).</span>'
        '</div>'
    )

    # First nested disclosure — the centroid read (§D.10.3), open by default.
    refread_div = (
        '<details class="tc-panel" id="refRead" open>'
        '<summary>What the numbers show</summary>'
        + ''.join(panels_html)
        + legend_html
        + '</details>'
    )

    # §D.10.2 / D-INV-36c — web bodies for EVERY shown direction (not only the nearest), so the
    # web notes can follow the shared selector client-side. A direction with no web content gets
    # no body — the whole disclosure hides while that direction is focused (D-INV-36d).
    web_divs = []
    web_artist_by_idx = {}
    for i, (lean, _, _) in enumerate(shown):
        conf_e = (confirmation or {}).get(lean.direction, [])
        wd = (web_notes or {}).get(lean.direction) if web_notes else None
        body = _web_body_html(lean.direction, conf_e, directions[lean.direction], confirm_z,
                              web_data=wd)
        if not body:
            continue
        artist = wd.get("artist", lean.direction) if isinstance(wd, dict) else lean.direction
        web_artist_by_idx[i] = artist
        hidden = ' style="display:none"' if i > 0 else ""
        web_divs.append(
            f'<div class="webdir web-panel-body" data-didx="{i}"'
            f' data-artist="{_esc(artist)}"{hidden}>{body}</div>'
        )

    # Second nested disclosure — the web notes, open by default; absent entirely when NO shown
    # direction has web content (§D.10.2 liveness). Hidden initially if the DEFAULT (nearest)
    # direction has no body — the selector JS re-shows it on a direction that does.
    web_panel = ""
    if web_divs:
        wp_style = "" if 0 in web_artist_by_idx else ' style="display:none"'
        first_artist = web_artist_by_idx.get(0, next(iter(web_artist_by_idx.values())))
        web_panel = (
            f'<details class="tc-panel" id="webPanel" open{wp_style}>'
            f'<summary>What the web says about'
            f' <span id="webPanelArtist">{_esc(first_artist)}</span></summary>'
            + ''.join(web_divs)
            + '</details>'
        )

    # Inline selector JS (ephemeral view state, D-INV-28 — never persists across reload).
    # One selector drives BOTH disclosures (D-INV-36b): bars, web body, web summary artist,
    # and the web disclosure's own visibility (D-INV-36d).
    tab_js = ""
    if len(shown) > 1:
        tab_js = (
            '<script>(function(){'
            'var rp=document.getElementById("refPanel");if(!rp)return;'
            'var btns=rp.querySelectorAll(".reftab");'
            'var panels=rp.querySelectorAll(".refpanel");'
            'var webs=rp.querySelectorAll(".webdir");'
            'var wp=document.getElementById("webPanel");'
            'var wa=document.getElementById("webPanelArtist");'
            'btns.forEach(function(b){'
            'b.addEventListener("click",function(){'
            'var idx=b.dataset.didx;'
            'btns.forEach(function(x){x.classList.toggle("active",x.dataset.didx===idx);});'
            'panels.forEach(function(p){p.style.display=p.dataset.didx===idx?"":"none";});'
            'var found=null;'
            'webs.forEach(function(w){var on=w.dataset.didx===idx;'
            'w.style.display=on?"":"none";if(on)found=w;});'
            'if(wp){if(found){wp.style.display="";'
            'if(wa)wa.textContent=found.dataset.artist||"";}'
            'else{wp.style.display="none";}}'
            '});});'
            '})()</script>'
        )

    # D-INV-37 — the one-shot URL entry reader (catalog direction-link hand-off, s59).
    # Reads ?direction= ONCE on load: focuses the named tab through the CLICK PATH
    # (D-INV-36b — bars, web body, summary all follow) and scrolls the panel into view;
    # an unknown name falls back to the nearest (default) and still scrolls. Emitted with
    # the panel REGARDLESS of tab count (a single-direction entry still scrolls); sits
    # AFTER tab_js so the click listeners are already attached. Never writes the URL or
    # the view store — the Detailed entry rides the link's #detailed hash (§B.15).
    # The .refpanel guard keeps the empty state ("no close direction yet") param-inert.
    entry_js = (
        '<script>(function(){var go=function(){try{'
        'var m=/[?&]direction=([^&#]+)/.exec(location.search||"");'
        'if(!m)return;'
        'var rp=document.getElementById("refPanel");if(!rp)return;'
        'if(!rp.querySelector(".refpanel"))return;'
        'var want=decodeURIComponent(m[1]);'
        'var btns=rp.querySelectorAll(".reftab");'
        'for(var i=0;i<btns.length;i++){'
        'if(btns[i].textContent.trim()===want){btns[i].click();break;}}'
        'rp.open=true;'
        'rp.scrollIntoView({block:"start"});'
        '}catch(e){}};'
        'if(document.readyState==="loading")'
        'document.addEventListener("DOMContentLoaded",go);else go();'
        '})()</script>'
    )

    # The ONE merged reference panel (D-INV-36a): title → shared selector → centroid read →
    # web notes, both nested disclosures open by default (like the Evidence sub-panels).
    return (
        '<details class="tc-panel" id="refPanel" open>'
        '<summary>You vs your closest match</summary>'
        + tabs_html
        + refread_div
        + web_panel
        + tab_js
        + entry_js
        + '</details>'
    )


def _ref_read_html(run_dir):
    """§D.10.3 — load fingerprint from disk + reference_directions.json + reference_web_notes.json,
    delegate to render_reference_read. Returns '' when the reference feature isn't set up
    (no run_dir / no directions file / I/O fails); when directions ARE defined but the run has
    no fingerprint, returns the D-INV-36e stub so the panel's absence never reads as a hole.

    Loads reference_web_notes.json as the one-source file (§D.10.2): it drives both the rich
    web panel and the bar ★/☆ marks (confirmation derived from its direct/indirect traits).
    Falls back to facet_confirmation.json for bar ★/☆ if reference_web_notes.json is absent.
    """
    import fingerprints as FP

    if not run_dir:
        return ""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    ref_path  = data_dir / "reference_directions.json"
    if not ref_path.exists():
        return ""
    try:
        ref_data = json.loads(ref_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    norm       = ref_data.get("_norm", {})
    directions = {k: v for k, v in ref_data.items() if k != "_norm"}
    if not directions:
        return ""
    raw_fp = FP.fingerprint_from_run_dir(run_dir)
    if raw_fp is None:
        # Directions ARE defined but this run carries no fingerprint (an old or partial full
        # run) — say so in the panel's place instead of vanishing (D-INV-36e stub).
        return _ref_stub_html("no comparison data in this run — re-run the analysis "
                              "to compare with your reference artists")

    # Primary source: reference_web_notes.json (supersedes facet_confirmation.json)
    web_notes = {}
    confirm_z = 0.4
    notes_path = data_dir / "reference_web_notes.json"
    if notes_path.exists():
        try:
            notes_data = json.loads(notes_path.read_text(encoding="utf-8"))
            confirm_z  = float(notes_data.get("_confirm_z", 0.4))
            web_notes  = {k: v for k, v in notes_data.items() if not k.startswith("_")}
        except Exception:
            pass

    # Fallback: facet_confirmation.json for bar ★/☆ only (no rich panel)
    confirmation = None
    if not web_notes:
        conf_path = data_dir / "facet_confirmation.json"
        if conf_path.exists():
            try:
                conf_data    = json.loads(conf_path.read_text(encoding="utf-8"))
                confirm_z    = float(conf_data.get("_confirm_z", 0.4))
                confirmation = {k: v for k, v in conf_data.items() if not k.startswith("_")}
            except Exception:
                pass

    return render_reference_read(raw_fp, directions, norm,
                                 confirmation=confirmation,
                                 confirm_z=confirm_z,
                                 web_notes=web_notes if web_notes else None)


TEMPLATE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Track Coach · __TITLE__</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230c0e14'/><rect x='6' y='14' width='4' height='12' rx='1.6' fill='%23a78bfa'/><rect x='13' y='7' width='4' height='19' rx='1.6' fill='%234cc9f0'/><rect x='20' y='11' width='4' height='15' rx='1.6' fill='%23ffd166'/></svg>">
<style>
:root{--bg:#0c0e14;--panel:#141822;--panel2:#1b2030;--ink:#e8ecf5;--ink-dim:#aeb6c8;--muted:#8b94a8;
 --line:#262c3c;--good:#46d39a;--warn:#ffb454;--bad:#ff6b6b;--bright:#ffd166;--wob:#a78bfa;--accent:var(--wob);
 --radius:10px;--radius-lg:14px;--radius-xl:18px;--radius-pill:20px;
 --dur-fast:120ms;--dur-base:180ms;--ease:ease-out;
 /* DS-INV-9 minimal slice (s57, the design-system values): --gap WITHIN a group,
    --rhythm BETWEEN top-level sections — so inter-panel > intra-panel (fixes the 24<30 inversion) */
 --gap:16px;--rhythm:28px}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#161b2b,var(--bg) 60%);
 color:var(--ink);font:14px/1.5 -apple-system,"SF Pro Display",Inter,Segoe UI,sans-serif;padding:28px}
.wrap{max-width:1120px;margin:0 auto}
.brandkick{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--wob);font-weight:700;margin:0 0 3px}
/* Run-mode badge: a pill next to the brand so it's obvious whether this is a full or quick read
   (2026-06-20: the badge must be visible both on the page and in the catalog). Quick = amber, full = green. */
.modebadge{display:inline-block;margin-left:6px;padding:1px 8px;border-radius:20px;font-size:9.5px;
 font-weight:700;letter-spacing:.06em;vertical-align:middle}
.modebadge[hidden]{display:none}
.modebadge.full{background:rgba(70,211,154,.16);color:var(--good)}
.modebadge.quick{background:rgba(255,209,102,.16);color:var(--bright)}
.modenote{color:var(--muted);font-size:12px;margin:-12px 0 20px;max-width:760px;line-height:1.5}
.modenote[hidden]{display:none}
.completeness{color:var(--muted);font-size:12px;margin:-8px 0 20px;max-width:760px;line-height:1.5}
.complab{display:inline-block;font-size:9.5px;font-weight:700;letter-spacing:.5px;color:#7c8398;margin-right:6px;text-transform:uppercase}
.backlink{display:inline-block;margin:0 0 8px;padding:4px 11px;border:1px solid var(--line);border-radius:20px;
 color:var(--muted);text-decoration:none;font-size:12px;font-weight:600}
.backlink:hover{color:var(--ink);border-color:var(--wob)}
.backlink[hidden]{display:none}
h1{font-size:20px;margin:0 0 2px;font-weight:700}
.sub{color:var(--muted);font-size:13px;margin-bottom:4px}
.topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
/* srcmeta — what file was analysed & when. Lives just under the title (and in footer). */
.srcmeta{color:var(--muted);font-size:12px;margin:2px 0 20px;display:flex;flex-wrap:wrap;gap:4px 16px}
/* INV-30: a long unbroken filename ellipsis-truncates instead of blowing the line out; the full
   value stays on hover (the title attr set in JS). Each bit still flex-wraps at the row level. */
.srcmeta b{color:var(--ink);font-weight:600;max-width:min(46ch,100%);overflow:hidden;
 text-overflow:ellipsis;white-space:nowrap;display:inline-block;vertical-align:bottom}
.srcmeta:empty{display:none}
/* ── segmented control (DS-INV-13): ONE component for the Simple⇄Detailed view-toggle
   AND the reference-direction tabs (#refRead .reftabs). Selected = bold --wob fill
   (was: the view-toggle's subtle panel2 fill / the reftabs' border-opacity). Both
   containers wear `.seg`; their buttons are direct children; the selected marker is
   `.on` (view-toggle) or `.active` (reftabs). */
.seg{display:inline-flex;background:var(--panel);border:1px solid var(--line);
 border-radius:var(--radius);overflow:hidden;flex:0 0 auto}
.seg>button{appearance:none;border:0;background:transparent;color:var(--muted);
 font:600 12.5px/1 inherit;padding:9px 14px;cursor:pointer;white-space:nowrap;
 transition:color var(--dur-fast) var(--ease),background var(--dur-fast) var(--ease)}
.seg>button:not(.on):not(.active):hover{color:var(--ink)}
/* selected = calm: the old subtle panel2 lift, SAME weight, no contrast inversion
   (2026-07-02: the bold --wob fill read too loud and the invert/bold jarred). */
.seg>button.on,.seg>button.active{background:var(--panel2);color:var(--ink);box-shadow:0 1px 0 rgba(0,0,0,.3)}
/* quick reads have no Simple/Detailed view (no stems to reveal) — a hint sits where the toggle was */
.viewhint{color:var(--muted);font-size:12px;max-width:300px;line-height:1.4;align-self:center;text-align:right}
/* (the calm verdict headline panel was removed 2026-07-03, s49) */
/* SIMPLE VIEW — Simple no longer strips substance. The PLAYER, the Producer's read, the EVIDENCE
   drawer, and the timecoded recs all stay visible in BOTH views (hiding them just read as "things
   vanished"). The Evidence drawer is ALWAYS shown now (2026-06-20, INV-18) — it used to be
   Simple-hidden, which meant full-Simple uniquely buried it while quick + full-Detailed showed it.
   Detailed adds only the DEEP stem layer on top: the #stemlanes canvas + its #seqKey. */
/* Demux / per-stem visualisation (#stemlanes + its #seqKey) shows in DETAILED ONLY —
   confirmed 2026-06-20 (the demux stems are shown only in the detailed view).
   The transport (play/seek/time) stays usable in BOTH views; only the stem-lane canvas + key hide. */
body.simple #stemlanes,body.simple #seqKey{display:none!important}
/* The merged reference panel (§D.10.1/D-INV-36): ONE container #refPanel — shared selector +
   nested centroid read (#refRead) + nested web notes (#webPanel) — Detailed-only as a unit. */
body.simple #refPanel{display:none!important}
/* reference-direction tabs: the same `.seg` segmented bar (container styling comes from
   `.seg`; the buttons from `.seg>button`); only spacing below is bespoke here. */
#refPanel .reftabs{margin-bottom:14px}
#refRead .refread-hdr{font-size:14.5px;font-weight:600;margin:0 0 8px}
#refRead .refread-summary{color:var(--muted);font-size:12.5px;margin:0 0 16px}
#refRead .refread-bars{display:flex;flex-direction:column;gap:7px}
/* Axis orientation label above the bars — "lower · them · higher". Mirrors the bar geometry:
   left of center = lower than your closest match, right = higher. One row, muted text. */
#refRead .refread-axis{display:flex;justify-content:space-between;padding:0 0 4px;
 font-size:10px;color:var(--muted);margin-left:calc(64px + 155px + 16px);margin-right:calc(110px + 8px)}
/* Row = [cat-chip][label + ★][bar][words]. class stays plain "refread-row" — data-confirmed for tinting */
#refRead .refread-row{display:flex;align-items:center;gap:8px;border-radius:4px;padding:1px 2px}
#refRead .refread-row[data-confirmed]{background:rgba(255,177,63,.05)}
#refRead .refread-row[data-confirmed] .refread-label{color:var(--ink)}
#refRead .refread-cat{display:inline-block;width:64px;flex:0 0 64px;font-size:9.5px;color:#fff;
 text-align:center;border-radius:4px;padding:1.5px 0;font-weight:600;letter-spacing:.02em}
#refRead .refread-label{flex:0 0 155px;font-size:12.5px;color:var(--muted);text-align:right;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#refRead .refread-label .refread-star{font-size:11px;margin-left:3px;color:var(--warn)}
#refRead .refread-label .refread-halfstar{color:var(--ink-dim)}
#refRead .refread-label .refread-chip{font-size:8.5px;background:rgba(111,223,184,.12);
 color:var(--good);padding:0 4px;border-radius:5px;margin-left:3px;cursor:help;
 font-weight:500;vertical-align:1px}
#refRead .refread-barwrap{flex:1;position:relative;height:12px;background:var(--panel2);border-radius:var(--radius);overflow:hidden}
#refRead .refread-center{position:absolute;left:50%;top:0;width:2px;height:100%;background:var(--muted)}
#refRead .refread-bar{position:absolute;top:1px;height:10px;border-radius:4px;min-width:2px}
#refRead .refread-words{flex:0 0 110px;font-size:11.5px;color:var(--muted);padding-left:4px}
#refRead .refread-legend{margin-top:16px;border-top:1px solid var(--line);padding-top:12px;
 display:flex;flex-direction:column;gap:5px;font-size:11.5px;color:var(--muted)}
#refRead .refread-legend b{color:var(--ink)}
#refRead .refread-legend .refread-chip{font-size:8.5px;background:rgba(111,223,184,.12);
 color:var(--good);padding:0 4px;border-radius:5px;font-weight:500;cursor:help}
/* Web-info plaque (§D.10.2, "What the web says") — since the D-INV-36 merge a NESTED-OPEN
   disclosure inside #refPanel, after #refRead; hidden with the container in Simple. */
/* #webPanel vertical spacing now governed by --rhythm (base .tc-panel margin-bottom); the old
   per-id 10px top override zeroed the bottom and helped invert the gap hierarchy — removed (s57). */
#webPanel .web-panel-body{padding:4px 0 4px}
#webPanel .web-artist-hdr{font-size:12.5px;font-weight:600;margin:0 0 4px;color:var(--ink)}
#webPanel .web-genre-era{font-size:11.5px;color:var(--muted);margin:0 0 6px;font-style:italic}
#webPanel .web-blurb{font-size:12.5px;color:var(--ink);margin:0 0 10px;line-height:1.55}
#webPanel .web-facets{margin:0 0 10px;padding:0 0 0 16px;display:flex;flex-direction:column;gap:5px}
#webPanel .web-facet-row{font-size:12.5px;color:var(--muted);list-style:none}
#webPanel .web-facet-nosay{opacity:.75}
#webPanel .web-nosay{display:inline-block;font-size:9px;font-weight:700;text-transform:uppercase;
 padding:1px 5px;border-radius:10px;background:rgba(139,148,168,.12);color:var(--muted);
 letter-spacing:.04em;vertical-align:middle;margin-left:3px}
#webPanel .web-note{font-size:11px;color:var(--muted);opacity:.65;margin:6px 0 0;font-style:italic}
/* Rich web panel (§D.10.2) — tc-rn-* semantic markup, dark theme (in-widget). */
/* Approved readable layout (2026-07-04, variant A): blurb first, glyph-led confirmed  */
/* rows, one muted web-only group, visible sources, one footnote legend. No per-row pills.        */
/* Light theme for the same classes lives in build_reference_notes.py (side page).                */
#webPanel .tc-rn-head{margin:0 0 3px}
/* s57 (2026-07-05): fonts snapped UP to the widget's whole-number scale (was scattered
   10/10.5/11.5/12.5 — the audit's "fractional" set); section headings lifted --muted→--ink so a heading is
   never dimmer than its own body (brightness hierarchy); sources given a chain-link icon + underline. */
#webPanel .tc-rn-artist{font-size:13px;font-weight:700;color:var(--ink)}
#webPanel .tc-rn-realname{font-size:12px;color:var(--muted);margin-left:5px;font-style:italic}
#webPanel .tc-rn-genre{font-size:12px;color:var(--muted);margin:2px 0 10px;font-style:italic}
#webPanel .tc-rn-note{border-left:3px solid var(--warn);padding:6px 10px;margin:0 0 10px;
 font-size:12px;color:var(--muted);line-height:1.5;background:rgba(255,180,84,.07);
 border-radius:0 6px 6px 0}
#webPanel .tc-rn-blurb{font-size:13px;color:var(--ink);margin:0 0 12px;line-height:1.6}
/* Section labels (variant A) — --ink so the heading is never dimmer than the body it heads (s57) */
#webPanel .rn-section-label{font-size:11px;font-weight:700;text-transform:uppercase;
 letter-spacing:.07em;color:var(--ink);margin:10px 0 6px}
#webPanel .rn-webonly-label{margin-top:14px}
#webPanel .rn-webonly-qualifier{font-weight:400;text-transform:none;letter-spacing:0;opacity:.75}
/* Glyph-led confirmed trait rows (variant A) — no trailing pill */
#webPanel .rn-confirmed-list{list-style:none;margin:0 0 4px;padding:0;
 display:flex;flex-direction:column;gap:6px}
#webPanel .rn-trait-row{display:flex;gap:8px;align-items:baseline;font-size:13px;color:var(--ink);line-height:1.5}
#webPanel .rn-trait-glyph{flex:0 0 14px;text-align:center;color:var(--good);font-size:13px}
#webPanel .rn-trait-glyph.rn-trait-glyph-indirect{opacity:.8}
#webPanel .rn-trait-text{flex:1;line-height:1.4}
/* Muted web-only group — ONE dot-separated inline line (not N pills) */
#webPanel .rn-webonly-group{font-size:12px;color:var(--muted);line-height:1.6;margin:0 0 12px;opacity:.85}
/* Footnote legend */
#webPanel .rn-footnote{font-size:11px;color:var(--muted);opacity:.72;margin:12px 0 0;
 font-style:italic;line-height:1.5}
/* Sources — read as links: chain-link icon + underline (s57; ↗ arrow retired 2026-07-05). Label --ink. */
#webPanel .tc-rn-sources-label{font-size:11px;font-weight:700;text-transform:uppercase;
 letter-spacing:.07em;color:var(--ink);margin:10px 0 5px}
#webPanel .tc-rn-sources{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
#webPanel .tc-rn-sources a{font-size:12px;color:var(--ink-dim);text-decoration:underline;
 text-underline-offset:2px;text-decoration-color:var(--muted)}
#webPanel .tc-rn-sources a .tc-rn-link-ico{width:11px;height:11px;color:var(--wob);vertical-align:-1px;margin-right:5px}
#webPanel .tc-rn-sources a:hover{color:var(--ink);text-decoration-color:var(--ink)}
/* Recommendation cards now sit directly under the graph (the cards the timeline triangles
   point to). Simple shows ONLY the timecoded recs — the ones with a triangle on the graph;
   Detailed shows all (global/whole-track recs included). The 2-vs-5 split is per-track: it's
   just however many recs are timecoded. (2026-06-19.) */
body.simple #recs .rec:not([data-t]){display:none!important}
/* Quick is the view-ladder FLOOR (2026-06-20): it shows the SAME brief recs as the calm view —
   the timecoded ones — so quick ⊆ Simple ⊆ Detailed holds. Quick has no toggle, so it gets its own
   body.quick gate (it never enters .simple). Evidence stays visible (INV-18); only the recs are brief. */
body.quick #recs .rec:not([data-t]){display:none!important}
/* VITALS strip — one scannable row of measured spec numbers. */
.vitals{display:flex;flex-wrap:wrap;gap:0;background:var(--panel);border:1px solid var(--line);
 border-radius:14px;padding:4px 6px;margin-bottom:22px;align-items:stretch}
.vitals .vit{display:flex;flex-direction:column;gap:2px;padding:9px 18px;position:relative;flex:1 0 auto}
.vitals .vit+.vit::before{content:"";position:absolute;left:0;top:18%;height:64%;width:1px;background:var(--line)}
.vitals .vlabel{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.7px}
.vitals .vval{font-size:16px;font-weight:600;color:var(--ink);white-space:nowrap}
.vitals .vval small{font-size:11px;color:var(--muted);font-weight:500;margin-left:3px}
.vitals .vval.warn{color:var(--warn)}.vitals .vval.bad{color:var(--bad)}.vitals .vval.good{color:var(--good)}
.vitals .vit[title]{cursor:help}
@media(max-width:760px){.vitals .vit{flex:1 0 33%}.vitals .vit:nth-child(3n+1)::before{display:none}}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.card .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.7px}
.card .v{font-size:16px;font-weight:600;margin-top:6px}
.card .v.good{color:var(--good)}.card .v.warn{color:var(--warn)}.card .v.bad{color:var(--bad)}
.card .cs{font-size:11px;color:var(--muted);margin-top:4px}
.card .ic{color:var(--muted);font-size:10px;opacity:.7}
.card[title]{cursor:help}
.cardhdr{grid-column:1/-1;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.8px;font-weight:700;margin:6px 2px 0}
.cardhdrhint{display:block;text-transform:none;letter-spacing:0;font-weight:400;font-size:11.5px;color:var(--muted);opacity:.85;margin-top:3px}
.read{border-left:3px solid var(--wob)}
/* Producer's read — built for SCANNING, not a wall: calm muted body so emphasis
   (white bold) and section heads (yellow) carry the hierarchy; generous spacing;
   section dividers; real bullet list. Full width (no reading cap — line length
   was never the problem; structure + colour hierarchy is). */
.read #readBody{font-size:14.5px;line-height:1.8;color:var(--ink-dim)}
.read #readBody p{margin:0 0 16px}
/* §B.12 "how it develops" — a quiet computed lead-line, set apart from the authored prose. */
.read #readBody p.readdev{margin:0 0 20px;padding:10px 14px;background:rgba(124,107,255,.07);
 border-left:2px solid var(--accent);border-radius:0 6px 6px 0;color:var(--ink-dim);font-size:14px}
.read #readBody p.readdev .devlab{display:inline-block;margin-right:8px;font-size:10.5px;font-weight:700;
 letter-spacing:.06em;text-transform:uppercase;color:var(--accent)}
.read #readBody strong{color:#fff;font-weight:600}
.read #readBody em{color:var(--ink);font-style:italic}
.read #readBody h3{font-size:15.5px;color:var(--bright);margin:30px 0 12px;font-weight:700;
 letter-spacing:.01em;padding-top:16px;border-top:1px solid var(--line)}
.read #readBody h3:first-child{margin-top:2px;padding-top:0;border-top:0}
.read #readBody ul{margin:0 0 16px;padding:0;list-style:none}
.read #readBody li{position:relative;margin:0 0 12px;padding:0 0 0 22px}
.read #readBody li:last-child{margin-bottom:0}
.read #readBody li:before{content:"";position:absolute;left:3px;top:8px;width:6px;height:6px;
 border-radius:50%;background:var(--wob)}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;margin-top:8px;font-weight:600}
.tag.good{background:rgba(70,211,154,.14);color:var(--good)}
.tag.warn{background:rgba(255,180,84,.14);color:var(--warn)}
.tag.bad{background:rgba(255,107,107,.14);color:var(--bad)}
/* ── tc-panel: ONE canonical collapsible panel — the single look for every section ────── */
details.tc-panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;
 padding:14px 20px 18px;margin-bottom:var(--rhythm)}  /* between top-level sections (DS-INV-9) */
details.tc-panel>summary{cursor:pointer;list-style:none;user-select:none;
 color:var(--ink);font-size:15px;font-weight:600;padding:4px 0 10px}
details.tc-panel>summary::-webkit-details-marker{display:none}
details.tc-panel>summary::before{content:"▸ ";color:var(--wob)}
details.tc-panel[open]>summary::before{content:"▾ "}
/* collapsed: symmetric padding so the title sits VERTICALLY CENTRED, not top-heavy
   (2026-07-02). Open keeps the larger bottom padding for the content below. */
details.tc-panel:not([open]){padding-bottom:14px}
details.tc-panel:not([open])>summary{padding-bottom:4px}
/* D-INV-36e — the reference panel's empty-state stub: the same plaque look as a COLLAPSED
   tc-panel, but a plain div — no arrow, no pointer, nothing to open. */
div.tc-panel.refstub{background:var(--panel);border:1px solid var(--line);border-radius:18px;
 padding:18px 20px;margin-bottom:var(--rhythm)}
.refstub-title{color:var(--ink);font-size:15px;font-weight:600}
.refstub-note{color:var(--muted);font-size:13px;margin-left:10px}
.hint{color:var(--muted);font-size:12px;margin:0 0 16px}
.legend{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:10px;font-size:12px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px}
canvas{width:100%;display:block;border-radius:10px;cursor:crosshair}
.readout{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px;font-size:12.5px;color:var(--muted);
 background:var(--panel2);border-radius:10px;padding:10px 14px;min-height:20px}
.readout b{color:var(--ink);font-weight:600}
.mgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.mcard{background:var(--panel2);border:1px solid var(--line);border-radius:var(--radius-lg);padding:12px 14px}
.mcard .z{font-size:12px;color:var(--muted)}.mcard .pct{font-size:20px;font-weight:600;margin-top:3px}
/* Container-relative reflow (s34): the old `1fr 1fr` + `@media(max-width:760px)`
   collapsed to ONE column by VIEWPORT width — on a ~2/3-screen window
   (or a browser zoom) the viewport fell under 760px and every rec stacked in one
   crooked column. `auto-fit` sizes the column count from the GRID's OWN width
   (i.e. the #recsPanel it sits in), never the raw window: 1 column when narrow,
   2 on a ~2/3 window, 3 when there's room. Wider vertical gap so the plates
   breathe. Regression-tested in a real browser: tests/test_headless_render.py. */
/* recs grid: reflow by the panel's OWN width, capped at 2 columns (never 3 —
   a rec card wants a readable line length). max(300px, half-minus-gap) forces at most two
   columns and drops to one when cramped; no media/container query. */
.recs{display:grid;grid-template-columns:repeat(auto-fit,minmax(max(300px,(100% - 18px)/2),1fr));gap:18px}
.rec{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--wob);border-radius:var(--radius-lg);padding:14px 16px}
.rec.crit{border-left-color:var(--bad)}.rec.do{border-left-color:var(--good)}.rec.concept{border-left-color:var(--bright)}
.rec h3{margin:0 0 6px;font-size:13px;font-weight:600}
.rec .when{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.3px;padding:2px 8px;border-radius:20px;margin-bottom:7px;vertical-align:middle}
.rec .when.tbound{color:var(--bright);background:rgba(255,209,102,.12);border:1px solid rgba(255,209,102,.3)}
.rec .when.glob{color:var(--muted);background:transparent;border:1px solid var(--line)}
.rec.tb{cursor:pointer}
.rec[data-t]:hover{border-color:var(--muted)}
.rec.flash{border-color:var(--wob);box-shadow:0 0 0 2px rgba(167,139,250,.35);transition:box-shadow .2s}
.rec[data-t]:hover .when.tbound{background:rgba(255,209,102,.2)}
.rec p{margin:6px 0 0;font-size:13px;color:var(--ink)}.rec p b{color:#fff}
.rec p.fix{margin-top:9px;padding:7px 10px;background:rgba(70,211,154,.09);border-radius:var(--radius);color:#dfe7d8}
.rec p.fix b{color:#eafff2}
.fixlab{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.4px;color:var(--good);margin-right:6px;text-transform:uppercase}
/* §B.13 card evidence — a quiet "where this came from" line; transparency, never shouting. */
.rec p.based{margin-top:8px;font-size:12px;line-height:1.5;color:var(--muted)}
.basedlab{display:inline-block;font-size:9.5px;font-weight:700;letter-spacing:.5px;color:#7c8398;margin-right:6px;text-transform:uppercase}
/* INV-34 — card-click navigation: a brief pulse on the graph panel so the eye lands where the playhead
   jumped. CSS-only (the canvas draw is untouched). */
@keyframes graphpulse{0%{box-shadow:0 0 0 0 rgba(124,107,255,0)}18%{box-shadow:0 0 0 3px rgba(124,107,255,.55)}100%{box-shadow:0 0 0 0 rgba(124,107,255,0)}}
/* one shared pulse look for EVERY evidence target (§B.13 INV-48b — story arc, tonal bars,
   vitals strip, drawer panels), so the emphasis reads the same wherever a card leads. */
.tc-panel.pulse,.vitals.pulse{animation:graphpulse 1.1s ease-out;border-radius:var(--radius-lg)}
.empty-note{color:var(--bad);font-size:12px;margin:0 0 12px;font-weight:600}
.foot{color:var(--muted);font-size:11.5px;margin-top:8px;text-align:center}
.scale{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted);margin-top:8px}
.scalebar{height:10px;width:160px;border-radius:5px;background:linear-gradient(90deg,#000004,#3b0f70,#8c2981,#de4968,#fe9f6d,#fcfdbf)}
.presbar{height:10px;width:120px;border-radius:5px;background:linear-gradient(90deg,rgba(70,211,154,.06),rgba(70,211,154,1))}
.ptop{display:flex;align-items:center;gap:14px;margin-bottom:12px}
/* Play = accent-outline, not a loud solid block — matches how --wob is used elsewhere
   (thin accent lines on read/rec/cue), fills in on hover. Smaller than before. */
.pbtn{background:var(--panel2);color:var(--wob);border:1px solid var(--wob);border-radius:var(--radius);padding:7px 15px;font-weight:700;font-size:13px;cursor:pointer;transition:background var(--dur-base),color var(--dur-base)}
.pbtn:hover{background:var(--wob);color:var(--bg)}
.pbtn.pmini{padding:7px 10px;background:var(--panel2);color:var(--muted);border:1px solid var(--line);font-size:13px}
.pbtn.pmini:hover{background:var(--panel2);color:var(--ink)}
.ptime{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13px}
/* timeline callouts ("comments"): triangle cues over the scenes (canvas-drawn). The cards they
   point to live in the Recommendations panel under the graph — no separate list here any more. */
.ctip{position:fixed;z-index:60;pointer-events:none;display:none;background:rgba(12,14,20,.96);
 border:1px solid var(--line);border-radius:var(--radius);padding:7px 11px;font-size:12.5px;color:var(--ink);
 line-height:1.55;max-width:260px;box-shadow:0 6px 20px rgba(0,0,0,.45)}
.ctip b{font-weight:600}.ctip .tdim{color:var(--muted)}
.pstems{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.pstem{display:flex;align-items:center;gap:8px;background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:8px 10px}
.pstem .nm{flex:1;font-size:12.5px;font-weight:600}
.pstem button{background:transparent;border:1px solid var(--line);color:var(--muted);border-radius:var(--radius);font-size:10.5px;padding:3px 7px;cursor:pointer;font-weight:600}
.pstem button.on{color:var(--bg)}
.pstem button.mute.on{background:var(--bad);border-color:var(--bad)}
.pstem button.solo.on{background:var(--good);border-color:var(--good)}
.ltog{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.ltog .lbl{font-size:11px;color:var(--muted);margin-right:2px}
.ltog button{background:var(--panel2);border:1px solid var(--line);color:var(--muted);
 border-radius:var(--radius);font-size:11px;padding:4px 10px;cursor:pointer;font-weight:600}
.ltog button.on{background:var(--wob);border-color:var(--wob);color:var(--bg)}
/* sequencer legend: explains height=loudness, colour=frequency, M/S, weak */
.seqkey{display:flex;flex-wrap:wrap;align-items:center;gap:7px 16px;margin-top:10px;
 font-size:11px;color:var(--muted);line-height:1.5}
.seqkey b{color:var(--ink);font-weight:600}
.seqkey .sw{display:inline-block;width:46px;height:9px;border-radius:3px;vertical-align:middle;margin-right:5px}
.seqkey .chip{display:inline-flex;align-items:center}
.seqkey .ms{display:inline-block;min-width:13px;height:13px;line-height:13px;text-align:center;
 border-radius:3px;font-size:8px;font-weight:700;color:var(--bg);margin-right:4px}
/* Evidence drawer and Catalog: tc-panel chrome, collapsed by default. Top-level spacing comes from
   --rhythm (base margin-bottom); sub-panels nested INSIDE a container panel (#evidence, and #refPanel
   since the D-INV-36 merge — structural, not per-id) take the smaller --gap so the intra-panel gap
   is clearly tighter than the inter-panel rhythm (DS-INV-9 minimal slice, s57; widened s58). */
#evidence>details.tc-panel,#refPanel>details.tc-panel{margin-bottom:var(--gap)}
/* CATALOG inner tracks */
.catgrp{margin:4px 0 2px;color:var(--muted);font-size:10.5px;text-transform:uppercase;
 letter-spacing:.7px;font-weight:700}
.catrun{display:flex;align-items:center;gap:10px;padding:9px 12px;border:1px solid var(--line);
 border-radius:var(--radius);margin:7px 0;background:var(--panel2)}
.catrun.self{border-color:var(--wob);box-shadow:inset 0 0 0 1px rgba(167,139,250,.25)}
.catrun .cv{font-weight:600;color:var(--ink);white-space:nowrap}
.catrun .cd{color:var(--muted);font-size:11.5px;white-space:nowrap}
.catrun .cmode{font-size:9.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);
 border:1px solid var(--line);border-radius:20px;padding:1px 7px}
.catrun .cverd{color:var(--ink);font-size:12.5px;flex:1;min-width:120px}
.catrun a.copen{margin-left:auto;color:var(--wob);font-size:11.5px;font-weight:600;
 text-decoration:underline;text-underline-offset:2px;
 white-space:nowrap;border:1px solid var(--wob);border-radius:var(--radius);padding:3px 10px;transition:background var(--dur-fast)}
/* same chain-link glyph as the web-panel sources, + underline (2026-07-05: the same one, underlined) */
.catrun a.copen .tc-rn-link-ico{width:11px;height:11px;vertical-align:-1px;margin-right:5px}
.catrun a.copen:hover{background:rgba(167,139,250,.16);text-decoration:underline}
.catrun .cnow{margin-left:auto;color:var(--wob);font-size:11px;font-weight:700;white-space:nowrap}
.catrun .cmiss{margin-left:auto;color:var(--muted);font-size:11px}
.cattrack{border:1px solid var(--line);border-radius:var(--radius-lg);margin:8px 0;background:rgba(0,0,0,.12)}
.cattrack>summary{cursor:pointer;list-style:none;padding:11px 14px;font-weight:600;color:var(--ink)}
.cattrack>summary::-webkit-details-marker{display:none}
.cattrack>summary::before{content:"▸ ";color:var(--muted)}
.cattrack[open]>summary::before{content:"▾ "}
.cattrack>summary .cvn{color:var(--muted);font-weight:500;font-size:12px;margin-left:6px}
.cattrack .catinner{padding:0 14px 10px}
</style></head><body class="__BODYCLASS__"><div class="wrap">
<div class="ctip" id="ctip"></div>
<div class="topbar">
 <div><a id="backLink" class="backlink" href="#" hidden></a>
   <div class="brandkick">Track Coach __MODEBADGE__</div>
   <h1 id="title"></h1><div class="sub" id="sub"></div></div>
 <!-- Simple⇄Detailed is a PURE client-side toggle: it shows/hides panels already
      embedded in this file. It never calls the network, never costs anything. On a QUICK read
      there are no stems to reveal, so the toggle is replaced server-side by a hint. -->
 __VIEWTOGGLE__
</div>
<div class="srcmeta" id="srcmeta"></div>
<!-- Run-mode note: only on a quick read, spell out what a full run would add (2026-06-20). -->
__MODENOTE__

<!-- VITALS — the credible spec-sheet, read in one glance, builds trust.
     Single authoritative numbers about the finished mix (no time axis). -->
<div class="vitals" id="vitals"></div>

<!-- (the calm verdict headline panel was removed 2026-07-03, s49.
     The verdict text still feeds the catalog self-row below; only the top panel is gone.) -->

<!-- 1. VISUAL FIRST: Track Story + player/sequencer is the centrepiece & the proof. -->
<details class="tc-panel" id="storyPanel" open>
 <summary><span id="storyTitle"></span></summary>
 <p class="hint" id="storyHint"></p>
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
</details>

<!-- 2. RECOMMENDATIONS sit DIRECTLY under the graph — these ARE the cards the timeline
     triangles point to (no separate callout list on the graph any more). Each timecoded
     rec has a matching triangle above; clicking a triangle flashes its card here. Simple
     shows ONLY the timecoded recs (the ones with a triangle); Detailed shows all. -->
<details class="tc-panel" id="recsPanel" open>
 <summary><span id="recsTitle"></span></summary>
 <p class="hint" id="recsHint"></p>
 <div class="legend" id="recLegend" style="margin-bottom:14px"></div>
 <div class="recs" id="recs"></div>
</details>

<!-- 3. THE READ: the diagnosis in prose, the Producer's view. Rendered SERVER-SIDE (markdown→HTML
     in Python) so #readBody is a real, testable artifact and headings never leak a literal '#'. -->
<details class="tc-panel read" id="readPanel"__READPANELSTYLE__>
 <summary><span id="readTitle">__READTITLE__</span></summary>
 <div id="readBody">__READBODY__</div>
</details>

<!-- Tonal balance — sits between the producer's read and the reference read (§D.10.3 order:
     producer read → tonal balance → centroid read → web panel). Always visible. -->
<details class="tc-panel" id="tonalPanel" open>
 <summary>Tonal balance — average spectrum of the mix</summary>
 <p class="hint">Each bar is one octave band's level across the whole track (0 dB = loudest band). A band that sticks out from its neighbours is a resonance (boxy/harsh); a dip is a hole (dull/thin).</p>
 <canvas id="tonal" height="170"></canvas>
</details>

<!-- 4. REFERENCE PANEL (§D.10, D-INV-36) — ONE merged container: shared direction selector +
     nested centroid read + nested web notes (both open). Server-side rendered; Detailed-only
     via CSS on the container (body.simple hides it whole). Empty string when quick mode or
     no run_dir; a NON-expandable stub plaque ("no close direction yet" / "no comparison
     data in this run") when directions exist but there is nothing to compare (D-INV-36e). -->
__REFREAD__

<details class="tc-panel" id="evidence">
 <summary>Evidence &amp; detail — the project arrangement, automation, stem↔track map, rhythm and transcribed notes</summary>

 <details class="tc-panel" id="arrPanel" open>
  <summary><span id="arrTitle"></span></summary>
  <p class="hint" id="arrHint"></p>
  <div class="legend" id="arrLegend"></div>
  <canvas id="arr" height="300"></canvas>
  <div class="readout" id="arrReadout"></div>
 </details>

 <details class="tc-panel" id="autoPanel" open>
  <summary><span id="autoTitle"></span></summary>
  <p class="hint" id="autoHint"></p>
  <canvas id="auto" height="220"></canvas>
  <div class="readout" id="autoReadout"></div>
 </details>

 <details class="tc-panel" id="mapPanel" open>
  <summary><span id="mapTitle"></span></summary>
  <p class="hint" id="mapHint"></p>
  <div class="mgrid" id="mapRows"></div>
  <div id="mapNotes" style="margin-top:14px"></div>
 </details>

 <details class="tc-panel" id="rhyPanel" open>
  <summary><span id="rhyTitle"></span></summary>
  <p class="hint" id="rhyHint"></p>
  <div class="mgrid" id="rhyRows"></div>
  <div id="rhySep" style="margin-top:14px"></div>
 </details>

 <details class="tc-panel" id="notePanel" open>
  <summary><span id="noteTitle"></span></summary>
  <p class="hint" id="noteHint"></p>
  <canvas id="note" height="260"></canvas>
  <div class="readout" id="noteReadout"></div>
 </details>
</details>

<!-- CATALOG — every track & version analysed. Current track's versions inline; other
     tracks fold open to their own versions. Links are relative (work on GitHub Pages).
     Shown in BOTH Simple and Detailed views. -->
<details class="tc-panel" id="catalog" style="display:none">
 <summary id="catSummary"></summary>
 <p class="hint" id="catHint" style="margin:6px 2px 14px"></p>
 <div id="catBody"></div>
</details>

<div class="foot" id="foot"></div>
</div>
<script>
const D=__PAYLOAD__, T=D.t;
// INV-STEMNAME-ALL (0.9.22): one display name per stem/family, resolved from the Python payload.
// Every JS surface MUST go through disp()/fdisp() — never show a raw Demucs/model name.
function disp(s){return (D.stem_display&&D.stem_display[s])||"a part";}
function fdisp(s){return (D.fam_display&&D.fam_display[s])||"a part";}
const fmtT=s=>(s<0?"0:00":Math.floor(s/60)+":"+String(Math.round(s%60)).padStart(2,"0"));
// Timeline callouts ("comments"): the located recommendations, in time order, each
// given a letter (a,b,c…). The same list drives the triangle cues over the scenes,
// the list under the story, and the letter badges in "Start here" — one shared identity.
const CUELET="abcdefghijklmnopqrstuvwxyz";
const CUES=(D.recs||[]).map((r,i)=>({r,i})).filter(o=>o.r.t!=null)
  .sort((a,b)=>a.r.t-b.r.t).map((o,k)=>({r:o.r,idx:o.i,t:+o.r.t,letter:CUELET[k]||"•",cls:o.r.cls||""}));
const cueByIdx={};CUES.forEach(c=>{cueByIdx[c.idx]=c;});
// flash + scroll to the FULL recommendation card (the single place the
// paragraph + "→ Try" fix live). Used by the arc's cue click — triangle band or anywhere
// in the cue's column (SPEC §B.13 INV-49b); the canvas click handler is its only caller.
function flashRec(letter){if(!letter)return;const el=document.querySelector('#recs .rec[data-let="'+letter+'"]');
 if(!el)return;el.classList.add("flash");el.scrollIntoView({behavior:"smooth",block:"center"});
 setTimeout(()=>el.classList.remove("flash"),1600);}
// H1 leads with the TRACK name (from --title); the brand lives in the .brandkick
// eyebrow above + the footer + the browser tab, not stealing the track-name slot.
document.getElementById("title").textContent=document.title.replace(/^Track Coach · /,"");
// ── Back to the Library/Catalog. Prefer the catalog page embedded at build time (D.backHref) so the
// button is ALWAYS there however the widget was opened; otherwise fall back to history.back() when
// the catalog navigated here in place. Hidden only if neither is available (standalone widget).
(function(){const b=document.getElementById("backLink");if(!b)return;
 b.textContent=T.back_to_library||"← Library";
 if(D.backHref){b.href=D.backHref;b.hidden=false;}
 else if(history.length>1){b.hidden=false;
  b.addEventListener("click",e=>{e.preventDefault();history.back();});}})();
(function(){const sfx=D.mode==="quick"?(T.subtitle_quick||"quick read"):(T.subtitle||"");
document.getElementById("sub").textContent=`${fmtT(D.dur)} · ${D.tempo} BPM`+(sfx?` · ${sfx}`:"");})();
// (The run-mode badge + quick explainer are rendered server-side into the markup — see build_html.)
// ── Source files + date: what was analysed and when (header line + folded into footer)
const META=D.meta||{};
(function(){const el=document.getElementById("srcmeta");if(!el)return;const bits=[];
 if(META.audio)bits.push(`${T.src_audio||"Audio"}: <b title="${META.audio}">${META.audio}</b>`);
 if(META.als)bits.push(`${T.src_project||"Project"}: <b title="${META.als}">${META.als}</b>`);
 if(META.track_version)bits.push(`<b>${META.track_version}</b>`);
 if(META.analyzed_at){const adate=(META.analyzed_at||"").split(" ")[0];
  const bdate=META.built_at||"";const diffDate=bdate&&bdate!==adate;
  bits.push(`${T.src_analyzed||"Analyzed"}: <b>${META.analyzed_at}</b>`+
   (diffDate?`<span style="opacity:.6"> · report built: ${bdate}</span>`:""));}
 el.innerHTML=bits.join('<span style="opacity:.4">·</span>');})();
// (the calm verdict headline panel was removed 2026-07-03, s49;
//  D.verdict still feeds the catalog self-row render below.)
// ── Simple⇄Detailed toggle. PURE presentation: flips a body class that hides/shows
// already-embedded panels and re-filters the story lanes. No network, no recompute.
(function(){const tg=document.getElementById("viewToggle");if(!tg)return;
 // Quick reads have no Simple/Detailed view (no stems to reveal): the server rendered a hint in
 // #viewToggle instead of the control, and we bail here so the body never gets `.simple` — the
 // evidence drawer and all recommendations stay visible.
 if(D.mode==="quick")return;
 tg.setAttribute("aria-label",T.view_aria||"Detail level");
 tg.innerHTML=`<button data-v="simple">${T.view_simple||"Simple"}</button>`+
  `<button data-v="full">${T.view_full||"Detailed"}</button>`;
 /* VIEW_LOGIC_START — pure DOM-free view helpers (SPEC §B.15/INV-31); node-executed by test_view_logic */
 function resolveView(hash,stored){
  var h=(hash||"").toLowerCase();
  if(h.indexOf("full")>=0||h.indexOf("detail")>=0)return "detailed";
  if(h.indexOf("simple")>=0||h.indexOf("calm")>=0)return "simple";
  if(stored==="detailed")return "detailed";
  if(stored==="simple")return "simple";
  return "simple";
 }
 function safeGetView(){try{return localStorage.getItem("tc_view");}catch(e){return null;}}
 function safeSetView(v){try{localStorage.setItem("tc_view",v);}catch(e){}}
 if(typeof module!=="undefined")module.exports={resolveView,safeGetView,safeSetView};
 /* VIEW_LOGIC_END */
 // _viewInited: only update the URL hash on USER toggles, not on the initial applyView() call.
 let _viewInited=false;
 function applyView(v){document.body.classList.toggle("simple",v==="simple");
  tg.querySelectorAll("button").forEach(b=>b.classList.toggle("on",b.dataset.v===v||(v==="detailed"&&b.dataset.v==="full")));
  if(v==="simple"&&window.__resetMix)window.__resetMix();  // SPEC §B.14: Simple hides the stem grid (M/S controls) → reset to full mix, never strand a hidden solo/mute
  // JOB-2: reflect view in URL hash so the state is shareable and the page opens in the right view.
  // Only update after init (on actual toggles) to keep the URL clean on first load.
  if(_viewInited){try{history.replaceState(null,'',v==='simple'?'#simple':'#detailed');}catch(e){}}
  // let every canvas relayout for its new width / lane count
  window.dispatchEvent(new Event("resize"));}
 tg.querySelectorAll("button").forEach(b=>b.onclick=()=>{applyView(b.dataset.v);safeSetView(b.dataset.v==="full"?"detailed":b.dataset.v);});
 // INV-31: initial view from URL hash (one-shot) > remembered preference > calm default.
 // Only a toggle writes tc_view; loading from hash or default never persists a preference.
 applyView(resolveView(location.hash,safeGetView()));_viewInited=true;})();
// The Producer's read (#readTitle/#readBody) is rendered SERVER-SIDE (see _read_html in
// build_widget.py) and already present in the markup — no client-side markdown parsing here.
document.getElementById("arrTitle").textContent=T.arr_title;
document.getElementById("arrReadout").textContent=T.hover;
document.getElementById("autoReadout").textContent=T.hover;
document.getElementById("noteReadout").textContent=T.hover;
document.getElementById("recsTitle").textContent=T.recs_title;
document.getElementById("recsHint").textContent=T.recs_hint;
document.getElementById("recLegend").innerHTML=
 `<span><i style="background:var(--bad)"></i>${T.legend_crit}</span>`+
 `<span><i style="background:var(--good)"></i>${T.legend_do}</span>`+
 `<span><i style="background:var(--bright)"></i>${T.legend_concept}</span>`;
(function(){let f=(T.footer||"").replace("{ver}",D.version||"");
 const tail=[];if(META.audio)tail.push(META.audio);if(META.analyzed_at)tail.push(META.analyzed_at);
 if(tail.length)f+=" · "+tail.join(" · ");
 document.getElementById("foot").textContent=f;})();
// ── CATALOG: every track & version analysed. Current track inline; others fold open.
// Relative links → work when the whole output tree is published (e.g. GitHub Pages).
(function(){const wrap=document.getElementById("catalog");const C=D.catalog;
 if(!wrap||!C||!C.tracks||!C.tracks.length){if(wrap)wrap.style.display="none";return;}
 const esc=s=>(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
 const runRow=r=>{const right=r.self?`<span class="cnow">● ${T.cat_current||"you are here"}</span>`
    :r.exists?`<a class="copen" href="${encodeURI(r.rel)}"><svg class="tc-rn-link-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 15l6-6"/><path d="M11 6l1-1a4 4 0 0 1 6 6l-1 1"/><path d="M13 18l-1 1a4 4 0 0 1-6-6l1-1"/></svg>${T.cat_open||"Open"}</a>`
    :`<span class="cmiss">${T.cat_missing||"(file not found)"}</span>`;
  // self row may not have its verdict recorded in index.json yet — fall back to this build's
  const vt=(r.self&&!r.verdict)?(D.verdict||""):(r.verdict||"");
  return `<div class="catrun${r.self?" self":""}">`+
   `<span class="cv">${esc(r.version||"—")}</span>`+
   (r.date?`<span class="cd">${esc(r.date)}</span>`:"")+
   (r.mode?`<span class="cmode">${esc(r.mode)}</span>`:"")+
   `<span class="cverd">${esc(vt)}</span>${right}</div>`;};
 const selfTrack=C.tracks.find(t=>t.self),others=C.tracks.filter(t=>!t.self);
 let html="";
 if(selfTrack){html+=`<div class="catgrp">${T.cat_this_track||"This track"} · ${esc(selfTrack.track)}</div>`+
   selfTrack.runs.map(runRow).join("");}
 if(others.length){html+=`<div class="catgrp" style="margin-top:14px">${T.cat_other_tracks||"Other tracks"}</div>`+
   others.map(t=>{const vn=(T.cat_versions||"{n} version(s)").replace("{n}",t.runs.length);
    return `<details class="cattrack"><summary>${esc(t.track)}<span class="cvn">${vn}</span></summary>`+
     `<div class="catinner">${t.runs.map(runRow).join("")}</div></details>`;}).join("");}
 document.getElementById("catBody").innerHTML=html;
 document.getElementById("catSummary").textContent=`${T.cat_title||"All analyses"} (${C.n_runs})`;
 document.getElementById("catHint").textContent=T.cat_hint||"";
 wrap.style.display="";
 if((location.hash||"").toLowerCase().indexOf("catalog")>=0)wrap.open=true;})();
// sequencer legend — what the lane drawing actually encodes (two dimensions + controls)
(function(){const el=document.getElementById("seqKey");if(!el)return;
 const stk="linear-gradient(0deg,rgb(255,78,80) 0 34%,rgb(76,214,140) 34% 67%,rgb(80,168,255) 67% 100%)";
 el.innerHTML=
  `<span class="chip"><span class="sw" style="background:${stk}"></span><b>Stacked layers</b>&nbsp;= `+
   `<b style="color:rgb(255,78,80)">bass</b> / <b style="color:rgb(76,214,140)">mids</b> / <b style="color:rgb(80,168,255)">highs</b>, bottom→top. `+
   `Taller band = more energy there; several tall at once = they hit together.</span>`+
  `<span class="chip"><b>≈&nbsp;name</b>&nbsp;= which project track this stem sounds like (only when we're confident)</span>`;
 // SPEC CR-2 (docs/SPEC.md §1) + INV-STEMNAME-NEARSILENT-ID (s46): near-silent stems are dropped from
 // the per-stem VIZ (rhythm, notes, masking cards) but appear as muted lanes. The legend note names
 // them by their identified label so "vocals, piano → near-silent 1, near-silent 2" is never shown.
 const OM=(D.stem&&D.stem.omitted)||[];
 if(OM.length){
  const names=OM.map(s=>disp(s)).join(", ");
  el.insertAdjacentHTML("beforeend",
   `<span class="chip" id="omittedNote"><span class="sw" style="background:#a78bfa;opacity:.55"></span>`+
   `stems ${names} omitted — too little material to read</span>`);}
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
 const tpc=(V.tempo_changes||[]).length;
 push("Tempo",(V.tempo_bpm!=null?V.tempo_bpm+" <small>BPM</small>"+(tpc>1?` <small>+${tpc-1} change${tpc>2?"s":""}</small>`:""):null),
   "",(tpc>1?"Project tempo from the .als — it changes mid-track; see the marks on the timeline.":(D.tempo_src==="als"?"Project tempo from the .als.":"Detected from the audio. May differ ±1–2 from the project tempo.")));
 push("Key",V.key+(V.key_conf!=null&&V.key_conf<0.5?" <small>best guess</small>":""),"",`Estimated key/scale (Krumhansl-Schmuckler on chroma). Confidence: ${V.key_conf!=null?V.key_conf:"—"}. A confidence near 0 means ambiguous/atonal.`);
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
 const dev=r.ev?` data-ev="${r.ev}"`:"";
 const fix=r.fix?`<p class="fix"><span class="fixlab">→ Try</span> ${r.fix}</p>`:"";
 const based=r.based?`<p class="based"><span class="basedlab">Based on</span> ${r.based}</p>`:"";
 const cue=cueByIdx[i];const tag=cue?`<b style="color:var(--ink);text-transform:uppercase">${cue.letter}</b> `:"";
 const chip=tb?`<span class="when tbound">⏱ ${r.when}</span>`:`<span class="when glob">whole track</span>`;
 const dl=cue?` data-let="${cue.letter}"`:"";
 return `<div class="rec ${r.cls}${tb?' tb':''}"${dl}${jump}${dev}>${tag}${chip}<h3>${r.h}</h3><p>${r.p}</p>${fix}${based}</div>`;}).join("")||"<p class='hint'>—</p>";
// The card CLICK wiring (INV-48) lives AFTER the panel-gating IIFEs below — a card's target must be
// judged present/hidden only once every panel has decided whether it renders on this run's data.

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
 const PADL=70,PADR=14,PADT=30,PADB=22,RIB=30,MOM=18,CUR=112,rowH=12,gap=8;
 // ONE structure bar: scenes are coloured + lettered by their self-similarity cluster
 // (s.letter = recurrence cluster). Same letter ⇒ same hue ⇒ that part returns; the
 // repeating ones get an outline. (Replaces the old separate "Form / repeats" lane.)
 const SPAL=["#5b8cff","#46d39a","#ffb454","#c77dff","#5ad1c2","#ff6b9d"];
 const sceneLetters=[...new Set((ST.scenes||[]).map(s=>s.letter))];
 const scol=L=>SPAL[Math.max(0,sceneLetters.indexOf(L))%SPAL.length];
 const sreps=new Set();{const seen={};(ST.scenes||[]).forEach(s=>{if(seen[s.letter])sreps.add(s.letter);seen[s.letter]=1;});}
 const sceneLeadVaries=new Set((ST.scenes||[]).map(s=>s.lead).filter(Boolean)).size>1;
 // colour for a callout cue/triangle by its rec class (crit/do/concept)
 const cueCol=cls=>cls==="crit"?getCss("--bad"):cls==="do"?getCss("--good"):cls==="concept"?getCss("--bright"):getCss("--wob");
 const fams=ST.families||[],nf=fams.length,bins=ST.bins,iv=ST.intensity,nb=bins.length;
 // The Track-story graph REACTS to the view toggle (2026-06-19; restores the
 // 0.5.13 behaviour that 0.5.19 wrongly removed — see JOURNAL.md). Simple = the 3 power-driving
 // lanes only (energy/brightness/density = in_power); Detailed = all lanes (+modulation, +stereo
 // width). apply() dispatches a resize on toggle, so resize()→pickComps() relayouts live.
 const ALLCOMPS=ST.components||[];const compLaneH=20;  // CONSTANT per lane in both views, so the
 // total curve-area height = (#lanes × compLaneH) is PROPORTIONAL TO THE LANE COUNT. That makes
 // Simple (4 lanes) shorter than Detailed (5) automatically. Session 0b5ab53e:
 //   L186 keep stereo or density in Simple too → Simple = energy+brightness+density+stereo;
 //   L402 in the Simple view the total height for their area must be SMALLER → area ∝ count (4<5).
 // (Supersedes the older 2-full-size reading from L542 of a prior session. DON'T revert to that.)
 const SIMPLE_LANES=["energy","brightness","density","stereo"];
 let comps=ALLCOMPS,ncomp=comps.length;
 // A quick read has no Simple/Detailed toggle, so it draws the SAME calm 4-lane graph the other
 // widgets open with (the full Detailed 5th lane = modulation is a deep-detail thing). We treat
 // quick like Simple for LANE SELECTION only — without putting `.simple` on <body>, so the
 // evidence drawer and all recommendations stay visible in quick.
 const pickComps=()=>{const simple=document.body.classList.contains("simple")||D.mode==="quick";
   comps=simple?ALLCOMPS.filter(c=>SIMPLE_LANES.includes(c.key)):ALLCOMPS;
   ncomp=comps.length;};
 const curveTop=PADT+RIB+MOM,compTop=curveTop+CUR+10,famBot=()=>famTop+nf*rowH;
 let famTop=compTop+ncomp*compLaneH+gap;
 let W,H;const xOf=t=>PADL+(t/ST.dur)*(W-PADL-PADR);
 const imax=Math.max.apply(null,iv);
 function resize(){W=cv.clientWidth;pickComps();famTop=compTop+ncomp*compLaneH+gap;H=famTop+nf*rowH+PADB;cv.style.height=H+"px";
  cv.width=W*devicePixelRatio;cv.height=H*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);draw();}
 function draw(hx){ctx.clearRect(0,0,W,H);
  ST.scenes.forEach(s=>{const x0=xOf(s.t0),x1=xOf(s.t1),w=Math.max(1,x1-x0-1),rep=sreps.has(s.letter),c=scol(s.letter);
   ctx.fillStyle=c+(rep?"cc":"99");ctx.fillRect(x0,PADT,w,RIB);
   if(rep){ctx.strokeStyle=c;ctx.lineWidth=1.2;ctx.strokeRect(x0+.5,PADT+.5,w-1,RIB-1);}
   if(w>44){ctx.fillStyle="#0c0e14";ctx.textAlign="left";ctx.textBaseline="alphabetic";
    ctx.font="700 11px sans-serif";ctx.fillText(s.letter+" · "+s.name,x0+6,PADT+13);
    if(s.lead&&sceneLeadVaries){ctx.font="600 9px sans-serif";ctx.fillText("lead: "+s.lead,x0+6,PADT+25);}}});
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
  // tempo changes (from the .als) — teal marks where the tempo switches; label below the metre row.
  // Skips the base tempo; nothing drawn when the tempo is constant.
  const TPC=(D.vitals&&D.vitals.tempo_changes)||[];
  if(TPC.length>1)TPC.slice(1).forEach(c=>{const x=xOf(c.time_s);
   ctx.strokeStyle="#4ec3c3";ctx.lineWidth=1;ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(x,PADT);ctx.lineTo(x,famBot());ctx.stroke();ctx.setLineDash([]);
   ctx.fillStyle="#4ec3c3";ctx.font="700 9px sans-serif";ctx.textAlign="center";ctx.fillText(c.bpm+" bpm",x,famBot()+20);});
  ctx.fillStyle=getCss("--muted");ctx.font="10px sans-serif";ctx.textAlign="center";for(let t=0;t<=ST.dur;t+=60)ctx.fillText(fmtT(t),xOf(t),H-7);
  if(hx!=null){ctx.strokeStyle="rgba(255,255,255,.6)";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(hx,PADT);ctx.lineTo(hx,famBot());ctx.stroke();}}
 // find a callout cue near the cursor. The cue's click zone is its whole COLUMN on the
 // canvas (SPEC §B.13 INV-49a, 2026-07-05) — any height, not only the triangle band; the
 // snap radius (11 px) is unchanged. Away from every cue the arc stays plain click=seek.
 function cueAt(mx){let best=null,bd=11;
  CUES.forEach(c=>{const d=Math.abs(mx-xOf(c.t));if(d<bd){bd=d;best=c;}});return best;}
 cv.addEventListener("mousemove",e=>{const r=cv.getBoundingClientRect();const mx=e.clientX-r.left,my=e.clientY-r.top;
  const cue=cueAt(mx,my);cv.style.cursor=cue?"pointer":"default";
  const t=Math.max(0,Math.min(ST.dur,(mx-PADL)/(W-PADL-PADR)*ST.dur));draw(xOf(t));
  if(cue){showTip(e,`<b>${cue.letter.toUpperCase()} · ${cue.r.when}</b><br>${cue.r.h}<br><span class="tdim">click to read below</span>`);return;}
  const sc=ST.scenes.find(s=>t>=s.t0&&t<s.t1);const on=fams.filter(f=>f.intervals.some(p=>t>=p[0]&&t<=p[1])).map(f=>f.name);
  showTip(e,`<b>${fmtT(t)}</b>`+(sc?` · <b>${sc.letter} · ${sc.name}</b>`:"")
   +(sc&&sc.lead&&sceneLeadVaries?` <span class="tdim">· lead: ${sc.lead}</span>`:"")
   +(sc&&sreps.has(sc.letter)?`<br><span class="tdim">part ${sc.letter} returns elsewhere</span>`:"")
   +(on.length?`<br><span class="tdim">playing: ${on.join(", ")}</span>`:""));});
 cv.addEventListener("mouseleave",()=>{draw();hideTip();cv.style.cursor="default";});
 cv.addEventListener("click",e=>{const r=cv.getBoundingClientRect();const mx=e.clientX-r.left,my=e.clientY-r.top;
  const cue=cueAt(mx,my);
  if(cue){if(window.__seek)window.__seek(cue.t);flashRec(cue.letter);return;}
  const t=Math.max(0,Math.min(ST.dur,(mx-PADL)/(W-PADL-PADR)*ST.dur));if(window.__seek)window.__seek(t);});
 PH.push(t=>draw(xOf(t)));
 window.addEventListener("resize",resize);resize();
})();

// ── Form / repeats: now folded INTO the single structure bar at the top of the Track
// Story (each named scene is coloured + lettered by its self-similarity cluster, so a
// returning part shares letter+colour). The old standalone form lane was removed in 0.6.1.

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

// ── Automation "intention vs result": real project envelopes (filter/gain/pitch/sends)
// as small-multiple lanes, each scaled to its own range, on the SAME time axis as the
// arrangement. A faint Brightness ghost rides in every lane so a flat automation against
// a still-rising sound reads at a glance — the marquee "intention and result disagree".
// (Restored in 0.6.6; the panel was dropped in the 0.6 declutter though its data stayed
//  in the payload. The stem-frequency heatmap remains folded into the sequencer colour.)
(function(){
 const A=ALS,P=document.getElementById("autoPanel");
 if(!A||!A.automations||!A.automations.length){if(P)P.style.display="none";return;}
 const AU=A.automations;
 document.getElementById("autoTitle").textContent=T.auto_title;
 document.getElementById("autoHint").textContent=T.auto_hint;
 // Brightness reference (normalised 0..1 over story bins) — the "result" the ear hears.
 const SB=(D.story&&D.story.bins)||null;
 const bComp=((D.story&&D.story.components)||[]).find(c=>c.key==="brightness");
 const bref=(SB&&bComp&&bComp.vals&&bComp.vals.length===SB.length)?bComp.vals:null;
 const cv=document.getElementById("auto"),ctx=cv.getContext("2d");
 const PADL=140,PADR=14,PADT=14,PADB=24,laneGap=10;const n=AU.length;
 let W,H,laneH;const xOf=t=>PADL+(t/D.dur)*(W-PADL-PADR);
 // step lookup of an envelope value at time t (envelopes hold between points)
 const valAt=(pts,t)=>{let v=pts[0][1];for(const p of pts){if(p[0]<=t)v=p[1];else break;}return v;};
 const yIn=(top,v,lo,hi)=>top+laneH-3-((hi>lo?(v-lo)/(hi-lo):0))*(laneH-6);
 function resize(){W=cv.clientWidth;laneH=54;H=PADT+PADB+n*(laneH+laneGap);cv.style.height=H+"px";
  cv.width=W*devicePixelRatio;cv.height=H*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);draw();}
 function draw(hx){ctx.clearRect(0,0,W,H);
  AU.forEach((au,i)=>{const top=PADT+i*(laneH+laneGap),col=au.fam||"#8b94a8";
   // lane baseline + label
   ctx.strokeStyle=getCss("--line");ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(PADL,top+laneH-2);ctx.lineTo(W-PADR,top+laneH-2);ctx.stroke();ctx.globalAlpha=1;
   ctx.fillStyle=getCss("--muted");ctx.font="600 10px sans-serif";ctx.textAlign="right";ctx.textBaseline="middle";
   const lbl=au.label.length>26?au.label.slice(0,25)+"…":au.label;
   ctx.fillText(lbl,PADL-8,top+laneH/2-4);ctx.textBaseline="alphabetic";
   // faint Brightness ghost (the "result") for direct comparison
   if(bref){ctx.strokeStyle="#ffd166";ctx.globalAlpha=.28;ctx.lineWidth=1;ctx.setLineDash([3,3]);ctx.beginPath();
    SB.forEach((t,j)=>{const x=xOf(t),y=top+laneH-3-bref[j]*(laneH-6);j?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();
    ctx.setLineDash([]);ctx.globalAlpha=1;}
   // the automation envelope itself (the "intention"), scaled to its own range
   ctx.strokeStyle=col;ctx.lineWidth=1.8;ctx.beginPath();
   au.pts.forEach((p,j)=>{const x=xOf(p[0]),y=yIn(top,p[1],au.vmin,au.vmax);j?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();});
  drawLocators(ctx,xOf,PADT,H-PADB,null);
  ctx.fillStyle=getCss("--muted");ctx.font="10px sans-serif";ctx.textAlign="center";
  for(let t=0;t<=D.dur;t+=60)ctx.fillText(fmtT(t),xOf(t),H-8);
  if(hx!=null){ctx.strokeStyle="rgba(255,255,255,.5)";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(hx,PADT);ctx.lineTo(hx,H-PADB);ctx.stroke();}}
 cv.addEventListener("mousemove",e=>{const r=cv.getBoundingClientRect();
  const t=Math.max(0,Math.min(D.dur,(e.clientX-r.left-PADL)/(W-PADL-PADR)*D.dur));draw(xOf(t));
  const parts=AU.map(au=>`${au.label.split(" · ").pop()}: <b>${(+valAt(au.pts,t)).toFixed(2)}</b>`);
  document.getElementById("autoReadout").innerHTML=`<span><b>${fmtT(t)}</b></span>`+parts.map(p=>`<span>${p}</span>`).join("");});
 cv.addEventListener("mouseleave",()=>{draw();document.getElementById("autoReadout").textContent=T.hover;});
 cv.addEventListener("click",e=>{const r=cv.getBoundingClientRect();const t=Math.max(0,Math.min(D.dur,(e.clientX-r.left-PADL)/(W-PADL-PADR)*D.dur));if(window.__seek)window.__seek(t);});
 PH.push(t=>draw(xOf(t)));
 window.addEventListener("resize",resize);
 const ev=document.getElementById("evidence");if(ev)ev.addEventListener("toggle",()=>{if(ev.open)resize();});
 resize();
})();

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
     <span style="width:38px;color:var(--muted)">${fdisp(m.family)}</span>
     <div style="flex:1;height:6px;background:var(--line);border-radius:3px;overflow:hidden">
       <div style="height:100%;width:${w}%;background:${FCOL[m.family]||"#888"}"></div></div>
     <span style="width:34px;text-align:right;color:var(--muted)">${m.r.toFixed(2)}</span></div>`;}).join("");
  return `<div class="mcard"><div style="display:flex;justify-content:space-between;align-items:baseline">
    <div class="z" style="font-size:13px;color:var(--ink);font-weight:600">${disp(name)}</div>
    <span class="tag ${vcls}" style="margin-top:0">${head}</span></div>
    ${bars}<div class="z" style="margin-top:8px;color:var(--ink-dim)">${d.verdict_text}</div></div>`;}).join("");
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
 const OM_RHY=new Set((D.stem&&D.stem.omitted)||[]);
 document.getElementById("rhyRows").innerHTML=Object.entries(R.rhythm).filter(([s])=>!OM_RHY.has(s)).map(([s,d])=>{
  const col=FCOL[s]||"#8b94a8";
  const tight=d.offgrid_ms!=null?T.rhy_tight.replace("{ms}",d.offgrid_ms):"—";
  const sync=d.syncopation_pct!=null?T.rhy_sync.replace("{p}",d.syncopation_pct):"—";
  return `<div class="mcard"><div class="z" style="font-size:13px;color:var(--ink);font-weight:600">${disp(s)}</div>
   <div class="pct" style="color:${col};font-size:20px">${T.rhy_rate.replace("{r}",d.onset_rate)}</div>
   <div class="z">${tight} · ${sync}</div>${spark(d.onset_density,col)}</div>`;}).join("");
 const sep=R.separation||{};let html="";
 const rdb=sep.reconstruction_error_db;
 const rcls=rdb==null?"warn":rdb<-25?"do":rdb<-12?"concept":"crit";
 // C5: human-readable headline in h3; raw dB in title tooltip for producers who want it.
 const sepHead=rdb==null?"—":rdb<-25?"The split is clean — the parts add back up to the original mix"
   :rdb<-12?"The stems don't sum back cleanly — some signal may bleed between parts"
   :"The stems don't add back up to the mix";
 html+=`<div class="rec ${rcls}"><div class="when">${T.rhy_sep}</div>
   <h3>${sepHead}</h3></div>`;
 const leaks=(sep.leakage||[]).filter(l=>l.r>=0.2);
 // C6: words-first for leakage pairs; raw numbers in a title tooltip.
 let lbody;
 if(!leaks.length){lbody=T.rhy_noleak;}
 else{const tip=leaks.map(l=>`${disp(l.a)} ↔ ${disp(l.b)}: ${l.r.toFixed(2)}`).join(", ");
  const top=leaks[0];const rest=leaks.slice(1);
  const allClean=rest.every(l=>l.r<0.4);
  let txt=`${disp(top.a)} and ${disp(top.b)} bleed into each other noticeably`;
  if(rest.length&&allClean)txt+="; the rest stay clean";
  else if(rest.length)txt+="; "+rest.map(l=>`${disp(l.a)} and ${disp(l.b)} overlap slightly`).join(", ");
  lbody=`<span title="${tip.replace(/"/g,'&quot;')}">${txt}</span>`;}
 html+=`<div class="rec ${leaks.length?"concept":"do"}" style="margin-top:12px"><div class="when">${T.rhy_leak}</div>
   <p style="margin-top:2px">${lbody}</p></div>`;
 // CR-4: bands that are most likely a louder, correlated neighbour bleeding in — caveat, don't attribute.
 const bleed=D.leakage_caveats||[];
 if(bleed.length){html+=`<div class="rec crit" style="margin-top:12px"><div class="when">${T.rhy_bleed_title}</div>`+
   bleed.map(b=>`<p style="margin:4px 0 0">${T.rhy_bleed_line.replace(/{stem}/g,disp(b.stem)).replace(/{source}/g,disp(b.source)).replace("{band}",b.band_label).replace("{gap}",b.gap_db)}</p>`).join("")+`</div>`;}
 document.getElementById("rhySep").innerHTML=html;
})();

// Drum-breakdown panel cut in the declutter (v0.5.2): kick/snare/hat now live INSIDE
// the drums lane of the sequencer (kick at the bottom). D.drums still feeds that lane.

// ── Part D: transcribed-notes piano roll ──
(function(){
 const N=D.notes,P=document.getElementById("notePanel");
 if(!N||!N.notes||!N.notes.length){P.style.display="none";return;}
 const lo=N.pitch_min,hi=N.pitch_max,span=Math.max(1,hi-lo);
 // Route all stem labels through disp() (the resolved character name). For the "other" stem
 // (Demucs catch-all), disp() returns the character label (e.g. "lead"); add the extra hint
 // so the reader knows this is where the melody/chords live. See note_label_other / note_hint_other.
 const nlabel=disp(N.label);
 const nextra=N.label==="other"?(T.note_hint_other||""):"";
 document.getElementById("noteTitle").textContent=T.note_title.replace("{label}",nlabel);
 document.getElementById("noteHint").textContent=T.note_hint
  .replace("{label}",nlabel).replace("{lo}",noteName(lo)).replace("{hi}",noteName(hi)).replace("{n}",N.n_notes)+nextra;
 function noteName(p){const NM=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"];return NM[((p%12)+12)%12]+(Math.floor(p/12)-1);}
 const cv=document.getElementById("note"),ctx=cv.getContext("2d");
 const PADL=46,PADR=14,PADT=10,PADB=22;let W,H;const xOf=t=>PADL+(t/D.dur)*(W-PADL-PADR);
 const yOf=p=>PADT+(1-(p-lo)/span)*(H-PADT-PADB);
 // Pin a fixed height (like the other canvases). Reading clientHeight back into cv.height with
 // a width:100% canvas and no CSS height made the roll's height run away (260→…→900px). Set it.
 function resize(){W=cv.clientWidth;H=260;cv.style.height=H+"px";cv.width=W*devicePixelRatio;cv.height=H*devicePixelRatio;
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

// ── §B.13 INV-48: a card leads to ITS evidence ──
// Runs AFTER every panel-gating IIFE above, so "present" means what the eye can actually reach on this
// run's data. Scoped to #recs — the map-panel note cards reuse the .rec class but are NOT recs (CN-8).
// Click = seek (when timecoded) + open closed ancestor <details> + scroll + pulse the TARGET panel;
// the pulse stays a CSS/DOM class toggle, never a canvas edit (INV-34). A hidden/absent target degrades:
// timecoded cards keep the story arc (INV-48d), global cards stay inert (no pointer, no title, no click).
(function(){
 const present=id=>{const e=id?document.getElementById(id):null;
  return (e&&e.style.display!=="none")?e:null;};
 document.getElementById("recs").querySelectorAll(".rec").forEach(el=>{
  const tb=el.dataset.t!=null&&el.dataset.t!=="";
  let tgt=present(el.dataset.ev);
  if(!tgt){if(!tb)return;tgt=document.getElementById("storyPanel");}          // INV-48d
  if(!tb){el.style.cursor="pointer";el.title="Show the evidence";}            // INV-48e
  el.onclick=()=>{
   if(tb&&window.__seek)window.__seek(+el.dataset.t);
   // INV-48c: never land on a shut drawer — open every closed ancestor first (its toggle
   // listeners resize the canvases inside); nothing is persisted, the user can fold it back.
   for(let d=tgt.closest("details");d;d=d.parentElement?d.parentElement.closest("details"):null){if(!d.open)d.open=true;}
   tgt.scrollIntoView({behavior:"smooth",block:"start"});
   // INV-34: the attention pulse on the TARGET panel. Reflow reset lets repeat clicks re-fire it.
   tgt.classList.remove("pulse");void tgt.offsetWidth;tgt.classList.add("pulse");
   setTimeout(()=>tgt.classList.remove("pulse"),1200);};
 });
})();

// ── Part E: synced stem player ──
(function(){
 const PL=D.player,P=document.getElementById("playerControls");
 if(!PL||!PL.srcs||!PL.srcs.length){if(P)P.style.display="none";return;}
 const isMix=PL.kind==="mix";   // quick run: ONE mix source, transport only — no player lane grid
 const wrap=document.getElementById("playAudios");
 // Near-silent stems start MUTED (CR-2: they carry no real content — the listener should not be
 // surprised by silence on play, and they should be able to unmute/solo them deliberately).
 const _nsOmit=new Set((D.stem&&D.stem.omitted)||[]);
 const auds=PL.srcs.map(s=>{const a=new Audio();a.src=s.src;a.preload="auto";wrap.appendChild(a);
  const startMuted=_nsOmit.has(s.name);if(startMuted)a.muted=true;
  return {name:s.name,a:a,mute:startMuted,solo:false};});
 // Expose state for test_nearsilent_stems_appear_as_muted_lanes (INV-44)
 window.__ns_state=auds.map(s=>({name:s.name,mute:s.mute}));
 /* PLAYER_LOGIC_START — pure DOM-free player state machine (SPEC §B.14); node-executed by test_player_logic */
 const pgains=stems=>{const anySolo=stems.some(s=>s.solo);return stems.map(s=>anySolo?!s.solo:s.mute);};   // → muted[] per stem
 const toggleStem=(stems,i,kind)=>{const s=stems.map(x=>({mute:x.mute,solo:x.solo}));  // one mode at a time, across the whole player
  if(kind==="mute"){s[i].mute=!s[i].mute;if(s[i].mute)s.forEach(x=>x.solo=false);}
  else{s[i].solo=!s[i].solo;if(s[i].solo)s.forEach(x=>x.mute=false);}return s;};
 const seekResult=(t,dur,wasPlaying)=>{t=Math.max(0,Math.min(dur,t));return {t:t,resume:!!wasPlaying};};   // clamp + keep transport
 const resetMix=stems=>stems.map(()=>({mute:false,solo:false}));   // full mix — solo/mute is a Detailed-only capability (SPEC §B.14): leaving the stem grid (→ Simple) resets to full mix so you never strand a hidden solo
 if(typeof module!=="undefined")module.exports={pgains,toggleStem,seekResult,resetMix};
 /* PLAYER_LOGIC_END */
 const master=auds[0].a;
 const btn=document.getElementById("playBtn"),tEl=document.getElementById("playTime");
 btn.textContent=T.play_play;
 const dur=()=>master.duration||D.dur;
 let drawL=()=>{},lresize=()=>{};   // the player lane grid is built below in FULL mode only
 const PN=document.getElementById("playNote");
 if(isMix){   // mix player: hide the per-stem grid + its key; seeking happens via the charts (window.__seek)
  const sl=document.getElementById("stemlanes");if(sl)sl.style.display="none";
  const sk=document.getElementById("seqKey");if(sk)sk.style.display="none";
  if(PN)PN.textContent=T.play_note_mix||"";
 }else{
  if(PN)PN.textContent=T.play_note;
  buildStemGrid();
 }
 function buildStemGrid(){   // FULL only — everything stem-lane lives in here; drawL/lresize get assigned
 function gains(){const m=pgains(auds);
  auds.forEach((s,i)=>{s.a.muted=m[i];});drawL(lxOf(window.__pht||0));}  // keep the playhead put (SPEC §B.14: pgains resolves audibility)
 window.__resetMix=()=>{const r=resetMix(auds);auds.forEach((a,i)=>{a.mute=r[i].mute;a.solo=r[i].solo;});gains();};  // Simple hides the stem grid → reset to full mix so a hidden solo never strands you (SPEC §B.14)
 // ── sequencer lanes: one playable lane per stem, with mute/solo + envelope ──
 // Each lane bridges the Demucs stem to the real project part (from the stem map),
 // so the eye (arrangement = project groups) and the ear (these stems) stay connected.
 const FAMCOL={kick:"#ff5d73",bass:"#a78bfa",drums:"#4cc9f0",hats:"#5ad1c2",
               chord:"#46d39a",lead:"#ffd166",other:"#8b94a8"};
 const SM=D.stem,MAP=D.stemmap&&D.stemmap.stems;
 function bridge(name){const sm=MAP&&MAP[name];if(!sm)return{txt:"",col:null};
  // Empty verdict: the main label already carries the identified "(near-silent)" word via disp() —
  // returning "near-silent" here would duplicate it in the sub-line (s14 double-label bug class).
  if(sm.verdict==="empty")return{txt:"",col:null};
  // s14: the tiny sub-line shows the REAL PROJECT TRACK when the map is confident (e.g. "Guitar"),
  // never the raw Demucs name/family ("guitar · → other" was a salad of two Demucs words). Only when the
  // verdict is genuinely `clear` — otherwise nothing, no guessing.
  if(sm.verdict==="clear"){const t=(sm.track_matches&&sm.track_matches[0]&&sm.track_matches[0].track);
   if(t)return{txt:t,col:(FAMCOL[sm.best_family]||null)};}
  return{txt:"",col:null};}
 const BANDS=(SM&&SM.bands)||["sub","low","low_mid","mid","hi_mid","air"];
 const VIZ=SM&&SM.viz;   // fine-resolution drawing grid (~0.25 s), if present
 // CR-3: scale per-stem height/colour against an ABSOLUTE dB floor (a fixed reference: floor → 0 dBFS),
 // NOT each stem's own min/max. A quiet stem then stays low instead of stretching its loudest band up
 // to full — it renders as the near-silence it is, never as content. floor..0 dB → 0..1.
 const CFLOOR=(SM&&SM.colour_floor_db)||-60;
 function normEnv(a,bins){const rng=Math.max(6,0-CFLOOR);
  return{vals:a.map(x=>(x==null||x<=CFLOOR)?0:Math.max(0,Math.min(1,(x-CFLOOR)/rng))),bins:bins};}
 function volEnv(name){
  if(VIZ&&VIZ.bb&&VIZ.bb[name])return normEnv(VIZ.bb[name],VIZ.bins);   // fine
  if(SM&&SM.bb&&SM.bb[name]&&SM.time_bins)return normEnv(SM.bb[name],SM.time_bins); // 4 s
  if(MAP&&MAP[name]&&MAP[name].env)return{vals:MAP[name].env,bins:D.stemmap.bins};
  return null;}
 const lin=db=>(db==null||db<=CFLOOR)?0:Math.pow(10,db/10);  // dB → linear power, gated at the absolute floor (CR-3)
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
 // INV-STEMNAME-NEARSILENT-ID (s46) + CR-2: near-silent stems ARE shown as muted, labelled rows at
 // the bottom of the lane grid (they were there in 0.8.1, hidden in s45 — regression now fixed).
 // Their M/S buttons work; they start MUTED so the listener isn't surprised by silence on play.
 // They carry no real content (env/bands are null → flat faint line), honest per CR-2.
 // Their main label uses disp() (D.stem_display) — the identified label e.g. "mid (near-silent)".
 const OM_LN=new Set((D.stem&&D.stem.omitted)||[]);
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
 drawL=function(hx){if(!LW)return;lx.clearRect(0,0,LW,LH);
  const anySolo=auds.some(a=>a.solo);
  lanes.forEach(L=>{const active=anySolo?L.s.solo:!L.s.mute;
   lx.fillStyle="rgba(255,255,255,.02)";lx.fillRect(PADL,L.y,LW-PADL-PADR,L.h);
   box(3,L.y+3,L.s.mute,"#ff6b6b","M");box(3,L.y+L.h-15,L.s.solo,"#46d39a","S");
   // (g) lane label: ONE plain label per stem (s14, docs/SPEC.md §B.7). Always through disp()
   // (D.stem_display) — the ONE resolved name. For a significant stem this is the character label
   // ("bass", "lead", "mid"); for a near-silent stem it is the identified label ("mid (near-silent)")
   // — NEVER the bare "near-silent" (that erased which stem it was, the s45 regression).
   // NEVER the raw Demucs family word. The raw stem name still shows tiny below when the stemmap is
   // clear (G8 — so you know which file it is). Sub-line is suppressed when it would repeat the main label.
   const mainLbl=disp(L.name);
   lx.globalAlpha=active?1:.45;lx.fillStyle=active?getCss("--ink"):getCss("--muted");
   lx.font="600 9.5px sans-serif";lx.textAlign="left";if(!L.drum)lx.fillText(trunc(mainLbl),19,L.y+L.h/2+3);lx.globalAlpha=1;
   if(L.drum){drawDrum(L,active);}
   else if(L.env){drawWave(L,active);}
   else{ // near-silent / omitted stem (no envelope data, SPEC CR-2): a flat faint line on the baseline so
    // the lane reads as PRESENT-but-empty, not missing — the "purple line" restore (regression from 0.8.1).
    const base=L.y+L.h-2;lx.globalAlpha=active?.55:.28;lx.strokeStyle=L.col||"#a78bfa";lx.lineWidth=1.5;
    lx.beginPath();lx.moveTo(PADL,base);lx.lineTo(LW-PADR,base);lx.stroke();lx.globalAlpha=1;}
   // tiny sub-line: ONLY the real project track (map clear) — NEVER the raw Demucs name (s14:
   // "guitar · → other" was salad). Skip when it would repeat the main label to avoid a double-label.
   if(!L.drum&&L.br.txt&&L.br.txt!==mainLbl){lx.globalAlpha=active?.7:.35;
    lx.fillStyle=L.br.col||getCss("--muted");lx.font="8px sans-serif";lx.textAlign="left";lx.fillText(L.br.txt,PADL+4,L.y+9);lx.globalAlpha=1;}});
  drawLocators(lx,lxOf,LPT,LH-LPB,null);
  lx.fillStyle=getCss("--muted");lx.font="10px sans-serif";lx.textAlign="center";
  for(let t=0;t<=dur();t+=60)lx.fillText(fmtT(t),lxOf(t),LH-5);
  if(hx!=null){lx.strokeStyle="rgba(255,255,255,.6)";lx.lineWidth=1;lx.beginPath();lx.moveTo(hx,LPT);lx.lineTo(hx,LH-LPB);lx.stroke();}}
 lresize=function(){LW=lcv.clientWidth;LH=layout()+LPB;lcv.style.height=LH+"px";
  lcv.width=LW*devicePixelRatio;lcv.height=LH*devicePixelRatio;lx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);drawL();}
 lcv.addEventListener("click",e=>{const r=lcv.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;
  for(let i=0;i<lanes.length;i++){const L=lanes[i];
   // M and S are mutually exclusive — and across the WHOLE player: muting puts you in "mute mode"
   // (clears every solo), soloing puts you in "solo mode" (clears every mute). So you can never have a
   // mute on one stem AND a solo on another at the same time (2026-06-21: this is wrong).
   if(x>=3&&x<=15){const si=auds.indexOf(L.s),apply=k=>{const ns=toggleStem(auds,si,k);auds.forEach((a,j)=>{a.mute=ns[j].mute;a.solo=ns[j].solo;});gains();};
    if(y>=L.y+3&&y<=L.y+15){apply("mute");return;}        // SPEC §B.14: toggleStem keeps one mode at a time
    if(y>=L.y+L.h-15&&y<=L.y+L.h-3){apply("solo");return;}}}
  if(x>=PADL)seekTo(Math.max(0,Math.min(dur(),(x-PADL)/(LW-PADL-PADR)*dur())));});  // gutter clicks don't seek to 0
 window.addEventListener("resize",lresize);
 PH.push(t=>drawL(lxOf(t)));
 }  // ── end buildStemGrid (FULL only) ──
 function paint(t){window.__pht=t;
  tEl.textContent=fmtT(t)+" / "+fmtT(dur());PH.forEach(f=>f(t));}
 function loop(){if(!master.paused){paint(master.currentTime);requestAnimationFrame(loop);}}
 function play(){auds.forEach(s=>{s.a.currentTime=master.currentTime;});
  Promise.all(auds.map(s=>s.a.play())).catch(()=>{});
  btn.textContent=T.play_pause;requestAnimationFrame(loop);}
 function pause(){auds.forEach(s=>s.a.pause());btn.textContent=T.play_play;}
 btn.onclick=()=>{master.paused?play():pause();};
 const rew=document.getElementById("rewBtn");if(rew)rew.onclick=()=>seekTo(0);  // Ableton-style back-to-start
 function seekTo(t){const r=seekResult(t,dur(),!master.paused);  // SPEC §B.14: clamp + keep transport (a seek must NOT stop playback)
  auds.forEach(s=>{s.a.currentTime=r.t;});paint(r.t);
  if(r.resume)Promise.all(auds.map(s=>s.a.play())).catch(()=>{});}  // re-sync the stems + keep playing
 window.__seek=t=>{seekTo(t);};   // charts/lanes call this on click; the playhead line IS the seek UI
 master.addEventListener("ended",pause);
 master.addEventListener("loadedmetadata",()=>{paint(0);lresize();});
 paint(0);lresize();
})();
// A0 / INV-GATE (Fable audit 2026-07-03): each evidence sub-panel self-hides (display:none) when it
// has no data; the OUTER #evidence container did not, so a QUICK (mix-only) run — which structurally
// has no stems and no .als, hence NO arrangement/automation/map/rhythm/notes — showed an #evidence
// collapsible that opened to nothing. A quick run can never carry evidence, so hide the container in
// quick; a full run always carries evidence, so #evidence stays (its always-visible contract holds).
(function(){var ev=document.getElementById("evidence");if(!ev)return;
 var badge=document.getElementById("modeBadge");
 if(badge&&badge.classList.contains("quick")){ev.style.display="none";}})();
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
    p.add_argument("--audio-mix-rel", default=None,
                   help="directory (relative to the output HTML) holding a single mix audio file "
                        "(e.g. 'mix_web'). Used by QUICK runs that have no stems — gives a single-track "
                        "player (transport + seek). Ignored when --audio-stems-rel has stems.")
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
    p.add_argument("--mode", default="full", choices=["quick", "full"],
                   help="run mode — sets the header label (full→'deep mode', quick→'quick read')")
    p.add_argument("--title", default=None)
    p.add_argument("--strings", default=None, help="JSON file overriding the English text (any language)")
    p.add_argument("--dump-strings", action="store_true", help="print the canonical English strings JSON and exit")
    p.add_argument("--verdict", default=None,
                   help="1–2 sentence headline shown at the top of the Simple view. "
                        "If omitted, the first sentences of the --narrative are used.")
    p.add_argument("--src-audio", default=None, help="source audio filename, shown in the widget header/footer")
    p.add_argument("--src-als", default=None, help="source .als filename, shown in the widget header/footer")
    p.add_argument("--track-version", default=None, help="the track's own version label (e.g. v0.6.2)")
    p.add_argument("--analyzed-at", default=None, help="ISO timestamp of this run (defaults to now)")
    p.add_argument("--catalog", default=None,
                   help="catalog.json from run_dir.py — embeds the all-tracks/all-versions index "
                        "(collapsible, with past verdicts + relative links) at the bottom of the widget")
    p.add_argument("--back-href", default=None,
                   help="URL of the library index page — wires the ← Library back button")
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
    # CR-6: per-stem self-similarity — discover result_selfsim_<stem>.json beside the mix self-sim (the
    # pipeline writes one per SIGNIFICANT stem). stem_repetition() re-checks significance, so a stray
    # file for an insignificant stem is ignored.
    per_stem_selfsim = {}
    if args.selfsim:
        for p in Path(args.selfsim).resolve().parent.glob("result_selfsim_*.json"):
            try:
                per_stem_selfsim[p.stem.replace("result_selfsim_", "")] = json.loads(p.read_text())
            except Exception:
                pass
    # G13: per-stem notes — discover result_notes_<stem>.json beside --notes (or --masking), one per
    # SIGNIFICANT non-drum stem (the pipeline writes them). Feeds polyphony → melody/chord/pad split.
    # stem_character only reads the significant stems, so a stray file is harmless.
    per_stem_notes = {}
    _notes_dir = next((Path(a).resolve().parent for a in (args.notes, args.masking, args.selfsim) if a), None)
    if _notes_dir:
        for p in _notes_dir.glob("result_notes_*.json"):
            try:
                per_stem_notes[p.stem.replace("result_notes_", "")] = json.loads(p.read_text())
            except Exception:
                pass
    # §B.11: per-stem CORE measurements — discover result_core_<stem>.json beside --core (one per
    # SIGNIFICANT stem; the glob excludes the mix's result_core.json, which has no _<stem> suffix).
    # Missing files → no per-stem cards, no error (CR-1 back-compat).
    per_stem_core = {}
    _core_dir = next((Path(a).resolve().parent for a in (args.core, args.masking, args.selfsim) if a), None)
    if _core_dir:
        for p in _core_dir.glob("result_core_*.json"):
            try:
                per_stem_core[p.stem.replace("result_core_", "")] = json.loads(p.read_text())
            except Exception:
                pass
    narrative_md = Path(args.narrative).read_text(encoding="utf-8") if args.narrative else None
    from datetime import datetime
    _now = datetime.now()
    # C19: derive analysis date from the run-dir name (format YYYY-MM-DD_HHMM) when --analyzed-at
    # is not passed explicitly. This ensures the widget shows when the analysis actually ran, not
    # when the report was built (which can be days later on a re-render).
    _run_dir_name = Path(args.out).parent.name
    _run_date = None
    _rdm = re.match(r"^(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})$", _run_dir_name)
    if _rdm:
        _run_date = f"{_rdm.group(1)} {_rdm.group(2)}:{_rdm.group(3)}"
    meta = {
        "audio": args.src_audio,
        "als": args.src_als,
        "track_version": args.track_version,
        "analyzed_at": args.analyzed_at or _run_date or _now.strftime("%Y-%m-%d %H:%M"),
        "built_at": _now.strftime("%Y-%m-%d"),
    }
    catalog = json.loads(Path(args.catalog).read_text()) if args.catalog and Path(args.catalog).exists() else None
    # Derive run_dir from --core so the reference-read block can load the fingerprint (§D.10.3).
    run_dir = str(Path(args.core).resolve().parent) if args.core else None
    build_html(core, detail, masking, als, args.out, args.title, S,
               als_offset_s=args.als_offset_s, stemmap=stemmap, rhythm=rhythm, notes=notes, drums=drums,
               audio_stems_rel=args.audio_stems_rel, presence_threshold=args.presence_threshold,
               narrative_md=narrative_md, selfsim=selfsim, meta=meta, verdict=args.verdict, catalog=catalog,
               mode=args.mode, back_href=args.back_href, audio_mix_rel=args.audio_mix_rel,
               per_stem_selfsim=per_stem_selfsim or None, per_stem_notes=per_stem_notes or None,
               per_stem_core=per_stem_core or None, run_dir=run_dir)
    # Record this run's verdict back into run_meta.json + index.json so FUTURE catalogs
    # can show this version's verdict alongside the others. Best-effort, never fatal.
    try:
        _record_history(Path(args.out), _verdict_text(args.verdict, narrative_md))
    except Exception as e:
        print(f"(history update skipped: {e})")


def _record_history(out_path, verdict):
    out_dir = out_path.resolve().parent
    widget = out_path.name
    rm = out_dir / "run_meta.json"
    if rm.exists():
        meta = json.loads(rm.read_text())
        meta["verdict"] = verdict or meta.get("verdict", "")
        meta["widget"] = widget
        rm.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    idx_path = out_dir.parent.parent / "index.json"  # base/<slug>/<run>/  → base/index.json
    if not idx_path.exists():
        return
    idx = json.loads(idx_path.read_text())
    for e in idx.get("runs", []) + ([idx["latest"]] if idx.get("latest") else []):
        if not isinstance(e, dict):  # legacy index could hold a bare slug string — skip it
            continue
        if Path(e.get("run_dir", "")).resolve() == out_dir:
            e["verdict"] = verdict or e.get("verdict", "")
            e["widget"] = widget
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
