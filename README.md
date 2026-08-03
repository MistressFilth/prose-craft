# prose-craft

[![Checks](https://github.com/MistressFilth/prose-craft/actions/workflows/check.yml/badge.svg)](https://github.com/MistressFilth/prose-craft/actions/workflows/check.yml)

A `pydantic-ai` engine for designing and applying prose voices.

- **Typer CLI** (`prose`) with subcommands for analyze, edit,
  architect, tune-diction, voice compose/refine/draft/edit/check/list/
  show/init, migrate, mcp.
- **FastMCP server** (`prose mcp`) over stdio, exposing the engine as
  tools and resources to any MCP host.
- **Voice profiles** at `$XDG_DATA_HOME/prose-craft/voices/<name>/voice.md`.
- **Claude Code plugin** at `claude-code/plugin/` is a thin adapter over the engine.

## Install

```bash
make init
```

The Makefile target runs `uv sync --all-extras` and installs the engine
plus its dev tools.

## Quickstart

```bash
# List voices
prose voice list

# Analyze a draft (no LLM round-trip when --metrics-only)
prose analyze chapter.md --voice MistressFilth --metrics-only

# Edit prose in a voice
prose edit chapter.md --voice MistressFilth

# Run the composer wizard
prose voice compose MistressFilth

# Start the MCP server
prose mcp
```

## Migrating from the old plugin

If you have existing voices in `${CLAUDE_PLUGIN_DATA}/voices/`, copy
them into the new XDG-resident location:

```bash
prose migrate voices
```

The old directory is left untouched; delete the new one to roll back.

## Using the MCP server from Claude Code

```bash
claude mcp add --transport stdio prose-craft -- uv run --project . prose-craft mcp
```

The plugin in `claude-code/plugin/` is registered the same way as before and now
depends on the MCP server for its tools.

## Architecture

Single composition root (`ProseCraft`) constructs seven `pydantic-ai`
agents. Deterministic primitives in `src/prose_craft/analysis/` are
pure Python, callable from CLI, agents (as tools), and MCP. Voice
profiles are Pydantic models that round-trip the existing `voice.md`
front-matter format.

## Development

```bash
make test         # unit + features tests
make check        # lint, typecheck, format
make format       # auto-fix lint/format findings
pre-commit run --all-files   # run the full pre-commit suite locally
```

## Project links

- [Changelog](CHANGELOG.md)
- [Agent instructions](AGENTS.md)
- [License](LICENSE) (GPL-2.0)
