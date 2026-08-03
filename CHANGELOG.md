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

## [0.2.1] - 2026-08-03

### Changed
- fix(release): drop vestigial plugin pyproject from metadata surfaces

## [0.2.2] - 2026-08-03

### Changed
- fix(release): drop unsupported capture kwarg from _run calls

- fix(release): lstrip commit blocks to recover subject on first line

- chore: align uv.lock with pyproject version

- fix(release): close mkstemp fd on failure to prevent leak

- fix(release): auto-commit metadata before tagging (#11)

Co-authored-by: v0idbit <>
- chore(release): 0.2.1 via guarded release helper (#10)

* fix(release): drop vestigial plugin pyproject from metadata surfaces

* chore(release): 0.2.1 via guarded release helper

---------

Co-authored-by: v0idbit <>

