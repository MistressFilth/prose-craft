---
name: refine-voice
description: Iterate on an existing voice profile. Re-enters the compose dialogue against the existing voice.md, picks up at the next null or unconfirmed field, and supports targeted edits to specific dimensions. Use when the writer has a populated profile and wants to refine, extend, or rethink a dimension.
user-invocable: true
allowed-tools: Bash Read Write Edit
---

# Refine Voice

Re-enter the compose dialogue against an existing voice.

## Usage

```
/refine-voice <name>              # walk all dimensions; skip already-populated ones
/refine-voice <name> <dim>        # focus on a single dimension
```

`<name>` is a voice directory under `${CLAUDE_PLUGIN_DATA}/voices/`.
`<dim>` is one of `purpose`, `audience`, `register`, `diction`, `rhythm`, `syntax`, `lexicon`, `structure`, `never`, `body`.

## What happens

1. Verify `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` exists. Bail with a clear error when missing; suggest `/compose-voice`.
2. Dispatch the `voice-composer` agent against the existing file. The agent reads what's populated, identifies the next null or unconfirmed field (or the explicitly named dimension), and walks only those.
3. Each accepted change is written back via `voice_io.py`. The prose body (D10) is preserved byte-exact unless the writer is editing it.
4. When the voice has `imported_from` set and `import-notes.md` contains unfilled D1-D10 sections, the agent continues the import protocol from the next null dimension. `/refine-voice <name> <dim>` overrides to a single-dimension edit even mid-import.

## Operating rules

- **Resumable.** Quitting mid-session is fine; the file already reflects every confirmed answer.
- **Targeted edits stay targeted.** When the writer names a dimension, the agent walks that dimension only and returns.
- **Propose, never impose.** Same protocol as `/compose-voice`.
- **D8 structure refinement runs the four-failure-mode protocol when the voice produces a recurring artifact form.** When the writer refines D8 on a recurring-form voice, the composer walks the four-failure-mode escalator (verbatim / family-pattern at noun-slot / catch-all-frame / form-dropping). When the writer is refining a one-off form, free-form prose stays the right shape.
- **D7 lexicon refinement runs the form-vs-rotation question on lists of 3+ entries.** When the writer adds a third entry to a `lexicon.*` list field, the composer asks whether the phrases are voice signature (recur by design — stay inline) or a rotation pool (recur by reflex — ship as a bank with `selection: random-dedup`).

## Backup before refining

The composer mutates `voice.md` in place. Before refining substantial dimensions (D8 structure, D7 lexicon, D9 never-list), back up the voice's directory:

```bash
TS=$(date -u +%Y%m%d-%H%M%S)
mkdir -p /Users/MistressFilth/.claude/plugins/data/prose/voices/.backups/${TS}-refine-<name>
cp -r /Users/MistressFilth/.claude/plugins/data/prose/voices/<name> \
  /Users/MistressFilth/.claude/plugins/data/prose/voices/.backups/${TS}-refine-<name>/
```

The plugin trusts git for version history when `voice.md` lives in a git-tracked directory; the snapshot above is the recovery mechanism when it does not. See `prose/docs/voice-design-guide.md` G20.

## Outputs

- `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` updated in place.
- Console summary: dimensions touched, fields changed.
