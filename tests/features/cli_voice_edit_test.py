"""Feature tests for auto-shadow before voice edit."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


@pytest.fixture
def shipped_voice(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (shared / "prose-craft" / "voices" / "shipped").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "shipped" / "voice.md").write_text(
        "---\n"
        "voice: shipped\n"
        "version: 1\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "register: {}\n"
        "diction: {}\n"
        "rhythm: {}\n"
        "syntax: {}\n"
        "lexicon: {}\n"
        "structure: {}\n"
        "---\nbody"
    )
    target = tmp_path / "draft.txt"
    target.write_text("draft prose to edit")
    return user, shared, target


def test_edit_shadows_shared_into_user(monkeypatch, shipped_voice, tmp_path):
    user, _, target = shipped_voice
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-opus-4-5")
    runner.invoke(app, ["voice", "edit", str(target), "--voice", "shipped"])
    assert (user / "shipped" / "voice.md").is_file()


def test_edit_user_voice_does_not_reshadow(monkeypatch, shipped_voice, tmp_path):
    user, _, target = shipped_voice
    (user / "shipped" / "voice.md").parent.mkdir(parents=True)
    (user / "shipped" / "voice.md").write_text(
        "---\n"
        "voice: shipped\n"
        "version: 1\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "register: {}\n"
        "diction: {}\n"
        "rhythm: {}\n"
        "syntax: {}\n"
        "lexicon: {}\n"
        "structure: {}\n"
        "purpose: LOCAL\n"
        "---\nbody"
    )
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-opus-4-5")
    runner.invoke(app, ["voice", "edit", str(target), "--voice", "shipped"])
    text = (user / "shipped" / "voice.md").read_text()
    assert "LOCAL" in text


def test_edit_voices_root_override_shadows_to_override_root(monkeypatch, shipped_voice, tmp_path):
    user, _, target = shipped_voice
    override = tmp_path / "override"
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-opus-4-5")
    runner.invoke(
        app,
        [
            "voice",
            "edit",
            str(target),
            "--voice",
            "shipped",
            "--voices-root",
            str(override),
        ],
    )
    assert (override / "shipped" / "voice.md").is_file()
    assert not (user / "shipped" / "voice.md").is_file()
