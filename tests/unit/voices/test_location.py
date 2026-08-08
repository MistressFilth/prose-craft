"""Tests for prose_craft.voices.location."""

from pathlib import Path

import pytest

from prose_craft.voices.location import (
    VoiceNameError,
    _discover_project_root,
    voice_path,
    voice_roots,
)


def test_voice_path_validates_name(tmp_voices_root: Path) -> None:
    with pytest.raises(VoiceNameError):
        voice_path("Invalid Name", root=tmp_voices_root)
    with pytest.raises(VoiceNameError):
        voice_path("../escape", root=tmp_voices_root)
    path = voice_path("MistressFilth", root=tmp_voices_root)
    assert path == tmp_voices_root / "MistressFilth" / "voice.md"


def test_voice_path_allows_hyphens(tmp_voices_root: Path) -> None:
    assert voice_path("d-nova", root=tmp_voices_root) == tmp_voices_root / "d-nova" / "voice.md"


def test_voice_path_defaults_to_load_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A None root delegates to load_settings().voices_root."""
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
    """The earlier ``get_voices_root`` resolver moved to ``paths``."""
    from prose_craft.voices import location

    assert not hasattr(location, "get_voices_root")


def test_discover_finds_closest_project_root(tmp_path: Path) -> None:
    (tmp_path / ".prose-craft" / "voices").mkdir(parents=True)
    cwd = tmp_path / "sub" / "deep"
    cwd.mkdir(parents=True)

    assert _discover_project_root(cwd) == tmp_path / ".prose-craft" / "voices"


def test_discover_no_marker_returns_none(tmp_path: Path) -> None:
    cwd = tmp_path / "sub"
    cwd.mkdir()

    assert _discover_project_root(cwd) is None


def test_discover_closest_wins_over_ancestor(tmp_path: Path) -> None:
    (tmp_path / ".prose-craft" / "voices").mkdir(parents=True)
    (tmp_path / "sub" / ".prose-craft" / "voices").mkdir(parents=True)
    cwd = tmp_path / "sub"

    assert _discover_project_root(cwd) == tmp_path / "sub" / ".prose-craft" / "voices"


def test_discover_refuses_symlinked_parent(tmp_path: Path) -> None:
    (tmp_path / "parent" / ".prose-craft" / "voices").mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "parent")
    cwd = tmp_path / "link" / "sub"
    cwd.mkdir(parents=True)

    assert _discover_project_root(cwd) is None


def test_discover_refuses_symlinked_marker(tmp_path: Path) -> None:
    real = tmp_path / ".prose-craft" / "voices_real"
    real.mkdir(parents=True)
    (tmp_path / ".prose-craft" / "voices").symlink_to(real)

    assert _discover_project_root(tmp_path) is None


def test_discover_walks_past_intermediate_dirs(tmp_path: Path) -> None:
    (tmp_path / "a" / "b" / "c" / ".prose-craft" / "voices").mkdir(parents=True)
    cwd = tmp_path / "a" / "b" / "c" / "d" / "e" / "f"
    cwd.mkdir(parents=True)

    assert _discover_project_root(cwd) == tmp_path / "a" / "b" / "c" / ".prose-craft" / "voices"


def test_discover_handles_missing_cwd(tmp_path: Path) -> None:
    # CWD that doesn't exist anymore — return None, no exception.
    missing = tmp_path / "deleted"
    # do not mkdir

    assert _discover_project_root(missing) is None


def test_voice_roots_includes_project_between_user_and_shared(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    project = tmp_path / ".prose-craft" / "voices"
    project.mkdir(parents=True)

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    monkeypatch.chdir(tmp_path)

    roots = voice_roots()

    assert roots == [user, project, shared / "prose-craft" / "voices"]


def test_voice_roots_omits_project_when_no_marker(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    monkeypatch.chdir(tmp_path)

    roots = voice_roots()

    assert roots == [user, shared / "prose-craft" / "voices"]
