#!/usr/bin/env python3
"""Heuristic mood/style tag deriver tests (scripts/tags.py).

The tags are a deterministic DRAFT (valence–arousal model) the agent later overrides. We pin the
quadrant logic + energy level so a refactor can't silently change what a track gets tagged. Pure,
no deps.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import tags  # noqa: E402


def core(energy_mean, brightness_mean, key, tempo, wobble=0.0):
    """Build a minimal core dict with flat energy/brightness curves at the given means."""
    return {"energy": [energy_mean] * 8, "brightness": [brightness_mean] * 8,
            "tempo": tempo, "vitals": {"key": key, "tempo_bpm": tempo},
            "wobble_rate_median_hz": wobble}


class EnergyLevel(unittest.TestCase):
    def test_scales_1_to_10(self):
        self.assertEqual(tags.energy_level({"energy": [0.0]}), 1)
        self.assertEqual(tags.energy_level({"energy": [1.0]}), 10)
        self.assertEqual(tags.energy_level({"energy": [0.669] * 5}), 7)  # Shared Memories

    def test_missing_energy_is_midpoint(self):
        self.assertEqual(tags.energy_level({}), 5)  # mean 0.5 → round(4.5)=4 (banker's) +1


class MoodQuadrant(unittest.TestCase):
    def test_dark_driving_minor_high_energy(self):
        t = tags.derive_tags(core(0.7, 0.55, "E minor", 123))
        self.assertEqual(t["mood_tags"], ["dark", "driving"])

    def test_energetic_uplifting_major_high(self):
        t = tags.derive_tags(core(0.85, 0.85, "C major", 130))
        self.assertEqual(t["mood_tags"], ["energetic", "uplifting"])

    def test_calm_minor_is_melancholic(self):
        t = tags.derive_tags(core(0.1, 0.3, "A minor", 70))
        self.assertEqual(t["mood_tags"], ["melancholic"])

    def test_calm_major_is_dreamy(self):
        t = tags.derive_tags(core(0.1, 0.9, "G major", 70))
        self.assertEqual(t["mood_tags"], ["dreamy"])


class StyleHint(unittest.TestCase):
    def test_tempo_bands(self):
        self.assertEqual(tags.derive_tags(core(0.5, 0.5, "C major", 90))["style_tags"], ["downtempo"])
        self.assertEqual(tags.derive_tags(core(0.5, 0.5, "C major", 123))["style_tags"], ["house/club"])
        self.assertEqual(tags.derive_tags(core(0.5, 0.5, "C major", 140))["style_tags"], ["techno/uptempo"])
        self.assertEqual(tags.derive_tags(core(0.5, 0.5, "C major", 174))["style_tags"], ["fast/dnb-ish"])

    def test_wobble_adds_bass_hint(self):
        self.assertIn("bass/wobble", tags.derive_tags(core(0.5, 0.5, "C major", 140, wobble=2.5))["style_tags"])


class ModelBounds(unittest.TestCase):
    def test_valence_arousal_in_unit_range(self):
        m = tags.derive_tags(core(2.0, 2.0, "E minor", 999))["_model"]  # extreme inputs clamp
        self.assertTrue(0.0 <= m["arousal"] <= 1.0)
        self.assertTrue(0.0 <= m["valence"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
