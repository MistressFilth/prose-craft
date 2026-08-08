"""Feature tests for `voice delete`."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


@pytest.fixture
def user_voice(monkeypatch, tmp_path):
    user = tmp_path / "user"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    (user / "alpha" / "voice.md").parent.mkdir(parents=True)
    (user / "alpha" / "voice.md").write_text(
        "---\n"
        "voice: alpha\n"
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
    return user


@pytest.fixture
def shared_tree(monkeypatch, tmp_path):
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
    return user, shared


def test_delete_without_force_refuses(user_voice):
    result = runner.invoke(app, ["voice", "delete", "alpha"])
    assert result.exit_code == 2
    assert "--force" in result.output
    assert (user_voice / "alpha" / "voice.md").is_file()


def test_delete_with_force_removes(user_voice):
    result = runner.invoke(app, ["voice", "delete", "alpha", "--force"])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()
    assert not (user_voice / "alpha").exists()


def test_delete_missing_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "user"))
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    result = runner.invoke(app, ["voice", "delete", "ghost", "--force"])
    assert result.exit_code == 2
    assert "not found" in result.output.lower()


def test_delete_invalid_name_errors(user_voice):
    result = runner.invoke(app, ["voice", "delete", "../escape", "--force"])
    assert result.exit_code == 2
    assert "invalid" in result.output.lower() or "voice name" in result.output.lower()


def test_delete_shared_only_refuses_even_with_force(shared_tree):
    user, shared = shared_tree
    result = runner.invoke(app, ["voice", "delete", "shipped", "--force"])
    assert result.exit_code == 2
    assert "shared" in result.output.lower()
    assert (shared / "prose-craft" / "voices" / "shipped").is_dir()
    assert not (user / "shipped").exists()


def test_delete_user_and_shared_keeps_shared(shared_tree, tmp_path):
    user, shared = shared_tree
    # Add a user copy on top of the shared one
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

    result = runner.invoke(app, ["voice", "delete", "shipped", "--force"])
    assert result.exit_code == 0
    assert "shared" in result.output.lower()  # operator sees the warning
    assert not (user / "shipped").exists()
    assert (shared / "prose-craft" / "voices" / "shipped").is_dir()


def test_delete_with_voices_root_override(user_voice):
    # --voices-root bypasses the multi-root walk
    result = runner.invoke(
        app, ["voice", "delete", "alpha", "--force", "--voices-root", str(user_voice)]
    )
    assert result.exit_code == 0
    assert not (user_voice / "alpha").exists()
