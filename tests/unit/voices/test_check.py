"""Tests for prose_craft.voices.check."""

from datetime import date

from prose_craft.voices.check import check_voice
from prose_craft.voices.model import (
    DictionConfig,
    LexiconConfig,
    NeverEntry,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SubstitutionRule,
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
