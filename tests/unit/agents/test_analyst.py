"""Tests for prose_craft.agents.analyst.build_analyst."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, RunContext, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from prose_craft.agents.analyst import build_analyst
from prose_craft.agents.tools import (
    read_file,
    run_clause_density_tool,
    run_dispersion_tool,
    run_voice_check_tool,
)
from prose_craft.orchestrator.deps import AnalysisDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(fn)


def _make_ctx(deps: Any) -> RunContext[Any]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


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


def test_analyst_toolset_matches_spec():
    """Per spec Agent Contracts table: analyst gets read_file + the three analysis tools."""
    agent = build_analyst("test")
    toolset = agent.toolsets[0]
    names = set(toolset.tools)
    assert names == {
        read_file.__name__,
        run_voice_check_tool.__name__,
        run_dispersion_tool.__name__,
        run_clause_density_tool.__name__,
    }


def test_analyst_clause_density_tool_runs():
    """The clause-density tool returns JSON with the expected keys."""
    agent = build_analyst("test")
    toolset = agent.toolsets[0]
    tool = toolset.tools[run_clause_density_tool.__name__]
    ctx = _make_ctx(AnalysisDeps(file_path=Path("/tmp/x.md")))
    payload = json.loads(tool.function(ctx, "She walked home slowly.", None))
    assert set(payload) == {"ppc_per_1k", "agentless_passive_per_1k"}
    assert isinstance(payload["ppc_per_1k"], float)
