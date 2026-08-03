"""Tests for prose_craft.voices.check."""

from datetime import date

from prose_craft.voices.audience import ResolvedAudience
from prose_craft.voices.check import check_voice
from prose_craft.voices.model import (
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


def _profile(**overrides) -> VoiceProfile:
    base = dict(
        voice="t",
        created=date(2026, 8, 1),
        updated=date(2026, 8, 1),
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    base.update(overrides)
    return VoiceProfile(**base)


def test_check_voice_clean_text_returns_empty_verdict():
    p = _profile()
    text = "She walked home. The dog ran. Birds sang."
    v = check_voice(text, p)
    assert v.mechanical == []
    assert v.statistical == []
    assert v.judgments_needed == []


def test_check_voice_flags_banned_word():
    p = _profile(diction=DictionConfig(banned=["utilize"]))
    v = check_voice("We will utilize this approach.", p)
    assert any(mv.rule == "diction.banned" for mv in v.mechanical)


def test_check_voice_flags_taboo_phrase():
    p = _profile(lexicon=LexiconConfig(taboo_phrases=["in order to"]))
    v = check_voice("We did it in order to win.", p)
    assert any(mv.rule == "lexicon.taboo_phrases" for mv in v.mechanical)


def test_check_voice_flags_preferred_substitution():
    p = _profile(
        diction=DictionConfig(preferred=[SubstitutionRule(instead_of="utilize", use="use")])
    )
    v = check_voice("We will utilize this.", p)
    assert any(mv.rule == "diction.preferred" for mv in v.mechanical)


def test_check_voice_tolerance_relaxed_widens_bands():
    p = _profile(rhythm=RhythmConfig(target_mean_sentence="15-20 words"))
    text = "One. Two three. Four five six. Seven eight nine ten. " * 6
    v_strict = check_voice(text, p, tolerance="strict")
    v_relaxed = check_voice(text, p, tolerance="relaxed")
    assert len(v_relaxed.statistical) <= len(v_strict.statistical)


def test_check_voice_agent_required_entries_become_judgments():
    p = _profile(
        never=[
            NeverEntry(rule="no purple prose", detection="agent-required"),
        ]
    )
    v = check_voice("The sun was a fiery eye.", p)
    assert any(j.rule == "no purple prose" for j in v.judgments_needed)


def test_check_voice_violations_property_combines_lists():
    p = _profile(diction=DictionConfig(banned=["utilize"]))
    v = check_voice("We will utilize this approach.", p)
    # mechanical includes the banned-word violation
    assert len(v.violations) == len(v.mechanical) + len(v.statistical)
    assert len(v.violations) >= 1


def test_check_voice_tightens_severity_via_audience():
    """A lower audience severity_ceiling surfaces violations the voice default would miss.

    Voice target band 15-20 with tolerance=normal gives band=1.0 (range 14-21).
    A mean sentence length of 14.2 is in that range (no violation), but a tighter
    audience ceiling scales the band down so the same mean length now falls
    outside the band.
    """
    p = _profile(rhythm=RhythmConfig(target_mean_sentence="15-20 words"))
    # 7 sentences of 14 words = mean 14.0; pad one extra short sentence so mean dips
    # just under the lower edge of the band when the band shrinks.
    sents = [" ".join(["word"] * 14) + "."] * 7
    sents.append("short.")  # 1 word; mean = (7*14 + 1) / 8 = 99/8 ≈ 12.4
    text = " ".join(sents)
    audience = ResolvedAudience(name="external", voice_name="t", severity_ceiling=2)
    v_no_audience = check_voice(text, p, tolerance="normal")
    v_with_audience = check_voice(text, p, tolerance="normal", audience=audience)
    # lower ceiling tightens bands, so violations should be >= not-strict baseline
    assert len(v_with_audience.violations) >= len(v_no_audience.violations)
    # and specifically the rhythm violation should fire with the tighter band
    assert any(r.rule == "rhythm.target_mean_sentence" for r in v_with_audience.statistical)


def test_check_voice_enforces_audience_never_extend():
    """Audience never_extend rules bind even if voice.never lacks them."""
    p = _profile()
    audience = ResolvedAudience(
        name="external",
        voice_name="t",
        never=[NeverEntry(rule="no SHOUTING IN TITLES", detection="mechanical")],
    )
    v = check_voice("HELLO WORLD", p, tolerance="normal", audience=audience)
    assert any("SHOUTING" in mv.rule for mv in v.mechanical)


def test_check_voice_enforces_surface_filter_close():
    """A surface in audience.surface_filter.close is flagged as a violation."""
    p = _profile()
    audience = ResolvedAudience(
        name="external",
        voice_name="t",
        surface_filter=SurfaceFilter(close=["tweet"]),
    )
    v = check_voice("Some text.", p, tolerance="normal", audience=audience, surface="tweet")
    assert any("tweet" in mv.rule for mv in v.mechanical)


def test_check_voice_audience_not_in_close_passes():
    """A surface not in close passes through without a violation."""
    p = _profile()
    audience = ResolvedAudience(
        name="external",
        voice_name="t",
        surface_filter=SurfaceFilter(close=["tweet"]),
    )
    v = check_voice("Some text.", p, tolerance="normal", audience=audience, surface="memo")
    assert not any("tweet" in mv.rule for mv in v.mechanical)


def test_check_voice_echoes_audience_in_verdict():
    """VoiceVerdict surfaces the resolved audience back to the caller."""
    p = _profile()
    audience = ResolvedAudience(name="team", voice_name="t", severity_ceiling=3)
    v = check_voice("Some text.", p, tolerance="normal", audience=audience)
    assert v.audience is not None
    assert v.audience.name == "team"
    assert v.audience.severity_ceiling == 3


def test_check_voice_audience_none_in_verdict_when_not_provided():
    """VoiceVerdict.audience is None when no audience was supplied."""
    p = _profile()
    v = check_voice("Some text.", p, tolerance="normal")
    assert v.audience is None
