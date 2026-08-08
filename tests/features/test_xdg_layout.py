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

    root = paths.default_voices_root()
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
    voices = paths.default_voices_root()
    assert voices not in composer.parents


@posix_only
def test_runtime_dir_is_0700_on_posix(tmp_path: Path) -> None:
    created = paths.app_runtime_dir()
    assert stat.S_IMODE(created.stat().st_mode) == 0o700


def test_shared_config_sets_baseline_when_user_absent(tmp_path, monkeypatch):
    """A shared XDG_CONFIG_DIRS file sets model when user config absent."""
    from prose_craft.config import load_settings

    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "prose-craft").mkdir()
    (shared / "prose-craft" / "config.toml").write_text(
        'model = "shared-model"\n', encoding="utf-8"
    )

    monkeypatch.setenv("XDG_CONFIG_DIRS", str(shared))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user"))
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)

    settings = load_settings()
    assert settings.model == "shared-model"


def test_user_config_overrides_shared_config(tmp_path, monkeypatch):
    """User XDG_CONFIG_HOME config wins over shared XDG_CONFIG_DIRS."""
    from prose_craft.config import load_settings

    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "prose-craft").mkdir()
    (shared / "prose-craft" / "config.toml").write_text(
        'model = "shared-model"\n', encoding="utf-8"
    )
    user = tmp_path / "user"
    (user / "prose-craft").mkdir(parents=True)
    (user / "prose-craft" / "config.toml").write_text('model = "user-model"\n', encoding="utf-8")

    monkeypatch.setenv("XDG_CONFIG_DIRS", str(shared))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user))
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)

    settings = load_settings()
    assert settings.model == "user-model"


def test_explicit_kwarg_wins_over_shared_and_user(tmp_path, monkeypatch):
    """Explicit kwargs to load_settings win over both shared and user."""
    from prose_craft.config import load_settings

    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "prose-craft").mkdir()
    (shared / "prose-craft" / "config.toml").write_text(
        'model = "shared-model"\n', encoding="utf-8"
    )
    user = tmp_path / "user"
    (user / "prose-craft").mkdir(parents=True)
    (user / "prose-craft" / "config.toml").write_text('model = "user-model"\n', encoding="utf-8")

    monkeypatch.setenv("XDG_CONFIG_DIRS", str(shared))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user))
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)

    settings = load_settings(model="explicit-model")
    assert settings.model == "explicit-model"


def test_invalid_shared_toml_raises_with_path(tmp_path, monkeypatch):
    """Invalid TOML in a shared config surfaces as ConfigurationError carrying the file path."""
    import pytest
    from prose_craft.config import ConfigurationError, load_settings

    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "prose-craft").mkdir()
    (shared / "prose-craft" / "config.toml").write_text(
        "this is not valid toml ===\n", encoding="utf-8"
    )

    monkeypatch.setenv("XDG_CONFIG_DIRS", str(shared))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user"))
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)

    with pytest.raises(ConfigurationError) as excinfo:
        load_settings()
    assert excinfo.value.path == shared / "prose-craft" / "config.toml"


def test_invalid_shared_keys_raise_with_shared_path(tmp_path, monkeypatch):
    """Unknown keys in a shared config surface as ConfigurationError carrying the SHARED path."""
    import pytest
    from prose_craft.config import ConfigurationError, load_settings

    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "prose-craft").mkdir()
    (shared / "prose-craft" / "config.toml").write_text(
        'model = "shared-model"\nunknown_key = "boom"\n', encoding="utf-8"
    )

    monkeypatch.setenv("XDG_CONFIG_DIRS", str(shared))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user"))
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)

    with pytest.raises(ConfigurationError) as excinfo:
        load_settings()
    assert excinfo.value.path == shared / "prose-craft" / "config.toml"


def test_first_shared_dir_wins_over_second(tmp_path, monkeypatch):
    """Multiple XDG_CONFIG_DIRS entries: first wins over second."""
    from prose_craft.config import load_settings

    first = tmp_path / "first"
    first.mkdir()
    (first / "prose-craft").mkdir()
    (first / "prose-craft" / "config.toml").write_text('model = "first-model"\n', encoding="utf-8")
    second = tmp_path / "second"
    second.mkdir()
    (second / "prose-craft").mkdir()
    (second / "prose-craft" / "config.toml").write_text(
        'model = "second-model"\n', encoding="utf-8"
    )

    monkeypatch.setenv("XDG_CONFIG_DIRS", f"{first}{os.pathsep}{second}")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user"))
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)

    settings = load_settings()
    assert settings.model == "first-model"


def test_voice_init_invalidates_persistent_cache(tmp_path, monkeypatch):
    """Building the cache, then running voice init, then re-listing sees the new voice."""
    from prose_craft import xdg

    user_cfg = tmp_path / "user_cfg"
    user_cfg.mkdir()
    user_voices = tmp_path / "user_voices"
    user_voices.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    monkeypatch.setenv("XDG_CONFIG_HOME", str(user_cfg))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_dir))
    monkeypatch.setenv("XDG_DATA_DIRS", "")
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user_voices))
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)

    cache_file = xdg.voices_index_path()
    assert not cache_file.exists()

    # First list builds and persists the cache.
    from typer.testing import CliRunner
    from prose_craft.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["voice", "list"])
    assert result.exit_code == 0, result.output
    assert cache_file.exists()

    # Init a new voice. The write should invalidate the cache.
    result = runner.invoke(app, ["voice", "init", "new-voice"])
    assert result.exit_code == 0, result.output
    assert not cache_file.exists(), "cache should be invalidated by voice init"

    # Next list rebuilds the cache and includes the new voice.
    result = runner.invoke(app, ["voice", "list"])
    assert result.exit_code == 0, result.output
    assert "new-voice" in result.output
