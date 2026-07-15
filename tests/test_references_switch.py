#!/usr/bin/env python3
"""The global show/hide-references switch (D-INV-6 / D-INV-23).

One NAMED switch, shared by the catalog's "Leans toward" reference column and a track's widget
reference plaque (#refPanel, which carries the "Leans toward ⟨artist⟩" chip). It is ONE global
PERSISTED flag that BOTH the catalog page AND a track's widget read — hiding references on either
page hides both; it is never a per-page toggle. What it hides: the catalog reference column
(header + cells) + the widget #refPanel (plaque chip + nested read/web). What it must NOT hide: the
§F own-library "Similar in library" column (D-INV-7) — always-on library data, never a reference.

Offline HTML widgets ⇒ "persisted global flag" = a fixed localStorage key read on every load, the
SAME key on both surfaces (`tc_refs_hidden`), riding a `refs-hidden` <body> class whose CSS hides
the reference surfaces. Default = SHOWN (flag absent → visible), so existing render/completeness
tests stay green.

These assert the wiring at string/DOM level (no browser): the control is emitted with the shared
key, the reference surfaces carry the hideable hook, and the §F own column does not. The live
browser check — that toggling actually hides #refPanel + the reference column and that the state
survives a reload via localStorage — is a follow-up for the headless harness (not run here to avoid
Chrome saturation).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import catalog  # noqa: E402
import build_widget  # noqa: E402
import similarity_columns as SC  # noqa: E402
import fingerprints as FP  # noqa: E402

# The one shared flag + hook — the SAME strings must appear on both surfaces (D-INV-23).
KEY = "tc_refs_hidden"
BODY_HOOK = "refs-hidden"


def _lean_entry(track="test_track"):
    """A catalog entry pre-injected with a synthetic Lean so the reference column renders (mirrors
    what build_catalog injects at runtime), which in turn makes the switch control render."""
    e = {"track": track, "audio_sha": "h1", "stamp": "2026-01-01_0900", "audio_mtime": 1000,
         "widget": f"{track}-2026-01-01_0900.html", "mode": "full", "title": "Test Track",
         "arc": [0.1, 0.5, 1.0], "energy": [0.1, 0.5, 1.0]}
    e["_leans"] = [SC.Lean(direction="Boards of Canada", level="close", runner=None, n_shared=10)]
    # A sibling so the §F own-library column also renders — we prove it is NOT hidden by the switch.
    e["_siblings"] = [SC.Sibling(track="other_track", level="mid", n_shared=8)]
    return e


class CatalogSwitch(unittest.TestCase):
    """D-INV-6/23 on the catalog surface — control, shared key, column hook, §F exemption."""

    def setUp(self):
        self.html = catalog.render_catalog_html([_lean_entry()])

    def test_1_control_and_shared_key_present(self):
        # (1) the switch control is emitted, and (2) it reads/writes the ONE shared localStorage key.
        self.assertIn('id="refsToggle"', self.html, "catalog must render the references switch control")
        self.assertIn(KEY, self.html,
                      f"catalog must read/write the shared flag key {KEY!r} (D-INV-23: one global flag)")
        # A named switch — the same label the widget uses.
        self.assertIn("Hide references", self.html)

    def test_2_reference_column_carries_hide_hook(self):
        # (2) the reference column — header AND cells — carries the hideable `c-lean` hook, and the
        # CSS actually hides it under the body flag.
        self.assertIn('class="c-lean"', self.html, "the 'Leans toward' HEADER must carry the c-lean hook")
        self.assertIn('class="c-sim c-lean"', self.html, "the reference CELLS must carry the c-lean hook")
        self.assertIn(f"body.{BODY_HOOK} .c-lean", self.html,
                      "CSS must hide the reference column when the body carries the refs-hidden flag")

    def test_3_own_library_column_not_under_hook(self):
        # (3) the §F own-library column renders but is NOT under the switch (D-INV-7).
        self.assertIn("c-sibs", self.html, "the §F own-library column must still render")
        self.assertNotIn(f"body.{BODY_HOOK} .c-sibs", self.html,
                         "the §F own-library column must NEVER be under the references switch (D-INV-7)")
        # And the own-library cells must not accidentally wear the reference hook.
        self.assertNotIn("c-sibs c-lean", self.html)
        self.assertNotIn("c-lean c-sibs", self.html)

    def test_4_default_is_shown(self):
        # Default = shown: the server-rendered markup carries NO refs-hidden body class, so existing
        # render/completeness gates see the full reference content.
        self.assertNotIn(f'class="{BODY_HOOK}', self.html)
        self.assertNotIn(f'body class="{BODY_HOOK}"', self.html)
        # The control starts un-pressed (shown); the JS corrects it from the stored flag on load.
        self.assertIn('aria-pressed="false"', self.html)

    def test_5_control_sheds_with_the_column(self):
        # The control renders wherever a reference surface renders — and NOWHERE else. An all-quick
        # library sheds the whole reference column (D-INV-22), so the switch sheds with it.
        eq = {"track": "q", "audio_sha": "h1", "stamp": "2026-01-01_0900", "audio_mtime": 1000,
              "widget": "q.html", "mode": "quick", "title": "Q", "arc": [0.1, 0.5]}
        h = catalog.render_catalog_html([eq])
        self.assertNotIn('id="refsToggle"', h, "no reference column ⇒ no switch (nothing to switch)")
        self.assertNotIn('class="c-lean"', h)


class WidgetSwitch(unittest.TestCase):
    """D-INV-6/23 on the widget surface — the plaque chip #refPanel is the hidden surface."""

    def test_1_template_has_hook_and_shared_key(self):
        T = build_widget.TEMPLATE
        # (2) the widget reference plaque #refPanel carries the hideable hook, wired to the SAME key.
        self.assertIn(f"body.{BODY_HOOK} #refPanel", T,
                      "CSS must hide the widget reference plaque #refPanel under the refs-hidden flag")
        self.assertIn(KEY, T, f"the widget must read/write the shared flag key {KEY!r} (D-INV-23)")
        self.assertIn("__REFSTOGGLE__", T, "the widget template must carry the switch-control slot")
        # A named switch — the same labels the catalog uses.
        self.assertIn("Hide references", T)
        self.assertIn("Show references", T)

    def test_2_control_renders_only_with_a_reference_surface(self):
        # The control renders wherever a reference surface (#refPanel) renders, and nowhere else.
        present = build_widget._refs_toggle_html(True)
        self.assertIn('id="refsToggle"', present)
        self.assertIn('aria-pressed="false"', present)   # default shown
        self.assertEqual(build_widget._refs_toggle_html(False), "",
                         "no reference surface ⇒ no switch (nothing to switch)")

    def test_3_plaque_chip_lives_inside_the_hidden_panel(self):
        # The widget's reference PLAQUE CHIP ("Leans toward ⟨artist⟩") lives inside #refPanel, so the
        # #refPanel hook hides the chip and the panel TOGETHER (D-INV-6). Render the real panel.
        axes = FP.AXES
        raw = {a: 0.5 for a in axes}
        dirs = {"ArtistA": {a: 1.0 for a in axes}, "ArtistB": {a: -1.0 for a in axes}}
        norm = {"mu": {a: 0.0 for a in axes}, "sd": {a: 1.0 for a in axes}}
        panel = build_widget.render_reference_read(raw, dirs, norm)
        self.assertIn('id="refPanel"', panel, "the reference plaque is the #refPanel container")
        self.assertIn("Leans toward", panel, "the plaque chip names the nearest direction")
        # The chip is INSIDE the panel container, so hiding #refPanel hides the chip with it.
        self.assertTrue(panel.strip().startswith("<details") or panel.strip().startswith("<div"),
                        "the plaque chip has no separate container to strand outside #refPanel")


class OneGlobalSharedSwitch(unittest.TestCase):
    """D-INV-23: ONE global persisted flag that BOTH pages read — proven at source level by the
    identical key + body hook on both surfaces (not two independent per-page toggles)."""

    def test_same_key_and_hook_on_both_surfaces(self):
        wsrc = (Path(__file__).resolve().parent.parent / "scripts" / "build_widget.py").read_text()
        csrc = (Path(__file__).resolve().parent.parent / "scripts" / "catalog.py").read_text()
        for src, name in ((wsrc, "build_widget.py"), (csrc, "catalog.py")):
            self.assertIn(f'"{KEY}"', src, f"{name} must use the shared flag key {KEY!r}")
            self.assertIn(BODY_HOOK, src, f"{name} must use the shared body hook {BODY_HOOK!r}")

    def test_rendered_surfaces_agree_on_the_key(self):
        # Both rendered pages carry the SAME key string — the one flag both read (D-INV-23).
        cat = catalog.render_catalog_html([_lean_entry()])
        self.assertIn(KEY, cat)
        self.assertIn(KEY, build_widget.TEMPLATE)


if __name__ == "__main__":
    unittest.main()
