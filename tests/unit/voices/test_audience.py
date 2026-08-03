"""Tests for prose_craft.voices.audience."""

from __future__ import annotations

from prose_craft.voices.audience import AudienceNotFoundError, ResolvedAudience
from prose_craft.voices.model import NeverEntry, SurfaceFilter


def test_resolved_audience_minimal_defaults():
    a = ResolvedAudience(name="team", voice_name="discordian-base")
    assert a.severity_ceiling == 5
    assert a.dial_ceiling == 1.0
    assert a.never == []
    assert a.surface_filter is None
    assert a.surface_target is None
    assert a.closed is False
    assert a.reason is None
    assert a.warnings == []
    assert a.source == "voice_default"


def test_resolved_audience_populated():
    a = ResolvedAudience(
        name="external",
        voice_name="discordian-base",
        severity_ceiling=4,
        dial_ceiling=0.8,
        never=[NeverEntry(rule="no em-dashes")],
        surface_filter=SurfaceFilter(close=["tweet"]),
        surface_target="postmortem",
        closed=True,
        reason="internal only",
        warnings=["audience 'external' is closed"],
        source="cli",
    )
    assert a.severity_ceiling == 4
    assert a.closed is True
    assert a.warnings == ["audience 'external' is closed"]


def test_audience_not_found_error_carries_voice_and_available():
    err = AudienceNotFoundError(
        voice="discordian-base", audience="foo", available=["private", "team", "external"]
    )
    msg = str(err)
    assert "discordian-base" in msg
    assert "foo" in msg
    assert "private" in msg and "team" in msg and "external" in msg
