"""Tests for prose_craft.voices.audience."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from prose_craft.voices import audience as audience_mod
from prose_craft.voices.audience import (
    AudienceNotFoundError,
    ResolvedAudience,
    resolve_audience,
)
from prose_craft.voices.io import write_voice
from prose_craft.voices.model import (
    AudienceCeiling,
    AudiencesBlock,
    DictionConfig,
    LexiconConfig,
    NeverEntry,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SurfaceFilter,
    SyntaxConfig,
    VoiceProfile,
)


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


def _write_voice(root: Path, name: str, audiences: AudiencesBlock) -> Path:
    voice_dir = root / name
    voice_dir.mkdir(parents=True)
    profile = VoiceProfile(
        voice=name,
        created=date(2026, 8, 1),
        updated=date(2026, 8, 1),
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
        audiences=audiences,
    )
    write_voice(profile, root=root)
    return voice_dir


def test_resolve_returns_none_when_no_audiences_and_no_flag(tmp_path):
    root = tmp_path
    _write_voice(root, "minimal", AudiencesBlock())
    result = resolve_audience("minimal", voices_root=root)
    assert result is None


def test_resolve_picks_most_permissive_audience_by_default(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(
        rationale="test",
        private=AudienceCeiling(severity_ceiling=5, dial_ceiling=1.0),
        team=AudienceCeiling(severity_ceiling=3, dial_ceiling=0.7),
        external=AudienceCeiling(severity_ceiling=5, dial_ceiling=0.9),
    )
    _write_voice(root, "test", audiences)
    result = resolve_audience("test", voices_root=root)
    assert result is not None
    assert result.name == "private"  # tied severity=5, highest dial=1.0 wins
    assert result.source == "voice_default"


def test_resolve_cli_audience_wins_over_default(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(
        private=AudienceCeiling(severity_ceiling=5),
        team=AudienceCeiling(severity_ceiling=3),
    )
    _write_voice(root, "test", audiences)
    result = resolve_audience("test", cli_audience="team", voices_root=root)
    assert result is not None
    assert result.name == "team"
    assert result.severity_ceiling == 3
    assert result.source == "cli"


def test_resolve_unknown_cli_audience_raises(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(
        private=AudienceCeiling(),
        team=AudienceCeiling(),
    )
    _write_voice(root, "test", audiences)
    with pytest.raises(audience_mod.AudienceNotFoundError) as ei:
        resolve_audience("test", cli_audience="missing", voices_root=root)
    assert ei.value.audience == "missing"
    assert "private" in ei.value.available


def test_resolve_front_matter_audience_overrides_default(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(
        private=AudienceCeiling(severity_ceiling=5),
        team=AudienceCeiling(severity_ceiling=3),
    )
    _write_voice(root, "test", audiences)
    brief = tmp_path / "brief.md"
    brief.write_text("---\naudience: team\n---\nbody\n", encoding="utf-8")
    result = resolve_audience("test", front_matter_path=brief, voices_root=root)
    assert result is not None
    assert result.name == "team"
    assert result.source == "frontmatter"


def test_resolve_cli_overrides_front_matter(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(
        private=AudienceCeiling(),
        team=AudienceCeiling(),
        external=AudienceCeiling(),
    )
    _write_voice(root, "test", audiences)
    brief = tmp_path / "brief.md"
    brief.write_text("---\naudience: team\n---\nbody\n", encoding="utf-8")
    result = resolve_audience(
        "test",
        cli_audience="external",
        front_matter_path=brief,
        voices_root=root,
    )
    assert result is not None
    assert result.name == "external"
    assert result.source == "cli"


def test_resolve_front_matter_severity_and_dial(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(team=AudienceCeiling(severity_ceiling=4, dial_ceiling=0.8))
    _write_voice(root, "test", audiences)
    brief = tmp_path / "brief.md"
    brief.write_text("---\nseverity_ceiling: 2\ndial_ceiling: 0.5\n---\n", encoding="utf-8")
    result = resolve_audience("test", front_matter_path=brief, voices_root=root)
    assert result is not None
    assert result.severity_ceiling == 2
    assert result.dial_ceiling == 0.5


def test_resolve_front_matter_invalid_type_raises(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(team=AudienceCeiling(severity_ceiling=3))
    _write_voice(root, "test", audiences)
    brief = tmp_path / "brief.md"
    brief.write_text("---\nseverity_ceiling: high\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="severity_ceiling"):
        resolve_audience("test", front_matter_path=brief, voices_root=root)


def test_resolve_front_matter_parse_error_falls_through(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(team=AudienceCeiling(severity_ceiling=3))
    _write_voice(root, "test", audiences)
    brief = tmp_path / "brief.md"
    # Broken YAML — falls through to voice default.
    brief.write_text("---\n: :\n---\n", encoding="utf-8")
    result = resolve_audience("test", front_matter_path=brief, voices_root=root)
    assert result is not None
    assert result.source == "voice_default"
    assert any("front-matter" in w for w in result.warnings)


def test_resolve_surface_from_front_matter(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(team=AudienceCeiling(severity_ceiling=3))
    _write_voice(root, "test", audiences)
    brief = tmp_path / "brief.md"
    brief.write_text("---\nsurface: rfc\n---\n", encoding="utf-8")
    result = resolve_audience("test", front_matter_path=brief, voices_root=root)
    assert result is not None
    assert result.surface_target == "rfc"


def test_resolve_cli_surface_overrides_front_matter(tmp_path):
    root = tmp_path
    audiences = AudiencesBlock(team=AudienceCeiling(severity_ceiling=3))
    _write_voice(root, "test", audiences)
    brief = tmp_path / "brief.md"
    brief.write_text("---\nsurface: rfc\n---\n", encoding="utf-8")
    result = resolve_audience(
        "test",
        cli_surface="memo",
        front_matter_path=brief,
        voices_root=root,
    )
    assert result is not None
    assert result.surface_target == "memo"
