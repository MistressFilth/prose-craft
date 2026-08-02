"""Prose editor agent (four-pass)."""

from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import EditResult
from prose_craft.agents.tools import read_file, run_voice_check_tool
from prose_craft.orchestrator.deps import EditorDeps
from prose_craft.orchestrator.prompts import EDITOR_SYSTEM_PROMPT


def build_editor(model: str) -> Agent[EditorDeps, EditResult]:
    """Construct the editor agent."""
    return make_sub_agent(
        model=model,
        output_type=EditResult,
        system_prompt=EDITOR_SYSTEM_PROMPT,
        tools=[read_file, run_voice_check_tool],
    )
