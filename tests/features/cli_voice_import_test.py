"""Feature tests for `voice import`."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


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


def test_import_copies_shared_to_user(shared_tree):
    user, _ = shared_tree
    result = runner.invoke(app, ["voice", "import", "shipped"])
    assert result.exit_code == 0
    assert (user / "shipped" / "voice.md").is_file()


def test_import_missing_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "user"))
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    result = runner.invoke(app, ["voice", "import", "ghost"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_import_already_local_errors(monkeypatch, tmp_path):
    user = tmp_path / "user"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
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
    result = runner.invoke(app, ["voice", "import", "alpha"])
    assert result.exit_code == 1
    assert "already" in result.output.lower()
