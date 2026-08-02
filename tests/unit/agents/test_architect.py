"""Tests for prose_craft.agents.architect.build_architect."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, RunContext, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from prose_craft.agents.architect import build_architect
from prose_craft.agents.tools import read_file, run_voice_check_tool
from prose_craft.orchestrator.deps import ArchitectDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


def _make_ctx(deps: Any) -> RunContext[Any]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def test_architect_returns_result(tmp_path: Path):
    draft = tmp_path / "chapter.md"
    draft.write_text("Some prose.", encoding="utf-8")
    # Use pydantic-ai's "test" sentinel so the agent constructs without a
    # real provider; the FunctionModel override below drives the run.
    agent = build_architect("test")
    deps = ArchitectDeps(file_path=draft)
    payload = {
        "analysis": "The opening is slow.",
        "diagnosis": "Front-load the inciting incident.",
        "reconstruction_proposal": "Open with the sound.",
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Architect this.", deps=deps)
    assert result.output.analysis == "The opening is slow."
    assert "inciting" in result.output.diagnosis


def test_architect_toolset_matches_spec():
    """Per spec: architect gets read_file + run_voice_check_tool."""
    agent = build_architect("test")
    toolset = agent.toolsets[0]
    assert set(toolset.tools) == {
        read_file.__name__,
        run_voice_check_tool.__name__,
    }


def test_architect_read_file_tool_runs(tmp_path: Path):
    draft = tmp_path / "x.md"
    draft.write_text("open the window", encoding="utf-8")
    agent = build_architect("test")
    toolset = agent.toolsets[0]
    tool = toolset.tools[read_file.__name__]
    ctx = _make_ctx(ArchitectDeps(file_path=draft))
    assert tool.function(ctx, str(draft)) == "open the window"
