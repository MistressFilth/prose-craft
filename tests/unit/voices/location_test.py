"""Tests for prose_craft.voices.location."""

from __future__ import annotations

from pathlib import Path

import pytest

from prose_craft.voices import location


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "PROSE_CRAFT_VOICES_ROOT",
        "PROSE_CRAFT_XDG_DATA_HOME",
        "XDG_DATA_HOME",
        "XDG_DATA_DIRS",
    ):
        monkeypatch.delenv(var, raising=False)


def test_voice_roots_user_first(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    roots = location.voice_roots()
    assert roots[0] == user
    assert roots[1] == shared / "prose-craft" / "voices"


def test_voice_roots_no_shared(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "user"))
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    roots = location.voice_roots()
    assert roots == [
        tmp_path / "user",
        Path("/usr/local/share/prose-craft/voices"),
        Path("/usr/share/prose-craft/voices"),
    ]


def test_voice_path_root_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "ignored"))
    explicit = tmp_path / "explicit"
    result = location.voice_path("foo", root=explicit)
    assert result == explicit / "foo" / "voice.md"


def test_voice_path_walks_roots(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (shared / "prose-craft" / "voices" / "alpha").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "alpha" / "voice.md").write_text("x")
    result = location.voice_path("alpha")
    assert result == shared / "prose-craft" / "voices" / "alpha" / "voice.md"


def test_voice_path_user_shadows_shared(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (user / "alpha" / "voice.md").parent.mkdir(parents=True)
    (user / "alpha" / "voice.md").write_text("user")
    (shared / "prose-craft" / "voices" / "alpha" / "voice.md").parent.mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "alpha" / "voice.md").write_text("shared")
    result = location.voice_path("alpha")
    assert result == user / "alpha" / "voice.md"
