"""Tests for prose_craft.orchestrator.prompts."""

from __future__ import annotations

from prose_craft.orchestrator.prompts import format_audience_block
from prose_craft.voices.audience import ResolvedAudience
from prose_craft.voices.model import NeverEntry, SurfaceFilter


def test_format_audience_block_none_returns_empty():
    assert format_audience_block(None) == ""


def test_format_audience_block_minimal():
    a = ResolvedAudience(name="team", voice_name="v")
    out = format_audience_block(a)
    assert "Audience: team" in out
    assert "Severity ceiling: 5/5" in out
    assert "Dial ceiling: 1.00" in out
    assert "Never list (merged): 0 rules" in out
    assert "(source: voice_default)" in out


def test_format_audience_block_with_warnings_and_surface():
    a = ResolvedAudience(
        name="external",
        voice_name="v",
        severity_ceiling=4,
        dial_ceiling=0.8,
        surface_filter=SurfaceFilter(admit=["memo"], close=["tweet"]),
        surface_target="postmortem",
        never=[NeverEntry(rule="no em-dash")],
        warnings=["audience 'external' is closed"],
        source="cli",
    )
    out = format_audience_block(a)
    assert "Audience: external" in out
    assert "Severity ceiling: 4/5" in out
    assert "Dial ceiling: 0.80" in out
    assert "Surfaces admitted: memo" in out
    assert "Surfaces closed: tweet" in out
    assert "Surface target: postmortem" in out
    assert "Never list (merged): 1 rules" in out
    assert "Warnings:" in out
    assert "audience 'external' is closed" in out
