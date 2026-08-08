# Changelog

## [Unreleased]

## [0.7.0] - 2026-08-08

### Added
- `voice delete <name>` removes a voice from the user root. Requires `--force`; without it the command prints the path that would be deleted and exits 2. Shared-only voices (voices that exist only in an `$XDG_DATA_DIRS/prose-craft/voices/` root) are refused even with `--force`. When the same name exists in both a user and a shared root, `--force` removes the user copy and prints a note that the shared copy remains.
- `prose_craft.voices.io.delete_voice()` library function plus `VoiceDeleteError` exception (already present in `io.py` but previously unused).

## [0.6.0] - 2026-08-07

### Fixed
- `TestDataDirs` in `tests/unit/test_xdg.py` used hardcoded colons in `$XDG_DATA_DIRS` fixtures, which on Windows (where `os.pathsep` is `;`) made the entire string one entry and tripped the `is_absolute()` validation. The fixtures now use `os.pathsep.join(...)` so the round-trip matches the platform separator. The class is also skipped on Windows because the POSIX-style `/a`, `/b`, `/c` paths used in the assertions are not absolute there.

### Added
- `$XDG_DATA_DIRS` lookup for shared voice packs. System-installed voices are visible alongside user voices; user voices shadow shared by name; first invocation of `voice edit --voice <name>` against a shared-only voice copies it to the user root.
- `voice import <name>` to explicitly copy a shared voice into the user root without invoking the agent.
- `voice list` annotates each entry with `[user]` / `[shared]` and accepts `--origin {user,shared,all}`.
- `voice show <name>` prints the origin tag and resolved path.
- `data_dirs()` resolver in `prose_craft.xdg`.
- `VoiceIndex` module + MCP cache for multi-root discovery.
- Pre-commit matches CI: pinned upstream `ruff-pre-commit v0.15.20` (lint + format with `--fix`, scoped to `src/prose_craft|tests|scripts|pyproject.toml`) + pinned upstream `ty-pre-commit v0.0.65` (with `--frozen` to prevent `uv.lock` rewrites) + one local `test` hook (`make test` with `GIT_*` env-strip).
- `pre-commit run --all-files` runs as a final step on every CI matrix leg (ubuntu/macos/windows) so `--no-verify` bypasses surface in PR checks.

### Changed
- `VoiceIndex.build()` deduplicates by directory name (not by parsed `voice` field) so the user-shadow-shared precedence is honored even for malformed shared voices.
- `list_voices` and `list_voice_errors` scan all roots when called without an explicit `root=`.
- `.pre-commit-config.yaml`: replaced two coarse local hooks (`make-check`, `make-test`) with three upstream + one local repo block.
- `pyproject.toml`: `pre-commit>=4.6.1` added to `[dependency-groups].dev`.

### Removed
- The `make-check` and `make-test` coarse local hooks (replaced by per-tool upstream hooks + the scoped `test` hook).

### Fixed
- `TestDataDirs` in `tests/unit/test_xdg.py` used hardcoded colons in `$XDG_DATA_DIRS` fixtures, which on Windows (where `os.pathsep` is `;`) made the entire string one entry and tripped the `is_absolute()` validation. The fixtures now use `os.pathsep.join(...)` so the round-trip matches the platform separator. The class is also skipped on Windows because the POSIX-style `/a`, `/b`, `/c` paths used in the assertions are not absolute there.
- The `voices_tree` fixture in `tests/features/cli_voice_list_test.py` joined two shared roots with a hardcoded colon while `xdg.data_dirs()` splits `$XDG_DATA_DIRS` on `os.pathsep`. On Windows the two paths collapsed into one malformed entry, failed the `is_absolute()` validation, and were dropped, leaving zero shared roots. The fixture now joins on `os.pathsep`.

## [0.5.0] - 2026-08-06

### Added
- Windows and macOS are now supported and tested platforms; CI runs the full suite on Linux, macOS, and Windows. `pyproject.toml` declares the corresponding `Operating System` classifiers.
- Directory resolution honors the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/) on every platform, falling back to each platform's native convention when the XDG variables are unset. Five overrides — `PROSE_CRAFT_XDG_DATA_HOME`, `_CONFIG_HOME`, `_CACHE_HOME`, `_STATE_HOME`, `_RUNTIME_DIR` — take precedence over the corresponding `XDG_*` variables, which take precedence over the native default. A value that is empty or relative is ignored, as the specification requires.
- `prose_craft.xdg` owns resolution; `prose_craft.paths` owns the layout. No other module reads an `XDG_*` variable.
- Strict persistent configuration at the platform config root under `prose-craft/config.toml`, with CLI-over-environment-over-TOML precedence and non-overwriting `prose config --init` creation.

### Changed
- Composer memory moved from `<voices_root>/.composer-state/` to the application state directory (`<state_root>/prose-craft/composer-state/`). It is agent state, not user data, and no longer sits inside the voice library. An orphaned `.composer-state/` left by an earlier version is inert and safe to delete.
- `prose config` no longer writes `PROSE_CRAFT_MODEL` or `PROSE_CRAFT_VOICES_ROOT` into the process environment. The flags affect only what the command prints.
- `platformdirs` is now a direct dependency. It was already present transitively, so no new package is installed.
- Promoted `pydantic-settings[toml]` to a direct dependency for typed TOML and environment settings sources.
- Plugin documentation refers to `<voices-root>` rather than `$XDG_DATA_HOME/prose-craft/voices`, which was only ever accurate on Linux. The voice-backup convention moved from inside the voices root to `<state-root>/prose-craft/backups/`.
- **No migration is required.** The voices root is unchanged on Linux and macOS.

### Fixed
- `prose voice draft` without `--to` no longer leaves a stray `.md` file in the system temp directory. The scratch file is created under the runtime directory and removed when the command finishes, including on failure.
- The unbound `write_voice` tool in `prose_craft.agents.tools` now pins `root=` to `load_settings().voices_root` explicitly. A future change that introduces shared-root walking in `voice_path` / `_io_write_voice` would otherwise have let any agent that wires the unbound tool silently overwrite a system-installed voice.
- Scratch files no longer fail outright when `XDG_RUNTIME_DIR` is exported but unusable — common under WSL, in containers, and in ssh sessions without a login session. The runtime root falls back to `<state_root>/prose-craft/run/`, which the specification sanctions.
- An unset `HOME` no longer resolves the voices root to a path relative to the current working directory.
- A relative value in `XDG_DATA_HOME` is now ignored instead of being resolved against the current working directory.
- `migrate voices` now discovers the newer `prose-voicecraft-prose-voicecraft` plugin-data directory in addition to the original `prose` directory. Users with the 17-voice discordian library cached under the new plugin name get the right source root on first migrate; previously the default pointed at an empty `prose/` dir and silently copied nothing.
- `voice list` now surfaces broken voice files via `list_voice_errors` instead of silently dropping them from the count. A voice whose front-matter fails to parse against the current schema is reported to stderr (e.g. `error: new-voice: 3 validation errors for VoiceProfile ...`) so the user can see why a voice is missing from the list rather than seeing a quietly truncated count.
- Two `migrate voices` tests asserted against the real user profile on Windows rather than a temporary directory, because they pinned `HOME` while `Path.home()` reads `USERPROFILE` there. They now pin both.
- MCP `analyze_prose` now short-circuits on `metrics_only=True` regardless of the `voice` argument, matching the CLI's `analyze --metrics-only` guarantee; a broken TOML config file with `metrics_only=True --voice X` no longer fails with a configuration error.
- `prose config --init` write-side failures (e.g. permission denied, fsync error) now report "could not write configuration at <path>" instead of "invalid configuration at <path>"; read-side wording is unchanged.
- `prose config --init` parent-directory creation and `tempfile.mkstemp` failures (permission denied, ENOSPC) now flow through the same "could not write" wording as fsync/link failures and exit 2 without a traceback; previously they surfaced as bare `OSError`/`PermissionError` from outside the try/except boundary.
- An empty or whitespace-only `model` in TOML, `PROSE_CRAFT_MODEL`, or an explicit `--model` flag is now rejected as `configuration error: model must not be empty` with the config file path; the analyzer no longer silently falls back to the built-in default when the override is empty.
- `prose` voice commands now report invalid voice names (path-traversal attempts, whitespace, empty) as exit 2 with no traceback. The CLI's `_handle_errors` registers `VoiceNameError` alongside the other user-input exceptions, and `_voice_compose_repl` validates the name up front so a traversal attempt cannot pass through the silent template-initializer path.
- Nested Typer wrappers now preserve the inner `typer.Exit(code)` instead of downgrading it. `voice refine` calls `voice compose` directly (not via the dispatcher), and the outer wrapper's generic `Exception` arm was masking the documented exit-2 by catching the inner `typer.Exit(2)` (a `RuntimeError` subclass) and re-raising `typer.Exit(1)` with a traceback. `_handle_errors` now propagates `typer.Exit` unchanged; a regression test sweeps the nested call with an invalid voice name and asserts the original exit code, no traceback, and the dedicated error message.

### Removed
- Bundled-voice fallback in voice discovery: `get_bundled_voices_root()` and the wheel-side fallback in `read_voice` / `list_voices` are gone. Voices resolve against the user root only.

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
