#!/usr/bin/env python3
"""Widget-contract tests — guard the panels a user must always see.

These exist because of a real incident: panels (the stem player, the Producer's read) were
gated behind the Simple view and *looked* deleted. The pipeline/offset unit tests can't catch
that — nothing crashes, the data is still in the file, it's just hidden by CSS. So we assert
the contract directly on the generated widget TEMPLATE + its CSS:

  1. The key panels EXIST in the template (player, producer's read, recs, story, evidence).
  2. The Simple view hides ONLY the deep "Evidence & detail" drawer — NEVER the player,
     the Producer's read, or recommendation cards. (Show-everything-but-evidence in Simple.)

No audio, no deps, instant — pure string/CSS assertions on the module-level TEMPLATE.
"""
import re, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402

TPL = build_widget.TEMPLATE
# every `body.simple … {display:none…}` selector list in the CSS
SIMPLE_HIDE = re.findall(r"body\.simple([^{]*)\{[^}]*display\s*:\s*none[^}]*\}", TPL)
SIMPLE_HIDE_SELECTORS = " ".join(SIMPLE_HIDE)


class PanelsExist(unittest.TestCase):
    def test_core_panels_present_in_template(self):
        for el in ('id="playerControls"', 'id="readPanel"', 'id="recs"',
                   'id="storyPanel"', 'id="story"', 'id="evidence"'):
            self.assertIn(el, TPL, f"template lost the panel: {el}")

    def test_player_is_actually_wired(self):
        # the player code + its data hook must be in the script, not just the empty div
        self.assertIn("D.player", TPL, "player has no data binding (D.player) in the script")

    def test_producer_read_has_reveal_wiring(self):
        # #readPanel starts hidden and is un-hidden when a narrative exists; if either the
        # narrative gate or the reveal is gone, the Producer's read can never appear.
        self.assertIn("if(D.narrative)", TPL, "producer's-read narrative gate is missing")
        self.assertIn('getElementById("readPanel")', TPL,
                      "producer's-read reveal (readPanel) is missing")


class SimpleViewContract(unittest.TestCase):
    """Simple must not silently swallow the things users expect to see."""

    def test_player_visible_in_simple(self):
        self.assertNotIn("#playerControls", SIMPLE_HIDE_SELECTORS,
                         "regression: the stem PLAYER is hidden in Simple view")

    def test_producer_read_visible_in_simple(self):
        self.assertNotIn("#readPanel", SIMPLE_HIDE_SELECTORS,
                         "regression: the Producer's read is hidden in Simple view")

    def test_recs_not_capped_in_simple(self):
        # the old `#recs .rec:nth-of-type(n+4){display:none}` cap made cards "disappear"
        self.assertNotRegex(TPL, r"body\.simple\s+#recs[^{]*nth-of-type",
                            "regression: recommendation cards are capped/hidden in Simple view")

    def test_simple_only_gates_the_evidence_drawer(self):
        # whatever Simple DOES hide, it must be only the deep evidence drawer
        hidden = re.findall(r"#([A-Za-z][\w-]*)", SIMPLE_HIDE_SELECTORS)
        self.assertEqual(set(hidden), {"evidence"},
                         f"Simple view hides unexpected panels: {sorted(set(hidden))}")


class ModeLabel(unittest.TestCase):
    """The header label must follow the run mode — quick runs were mislabelled 'deep mode'."""

    def test_subtitle_is_driven_by_mode_not_hardcoded(self):
        # the header must branch on D.mode, not always print the 'deep mode' string
        self.assertRegex(TPL, r'D\.mode\s*===?\s*["\']quick["\']',
                         "header subtitle does not branch on D.mode (quick runs mislabelled)")

    def test_both_mode_strings_exist(self):
        ui = build_widget.STRINGS["ui"]
        self.assertTrue(ui.get("subtitle"), "missing the deep-mode subtitle string")
        self.assertTrue(ui.get("subtitle_quick"), "missing the 'quick read' subtitle string")
        self.assertIn("subtitle_quick", TPL, "JS doesn't reference the quick subtitle string")


if __name__ == "__main__":
    unittest.main()
