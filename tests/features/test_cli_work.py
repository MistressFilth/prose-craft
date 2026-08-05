"""Behavioral tests for the four prose-work subcommands (analyze, edit, architect, tune-diction)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


def test_analyze_metrics_only_renders_prose_diagnostic(monkeypatch, tmp_path: Path) -> None:
    """`analyze --metrics-only` runs the deterministic path (no LLM) and renders the diagnostic."""
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    draft = tmp_path / "chapter.md"
    draft.write_text("She walked home. The dog ran.", encoding="utf-8")

    result = runner.invoke(app, ["analyze", str(draft), "--metrics-only"])

    assert result.exit_code == 0, result.stdout
    assert "Mean sentence length" in result.stdout or "Rhythm" in result.stdout


def test_voice_draft_scratch_lives_in_runtime_dir_and_is_removed(
    tmp_path: Path, monkeypatch
) -> None:
    """Without --to, the scratch file is created under the runtime dir and cleaned up.

    Asserts the path the stylist actually received, so this fails while
    the scratch file still goes to the system temp directory.
    """
    from unittest.mock import patch

    from prose_craft import paths
    from prose_craft.voices.model import AudienceCeiling, AudiencesBlock
    from tests.features.test_voice_audience_cli import FakeAgent, _make_voice

    voice_root = tmp_path / "voices"
    _make_voice(voice_root, "test", audiences=AudiencesBlock(private=AudienceCeiling()))
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))

    scratch = paths.scratch_dir()
    assert list(scratch.iterdir()) == []

    agent = FakeAgent()
    with patch("prose_craft.orchestrator.root.ProseCraft.voice_stylist", return_value=agent):
        result = runner.invoke(app, ["voice", "draft", "test", "brief text"])

    assert result.exit_code == 0, result.stdout
    used = Path(agent.deps.file_path)
    assert used.parent == scratch
    assert not used.exists()
    assert list(scratch.iterdir()) == []


def test_voice_draft_removes_scratch_when_the_run_raises(tmp_path: Path, monkeypatch) -> None:
    """The finally clause fires on the failure path too."""
    from unittest.mock import patch

    from prose_craft import paths
    from prose_craft.voices.model import AudienceCeiling, AudiencesBlock
    from tests.features.test_voice_audience_cli import _make_voice

    voice_root = tmp_path / "voices"
    _make_voice(voice_root, "test", audiences=AudiencesBlock(private=AudienceCeiling()))
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))

    scratch = paths.scratch_dir()

    with patch(
        "prose_craft.orchestrator.root.ProseCraft.voice_stylist",
        side_effect=RuntimeError("boom"),
    ):
        result = runner.invoke(app, ["voice", "draft", "test", "brief text"])

    assert result.exit_code != 0
    assert list(scratch.iterdir()) == []
