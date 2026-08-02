"""Tests for prose_craft.agents.voice_checker.build_voice_checker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, RunContext, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from prose_craft.agents.tools import load_voice, read_file
from prose_craft.agents.voice_checker import build_voice_checker
from prose_craft.orchestrator.deps import VoiceDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


def _make_ctx(deps: Any) -> RunContext[Any]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def test_voice_checker_returns_verdict(tmp_path: Path):
    draft = tmp_path / "prose.md"
    draft.write_text("We will utilize this.", encoding="utf-8")
    # Use pydantic-ai's "test" sentinel so the agent constructs without a
    # real provider; the FunctionModel override below drives the run.
    agent = build_voice_checker("test")
    deps = VoiceDeps(file_path=draft, voice_name="dnova")
    payload = {
        "mechanical": [],
        "statistical": [],
        "judgments_needed": [],
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Check.", deps=deps)
    assert result.output.mechanical == []
    assert result.output.judgments_needed == []


def test_voice_checker_toolset_matches_spec():
    """Per spec: voice_checker gets read_file + load_voice."""
    agent = build_voice_checker("test")
    toolset = agent.toolsets[0]
    assert set(toolset.tools) == {
        read_file.__name__,
        load_voice.__name__,
    }


def test_voice_checker_load_voice_tool_runs(tmp_path: Path, monkeypatch):
    """load_voice returns the full VoiceProfile JSON for a voice on disk."""
    voice_dir = tmp_path / "voices" / "dnova"
    voice_dir.mkdir(parents=True)
    (voice_dir / "voice.md").write_text(
        "---\n"
        "voice: dnova\n"
        "version: 1\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "register:\n"
        "  funny_serious: 0.5\n"
        "diction:\n"
        "  default_balance: 'germanic-leaning'\n"
        "  banned: []\n"
        "  preferred: []\n"
        "  germanic_for: []\n"
        "  latinate_for: []\n"
        "  inherit_lexicons: []\n"
        "rhythm:\n"
        "  target_mean_sentence: null\n"
        "  target_variation: null\n"
        "  paragraph_shape: null\n"
        "  one_sentence_paragraphs: null\n"
        "  forbidden_patterns: []\n"
        "syntax:\n"
        "  em_dashes: null\n"
        "  colons: null\n"
        "  semicolons: null\n"
        "  parentheticals: null\n"
        "  fragments: null\n"
        "  bullets: null\n"
        "  questions: null\n"
        "lexicon:\n"
        "  pet_phrases: []\n"
        "  characteristic_openers: []\n"
        "  characteristic_closers: []\n"
        "  taboo_phrases: []\n"
        "structure:\n"
        "  opening: null\n"
        "  closing: null\n"
        "  transitions: null\n"
        "  emphasis: null\n"
        "  citations: null\n"
        "---\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "voices"))
    agent = build_voice_checker("test")
    toolset = agent.toolsets[0]
    tool = toolset.tools[load_voice.__name__]
    ctx = _make_ctx(VoiceDeps(file_path=tmp_path / "prose.md", voice_name="dnova"))
    payload = json.loads(tool.function(ctx, "dnova"))
    assert payload["voice"] == "dnova"
    assert payload["diction"]["default_balance"] == "germanic-leaning"
