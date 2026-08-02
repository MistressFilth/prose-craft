"""Tests for prose_craft.voices.location."""

import platform
from pathlib import Path

import pytest

from prose_craft.voices.location import VoiceNameError, get_voices_root, voice_path


def test_voice_path_validates_name(tmp_voices_root: Path) -> None:
    with pytest.raises(VoiceNameError):
        voice_path("Invalid Name", root=tmp_voices_root)
    with pytest.raises(VoiceNameError):
        voice_path("../escape", root=tmp_voices_root)
    path = voice_path("MistressFilth", root=tmp_voices_root)
    assert path == tmp_voices_root / "MistressFilth" / "voice.md"


def test_voice_path_allows_hyphens(tmp_voices_root: Path) -> None:
    path = voice_path("d-nova", root=tmp_voices_root)
    assert path == tmp_voices_root / "d-nova" / "voice.md"


def test_get_voices_root_uses_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    root = get_voices_root()
    assert root == tmp_path / "prose-craft" / "voices"


def test_get_voices_root_uses_prose_craft_root_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "custom"))
    root = get_voices_root()
    assert root == tmp_path / "custom"


def test_get_voices_root_falls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    root = get_voices_root()
    if platform.system() == "Darwin":
        expected = tmp_path / "Library" / "Application Support" / "prose-craft" / "voices"
    else:
        expected = tmp_path / ".local" / "share" / "prose-craft" / "voices"
    assert root == expected
