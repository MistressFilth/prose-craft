"""Tests for prose_craft.voices.model."""

import pytest
from pydantic import ValidationError

from prose_craft.voices.model import (
    AudienceCeiling,
    DictionConfig,
    LexiconConfig,
    NeverEntry,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SubstitutionRule,
    SurfaceFilter,
    SyntaxConfig,
    VoiceProfile,
)


def test_minimal_profile_parses():
    p = VoiceProfile(
        voice="dnova",
        created="2026-08-01",
        updated="2026-08-01",
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    assert p.voice == "dnova"
    assert p.version == 1


def test_extra_keys_rejected():
    with pytest.raises(ValidationError):
        VoiceProfile.model_validate(
            {
                "voice": "x",
                "unknown_field": "y",
            }
        )


def test_audience_ceiling_defaults():
    c = AudienceCeiling()
    assert c.severity_ceiling == 5
    assert c.dial_ceiling == 1.0
    assert c.closed is False


def test_audience_ceiling_closed():
    c = AudienceCeiling(closed=True, reason="no external use")
    assert c.closed is True
    assert c.reason == "no external use"


def test_never_entry_detection_default():
    e = NeverEntry(rule="no em-dashes as sentence punctuation")
    assert e.detection == "agent-required"


def test_substitution_rule_in_diction():
    d = DictionConfig(
        banned=["utilize"],
        preferred=[SubstitutionRule(instead_of="utilize", use="use", note="prefer Germanic")],
    )
    assert "utilize" in d.banned
    assert d.preferred[0].use == "use"


def test_surface_filter_admit_list():
    f = SurfaceFilter(admit=["memo", "postcard"])
    assert f.admit == ["memo", "postcard"]
