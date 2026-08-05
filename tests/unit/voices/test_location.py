"""Tests for prose_craft.voices.location."""

from pathlib import Path

import pytest

from prose_craft.voices.location import VoiceNameError, voice_path


def test_voice_path_validates_name(tmp_voices_root: Path) -> None:
    with pytest.raises(VoiceNameError):
        voice_path("Invalid Name", root=tmp_voices_root)
    with pytest.raises(VoiceNameError):
        voice_path("../escape", root=tmp_voices_root)
    path = voice_path("MistressFilth", root=tmp_voices_root)
    assert path == tmp_voices_root / "MistressFilth" / "voice.md"


def test_voice_path_allows_hyphens(tmp_voices_root: Path) -> None:
    assert voice_path("d-nova", root=tmp_voices_root) == tmp_voices_root / "d-nova" / "voice.md"


def test_voice_path_defaults_to_paths_voices_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A None root delegates to paths.voices_root()."""
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    expected = tmp_path / "data" / "prose-craft" / "voices" / "d-nova" / "voice.md"
    assert voice_path("d-nova") == expected


def test_voice_path_default_honors_direct_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "elsewhere"))
    assert voice_path("d-nova") == tmp_path / "elsewhere" / "d-nova" / "voice.md"


def test_get_voices_root_is_gone() -> None:
    """The resolver moved to paths.voices_root()."""
    from prose_craft.voices import location

    assert not hasattr(location, "get_voices_root")
