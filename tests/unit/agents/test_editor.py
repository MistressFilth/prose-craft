"""Tests for prose_craft.agents.editor.build_editor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.editor import build_editor
from prose_craft.orchestrator.deps import EditorDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


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
