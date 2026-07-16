#!/usr/bin/env python3
"""Red-first regression tests for the three run_dir.py findings in
docs/COMMAND_AUDIT_2026-07-16.md (§ cmd_resume slug-collision, § dead collision
warning, § non-atomic index.json / silent zeroing).

All tests use tmp dirs. They NEVER touch ~/.track-coach/ (the real library/projects).
"""
import contextlib
import io
import json
import sys
import types
import unittest
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_dir      # noqa: E402


def _fake_args(**kw):
    ns = types.SimpleNamespace(base=None, als=None, track_version=None, mode="full")
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"FAKE")
    return path


# ─── Finding 1: cmd_resume ignores slug-collision disambiguation (G-INV-2b) ──

class ResumeSlugCollision(unittest.TestCase):
    """cmd_resume must resolve the slug the same way init does (walk base_slug,
    base_slug-2, ... matching _stored_identity), never co-mingling two different
    tracks that happen to slug the same."""

    def test_resume_finds_own_slug2_slot_not_track_a(self):
        """After init a/My_Track.wav (slug My_Track) and init b/My_Track.wav
        (slug My_Track-2), resume --audio b/My_Track.wav must report track B's
        run, never track A's."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            audio_a = _touch(Path(td) / "a" / "My_Track.wav")
            audio_b = _touch(Path(td) / "b" / "My_Track.wav")
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio_a), base=str(base)))
                run_dir.cmd_init(_fake_args(audio=str(audio_b), base=str(base)))

            slug = run_dir.slugify("My_Track.wav")
            resolved_base = base.resolve()
            root_a = resolved_base / slug
            root_b = resolved_base / f"{slug}-2"
            self.assertTrue(root_a.exists())
            self.assertTrue(root_b.exists(), "expected the -2 slot to be created for track B")

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                run_dir.cmd_resume(_fake_args(audio=str(audio_b), base=str(base)))
            payload = json.loads(out.getvalue().strip().splitlines()[-1])
            reported_run = Path(payload["run_dir"])
            self.assertTrue(
                str(reported_run).startswith(str(root_b)),
                f"resume --audio b/My_Track.wav returned {reported_run}, "
                f"which is not under track B's root {root_b} (co-mingled with track A)",
            )

    def test_resume_reports_no_earlier_run_when_no_slot_matches(self):
        """A brand-new track whose slug collides with an existing different track,
        but has no run of its own yet, must report 'no earlier run' — not track A's."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            audio_a = _touch(Path(td) / "a" / "My_Track.wav")
            audio_c = _touch(Path(td) / "c" / "My_Track.wav")  # never init'd
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio_a), base=str(base)))

            out = io.StringIO()
            err = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                run_dir.cmd_resume(_fake_args(audio=str(audio_c), base=str(base)))
            last_line = out.getvalue().strip()
            self.assertEqual(last_line, "", "no matching run for track C — stdout path must be empty")
            self.assertIn("no earlier run", err.getvalue().lower())


# ─── Finding 2: the collision warning is never emitted (G-INV-2b) ───────────

class CollisionWarningEmitted(unittest.TestCase):
    """_resolve_slug's warn string must actually reach the caller (and cmd_init's
    stderr) on a real slug collision, instead of being hard-coded to None."""

    def test_resolve_slug_returns_warning_on_collision(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            audio1 = _touch(Path(td) / "project_a" / "My_Track.wav")
            audio2 = _touch(Path(td) / "project_b" / "My_Track.wav")
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio1), base=str(base)))
            slug, warn = run_dir._resolve_slug(base, audio2.resolve(), None)
            self.assertEqual(slug, "My_Track-2")
            self.assertIsNotNone(warn, "_resolve_slug must return the built warning, not None")
            self.assertIn("My_Track", warn)

    def test_cmd_init_prints_warning_to_stderr_on_collision(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            audio1 = _touch(Path(td) / "project_a" / "My_Track.wav")
            audio2 = _touch(Path(td) / "project_b" / "My_Track.wav")
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio1), base=str(base)))
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                run_dir.cmd_init(_fake_args(audio=str(audio2), base=str(base)))
            self.assertIn("used by a different track", err.getvalue(),
                          "collision warning was never printed to stderr on real slug collision")


# ─── Finding 3: index.json non-atomic write + silent zeroing on corruption ───

class AtomicIndexWrite(unittest.TestCase):
    """update_index must write index.json atomically (tmp + os.replace) and must
    never silently zero an existing-but-corrupt index."""

    def test_no_tmp_file_left_behind_after_write(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            audio = _touch(Path(td) / "proj" / "My_Track.wav")
            with contextlib.redirect_stdout(io.StringIO()):
                run_dir.cmd_init(_fake_args(audio=str(audio), base=str(base)))
            leftovers = list(base.glob("index.json.tmp*"))
            self.assertEqual(leftovers, [], f"leftover tmp file(s) after atomic write: {leftovers}")
            self.assertTrue((base / "index.json").exists())

    def test_atomic_write_helper_uses_tmp_and_replace(self):
        """_atomic_write_text writes via a sibling tmp file + os.replace, never a
        direct write_text — verified by checking the tmp file is gone and content lands."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "index.json"
            run_dir._atomic_write_text(target, '{"runs": []}')
            self.assertTrue(target.exists())
            self.assertEqual(json.loads(target.read_text()), {"runs": []})
            self.assertEqual(list(Path(td).glob("*.tmp*")), [])

    def test_corrupt_existing_index_is_not_silently_zeroed(self):
        """A pre-existing, non-blank, unparseable index.json must be preserved (renamed
        aside) rather than silently discarded — the run history must not vanish."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            base.mkdir(parents=True)
            idx_path = base / "index.json"
            corrupt_text = '{"runs": [{"track": "Old_Track", "run_dir": "/x"}]  GARBAGE'
            idx_path.write_text(corrupt_text)

            audio = _touch(Path(td) / "proj" / "My_Track.wav")
            with contextlib.redirect_stdout(io.StringIO()) as out, \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                run_dir.cmd_init(_fake_args(audio=str(audio), base=str(base)))

            # The corrupt file must have been moved aside, not overwritten in place with the loss silent.
            corrupt_backups = list(base.glob("index.json.corrupt-*"))
            self.assertTrue(corrupt_backups, "corrupt index was not preserved under a .corrupt-<stamp> name")
            self.assertEqual(corrupt_backups[0].read_text(), corrupt_text,
                              "the moved-aside file must keep the original corrupt content")
            self.assertIn("unreadable", err.getvalue().lower(),
                          "no disclosure on stderr that the index was unreadable")

            # New index.json exists and is valid, with the new run recorded.
            new_idx = json.loads(idx_path.read_text())
            self.assertEqual(len(new_idx["runs"]), 1)

    def test_blank_or_absent_index_is_the_ordinary_fresh_case_no_warning(self):
        """No index.json at all is NOT a corruption case — no corrupt-aside file, no warning."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "projects"
            audio = _touch(Path(td) / "proj" / "My_Track.wav")
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                run_dir.cmd_init(_fake_args(audio=str(audio), base=str(base)))
            self.assertEqual(list(base.glob("index.json.corrupt-*")), [])
            self.assertNotIn("unreadable", err.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
