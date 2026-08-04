# Changelog

## [Unreleased]

### Fixed
- `migrate voices` now discovers the newer `prose-voicecraft-prose-voicecraft` plugin-data directory in addition to the original `prose` directory. Users with the 17-voice discordian library cached under the new plugin name get the right source root on first migrate; previously the default pointed at an empty `prose/` dir and silently copied nothing.
- `voice list` now surfaces broken voice files via `list_voice_errors` instead of silently dropping them from the count. A voice whose front-matter fails to parse against the current schema is reported to stderr (e.g. `error: new-voice: 3 validation errors for VoiceProfile ...`) so the user can see why a voice is missing from the list rather than seeing a quietly truncated count.

## [0.3.0] - 2026-08-03

### Added
- `voice check` accepts `--audience`, `--severity`, `--dial`, and `--surface` flags; the resolved `ResolvedAudience` is fed into `check_voice()` and echoed in the verdict.
- `voice check` (and the FastMCP `voice_check` tool) now mirror the audience knobs to a target surface: `--surface memo` resolves a `surface_filter.close: [memo]` audience into a violation.
- `VoiceVerdict` gains an `audience` echo field plus a `violations` property that combines mechanical and statistical findings.
- `VoiceProfile` carries the audience block as a first-class `AudiencesBlock` model with `private` / `team` / `external` slots, a `rationale` string, and an `entries()` accessor; shipped voices parse against the new schema.
- Voice IO accepts an optional ``voices_root`` parameter throughout the agent factory chain — ``ProseCraft(voices_root=...)``, ``build_voice_stylist(voices_root=...)``, ``bind_voice_tools(voices_root=...)`` — so a CLI ``--voices-root`` override reaches the agent's read-side tools.

### Changed
- Voice profiles' `audiences:` block is now honored by `voice draft`, `voice edit`, `voice check`, and the FastMCP server. New flags `--audience`, `--severity`, `--dial`, `--surface` apply on top of any front-matter `audience:` / `severity_ceiling:` / `dial_ceiling:` / `surface:` keys in the target file (precedence: CLI > front-matter > voice default). Default audience is the voice's most-permissive one. Closed audiences warn but allow. Severity and dial flags replace audience ceilings verbatim (caller responsibility). `voice check` tightens rule evaluation against the resolved audience's severity ceiling and merged `never_extend` list. `voice init` template now scaffolds an `audiences:` block.
- `check_voice()` accepts a `ResolvedAudience` and a `surface` string; the audience's severity ceiling tightens the statistical tolerance band, mechanical entries in `audience.never` are enforced, and a surface that lands in `audience.surface_filter.close` is flagged as a violation. The audience ceiling also tightens the pet-phrase density cap, so a "team" or "external" audience surfaces over-saturation earlier than a "private" audience at the same tolerance.
- `Violation.band` is now uniformly a `±N` band size (e.g. `"±0.6"`) for both `_check_pet_phrases` and `_check_sentence_length`. Older callers that read the tolerance name (e.g. `"normal"`) should switch to the new numeric form; the band is now the same shape as the audience-aware severity scale.

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
