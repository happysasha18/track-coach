#!/usr/bin/env python3
"""Render-offset resolution tests — every fallback case.

The render offset is where (in project seconds) the audio starts, used to align the .als
arrangement to the audio. Resolution order (track_analyzer.default_render_offset → (seconds, source)):
  1) earliest locator ("first_locator");  2) if none, earliest clip ("earliest_clip");  3) (None, None).
Pure-function tests on small inline .als-result JSON — no audio, no deps, instant.
"""
import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from track_analyzer import default_render_offset  # noqa: E402


def offset_for(doc):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(doc, f)
        p = Path(f.name)
    try:
        return default_render_offset(p)
    finally:
        p.unlink()


class OffsetResolution(unittest.TestCase):
    def test_earliest_locator_wins_even_when_unordered(self):
        doc = {"markers": [{"name": "B", "time_s": 23.61},
                           {"name": "A", "time_s": 7.87},
                           {"name": "C", "time_s": 39.34}],
               "tracks": []}
        self.assertEqual(offset_for(doc), (7.87, "first_locator"))

    def test_locator_beats_clips(self):
        # a locator exists, so clip starts are ignored even if a clip starts earlier
        doc = {"markers": [{"name": "A", "time_s": 10.0}],
               "tracks": [{"audio_clips": [{"start_s": 2.0}], "midi_clips": []}]}
        self.assertEqual(offset_for(doc), (10.0, "first_locator"))

    def test_no_locators_falls_back_to_earliest_clip(self):
        doc = {"markers": [],
               "tracks": [{"audio_clips": [{"start_s": 100.08}], "midi_clips": []},
                          {"audio_clips": [{"start_s": 7.87}], "midi_clips": []},
                          {"audio_clips": [], "midi_clips": [{"start_s": 23.61}]}]}
        self.assertEqual(offset_for(doc), (7.87, "earliest_clip"))

    def test_clip_fallback_considers_midi_too(self):
        doc = {"markers": [],
               "tracks": [{"audio_clips": [{"start_s": 50.0}], "midi_clips": [{"start_s": 4.5}]}]}
        self.assertEqual(offset_for(doc), (4.5, "earliest_clip"))

    def test_none_when_no_locators_and_no_clips(self):
        self.assertEqual(offset_for({"markers": [], "tracks": [{"audio_clips": [], "midi_clips": []}]}),
                         (None, None))

    def test_none_on_empty_doc(self):
        self.assertEqual(offset_for({}), (None, None))

    def test_ignores_malformed_entries(self):
        doc = {"markers": [{"name": "x"}, {"name": "y", "time_s": "oops"}],  # no usable time
               "tracks": [{"audio_clips": [{"start_s": None}, {"start_s": 12.0}], "midi_clips": []}]}
        self.assertEqual(offset_for(doc), (12.0, "earliest_clip"))

    def test_missing_file_returns_none(self):
        self.assertEqual(default_render_offset(Path("/no/such/file.json")), (None, None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
