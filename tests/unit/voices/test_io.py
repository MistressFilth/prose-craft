"""Tests for prose_craft.voices.io."""

from pathlib import Path

import pytest

from prose_craft.voices.io import (
    VoiceDeleteError,
    VoiceProfileNotFound,
    delete_voice,
    list_voices,
    read_voice,
    read_voice_file,
    write_voice,
)
from prose_craft.voices.location import VoiceNameError
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
    profile = read_voice("MistressFilth", root=FIXTURE_ROOT)
    assert profile.voice == "MistressFilth"
    assert profile.register.funny_serious == 0.3
    assert "utilize" in profile.diction.banned
    assert "the long now" in profile.lexicon.pet_phrases


def test_read_voice_missing(tmp_voices_root):
    with pytest.raises(VoiceProfileNotFound):
        read_voice("absent", root=tmp_voices_root)


def test_read_voice_file_returns_full_text(tmp_voices_root):
    body = "---\nvoice: raw\nversion: 1\n---\n\n# Body\n"
    path = tmp_voices_root / "raw" / "voice.md"
    path.parent.mkdir()
    path.write_text(body, encoding="utf-8")

    assert read_voice_file("raw", root=tmp_voices_root) == body


def test_read_voice_file_missing(tmp_voices_root):
    with pytest.raises(VoiceProfileNotFound):
        read_voice_file("absent", root=tmp_voices_root)


def test_read_voice_file_rejects_invalid_name(tmp_voices_root):
    with pytest.raises(VoiceNameError):
        read_voice_file("../escape", root=tmp_voices_root)


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


def test_list_voices_reports_broken_files(tmp_voices_root):
    """A voice file that fails to parse must surface as an error, not be
    silently dropped from the list. Otherwise a half-broken library
    (e.g. one voice from a previous schema) makes the count look
    wrong with no explanation.
    """
    from prose_craft.voices.io import list_voice_errors

    (tmp_voices_root / "good").mkdir()
    (tmp_voices_root / "good" / "voice.md").write_text(
        "---\nvoice: good\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n---\n",
        encoding="utf-8",
    )
    (tmp_voices_root / "bad").mkdir()
    (tmp_voices_root / "bad" / "voice.md").write_text(
        "---\nvoice: bad\nregister_discipline: {survives_old_schema: yes}\n---\n",
        encoding="utf-8",
    )

    errors = list_voice_errors(root=tmp_voices_root)
    assert len(errors) == 1
    assert errors[0].name == "bad"
    assert isinstance(errors[0].error, str)
    assert errors[0].error  # non-empty message

    # Healthy voice still lists; broken one is reported, not silent.
    summaries = list_voices(root=tmp_voices_root)
    assert {s.name for s in summaries} == {"good"}


def test_voice_init_template_includes_audiences_block():
    from prose_craft.data import load_template

    template = load_template()
    assert "audiences:" in template
    assert "private:" in template
    assert "team:" in template
    assert "external:" in template
    assert "rationale:" in template
    # Severity ceiling defaults to 5; external is 4
    assert "severity_ceiling: 5" in template
    assert "severity_ceiling: 4" in template


def test_voice_init_scaffolds_audiences_block(tmp_path, monkeypatch):
    """voice_init writes a voice.md with the scaffolded audiences block."""
    from typer.testing import CliRunner
    from prose_craft.cli import app

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["voice", "init", "new-voice"])
    assert result.exit_code == 0, result.output
    voice_md = tmp_path / "new-voice" / "voice.md"
    text = voice_md.read_text(encoding="utf-8")
    assert "audiences:" in text
    assert "private:" in text
    assert "team:" in text
    assert "external:" in text


def test_read_voice_missing_raises(tmp_path, monkeypatch):
    """read_voice / read_voice_file / read_voice_raw raise VoiceProfileNotFound
    when the name is absent from the user root. No bundled fallback."""
    from prose_craft.voices import io
    from prose_craft.voices.io import VoiceProfileNotFound

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))

    with pytest.raises(VoiceProfileNotFound):
        io.read_voice("does-not-exist")
    with pytest.raises(VoiceProfileNotFound):
        io.read_voice_file("does-not-exist")
    with pytest.raises(VoiceProfileNotFound):
        io.read_voice_raw("does-not-exist")

    assert io.list_voices() == []


def test_delete_voice_removes_user_directory(tmp_path):
    (tmp_path / "alpha" / "voice.md").parent.mkdir(parents=True)
    (tmp_path / "alpha" / "voice.md").write_text(
        "---\nvoice: alpha\nversion: 1\n---\n", encoding="utf-8"
    )
    # Add a companion file to confirm the whole directory goes, not just voice.md
    (tmp_path / "alpha" / "notes.txt").write_text("companion")

    deleted = delete_voice("alpha", root=tmp_path)

    assert deleted == tmp_path / "alpha"
    assert not (tmp_path / "alpha").exists()


def test_delete_voice_missing_raises(tmp_path):
    with pytest.raises(VoiceProfileNotFound):
        delete_voice("ghost", root=tmp_path)


def test_delete_voice_invalid_name_raises(tmp_path):
    with pytest.raises(VoiceNameError):
        delete_voice("../escape", root=tmp_path)


def test_delete_voice_rejects_traversal_even_when_sibling_matches(tmp_path):
    """A traversal name like ``../escape`` must raise VoiceNameError before
    any rmtree(), even when a sibling of ``user_root`` happens to contain
    a matching ``voice.md``. Otherwise shutil.rmtree(user_target) would
    happily delete a directory outside the user root.
    """
    user_root = tmp_path / "user"
    # Sibling of user_root that the traversal name would otherwise resolve
    # to if the regex check is bypassed.
    sibling = tmp_path / "escape"
    (sibling / "voice.md").parent.mkdir(parents=True)
    (sibling / "voice.md").write_text("---\nvoice: escape\nversion: 1\n---\n", encoding="utf-8")

    with pytest.raises(VoiceNameError):
        delete_voice("../escape", root=user_root)

    # The sibling directory (and its voice.md) must be untouched.
    assert (sibling / "voice.md").is_file()


def test_delete_voice_refuses_shared_only(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (shared / "prose-craft" / "voices" / "shipped" / "voice.md").parent.mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "shipped" / "voice.md").write_text(
        "---\nvoice: shipped\nversion: 1\n---\n", encoding="utf-8"
    )

    with pytest.raises(VoiceDeleteError):
        delete_voice("shipped")

    assert (shared / "prose-craft" / "voices" / "shipped").is_dir()


def test_delete_voice_removes_user_copy_keeps_shared(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    # User copy
    (user / "alpha" / "voice.md").parent.mkdir(parents=True)
    (user / "alpha" / "voice.md").write_text(
        "---\nvoice: alpha\nversion: 1\n---\n", encoding="utf-8"
    )
    # Shared copy
    (shared / "prose-craft" / "voices" / "alpha" / "voice.md").parent.mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "alpha" / "voice.md").write_text(
        "---\nvoice: alpha\nversion: 1\n---\n", encoding="utf-8"
    )

    deleted = delete_voice("alpha")

    assert deleted == user / "alpha"
    assert not (user / "alpha").exists()
    assert (shared / "prose-craft" / "voices" / "alpha").is_dir()
