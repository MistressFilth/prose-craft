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

## Pre-PR checklist

Before opening or merging a PR, the agent MUST:

1. **Keep versioning bumps adherent to SemVer.** Bump the appropriate segment for the nature of the change (major / minor / patch). Update every version surface listed in `@/home/divinefilth/.claude/rules/versioning.md` (root `pyproject.toml`, runtime `__version__`, `claude-code/plugin/prose-craft/.claude-plugin/plugin.json`, `claude-code/plugin/prose-craft/pyproject.toml` if present, and `.claude-plugin/marketplace.json`).
2. **Keep `CHANGELOG.md` up to date.** Add an entry under the `[Unreleased]` section describing the change, with `### Added` / `### Changed` / `### Fixed` / `### Removed` / `### Security` subsections as appropriate. The release helper collapses `[Unreleased]` into a dated section on `make release`.
3. **Keep `README.md` up to date.** New commands, new config options, new install steps, behavior changes — all reflected in the README before merge.
4. **Keep any `docs/` up to date.** If the repo has a `docs/` directory, the change is reflected there as well.
