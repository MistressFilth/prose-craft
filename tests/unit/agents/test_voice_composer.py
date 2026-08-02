"""Tests for prose_craft.agents.voice_composer.build_voice_composer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.voice_composer import build_voice_composer
from prose_craft.orchestrator.deps import ComposerDeps


def _function_model_returning_json(payload: list[dict[str, Any]]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # pydantic-ai 2.22.0 wraps non-model output types in a TypedDict
        # keyed by "response"; for list[VoiceDelta] the FunctionModel
        # must therefore return {"response": [...]} for the validator
        # to unpack the list.
        wrapped = {"response": payload}
        return ModelResponse(parts=[TextPart(json.dumps(wrapped))])

    return FunctionModel(fn)


def test_voice_composer_returns_deltas(tmp_path: Path):
    # Use pydantic-ai's "test" sentinel so the agent constructs without a
    # real provider; the FunctionModel override below drives the run.
    agent = build_voice_composer("test", tmp_path)
    deps = ComposerDeps(name="dnova", current_field="purpose")
    payload = [
        {"field": "purpose", "value": "formal memos", "prompt": "What is this voice for?"},
    ]
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Compose step.", deps=deps)
    assert len(result.output) == 1
    assert result.output[0].field == "purpose"
    assert result.output[0].value == "formal memos"
