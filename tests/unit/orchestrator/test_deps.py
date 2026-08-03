"""Tests for prose_craft.orchestrator.deps."""

from __future__ import annotations

from pathlib import Path

from prose_craft.orchestrator.deps import (
    AnalysisDeps,
    ArchitectDeps,  # noqa: F401  (symbol-presence check)
    ComposerDeps,
    EditorDeps,
    StylistDeps,
    TuneDeps,  # noqa: F401  (symbol-presence check)
    VoiceDeps,
)


def test_analysis_deps_defaults() -> None:
    d = AnalysisDeps(file_path=Path("x.md"))
    assert d.voice_name is None
    assert d.tolerance == "normal"


def test_editor_deps_optional_voice() -> None:
    d = EditorDeps(file_path=Path("x.md"))
    assert d.voice_name is None


def test_voice_deps_brief_optional() -> None:
    d = VoiceDeps(file_path=Path("x.md"), voice_name="v")
    assert d.brief_path is None


def test_stylist_deps_mode() -> None:
    d = StylistDeps(file_path=Path("x.md"), voice_name="v", mode="draft")
    assert d.mode == "draft"


def test_composer_deps_current_field() -> None:
    d = ComposerDeps(name="v", current_field="purpose")
    assert d.current_field == "purpose"


def test_stylist_deps_accepts_audience() -> None:
    d = StylistDeps(file_path=Path("/tmp/x.md"), voice_name="test")
    assert d.audience is None


def test_analysis_deps_accepts_audience() -> None:
    d = AnalysisDeps(file_path=Path("/tmp/x.md"))
    assert d.audience is None


def test_editor_deps_accepts_audience() -> None:
    d = EditorDeps(file_path=Path("/tmp/x.md"))
    assert d.audience is None


def test_architect_deps_accepts_audience() -> None:
    d = ArchitectDeps(file_path=Path("/tmp/x.md"))
    assert d.audience is None


def test_tune_deps_accepts_audience() -> None:
    d = TuneDeps(file_path=Path("/tmp/x.md"))
    assert d.audience is None


def test_voice_deps_accepts_audience() -> None:
    d = VoiceDeps(file_path=Path("/tmp/x.md"), voice_name="test")
    assert d.audience is None


def test_composer_deps_accepts_audience() -> None:
    d = ComposerDeps(name="test")
    assert d.audience is None
