# prose-craft → pydantic-ai rewrite

**Date:** 2026-08-01
**Status:** Approved (brainstorming gate closed)
**Repo:** `MistressFilth/prose-craft`
**References:** `MistressFilth/lies`, `MistressFilth/mage`

## Context

prose-craft is currently a Claude Code plugin only. Six agents (prose-analyst, prose-editor, prose-architect, voice-composer, voice-stylist, voice-checker), ten user-invocable skills, five reference skills, two output styles, a PostToolUse hook, and a `voices/` tree with a YAML schema. The deterministic checkers (`voice_check.py`, `clause_density_check.py`, `dispersion_check.py`, `prose_analyzer.py`) are pure Python with no LLM; the agents are markdown frontmatter + system-prompt text. There is no `src/`, no tests, no Makefile, no CHANGELOG, no AGENTS.md beyond a stub, and no `pyproject.toml` deps for pydantic-ai.

The plugin works in Claude Code and nowhere else. The voice schema is rich but locked inside Claude Code's plugin runtime. There is no way to script a voice check from a shell, no MCP surface for Cursor or other hosts, and no way to test the agents deterministically.

`lies` and `mage` are sibling repos that already solved this for their own domains: a Typer CLI as the user-facing entry, a `pydantic-ai` orchestrator under the hood, `pydantic-ai-harness` capabilities for cross-cutting concerns, and a FastMCP server for host-agnostic tool exposure. prose-craft should adopt the same shape.

The user has approved a full rewrite. The old plugin is replaced; voice profiles in `${CLAUDE_PLUGIN_DATA}/voices/` are preserved by a migration step that copies, never moves.

## Goals

1. Engine becomes a Typer CLI + `pydantic-ai` agents + `pydantic-ai-harness` capabilities + FastMCP server, all driven by a single composition root.
2. Every agent exposes a typed Pydantic input and a typed Pydantic output. No raw dicts cross the boundary.
3. Voice profiles persist as the same `voice.md` front-matter + prose body format. Runtime types are Pydantic models that round-trip the file.
4. Voice profiles live at `$XDG_DATA_HOME/prose-craft/voices/<name>/voice.md`. Migration from `${CLAUDE_PLUGIN_DATA}/voices/` is copy-only.
5. The Claude Code plugin survives as a thin adapter (sub-agents with model selection, slash commands, output styles). Engine has zero Claude Code dependencies.
6. Deterministic metrics (rhythm, diction, cohesion, readability, monotony, clause density, dispersion) are first-class Python modules callable from CLI, agents, and MCP. Single source of truth.
7. Compose / refine / draft / edit / analyze / architect / tune-diction / check / list / show are user-facing commands on the CLI. Compose is a stateful REPL with resume from disk.
8. Every test is deterministic. No live model calls in CI. `FunctionModel` fixtures encode expected agent behavior.
9. `make check` runs lint + typecheck + format. Pre-commit refuses a commit on first pass; format may mutate; author re-stages and retries.
10. Two version surfaces: `plugin/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. Both start at `0.1.0` for the rewrite. CHANGELOG entry summarizes the rewrite as one item under `[Unreleased]`.

## Non-goals

- No live-model integration tests in CI. Sanity tests against real Opus exist but are out-of-band, run on demand.
- No voice sample corpora, no stylometry, no fingerprinting. Voices are designed, not derived. (Existing constraint from the plugin — preserved.)
- No multi-voice composition. One voice per draft. (Existing constraint — preserved.)
- No new voice schema fields. D1–D10 stay. (`audiences:` ceiling block stays; the per-voice audience ceiling mechanism stays.)
- No streaming output in v1. Agent outputs are returned as finalized structured Pydantic models.
- No cross-host tool registry beyond FastMCP. The engine is the CLI; the MCP server is its public API.
- No automatic on-save voice check. The PostToolUse hook is gone. The writer invokes `prose voice check` or the MCP `voice_check` tool on demand.

## Architecture

### Composition root

`ProseCraft` is the single composition root. Constructed once per CLI invocation or MCP request. Owns model selection, voice location, and the harness `Memory` capability. Lazy-builds agents on first access.

```python
class ProseCraft:
    def __init__(
        self,
        *,
        model: str | None = None,
        voices_root: Path | None = None,
        log_level: str = "INFO",
    ) -> None: ...

    def analyst(self) -> Agent[AnalysisDeps, ProseDiagnostic]: ...
    def editor(self) -> Agent[EditorDeps, EditResult]: ...
    def architect(self) -> Agent[ArchitectDeps, ArchitectResult]: ...
    def tune_diction(self) -> Agent[TuneDeps, SubstitutionPlan]: ...
    def voice_checker(self) -> Agent[VoiceDeps, VoiceVerdict]: ...
    def voice_stylist(self) -> Agent[StylistDeps, DraftResult]: ...
    def voice_composer(self) -> Agent[ComposerDeps, list[VoiceDelta]]: ...
```

No top-level `run(command)` method. The orchestrator is constructed, the right agent is picked, the result is rendered. The plugin and the MCP server are both thin adapters over this root.

### Agent contracts

| Agent | Model | Deps | Output | Capabilities |
|---|---|---|---|---|
| `analyst` | Haiku | `AnalysisDeps` | `ProseDiagnostic` | tools: `read_file`, `run_voice_check_tool`, `run_dispersion_tool`, `run_clause_density_tool` |
| `editor` | Sonnet | `EditorDeps` | `EditResult` | tools: `read_file`, `run_voice_check_tool` |
| `architect` | Opus | `ArchitectDeps` | `ArchitectResult` | tools: `read_file`, `run_voice_check_tool` |
| `tune_diction` | Haiku | `TuneDeps` | `SubstitutionPlan` | tools: `read_file`, `load_voice_diction` |
| `voice_checker` | Haiku | `VoiceDeps` | `VoiceVerdict` | tools: `read_file`, `load_voice` |
| `voice_stylist` | Sonnet | `StylistDeps` | `DraftResult` | tools: `read_file`, `load_voice`, `run_voice_check_tool` |
| `voice_composer` | Opus | `ComposerDeps` | `list[VoiceDelta]` | tools: `load_voice`, `read_voice`, `write_voice`, `list_voices`, `apply_voice_delta`; capability: `Memory` |

All agent tools are pure-Python wrappers over the analysis/voices modules. No tool makes a network call except via the model.

### Deterministic primitives

`src/prose_craft/analysis/` is pure Python, no LLM, fully unit-tested. Modules:

- `sentences.py` — tokenize_sentences, word/syllable helpers
- `diction.py` — Germanic/Latinate classifier + substitution table
- `cohesion.py` — connective density
- `readability.py` — Flesch
- `monotony.py` — consecutive-length zones
- `clause_density.py` — ppc + agentless-passive
- `dispersion.py` — cross-draft lexical + structural
- `metrics.py` — `analyze_prose(text) -> ProseMetrics` (Pydantic)

Three callers hit them: CLI (fast path: `prose analyze --metrics-only`), agents (as tools), MCP server (as tools). The function is the single source of truth; the wrapper is a thin re-exporter.

### Flow per CLI subcommand

```
$ prose analyze chapter.md [--voice <name>] [--metrics-only]
  → cli.py: cmd_analyze(...)
  → ProseCraft().analyst().run_sync("Analyze this prose.", deps=AnalysisDeps(...))
  → Agent calls run_voice_check_tool if voice given
  → ProseDiagnostic returned; cli renders markdown to stdout
```

```
$ prose voice compose dnova
  → cli.py: cmd_voice_compose(name)  [Typer REPL]
  → read_voice(name) — load existing profile or blank
  → loop: composer.run_sync("next field", deps=ComposerDeps(current_field=...))
        → composer returns list[VoiceDelta]
        → user accepts / modifies / declines
        → apply_voice_delta writes to voice.md atomically
  → EOF / "done" / completion exits; resume state in harness Memory
```

### Error handling

Every CLI subcommand catches three classes:

1. `ModelRetry` / `UsageLimitExceeded` — bubble up with the model's hint; CLI prints to stderr, exits 1.
2. `VoiceProfileNotFound` — raised by `read_voice` when `--voice` names an absent profile; CLI prints `prose voice list` and exits 2.
3. Anything else — CLI prints traceback to stderr, exits 1. No silent swallowing.

`mcp.py` mirrors the same exception classes with MCP error responses. No silent fallbacks.

## Data model

### Voice profile

```python
class VoiceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice: str
    version: int = 1
    created: date
    updated: date
    authors: list[str] = []
    imported_from: str | None = None
    voice_persona: str | None = None
    purpose: str | None = None
    audience: str | None = None
    audiences: dict[str, AudienceCeiling] = {}
    register: RegisterAxes
    diction: DictionConfig
    rhythm: RhythmConfig
    syntax: SyntaxConfig
    lexicon: LexiconConfig
    structure: StructureConfig
    never: list[NeverEntry] = []
    attributions: list[Attribution] = []
    # prose body (D10) carried separately as raw text by io.py
```

All optional fields default to `None` so a partially-composed profile is still a valid file. `extra="forbid"` rejects unknown keys; the IO layer surfaces a clear error rather than silently dropping them.

### Audience ceiling

```python
class AudienceCeiling(BaseModel):
    severity_ceiling: int = 5             # 0..5
    dial_ceiling: float = 1.0             # 0.0..1.0
    fallback_voice: str | None = None
    never_extend: list[NeverEntry] = []
    surface_filter: SurfaceFilter | None = None
    closed: bool = False
    reason: str | None = None
```

### Detection kind

```python
class NeverEntry(BaseModel):
    id: str | None = None
    rule: str
    detection: Literal["mechanical", "statistical", "agent-required"] = "agent-required"
```

The detection kind drives which `check.py` sub-scanner emits the violation. The existing `voice_check.py` taxonomy (mechanical / statistical / agent-required) is preserved.

## Voice location + IO

### Location

```python
def get_voices_root() -> Path:
    """$XDG_DATA_HOME/prose-craft/voices
       or $HOME/.local/share/prose-craft/voices
       or $HOME/Library/Application Support/prose-craft/voices
    """

def voice_path(name: str, *, root: Path | None = None) -> Path:
    """<root>/<name>/voice.md. Validates name against [a-z0-9][a-z0-9-]*."""
```

`PROSE_CRAFT_VOICES_ROOT` env var overrides. `--voices-root` CLI flag overrides. Tests inject a `tmp_path` fixture.

### IO

```python
def read_voice(name: str, *, root: Path | None = None) -> VoiceProfile: ...
def write_voice(profile: VoiceProfile, *, root: Path | None = None) -> Path: ...
def list_voices(*, root: Path | None = None) -> list[VoiceSummary]: ...
```

Atomic writes (temp file in same dir, fsync, rename). Preserves the prose body verbatim — pyyaml parses the front-matter block; the rest of the file becomes `profile._prose_body`. Writes round-trip without touching the body.

### Migration

```python
def migrate_voices(
    *,
    src: Path | None = None,
    dst: Path | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> MigrationReport: ...
```

Default `src`: `$CLAUDE_PLUGIN_DATA/voices`. Default `dst`: XDG root. Source never modified. CLI shape: `prose migrate voices [--src] [--dst] [--overwrite] [--dry-run]`. Returns `MigrationReport(copied, skipped, errors)`.

## CLI surface

| Command | Description |
|---|---|
| `prose analyze <file> [--voice <name>] [--tolerance strict\|normal\|relaxed] [--metrics-only]` | Run analyst agent (or deterministic metrics only when `--metrics-only`) |
| `prose edit <file> [--voice <name>] [--tolerance ...]` | Run editor agent; writes back the edited file |
| `prose architect <file> [--voice <name>]` | Run architect agent; prints reconstruction proposal |
| `prose tune-diction <file> [--voice <name>]` | Run tune-diction agent; prints substitution plan |
| `prose voice list` | List every voice under the active root |
| `prose voice show <name> [--raw]` | Print voice profile as markdown (or raw file) |
| `prose voice check <file> --voice <name> [--tolerance ...]` | Run deterministic voice check; JSON output with `--json` |
| `prose voice compose <name>` | REPL wizard; resumable from disk |
| `prose voice refine <name> [dim]` | REPL wizard for a single dimension (or all unanswered) |
| `prose voice draft <name> <brief> [--to <output>]` | Run stylist agent in draft mode |
| `prose voice edit <file> --voice <name>` | Run stylist agent in edit mode |
| `prose voice init <name>` | Scaffold a blank voice.md from the template |
| `prose migrate voices [--src] [--dst] [--overwrite] [--dry-run]` | Copy voices from old plugin-data location to XDG root |
| `prose mcp` | Run the FastMCP server over stdio |
| `prose version` | Print engine version |
| `prose config` | Print model + voices root |
| `prose` (no subcommand) | Typer REPL with `/help` |

Global flags: `--model <id>` (overrides `PROSE_CRAFT_MODEL`), `--voices-root <path>` (overrides env).

## MCP surface

Ten elements over stdio.

| Element | Kind | Description |
|---|---|---|
| `analyze_prose(file_path, voice?, tolerance?, metrics_only?)` | tool | Analyst when `metrics_only=False`; deterministic primitives when `metrics_only=True`. Returns `ProseDiagnostic` as JSON. |
| `voice_check(file_path, voice, tolerance?, brief_path?)` | tool | Deterministic voice check. Returns `VoiceVerdict` as JSON. |
| `dispersion_check(new_draft_path, siblings)` | tool | Cross-draft scoring. Returns `DispersionProfile` as JSON. |
| `clause_density_check(file_path)` | tool | Passive + participial density. Returns `ClauseDensityResult` as JSON. |
| `edit_prose(file_path, voice?, tolerance?)` | tool | Editor agent. Returns `EditResult` as JSON. |
| `architect_prose(file_path, voice?)` | tool | Architect agent. Returns `ArchitectResult` as JSON. |
| `tune_diction(file_path, voice?)` | tool | Tune-diction agent. Returns `SubstitutionPlan` as JSON. |
| `voice_compose_step(name, current_field?)` | tool | One step of the composer wizard. Returns `list[VoiceDelta]`. |
| `prose://voices` | resource | Markdown list of every voice under the active root. |
| `prose://voices/{name}` | resource | Raw `voice.md` for the named voice. |

CLI launch: `prose mcp`. Claude Code registration mirrors lies:

```bash
claude mcp add --transport stdio prose-craft -- uv run --project . prose-craft mcp
```

## Plugin adapter

The Claude Code plugin survives as a thin adapter. The engine has zero Claude Code imports; the plugin depends on the engine via MCP.

```
plugin/
├── .claude-plugin/plugin.json
├── agents/
│   ├── prose-analyst.md        # calls mcp__prose-craft__analyze_prose
│   ├── prose-editor.md          # calls mcp__prose-craft__edit_prose
│   ├── prose-architect.md       # calls mcp__prose-craft__architect_prose
│   ├── voice-composer.md        # uses prose_compose_step
│   ├── voice-stylist.md         # calls stylist via CLI + voice_check via MCP
│   └── voice-checker.md         # calls mcp__prose-craft__voice_check
├── skills/                      # slash commands; 10-line adapters per subcommand
├── output-styles/
│   ├── literary-editor.md
│   └── voice-author.md
└── voices/_template/voice.md
```

No `hooks/hooks.json`. The PostToolUse hook is gone.

Per-agent frontmatter declares the model so Claude Code routes correctly:

```markdown
---
name: prose-analyst
description: Fast diagnostic of any prose file.
tools: mcp__prose-craft__analyze_prose, Read
model: haiku
---

You are a thin adapter over the `analyze_prose` MCP tool. When invoked:

1. Read the file at $ARGUMENTS.
2. Call `mcp__prose-craft__analyze_prose` with the file path and any flags.
3. Render the result as markdown.
```

The plugin's plugin.json declares a dependency on the prose-craft MCP server so installation is one step.

## Repository layout

```
prose-craft/
├── pyproject.toml              # uv-build; pydantic-ai-slim, pydantic-ai-harness, typer, fastmcp; requires-python >=3.10
├── uv.lock
├── Makefile                    # init / sync / test / lint / typecheck / format / check / release / help
├── README.md
├── CHANGELOG.md
├── AGENTS.md
├── CLAUDE.md                   # @AGENTS.md
├── .pre-commit-config.yaml
├── .gitignore
├── src/prose_craft/
│   ├── __init__.py             # __version__
│   ├── cli.py                  # Typer app
│   ├── mcp.py                  # FastMCP server (stdio)
│   ├── config.py               # env vars
│   ├── analysis/               # deterministic primitives
│   ├── voices/                 # profile model, IO, location, migration, check
│   ├── agents/                 # pydantic-ai agents
│   ├── orchestrator/           # ProseCraft + deps + prompts
│   └── references/             # inlined reference material (markdown): prose_analysis.md, diction_tuning.md, rhythm_mastery.md, cohesion_craft.md, voice_contract.md — loaded into agent system prompts; no plugin runtime dependency
├── tests/
│   ├── unit/
│   │   ├── analysis/
│   │   ├── voices/
│   │   └── agents/
│   ├── features/               # CLI + MCP round-trips
│   ├── fixtures/
│   │   ├── voices/
│   │   └── drafts/
│   └── conftest.py
├── plugin/                     # Claude Code adapter
│   ├── .claude-plugin/plugin.json
│   ├── agents/
│   ├── skills/
│   ├── output-styles/
│   └── voices/_template/voice.md
├── .claude-plugin/marketplace.json
└── docs/
    ├── README.md
    └── superpowers/
        ├── specs/
        └── plans/
```

## Testing strategy

| Layer | Tool | Coverage |
|---|---|---|
| Deterministic primitives | `pytest` + parametrize | 100% — every metric has a fixture with a known answer |
| Pydantic models | `pytest` | Round-trip every voice fixture; reject `extra` keys; assert `model_dump()` then re-parse yields equal model |
| Agent outputs | `pydantic_ai.models.function.FunctionModel` | Per-agent fixture script that drives `FunctionModel` and asserts structured output |
| CLI | Typer `CliRunner` + `FunctionModel` swap via `PROSE_CRAFT_MODEL` | Smoke-test every subcommand against a fixture draft |
| MCP server | `fastmcp.Client` over in-process transport | Round-trip every tool + resource |
| Migration | `pytest` + tmp_path | Old → new copy; idempotent re-runs; `--overwrite`; `--dry-run`; missing source; invalid name |
| Composer resume | `pytest` + harness `Memory` stub | Start compose, kill, restart, assert field index continues |

Conventions:
- `tests/unit/` — no I/O outside tmp_path; no LLM calls
- `tests/features/` — CLI + MCP round-trips with FunctionModel swaps
- `tests/fixtures/` — voice profiles, sample drafts (clean + with known violations), agent scripts
- `asyncio_mode = "auto"` (mirrors lies)
- `mypy --strict` over `src/prose_craft`
- `ruff check` + `ruff format`

## Rollout

Single PR. The rewrite is a fresh repo state; the old plugin is deleted. Both version surfaces start at `0.1.0`. CHANGELOG entry under `[Unreleased]`:

> **Changed:** Rewrite as pydantic-ai CLI + FastMCP server. Plugin reduced to thin adapter. Voice profiles moved from `${CLAUDE_PLUGIN_DATA}/voices/` to `$XDG_DATA_HOME/prose-craft/voices/`. Run `prose migrate voices` once to copy existing profiles.

The user's existing voice profiles in `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` are not touched by the upgrade. After installing the new version, the writer runs `prose migrate voices` once to copy them into the XDG tree. The old directory remains so the writer can roll back by deleting the new one.

## Risks

1. **Composer state loss on crash.** Mitigation: write to `voice.md` after every accepted field, not just on exit. `ComposerState.field_index` is the resume marker, not the source of truth.

2. **FunctionModel fixtures drift from real behavior.** Mitigation: out-of-band live-model sanity tests against real Opus on three known drafts. Drift caught before it costs a user a wrong edit.

3. **MCP stdio disconnect mid-call.** Deterministic tools (`voice_check`, `analyze_prose` metrics path) are pure functions of the file; no mid-call state. Model round-trips (`edit_prose`, `architect_prose`, `tune_diction`) are lost on disconnect; the writer re-invokes. Acceptable.

4. **XDG path resolution on macOS vs Linux.** Mitigation: the location module's tests parametrize over `XDG_DATA_HOME` set, unset, set to empty, set to relative path.

5. **Plugin adapter drift from MCP schema.** The plugin's agents are 10-line adapters over MCP tools; schema changes are reflected in the adapter markdown on the same commit.
