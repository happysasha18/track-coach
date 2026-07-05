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
import json, re, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "track_analyzer.py"
sys.path.insert(0, str(SCRIPT.parent))


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
        # skipping it = a deep analysis with no player and no player lanes (the old regression)
        self.assertGreaterEqual(step_index(self.lines, "make_web_stems.py"), 0)

    def test_full_also_encodes_a_web_mix_for_the_catalog(self):
        # the widget uses the per-stem player, but the catalog's one-button preview needs a single
        # mix → full ALSO encodes make_web_stems --audio into mix_web/ (session 10). Without it, full
        # rows in the catalog would never get a play button.
        mixes = [ln for ln in self.lines if "make_web_stems.py" in ln and "--audio" in ln]
        self.assertTrue(mixes, "full mode must encode a web mix (mix_web) for the catalog player")
        self.assertTrue(any("mix_web" in ln for ln in mixes), "the web mix must land in mix_web/")

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

    def test_no_demucs(self):
        # quick never separates or runs any stem-dependent analysis
        for s in ("separate.py", "masking.py", "drum_breakdown.py", "map_stems.py",
                  "rhythm_quality.py", "transcribe.py"):
            self.assertEqual(step_index(self.lines, s), -1,
                             f"quick mode must not run {s}")

    def test_encodes_a_web_mix_for_the_player(self):
        # quick has no stems but DOES compress the mix → the single-track player (Sasha 2026-06-20:
        # "плеер какая разница быстрый прогон?"). It reuses make_web_stems.py in --audio (mix) mode,
        # NOT --stems-dir (there are no stems).
        i = step_index(self.lines, "make_web_stems.py")
        self.assertGreaterEqual(i, 0, "quick must encode a web mix so the widget has a player")
        self.assertIn("--audio", self.lines[i], "quick mix-encode must use --audio (the mix)")
        self.assertNotIn("--stems-dir", self.lines[i], "quick has no stems dir to encode")

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


class MalformedRunIndexTolerated(unittest.TestCase):
    """A run dir nested under a SHARED track-coach-output/ (e.g. Wobble under the Fragile project)
    can inherit a legacy index.json whose `runs` holds a stray non-dict entry (an old slug string).
    Neither the run registrar (track_analyzer._register_run, before build) nor the catalog reader
    (run_dir cmd_catalog) may crash on it — they skip the bad entry and still process the real dict.
    Regression: Phase B 2026-06-23, `'str' object has no attribute 'get'` on the first fresh full
    build since the index schema firmed up. Sibling of INV-15 (deposit refuses malformed run dirs)."""

    def _tree(self, td):
        base = Path(td) / "track-coach-output"
        run = base / "My_Track" / "v1__2026-06-23_1000"
        run.mkdir(parents=True)
        idx = {"runs": ["My_Track_v1",                       # the stray legacy string
                        {"track": "My_Track", "version": "v1", "run_dir": str(run),
                         "analyzed_at": "2026-06-23 10:00", "mode": "full",
                         "widget": "analysis_widget_v1.html"}]}
        (base / "index.json").write_text(json.dumps(idx))
        return base, run

    def test_register_run_skips_non_dict_entry(self):
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as td:
            base, run = self._tree(td)
            ta._register_run(run, "analysis_widget_v1.html", "looks good")   # must not raise
            runs = json.loads((base / "index.json").read_text())["runs"]
            self.assertEqual(runs[0], "My_Track_v1")                         # stray left untouched
            self.assertEqual(runs[1]["verdict"], "looks good")               # real entry updated

    def test_catalog_reader_skips_non_dict_entry(self):
        with tempfile.TemporaryDirectory() as td:
            base, run = self._tree(td)
            out = subprocess.run([sys.executable, str(SCRIPT.parent / "run_dir.py"),
                                  "catalog", "--self", str(run)],
                                 text=True, capture_output=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            cat = json.loads((run / "catalog.json").read_text())
            self.assertEqual(cat["n_runs"], 1)                              # only the real dict counted


class AutoDepositIsDefault(unittest.TestCase):
    """G-INV-17 / H-INV-7: a successful `build` auto-deposits into the global library — it is
    the DEFAULT ingest, not a separate manual step. The only way to skip it is the explicit
    opt-OUT flag `--no-deposit`; there is no opt-IN `--deposit` flag. If deposit ever became
    opt-in, the user would silently lose the catalog entry they expect. Level: L0-DATA
    (the CLI contract + the `not args.no_deposit` gate at track_analyzer `_cmd_build`)."""

    def _build_help(self):
        out = subprocess.run([sys.executable, str(SCRIPT), "build", "--help"],
                             text=True, capture_output=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout + out.stderr

    def test_no_deposit_is_an_opt_out_flag(self):
        """`build --help` exposes `--no-deposit` as an opt-OUT (don't copy into the library)."""
        help_txt = self._build_help()
        self.assertIn("--no-deposit", help_txt,
                      "build must expose --no-deposit (the opt-out for auto-deposit, G-INV-17)")
        self.assertIn("don't copy", help_txt.lower().replace("’", "'"),
                      "--no-deposit help must read as an opt-out (don't copy into the library)")

    def test_no_opt_in_deposit_flag(self):
        """Deposit is automatic — there is NO opt-IN `--deposit` flag; the default build path
        deposits. A `--deposit` toggle would mean deposit is manual, breaking G-INV-17."""
        help_txt = self._build_help()
        # `--no-deposit` contains the substring "deposit"; assert no BARE `--deposit` opt-in.
        self.assertIsNone(re.search(r"--deposit\b", help_txt),
                          "there must be no opt-in --deposit flag; deposit is the default ingest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
