---
name: draft-in-voice
description: Generate prose against a designed voice. Loads the voice profile at ${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md, dispatches the voice-stylist agent in draft mode against a brief, and writes the result to a new file with `voice: <name>` front-matter. Use when the writer has a voice profile and a brief and wants new prose under that voice's rules.
user-invocable: true
allowed-tools: Bash Read Write

---

# Draft in Voice

Dispatch the `voice-stylist` agent in draft mode.

## Usage

```
/draft-in-voice <name> <brief>
/draft-in-voice <name> audience:<audience> <brief>
```

`<name>` is a voice directory under `${CLAUDE_PLUGIN_DATA}/voices/`.
`<brief>` is a short prose description of what the writer wants drafted (subject, length, audience). The brief can be a path to a markdown file or an inline string.

**State length as a word count, not a line count.** Lines are a formatting artifact (they move with paragraph-break density and sentence wrapping, not with content), so a line-count target invites the drafter into a measure-write-measure-again loop chasing a noisy number. A word count is stable and lets the drafter plan section budgets up front instead of iterating against the target after the fact. When the writer gives a line count anyway, convert it to an approximate word budget once before dispatching and pass the word figure in the brief.

`audience:<audience>` is OPTIONAL. When present, it sets the audience ceiling per § "Audience" below. Names: `private` (default when omitted), `team`, `external`, or any other name the voice declares in its own `audiences:` block. The argument may also be passed inside the brief itself as `audience:<name>` in front-matter; explicit `audience:` flag wins when both are present.

## What happens

1. **Resolve the audience.** When the writer passed `audience:<name>`, take that name. Otherwise look for an `audience:` key in the brief's front-matter when the brief is a markdown file. Otherwise default to `private`. The resolved audience is what the drafter writes into the draft front-matter in step 4.

2. **Read the voice profile.** Read `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md`. Bail with a clear error when the file is missing — suggest `/list-voices` and `/compose-voice`.

3. **Resolve the audience ceiling from the voice profile.** Look up `audiences.<resolved-audience>` in the voice's own `audiences:` block (front-matter of the `voice.md` read in step 2). When the voice declares no `audiences:` block, or the block omits the resolved audience, apply the `private` ceiling: full register, severity ceiling 5, dial ceiling 1.0, no closures. When the resolved entry declares `closed: true`, BAIL with a clear error naming the `reason:` and suggest a different audience or a different voice — do not continue.

4. **Dispatch the voice-stylist agent in draft mode.** The agent reads the voice profile as constitution, applies the audience resolution ceiling per the voice-contract's § "Audience resolution" (severity_ceiling, dial_ceiling, fallback_voice, never_extend, surface_filter), drafts prose against the brief, and runs one revision pass with `voice_check.py` before returning.

5. **Write the brief sibling.** Write the brief to a sibling `<brief-slug>.brief.md` file next to the draft so the PostToolUse hook (and `voice_check.py --brief`) can score the content half of the strip-test. When the brief argument is a path, copy the file to the sibling location; when it is an inline string, write the string verbatim. The sibling `.brief.md` is the canonical location the hook reads.

6. **Write the draft.** Default file path: `<brief-slug>.md` in the current working directory. Front-matter includes both `voice:` and `audience:`:

```markdown
---
voice: <name>
audience: <resolved-audience>
---

<draft body>
```

The PostToolUse hook fires on the write and surfaces any voice findings via the combined-output renderer.

## Audience

The audience answers "who is listening?" — perpendicular to the voice's "who is speaking?" The dial encodes register intensity; the audience encodes which surfaces and which moves carry safely to the listener. See the voice-contract's § "Audience resolution" for the full protocol; the short version:

| Audience | Default behavior |
|---|---|
| `private` | Voice as designed. Severity ceiling 5, dial unconstrained, no closures. The writer's own work. |
| `team` | Personal-affect surfaces close. Severity ceiling 3 (per voice). Teammate names cannot appear in irreverent register. The load-bearing claim still lands plainly. |
| `external` | Cosmic register closes entirely; voice falls back to `literary-editor` with the diction lexicon still binding. The voice's persona shapes thought, not surface. |

A voice may CLOSE outside private (yandere, kawaii, fnord, dandere, tsundere) — drafting against those voices with `audience:team` or `audience:external` BAILS and suggests a different voice. A voice may ADMIT external unmodified (bureaucratic, kuudere status-line, classic) — its register IS the professional surface.

Each voice's audience ceilings live in its own `audiences:` block in `voice.md`. Read that block to see what a given voice admits per audience; edit it with `/refine-voice` to change the behavior.

## Operating rules

- **Voice rules are constitution.** Every authored rule (banned words, target ranges, structural conventions, never-list entries) is honored in the first draft.
- **Audience is a ceiling, not a knob.** The audience can take admissions away from what the dial would otherwise grant; it cannot add. When the audience config declares `closed: true`, bail rather than draft.
- **Silent dimensions fall back to literary-editor.** The `literary-editor` output style governs anything the voice profile does not specify.
- **One revision pass.** After the first draft, the agent runs `voice_check.py`, addresses every mechanical and statistical violation, and returns. The hook handles iterative feedback after that.
- **Named-source attribution is preserved.** When the voice inherits rules from a named source (Williams, Orwell, Microsoft, etc.), the stylist attributes on first use and paraphrases explanatory prose.

## Outputs

- A new `.md` file with `voice: <name>` and `audience: <name>` front-matter and the drafted body.
- A short change-log printed to console: what the stylist drafted, the resolved audience and the override path used (universal-only or universal plus per-voice overrides), which voice rules were tightest, every audience-imposed ceiling that constrained the draft, what `voice_check.py` flagged.
