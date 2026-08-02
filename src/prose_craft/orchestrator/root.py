"""ProseCraft composition root.

Constructed once per CLI invocation or MCP request. Owns model
selection, voice location, and the log level. Lazy-builds agents on
first access so that an importer pays only for the agents it actually
exercises.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic_ai import Agent

from prose_craft.agents.results import (
    ArchitectResult,
    DraftResult,
    EditResult,
    ProseDiagnostic,
    SubstitutionPlan,
    VoiceDelta,
)
from prose_craft.config import get_model, get_voices_root
from prose_craft.orchestrator.deps import (
    AnalysisDeps,
    ArchitectDeps,
    ComposerDeps,
    EditorDeps,
    StylistDeps,
    TuneDeps,
    VoiceDeps,
)
from prose_craft.voices.check import VoiceVerdict

__all__ = ["ProseCraft"]

# Generic over the factory's return type. Unconstrained (rather than
# `bound=Agent`) because `Agent` is itself generic in `[DepsType,
# OutputType]` and `Agent[AnalysisDeps, ProseDiagnostic]` is not a
# subtype of the bare `Agent` class. The cache assignment and the
# per-accessor return types are what keep callers honest; the type
# ignores on the cache boundary document the upcast from `T` to `Agent`.
# TODO(whole-branch-review): Each agent should expose the deterministic
# primitives as tools per the spec's Agent Contracts table. The current
# implementation gives every agent only `read_file`. Decide between:
# (a) wrapping the analysis primitives as per-agent tools and rewriting
# the per-agent tests, or (b) amending the spec to "model handles analysis
# in-context." Defer the decision to the user; do not pick arbitrarily.

T = TypeVar("T")

# Per-line `# type: ignore[import-untyped]` comments on the seven
# `from prose_craft.agents.<x> import build_<x>` statements below are
# TEMPORARY: the `prose_craft.agents.*` package and its factories do not
# exist yet on this branch (Tasks 22-29 land them). Remove every
# `# type: ignore[import-untyped]` in this file as part of the PR that
# introduces the matching agent module. Until then, the inline imports
# remain correct, the cache key still works, and the test injects the
# factory via `sys.modules` so we can exercise the lazy path.


class ProseCraft:
    """Single composition root for CLI + MCP + plugin-adapter callers."""

    def __init__(
        self,
        *,
        model: str | None = None,
        voices_root: Path | None = None,
        log_level: str = "INFO",
    ) -> None:
        self.model = model or get_model()
        self.voices_root = (voices_root or get_voices_root()).resolve()
        self.log_level = log_level
        self._agents: dict[str, Agent] = {}

    def _lazy(self, key: str, factory: Callable[[], T]) -> T:
        if key not in self._agents:
            self._agents[key] = factory()  # type: ignore[assignment]
        return self._agents[key]  # type: ignore[return-value]

    def analyst(self) -> Agent[AnalysisDeps, ProseDiagnostic]:
        from prose_craft.agents.analyst import build_analyst

        return self._lazy("analyst", lambda: build_analyst(self.model))

    def editor(self) -> Agent[EditorDeps, EditResult]:
        from prose_craft.agents.editor import build_editor

        return self._lazy("editor", lambda: build_editor(self.model))

    def architect(self) -> Agent[ArchitectDeps, ArchitectResult]:
        from prose_craft.agents.architect import build_architect

        return self._lazy("architect", lambda: build_architect(self.model))

    def tune_diction(self) -> Agent[TuneDeps, SubstitutionPlan]:
        from prose_craft.agents.tune_diction import build_tune_diction

        return self._lazy("tune_diction", lambda: build_tune_diction(self.model))

    def voice_checker(self) -> Agent[VoiceDeps, VoiceVerdict]:
        from prose_craft.agents.voice_checker import build_voice_checker

        return self._lazy("voice_checker", lambda: build_voice_checker(self.model))

    def voice_stylist(self) -> Agent[StylistDeps, DraftResult]:
        from prose_craft.agents.voice_stylist import build_voice_stylist

        return self._lazy("voice_stylist", lambda: build_voice_stylist(self.model))

    def voice_composer(self) -> Agent[ComposerDeps, list[VoiceDelta]]:
        from prose_craft.agents.voice_composer import build_voice_composer

        return self._lazy(
            "voice_composer",
            lambda: build_voice_composer(self.model, self.voices_root),
        )
