#!/usr/bin/env python3
"""Card-order toggle — urgency ⇄ chronological (SPEC §B.11 / INV-26), Detailed only.

The recommendation cards default to urgency order (fix → do → concept). In the Detailed view a
small control flips them to the order they occur in the track (by timecode). Three levels:
 - the pure ordering helper `recSortOrder` runs in node (the REAL shipped function, extracted);
 - the control element + its Detailed-only CSS gate ship in the rendered widget (string);
 - in headless Chrome the toggle actually reorders the card nodes AND keeps them (appendChild moves
   a node, so its INV-48 click listeners survive) — a rebuild would drop them.
Each browser/node class skips cleanly where the engine is absent.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402
import headless_check as hc  # noqa: E402

NODE = shutil.which("node")
_HAVE_CHROME = Path(hc.CHROME).exists()
_LOGIC = re.compile(r"/\* RECSORT_LOGIC_START.*?RECSORT_LOGIC_END \*/", re.S)
_WIRE = re.compile(r"/\* RECSORT_WIRE_START.*?RECSORT_WIRE_END \*/", re.S)


def _rich_core(n=48, dur=120.0):
    """A core wired to spawn several recs INCLUDING time-bound ones (climax, endpoint, long tail
    section, wobble) so there are ≥2 timecoded cards to reorder — no private run needed."""
    tb = [round(i * dur / n, 3) for i in range(n)]
    ramp = [round(0.15 + 0.8 * i / n, 3) for i in range(n)]
    bright = [round(0.1 + 0.85 * i / n, 3) for i in range(n)]
    return {
        "duration_s": dur, "time_bins": tb, "tempo": 123,
        "energy": ramp, "brightness": bright,
        "density": [round(0.3 + 0.5 * (i % 5) / 5, 3) for i in range(n)],
        "wobble_rate": [round(1.0 + (i % 4), 3) for i in range(n)],
        "stereo_width": [round(0.4 + 0.3 * (i % 3) / 3, 3) for i in range(n)],
        "energy_trend": 0.5, "brightness_trend": 0.6, "density_trend": 0.05,
        "stereo_width_trend": 0.1, "wobble_rate_start_hz": 3.0, "wobble_rate_end_hz": 3.2,
        "section_bounds_s": [round(dur * 0.1, 2), round(dur * 0.15, 2)],
        "endpoint_cosine": 0.97,
        "vitals": {"true_peak_db": 0.6, "dynamic_range_db": 4.5},
        "tonal_balance": [{"band": "250", "dev_db": 6.0}],
    }


def _build_widget():
    tmp = Path(tempfile.mkdtemp(prefix="tc_recsort_"))
    out = tmp / "widget.html"
    build_widget.build_html(_rich_core(), {}, None, None, str(out), "Card Order Test",
                            build_widget.STRINGS, mode="full",
                            narrative_md="The mix reads clear.")
    return str(out)


class RecSortShipped(unittest.TestCase):
    """The control, its Detailed-only gate, and the pure/wire blocks are all in the artifact."""

    @classmethod
    def setUpClass(cls):
        cls.html = Path(_build_widget()).read_text(encoding="utf-8")

    def test_control_present(self):
        self.assertIn('id="recSort"', self.html)

    def test_detailed_only_gate(self):
        # Simple and Quick never show the toggle (INV-26 — the toggle is a Detailed affordance).
        self.assertIn("body.simple #recSort", self.html)
        self.assertIn("body.quick #recSort", self.html)

    def test_logic_and_wire_ship(self):
        self.assertRegex(self.html, _LOGIC)
        self.assertRegex(self.html, _WIRE)


@unittest.skipUnless(NODE, "node not installed — pure ordering test needs a JS engine")
class RecSortLogic(unittest.TestCase):
    """Execute the REAL extracted recSortOrder over real cases (assert on the artifact, not a mirror)."""

    @classmethod
    def setUpClass(cls):
        html = Path(_build_widget()).read_text(encoding="utf-8")
        cls.block = _LOGIC.search(html).group(0)

    def _order(self, ts, mode):
        js = (self.block + "\nconst ts=" + repr(list(ts)).replace("None", "null") +
              ";process.stdout.write(JSON.stringify(recSortOrder(ts," + repr(mode) + ")));")
        out = subprocess.run([NODE, "-e", js], text=True, capture_output=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        import json
        return json.loads(out.stdout)

    def test_urgency_is_identity(self):
        self.assertEqual(self._order([5, 1, None, 3], "urgency"), [0, 1, 2, 3])

    def test_time_ascending_globals_last(self):
        self.assertEqual(self._order([5, 1, None, 3], "time"), [1, 3, 0, 2])

    def test_time_ties_are_stable(self):
        # equal timecodes keep their urgency order (a stable sort)
        self.assertEqual(self._order([2, 2, 1], "time"), [2, 0, 1])

    def test_all_global_unchanged(self):
        self.assertEqual(self._order([None, None], "time"), [0, 1])


@unittest.skipUnless(_HAVE_CHROME, "headless Chrome not installed")
class RecSortReorderInChrome(unittest.TestCase):
    """The toggle reorders the REAL card nodes in a real browser and keeps them (listeners survive)."""

    @classmethod
    def setUpClass(cls):
        cls.widget = _build_widget()

    def _ts_order(self, click_time):
        js = (
            '(function(){'
            'var b=document.querySelector("#recSort button[data-s=\\"" + '
            '(%s?"time":"urgency") + "\\"]");'
            'if(b){b.__seen=1;b.click();}'                       # tag the node, then click it
            'var cards=[].slice.call(document.querySelectorAll("#recs .rec[data-t]"));'
            'return {order:cards.map(function(e){return parseFloat(e.getAttribute("data-t"));}),'
            'visible:getComputedStyle(document.getElementById("recSort")).display!=="none"};'
            '})()'
        ) % ("true" if click_time else "false")
        return hc.probe(self.widget, js, width=1100, height=3200, url_suffix="#detailed")

    def test_control_visible_in_detailed(self):
        r = self._ts_order(False)
        self.assertNotIn("__error", r, r.get("__error"))
        self.assertTrue(r["visible"], "the control shows in Detailed when there are timecoded cards")

    def test_by_time_sorts_ascending(self):
        r = self._ts_order(True)
        self.assertNotIn("__error", r, r.get("__error"))
        order = r["order"]
        self.assertGreaterEqual(len(order), 2, "the rich core must yield ≥2 timecoded cards")
        self.assertEqual(order, sorted(order), "By time orders the timecoded cards ascending")


if __name__ == "__main__":
    unittest.main(verbosity=2)
