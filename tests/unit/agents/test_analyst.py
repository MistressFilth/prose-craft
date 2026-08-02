"""Tests for prose_craft.agents.analyst.build_analyst."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.analyst import build_analyst
from prose_craft.orchestrator.deps import AnalysisDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


def test_analyst_returns_prose_diagnostic(tmp_path: Path):
    draft = tmp_path / "chapter.md"
    draft.write_text("She walked home. The dog ran. Birds sang.", encoding="utf-8")
    # Use pydantic-ai's "test" sentinel so the agent constructs without a
    # real provider; the FunctionModel override below drives the run.
    agent = build_analyst("test")
    deps = AnalysisDeps(file_path=draft)
    response_payload = {
        "metrics": {"word_count": 9, "sentence_count": 3},
        "issues": ["low variance"],
    }
    with agent.override(model=_function_model_returning_json(response_payload)):
        result = agent.run_sync("Analyze this.", deps=deps)
    assert result.output.metrics["word_count"] == 9
    assert result.output.issues == ["low variance"]
