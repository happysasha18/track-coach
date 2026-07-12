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
import json, os, re, subprocess, sys, tempfile, unittest
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
        # quick has no stems but DOES compress the mix → the single-track player (2026-06-20:
        # quick mode still gets a player). It reuses make_web_stems.py in --audio (mix) mode,
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


class SyntheticFixtureSourceGuarded(unittest.TestCase):
    """G-INV-21: a source living under a test-fixtures tree is auto-detected as synthetic, so a
    smoke/fixture run can never deposit into the real library even without the `--synthetic` flag.
    A normal source path is never mistaken for a fixture."""

    def test_fixture_source_marks_synthetic(self):
        import track_analyzer as ta
        self.assertTrue(ta.is_synthetic_source("/repo/tests/fixtures/synthetic/sine_220hz_1s.wav"),
                        "a source under tests/fixtures/ must be flagged synthetic (G-INV-21)")
        self.assertTrue(ta.is_synthetic_source(Path("tests/fixtures/synthetic/sine_220hz_1s.wav")),
                        "a relative fixtures path must be flagged synthetic too")

    def test_normal_source_not_marked(self):
        import track_analyzer as ta
        self.assertFalse(ta.is_synthetic_source("/Users/me/Music/Ableton/My Track/bounce.wav"),
                         "a real project source must not be flagged synthetic (G-INV-21)")
        self.assertFalse(ta.is_synthetic_source("/Users/me/testfixtures_album/song.wav"),
                         "a path merely containing the word must not trip the fixtures guard")

    def test_synthetic_flag_on_analyze(self):
        """`analyze --help` exposes the `--synthetic` opt-in for an intentional smoke run."""
        out = subprocess.run([sys.executable, str(SCRIPT), "analyze", "--help"],
                             text=True, capture_output=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("--synthetic", out.stdout + out.stderr,
                      "analyze must expose --synthetic (keeps a smoke run out of the library, G-INV-21)")


class RunValidityOrchestration(unittest.TestCase):
    """RC-INV-13/13a/13c: the library's incomplete runs are found; a completion re-measures the
    stored audio with --only-this (no re-trigger); the flags are exposed."""

    def _bands(self, db):
        return {b: [db] * 8 for b in ("sub", "low", "low_mid", "mid", "hi_mid", "air")}

    def _run(self, base, name, *, sustain, audio="/music/x.wav", audio_path=None):
        run = Path(base) / name; run.mkdir(parents=True)
        meta = {"mode": "full", "track": name}
        # Real runs store the FULL source path under 'audio_path'; the 'audio' key is a bare
        # basename (new runs) or absent (old v0.6.x runs). Mirror that so the resolver is tested
        # against the shape on disk, not a convenient full-path-under-'audio' fixture.
        if audio is not None:
            meta["audio"] = audio
        if audio_path is not None:
            meta["audio_path"] = audio_path
        (run / "run_meta.json").write_text(json.dumps(meta))
        (run / "result_core.json").write_text(json.dumps({
            "vitals": {"tempo_bpm": 120.0, "dynamic_range_db": 10.0},
            "stereo_width_mean": 0.5, "density_lv": 0.6, "energy_trend": 0.2}))
        mk = {"band_rms_db": {"drums": self._bands(-30.0), "bass": self._bands(-30.0),
                              "other": self._bands(-30.0)},
              "stems_analysed": ["drums", "bass", "other"], "duration_s": 48.0,
              "total_windows": 8, "spectral_centroid": {"other": 800.0}}
        if sustain:
            mk["sustain"] = {"bass": 0.5, "other": 0.4}
        (run / "result_masking.json").write_text(json.dumps(mk))
        (run / "result_notes_other.json").write_text(json.dumps({"n_notes": 42}))
        return str(run)

    def test_incomplete_deposits_found(self):
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            whole = self._run(d, "whole", sustain=True)
            partial = self._run(d, "partial", sustain=False)  # other significant, sustain missing
            lib = Path(d) / "lib"; (lib / "widgets").mkdir(parents=True)
            index = {"entries": [
                {"track": "Whole", "mode": "full", "src_run_dir": whole, "widget": "w.html"},
                {"track": "Partial", "mode": "full", "src_run_dir": partial, "widget": "p.html"}]}
            (lib / "index.json").write_text(json.dumps(index))
            inc = ta._incomplete_deposits(root=lib)
            names = [e.get("track") for e, sd, un in inc]
            self.assertEqual(names, ["Partial"], "only the incomplete run is listed")
            self.assertIn("pad sustain", inc[0][2])

    def test_complete_run_dry_plans_reanalyse_only_this(self):
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            partial = self._run(d, "partial", sustain=False, audio="/music/track.wav")
            cmds = ta._complete_run(partial, dry=True)
            self.assertEqual(len(cmds), 1)
            self.assertIn("analyze", cmds[0])
            self.assertIn("/music/track.wav", cmds[0])
            self.assertIn("--only-this", cmds[0], "the re-measure must not re-trigger the backfill")

    def test_complete_run_resolves_audio_path_key(self):
        """A run that stored its source only under 'audio_path' (old v0.6.x shape, and the key
        every real run writes) must still be completable — the resolver reads audio_path, not just
        the bare 'audio' basename. Regression: Wobble Drift no-oped silently. RC-INV-13a."""
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            partial = self._run(d, "partial", sustain=False, audio=None,
                                 audio_path="/music/track.wav")
            cmds = ta._complete_run(partial, dry=True)
            self.assertIsNotNone(cmds, "a run with only audio_path must still be completable")
            self.assertIn("/music/track.wav", cmds[0])
            self.assertIn("--only-this", cmds[0])

    def test_revalidate_apply_fails_loud_when_source_gone(self):
        """`revalidate --apply` must never report success while a run stays incomplete. When the
        source audio is unrecorded/gone it cannot complete the run, so it exits non-zero and says
        so — a run is complete or the tool tells you it failed, never a silent partial. RC-INV-13."""
        with tempfile.TemporaryDirectory() as d:
            partial = self._run(d, "partial", sustain=False, audio=None,
                                 audio_path="/does/not/exist.wav")
            lib = Path(d) / "lib"; (lib / "widgets").mkdir(parents=True)
            index = {"entries": [
                {"track": "Partial", "mode": "full", "src_run_dir": partial, "widget": "p.html"}]}
            (lib / "index.json").write_text(json.dumps(index))
            env = dict(os.environ, TRACK_COACH_LIBRARY=str(lib))
            out = subprocess.run([sys.executable, str(SCRIPT), "revalidate", "--apply"],
                                 text=True, capture_output=True, env=env)
            self.assertNotEqual(out.returncode, 0,
                                "must exit non-zero when a run could not be completed")
            self.assertIn("could not", (out.stdout + out.stderr).lower())

    def test_reference_run_validity_guard(self):
        """RC-INV-13e: a reference run about to feed a direction centroid is judged for validity at
        the point of use (reference runs never deposit, so the library gate never reaches them). An
        incomplete one is reported invalid with its unmeasured reads; a complete one passes."""
        import gen_reference_directions as g
        with tempfile.TemporaryDirectory() as d:
            partial = self._run(d, "partial", sustain=False)  # other significant, sustain missing
            whole = self._run(d, "whole", sustain=True)
            ok_p, un_p = g._run_valid(partial)
            ok_w, un_w = g._run_valid(whole)
            self.assertFalse(ok_p, "an incomplete reference run must be judged invalid")
            self.assertIn("pad sustain", un_p)
            self.assertTrue(ok_w, "a complete reference run must pass the guard")

    def test_flags_exposed(self):
        for cmd, flag in (("analyze", "--only-this"), ("build", "--only-this"),
                          ("revalidate", "--apply")):
            out = subprocess.run([sys.executable, str(SCRIPT), cmd, "--help"],
                                 text=True, capture_output=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn(flag, out.stdout + out.stderr, f"{cmd} must expose {flag}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
