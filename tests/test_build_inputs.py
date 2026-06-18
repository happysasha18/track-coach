#!/usr/bin/env python3
"""Rebuild-preservation tests — a bare `build` must not drop what a prior build set.

The incident: re-rendering an existing run with `track_analyzer.py build` (no flags) silently
replaced the human title with the raw folder name, and could drop the narrative. These assert
`resolve_build_inputs` keeps title / verdict / narrative sticky. Pure-function, no deps, instant.
"""
import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from track_analyzer import resolve_build_inputs, pick_inherit_source, inherit_prior_read  # noqa: E402


class TitleVerdict(unittest.TestCase):
    def test_bare_build_reuses_persisted_title(self):
        meta = {"track": "Total_Reboot_Foo", "title": "Total Reboot — Foo (2026)"}
        with tempfile.TemporaryDirectory() as d:
            r = resolve_build_inputs(meta, d)          # no flags = the bug's trigger
        self.assertEqual(r["title"], "Total Reboot — Foo (2026)")

    def test_bare_build_reuses_persisted_verdict(self):
        meta = {"track": "X", "verdict": "Dense club build, 123 BPM."}
        with tempfile.TemporaryDirectory() as d:
            r = resolve_build_inputs(meta, d)
        self.assertEqual(r["verdict"], "Dense club build, 123 BPM.")

    def test_explicit_flag_overrides_meta(self):
        meta = {"title": "old", "verdict": "old v"}
        with tempfile.TemporaryDirectory() as d:
            r = resolve_build_inputs(meta, d, title="new", verdict="new v")
        self.assertEqual((r["title"], r["verdict"]), ("new", "new v"))

    def test_title_derived_when_no_persisted_title(self):
        meta = {"track": "Total_Reboot_Bar", "track_version": "v2"}
        with tempfile.TemporaryDirectory() as d:
            r = resolve_build_inputs(meta, d)
        self.assertEqual(r["title"], "Total_Reboot_Bar v2")

    def test_no_title_anywhere_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            r = resolve_build_inputs({}, d)
        self.assertIsNone(r["title"])


class Narrative(unittest.TestCase):
    def test_narrative_md_in_run_dir_is_picked_up(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "narrative.md").write_text("# read\nbody")
            r = resolve_build_inputs({}, d)
        self.assertEqual(Path(r["narrative"]).name, "narrative.md")

    def test_no_narrative_md_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            r = resolve_build_inputs({}, d)
        self.assertIsNone(r["narrative"])

    def test_explicit_narrative_flag_wins(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "narrative.md").write_text("auto")
            r = resolve_build_inputs({}, d, narrative="/some/other/read.md")
        self.assertEqual(r["narrative"], "/some/other/read.md")


class InheritPriorRead(unittest.TestCase):
    """Re-analysing a track must carry the prior hand-written read forward, not drop it."""

    def test_picks_most_recent_sibling_with_narrative(self):
        dirs = ["2026-06-17_2147", "2026-06-18_0748", "2026-06-18_0930"]
        have = {"2026-06-17_2147", "2026-06-18_0930"}  # 0748 has none
        src = pick_inherit_source(dirs, "2026-06-18_0748", lambda d: d in have)
        self.assertEqual(src, "2026-06-18_0930")

    def test_excludes_current_run(self):
        dirs = ["2026-06-18_0748"]
        src = pick_inherit_source(dirs, "2026-06-18_0748", lambda d: True)
        self.assertIsNone(src)

    def test_none_when_no_sibling_has_a_narrative(self):
        dirs = ["a", "b"]
        self.assertIsNone(pick_inherit_source(dirs, "c", lambda d: False))

    def test_end_to_end_copies_narrative_and_seeds_meta(self):
        # mirrors the real incident: new run dir, prior run holds the read
        with tempfile.TemporaryDirectory() as base:
            track = Path(base) / "Total_Reboot_X"
            prior = track / "2026-06-17_2147"; prior.mkdir(parents=True)
            (prior / "narrative.md").write_text("# the good read\nbody")
            (prior / "run_meta.json").write_text(
                '{"title": "Total Reboot — X (2026)", "verdict": "v"}')
            new = track / "2026-06-18_0748"; new.mkdir()
            src = inherit_prior_read(new)
            self.assertEqual(Path(src).name, "2026-06-17_2147")
            self.assertEqual((new / "narrative.md").read_text(), "# the good read\nbody")
            import json
            self.assertEqual(json.loads((new / "run_meta.json").read_text())["title"],
                             "Total Reboot — X (2026)")

    def test_does_not_clobber_a_read_the_new_run_already_has(self):
        with tempfile.TemporaryDirectory() as base:
            track = Path(base) / "T"
            prior = track / "2026-06-17_2147"; prior.mkdir(parents=True)
            (prior / "narrative.md").write_text("OLD")
            new = track / "2026-06-18_0748"; new.mkdir()
            (new / "narrative.md").write_text("FRESH")
            inherit_prior_read(new)
            self.assertEqual((new / "narrative.md").read_text(), "FRESH")


if __name__ == "__main__":
    unittest.main()
