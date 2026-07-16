#!/usr/bin/env python3
"""Fixes from docs/COMMAND_AUDIT_2026-07-16.md, all inside scripts/catalog.py:

  1. G-INV-14 degradation message: a FULL run whose src_run_dir is gone must read
     "analysis data not available — re-analyse to restore" in BOTH similarity cells (not the
     quick-mode "full analysis only"), and that state must count as a SHOWN (non-shed) column.
  2. G-INV-16b/22 migrate/missing banners must count DISTINCT TRACKS, not entries.
  3. build_catalog's output_root must be library.output_root() (honours $TRACK_COACH_ROOT /
     $TRACK_COACH_LIBRARY), not root.parent.
  4. The stale-analysis chip's `var(--warn)` token must actually be defined in the catalog :root.
  5. `_siblings_cell` / `_row` no longer carry the dead, unread `href_map` parameter.

Pure render-level checks (1a, 4, 5) need no filesystem; build_catalog-level checks (1b, 2, 3)
build a temp library + index.json, mirroring tests/test_storage_relocation.py's pattern.
Methodology: spec → prove → matrix → test → code. NEVER loosen a test to make code pass.
"""
import inspect
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import library  # noqa: E402
import catalog  # noqa: E402


def _e(track, sha="sha1", stamp="2026-06-20_2100", mtime=1000, **kw):
    e = {"track": track, "audio_sha": sha, "stamp": stamp, "audio_mtime": mtime,
         "widget": f"{track}-{stamp}.html", "mode": "full",
         "bpm": 123, "arc": [0.1, 0.5, 1.0],
         "title": track.replace("_", " "),
         "_leans": [], "_siblings": []}
    e.update(kw)
    return e


class _EnvIsolated(unittest.TestCase):
    """Saves/restores $TRACK_COACH_ROOT and $TRACK_COACH_LIBRARY around a test — build_catalog now
    reads TRACK_COACH_ROOT via library.output_root() (finding 3), so a test that cares about the
    banner classification must pin both explicitly rather than ride whatever the host has set."""

    def setUp(self):
        self._saved_root = os.environ.pop("TRACK_COACH_ROOT", None)
        self._saved_lib = os.environ.pop("TRACK_COACH_LIBRARY", None)

    def tearDown(self):
        os.environ.pop("TRACK_COACH_ROOT", None)
        os.environ.pop("TRACK_COACH_LIBRARY", None)
        if self._saved_root is not None:
            os.environ["TRACK_COACH_ROOT"] = self._saved_root
        if self._saved_lib is not None:
            os.environ["TRACK_COACH_LIBRARY"] = self._saved_lib


GONE_MSG = "analysis data not available — re-analyse to restore"


# ─── Finding 1: G-INV-14 degradation message ─────────────────────────────────

class SourceGoneReasonRenderLevel(unittest.TestCase):
    """Pure render-level: a FULL row carrying the new R_SOURCE_GONE reason reads the SPEC phrase in
    BOTH similarity cells, never the quick-mode 'full analysis only' (which would self-contradict the
    row's own 'full' mode chip)."""

    def _page(self):
        return catalog.render_catalog_html(
            [_e("Gone", mode="full",
                _lean_reason=catalog.R_SOURCE_GONE, _sib_reason=catalog.R_SOURCE_GONE)])

    def test_lean_cell_reads_ginv14_phrase(self):
        page = self._page()
        self.assertIn(GONE_MSG, page, "G-INV-14: the exact SPEC phrase must appear")

    def test_both_cells_carry_the_phrase(self):
        page = self._page()
        self.assertEqual(page.count(GONE_MSG), 2,
                         "both the reference and own-library cells must show the phrase")

    def test_never_reads_full_analysis_only_for_a_full_row(self):
        page = self._page()
        self.assertNotIn("full analysis only", page,
                         "a FULL row that lost its source is NOT the quick-mode case (G-INV-14)")

    def test_mode_chip_still_reads_full(self):
        # The row's own "full" Analysis chip must not be contradicted by the message.
        page = self._page()
        self.assertIn('class="mode full"', page)

    def test_quick_row_is_unaffected_still_reads_full_analysis_only(self):
        # mode==quick keeps R_QUICK unchanged even if a caller injected _src_gone-style state —
        # exercised at the build_catalog level below; here we pin the pure-render contract: a quick
        # row with no explicit reason still reads its own phrase, never the G-INV-14 one.
        # A companion full row with a computed reason keeps the column from being shed by the
        # presence gate (D-INV-22) — an all-quick library sheds the column entirely, same as the
        # existing LeanCellEmptyCopy.test_quick_row_reads_full_analysis_only pattern.
        page = catalog.render_catalog_html(
            [_e("F", "h0", "2026-01-02_0900", 2000, mode="full"),
             _e("Q", "h1", "2026-01-01_0900", 1000, mode="quick")])
        self.assertIn("full analysis only", page)
        self.assertNotIn(GONE_MSG, page)


class SourceGoneCountsAsShownState(unittest.TestCase):
    """The new reason must be in the presence-gate sets (D-INV-22 / F-INV-7), so an all-gone-source
    library still shows the columns instead of shedding them as if nothing were ever computed."""

    def test_reason_in_lean_presence_gate(self):
        self.assertIn(catalog.R_SOURCE_GONE, catalog._LEAN_RESULT_REASONS)

    def test_reason_in_sib_presence_gate(self):
        self.assertIn(catalog.R_SOURCE_GONE, catalog._SIB_RESULT_REASONS)

    def test_column_not_shed_when_every_row_is_source_gone(self):
        page = catalog.render_catalog_html(
            [_e("Gone", mode="full",
                _lean_reason=catalog.R_SOURCE_GONE, _sib_reason=catalog.R_SOURCE_GONE)])
        self.assertIn("Leans toward", page, "the reference column must not be shed")
        self.assertIn("Similar in library", page, "the own-library column must not be shed")


class SourceGoneBuildCatalogLevel(_EnvIsolated):
    """build_catalog-level: a FULL entry whose src_run_dir does not exist on disk gets the new
    reason injected (not R_QUICK), so the rendered page carries the G-INV-14 phrase."""

    def test_full_entry_missing_src_run_dir_reads_ginv14_phrase(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root = tmp / "library"
            widgets_dir = lib_root / "widgets"
            widgets_dir.mkdir(parents=True)
            widget_name = "Gone_Track__v1__2026-01-01_1000.html"
            (widgets_dir / widget_name).write_text("<html>widget</html>")
            # src_run_dir intentionally never created on disk
            src_dir = tmp / "ableton" / "proj" / "track-coach-output" / "Gone_Track" / "v1__2026-01-01_1000"
            entry = {"track": "Gone_Track", "version": "v1", "stamp": "2026-01-01_1000",
                     "widget": widget_name, "mode": "full",
                     "src_run_dir": str(src_dir), "src_widget": "analysis_widget.html",
                     "deposited_at": "2026-01-01T10:00:00+00:00"}
            (lib_root / "index.json").write_text(json.dumps({"entries": [entry]}))
            os.environ["TRACK_COACH_ROOT"] = td  # pin: everything here reads as "in root" (finding 3)

            html_text = catalog.build_catalog(root=lib_root).read_text()
            self.assertIn(GONE_MSG, html_text,
                         "a full run whose src_run_dir vanished must show the G-INV-14 phrase")
            self.assertNotIn("full analysis only", html_text,
                             "must not be mislabeled as the quick-mode case")

    def test_quick_entry_missing_src_run_dir_still_reads_full_analysis_only(self):
        """mode==quick must win over the gone-source state (unchanged per the audit's fix note):
        two entries share the identical gone-src_run_dir condition, only `mode` differs, and each
        must land on its OWN reason — proving precedence, not just "some reason got picked".
        (A second, unrelated full+gone entry also keeps the presence gate from shedding the column,
        so the quick row's cell is actually visible to assert on — see LeanCellEmptyCopy in
        test_catalog.py for the same 'need a companion row' shape.)"""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lib_root = tmp / "library"
            widgets_dir = lib_root / "widgets"
            widgets_dir.mkdir(parents=True)
            entries = []
            for track, mode, stamp in (("Gone_Full", "full", "2026-01-02_0900"),
                                       ("Gone_Quick", "quick", "2026-01-01_0900")):
                widget_name = f"{track}__v1__{stamp}.html"
                (widgets_dir / widget_name).write_text("<html>widget</html>")
                src_dir = tmp / "ableton" / "proj" / "track-coach-output" / track / f"v1__{stamp}"
                entries.append({"track": track, "version": "v1", "stamp": stamp,
                                "widget": widget_name, "mode": mode,
                                "src_run_dir": str(src_dir), "src_widget": "analysis_widget.html",
                                "deposited_at": "2026-01-01T10:00:00+00:00"})
            (lib_root / "index.json").write_text(json.dumps({"entries": entries}))
            os.environ["TRACK_COACH_ROOT"] = td

            html_text = catalog.build_catalog(root=lib_root).read_text()
            self.assertIn("full analysis only", html_text, "the quick row keeps its own phrase")
            self.assertIn(GONE_MSG, html_text, "the full+gone row gets the G-INV-14 phrase")


# ─── Finding 2: migrate/missing banners count DISTINCT TRACKS ────────────────

class BannerCountsDistinctTracks(_EnvIsolated):
    """One track deposited from THREE outside-root versions must read '1 track', never '3 tracks'
    (G-INV-16b/22 — the old code incremented once per ENTRY)."""

    def test_one_track_three_outside_entries_reads_one_track(self):
        with tempfile.TemporaryDirectory() as td_lib, tempfile.TemporaryDirectory() as td_out:
            lib_root = Path(td_lib) / "library"
            widgets_dir = lib_root / "widgets"
            widgets_dir.mkdir(parents=True)
            entries = []
            for i in range(3):
                stamp = f"2026-01-0{i + 1}_1000"
                outside_dir = Path(td_out) / f"proj{i}" / "TrackA" / f"v{i + 1}__{stamp}"
                outside_dir.mkdir(parents=True)  # exists on disk -> "to move" (migrate), not junk
                w = f"TrackA__v{i + 1}__{stamp}.html"
                (widgets_dir / w).write_text("<html>x</html>")
                entries.append({"track": "TrackA", "version": f"v{i + 1}", "stamp": stamp,
                                "widget": w, "mode": "full", "audio_sha": f"sha{i}",
                                "src_run_dir": str(outside_dir),
                                "deposited_at": f"2026-01-0{i + 1}T10:00:00+00:00"})
            (lib_root / "index.json").write_text(json.dumps({"entries": entries}))
            os.environ["TRACK_COACH_ROOT"] = td_lib  # td_out is a SIBLING tempdir -> genuinely outside

            html_text = catalog.build_catalog(root=lib_root).read_text()
            self.assertIn("1 track", html_text,
                         "one track with 3 outside-root entries must be counted ONCE (G-INV-16b)")
            self.assertNotIn("3 track", html_text,
                             "the banner must not count per-entry")

    def test_one_track_three_gone_entries_reads_one_track_missing(self):
        """Same distinct-count fix applies to the missing-source banner (G-INV-22 junk case)."""
        with tempfile.TemporaryDirectory() as td_lib, tempfile.TemporaryDirectory() as td_out:
            lib_root = Path(td_lib) / "library"
            widgets_dir = lib_root / "widgets"
            widgets_dir.mkdir(parents=True)
            entries = []
            for i in range(3):
                stamp = f"2026-01-0{i + 1}_1000"
                # NEVER created on disk -> "gone" (missing-banner / junk)
                gone_dir = Path(td_out) / f"proj{i}" / "TrackB" / f"v{i + 1}__{stamp}"
                w = f"TrackB__v{i + 1}__{stamp}.html"
                (widgets_dir / w).write_text("<html>x</html>")
                entries.append({"track": "TrackB", "version": f"v{i + 1}", "stamp": stamp,
                                "widget": w, "mode": "full", "audio_sha": f"shb{i}",
                                "src_run_dir": str(gone_dir),
                                "deposited_at": f"2026-01-0{i + 1}T10:00:00+00:00"})
            (lib_root / "index.json").write_text(json.dumps({"entries": entries}))
            os.environ["TRACK_COACH_ROOT"] = td_lib

            html_text = catalog.build_catalog(root=lib_root).read_text()
            self.assertIn("1 track", html_text)
            self.assertNotIn("3 track", html_text)
            self.assertIn('class="missing-banner"', html_text)


# ─── Finding 3: output_root must be library.output_root(), not root.parent ───

class OutputRootHonoursConfiguredOverride(_EnvIsolated):
    """$TRACK_COACH_ROOT / $TRACK_COACH_LIBRARY may point at DIFFERENT bases (the documented
    override, G-INV-7). build_catalog's banner classification must follow TRACK_COACH_ROOT, not
    silently derive from wherever the library happens to sit (`root.parent`)."""

    def test_in_root_run_not_falsely_flagged_when_library_lives_elsewhere(self):
        with tempfile.TemporaryDirectory() as td_root, tempfile.TemporaryDirectory() as td_lib_base:
            # The library is deliberately NOT under td_root, so root.parent != TRACK_COACH_ROOT —
            # this is exactly the divergence the bug produced.
            lib_root = Path(td_lib_base) / "somewhere" / "library"
            widgets_dir = lib_root / "widgets"
            widgets_dir.mkdir(parents=True)

            inside_dir = Path(td_root) / "projects" / "TrackA" / "v1__2026-01-01_1000"
            inside_dir.mkdir(parents=True)  # genuinely inside TRACK_COACH_ROOT
            w = "TrackA__v1__2026-01-01_1000.html"
            (widgets_dir / w).write_text("<html>a</html>")
            entry = {"track": "TrackA", "version": "v1", "stamp": "2026-01-01_1000",
                     "widget": w, "mode": "full", "src_run_dir": str(inside_dir),
                     "deposited_at": "2026-01-01T10:00:00+00:00"}
            (lib_root / "index.json").write_text(json.dumps({"entries": [entry]}))

            os.environ["TRACK_COACH_ROOT"] = td_root
            os.environ["TRACK_COACH_LIBRARY"] = str(lib_root)

            html_text = catalog.build_catalog(root=None).read_text()
            self.assertNotIn('<div class="migrate-banner">', html_text,
                             "an in-TRACK_COACH_ROOT run must not be flagged for migrate just "
                             "because the library lives elsewhere (G-INV-7 override)")
            self.assertNotIn('class="missing-banner"', html_text)

    def test_output_root_function_is_used_not_root_parent(self):
        # Direct source-level pin: build_catalog must call library.output_root(), so the buggy
        # assignment stays gone (belt-and-braces on top of the behavioural test above).
        src = inspect.getsource(catalog.build_catalog)
        self.assertIn("output_root = library.output_root()", src)
        self.assertNotIn("output_root = root.parent", src)


# ─── Finding 4: --warn design token ───────────────────────────────────────────

class WarnTokenDefined(unittest.TestCase):
    """The stale-analysis chip uses `color:var(--warn)`; PALETTE and the catalog :root must both
    actually define it, or the warning colour silently falls back to inherited (black-on-dark)."""

    def test_palette_has_warn_key(self):
        self.assertIn("warn", catalog.PALETTE)
        self.assertEqual(catalog.PALETTE["warn"], "#ffb454",
                         "must match the widget canon --warn value (DS-INV-2)")

    def test_root_block_defines_warn(self):
        page = catalog.render_catalog_html([])
        root_block = re.search(r":root\{[^}]*\}", page).group(0)
        self.assertIn("--warn:", root_block, "--warn must be defined in the catalog :root")

    def test_stale_chip_var_warn_is_not_dangling(self):
        # Every var(--x) the CSS references should resolve to a :root definition somewhere in the
        # same page — at minimum this must hold for --warn (the dangling one this finding fixes).
        page = catalog.render_catalog_html([])
        root_block = re.search(r":root\{[^}]*\}", page).group(0)
        defined = set(re.findall(r"--([\w-]+):", root_block))
        self.assertIn("warn", defined)
        self.assertIn("color:var(--warn)", page, "the .stale rule must still reference the token")


# ─── Finding 5: dead href_map parameter removed ──────────────────────────────

class HrefMapDeadParamRemoved(unittest.TestCase):
    """`_siblings_cell` never read its `href_map` parameter (sibling chips use #row-<slug> anchors);
    the dead parameter + the `_href_map` construction that fed it must be gone, with no behaviour
    change to the existing catalog output."""

    def test_siblings_cell_signature_has_no_href_map(self):
        params = list(inspect.signature(catalog._siblings_cell).parameters)
        self.assertNotIn("href_map", params)
        self.assertEqual(params[:2], ["siblings", "title_map"])

    def test_row_signature_has_no_href_map(self):
        params = list(inspect.signature(catalog._row).parameters)
        self.assertNotIn("href_map", params)

    def test_siblings_cell_still_works_with_new_signature(self):
        from similarity_columns import Sibling, CLOSE
        sib = Sibling(track="B_Track", level=CLOSE, n_shared=12)
        td = catalog._siblings_cell([sib], {"B_Track": "B Track"})
        self.assertIn("B Track", td)
        self.assertIn('href="#row-B_Track"', td)

    def test_render_catalog_html_unaffected_by_the_removal(self):
        # No behaviour change: a normal render still emits sibling chips correctly end to end.
        # B_Track's OWN title link legitimately points at its widget (file:///runs/B/widget_B.html);
        # what must NOT happen is the SIBLING CHIP (in A_Track's row) carrying that same widget path.
        from similarity_columns import Sibling, CLOSE
        sib = Sibling(track="B_Track", level=CLOSE, n_shared=12)
        page = catalog.render_catalog_html([
            _e("A_Track", _siblings=[sib]),
            _e("B_Track", src_run_dir="/runs/B", src_widget="widget_B.html"),
        ])
        chip = re.search(r'<a class="sib-chip"[^>]*>', page)
        self.assertIsNotNone(chip, "the injected sibling must render a chip")
        self.assertIn('href="#row-B_Track"', chip.group(0))
        self.assertNotIn("file://", chip.group(0),
                         "the sibling chip must never carry the widget path (D-INV-28)")


if __name__ == "__main__":
    unittest.main()
