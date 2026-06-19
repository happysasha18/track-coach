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

    def test_back_to_library_link_exists_and_wired(self):
        # Sasha 2026-06-19/20: "нет кнопки как вернуться из трека в каталог" / "пропала кнопка бэк на
        # страницу каталога". A back link must exist, carry the translatable label, and link to the
        # library page embedded at build time (D.backHref) so it's ALWAYS present however the widget
        # was opened — with history.back() as the fallback when no href was baked in.
        self.assertIn('id="backLink"', TPL, "the back-to-Library link is missing")
        self.assertTrue(build_widget.STRINGS["ui"].get("back_to_library"),
                        "missing the back_to_library string")
        self.assertIn("back_to_library", TPL, "JS doesn't reference the back_to_library label")
        self.assertIn("D.backHref", TPL, "back link doesn't use the embedded catalog href (D.backHref)")
        self.assertIn("history.back()", TPL, "back link has no history.back() fallback")


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

    def test_simple_gating_is_a_small_known_set(self):
        # What Simple touches via display:none is a SMALL fixed set: the evidence drawer; the demux
        # stem viz (#stemlanes + #seqKey, Detailed-only); and the recs panel filtered to ONLY the
        # timecoded cards (#recs — Simple shows the cards with a triangle on the graph, Detailed shows
        # all). It must NOT creep to hide the transport, the read, or the recs panel wholesale.
        hidden = set(re.findall(r"#([A-Za-z][\w-]*)", SIMPLE_HIDE_SELECTORS))
        self.assertEqual(hidden, {"evidence", "stemlanes", "seqKey", "recs"},
                         f"Simple view gates an unexpected set: {sorted(hidden)}")

    def test_simple_shows_only_timecoded_recs(self):
        # Recs sit under the graph and are the cards the timeline triangles point to. Simple shows
        # ONLY the timecoded ones (those with a triangle); Detailed shows all. The gate targets the
        # global (non-data-t) cards, never a blanket #recs hide.
        self.assertRegex(TPL, r"body\.simple\s+#recs\s+\.rec:not\(\[data-t\]\)",
                         "Simple must hide ONLY the non-timecoded recs, not all of them")
        self.assertNotIn("storyCues", TPL,
                         "the separate callout list under the graph should be gone")

    def test_player_transport_visible_in_simple(self):
        # Sasha 2026-06-19 "плеер в обоих норм": only the stem-lane viz is gated, never the transport.
        for keep in ("#playBtn", "#playerControls"):
            self.assertNotIn(keep, SIMPLE_HIDE_SELECTORS,
                             f"regression: Simple hides the transport ({keep})")

    def test_story_graph_reacts_to_the_toggle(self):
        # Sasha's call (2026-06-19, JOURNAL.md): the Track-Story component lanes change with the view.
        # Simple = the 2 named lanes (energy+brightness) drawn full-size; Detailed = all. The 0.5.14→
        # 0.6 code flattened pickComps to "always ALLCOMPS", so the toggle did nothing to the graph.
        self.assertIn('document.body.classList.contains("simple")', TPL,
                      "pickComps must branch on the simple class")
        self.assertIn("SIMPLE_LANES.includes(c.key)", TPL,
                      "Simple must filter the graph to the named SIMPLE_LANES")
        # ── SETTLED SPEC (session 0b5ab53e, supersedes the older 2-lane L542) ───────────────────
        # Simple = energy + brightness + density + stereo (4). PRIMARY SOURCES:
        #   L186 "ты уверен что … стерео или плотность может тоже оставить в симпл?" (add them) and
        #   L7  "в симпл недостаёт линий" (Simple needs MORE lines, not fewer).
        # Modulation (wobble) is the ONLY Detailed-only lane. If this is to change, change it HERE
        # first with the new citation.
        m = re.search(r"SIMPLE_LANES\s*=\s*\[([^\]]*)\]", TPL)
        self.assertIsNotNone(m, "SIMPLE_LANES array not found")
        self.assertEqual(set(re.findall(r'"([^"]+)"', m.group(1))),
                         {"energy", "brightness", "density", "stereo"},
                         "Simple lanes must be energy + brightness + density + stereo (L186/L7)")

    def test_curve_area_height_is_proportional_to_lane_count(self):
        # Sasha, session 0b5ab53e L402: "в симпле вью общая высота для их площади должна быть МЕНЬШЕ".
        # The fix is structural: compLaneH is a CONSTANT (same in both views), so the total area
        # height = #lanes × compLaneH is PROPORTIONAL to the lane count → Simple (4) is automatically
        # shorter than Detailed (5). Guard that compLaneH does NOT branch on the view (a per-view
        # height was the 0.7.1/0.7.2 mistake) and is a single constant.
        self.assertNotRegex(TPL, r"compLaneH\s*=\s*simple\s*\?",
                            "compLaneH must NOT depend on the view — area must scale with lane count")
        self.assertRegex(TPL, r"const\s+compLaneH\s*=\s*\d+",
                         "compLaneH must be a single constant (area ∝ lane count)")

    def test_demux_stems_hidden_in_simple(self):
        # Demux / per-stem viz (#stemlanes + #seqKey) is DETAILED-ONLY — Sasha, repeatedly (L982) and
        # confirmed 2026-06-20: "демуксы мы договорились показывать только в детальном виде, не в
        # кратком". The transport stays in both; only the stem-lane canvas + its key are gated. (The
        # "show in Simple too" experiment was reverted — Simple keeps just the transport.)
        self.assertRegex(TPL, r"body\.simple\s+#stemlanes",
                         "regression: the demux stem visualisation must be hidden in Simple")
        self.assertRegex(TPL, r"body\.simple\s+#seqKey",
                         "regression: the demux sequencer key must be hidden in Simple")
        for keep in ('id="playerControls"', 'id="playBtn"', 'id="stemlanes"'):
            self.assertIn(keep, TPL, f"player element missing from the template: {keep}")


class AutomationPanel(unittest.TestCase):
    """The 'intention vs result' automation chart was dropped in the 0.6 declutter while its
    data kept riding in the payload (a silent regression). Guard that it's wired back."""

    def test_automation_panel_present_in_template(self):
        for el in ('id="autoPanel"', 'id="auto"', 'id="autoTitle"', 'id="autoHint"'):
            self.assertIn(el, TPL, f"automation panel lost the element: {el}")

    def test_automation_is_actually_wired(self):
        # the draw code must read the envelopes from the payload, not just declare an empty div
        self.assertIn("A.automations", TPL,
                      "automation chart has no data binding (ALS.automations) in the script")

    def test_automation_strings_referenced(self):
        for s in ("auto_title", "auto_hint"):
            self.assertTrue(build_widget.STRINGS["ui"].get(s), f"missing the {s} string")
            self.assertIn(s, TPL, f"JS doesn't reference the {s} string")

    def test_automation_lives_inside_evidence_drawer(self):
        # the panel sits in the deep drawer, so Simple gating it via #evidence is expected
        self.assertLess(TPL.index('id="evidence"'), TPL.index('id="autoPanel"'),
                        "automation panel must sit inside the Evidence drawer")


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
