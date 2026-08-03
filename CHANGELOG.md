# Changelog

## [Unreleased]

## [0.2.2] - 2026-08-03

### Fixed
- `scripts/release.py`: close `mkstemp` file descriptor on failure to prevent leak.
- `scripts/release.py`: drop unsupported `capture` keyword from `_run` calls.
- `scripts/release.py`: `lstrip` each commit block to recover the subject on the first line.
- `tests/unit/test_release.py`: drop vestigial plugin pyproject reference.
- `scripts/release.py`: drop vestigial `claude-code/plugin/pyproject.toml` from metadata surfaces.

## [0.2.1] - 2026-08-03

### Fixed
- `scripts/release.py`: auto-commit metadata before tagging so the tag points to a commit whose surfaces agree with the version.

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
