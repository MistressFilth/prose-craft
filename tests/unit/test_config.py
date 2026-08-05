"""Tests for prose_craft.config."""

from __future__ import annotations

import pytest

from prose_craft.config import DEFAULT_MODEL, get_model


def test_get_model_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    assert get_model() == DEFAULT_MODEL
    assert DEFAULT_MODEL == "anthropic:claude-opus-4-5"


def test_get_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-sonnet-4-5")
    assert get_model() == "anthropic:claude-sonnet-4-5"


def test_get_voices_root_re_export_is_gone() -> None:
    """Callers import voices_root from prose_craft.paths now."""
    from prose_craft import config

    assert not hasattr(config, "get_voices_root")
