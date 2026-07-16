#!/usr/bin/env python3
"""test_selection_audit.py — version/run selection correctness (audit root class 5).

Each is a code-vs-spec defect where the store picked the wrong version, run, widget, or tier:
  * prune-versions ordered by a dead ``audio_mtime`` key deposits never stored, so "newest" meant
    most-recently-ANALYSED and could delete the newest bounce (SPEC:1367 "by audio mtime / stamp").
  * a library mixing entries WITH and WITHOUT audio_mtime crashed the version sort (int vs str).
  * remove / prune-versions ignored the same-song alias map, so they operated on raw slugs and
    disagreed with the ONE catalog row the user sees (H-INV-2 / G-INV-23).
  * remove by the synthesized version label (v1..vN) reported "nothing found".
  * deposit --widget defaulted to the lexicographically-last widget, not the newest (a two-digit
    version made it deposit a stale build).
  * a corrupt run_meta.json failed OPEN past the reference/synthetic deposit gates (meta={}).
  * gc's best-undeposited tiebreak (name) diverged from the RC-INV-9 selector's (mtime), so gc
    could prune the exact run the read layer reads from (G-INV-15).
  * restore never restored the projects/ tier from a --full snapshot (H-INV-9 round-trip).

Pure stdlib unittest.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import library  # noqa: E402


def _entry(track, stamp, *, sha=None, mtime=None, mode="full", widget=None, version=""):
    e = {"track": track, "stamp": stamp, "mode": mode, "version": version,
         "widget": widget or f"{track}_{stamp}.html",
         "audio_sha": sha if sha is not None else f"sha-{track}-{stamp}"}
    if mtime is not None:
        e["audio_mtime"] = mtime
    return e


class VersionOrderTypeStable(unittest.TestCase):
    def test_mixed_mtime_and_stamp_does_not_crash_and_orders_by_mtime(self):
        """A library where one bounce carries audio_mtime and another only a stamp must sort
        without a TypeError (int vs str), newest-by-mtime last (oldest→newest)."""
        older = _entry("T", "2026-07-16_0900", sha="A", mtime=1000)
        newer = _entry("T", "2026-07-15_0800", sha="B", mtime=2000)  # analysed EARLIER, bounced LATER
        legacy = _entry("T", "2026-07-10_0700", sha="C")  # no audio_mtime
        versions = library.group_versions([newer, older, legacy])["T"]
        # newest first for display; the highest audio_mtime (B=2000) is newest
        self.assertEqual(versions[0]["sha"], "B")

    def test_prune_keeps_newest_bounce_by_mtime_not_analysis_time(self):
        """prune-versions --keep 1 must keep the newest AUDIO bounce, even if an older bounce was
        re-analysed more recently (a later stamp)."""
        newest_bounce = _entry("T", "2026-07-01_0000", sha="NEW", mtime=5000)
        old_bounce_reanalysed = _entry("T", "2026-07-16_2359", sha="OLD", mtime=1000)
        keep, drop = library.prune_versions_plan([old_bounce_reanalysed, newest_bounce], 1)
        kept_shas = {e["audio_sha"] for e in keep}
        self.assertEqual(kept_shas, {"NEW"}, "keep the newest bounce by mtime, not by analysis time")
        self.assertEqual({e["audio_sha"] for e in drop}, {"OLD"})


class RunMetricsStoresMtime(unittest.TestCase):
    def test_audio_mtime_carried_onto_entry(self):
        meta = {"audio_sha256": "abc", "audio_mtime": 1234567}
        m = library.run_metrics({}, meta)
        self.assertEqual(m.get("audio_mtime"), 1234567,
                         "run_metrics must carry audio_mtime so prune/order key is live")


class AliasAwareVerbs(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.lib = Path(self._tmp) / "library"
        (self.lib / "widgets").mkdir(parents=True)
        os.environ["TRACK_COACH_LIBRARY"] = str(self.lib)

    def tearDown(self):
        os.environ.pop("TRACK_COACH_LIBRARY", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _seed(self, entries, aliases=None):
        for e in entries:
            (self.lib / "widgets" / e["widget"]).write_text("<html>w</html>")
        library.save_index(self.lib, {"entries": entries})
        if aliases:
            library.save_aliases(self.lib, aliases)

    def test_remove_canonical_takes_the_folded_alias_entries(self):
        """`remove b` where a→b must drop a's folded bounces too (one visible row b)."""
        a = _entry("a", "s1", sha="X")
        b = _entry("b", "s2", sha="Y")
        self._seed([a, b], aliases={"a": "b"})
        args = types.SimpleNamespace(track="b", version=None, apply=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_remove(args)
        left = library.load_index(self.lib)["entries"]
        self.assertEqual(left, [], "removing canonical row b must also drop a's folded entry")

    def test_prune_versions_groups_by_canonical_row(self):
        """One song aliased a→b shows ONE row with 2 versions; prune --keep 1 drops the oldest."""
        a = _entry("a", "s1", sha="OLD", mtime=1000)
        b = _entry("b", "s2", sha="NEW", mtime=2000)
        self._seed([a, b], aliases={"a": "b"})
        keep, drop = library.prune_versions_plan([a, b], 1, library.load_aliases(self.lib))
        self.assertEqual({e["audio_sha"] for e in keep}, {"NEW"})
        self.assertEqual({e["audio_sha"] for e in drop}, {"OLD"})

    def test_remove_by_synthesized_label(self):
        """`remove T v1` (the oldest label the catalog shows) removes that bounce's group."""
        v1 = _entry("T", "s1", sha="OLD", mtime=1000)
        v2 = _entry("T", "s2", sha="NEW", mtime=2000)
        self._seed([v1, v2])
        args = types.SimpleNamespace(track="T", version="v1", apply=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_remove(args)
        left = {e["audio_sha"] for e in library.load_index(self.lib)["entries"]}
        self.assertEqual(left, {"NEW"}, "remove T v1 must drop the oldest bounce, keep the newest")


class DepositWidgetNewest(unittest.TestCase):
    def test_default_widget_is_newest_by_mtime(self):
        """_cmd_deposit's default --widget must hand deposit_from_run the newest-by-mtime widget,
        not the lexicographically-last one (a two-digit version makes v0.10.1 < v0.9.22)."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        run = Path(tmp) / "run"
        run.mkdir()
        (run / "run_meta.json").write_text(json.dumps({"track": "T", "mode": "full"}))
        stale = run / "analysis_widget_v0.9.22.html"
        fresh = run / "analysis_widget_v0.10.1.html"  # lexicographically SMALLER, but newer
        stale.write_text("stale")
        fresh.write_text("fresh")
        os.utime(stale, (1000, 1000))
        os.utime(fresh, (2000, 2000))
        seen = {}
        orig = library.deposit_from_run

        def spy(run_dir, widget_path, meta):
            seen["widget"] = Path(widget_path)
            raise SystemExit("stop after selection")  # short-circuit the heavy validity/deposit

        library.deposit_from_run = spy
        self.addCleanup(setattr, library, "deposit_from_run", orig)
        args = types.SimpleNamespace(run_dir=str(run), widget=None)
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                library._cmd_deposit(args)
        self.assertEqual(seen.get("widget", Path()).name, fresh.name,
                         "the default --widget must be newest by mtime")


class DepositCorruptMetaFailsClosed(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.lib = Path(self._tmp) / "library"
        (self.lib / "widgets").mkdir(parents=True)
        os.environ["TRACK_COACH_LIBRARY"] = str(self.lib)

    def tearDown(self):
        os.environ.pop("TRACK_COACH_LIBRARY", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_corrupt_run_meta_refuses_deposit(self):
        run = Path(self._tmp) / "run"
        run.mkdir()
        (run / "analysis_widget.html").write_text("<html>w</html>")
        (run / "run_meta.json").write_text("{ this is not json")  # torn mid-write
        args = types.SimpleNamespace(run_dir=str(run), widget=None)
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                library._cmd_deposit(args)


class GcBestUndepositedMtimeTiebreak(unittest.TestCase):
    def test_tiebreak_is_mtime_matching_rc_inv_9(self):
        """On equal result counts, gc must keep the run newest_run reads from (mtime tiebreak)."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        slug = Path(tmp) / "slug"
        older_name_newer_mtime = slug / "2026-07-10_1200"  # sorts FIRST by name, NEWER mtime
        newer_name_older_mtime = slug / "2026-07-12_0900"  # sorts LAST by name, OLDER mtime
        for d in (older_name_newer_mtime, newer_name_older_mtime):
            d.mkdir(parents=True)
            (d / "result_core.json").write_text("{}")
        os.utime(newer_name_older_mtime, (1000, 1000))
        os.utime(older_name_newer_mtime, (2000, 2000))
        best = library._best_undeposited_run(slug, set())
        self.assertEqual(best, older_name_newer_mtime,
                         "gc must keep the newest-by-mtime run, matching run_dir.newest_run")


class RestoreFullProjectsTier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.base = Path(self._tmp) / "root"
        (self.base / "backups").mkdir(parents=True)
        os.environ["TRACK_COACH_ROOT"] = str(self.base)

    def tearDown(self):
        os.environ.pop("TRACK_COACH_ROOT", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_full_snapshot_restores_projects(self):
        snap = self.base / "backups" / "2026-07-16_120000"
        (snap / "library").mkdir(parents=True)
        (snap / "library" / "index.json").write_text('{"entries": []}')
        (snap / "projects" / "T" / "run").mkdir(parents=True)
        (snap / "projects" / "T" / "run" / "result_core.json").write_text("{}")
        (snap / ".backup_ok").write_text("ok")
        args = types.SimpleNamespace(base=str(self.base), stamp="2026-07-16_120000",
                                     apply=True, force=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            library._cmd_restore(args)
        self.assertTrue((self.base / "projects" / "T" / "run" / "result_core.json").exists(),
                        "a --full snapshot must restore the projects/ scratch tier (H-INV-9)")


if __name__ == "__main__":
    unittest.main()
