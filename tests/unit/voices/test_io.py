"""Tests for prose_craft.voices.io."""

from pathlib import Path

import pytest

from prose_craft.voices.io import (
    VoiceProfileNotFound,
    list_voices,
    read_voice,
    write_voice,
)
from prose_craft.voices.model import (
    DictionConfig,
    LexiconConfig,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SyntaxConfig,
    VoiceProfile,
)


FIXTURE_ROOT = Path(__file__).parent.parent.parent / "fixtures" / "voices"


def test_read_voice_from_fixture(tmp_path):
    profile = read_voice("dnova", root=FIXTURE_ROOT)
    assert profile.voice == "dnova"
    assert profile.register.funny_serious == 0.3
    assert "utilize" in profile.diction.banned
    assert "the long now" in profile.lexicon.pet_phrases


def test_read_voice_missing(tmp_voices_root):
    with pytest.raises(VoiceProfileNotFound):
        read_voice("absent", root=tmp_voices_root)


def test_write_voice_round_trip(tmp_voices_root):
    p = VoiceProfile(
        voice="test",
        created="2026-08-01",
        updated="2026-08-01",
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    body = "\n# Body\n\nThis voice is X.\n"
    path = write_voice(p, body, root=tmp_voices_root)
    assert path.exists()
    reloaded = read_voice("test", root=tmp_voices_root)
    assert reloaded.voice == "test"
    # Re-read the raw file to confirm the body was preserved verbatim.
    raw = path.read_text(encoding="utf-8")
    assert body.strip() in raw


def test_write_atomic_no_partial_file_on_overwrite(tmp_voices_root):
    p = VoiceProfile(
        voice="atomic",
        created="2026-08-01",
        updated="2026-08-01",
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    write_voice(p, "first body", root=tmp_voices_root)
    write_voice(p, "second body", root=tmp_voices_root)
    raw = read_voice("atomic", root=tmp_voices_root)  # noqa: F841
    # VoiceProfile doesn't carry the body, but the file on disk should.
    path = tmp_voices_root / "atomic" / "voice.md"
    assert "second body" in path.read_text(encoding="utf-8")


def test_list_voices(tmp_voices_root):
    for name in ("alpha", "beta"):
        (tmp_voices_root / name).mkdir()
        (tmp_voices_root / name / "voice.md").write_text(
            f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
            "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n---\n",
            encoding="utf-8",
        )
    summaries = list_voices(root=tmp_voices_root)
    names = {s.name for s in summaries}
    assert names == {"alpha", "beta"}
