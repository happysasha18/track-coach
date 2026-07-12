#!/usr/bin/env python3
"""§E run validity — RC-INV-13/13a/13d. A run is complete or it does not exist.

A run is VALID when every promised signal whose source part the significance gate reads as PRESENT
carries a real value. A gate-absent part (a near-silent stem) is a valid "not present", never a gap.
Fixtures are synthetic + deterministic (made-up data, never real music)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import validity as V  # noqa: E402


def _bands(db):
    """Six-band × 8-window block all at `db` (a loud stem ≈ -30, a silent one ≈ -85)."""
    return {b: [db] * 8 for b in ("sub", "low", "low_mid", "mid", "hi_mid", "air")}


def _run(tmp, *, bass_db=-30.0, other_db=-30.0, drums_db=-30.0,
         sustain=True, centroid=True, notes=True, tempo=True):
    """A full run dir: loud drums/bass/other by default (all significant), with the sustain block,
    spectral centroid, and an other-stem notes file present. Flip a flag to break/omit a piece."""
    run = Path(tmp) / "run"; run.mkdir()
    core = {"vitals": {"dynamic_range_db": 10.0}, "stereo_width_mean": 0.5,
            "density_lv": 0.6, "energy_trend": 0.2}
    if tempo:
        core["vitals"]["tempo_bpm"] = 120.0
    (run / "result_core.json").write_text(json.dumps(core))
    mk = {"band_rms_db": {"drums": _bands(drums_db), "bass": _bands(bass_db),
                          "other": _bands(other_db)},
          "stems_analysed": ["drums", "bass", "other"], "duration_s": 48.0,
          "total_windows": 8}
    if sustain:
        mk["sustain"] = {"bass": 0.5, "other": 0.4}
    if centroid:
        mk["spectral_centroid"] = {"other": 800.0}
    (run / "result_masking.json").write_text(json.dumps(mk))
    if notes:
        (run / "result_notes_other.json").write_text(json.dumps({"n_notes": 42}))
    return str(run)


class RunValidity(unittest.TestCase):
    def test_complete_run_is_valid(self):
        with tempfile.TemporaryDirectory() as td:
            valid, reads = V.validity(_run(td), "full")
            self.assertTrue(valid, f"a fully-measured run must be valid; unmeasured: {reads}")
            self.assertEqual(reads, [])

    def test_broken_run_is_invalid_and_names_the_gap(self):
        """The other stem is significant but its sustain/centroid were never computed → invalid,
        and the unmeasured signals are named (what a redo must recover)."""
        with tempfile.TemporaryDirectory() as td:
            valid, reads = V.validity(_run(td, sustain=False, centroid=False), "full")
            self.assertFalse(valid, "a present stem with unmeasured sustain/brightness is invalid")
            self.assertIn("pad sustain", reads)
            self.assertIn("harmonic brightness", reads)

    def test_gate_absent_part_stays_valid(self):
        """A near-silent bass (below the significance floor) makes bass axes 'not present' — the run
        is still valid even though bass_sustain is absent (it is a real 'no bass', not a gap)."""
        with tempfile.TemporaryDirectory() as td:
            # bass near-silent; drop the bass entries from sustain so bass_sustain is absent
            run = _run(td, bass_db=-85.0)
            mk = json.loads((Path(run) / "result_masking.json").read_text())
            mk["sustain"] = {"other": 0.4}  # no bass sustain — but bass is insignificant, so fine
            (Path(run) / "result_masking.json").write_text(json.dumps(mk))
            valid, reads = V.validity(run, "full")
            self.assertTrue(valid, f"a genuinely-absent bass must not invalidate the run; got {reads}")
            self.assertNotIn("bass sustain", reads)

    def test_failed_mix_detector_invalidates(self):
        """A missing tempo (detector failed) reads as unmeasured, not an imputed 0 → invalid."""
        with tempfile.TemporaryDirectory() as td:
            valid, reads = V.validity(_run(td, tempo=False), "full")
            self.assertFalse(valid, "a run whose tempo detector produced nothing is invalid")
            self.assertIn("tempo", reads)

    def test_quick_run_valid_on_its_five_signals(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td) / "run"; run.mkdir()
            (run / "result_core.json").write_text(json.dumps({
                "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
                "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
            valid, reads = V.validity(str(run), "quick")
            self.assertTrue(valid, f"a quick run is complete for its five mix signals; got {reads}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
