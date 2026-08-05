"""In-process behavioral tests for the FastMCP server."""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastmcp import Client

import prose_craft.mcp as mcp_module
from prose_craft.agents.results import (
    ArchitectResult,
    EditResult,
    ProseDiagnostic,
    SubstitutionPlan,
    VoiceDelta,
)
from prose_craft.mcp import mcp


@pytest.fixture
def mcp_client() -> Client:
    """Connect a FastMCP client to the server in the same process."""
    return Client(mcp)


class _FakeAgent:
    def __init__(self, output: object) -> None:
        self._output = output

    async def run(self, _prompt: str, *, deps: object) -> SimpleNamespace:
        return SimpleNamespace(output=self._output)


class _FakeCraft:
    def analyst(self, **_kwargs: object) -> _FakeAgent:
        return _FakeAgent(ProseDiagnostic(metrics=None, issues=[]))

    def editor(self, **_kwargs: object) -> _FakeAgent:
        return _FakeAgent(EditResult(change_log="deterministic edit"))

    def architect(self, **_kwargs: object) -> _FakeAgent:
        return _FakeAgent(
            ArchitectResult(
                analysis="deterministic analysis",
                diagnosis="deterministic diagnosis",
                reconstruction_proposal="deterministic proposal",
            )
        )

    def tune_diction(self, **_kwargs: object) -> _FakeAgent:
        return _FakeAgent(SubstitutionPlan(voice_weighted=True))

    def voice_composer(self, **_kwargs: object) -> _FakeAgent:
        return _FakeAgent([VoiceDelta(field="purpose", value="test voice", prompt="test prompt")])


def _tool_text(result: Any) -> str:
    return str(result.content[0].text)


def _tool_json(result: Any) -> dict[str, Any]:
    return json.loads(_tool_text(result))


def _resource_text(result: Sequence[Any]) -> str:
    return str(result[0].text)


def _write_voice(
    root: Path,
    name: str = "MistressFilth",
    *,
    banned: str = "[]",
    with_audiences: bool = False,
) -> str:
    audiences = (
        "audiences:\n"
        "  external:\n"
        "    severity_ceiling: 4\n"
        "    dial_ceiling: 0.8\n"
        "    surface_filter:\n"
        "      close: [memo]\n"
        if with_audiences
        else ""
    )
    text = (
        "---\n"
        f"voice: {name}\n"
        "version: 1\n"
        "created: 2026-08-01\n"
        "updated: 2026-08-01\n"
        "register: {}\n"
        "diction:\n"
        f"  banned: {banned}\n"
        "rhythm: {}\n"
        "syntax: {}\n"
        "lexicon: {}\n"
        "structure: {}\n"
        f"{audiences}"
        "---\n"
    )
    voice_file = root / name / "voice.md"
    voice_file.parent.mkdir(parents=True)
    voice_file.write_text(text, encoding="utf-8")
    return text


def _patch_fake_craft(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_module, "_craft", lambda: _FakeCraft())


def test_mcp_server_module_imports() -> None:
    assert mcp.name == "prose-craft"


def test_run_stdio_callable() -> None:
    assert callable(mcp_module.run_stdio)


@pytest.mark.asyncio
async def test_mcp_lists_all_tools_and_resource_routes(mcp_client: Client) -> None:
    async with mcp_client:
        tools = await mcp_client.list_tools()
        assert {tool.name for tool in tools} == {
            "analyze_prose",
            "voice_check",
            "dispersion_check",
            "clause_density_check",
            "edit_prose",
            "architect_prose",
            "tune_diction",
            "voice_compose_step",
        }
        resources = await mcp_client.list_resources()
        templates = await mcp_client.list_resource_templates()
        assert {str(resource.uri) for resource in resources} == {"prose://voices"}
        assert {template.uriTemplate for template in templates} == {"prose://voices/{name}"}


@pytest.mark.asyncio
async def test_mcp_list_voices_resource_empty(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An empty user root shows "(no voices)" — no bundled fallback."""
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    async with mcp_client:
        result = await mcp_client.read_resource("prose://voices")
        assert "(no voices)" in _resource_text(result)


@pytest.mark.asyncio
async def test_mcp_list_voices_resource_with_voice(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path)
    async with mcp_client:
        result = await mcp_client.read_resource("prose://voices")
        assert "MistressFilth" in _resource_text(result)


@pytest.mark.asyncio
async def test_mcp_read_voice_resource_returns_raw_file(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    body = (
        "---\n"
        "voice: MistressFilth\n"
        "version: 1\n"
        "created: 2026-08-01\n"
        "updated: 2026-08-01\n"
        "register: {}\n"
        "diction: {}\n"
        "rhythm: {}\n"
        "syntax: {}\n"
        "lexicon: {}\n"
        "structure: {}\n"
        "---\n\n"
        "# Body\n\n"
        "This voice is X.\n"
    )
    voice_file = tmp_path / "MistressFilth" / "voice.md"
    voice_file.parent.mkdir()
    voice_file.write_text(body, encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.read_resource("prose://voices/MistressFilth")
        assert _resource_text(result) == body


@pytest.mark.asyncio
async def test_mcp_analyze_prose_tool(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    draft = tmp_path / "chapter.md"
    draft.write_text("She walked home. The dog ran. Birds sang.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "analyze_prose",
            {"file_path": str(draft), "metrics_only": True},
        )
        data = _tool_json(result)
        assert "metrics" in data


@pytest.mark.asyncio
async def test_mcp_voice_check_tool(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, banned="[utilize]")
    draft = tmp_path / "p.md"
    draft.write_text("We will utilize this.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "voice_check",
            {"file_path": str(draft), "voice": "MistressFilth"},
        )
        data = _tool_json(result)
        assert "mechanical" in data


@pytest.mark.asyncio
async def test_mcp_dispersion_check_tool(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    draft = tmp_path / "draft.md"
    sibling = tmp_path / "sibling.md"
    draft.write_text("She walked home. The dog ran.", encoding="utf-8")
    sibling.write_text("Rain crossed town. The lamps burned.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "dispersion_check",
            {"new_draft_path": str(draft), "siblings": [str(sibling)]},
        )
        data = _tool_json(result)
        assert data["n"] == 2
        assert "altitude_1" in data


@pytest.mark.asyncio
async def test_mcp_clause_density_check_tool(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    draft = tmp_path / "draft.md"
    draft.write_text("Walking home, she saw the door was opened.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "clause_density_check",
            {"file_path": str(draft)},
        )
        data = _tool_json(result)
        assert "ppc_per_1k" in data
        assert "agentless_passive_per_1k" in data


@pytest.mark.asyncio
async def test_mcp_edit_prose_tool(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_fake_craft(monkeypatch)
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool("edit_prose", {"file_path": str(draft)})
        data = _tool_json(result)
        assert data["change_log"] == "deterministic edit"


@pytest.mark.asyncio
async def test_mcp_architect_prose_tool(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_fake_craft(monkeypatch)
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool("architect_prose", {"file_path": str(draft)})
        data = _tool_json(result)
        assert data["diagnosis"] == "deterministic diagnosis"


@pytest.mark.asyncio
async def test_mcp_tune_diction_tool(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_fake_craft(monkeypatch)
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool("tune_diction", {"file_path": str(draft)})
        data = _tool_json(result)
        assert data["voice_weighted"] is True


@pytest.mark.asyncio
async def test_mcp_voice_compose_step_tool(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_fake_craft(monkeypatch)
    async with mcp_client:
        result = await mcp_client.call_tool(
            "voice_compose_step",
            {"name": "test-voice", "current_field": "purpose"},
        )
        data = json.loads(_tool_text(result))
        assert data == [{"field": "purpose", "value": "test voice", "prompt": "test prompt"}]


@pytest.mark.asyncio
async def test_mcp_voice_check_accepts_audience_param(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """voice_check resolves supplied audience knobs and applies the target surface."""
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, with_audiences=True)
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "voice_check",
            {
                "file_path": str(draft),
                "voice": "MistressFilth",
                "audience": "external",
                "severity_ceiling": 2,
                "dial_ceiling": 0.4,
                "surface": "memo",
            },
        )
        data = _tool_json(result)
        audience = data["audience"]
        assert isinstance(audience, dict)
        assert audience["name"] == "external"
        assert audience["severity_ceiling"] == 2
        assert audience["dial_ceiling"] == 0.4
        assert audience["surface_target"] == "memo"
        assert any(
            finding["rule"] == "audience.surface_filter.close.memo"
            for finding in data["mechanical"]
        )


@pytest.mark.asyncio
async def test_mcp_analyze_prose_accepts_audience_param(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, with_audiences=True)
    _patch_fake_craft(monkeypatch)
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "analyze_prose",
            {
                "file_path": str(draft),
                "voice": "MistressFilth",
                "audience": "external",
                "severity_ceiling": 2,
                "dial_ceiling": 0.4,
                "surface": "memo",
            },
        )
        assert "issues" in _tool_json(result)


@pytest.mark.asyncio
async def test_mcp_edit_prose_accepts_audience_param(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, with_audiences=True)
    _patch_fake_craft(monkeypatch)
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "edit_prose",
            {
                "file_path": str(draft),
                "voice": "MistressFilth",
                "audience": "external",
                "severity_ceiling": 2,
                "dial_ceiling": 0.4,
                "surface": "memo",
            },
        )
        assert _tool_json(result)["change_log"] == "deterministic edit"


@pytest.mark.asyncio
async def test_mcp_architect_prose_accepts_audience_param(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, with_audiences=True)
    _patch_fake_craft(monkeypatch)
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "architect_prose",
            {
                "file_path": str(draft),
                "voice": "MistressFilth",
                "audience": "external",
                "severity_ceiling": 2,
                "dial_ceiling": 0.4,
                "surface": "memo",
            },
        )
        assert _tool_json(result)["diagnosis"] == "deterministic diagnosis"


@pytest.mark.asyncio
async def test_mcp_tune_diction_accepts_audience_param(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, with_audiences=True)
    _patch_fake_craft(monkeypatch)
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    async with mcp_client:
        result = await mcp_client.call_tool(
            "tune_diction",
            {
                "file_path": str(draft),
                "voice": "MistressFilth",
                "audience": "external",
                "severity_ceiling": 2,
                "dial_ceiling": 0.4,
                "surface": "memo",
            },
        )
        assert _tool_json(result)["voice_weighted"] is True


@pytest.mark.asyncio
async def test_mcp_voice_compose_step_accepts_audience_param(
    mcp_client: Client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, name="test-voice", with_audiences=True)
    _patch_fake_craft(monkeypatch)
    async with mcp_client:
        result = await mcp_client.call_tool(
            "voice_compose_step",
            {
                "name": "test-voice",
                "current_field": "purpose",
                "audience": "external",
                "severity_ceiling": 2,
                "dial_ceiling": 0.4,
                "surface": "memo",
            },
        )
        data = json.loads(_tool_text(result))
        assert data == [{"field": "purpose", "value": "test voice", "prompt": "test prompt"}]
