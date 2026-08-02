# Changelog

## [Unreleased]

### Added
- Voice profile read/write/list (`prose_craft.voices.io`): `read_voice`,
  `read_voice_raw`, `write_voice`, `list_voices`. Atomic writes
  (temp file + fsync + rename) with verbatim prose-body preservation.
  Fixture voice `MistressFilth` lands under `tests/fixtures/voices/`.

### Changed
- Rewrite as pydantic-ai CLI + FastMCP server. Plugin reduced to thin adapter.
  Voice profiles moved from `${CLAUDE_PLUGIN_DATA}/voices/` to
  `$XDG_DATA_HOME/prose-craft/voices/`. Run `prose migrate voices` once to
  copy existing profiles.

## [0.0.0] - 2026-07-14

Initial release as a Claude Code plugin only.
