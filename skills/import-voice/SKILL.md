---
name: import-voice
description: Bootstrap a new voice profile from authored source material. The voice-composer agent reads documents or notes the writer provides, walks D1-D10 with citation-grounded proposals, and produces a populated voice.md. Use when the writer has existing documentation that describes or specifies a voice. Importing is transcription, not cloning — the writer's authored choices drive every dimension.
user-invocable: true
allowed-tools: Bash Read Write Edit

---

# Import voice

Bootstrap and run an import-voice session.

## Usage

```
/import-voice <name>
```

`<name>` becomes the voice's directory key under `${CLAUDE_PLUGIN_DATA}/voices/<name>/` and is stored in the profile's `voice:` field. Use lowercase letters, digits, and hyphens. Examples: `discordian`, `house-rfc`, `noir-detective`.

## What happens

1. Bail when `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` already exists. Suggest `/refine-voice <name>` to iterate on an existing profile.
2. Prompt the writer for a one-line description of the source material. This description is stored in the profile as `imported_from:` — a single audit-log line visible in every future inspection. Then run:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/voice_init.py <name> \
  --from "<description>"
```
3. Dispatch the `voice-composer` agent with the new voice path. The agent detects `imported_from:` set in the front-matter and runs the import protocol: it solicits intake, reads every path the writer provides, and walks D1-D10 with citation-grounded proposals. Standard compose questions fill any dimension the intake material does not address.

## Operating rules

- **Propose, never impose.** Same contract as `/compose-voice`. Every value the writer sees is a proposal; her literal confirmation is what gets written.
- **Designing, not deriving.** This skill imports authored descriptions of a voice, not a prose corpus to measure. When the writer pastes finished-prose samples, the agent applies the corpus-refusal rule.
- **Resumable.** `import-notes.md` captures the citation for every filled dimension. Quitting mid-session is fine; `/refine-voice <name>` continues from the next unfilled dimension.
- **One source description, many documents.** The `--from` description is a one-liner (e.g. "Pope-mode from sacred-lexicon"). The writer pastes the actual file paths or notes during the intake turn.
- **Audience ceilings ship pre-filled and editable.** The imported voice starts with the template's three starter audiences (`private`, `team`, `external`). At D2.5 the composer confirms or tightens them: when the intake material describes how the voice carries to teammates or public readers, the composer cites it and proposes the matching ceiling (tighten, widen, or `closed: true` + `reason:`); otherwise the starter defaults stand as compose-fallback. The ceiling travels inline in `voice.md`; the drafter resolves it there and falls back to `private` for any audience the block omits.
- **Recurring-form voices get the four-failure-mode escalator at D8.** When the imported voice produces a recurring artifact form, the composer walks the writer through the four-failure-mode opener discipline (verbatim / family-pattern / catch-all-frame / form-drop). See `prose/docs/voice-design-guide.md` § "The four-failure-mode opener discipline" for the rationale.
- **Imported lexicon fields get the form-vs-rotation triage.** When intake produces 3+ phrases for a `lexicon.*` field, the composer asks whether the phrases are voice signature (stay inline) or a rotation pool (ship as `banks/<field>.md` with `selection: random-dedup`). See G2 / G16 in the design guide.
- **Imported exemplars are register-anchors, not finished prose.** When intake material includes finished sample artifacts, the composer refuses to ship them as exemplars and instead authors a register-anchor exemplar describing the registers and failure modes the sample artifacts illustrate. See G17.

## Outputs

- `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` — populated profile.
- `${CLAUDE_PLUGIN_DATA}/voices/<name>/import-notes.md` — per-dimension citation trail (intake §N or path:lines for each confirmed value, compose-fallback entries marked, full candidate lists for narrowed fields, unresolved references).
- Console summary: dimensions sourced from intake vs. compose fallback vs. unresolved; named-source presets accepted.
