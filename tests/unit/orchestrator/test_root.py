"""Tests for prose_craft.orchestrator.root."""

from __future__ import annotations

import sys
import types

import pytest
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.orchestrator.root import ProseCraft


def _stub_response(content: str):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content)])

    return FunctionModel(fn)


def test_prose_craft_constructs_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", "/tmp/test-voices")
    craft = ProseCraft()
    assert craft.model == "anthropic:claude-opus-4-5"
    assert str(craft.voices_root).endswith("test-voices")


def test_prose_craft_lazy_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lazy accessor caches the agent on first access; second access returns same instance.

    The real `prose_craft.agents.analyst` module lands in task 22, so this
    test injects a fake module via `sys.modules` to exercise the lazy-build
    path today. Replace the `sys.modules` injection with a real factory
    import once task 22 lands.
    """
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", "/tmp/test-voices")

    # Sentinel that stands in for the Agent instance the real factory would return.
    fake_agent = object()

    # Inject a fake `prose_craft.agents.analyst` module so the deferred
    # `from prose_craft.agents.analyst import build_analyst` resolves.
    fake_module = types.ModuleType("prose_craft.agents.analyst")
    fake_module.build_analyst = lambda _model: fake_agent  # noqa: ARG005
    monkeypatch.setitem(sys.modules, "prose_craft.agents.analyst", fake_module)

    craft = ProseCraft()
    # First access builds and caches; second access returns the cached instance.
    a1 = craft.analyst()
    a2 = craft.analyst()
    assert a1 is a2
    assert a1 is fake_agent
