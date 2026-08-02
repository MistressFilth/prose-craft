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
