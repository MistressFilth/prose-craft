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


def test_show_annotates_shared_origin(monkeypatch, tmp_path):
    """`voice show <name>` prepends `[shared]` for a voice from $XDG_DATA_DIRS.

    The annotation gives operators a one-line signal of where a voice
    came from without having to cross-reference `voice list`. Pairs
    with the per-origin list filter above so the same vocabulary
    appears across both commands.

    The fixture profile is parseable end-to-end (VoiceProfile rejects
    extras and requires every D-block) so ``voice show`` can complete
    the full render; the assertion is on the annotation, not the body.
    """
    from typer.testing import CliRunner

    from prose_craft.cli import app

    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (shared / "prose-craft" / "voices" / "shipped").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "shipped" / "voice.md").write_text(
        "---\n"
        "voice: shipped\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "register: {}\n"
        "diction: {}\n"
        "rhythm: {}\n"
        "syntax: {}\n"
        "lexicon: {}\n"
        "structure: {}\n"
        "---\n"
        "body\n"
    )

    result = CliRunner().invoke(app, ["voice", "show", "shipped"])

    assert result.exit_code == 0, result.output
    assert "[shared]" in result.stdout
    assert "shipped" in result.stdout


def test_show_rejects_invalid_name_in_shared_root_raw(monkeypatch, tmp_path):
    """`voice show <invalid> --raw` must still raise ``VoiceNameError``.

    Regression: ``VoiceIndex.build()`` enumerates directory names
    without checking ``_NAME_RE``, so an invalidly named shared
    directory like ``123bad/voice.md`` is picked up by the index even
    though it would be rejected by ``voice_path()``. The previous
    default-branch implementation validated the name only when the
    index returned ``None`` — when the index DID match, ``--raw`` read
    ``entry.path`` directly and bypassed the regex check entirely. The
    fix validates the name BEFORE the index lookup so the documented
    ``VoiceNameError`` → exit-2 wording is preserved across both
    branches.
    """
    from typer.testing import CliRunner

    from prose_craft.cli import app

    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    # ``123bad`` fails ``_NAME_RE`` (must start with a letter) but
    # VoiceIndex.build() will happily pick up the directory.
    (shared / "prose-craft" / "voices" / "123bad").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "123bad" / "voice.md").write_text(
        "---\n"
        "voice: 123bad\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "register: {}\n"
        "diction: {}\n"
        "rhythm: {}\n"
        "syntax: {}\n"
        "lexicon: {}\n"
        "structure: {}\n"
        "---\n"
        "body\n"
    )

    result = CliRunner().invoke(app, ["voice", "show", "123bad", "--raw"])

    assert result.exit_code == 2, result.output
    assert "invalid voice name" in result.output
    assert "Traceback" not in result.output


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