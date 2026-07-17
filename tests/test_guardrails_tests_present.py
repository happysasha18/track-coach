"""The tests-present guardrail exempts vendored pack scripts.

A change confined to a live-spec pack script vendored under scripts/ (listed in
ratchet-manifest.json) is upstream code covered by test_ratchet_lock.py, so it must not
demand a NEW track-coach test — while a real product-code change still must. Guards the
false positive the 2026-07-17 pack catch-up hit (a spec-style-lint.py refresh blocked the
push though its coverage was unchanged).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import guardrails  # noqa: E402


class TestsPresentExemption(unittest.TestCase):
    def test_vendored_only_change_needs_no_track_coach_test(self):
        vendored = {"scripts/spec-style-lint.py"}
        ok, scripts_touched, _ = guardrails._tests_present_verdict(
            ["scripts/spec-style-lint.py"], vendored)
        self.assertTrue(ok, "a vendored-pack-only change must pass tests-present")
        self.assertEqual(scripts_touched, [], "the vendored file is exempt, not counted")

    def test_product_script_change_still_needs_a_test(self):
        ok, scripts_touched, _ = guardrails._tests_present_verdict(
            ["scripts/build_widget.py"], set())
        self.assertFalse(ok, "a product-code change with no test must still fail")
        self.assertEqual(scripts_touched, ["scripts/build_widget.py"])

    def test_product_change_with_a_test_passes(self):
        ok, _, tests_touched = guardrails._tests_present_verdict(
            ["scripts/build_widget.py", "tests/test_widget_render.py"], set())
        self.assertTrue(ok)
        self.assertEqual(tests_touched, ["tests/test_widget_render.py"])

    def test_real_manifest_lists_the_vendored_scripts(self):
        vendored = guardrails._vendored_pack_scripts()
        self.assertIn("scripts/spec-style-lint.py", vendored)
        # only scripts/*.py are in scope for this check (check-freeze.sh is a .sh, excluded)
        self.assertTrue(all(v.startswith("scripts/") and v.endswith(".py") for v in vendored))


if __name__ == "__main__":
    unittest.main()
