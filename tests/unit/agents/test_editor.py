"""Tests for prose_craft.agents.editor.build_editor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, RunContext, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from prose_craft.agents.editor import build_editor
from prose_craft.agents.tools import read_file, run_voice_check_tool
from prose_craft.orchestrator.deps import EditorDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


def _make_ctx(deps: Any) -> RunContext[Any]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def test_editor_returns_edit_result(tmp_path: Path):
    draft = tmp_path / "chapter.md"
    draft.write_text("Original prose.", encoding="utf-8")
    agent = build_editor("test")
    deps = EditorDeps(file_path=draft)
    payload = {
        "changes": [{"before": "Original prose.", "after": "New prose.", "why": "tighter"}],
        "change_log": "rules_honored: x",
        "rules_honored": ["x"],
        "fallback_dimensions": [],
        "agent_required": [],
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Edit this.", deps=deps)
    assert result.output.changes[0].after == "New prose."
    assert result.output.rules_honored == ["x"]


def test_editor_toolset_matches_spec():
    """Per spec: editor gets read_file + run_voice_check_tool."""
    agent = build_editor("test")
    toolset = agent.toolsets[0]
    assert set(toolset.tools) == {
        read_file.__name__,
        run_voice_check_tool.__name__,
    }


def test_editor_read_file_tool_runs(tmp_path: Path):
    """Sanity-check the read_file tool via direct invocation."""
    draft = tmp_path / "x.md"
    draft.write_text("hello world", encoding="utf-8")
    agent = build_editor("test")
    toolset = agent.toolsets[0]
    tool = toolset.tools[read_file.__name__]
    ctx = _make_ctx(EditorDeps(file_path=draft))
    assert tool.function(ctx, str(draft)) == "hello world"
