"""render_run's from-cache re-render forwards the header version badge (finding d, s77).

A library re-render from cached analysis goes through render_run.discover_inputs -> the meta dict ->
build_widget.build_html, which shows a bold version chip when META.track_version is set. The resolver
used to read title/mode/analyzed_at/verdict from run_meta.json but NOT track_version, so a from-cache
re-render silently dropped the chip the real deposit path keeps. This pins that the field is carried.

Pure stdlib unittest — no librosa; exercises the resolver, which is where the field was dropped.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render_run  # noqa: E402


class RenderRunMeta(unittest.TestCase):
    def test_discover_inputs_forwards_track_version(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "run_meta.json").write_text(json.dumps({
                "track": "T", "title": "T v9.9.9", "track_version": "v9.9.9",
                "mode": "full", "analyzed_at": "2026-07-17 12:00",
            }))
            (run / "result_core.json").write_text(json.dumps({"duration_s": 1.0}))
            found = render_run.discover_inputs(run)
            self.assertEqual(found.get("track_version"), "v9.9.9",
                             "render_run.discover_inputs dropped run_meta's track_version — the "
                             "from-cache re-render would lose the header version chip")

    def test_absent_track_version_is_none_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "run_meta.json").write_text(json.dumps({"track": "T", "mode": "full"}))
            (run / "result_core.json").write_text(json.dumps({"duration_s": 1.0}))
            found = render_run.discover_inputs(run)
            self.assertIsNone(found.get("track_version"))


if __name__ == "__main__":
    unittest.main()
