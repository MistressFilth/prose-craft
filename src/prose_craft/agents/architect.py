"""Prose architect agent (Opus)."""

from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import ArchitectResult
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import ArchitectDeps
from prose_craft.orchestrator.prompts import ARCHITECT_SYSTEM_PROMPT


def build_architect(model: str) -> Agent[ArchitectDeps, ArchitectResult]:
    """Construct the architect agent."""
    return make_sub_agent(
        model=model,
        output_type=ArchitectResult,
        system_prompt=ARCHITECT_SYSTEM_PROMPT,
        tools=[read_file],
    )
