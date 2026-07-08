---
name: compose-voice
description: Author a new voice profile through guided dialogue. The voice-composer agent walks the writer through ten dimensions (purpose, audience, six-axis register, diction, rhythm, syntax, lexicon, structure, never-list, prose body) plus the per-voice audience ceilings, records her literal choices, and produces a populated voice.md at ${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md. Use when the writer wants to design a voice.
user-invocable: true
allowed-tools: Bash Read Write Edit
---

# Compose Voice

## Usage

`<name>` becomes the voice's directory key under `${CLAUDE_PLUGIN_DATA}/voices/<name>/` and is stored in the profile's `voice:` field. Use lowercase letters, digits, and hyphens. Examples: `MistressFilth`, `house-rfc`, `newsletter`.

## What happens

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/voice_init.py <name>`. This copies `voices/_template/voice.md` into `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` and fills the metadata placeholders (`voice`, `created`, `updated`, `author`). Exits early when the voice already exists; ask the writer whether she meant `/refine-voice <name>` instead.
2. Dispatch the `voice-composer` agent with the new voice path. The agent reads the file, walks through any null fields in fixed order (D1 → D10), and edits the front-matter via `scripts/voice_io.py` after each answer.
3. The agent is resumable. Quitting mid-session is fine; the writer re-enters with `/compose-voice <name>` (which becomes `/refine-voice <name>` once the file exists with any populated fields) to pick up where she left off.

## Operating rules

The compose dialogue is opinionated; here is what the writer can expect:

- **The writer's literal answer is what gets recorded.** No silent invention.
- **Propose, never impose.** When an earlier answer correlates with a default for a later dimension, the agent proposes after the writer arrives at that dimension and asks her to confirm.
- **Show me, don't ask me.** When the writer can't articulate a preference, the agent offers two short contrasting passages and asks which feels closer.
- **Named-source presets are offered, not pushed.** Six presets land at the relevant dimensions (Fowler, Williams, Strunk, Microsoft, Orwell, generic prose-body shape). The writer accepts, modifies, or declines each.
- **Skipping is fine.** Any dimension can be left null and filled later via `/refine-voice`.
- **Audience ceilings ship pre-filled and editable.** Right after D2, the composer confirms the voice's `audiences:` block — the three starter audiences (`private`, `team`, `external`) the template ships. The writer tightens `team`/`external` to fit how this voice carries outward, or closes either with `closed: true` + a `reason:` when the voice's affect turned toward that reader reads as performative. The ceiling travels inline with the voice; the drafter resolves it from `voice.md` and falls back to `private` for any audience the block omits. Keeping the defaults unchanged is valid.
- **Recurring-form voices get the four-failure-mode escalator at D8.** When the voice produces a recurring artifact form (postcards, memos, dispatches, letters, retros, decrees, transmissions), the composer walks the writer through the four-failure-mode opener discipline (verbatim / family-pattern at noun-slot / catch-all-frame / form-dropping). The discipline addresses a real architectural constraint — the `voice-stylist` agent has no cross-draft awareness, and the only mechanism preventing rotation/family-pattern convergence at recurring beats is what the voice profile names as a failure mode at design time. See `prose/docs/voice-design-guide.md` § "The four-failure-mode opener discipline" for the rationale.
- **Lexicon fields with 3+ rotation-prone entries ship as banks from the start.** When the writer reaches three entries in a `lexicon.*` list field, the composer asks the form-vs-rotation question — phrases that ARE the voice's signature stay inline; phrases that should rotate move into `banks/<field>.md` with `selection: random-dedup` immediately, not at the seventh-entry ceiling.

## Backup before composing

The composer mutates `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` in place via `voice_io.py`. The writer's git history is the recovery mechanism. Before running `/compose-voice` against an existing voice or before substantial refinements:

```bash
TS=$(date -u +%Y%m%d-%H%M%S)
mkdir -p /Users/MistressFilth/.claude/plugins/data/prose/voices/.backups/${TS}-compose-<name>
cp -r /Users/MistressFilth/.claude/plugins/data/prose/voices/<name> \
  /Users/MistressFilth/.claude/plugins/data/prose/voices/.backups/${TS}-compose-<name>/
```

Backups are cheap and let the writer roll back without losing prior state. See `prose/docs/voice-design-guide.md` G20.

## Outputs

- `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` — populated profile.
- Console summary: which dimensions were authored, which were skipped, which named-source presets were accepted.

The first compose run for a voice typically takes 45-90 minutes of active dialogue. The dialogue is resumable; a 20-minute session that covers D1-D3 and skips the rest is a valid first pass.
