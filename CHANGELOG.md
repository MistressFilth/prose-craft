# Changelog

## [Unreleased]

### Added
- Pre-PR checklist to `AGENTS.md`.
- Release helper groups bullets by Conventional Commit type into `### Added` / `### Fixed` / `### Changed`.

### Fixed
- Release helper no longer leaks `Co-authored-by:` footers, `---------` squash-merge separators, or `BREAKING CHANGE:` footers into changelog bullets.
- Release helper classifies `fix:` commits under `### Fixed` instead of `### Changed`.

## [0.2.2] - 2026-08-03

### Fixed
- lstrip commit blocks to recover subject on first line.
- Close mkstemp fd on failure to prevent leak.
- Drop unsupported capture kwarg from `_run` calls.

## [0.2.1] - 2026-08-03

### Fixed
- Drop vestigial plugin pyproject from metadata surfaces.

## [0.2.0] - 2026-08-03

### Changed
- Standardize Claude Code plugin layout under `claude-code/plugin/prose-craft/`.
- Align package, runtime, plugin, and marketplace version metadata at `0.2.0`.
- Add repository quality gates and release workflow documentation.

## [0.1.0] - 2026-08-01

### Changed
- Rewrite as pydantic-ai CLI + FastMCP server. Plugin reduced to thin
  adapter. Voice profiles moved from `${CLAUDE_PLUGIN_DATA}/voices/` to
  `$XDG_DATA_HOME/prose-craft/voices/`. Run `prose migrate voices` once
  to copy existing profiles.

## [0.0.0] - 2026-07-14

Initial release as a Claude Code plugin only.
