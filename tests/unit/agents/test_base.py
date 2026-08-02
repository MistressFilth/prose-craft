"""Tests for prose_craft.agents.base.make_sub_agent."""

from __future__ import annotations

from pydantic_ai.capabilities import DynamicCapability

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import ProseDiagnostic

PREFIX = (
    "You are a prose-craft sub-agent. Do one task precisely and return a structured result.\n\n"
)


def _my_tool(x: int) -> int:
    return x


def test_make_sub_agent_prepends_standard_prefix():
    agent = make_sub_agent("test", ProseDiagnostic, "Do the thing.")
    system_prompt = agent._system_prompts[0]
    assert system_prompt.startswith(PREFIX)


def test_make_sub_agent_preserves_caller_system_prompt():
    body = "Do the thing."
    agent = make_sub_agent("test", ProseDiagnostic, body)
    system_prompt = agent._system_prompts[0]
    assert system_prompt.endswith(body)
    assert system_prompt == PREFIX + body


def test_make_sub_agent_wires_output_type():
    agent = make_sub_agent("test", ProseDiagnostic, "Do the thing.")
    assert agent.output_type is ProseDiagnostic


def test_make_sub_agent_passes_tools_through():
    agent = make_sub_agent("test", ProseDiagnostic, "Do the thing.", tools=[_my_tool])
    function_toolset = agent.toolsets[0]
    assert _my_tool.__name__ in function_toolset.tools


def test_make_sub_agent_passes_capabilities_through():
    marker = object()
    agent = make_sub_agent("test", ProseDiagnostic, "Do the thing.", capabilities=[marker])
    dynamic_caps = [
        c for c in agent._root_capability.capabilities if isinstance(c, DynamicCapability)
    ]
    assert len(dynamic_caps) == 1
    assert dynamic_caps[0].capability_func is marker


def test_make_sub_agent_default_tools_list_is_empty():
    agent = make_sub_agent("test", ProseDiagnostic, "Do the thing.")
    function_toolset = agent.toolsets[0]
    assert list(function_toolset.tools) == []


def test_make_sub_agent_default_capabilities_list_is_empty():
    agent = make_sub_agent("test", ProseDiagnostic, "Do the thing.")
    dynamic_caps = [
        c for c in agent._root_capability.capabilities if isinstance(c, DynamicCapability)
    ]
    assert dynamic_caps == []


def test_make_sub_agent_explicit_empty_tools_and_capabilities():
    agent = make_sub_agent("test", ProseDiagnostic, "Do the thing.", tools=[], capabilities=[])
    function_toolset = agent.toolsets[0]
    assert list(function_toolset.tools) == []
    dynamic_caps = [
        c for c in agent._root_capability.capabilities if isinstance(c, DynamicCapability)
    ]
    assert dynamic_caps == []
