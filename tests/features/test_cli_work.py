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
