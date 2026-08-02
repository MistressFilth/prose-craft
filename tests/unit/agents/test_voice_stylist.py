"""Tests for prose_craft.agents.voice_stylist.build_voice_stylist."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, RunContext, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from prose_craft.agents.tools import load_voice, read_file, run_voice_check_tool
from prose_craft.agents.voice_stylist import build_voice_stylist
from prose_craft.orchestrator.deps import StylistDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


def _make_ctx(deps: Any) -> RunContext[Any]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def test_voice_stylist_draft_mode(tmp_path: Path):
    draft = tmp_path / "chapter.md"
    draft.write_text("seed text", encoding="utf-8")
    # Use pydantic-ai's "test" sentinel so the agent constructs without a
    # real provider; the FunctionModel override below drives the run.
    agent = build_voice_stylist("test")
    deps = StylistDeps(file_path=draft, voice_name="MistressFilth", mode="draft")
    payload = {
        "text": "Drafted text in the MistressFilth voice.",
        "change_log": "rules_honored: diction.banned",
        "voice_check_report": None,
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Draft.", deps=deps)
    assert "MistressFilth" in result.output.text
    assert result.output.voice_check_report is None


def test_voice_stylist_toolset_matches_spec():
    """Per spec: voice_stylist gets read_file + load_voice + run_voice_check_tool."""
    agent = build_voice_stylist("test")
    toolset = agent.toolsets[0]
    assert set(toolset.tools) == {
        read_file.__name__,
        load_voice.__name__,
        run_voice_check_tool.__name__,
    }


def test_voice_stylist_read_file_tool_runs(tmp_path: Path):
    draft = tmp_path / "x.md"
    draft.write_text("seed", encoding="utf-8")
    agent = build_voice_stylist("test")
    toolset = agent.toolsets[0]
    tool = toolset.tools[read_file.__name__]
    ctx = _make_ctx(StylistDeps(file_path=draft, voice_name="MistressFilth"))
    assert tool.function(ctx, str(draft)) == "seed"
