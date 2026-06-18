#!/usr/bin/env python3
"""Orchestration-plan tests — the cheapest, highest-value tests for this project.

They assert the *shape* of the pipeline `track_analyzer.py analyze` would run, using
`--dry-run` (no audio, no deps, no Demucs — instant). Every bug this project shipped
lived in the orchestration seams, so this is exactly where a regression test pays off:

  - the deep steps must all read the SAME stems dir (the `stems/` vs `stems_6s/`
    mismatch once silently dropped the player and every stem lane);
  - web-stems (the player) must always be produced in full mode;
  - quick mode must NOT touch Demucs/stems;
  - run-dir first, build last.

Pure stdlib unittest, so it runs with plain `python3 -m unittest` — no pytest needed.
"""
import subprocess, sys, unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "track_analyzer.py"


def plan(*extra):
    """Return the dry-run command lines for an analyze invocation."""
    cmd = [sys.executable, str(SCRIPT), "analyze",
           "/x/My_Track_[v0.6.2].wav", "--dry-run", *extra]
    out = subprocess.run(cmd, check=True, text=True, capture_output=True)
    # step commands are printed (to stdout) as "  $ …"
    return [ln.strip()[2:] for ln in (out.stdout + out.stderr).splitlines()
            if ln.strip().startswith("$ ")]


def step_index(lines, needle):
    for i, ln in enumerate(lines):
        if needle in ln:
            return i
    return -1


class FullMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = plan("--als", "/x/p.als", "--als-offset-s", "7.2")

    def test_run_dir_is_first(self):
        self.assertIn("run_dir.py init", self.lines[0])

    def test_analyze_is_measure_only(self):
        # analyze measures; it must NOT render (that's `build`, after the read). No double-render.
        self.assertEqual(step_index(self.lines, "build_widget.py"), -1)
        self.assertEqual(step_index(self.lines, "run_dir.py catalog"), -1)

    def test_last_step_is_web_stems(self):
        self.assertIn("make_web_stems.py", self.lines[-1])

    def test_all_deep_steps_share_one_stems_dir(self):
        # the bug class: a step reading a different stems dir produces nothing silently
        deep = ["masking.py", "rhythm_quality.py", "drum_breakdown.py",
                "map_stems.py", "make_web_stems.py", "transcribe.py"]
        for s in deep:
            line = self.lines[step_index(self.lines, s)]
            self.assertIn("stems_6s", line, f"{s} must read the shared stems_6s dir")
            self.assertNotIn("stems/ ", line)  # never the bare 4-stem default here

    def test_web_stems_is_present(self):
        # skipping it = a deep analysis with no player and no stem lanes (the old regression)
        self.assertGreaterEqual(step_index(self.lines, "make_web_stems.py"), 0)

    def test_separation_before_its_consumers(self):
        sep = step_index(self.lines, "separate.py")
        for consumer in ("masking.py", "make_web_stems.py", "drum_breakdown.py"):
            self.assertLess(sep, step_index(self.lines, consumer))

    def test_map_stems_only_with_als_and_offset(self):
        # present here because we passed both --als and --als-offset-s
        self.assertGreaterEqual(step_index(self.lines, "map_stems.py"), 0)


class QuickMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = plan("--mode", "quick")

    def test_no_demucs_or_stems(self):
        for s in ("separate.py", "masking.py", "make_web_stems.py", "drum_breakdown.py"):
            self.assertEqual(step_index(self.lines, s), -1,
                             f"quick mode must not run {s}")

    def test_still_runs_core_detail_selfsim(self):
        for s in ("analyze_core.py", "analyze_detail.py", "self_similarity.py"):
            self.assertGreaterEqual(step_index(self.lines, s), 0)

    def test_does_not_render(self):
        self.assertEqual(step_index(self.lines, "build_widget.py"), -1)


class MapStemsGuard(unittest.TestCase):
    def test_map_stems_skipped_without_offset(self):
        # als but no offset, and dry-run can't read a locator → map_stems is skipped
        lines = plan("--als", "/x/p.als")
        self.assertEqual(step_index(lines, "map_stems.py"), -1)


def build_plan(*extra):
    cmd = [sys.executable, str(SCRIPT), "build", "--run-dir", "/x/run", "--dry-run", *extra]
    out = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return [ln.strip()[2:] for ln in (out.stdout + out.stderr).splitlines()
            if ln.strip().startswith("$ ")]


class BuildPlan(unittest.TestCase):
    """build is the single render step — it must produce the catalog and the widget."""
    @classmethod
    def setUpClass(cls):
        cls.lines = build_plan()

    def test_renders_widget(self):
        self.assertGreaterEqual(step_index(self.lines, "build_widget.py"), 0)

    def test_builds_catalog_before_widget(self):
        cat = step_index(self.lines, "run_dir.py catalog")
        self.assertGreaterEqual(cat, 0)
        self.assertLess(cat, step_index(self.lines, "build_widget.py"))

    def test_no_catalog_flag_skips_it(self):
        lines = build_plan("--no-catalog")
        self.assertEqual(step_index(lines, "run_dir.py catalog"), -1)
        self.assertGreaterEqual(step_index(lines, "build_widget.py"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
