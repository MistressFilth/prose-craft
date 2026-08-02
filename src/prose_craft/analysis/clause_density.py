"""Present participial clause + agentless passive density."""

from __future__ import annotations

import re

from pydantic import BaseModel

_PPC_RE = re.compile(
    r"\b(Walking|Running|Sitting|Standing|Talking|Working|Looking|Holding|"
    r"Carrying|Wearing|Holding|Reading|Writing|Eating|Drinking|Thinking|"
    r"Feeling|Hearing|Watching|Coming|Going|Playing|Crying|Laughing|"
    r"Smiling|Frowning|Sleeping|Waiting|Hoping|Fearing|Loving|Hating|"
    r"Reaching|Pulling|Pushing|Kicking|Striking|Opening|Closing|Lifting|"
    r"Dropping|Falling|Rising|Stopping|Starting|Building|Breaking)\b",
    re.IGNORECASE,
)
_AGENTLESS_PASSIVE_RE = re.compile(
    r"\b(was|were|is|are|been|be|being)\s+(\w+(ed|en|t))\b",
    re.IGNORECASE,
)


class ClauseDensity(BaseModel):
    ppc_per_1k: float
    agentless_passive_per_1k: float


def measure_clause_density(text: str, words: list[str]) -> ClauseDensity:
    """Measure present participial clauses and agentless passives per 1k words."""
    if not words:
        return ClauseDensity(ppc_per_1k=0.0, agentless_passive_per_1k=0.0)
    word_count = len(words)
    ppc = len(_PPC_RE.findall(text))
    passive = len(_AGENTLESS_PASSIVE_RE.findall(text))
    return ClauseDensity(
        ppc_per_1k=round(ppc / word_count * 1000, 1),
        agentless_passive_per_1k=round(passive / word_count * 1000, 1),
    )
