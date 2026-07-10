---
name: deepen-voice
description: Move one inline list from voice.md into a bank file. /deepen-voice takes the named field (e.g. pet_phrases) from lexicon, writes it as a bank depth file at banks/<field>.md with kind:bank front-matter, removes the inline key from voice.md, and registers the bank in the depth manifest. Fails fast when the field already has a bank file.
user-invocable: true
allowed-tools: Bash Read Write Edit
argument-hint: "<voice> <field>"
---

# Deepen Voice

Move an inline lexicon list into a dedicated bank depth file.

## Usage

```
/deepen-voice <voice> <field>
```

`<voice>` is the voice directory key under `${CLAUDE_PLUGIN_DATA}/voices/<voice>/`.
`<field>` is the lexicon field to deepen, e.g. `lexicon.pet_phrases` in the voice front-matter, `pet_phrases` (resolves to same).

## Arguments

| Argument | Type | Description |
|---|---|---|
| `<voice>` | string | Voice name (directory key). Lowercase letters, digits, and hyphens. |
| `<field>` | string | Lexicon field name to move into a bank file. |

## What happens

1. Read `${CLAUDE_PLUGIN_DATA}/voices/<voice>/voice.md` via `voice_io.py`.
2. Fail fast with a diagnostic naming the existing bank file path when `banks/<field>.md` already appears in the depth manifest.
3. Extract the inline list at `lexicon.<field>` from the voice front-matter.
4. Write `${CLAUDE_PLUGIN_DATA}/voices/<voice>/banks/<field>.md` with the following front-matter shape:

   ```yaml
   kind: bank
   field: lexicon.<field>
   selection: random-dedup
   exhaustion: cycle
   floor: <count>
   ```

   where `<count>` equals the number of entries in the extracted list. The numbered list of phrases follows as the body.
5. Remove the inline `lexicon.<field>` key from `voice.md`.
6. Add a `depth:` manifest entry `{path: banks/<field>.md, kind: bank}` to `voice.md`. When `depth:` is absent, initialize it as a list with this single entry.
7. Write the updated `voice.md` back via `voice_io.py`.

## Error conditions

- **Field already banked.** When `banks/<field>.md` is present in the depth manifest, the skill fails with:

  ```
  Error: lexicon.<field> is already banked at banks/<field>.md
  ```

  No files are written. The existing bank and depth manifest are unchanged.

## Outputs

- `${CLAUDE_PLUGIN_DATA}/voices/<voice>/banks/<field>.md` — new bank depth file.
- Updated `${CLAUDE_PLUGIN_DATA}/voices/<voice>/voice.md` — inline key removed, depth manifest updated.
- Console confirmation: bank path, field name, entry count, new floor value.
