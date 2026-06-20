## What this track is

An **instrumental, hypnotic world-electronica loop** — E minor, **123 BPM, 4/4, 5:38 long**.
It doesn't run on a build-and-drop; it runs on **repetition and slow accumulation**. The
clearest tell is in the arcs: loudness is essentially flat across the whole track (energy
trend +0.04) and so is brightness (+0.011), but **density keeps climbing (+0.15)** — more
events pile up over time. And the **end is spectrally almost identical to the start**
(endpoint cosine 0.9956). So it loops and lingers like a memory rather than telling a story
start-to-finish — the title fits the music.

## The shape, scene by scene

From the audio's own self-similarity the form is **A · B · C · B · C · D · C · D · C · B** —
i.e. it's carried by two recurring rooms (**B** and **C**) with a **D** variation that comes
back twice:

- **Intro — A (0:00–0:16).** Short statement of the motif before the groove settles.
- **First body — B/C (0:16–1:30).** The main hypnotic pocket establishes; section edges the
  analyser marks at ~0:31 and ~1:35.
- **D variations (2:21–2:53 and 4:11–4:40).** The two moments where the track actually
  *changes its mind* — these are your real contrast points. Everything between them is **C**
  (2:53–4:11 is one long C), the longest single stretch in the track.
- **Return to B (5:13–end).** It closes back on the opening room — consistent with the
  near-1.0 endpoint similarity.

The honest read: **C dominates the back half.** If this is meant purely as a hypnotic
loop, that's the point and it works. If it's meant to *travel*, the stretch from ~2:53 to
~4:11 is the place a listener's attention can drift — one more genuine lift or a short
breakdown there would earn the length.

## The mix, in one glance

This is a **clean, dynamic, breathing master** — the opposite of a loudness-war print:

- **−12.9 LUFS with DR 14.5** — quiet and very dynamic. There's real headroom and movement;
  nothing is crushed.
- **True peak sits under 0 dBTP** — no inter-sample clipping. Safe for lossy codecs.
- **Phase correlation 0.88, stereo width 0.32** — mono-safe, moderately wide. The low end
  won't cancel on a mono club rig.
- **Tonal balance** leans **warm and intimate**: a gentle **+2.7 dB bump at 60–120 Hz**
  (body/low-warmth), the **sub (20–60 Hz) a touch light (−2.5)**, and **air rolled off
  above 8 kHz (−3.0)**. Nothing wrong — it reads as a deliberate, slightly dark, cosy
  tone. Whether you want more sparkle on top or more sub weight under the kick is a taste call.

## On the separation (so you trust the rest)

The stems split **cleanly** — they sum back to the mix at −27.5 dB residual, so nothing's
missing. But the **stem→project mapping came back humble** (`nomatch`/`mixed`): this is a
dense, overlapping arrangement where everything plays at once, and the correlation method
honestly won't claim a match it can't prove. Two things to know so you read the lanes right:

- **`piano` and `vocals` stems are empty.** It's an instrumental, and Demucs put the melodic
  material into **`other`** (and some into `guitar`) rather than its own piano lane. So any
  "masking" flag against the vocals/piano stems is an artifact of a near-silent stem — **ignore
  those**, they're not real conflicts.
- **The melodic `other` stem is 0% masked by the bass** — the lead/keys sit in clear air, not
  buried. The only real low-frequency sharing is **kick↔bass in the sub (~22% of windows)**,
  which is normal for this kind of track.

## The few things worth your attention (your call, not orders)

- **Length vs. lift.** 5:38 with an almost-flat energy arc (+0.04) and C as the dominant
  recurring room. Beautiful as a hypnotic piece; if you want it to build, the long C at
  **2:53–4:11** is where a second D-style variation or a real breakdown would pay off most.
- **Air above 8 kHz is down ~3 dB.** If the lead/violins feel a touch veiled, a gentle high
  shelf would open them — but the dark tone may be intentional for the mood.
- **Sub (20–60 Hz) is light.** On a big system you might want a little more weight under the
  kick; on headphones it's already balanced. Taste, not a fault.
- **It's built to loop** (endpoint cosine 0.9956). Begins and ends on the same texture by
  design — perfect for the title, just worth knowing if you ever want a hard ending.

*A measurement note:* tempo came back **123 BPM, E minor, 4/4** (steady, no metre changes).
The `.als` (Shared_Memories_Live_12.2) gave the arrangement/automation ground truth; the
stem lanes are Demucs approximations of it, so when the two disagree, trust the project.
