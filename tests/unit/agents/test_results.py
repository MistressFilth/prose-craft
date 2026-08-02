"""Tests for prose_craft.agents.results."""

from __future__ import annotations

from prose_craft.agents.results import (
    ArchitectResult,  # noqa: F401  (public API surface; exercised by later tasks)
    DraftResult,  # noqa: F401  (public API surface; exercised by later tasks)
    EditResult,
    ProseDiagnostic,
    SubstitutionPlan,  # noqa: F401  (public API surface; exercised by later tasks)
    VoiceDelta,
)


def test_prose_diagnostic_minimal():
    d = ProseDiagnostic(metrics=None, issues=[])
    assert d.voice_section is None
    assert d.dispersion is None


def test_edit_result_change_log_structure():
    e = EditResult(
        changes=[],
        change_log="rules_honored: x\nfallback_dimensions: y\nagent_required: z",
        rules_honored=["x"],
        fallback_dimensions=["y"],
        agent_required=["z"],
    )
    assert e.rules_honored == ["x"]


def test_voice_delta():
    d = VoiceDelta(field="purpose", value="formal memos", prompt="What is this voice for?")
    assert d.field == "purpose"
    assert d.value == "formal memos"
