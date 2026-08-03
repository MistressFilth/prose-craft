# Changelog

## [0.2.0] - 2026-08-03

### Changed
- Standardize Claude Code plugin layout under `claude-code/plugin/`.
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
