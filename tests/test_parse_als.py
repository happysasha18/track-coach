"""Tests for parse_als.py — time-signature automation decoding.

Two groups:
  TimeSigDecoder   — unit tests for _decode_ts_enum; fast, no file I/O.
  FragileMeterChanges — disk-gated integration test; skipped when the .als is absent
                        (CI-safe, mirrors the Lazy Sparks pattern in test_reference_read.py).

Ground truth (from Alexander's Ableton screenshot):
  Fragile_Live12.1.1_minimal.als metre changes around bars 369-392:
  9/16 → 13/8 → 13/8 → 4/4
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import parse_als  # noqa: E402

# Disk path — skipped in CI/other machines where the file is absent
FRAGILE_MINIMAL = (
    Path.home()
    / "Desktop/Projects/Fragile_Live12.1.1 Project/Fragile_Live12.1.1_minimal.als"
)


class TimeSigDecoder(unittest.TestCase):
    """Unit tests for _decode_ts_enum — synthetic values, no file I/O.

    Encoding: value = log2(den) * 99 + (num - 1)
    Verified against Fragile ground truth (201=4/4, 309=13/8, 404=9/16).
    """

    def test_4_4(self):
        """201 must decode to 4/4 (project default in Fragile)."""
        self.assertEqual(parse_als._decode_ts_enum(201), "4/4")

    def test_13_8(self):
        """309 must decode to 13/8 (ground-truth metre change in Fragile)."""
        self.assertEqual(parse_als._decode_ts_enum(309), "13/8")

    def test_9_16(self):
        """404 must decode to 9/16 (ground-truth metre change in Fragile)."""
        self.assertEqual(parse_als._decode_ts_enum(404), "9/16")

    def test_3_4(self):
        """3/4: log2(4)=2, (3-1)=2 → 2*99+2=200."""
        self.assertEqual(parse_als._decode_ts_enum(200), "3/4")

    def test_7_8(self):
        """7/8: log2(8)=3, (7-1)=6 → 3*99+6=303."""
        self.assertEqual(parse_als._decode_ts_enum(303), "7/8")

    def test_1_4(self):
        """1/4: log2(4)=2, (1-1)=0 → 2*99+0=198."""
        self.assertEqual(parse_als._decode_ts_enum(198), "1/4")

    def test_4_1(self):
        """4/1: log2(1)=0, (4-1)=3 → 0*99+3=3."""
        self.assertEqual(parse_als._decode_ts_enum(3), "4/1")

    def test_roundtrip_various(self):
        """Encode then decode must be identity for representative cases."""
        import math
        cases = [
            (4, 4), (3, 4), (7, 8), (9, 16), (13, 8), (6, 8), (5, 4), (11, 16),
        ]
        for num, den in cases:
            den_idx = int(math.log2(den))
            value = den_idx * 99 + (num - 1)
            self.assertEqual(
                parse_als._decode_ts_enum(value), f"{num}/{den}",
                f"round-trip failed for {num}/{den} (value={value})",
            )


@unittest.skipUnless(
    FRAGILE_MINIMAL.exists(),
    "Fragile_Live12.1.1_minimal.als not on this machine — disk-gated test skipped",
)
class FragileMeterChanges(unittest.TestCase):
    """Disk-gated: parse the minimal .als and verify metre changes.

    Ground truth (Alexander's Ableton screenshot, bars 369-392):
        9/16 → 13/8 → (13/8) → 4/4
    The assertions check that 9/16, 13/8, 4/4 appear IN THAT ORDER as a
    subsequence of time_sig_changes[*].sig — dedup of consecutive identical
    sigs means the two 13/8 events collapse to one.
    """

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.mkdtemp()
        out = str(Path(tmp) / "result_als.json")
        parse_als.parse_als(str(FRAGILE_MINIMAL), out)
        with open(out, encoding="utf-8") as f:
            cls.result = json.load(f)
        cls.sigs = [c["sig"] for c in cls.result.get("time_sig_changes", [])]

    def test_time_sig_changes_present(self):
        self.assertGreater(
            len(self.sigs), 1,
            "time_sig_changes must have more than one entry (project has metre changes)",
        )

    def test_9_16_present(self):
        self.assertIn("9/16", self.sigs, "9/16 must appear in time_sig_changes")

    def test_13_8_present(self):
        self.assertIn("13/8", self.sigs, "13/8 must appear in time_sig_changes")

    def test_4_4_present(self):
        self.assertIn("4/4", self.sigs, "4/4 must appear in time_sig_changes")

    def test_order_9_16_then_13_8_then_4_4(self):
        """9/16 must appear before 13/8, which must appear before a 4/4 return."""
        sigs = self.sigs
        try:
            idx_9_16 = next(i for i, s in enumerate(sigs) if s == "9/16")
            idx_13_8 = next(i for i, s in enumerate(sigs) if s == "13/8" and i > idx_9_16)
            next(i for i, s in enumerate(sigs) if s == "4/4" and i > idx_13_8)
        except StopIteration:
            self.fail(
                f"Expected 9/16 → 13/8 → 4/4 as ordered subsequence; got: {sigs}"
            )

    def test_beats_ascending(self):
        changes = self.result.get("time_sig_changes", [])
        beats = [c["beat"] for c in changes]
        self.assertEqual(beats, sorted(beats), "time_sig_changes must be sorted by beat")

    def test_time_s_consistent_with_beat(self):
        """time_s ≈ beat * (60 / bpm) for each entry."""
        bpm = self.result.get("bpm", 120)
        beat_to_s = 60.0 / bpm
        for entry in self.result.get("time_sig_changes", []):
            expected = round(entry["beat"] * beat_to_s, 1)
            actual = round(entry["time_s"], 1)
            self.assertAlmostEqual(
                actual, expected, delta=0.5,
                msg=f"time_s mismatch at beat {entry['beat']}: {actual} vs {expected}",
            )


if __name__ == "__main__":
    unittest.main()
