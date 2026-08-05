"""End-to-end: every file lands in the directory its role calls for."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from prose_craft import paths
from prose_craft.cli import app

runner = CliRunner()

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX modes only")


def test_voice_init_writes_to_the_data_root(tmp_path: Path) -> None:
    """The profile lands at the expected path.

    Note what this does NOT assert: that the config or cache roots are
    empty. Those are the same directory as the data root on Windows
    (all four collapse onto %LOCALAPPDATA%) and config is the same on
    macOS. Asserting a sibling role's emptiness fails on two of three
    platforms; assert the specific expected path instead.
    """
    result = runner.invoke(app, ["voice", "init", "layout-probe"])
    assert result.exit_code == 0, result.output

    data = tmp_path / ".xdg" / "data" / "prose-craft" / "voices"
    assert (data / "layout-probe" / "voice.md").is_file()


def test_voice_init_creates_nothing_outside_the_voices_tree(tmp_path: Path) -> None:
    """The application data directory holds the voices directory and nothing else."""
    result = runner.invoke(app, ["voice", "init", "layout-probe"])
    assert result.exit_code == 0, result.output

    app_data = tmp_path / ".xdg" / "data" / "prose-craft"
    assert sorted(p.name for p in app_data.iterdir()) == ["voices"]


def test_voices_root_holds_no_dot_directories(tmp_path: Path) -> None:
    """Regression: .composer-state used to be created here."""
    result = runner.invoke(app, ["voice", "init", "layout-probe"])
    assert result.exit_code == 0, result.output

    root = paths.voices_root()
    assert [p.name for p in root.iterdir() if p.name.startswith(".")] == []


def test_voice_list_reads_the_data_root(tmp_path: Path) -> None:
    runner.invoke(app, ["voice", "init", "layout-probe"])
    result = runner.invoke(app, ["voice", "list"])
    assert result.exit_code == 0, result.output
    assert "layout-probe" in result.stdout


def test_config_reports_the_resolved_voices_root(tmp_path: Path) -> None:
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0, result.output
    expected = tmp_path / ".xdg" / "data" / "prose-craft" / "voices"
    assert str(expected) in result.stdout


def test_direct_override_wins_over_the_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = tmp_path / "elsewhere"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(override))

    result = runner.invoke(app, ["voice", "init", "layout-probe"])
    assert result.exit_code == 0, result.output
    assert (override / "layout-probe" / "voice.md").is_file()
    assert not (tmp_path / ".xdg" / "data" / "prose-craft").exists()


def test_prose_craft_override_wins_over_spec_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_XDG_DATA_HOME", str(tmp_path / "override-data"))

    result = runner.invoke(app, ["voice", "init", "layout-probe"])
    assert result.exit_code == 0, result.output
    assert (
        tmp_path / "override-data" / "prose-craft" / "voices" / "layout-probe" / "voice.md"
    ).is_file()


def test_spec_var_redirects_on_every_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """XDG_DATA_HOME is the escape hatch on macOS and Windows too.

    platformdirs ignores it off Linux; this design's own resolution
    layer is what makes it work everywhere.
    """
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "spec-data"))

    result = runner.invoke(app, ["voice", "init", "layout-probe"])
    assert result.exit_code == 0, result.output
    assert (
        tmp_path / "spec-data" / "prose-craft" / "voices" / "layout-probe" / "voice.md"
    ).is_file()


def test_composer_state_is_not_in_the_voices_root(tmp_path: Path) -> None:
    """Agent memory stays out of the user's voice library."""
    runner.invoke(app, ["voice", "init", "layout-probe"])

    composer = paths.composer_state_dir()
    voices = paths.voices_root()
    assert voices not in composer.parents


@posix_only
def test_runtime_dir_is_0700_on_posix(tmp_path: Path) -> None:
    created = paths.app_runtime_dir()
    assert stat.S_IMODE(created.stat().st_mode) == 0o700
