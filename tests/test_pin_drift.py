"""Architecture SYMBOL anchors do not rot silently (adopted from live-spec, row 90).

track-coach's ARCHITECTURE.md pins code by SYMBOL — `build_recommendations:1483`, `PLAYER_LOGIC:4689`,
`:root:3509` — where the named symbol is normative and the `:line` is a cache (SPEC E-14). When an edit
grows a pinned file, the cached lines drift and every anchor quietly lies (the s77 adoption found 22 of
them drifted by hundreds of lines at once). This gate runs guardrails/check_pin_drift.py --strict over
the real ARCHITECTURE.md; a NEW drift reds. The negative test proves the checker actually catches drift,
so a green here can't be a broken-checker green (INV-6).
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "guardrails" / "check_pin_drift.py"
ARCH = ROOT / "docs" / "ARCHITECTURE.md"


def _run(arch_path):
    return subprocess.run(
        ["python3", str(CHECKER), str(arch_path), "--strict"],
        capture_output=True, text=True, cwd=str(ROOT),
    )


class PinDrift(unittest.TestCase):
    def test_real_architecture_anchors_all_resolve_strict(self):
        r = _run(ARCH)
        self.assertEqual(
            r.returncode, 0,
            "an ARCHITECTURE.md symbol anchor no longer lives near its cached line — re-resolve it and "
            "refresh the cache (SPEC E-14):\n" + r.stdout + r.stderr,
        )

    def test_checker_catches_a_drifted_anchor(self):
        """A `symbol:line` pointing at the wrong line of a real file must RED under --strict."""
        with tempfile.TemporaryDirectory() as d:
            arch = Path(d) / "ARCHITECTURE.md"
            # build_recommendations really lives near line 1483 in scripts/build_widget.py;
            # pin it at line 1 (far outside the +/-25 window) and the gate must flag drift.
            arch.write_text(
                "## Nodes\n\n"
                "| N | Job | Owning code | tests |\n"
                "|---|---|---|---|\n"
                "| N1 | x | `build_widget.py` `build_recommendations:1` | t |\n"
            )
            r = _run(arch)
            self.assertNotEqual(r.returncode, 0,
                                "checker passed an anchor pinned at the wrong line:\n" + r.stdout)
            self.assertIn("DRIFT", r.stdout)


if __name__ == "__main__":
    unittest.main()
