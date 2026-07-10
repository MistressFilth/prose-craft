---
name: migrate-voice
description: Migrate an inline extensions block to separate depth files by wrapping voice_init.py --migrate-extensions. /migrate-voice applies the migration directly with no dry-run preview step. The writer recovers prior content via git history if the migration is unwanted.
user-invocable: true
allowed-tools: Bash Read
argument-hint: "<voice> [--extensions]"
---

# Migrate Voice

Apply a one-shot migration of an inline `extensions` block to separate depth files.

## Usage

```
/migrate-voice <voice> [--extensions]
```

`<voice>` is the voice directory key under `${CLAUDE_PLUGIN_DATA}/voices/<voice>/`.

## Flags

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--extensions` | boolean | false | Select the extensions migration mode (migrate inline extensions block to depth files). |

## Arguments

| Argument | Type | Description |
|---|---|---|
| `<voice>` | string | Voice name (directory key). Lowercase letters, digits, and hyphens. |

## What happens

1. Shell out to `voice_init.py --migrate-extensions <voice>`, passing the resolved voice directory path.
2. The migration runs directly with no dry-run preview step. All changes are applied in place.
3. On success, report the depth files written and the updated `voice.md` path.

> **Recovery.** Because the migration writes directly, the writer recovers prior content via `git history` if the result is unwanted. Commit or stash before invoking when unsure. When the voice's data directory is not git-tracked, take a manual backup before running:
>
> ```bash
> TS=$(date -u +%Y%m%d-%H%M%S)
> mkdir -p /Users/MistressFilth/.claude/plugins/data/prose/voices/.backups/${TS}-migrate-<voice>
> cp -r /Users/MistressFilth/.claude/plugins/data/prose/voices/<voice> \
>   /Users/MistressFilth/.claude/plugins/data/prose/voices/.backups/${TS}-migrate-<voice>/
> ```
>
> See `prose/docs/voice-design-guide.md` G20.

## What voice_init.py --migrate-extensions does

- Reads `${CLAUDE_PLUGIN_DATA}/voices/<voice>/voice.md`.
- Extracts the `extensions` front-matter block.
- Writes one depth file per sub-block (banks, wells, dials, move-catalog, surfaces).
- Strips the `extensions` block from `voice.md`.
- Adds a `depth:` manifest to `voice.md` listing each written file.
- Generates `INDEX.md` when there are three or more depth files.

## Outputs

- Updated `${CLAUDE_PLUGIN_DATA}/voices/<voice>/voice.md` — `extensions` block removed, `depth:` manifest added.
- Depth files written under the voice directory (reported by the script).
- Console confirmation from `voice_init.py` listing files written.
