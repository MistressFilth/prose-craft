---
name: collapse-voice
description: Fold a bank depth file back into an inline lexicon entry in voice.md. /collapse-voice reads banks/<field>.md, checks that the bank's phrase count fits within the inline ceiling, writes the phrases back into lexicon.<field> in voice.md, removes the bank file, and removes its depth manifest entry. Fails when the bank exceeds the inline ceiling.
user-invocable: true
allowed-tools: Bash Read Write Edit
argument-hint: "<voice> <field>"
---

# Collapse Voice

Fold a bank depth file back into an inline lexicon entry.

## Usage

```
/collapse-voice <voice> <field>
```

`<voice>` is the voice directory key under `${CLAUDE_PLUGIN_DATA}/voices/<voice>/`.
`<field>` is the lexicon field to collapse, e.g. `lexicon.pet_phrases` and `banks/pet_phrases.md` (resolves to `pet_phrases`).

## Arguments

| Argument | Type | Description |
|---|---|---|
| `<voice>` | string | Voice name (directory key). Lowercase letters, digits, and hyphens. |
| `<field>` | string | Lexicon field name whose bank to collapse back inline. |

## What happens

1. Read `${CLAUDE_PLUGIN_DATA}/voices/<voice>/voice.md` via `voice_io.py`.
2. Locate the bank file `banks/<field>.md` via the depth manifest.
3. Read `banks/<field>.md` and count the phrases in the body.
4. Compare the phrase count against the inline ceiling for `lexicon.<field>`. The inline ceiling is 7.
5. Fail with a diagnostic when the bank exceeds the ceiling (see below).
6. Write the phrases back into `lexicon.<field>` in the voice front-matter.
7. Remove `banks/<field>.md` from the voice directory.
8. Remove the `banks/<field>.md` entry from the `depth:` manifest in `voice.md`. When the manifest becomes empty, remove the `depth:` key entirely.
9. Write the updated `voice.md` back via `voice_io.py`.

## Error conditions

- **Bank exceeds inline ceiling.** When the bank phrase count is greater than the inline ceiling, the skill fails with:

  ```
  Error: banks/<field>.md contains <actual> entries, which exceeds the inline ceiling of <ceiling>.
  Use /deepen-voice to keep the bank or trim the bank to <ceiling> entries first.
  ```

  No files are written or removed. The bank file, depth manifest, and `voice.md` are unchanged.

## Outputs

- Updated `${CLAUDE_PLUGIN_DATA}/voices/<voice>/voice.md` — `lexicon.<field>` restored inline, depth manifest entry removed.
- `${CLAUDE_PLUGIN_DATA}/voices/<voice>/banks/<field>.md` — removed.
- Console confirmation: field name, entry count restored, bank file removed.
