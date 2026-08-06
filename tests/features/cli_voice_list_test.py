"""Feature tests for the `voice list` command with shared roots."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


@pytest.fixture
def voices_tree(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared_a = tmp_path / "shared_a"
    shared_b = tmp_path / "shared_b"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", f"{shared_a}:{shared_b}")

    (user / "local").mkdir(parents=True)
    (user / "local" / "voice.md").write_text("---\nvoice: local\n---\n")

    (shared_a / "prose-craft" / "voices" / "shipped").mkdir(parents=True)
    (shared_a / "prose-craft" / "voices" / "shipped" / "voice.md").write_text(
        "---\nvoice: shipped\n---\n"
    )

    (shared_b / "prose-craft" / "voices" / "extra").mkdir(parents=True)
    (shared_b / "prose-craft" / "voices" / "extra" / "voice.md").write_text(
        "---\nvoice: extra\n---\n"
    )
    return user, shared_a, shared_b


def test_list_shows_all_three(voices_tree):
    result = runner.invoke(app, ["voice", "list"])
    assert result.exit_code == 0
    assert "local" in result.stdout
    assert "[user]" in result.stdout
    assert "shipped" in result.stdout
    assert "[shared]" in result.stdout
    assert "extra" in result.stdout


def test_list_origin_filter_user(voices_tree):
    result = runner.invoke(app, ["voice", "list", "--origin", "user"])
    assert result.exit_code == 0
    assert "local" in result.stdout
    assert "shipped" not in result.stdout
    assert "extra" not in result.stdout


def test_list_origin_filter_shared(voices_tree):
    result = runner.invoke(app, ["voice", "list", "--origin", "shared"])
    assert result.exit_code == 0
    assert "local" not in result.stdout
    assert "shipped" in result.stdout
    assert "extra" in result.stdout


def test_list_voices_root_override_single_root_only(monkeypatch, tmp_path):
    """Explicit --voices-root preserves v0.4.0 single-root semantics.

    Regression: when the user supplies ``--voices-root PATH`` to the
    ``voice list`` subcommand, the shared roots in ``$XDG_DATA_DIRS``
    must be ignored — the user is asking to inspect that exact
    directory, not the merged multi-root view. Any drift here means a
    shell alias or scripted override is silently seeing voices from
    locations the caller did not ask about.

    Setup uses ``voice init`` (rather than a hand-rolled voice file)
    because the single-root path goes through ``list_voices()``,
    which parses the profile; the multi-root path through
    ``VoiceIndex.build()`` does not. Using the CLI template keeps the
    parseable profile out of the test fixture.
    """
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))

    init_result = runner.invoke(app, ["voice", "init", "local"])
    assert init_result.exit_code == 0, init_result.output

    (shared / "prose-craft" / "voices" / "shipped").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "shipped" / "voice.md").write_text(
        "---\nvoice: shipped\n---\n"
    )

    result = runner.invoke(app, ["voice", "list", "--voices-root", str(user)])
    assert result.exit_code == 0, result.output
    assert "local" in result.stdout
    assert "shipped" not in result.stdout
    assert "[shared]" not in result.stdout