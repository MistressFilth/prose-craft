# MistressFilth/prose-craft

Repository for the prose-craft engine: a `pydantic-ai` CLI + FastMCP server
for designing and applying prose voices, with a thin Claude Code plugin
adapter at `claude-code/plugin/prose-craft/`.

## Project Layout

- `src/prose_craft/` — shipped engine.
- `tests/` — unit and feature tests.
- `claude-code/plugin/prose-craft/` — shipped Claude Code adapter.
- `.claude-plugin/marketplace.json` — development marketplace manifest.

## Working memory

Cross-repo scratch, brainstorm output, and any artifact **not yet promoted**
to the engine docs lives in the project-notes hub:

`@/home/divinefilth/code/project-notes/prose-craft/AGENTS.md`

## Conventions

See `@/home/divinefilth/.claude/rules/` for shared repo standards
(commit format, required files, Makefile targets, pre-commit, versioning,
changelog, plugin packaging).
