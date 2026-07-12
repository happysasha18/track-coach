#!/usr/bin/env python3
"""Development-mode read (SPEC §B.12 / matrix INV-32, 2026-06-23).

`development_mode(core)` is the OBSERVATION behind the Producer's read line "grows by loud + bright;
stereo & density sit idle". It must (a) name each dominant axis WITH its direction (any axis can be
dominant while moving down — never "grows by brightness" on a darkening track), (b) flag idle axes only
when something develops, (c) say NOTHING on a flat track (so it never double-covers `energy_flat`).
Calibrated by deed on the 3 library tracks — the trend numbers below are the real ones.
"""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget as bw  # noqa: E402


def _axes(res):
    return {d["axis"]: d for d in res["dominant"]}


class DevelopmentMode(unittest.TestCase):
    # ── real library tracks (result_core.json trends, 2026-06-23) ──
    def test_lazy_grows_by_loud_and_bright(self):
        core = {"energy_trend": 0.284, "brightness_trend": 0.242,
                "density_trend": 0.057, "stereo_width_trend": 0.086}
        res = bw.development_mode(core)
        a = _axes(res)
        self.assertEqual(set(a), {"energy", "brightness"})       # both clearly dominant
        self.assertEqual(a["energy"]["dir"], "up")
        self.assertEqual(a["brightness"]["dir"], "up")
        self.assertEqual(set(res["idle"]), {"density", "stereo width"})
        # strongest first
        self.assertEqual(res["dominant"][0]["axis"], "energy")

    def test_shared_busier_and_image_tightens(self):
        core = {"energy_trend": 0.042, "brightness_trend": 0.018,
                "density_trend": 0.146, "stereo_width_trend": -0.199}
        res = bw.development_mode(core)
        a = _axes(res)
        self.assertEqual(set(a), {"density", "stereo width"})
        self.assertEqual(a["density"]["dir"], "up")
        self.assertEqual(a["stereo width"]["dir"], "down")        # image NARROWS — direction matters
        self.assertIn("tightens", a["stereo width"]["phrase"])
        self.assertEqual(set(res["idle"]), {"energy", "brightness"})

    def test_wobble_opens_only_in_brightness(self):
        core = {"energy_trend": -0.03, "brightness_trend": 0.411,
                "density_trend": 0.083, "stereo_width_trend": 0.187}
        res = bw.development_mode(core)
        a = _axes(res)
        self.assertEqual(set(a), {"brightness", "stereo width"})
        self.assertEqual(res["dominant"][0]["axis"], "brightness")  # by far the strongest
        self.assertEqual(set(res["idle"]), {"energy", "density"})

    # ── direction / edge cases (prover F1, F5) ──
    def test_darkening_track_says_darkens_not_grows(self):
        core = {"energy_trend": 0.0, "brightness_trend": -0.30,
                "density_trend": 0.0, "stereo_width_trend": 0.0}
        a = _axes(bw.development_mode(core))
        self.assertEqual(a["brightness"]["dir"], "down")
        self.assertIn("darkens", a["brightness"]["phrase"])

    def test_flat_track_returns_empty_both(self):
        core = {"energy_trend": 0.05, "brightness_trend": -0.04,
                "density_trend": 0.02, "stereo_width_trend": 0.08}
        res = bw.development_mode(core)
        self.assertEqual(res["dominant"], [])
        self.assertEqual(res["idle"], [])      # no dominant ⇒ no idle flag, read stays silent

    def test_moderate_axis_is_neither_named_nor_flagged(self):
        # density 0.11 sits in the 0.10–0.12 gap → not dominant, not idle
        core = {"energy_trend": 0.30, "brightness_trend": 0.0,
                "density_trend": 0.11, "stereo_width_trend": 0.0}
        res = bw.development_mode(core)
        self.assertEqual({d["axis"] for d in res["dominant"]}, {"energy"})
        self.assertEqual(set(res["idle"]), {"brightness", "stereo width"})  # density excluded

    def test_missing_trend_keys_are_skipped(self):
        res = bw.development_mode({"energy_trend": 0.30})
        self.assertEqual({d["axis"] for d in res["dominant"]}, {"energy"})
        self.assertEqual(res["idle"], [])      # other axes absent, not idle
        self.assertEqual(bw.development_mode({}), {"dominant": [], "idle": []})
        self.assertEqual(bw.development_mode(None), {"dominant": [], "idle": []})


if __name__ == "__main__":
    unittest.main()
