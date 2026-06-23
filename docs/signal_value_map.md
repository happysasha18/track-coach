# Why the analysis (the "starship" map) — signals × combinations → user value

Sasha's challenge (2026-06-23): *"если там 5 сигналов и в результате 10 рекомендаций, то о чём это всё?
зачем весь звездолёт? чтобы просто очевидные сигналы ко времени привязать?"*

This maps every recommendation the tool actually produces back to the signal(s) behind it, and sorts them
by **how much the combination adds** over reading one meter. Grounded in the real rec keys
(`build_widget.py` REC_CLASS + per-stem cards) and the real rendered advice on Lazy / Shared / Wobble.

## The raw signals we measure (≈ the inputs)
Mix: tempo · key · LUFS · true-peak · dynamic range · stereo width · phase · 9-band tonal balance ·
energy curve · brightness curve · density curve · modulation (LFO) rate · structure / self-similarity
(sections, intro↔outro) · groove / swing · climax & breakdown location.
Per separated part (×6 stems): energy · density · stereo · dynamic range · brightness · character
(kick/bass/lead/chord/melody/perc) · prominence · repetition · frequency spectrum & masking clashes · leakage.
Project (.als): tracks · MIDI notes · audio clips · **automation envelopes** · locators.
Cross: stem ↔ project-track map · automation **intention vs measured result**.

## Tier A — single signal + words ("a meter with a sentence"). The OBVIOUS tier.
One number crosses a threshold → a templated sentence. A standard meter/trained ear gives these too.
This is where the "same recs across tracks" / "just timestamp the obvious" feeling lives.

| Rec | Signal(s) | Why it's thin |
|---|---|---|
| Master peaks over 0 (clipping) | true-peak | one number, universal advice |
| No overall rise & fall | energy trend | one curve's slope |
| Groove swings X ms | swing | one number; sentence identical every track |
| Modulation stays put | modulation-rate trend | one number |
| A part is "more compressed" | that part's dynamic range | one number (the lone-number risk Sasha named) |
| Tonal resonance / a band sticks out | tonal balance | one band vs the rest |

→ **These don't justify the starship.** Keep them as a checklist, but they must be made RELATIVE
("192 ms vs ~25 on a tight grid") and ideally folded into a combination, or they read as filler.

## Tier B — COMBINATIONS no single signal can give. THIS is the starship.
Two-plus signals fused into one precise, actionable, non-obvious statement.

| Rec | Signals fused | What the combo buys (a meter can't) |
|---|---|---|
| "The bass buries the **lead** around **≈290 Hz**, ~50% of the track, worst **4:50**" | separation × per-stem spectrum × time-overlap × **character** (which part is the lead) | the exact culprit, the exact frequency, the exact moment, named in your terms — a precise EQ move |
| "After **2:53** nothing new — the last 49% recombines" | structure/self-similarity × novelty-over-time × duration | *where the track stops developing* — invisible to any single meter |
| "The **bass** carries the development while the lead & drums loop" | per-part repetition × character map | which part to vary / which is doing the work |
| "A new element (**melody**) enters at **4:54**" | per-stem onset × level gate × character | a finale accent vs a stray tail — judged, not just detected |
| "Climax arrives **late** (82%)" | energy-peak location × structure × length | arrangement timing, not loudness |
| **"You drew the filter to stop at 2:45 but brightness keeps rising to 3:10"** | **.als automation envelope × measured brightness** | intention vs result — connects what you DREW to what you HEAR. Nobody else has this. |

→ **The .als / intention-vs-result row is the crown jewel** — the one signal no other tool on earth has,
because it reads your actual Ableton project against the rendered sound.

## Tier C — per-part cards (one signal × the SEPARATION). The middle.
"The drums are narrower / the bass is more dynamic than the rest." Each is one axis, but applied to a
*separated part vs the others* — so the value is signal × Demucs separation: it turns a mix-level number
into "**which** part is the outlier." Specific, per-track — this is the work that made the 3 tracks read
differently (verified: most distinct advice-types are these + Tier B, not Tier A).

## The honest answer to "зачем звездолёт"
- If the tool only shipped **Tier A**, Sasha would be right — it'd be a meter with sentences.
- The justification is **Tier B + C**: separation + character + structure + the .als let us say things a
  meter physically cannot ("bass buries the *lead* at 290 Hz at 4:50", "you drew it to stop but it doesn't").
- **So the next investment isn't more lone-number cards — it's more COMBINATIONS**, especially anything
  that pulls in the **.als/project** signal (the uncopyable asset), and making Tier A cards relative or
  merging them into combinations so nothing reads as filler.

This map also IS the source for the card-evidence feature: a card's "where it came from" line should name
its tier-B fusion ("bass × lead × 290 Hz × 4:50"), not a lone "dynamics 30.7".

## The split that matters most to Sasha (2026-06-23): TECHNICAL vs ARTISTIC
Sasha: *"есть технические штуки 'бас перекрывает лид', а есть художественные… художественное мышление,
понимаешь?"* The technical tier is mix engineering; the ARTISTIC tier is composition — and it's the soul.

**Artistic advice we ALREADY ship (credit where due — Sasha gave these):**
- Development — *what carries it vs what loops* (`stem_evolves`), *where new ideas stop* (`plateau`),
  *develops only via brightness* (`brightness`).
- Arc / journey — *climax timing* (`climax`), *ends like it starts* (`endpoint`), *no overall rise & fall*
  (`energy_flat`).
- Dynamics — *the breakdown / dip* (`breakdown`), macro (`energy_flat`) + micro/transients (`squashed`).
- Events — *a new element enters at the end* (`late_entry`).
- Movement — *modulation stays put* (`wobble`).

**Why some went stale (Sasha: "потом это стало шаблонно"):** they fire as FIXED-template sentences — e.g.
breakdown always says "the only one in the whole track", swing always says the same line. The data differs
per track, the FRAMING is canned, so it reads identical. Artistic cards need the same relative/contextual
treatment as everything else — speak the shape of THIS track, contrast it, don't recite a template.

**The artistic GAPS Sasha wants ("было бы прикольно") — mapped to what we can compute:**
| Idea (Sasha's words) | Have it? | What it'd take |
|---|---|---|
| **Which FORM development takes** — by density / by opening the filter / by widening stereo / by frequency range | partial — `brightness` is ONE mode | generalize: we already track density, stereo, brightness, range over time → name the dominant mode(s) and the absent ones ("you grow by brightness, barely by stereo — try widening") |
| **Contrast vs gradient between scenes** — hard cut or smooth morph at each boundary | ❌ no | self-similarity gives the boundaries; measure how FAST the signals jump across each → label sharp-cut vs gradient |
| **Interest / boredom as a curve over time** (not only the end) | partial — `plateau` (end), `long_section` (one stretch) | a per-stretch "is it still evolving here?" read across the whole track, not just the tail |
| **Valley → drop arc quality** (does a drop earn its hit) | partial — `breakdown`, drop detection | combine: a drop with NO real dip before it → "it won't land"; a dip→lift → "this one hits" |
| **Macro vs micro dynamics** as a pair | ✅ `energy_flat` + `squashed` | could be voiced together as one dynamics story |
| **Consonance / dissonance development** (harmonic tension) | ❌ no | needs note/chord analysis (basic-pitch exists) — ambitious, park it |

→ The richest, most uniquely-artistic next moves: **name the MODE of development**, and **contrast-vs-gradient
between scenes**. Both reuse signals we already have; both are "художественное мышление", not a meter.

## First artistic probe, VALIDATED across 4 tracks (2026-06-23) — "effort × felt-movement"
Sasha's example: *"смотришь что слышно, а там дофига автоматизаций, а на выходе ноль динамики."* We read each
project's `.als` automations, split them MACRO (volume/filter/gain = the big arc) vs MICRO (sends/timbre/
color/mod), and paired the split with the OUTPUT movement (energy/brightness/density/stereo trend). To check
Sasha's templating worry, ran it on 4 of his tracks (Lazy, Shared, Wobble all full; **Heater** added cheaply
= parse_als + analyze_core only, no Demucs — quick run dir `…/Heater_Live12 Project/track-coach-output/
_quick_effort`, audio v0.22 + Heater_Live12.1.als):

| Track | autos | macro share | output movement | one-line story |
|---|---|---|---|---|
| Lazy | 95 | 15% | loud +0.19, bright +0.13 | micro-heavy, but the loudness arc DOES build |
| Shared | 35 | 9% | density +0.10, stereo −0.11 | barely automated, yet develops — by getting busier + tightening the image |
| Wobble | 99 | 13% | bright +0.16, loud −0.03 | tons of detail automation, flat loudness, opens only in brightness |
| Heater | 42 | 14% | loud +0.14, bright +0.18, stereo −0.24, **+1 meter change** | really opens up (loud+bright) while the image narrows hard |

**Result = NOT templated** — four distinct stories. **Bonus cross-track fingerprint (a real observation about
Sasha as a producer):** macro share 9–15% on ALL four — he automates DETAIL ≫ the big arc, consistently.
**Design lesson:** the effort-split ALONE would template (it's his stable style); the non-templated value is
the FUSION "where the effort goes × which FORM the output develops in", phrased per-track. That fusion is the
shape of the first artistic card. (Heater also surfaced a real time-signature change → the "meter" dimension
is live in his music.)
