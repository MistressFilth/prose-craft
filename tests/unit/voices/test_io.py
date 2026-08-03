"""Tests for prose_craft.voices.io."""

from pathlib import Path

import pytest

from prose_craft.voices.io import (
    VoiceProfileNotFound,
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


def test_all_repo_voices_parse():
    """Every shipped voice under ``../voices/`` parses against the model.

    Catches schema drift between the pydantic ``VoiceProfile`` and the
    on-disk YAML (e.g. ``audiences.rationale``, ``never`` as bare
    strings, register axes with inline annotations).
    """
    from prose_craft.voices.io import _parse_voice_file

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    voices_root = repo_root.parent / "voices"
    assert voices_root.is_dir(), f"missing voices root: {voices_root}"

    parsed: list[str] = []
    for voice_dir in sorted(voices_root.iterdir()):
        if not voice_dir.is_dir():
            continue
        voice_md = voice_dir / "voice.md"
        if not voice_md.is_file():
            continue
        profile = _parse_voice_file(voice_md)
        parsed.append(profile.voice)

    assert len(parsed) >= 10, f"expected at least 10 voices, got {len(parsed)}: {parsed}"


def test_list_voices_falls_back_to_bundled(tmp_path, monkeypatch):
    """When the user root has no voices, bundled shipped voices appear.

    Simulates a freshly installed tool with an empty XDG root: voices
    shipped via the wheel (``prose_craft/_bundled_voices/``) must show
    up in ``list_voices`` so ``prose voice list`` works out of the box.
    """
    from prose_craft.voices import io, location
    from prose_craft.voices.location import get_bundled_voices_root

    bundled = get_bundled_voices_root()
    if bundled is None:
        # Editable install / wheel built without force-include — skip.
        pytest.skip("no bundled voices available in this environment")

    # Force the user root to an empty dir so the fallback must fire.
    monkeypatch.setattr(location, "get_voices_root", lambda: tmp_path)

    summaries = io.list_voices()
    names = {s.name for s in summaries}
    assert names, "expected bundled voices when user root is empty"
    # Bundled voices live under ``discordian-*`` in this repo.
    assert any(n.startswith("discordian-") for n in names)


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


def test_resolve_voice_path_falls_back_to_bundled(tmp_path, monkeypatch):
    """``_resolve_voice_path`` finds bundled voices when user root is empty."""
    from prose_craft.voices import io, location
    from prose_craft.voices.location import get_bundled_voices_root

    bundled = get_bundled_voices_root()
    if bundled is None:
        pytest.skip("no bundled voices available in this environment")

    monkeypatch.setattr(location, "get_voices_root", lambda: tmp_path)
    bundled_voice = bundled / "discordian-base" / "voice.md"
    assert bundled_voice.is_file()

    resolved = io._resolve_voice_path("discordian-base", tmp_path)
    assert resolved == bundled_voice
