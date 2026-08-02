"""Tests for prose_craft.agents.tune_diction.build_tune_diction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.tune_diction import build_tune_diction
from prose_craft.orchestrator.deps import TuneDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


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
