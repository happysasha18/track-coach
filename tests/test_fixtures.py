#!/usr/bin/env python3
"""GOLDEN-render tests on real committed fixtures (`tests/fixtures/`).

The synthetic fixtures in the other suites prove the mechanics; these prove the skill survives REAL
analysis data end-of-pipeline. We render a widget straight from a real `result_core.json` + the model's
`narrative.md` (derived numbers + prose — no music) for both a quick read (Fragile) and a full run
(Shared Memories), and assert the session-10 invariants on the SHIPPED output. Pure stdlib (build_widget
has no deps), so it runs anywhere `python3 -m unittest` does.

Decided with Sasha (session 10): commit light artifacts (JSON + read) + one tiny synthetic clip; never
the audio. See docs/TEST_MATRIX.md.
"""
import json
import re
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_widget  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def _render(track_dir, *, mode):
    """Render a widget from a fixture's real core + narrative; return (html, payload)."""
    core = json.loads((FIX / track_dir / "result_core.json").read_text())
    narr = (FIX / track_dir / "narrative.md").read_text()
    out = Path(tempfile.mkdtemp(prefix="tc_fix_")) / "w.html"
    build_widget.build_html(core, {}, None, None, str(out), None, build_widget.STRINGS,
                            mode=mode, narrative_md=narr)
    html = out.read_text(encoding="utf-8")
    payload, _ = json.JSONDecoder().raw_decode(html.split("const D=", 1)[1])
    return html, payload


class GoldenRenderFromRealData(unittest.TestCase):
    """Render real Fragile (quick) + Shared Memories (full) and check the invariants hold on real data."""

    @classmethod
    def setUpClass(cls):
        cls.q_html, cls.q = _render("fragile", mode="quick")
        cls.f_html, cls.f = _render("shared_memories", mode="full")
        cls.q_dur = json.loads((FIX / "fragile" / "result_core.json").read_text())["duration_s"]
        cls.f_dur = json.loads((FIX / "shared_memories" / "result_core.json").read_text())["duration_s"]

    def test_read_renders_server_side_without_a_literal_hash(self):  # INV-1 / INV-2
        for html in (self.q_html, self.f_html):
            body = re.search(r'<div id="readBody">(.*?)</div>', html, re.S).group(1)
            self.assertTrue(body.strip(), "read did not render into #readBody")
            self.assertNotIn("<p>#", body, "a literal '#' leaked into the real read")
            self.assertIn("<h3>", body, "the real read lost its headings")

    def test_structure_bar_is_tidy_on_real_data(self):  # INV-5
        for label, payload, dur in (("quick", self.q, self.q_dur), ("full", self.f, self.f_dur)):
            scenes = payload["story"]["scenes"]
            self.assertTrue(scenes, f"{label}: no scenes")
            for i in range(1, len(scenes)):
                self.assertEqual(scenes[i]["t0"], scenes[i - 1]["t1"], f"{label}: bar has a gap")
                self.assertNotEqual(scenes[i]["letter"], scenes[i - 1]["letter"],
                                    f"{label}: adjacent same-letter sliver survived")
            self.assertEqual(scenes[0]["t0"], 0.0, f"{label}: bar must start at 0")
            self.assertAlmostEqual(scenes[-1]["t1"], dur, delta=0.5, msg=f"{label}: bar must span the track")

    def test_quick_has_hint_full_has_toggle(self):  # INV-3
        self.assertIn('<div class="viewhint" id="viewToggle">', self.q_html, "quick lost its hint")
        self.assertNotIn('<div class="viewtoggle" id="viewToggle">', self.q_html, "quick grew a toggle")
        self.assertIn('<div class="viewtoggle" id="viewToggle"></div>', self.f_html, "full lost its toggle")

    def test_all_five_story_curves_present(self):
        for payload in (self.q, self.f):
            comps = {c["key"] for c in payload["story"]["components"]}
            self.assertEqual(comps, {"energy", "brightness", "density", "modulation", "stereo"})

    def test_every_card_carries_a_based_on_line(self):  # INV-31 (SPEC §B.13) — card evidence
        for label, payload, html in (("quick", self.q, self.q_html), ("full", self.f, self.f_html)):
            recs = payload["recs"]
            self.assertTrue(recs, f"{label}: no recs on real data to check")
            for r in recs:
                self.assertTrue(r.get("based", "").strip(),
                                f"{label}: card {r['h']!r} has an empty based-on line")
                # never a bare metric identifier as the whole line
                self.assertNotRegex(r["based"], r"^[a-z_]+$",
                                    f"{label}: card {r['h']!r} based-on is a bare tag")
            self.assertIn('class="based"', html, f"{label}: based-on line did not render")

    def test_develop_mode_line_leads_the_read_when_the_track_develops(self):  # INV-32 (SPEC §B.12)
        # Shared Memories develops (density up + image tightens) → the read leads with the observation,
        # carrying DIRECTION (tightens, not widens).
        self.assertIn('class="readdev"', self.f_html, "developing track lost its 'how it develops' line")
        dev = re.search(r'<p class="readdev">(.*?)</p>', self.f_html, re.S).group(1)
        self.assertIn("How it develops", dev)
        self.assertIn("tightens the image", dev)   # stereo trend is negative — direction matters (F1)

    def test_develop_line_shows_even_without_an_authored_read(self):  # §B.12 — Demucs run, no narrative
        core = json.loads((FIX / "shared_memories" / "result_core.json").read_text())
        out = Path(tempfile.mkdtemp(prefix="tc_nonarr_")) / "w.html"
        build_widget.build_html(core, {}, None, None, str(out), None, build_widget.STRINGS,
                                mode="full", narrative_md=None)   # NO read authored
        html = out.read_text(encoding="utf-8")
        self.assertIn('class="readdev"', html, "dev line vanished when there was no narrative")
        self.assertNotIn('id="readPanel" style="display:none"', html, "read panel hid despite a dev line")


class SyntheticClipIntegrity(unittest.TestCase):
    """The committed synthetic clip is the seed for the analyze→json smoke test (run in the full uv env).
    Here we just guard it's a valid, tiny, mono 16-bit wav so it can't rot in the repo."""

    def test_clip_is_a_small_mono_wav(self):
        clip = FIX / "synthetic" / "sine_220hz_1s.wav"
        self.assertTrue(clip.exists(), "the synthetic smoke-test clip is missing")
        self.assertLess(clip.stat().st_size, 200_000, "the synthetic clip must stay tiny")
        with wave.open(str(clip), "rb") as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertGreater(w.getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
