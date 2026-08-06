# prose-craft

[![Checks](https://github.com/MistressFilth/prose-craft/actions/workflows/check.yml/badge.svg)](https://github.com/MistressFilth/prose-craft/actions/workflows/check.yml)

A `pydantic-ai` engine for designing and applying prose voices.

- **Typer CLI** (`prose`) with subcommands for analyze, edit,
  architect, tune-diction, voice compose/refine/draft/edit/check/list/
  show/init, migrate, mcp.
- **FastMCP server** (`prose mcp`) over stdio, exposing the engine as
  tools and resources to any MCP host.
- **Voice profiles** at the platform voices root (`prose config` resolves it).
- **Linux, macOS, and Windows**, each tested in CI.
- **Claude Code plugin** at `claude-code/plugin/` is a thin adapter over the engine.

## Install

```bash
make init
```

The Makefile target runs `uv sync --all-extras` and installs the engine
plus its dev tools.

## Quickstart

```bash
# List voices
prose voice list

# Analyze a draft (no LLM round-trip when --metrics-only)
prose analyze chapter.md --voice MistressFilth --metrics-only

# Edit prose in a voice
prose edit chapter.md --voice MistressFilth

# Run the composer wizard
prose voice compose MistressFilth

# Start the MCP server
prose mcp
```

## Audience-aware drafting

Voice profiles can scope rules to an audience (`private`, `team`, `external`, or custom). Select the audience when drafting, editing, or checking:

```bash
# Pick the audience explicitly. Defaults to the voice's most-permissive one.
prose voice draft discordian-base --audience external "..."

# Tighten ceilings and pick a surface.
prose voice draft discordian-base \
    --audience external \
    --severity 3 \
    --dial 0.8 \
    --surface postmortem \
    --to /tmp/out.md \
    "..."
```

Or put the audience in the target file's YAML front-matter:

```markdown
---
audience: external
severity_ceiling: 3
dial_ceiling: 0.8
surface: postmortem
---

# draft goes here
```

Precedence: CLI flag > front-matter > voice default. Closed audiences print a warning to stderr and proceed. Severity and dial flags replace audience ceilings verbatim — caller is responsible for not exceeding them.

The FastMCP server tools (`analyze_prose`, `voice_check`, `edit_prose`, `architect_prose`, `tune_diction`, `voice_compose_step`) accept the same `audience` / `severity_ceiling` / `dial_ceiling` / `surface` parameters.

## Configuration

Prose-craft honors the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/) on every platform, and falls back to each platform's native convention when the XDG variables are unset.

| | Linux | macOS | Windows |
|---|---|---|---|
| Voices | `~/.local/share/prose-craft/voices/` | `~/Library/Application Support/prose-craft/voices/` | `%LOCALAPPDATA%\prose-craft\voices\` |
| Composer state | `~/.local/state/prose-craft/composer-state/` | `~/Library/Application Support/prose-craft/composer-state/` | `%LOCALAPPDATA%\prose-craft\composer-state\` |
| Draft scratch | `$XDG_RUNTIME_DIR/prose-craft/scratch/` | `~/Library/Caches/TemporaryItems/prose-craft/scratch/` | `%LOCALAPPDATA%\Temp\prose-craft\scratch\` |

Run `prose config` to print the resolved voices root on your machine.

Each root resolves through `PROSE_CRAFT_XDG_<NAME>`, then `XDG_<NAME>`, then the
native default. The XDG variables work on macOS and Windows too:

```bash
XDG_DATA_HOME=/mnt/voices prose voice list
```

A value that is empty or relative is ignored, per the specification.

### Persistent settings

Create a TOML config file at the platform config root to set values that
survive across invocations:

| | Linux | macOS | Windows |
|---|---|---|---|
| Config | `~/.config/prose-craft/config.toml` | `~/Library/Application Support/prose-craft/config.toml` | `%LOCALAPPDATA%\prose-craft\config.toml` |

The file accepts two fields today. Values are typed strictly — unknown keys,
wrong-typed values, empty or relative paths, and malformed TOML all surface
as a `configuration error` naming the offending file:

```toml
model = "anthropic:claude-opus-4-5"

[paths]
voices_root = "/absolute/path/to/voices"
```

`paths.voices_root` is expanded against `~` and must be absolute; a relative
value is rejected. Run `prose config --init` to write the built-in defaults
to the platform config root — the operation refuses to overwrite an existing
file and exits 2 instead, leaving your edits untouched.

Precedence is exactly four layers, highest wins:

```text
CLI option > PROSE_CRAFT_* environment variable > config.toml > built-in/XDG default
```

So `--model` / `--voices-root` win for a single invocation, `PROSE_CRAFT_MODEL`
and `PROSE_CRAFT_VOICES_ROOT` win for a session, the TOML file wins for a
machine, and the XDG default is the fallback.

The `version` command is intentionally independent of the config file —
`prose version` still prints the package version when the TOML is broken or
missing, so you always have a way to diagnose which version is installed.

`PROSE_CRAFT_VOICES_ROOT` names the voices directory outright and wins over all
of the above; `--voices-root` is its per-invocation equivalent.

`PROSE_CRAFT_MODEL` selects the model (default `anthropic:claude-opus-4-5`).

If `XDG_RUNTIME_DIR` is exported but unusable — common under WSL, in containers,
and in ssh sessions without a login session — scratch files fall back to
`<state-root>/prose-craft/run/`.

## Migrating from the old plugin

If you have existing voices in `${CLAUDE_PLUGIN_DATA}/voices/`, copy
them into the new XDG-resident location:

```bash
prose migrate voices
```

The old directory is left untouched; delete the new one to roll back.

An orphaned `.composer-state/` directory inside your voices root is inert as of
0.4.0 — composer memory now lives under the state root. It is safe to delete.

## Using the MCP server from Claude Code

```bash
claude mcp add --transport stdio prose-craft -- uv run --project . prose-craft mcp
```

The plugin in `claude-code/plugin/` is registered the same way as before and now
depends on the MCP server for its tools.

## Architecture

Single composition root (`ProseCraft`) constructs seven `pydantic-ai`
agents. Deterministic primitives in `src/prose_craft/analysis/` are
pure Python, callable from CLI, agents (as tools), and MCP. Voice
profiles are Pydantic models that round-trip the existing `voice.md`
front-matter format.

## Development

```bash
make test         # unit + features tests
make check        # lint, typecheck, format
make format       # auto-fix lint/format findings
pre-commit run --all-files   # run the full pre-commit suite locally
```

## Project links

- [Changelog](CHANGELOG.md)
- [Agent instructions](AGENTS.md)
- [License](LICENSE) (GPL-2.0)
