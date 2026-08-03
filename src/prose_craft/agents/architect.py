"""Prose architect agent (Opus)."""

from __future__ import annotations

from prose_craft.voices.audience import ResolvedAudience

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import ArchitectResult
from prose_craft.agents.tools import read_file, run_voice_check_tool
from prose_craft.orchestrator.deps import ArchitectDeps
from prose_craft.orchestrator.prompts import ARCHITECT_SYSTEM_PROMPT, format_audience_block


def build_architect(model: str, *, audience: ResolvedAudience | None = None) -> Agent[ArchitectDeps, ArchitectResult]:
    """Construct the architect agent."""
    rendered = ARCHITECT_SYSTEM_PROMPT.format(audience_block=format_audience_block(audience))
    return make_sub_agent(
        model=model,
        output_type=ArchitectResult,
        system_prompt=rendered,
        tools=[read_file, run_voice_check_tool],
    )
