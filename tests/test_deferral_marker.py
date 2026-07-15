"""test_deferral_marker.py — the mechanical net that stops derivable work being
parked for the human's greenlight (guardrails/check_deferral_marker.py).

Root cause it guards (2026-07-15, Alexander "я нигде не просил меня ждать"): a
code-vs-spec defect is derivable from its spec sentence → the agent's own (INV-152),
so it must never sit behind a "wait for his greenlight" marker.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load the guardrail module by path (guardrails/ is not an importable package).
_spec = importlib.util.spec_from_file_location(
    "check_deferral_marker", ROOT / "guardrails" / "check_deferral_marker.py"
)
cdm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdm)


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "NEXT_STEPS.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_real_next_steps_is_clean():
    """The live NEXT_STEPS.md must carry no wrongly-parked work."""
    assert cdm.check(ROOT / "NEXT_STEPS.md") == []


def test_defect_with_greenlight_is_flagged(tmp_path):
    """Check A: a code-vs-spec defect behind a greenlight marker is a finding."""
    p = _write(tmp_path,
        "**Product-code defect — code diverged from the spec (spec is right). "
        "Alexander greenlights the reopen.**\n")
    findings = cdm.check(p)
    assert any(f.strip().startswith("A") for f in findings), findings


def test_negated_greenlight_passes(tmp_path):
    """'No greenlight — the agent's own' states the ABSENCE of a wait; not a finding."""
    p = _write(tmp_path,
        "**Product-code defect — code diverged from the spec (spec is right). "
        "Each is derivable → the agent's own to fix. No greenlight.**\n")
    assert cdm.check(p) == []


def test_unjustified_park_block_is_flagged(tmp_path):
    """Check B: a human-parked block naming no human-only fact is a finding."""
    p = _write(tmp_path,
        "**🙋 Alexander drives these:**\n"
        "1. Fix the rep-selection to prefer completeness then stamp.\n")
    findings = cdm.check(p)
    assert any(f.strip().startswith("B") for f in findings), findings


def test_justified_park_block_passes(tmp_path):
    """A park block naming a human-only fact (taste/scope) — or whose bullet does — passes."""
    p = _write(tmp_path,
        "**🙋 His call (taste/scope — I recommend, he decides):**\n"
        "- References show/hide switch — DEFER post-1.0 (a nicety).\n")
    assert cdm.check(p) == []


def test_park_block_fact_inherited_from_bullet(tmp_path):
    """A generic park heading is justified when a bullet in its block names the fact."""
    p = _write(tmp_path,
        "**🙋 Alexander drives these:**\n"
        "1. README marketing prose — his promotion/marketing taste.\n")
    assert cdm.check(p) == []
