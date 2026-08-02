# Changelog

## [Unreleased]

### Added
- Voice profile read/write/list (`prose_craft.voices.io`): `read_voice`,
  `read_voice_raw`, `write_voice`, `list_voices`. Atomic writes
  (temp file + fsync + rename) with verbatim prose-body preservation.
  Fixture voice `MistressFilth` lands under `tests/fixtures/voices/`.
- Orchestrator package (`prose_craft.orchestrator`) with shared
  Pydantic dep models consumed by every agent: `AnalysisDeps`,
  `EditorDeps`, `ArchitectDeps`, `TuneDeps`, `VoiceDeps`, `StylistDeps`,
  `ComposerDeps`. Tolerance and stylist-mode are typed literals.
- `ProseCraft` composition root (`prose_craft.orchestrator.root`):
  constructed once per CLI/MCP/plugin invocation, owns model selection,
  voices-root, and log level. Exposes seven lazy agent accessors
  (`analyst`, `editor`, `architect`, `tune_diction`, `voice_checker`,
  `voice_stylist`, `voice_composer`) that build on first access and
  cache the result.
- CLI subcommands: `voice check <file> --voice <name>` runs the
  deterministic three-category voice check (mechanical, statistical,
  judgments-needed) and renders markdown or `--json`; `voice init <name>`
  scaffolds a blank `voice.md` from the bundled template. Both honor
  `--voices-root`.
- CLI subcommand: `migrate voices [--src] [--dst] [--overwrite]
  [--dry-run]` copies voice profiles from a legacy plugin-data location
  to the XDG root; renders a copied/skipped/errors summary.

### Changed
- Rewrite as pydantic-ai CLI + FastMCP server. Plugin reduced to thin adapter.
  Voice profiles moved from `${CLAUDE_PLUGIN_DATA}/voices/` to
  `$XDG_DATA_HOME/prose-craft/voices/`. Run `prose migrate voices` once to
  copy existing profiles.

## [0.0.0] - 2026-07-14

Initial release as a Claude Code plugin only.
