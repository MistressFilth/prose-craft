"""Tools shared by every agent.

These are thin pydantic-ai-compatible wrappers over the deterministic
primitives in ``prose_craft.analysis`` and ``prose_craft.voices``.
The spec's Agent Contracts table (lines 70-79 of
``docs/superpowers/specs/2026-08-01-prose-craft-pydantic-ai-design.md``)
assigns a specific subset of these tools to each agent.

Voice IO tools (``load_voice``, ``read_voice``, ``write_voice``,
``list_voices``, ``apply_voice_delta``) accept a ``root`` keyword
parameter so the agent factory can bind a configured ``voices_root``
via closure — keeping the model-facing schema free of the path while
still threading the configured root through to
``prose_craft.voices.io``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from pydantic_ai import RunContext

from prose_craft.analysis.clause_density import measure_clause_density
from prose_craft.analysis.dispersion import measure_set
from prose_craft.analysis.sentences import tokenize_words
from prose_craft.voices.check import check_voice
from prose_craft.voices.io import (
    list_voices as _io_list_voices,
    read_voice as _io_read_voice,
    read_voice_raw,
    write_voice as _io_write_voice,
)
from prose_craft.voices.model import DictionConfig, VoiceProfile


def read_file(ctx: RunContext[Any], file_path: str) -> str:
    """Read a UTF-8 file and return its contents.

    Resolves the path; raises FileNotFoundError for missing files. The
    agent surface always passes a string for portability.
    """
    path = Path(file_path)
    return path.read_text(encoding="utf-8")


def run_voice_check_tool(
    ctx: RunContext[Any],
    text: str,
    voice_name: str,
) -> str:
    """Run the deterministic voice checker against ``text``.

    Loads the named ``VoiceProfile`` from the standard voice root
    (``prose_craft.paths.voices_root()``) and returns the
    JSON-serialized ``VoiceVerdict``.

    The agent decides whether to layer model-judged entries on top; this
    primitive returns only the deterministic mechanical + statistical
    findings plus the agent-required prompts surfaced for the model.
    """
    profile = _io_read_voice(voice_name)
    verdict = check_voice(text, profile)
    return verdict.model_dump_json()


def run_dispersion_tool(
    ctx: RunContext[Any],
    new_draft: str,
    sibling_paths: list[str],
) -> str:
    """Measure cross-draft dispersion for ``new_draft`` against siblings.

    Reads each path under ``sibling_paths`` as UTF-8 text and computes
    the lexical + structural dispersion profile against the new draft.
    Returns the JSON-serialized ``DispersionProfile``.

    Pass an empty ``sibling_paths`` list to measure the draft in
    isolation (``n=1`` profile with all-zero altitudes).
    """
    siblings = [Path(p).read_text(encoding="utf-8") for p in sibling_paths]
    profile = measure_set(new_draft, siblings)
    return profile.model_dump_json()


def run_clause_density_tool(
    ctx: RunContext[Any],
    text: str,
    voice_name: str | None = None,
) -> str:
    """Measure present participial clauses + agentless passives per 1k words.

    Returns the JSON-serialized ``ClauseDensity``. The ``voice_name``
    argument is reserved for future voice-aware measurement; today it
    is accepted but unused.
    """
    del voice_name  # Reserved for future voice-aware measurement.
    words = tokenize_words(text)
    density = measure_clause_density(text, words)
    return density.model_dump_json()


def load_voice_diction(
    ctx: RunContext[Any],
    voice_name: str,
) -> str:
    """Load the ``DictionConfig`` for ``voice_name`` and return it as JSON.

    Loads the full profile (cheap: one parse, no IO beyond the file)
    and returns only the ``diction`` sub-model. Useful for tune-diction
    weighting without handing the model the entire profile.
    """
    profile = _io_read_voice(voice_name)
    diction = DictionConfig.model_validate(profile.diction.model_dump())
    return diction.model_dump_json()


def load_voice(
    ctx: RunContext[Any],
    voice_name: str,
) -> str:
    """Load the full ``VoiceProfile`` for ``voice_name`` and return it as JSON.

    The prose body is not included — ``_io_read_voice`` discards it
    during parse. Use the ``read_voice`` tool if the body is needed.

    The ``voice_name`` parameter is the routing key: the loaded
    profile's ``voice`` field must equal ``voice_name`` (rejected
    otherwise). The composer's pipeline uses ``load_voice`` to fetch
    the current profile, then ``apply_voice_delta`` to mutate it,
    then ``write_voice`` to persist it.
    """
    profile = _io_read_voice(voice_name)
    if profile.voice != voice_name:
        raise ValueError(
            f"profile.voice={profile.voice!r} does not match voice_name={voice_name!r}"
        )
    return profile.model_dump_json()


def read_voice(ctx: RunContext[Any], voice_name: str) -> str:
    """Return the prose body of ``voice_name``'s voice.md (no front-matter).

    The body is the text after the closing ``---`` marker, preserved
    verbatim by ``read_voice_raw``. Useful for surfacing the
    voice-composer's literal prose choices to a follow-up step.
    """
    _profile, body = read_voice_raw(voice_name)
    return body


def write_voice(
    ctx: RunContext[Any],
    voice_name: str,
    profile_json: str,
    prose_body: str = "",
) -> str:
    """Validate ``profile_json`` and persist the profile to voice.md.

    Round-trips through ``VoiceProfile.model_validate_json`` so the
    stored file always reflects the schema. The ``voice_name``
    argument must match ``profile.voice`` (rejected otherwise) so the
    tool cannot be used to route a payload to the wrong voice.

    When ``prose_body`` is empty (or omitted), the existing prose
    body of ``voice_name``'s voice.md is preserved verbatim. Pass a
    non-empty ``prose_body`` to overwrite the body. Returns a status
    line describing the write.
    """
    profile = VoiceProfile.model_validate_json(profile_json)
    if profile.voice != voice_name:
        raise ValueError(
            f"profile.voice={profile.voice!r} does not match voice_name={voice_name!r}"
        )

    body = prose_body
    if not body:
        try:
            _existing, existing_body = read_voice_raw(voice_name)
            body = existing_body
        except Exception:
            # No prior voice.md; write an empty body.
            body = ""

    path = _io_write_voice(profile, prose_body=body)
    return f"wrote {path}"


def list_voices(ctx: RunContext[Any]) -> str:
    """List every voice under the voices root as JSON-serialized summaries.

    Each summary carries the voice's name and ``updated`` date.
    """
    summaries = _io_list_voices()
    if not summaries:
        return "[]"
    return "[" + ",".join(s.model_dump_json() for s in summaries) + "]"


def apply_voice_delta(
    ctx: RunContext[Any],
    voice_name: str,
    current_profile_json: str,
    delta_json: str,
) -> str:
    """Apply a ``VoiceDelta`` to a profile and return the updated profile JSON.

    ``voice_name`` is validated against ``profile.voice`` (rejected
    otherwise) so the result cannot be silently rerouted to a
    different voice. The delta's ``field`` is also rejected if it is
    ``"voice"`` — the identity field is never mutable via delta.

    Otherwise the delta's ``field`` -> ``value`` mapping is applied
    onto the profile payload, then revalidated against the strict
    ``VoiceProfile`` schema. The ``updated`` date is set to today.

    Returns the updated profile as JSON so the caller can round-trip
    it back through ``write_voice``.
    """
    profile = VoiceProfile.model_validate_json(current_profile_json)
    if profile.voice != voice_name:
        raise ValueError(
            f"profile.voice={profile.voice!r} does not match voice_name={voice_name!r}"
        )

    delta = _load_delta(delta_json)
    if delta.field == "voice":
        raise ValueError(
            "delta.field='voice' is not modifiable via apply_voice_delta; "
            "the voice identity is set at write_voice time"
        )
    if delta.value == profile.voice:
        # Caller asked to set 'voice' to the current value through a
        # different field; no harm, but flag for callers that meant
        # to change identity.
        pass

    payload = profile.model_dump(mode="json")
    payload[delta.field] = delta.value
    payload["updated"] = date.today().isoformat()
    updated = VoiceProfile.model_validate(payload)
    return updated.model_dump_json()


def _load_delta(delta_json: str) -> Any:
    """Validate a VoiceDelta JSON document and return the typed delta.

    Importing ``VoiceDelta`` lazily avoids a top-level cycle between
    ``agents.results`` and ``agents.tools`` at import time.
    """
    from prose_craft.agents.results import VoiceDelta

    return VoiceDelta.model_validate_json(delta_json)


# ---------------------------------------------------------------------------
# Composer factory helpers: bind ``voices_root`` into root-aware closures.
#
# The raw tools above do not include ``root`` in the model-facing
# signature (pydantic-ai would otherwise expose the path in the JSON
# schema). Instead, ``bind_composer_tools`` returns wrapper functions
# that close over a configured root, giving the agent factory a clean
# way to thread ``voices_root`` through to ``prose_craft.voices.io``
# without leaking the path into the tool schema.
# ---------------------------------------------------------------------------


def _coerce_root(root: Path | str | None) -> Path | None:
    """Normalize a strings-or-Path root to Path | None."""
    if root is None:
        return None
    return Path(root)


def bind_composer_tools(voices_root: Path | str) -> dict[str, Any]:
    """Return voice tools bound to ``voices_root``.

    Each returned callable has the same model-facing signature as the
    raw tool in this module; the ``voices_root`` is supplied as a
    closure. This is the bridge between the configured
    :class:`ProseCraft` instance and the IO primitives.
    """
    root = _coerce_root(voices_root)

    def load_voice_bound(ctx: RunContext[Any], voice_name: str) -> str:
        profile = _io_read_voice(voice_name, root=root)
        if profile.voice != voice_name:
            raise ValueError(
                f"profile.voice={profile.voice!r} does not match voice_name={voice_name!r}"
            )
        return profile.model_dump_json()

    def read_voice_bound(ctx: RunContext[Any], voice_name: str) -> str:
        _profile, body = read_voice_raw(voice_name, root=root)
        return body

    def write_voice_bound(
        ctx: RunContext[Any],
        voice_name: str,
        profile_json: str,
        prose_body: str = "",
    ) -> str:
        profile = VoiceProfile.model_validate_json(profile_json)
        if profile.voice != voice_name:
            raise ValueError(
                f"profile.voice={profile.voice!r} does not match voice_name={voice_name!r}"
            )

        body = prose_body
        if not body:
            try:
                _existing, existing_body = read_voice_raw(voice_name, root=root)
                body = existing_body
            except Exception:
                body = ""

        path = _io_write_voice(profile, prose_body=body, root=root)
        return f"wrote {path}"

    def list_voices_bound(ctx: RunContext[Any]) -> str:
        summaries = _io_list_voices(root=root)
        if not summaries:
            return "[]"
        return "[" + ",".join(s.model_dump_json() for s in summaries) + "]"

    def apply_voice_delta_bound(
        ctx: RunContext[Any],
        voice_name: str,
        current_profile_json: str,
        delta_json: str,
    ) -> str:
        profile = VoiceProfile.model_validate_json(current_profile_json)
        if profile.voice != voice_name:
            raise ValueError(
                f"profile.voice={profile.voice!r} does not match voice_name={voice_name!r}"
            )

        delta = _load_delta(delta_json)
        if delta.field == "voice":
            raise ValueError(
                "delta.field='voice' is not modifiable via apply_voice_delta; "
                "the voice identity is set at write_voice time"
            )

        payload = profile.model_dump(mode="json")
        payload[delta.field] = delta.value
        payload["updated"] = date.today().isoformat()
        updated = VoiceProfile.model_validate(payload)
        return updated.model_dump_json()

    # Closure-bound tools get ``<locals>.<name>`` from the closure's
    # ``__name__``; pydantic-ai's FunctionToolset would otherwise
    # advertise ``load_voice_bound`` etc. Override the name so the
    # toolset matches the raw tool names the rest of the codebase
    # (and the spec) use.
    load_voice_bound.__name__ = "load_voice"
    read_voice_bound.__name__ = "read_voice"
    write_voice_bound.__name__ = "write_voice"
    list_voices_bound.__name__ = "list_voices"
    apply_voice_delta_bound.__name__ = "apply_voice_delta"

    return {
        "load_voice": load_voice_bound,
        "read_voice": read_voice_bound,
        "write_voice": write_voice_bound,
        "list_voices": list_voices_bound,
        "apply_voice_delta": apply_voice_delta_bound,
    }


def bind_voice_tools(voices_root: Path | str | None) -> dict[str, Any]:
    """Return read-only voice tools bound to ``voices_root``.

    ``voice_stylist`` and ``voice_checker`` need only the read side of
    the voice-IO surface — ``load_voice``, ``read_voice``,
    ``list_voices``, ``load_voice_diction``, ``run_voice_check_tool``.
    Binding them to a configured root keeps the agents in sync with
    ``--voices-root`` CLI overrides.

    ``None`` is accepted and falls back to the raw (env-default) tools
    so unit tests can pass ``None`` without monkeypatching IO. A non-
    ``None`` root closes over the path and reaches the configured
    store on every call.
    """
    if voices_root is None:
        return {
            "load_voice": load_voice,
            "read_voice": read_voice,
            "list_voices": list_voices,
            "load_voice_diction": load_voice_diction,
            "run_voice_check_tool": run_voice_check_tool,
        }
    root = _coerce_root(voices_root)

    def load_voice_bound(ctx: RunContext[Any], voice_name: str) -> str:
        profile = _io_read_voice(voice_name, root=root)
        if profile.voice != voice_name:
            raise ValueError(
                f"profile.voice={profile.voice!r} does not match voice_name={voice_name!r}"
            )
        return profile.model_dump_json()

    def read_voice_bound(ctx: RunContext[Any], voice_name: str) -> str:
        _profile, body = read_voice_raw(voice_name, root=root)
        return body

    def list_voices_bound(ctx: RunContext[Any]) -> str:
        summaries = _io_list_voices(root=root)
        if not summaries:
            return "[]"
        return "[" + ",".join(s.model_dump_json() for s in summaries) + "]"

    def load_voice_diction_bound(ctx: RunContext[Any], voice_name: str) -> str:
        profile = _io_read_voice(voice_name, root=root)
        diction = DictionConfig.model_validate(profile.diction.model_dump())
        return diction.model_dump_json()

    def run_voice_check_tool_bound(
        ctx: RunContext[Any],
        text: str,
        voice_name: str,
    ) -> str:
        profile = _io_read_voice(voice_name, root=root)
        verdict = check_voice(text, profile)
        return verdict.model_dump_json()

    load_voice_bound.__name__ = "load_voice"
    read_voice_bound.__name__ = "read_voice"
    list_voices_bound.__name__ = "list_voices"
    load_voice_diction_bound.__name__ = "load_voice_diction"
    run_voice_check_tool_bound.__name__ = "run_voice_check_tool"

    return {
        "load_voice": load_voice_bound,
        "read_voice": read_voice_bound,
        "list_voices": list_voices_bound,
        "load_voice_diction": load_voice_diction_bound,
        "run_voice_check_tool": run_voice_check_tool_bound,
    }
