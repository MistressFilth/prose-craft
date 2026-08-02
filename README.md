# prose-craft

A `pydantic-ai` engine for designing and applying prose voices.

- **Typer CLI** with subcommands for analyze, edit, architect, tune-diction,
  voice compose/refine/draft/edit/check/list/show/init, migrate, mcp.
- **FastMCP server** over stdio, exposing the engine as tools and resources
  to any MCP host.
- **Voice profiles** at `$XDG_DATA_HOME/prose-craft/voices/<name>/voice.md`.
- **Plugin adapter** at `plugin/` is a thin Claude Code integration.

## Install

```bash
make init
```

## Quickstart

```bash
prose voice list
prose analyze chapter.md --voice dnova
prose voice compose dnova
prose mcp
```

## Migrating from the old plugin

If you have existing voices in `${CLAUDE_PLUGIN_DATA}/voices/`, copy them
into the new XDG-resident location:

```bash
prose migrate voices
```

The old directory is left untouched; delete the new one to roll back.

## Development

```bash
make test
make check
```

See `docs/superpowers/specs/2026-08-01-prose-craft-pydantic-ai-design.md`
for the architecture.
