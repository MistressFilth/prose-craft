"""Tests for prose_craft.agents.voice_checker.build_voice_checker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.voice_checker import build_voice_checker
from prose_craft.orchestrator.deps import VoiceDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


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
