"""Tests for prose_craft.agents.tune_diction.build_tune_diction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, RunContext, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from prose_craft.agents.tune_diction import build_tune_diction
from prose_craft.agents.tools import load_voice_diction, read_file
from prose_craft.orchestrator.deps import TuneDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


def _make_ctx(deps: Any) -> RunContext[Any]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def test_tune_diction_returns_substitution_plan(tmp_path: Path):
    draft = tmp_path / "prose.md"
    draft.write_text("We will utilize this approach.", encoding="utf-8")
    # Use pydantic-ai's "test" sentinel so the agent constructs without a
    # real provider; the FunctionModel override below drives the run.
    agent = build_tune_diction("test")
    deps = TuneDeps(file_path=draft)
    payload = {
        "suggestions": [{"instead_of": "utilize", "use": "use", "note": "prefer Germanic"}],
        "voice_weighted": False,
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Tune.", deps=deps)
    assert result.output.suggestions[0].instead_of == "utilize"
    assert result.output.voice_weighted is False


def test_tune_diction_toolset_matches_spec():
    """Per spec: tune_diction gets read_file + load_voice_diction."""
    agent = build_tune_diction("test")
    toolset = agent.toolsets[0]
    assert set(toolset.tools) == {
        read_file.__name__,
        load_voice_diction.__name__,
    }


def test_tune_diction_load_voice_diction_tool_runs(tmp_path: Path, monkeypatch):
    """load_voice_diction reads the voice profile and returns its diction block."""
    voice_dir = tmp_path / "voices" / "MistressFilth"
    voice_dir.mkdir(parents=True)
    voice_md = voice_dir / "voice.md"
    voice_md.write_text(
        "---\n"
        "voice: MistressFilth\n"
        "version: 1\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "register:\n"
        "  funny_serious: 0.5\n"
        "diction:\n"
        "  default_balance: 'germanic-leaning'\n"
        "  banned: ['utilize']\n"
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
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "voices"))
    agent = build_tune_diction("test")
    toolset = agent.toolsets[0]
    tool = toolset.tools[load_voice_diction.__name__]
    ctx = _make_ctx(TuneDeps(file_path=tmp_path / "prose.md"))
    payload = json.loads(tool.function(ctx, "MistressFilth"))
    assert payload["default_balance"] == "germanic-leaning"
    assert payload["banned"] == ["utilize"]
    assert "preferred" in payload
