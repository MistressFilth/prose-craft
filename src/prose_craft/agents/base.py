"""Shared factory for sub-agents."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from pydantic_ai import Agent

T = TypeVar("T")


def make_sub_agent(
    model: str,
    output_type: type[T],
    system_prompt: str,
    tools: list[Callable[..., Any]] | None = None,
    capabilities: list[Any] | None = None,
    *,
    format_kwargs: dict[str, object] | None = None,
) -> Agent[Any, T]:
    """Construct a pydantic-ai sub-agent.

    Adds the standard prose-craft sub-agent prefix. Tools and
    capabilities are passed through unchanged.
    """
    prefix = (
        "You are a prose-craft sub-agent. Do one task precisely and return a structured result.\n\n"
    )
    rendered = system_prompt.format(**(format_kwargs or {}))
    return Agent(
        model,
        output_type=output_type,
        system_prompt=prefix + rendered,
        tools=tools or [],
        capabilities=capabilities or [],
    )
