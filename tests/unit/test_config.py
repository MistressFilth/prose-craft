"""Tests for prose_craft.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from prose_craft.config import DEFAULT_MODEL, get_model, get_voices_root


def test_get_model_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    assert get_model() == DEFAULT_MODEL
    assert DEFAULT_MODEL == "anthropic:claude-opus-4-5"


def test_get_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-sonnet-4-5")
    assert get_model() == "anthropic:claude-sonnet-4-5"


def test_get_voices_root_matches_voices_location(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from prose_craft.voices.location import get_voices_root as voices_root

    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert get_voices_root() == voices_root()
