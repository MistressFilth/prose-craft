---
name: list-voices
description: Enumerate the writer's voices. Lists every directory under ${CLAUDE_PLUGIN_DATA}/voices/ that contains a voice.md, with name, last-updated date, and a one-line purpose summary. Use to remember what voices exist before drafting or refining.
user-invocable: true
allowed-tools: Bash Read
---

# List voices

Enumerate voices in the writer's library.

## Usage

```
/list-voices
```

## What happens

1. Walk `${CLAUDE_PLUGIN_DATA}/voices/`. Skip dotfiles and the `_template`, `_lexicons`, `_never_lists` collections (those live in `${CLAUDE_PLUGIN_ROOT}`, not the user's data dir, but a defensive skip catches stray copies).
2. For each subdirectory containing a `voice.md`, parse the front-matter and emit one row:

   ```
   <name>............updated YYYY-MM-DD  <purpose first line>
   ```

3. When the data directory is empty or missing, print a single line:

   ```
   No voices yet. Try /compose-voice <name>.
   ```

## Outputs

- One-shot console rendering. No files written. Read-only.
