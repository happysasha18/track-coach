#!/usr/bin/env python3
"""Red-first tests for the 2026-07-16 command audit findings in track_analyzer.py
(docs/COMMAND_AUDIT_2026-07-16.md). Each class targets one finding:

  1. G-INV-11 / RC-INV-13a — _complete_run must not forget the old library entry before
     confirming (verify-by-deed) the replacement actually deposited.
  2. audit root class 1 — _update_meta must write run_meta.json via the shared atomic-write
     helper (library._atomic_write_text), not a plain in-place write_text.
  3. LOW correctness — `analyze --als --dry-run` (no explicit --als-offset-s) must not go
     silent about map_stems.
  4. RC-INV-13f / E-4 — a KeyboardInterrupt mid-analyze must not stamp analysis_state:"failed".
  5. LOW correctness — the nested `build` launched by the backfill must not leak its own
     stdout (widget path) onto the caller's stdout.

Pure stdlib unittest; no Demucs/browser. subprocess.run inside track_analyzer is monkeypatched
for the _complete_run tests (findings 1 & 5) so they run instantly with no real re-analysis.
"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "track_analyzer.py"
sys.path.insert(0, str(SCRIPT.parent))


# ── finding 2: _update_meta must be crash-consistent (atomic write) ────────────────────────

class UpdateMetaAtomic(unittest.TestCase):
    """_update_meta is called 4-7x per run (offset, fingerprint, tags, reference/synthetic
    markers, analysis_state). A hard kill mid-write must leave the old or the new complete
    run_meta.json, never a torn one — so it must route through the shared atomic-write helper
    (library._atomic_write_text), the ONE writer every index/marker save in this codebase uses."""

    def test_update_meta_routes_through_atomic_write_helper(self):
        import track_analyzer as ta
        import library
        calls = []
        real = library._atomic_write_text

        def spy(path, text):
            calls.append((Path(path), text))
            real(path, text)

        library._atomic_write_text = spy
        try:
            with tempfile.TemporaryDirectory() as d:
                out_dir = Path(d)
                ta._update_meta(out_dir, {"analysis_state": "running"})
        finally:
            library._atomic_write_text = real
        self.assertEqual(len(calls), 1,
                         "_update_meta must write run_meta.json via library._atomic_write_text "
                         "(G-INV-11 / audit root class 1)")
        self.assertEqual(calls[0][0], out_dir / "run_meta.json")
        self.assertEqual(json.loads(calls[0][1]), {"analysis_state": "running"})

    def test_update_meta_still_merges_and_persists_correctly(self):
        # the fix must not change the observable behaviour — merge semantics stay intact
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d)
            ta._update_meta(out_dir, {"a": 1, "b": 2})
            ta._update_meta(out_dir, {"b": 3})
            meta = json.loads((out_dir / "run_meta.json").read_text())
        self.assertEqual(meta, {"a": 1, "b": 3})


# ── finding 4: KeyboardInterrupt must not stamp analysis_state:"failed" ────────────────────

class KeyboardInterruptNotStampedFailed(unittest.TestCase):
    """RC-INV-13f / E-4: the pipeline guard around cmd_analyze must distinguish a mere
    interruption (Ctrl-C) from a terminal step failure. Stamping "failed" on KeyboardInterrupt
    produces the false 'source may be unreadable' honest-failure page for a run that would
    complete fine on retry. Mirrors the harness in test_pipeline_plan.py's AnalysisStateStamp
    (Runner.step monkeypatched to a raising stub; Runner.plain stays real so out_dir/run_meta.json
    are the genuine artifact)."""

    def _args(self, audio, base):
        import argparse
        return argparse.Namespace(
            audio=str(audio), als=None, als_offset_s=None, mode="full", model="htdemucs_6s",
            track_version=None, bpm=None, base=str(base), skip_transcribe=True, dry_run=False,
            reference=False, artist=None, synthetic=False, only_this=False)

    def test_keyboard_interrupt_does_not_stamp_failed(self):
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            audio = Path(d) / "src.wav"; audio.write_bytes(b"\x00")
            base = Path(d) / "out"; base.mkdir()

            def fake_step(self, profile, script, *args):
                if script == "separate.py":
                    raise KeyboardInterrupt()
                return ""

            real_step = ta.Runner.step
            ta.Runner.step = fake_step
            try:
                args = self._args(audio, base)
                with self.assertRaises(KeyboardInterrupt):
                    ta.cmd_analyze(args)
            finally:
                ta.Runner.step = real_step
            runs = list(Path(base).rglob("run_meta.json"))
            self.assertEqual(len(runs), 1, f"expected exactly one run dir, found {runs}")
            meta = json.loads(runs[0].read_text())
            self.assertNotEqual(meta.get("analysis_state"), "failed",
                               "a Ctrl-C interruption must not be mislabeled a terminal failure")
            self.assertEqual(meta.get("analysis_state"), "running",
                            "an interrupted run keeps the recoverable state stamped before the "
                            "pipeline started")

    def test_a_real_step_failure_still_stamps_failed(self):
        # regression guard: this fix must not weaken the EXISTING terminal-failure contract
        # (test_pipeline_plan.AnalysisStateStamp.test_terminal_failure_stamps_failed_with_reason)
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            audio = Path(d) / "src.wav"; audio.write_bytes(b"\x00")
            base = Path(d) / "out"; base.mkdir()

            def fake_step(self, profile, script, *args):
                if script == "separate.py":
                    sys.exit("✗ track-coach: step failed — separate.py (deep) (exit 1).")
                return ""

            real_step = ta.Runner.step
            ta.Runner.step = fake_step
            try:
                args = self._args(audio, base)
                with self.assertRaises(SystemExit):
                    ta.cmd_analyze(args)
            finally:
                ta.Runner.step = real_step
            runs = list(Path(base).rglob("run_meta.json"))
            meta = json.loads(runs[0].read_text())
            self.assertEqual(meta.get("analysis_state"), "failed")


# ── finding 3: dry-run must not go silent about map_stems ──────────────────────────────────

class DryRunMapStemsNote(unittest.TestCase):
    """The module's own contract (track_analyzer.py line 29) promises --dry-run "prints the
    plan without running anything". `analyze --als --dry-run` with no explicit --als-offset-s
    (the documented default case) previously printed neither the map_stems step nor a note —
    a silent omission. Now it must at least say what a real run would do."""

    def test_dry_run_notes_map_stems_without_explicit_offset(self):
        cmd = [sys.executable, str(SCRIPT), "analyze", "/x/fake.mp3",
               "--als", "/x/fake.als", "--dry-run"]
        out = subprocess.run(cmd, check=True, text=True, capture_output=True)
        combined = out.stdout + out.stderr
        self.assertIn("map_stems", combined,
                      "the dry-run plan must mention map_stems even without an explicit offset "
                      "(it silently omitted it before the fix)")

    def test_explicit_offset_plans_the_real_step_unchanged(self):
        # regression guard: an explicit --als-offset-s must still print the real $ command
        cmd = [sys.executable, str(SCRIPT), "analyze", "/x/fake.mp3", "--als", "/x/fake.als",
               "--als-offset-s", "3.0", "--dry-run"]
        out = subprocess.run(cmd, check=True, text=True, capture_output=True)
        lines = [ln.strip()[2:] for ln in (out.stdout + out.stderr).splitlines()
                 if ln.strip().startswith("$ ")]
        self.assertTrue(any("map_stems.py" in ln for ln in lines),
                        "an explicit offset must still schedule the actual map_stems.py command")

    def test_no_als_prints_no_map_stems_mention(self):
        # regression guard: no --als at all must stay exactly as before (no mention at all)
        cmd = [sys.executable, str(SCRIPT), "analyze", "/x/fake.mp3", "--dry-run"]
        out = subprocess.run(cmd, check=True, text=True, capture_output=True)
        combined = out.stdout + out.stderr
        self.assertNotIn("map_stems", combined)


# ── findings 1 & 5: _complete_run verify-by-deed + no stdout leak ──────────────────────────

class CompleteRunVerifyByDeedAndStdoutIsolation(unittest.TestCase):
    """_complete_run (the nested re-measure + rebuild used by the default backfill, RC-INV-13a):

    Finding 1 (G-INV-11 / RC-INV-13a): a nested `build` that exits 0 without actually depositing
    (cmd_build swallows DepositError and just prints 'library deposit skipped') must NOT cause
    the old library entry to be forgotten — deleting it before the replacement is confirmed on
    disk leaves the track with neither a valid old nor a valid new entry.

    Finding 5: the nested build subprocess must run with its stdout CAPTURED, never inherited —
    otherwise its own widget-path print leaks onto the caller's stdout after the requested run's
    path (cmd_build's stdout contract is exactly one path).

    subprocess.run is monkeypatched (only the two calls _complete_run makes: analyze then build)
    so these run instantly with no real re-analysis / Demucs / library.deposit_from_run."""

    def _seed_run(self, base, name, *, audio_path):
        run = Path(base) / name; run.mkdir(parents=True)
        (run / "run_meta.json").write_text(json.dumps(
            {"mode": "full", "track": name, "audio_path": audio_path}))
        return run

    def _seed_library(self, lib_root, run_dir, widget_name="w.html"):
        (lib_root / "widgets").mkdir(parents=True, exist_ok=True)
        (lib_root / "widgets" / widget_name).write_text("<html>old</html>")
        idx = {"entries": [{"track": "T", "mode": "full", "src_run_dir": str(run_dir),
                            "widget": widget_name}]}
        (lib_root / "index.json").write_text(json.dumps(idx))

    def _patch_subprocess(self, ta, new_run, *, build_returncode=0, build_stdout="",
                          deposit_into=None):
        """Return (fake_run, calls). deposit_into=(lib_root, new_run) makes the fake nested
        build write a fresh index entry for new_run, simulating a real successful deposit."""
        calls = []
        real_run = ta.subprocess.run

        def fake_run(cmd, **kw):
            calls.append((list(cmd), kw))
            if "analyze" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=json.dumps({"run_dir": str(new_run)}) + "\n", stderr="")
            if "build" in cmd:
                if deposit_into is not None:
                    lib_root, run_for_entry = deposit_into
                    idx = json.loads((lib_root / "index.json").read_text())
                    idx["entries"].append({"track": "T", "mode": "full",
                                           "src_run_dir": str(run_for_entry),
                                           "widget": "new.html"})
                    (lib_root / "index.json").write_text(json.dumps(idx))
                return subprocess.CompletedProcess(cmd, build_returncode, stdout=build_stdout,
                                                   stderr="")
            return real_run(cmd, **kw)  # pragma: no cover — _complete_run makes only 2 calls

        return fake_run, calls

    def test_nested_build_stdout_is_captured_not_inherited(self):
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                audio = Path(d) / "src.wav"; audio.write_bytes(b"\x00")
                old_run = self._seed_run(d, "old", audio_path=str(audio))
                new_run = Path(d) / "new"; new_run.mkdir()
                fake_run, calls = self._patch_subprocess(
                    ta, new_run, build_stdout="NESTED-WIDGET-PATH.html\n")
                real_run = ta.subprocess.run
                ta.subprocess.run = fake_run
                try:
                    ta._complete_run(str(old_run))
                finally:
                    ta.subprocess.run = real_run
                build_calls = [(c, kw) for c, kw in calls if "build" in c]
                self.assertEqual(len(build_calls), 1)
                _, kw = build_calls[0]
                self.assertTrue(kw.get("capture_output"),
                                "the nested build must run with capture_output=True — otherwise "
                                "its stdout is inherited and leaks onto the caller's (finding 5)")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_old_entry_kept_when_nested_build_exits_0_without_depositing(self):
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                lib_root = Path(os.environ["TRACK_COACH_LIBRARY"])
                audio = Path(d) / "src.wav"; audio.write_bytes(b"\x00")
                old_run = self._seed_run(d, "old", audio_path=str(audio))
                new_run = Path(d) / "new"; new_run.mkdir()
                self._seed_library(lib_root, old_run)
                # nested build exits 0 (DepositError swallowed) but never writes a new index entry
                fake_run, _ = self._patch_subprocess(ta, new_run, build_returncode=0)
                real_run = ta.subprocess.run
                ta.subprocess.run = fake_run
                try:
                    ta._complete_run(str(old_run))
                finally:
                    ta.subprocess.run = real_run

                idx = json.loads((lib_root / "index.json").read_text())
                self.assertEqual(len(idx["entries"]), 1,
                                 "the old entry must be KEPT — the replacement never deposited "
                                 "(G-INV-11 finding 1)")
                self.assertEqual(idx["entries"][0]["src_run_dir"], str(old_run))
                self.assertTrue((lib_root / "widgets" / "w.html").exists(),
                                "the old widget file must survive an unconfirmed replacement")
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]

    def test_old_entry_forgotten_once_replacement_confirmed_in_index(self):
        # positive case: unchanged happy path once the deposit is confirmed by deed
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                lib_root = Path(os.environ["TRACK_COACH_LIBRARY"])
                audio = Path(d) / "src.wav"; audio.write_bytes(b"\x00")
                old_run = self._seed_run(d, "old", audio_path=str(audio))
                new_run = Path(d) / "new"; new_run.mkdir()
                self._seed_library(lib_root, old_run)
                fake_run, _ = self._patch_subprocess(
                    ta, new_run, build_returncode=0, deposit_into=(lib_root, new_run))
                real_run = ta.subprocess.run
                ta.subprocess.run = fake_run
                try:
                    ta._complete_run(str(old_run))
                finally:
                    ta.subprocess.run = real_run

                idx = json.loads((lib_root / "index.json").read_text())
                srcs = {str(Path(e["src_run_dir"]).resolve()) for e in idx["entries"]}
                self.assertNotIn(str(old_run.resolve()), srcs,
                                 "the old, now-superseded entry must be forgotten once the "
                                 "replacement is confirmed deposited")
                self.assertIn(str(new_run.resolve()), srcs)
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


class RunDepositedHelper(unittest.TestCase):
    """_run_deposited: the verify-by-deed check _complete_run uses before forgetting an old
    entry — does the library index carry an entry whose src_run_dir resolves to this run dir?"""

    def test_true_when_index_has_a_matching_entry(self):
        import track_analyzer as ta
        with tempfile.TemporaryDirectory() as d:
            os.environ["TRACK_COACH_LIBRARY"] = str(Path(d) / "lib")
            try:
                lib_root = Path(os.environ["TRACK_COACH_LIBRARY"])
                lib_root.mkdir(parents=True)
                run = Path(d) / "run"; run.mkdir()
                other = Path(d) / "other"; other.mkdir()
                (lib_root / "index.json").write_text(json.dumps(
                    {"entries": [{"src_run_dir": str(run), "widget": "w.html"}]}))
                self.assertTrue(ta._run_deposited(run))
                self.assertFalse(ta._run_deposited(other))
            finally:
                del os.environ["TRACK_COACH_LIBRARY"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
