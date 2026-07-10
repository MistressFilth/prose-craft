---
name: show-voice
description: Print a voice profile. Reads ${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md and renders a human-friendly summary of the front-matter dimensions plus the prose body. Use when the writer wants to remember what a voice says, share it, or audit it before drafting.
user-invocable: true
allowed-tools: Bash Read
---

# Show voice

Print a voice profile.

## Usage

```
/show-voice <name>              # render the human-friendly summary
/show-voice <name> --raw        # print the raw voice.md contents
```

## What happens

1. Resolve `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md`. Bail when missing; suggest `/list-voices`.
2. With no flags, render a summary in this shape:

   ```
   Voice: <name>              (created YYYY-MM-DD, updated YYYY-MM-DD)
   Author: <author>

   Purpose:    <D1 prose>
   Audience:   <D2 prose>

   Register:
     funny-serious...................0.7
     formal-casual....................0.4
     respectful-irreverent............0.2
     enthusiastic-matter-of-fact......0.6
     certainty.........................0.5
     density...........................0.7

   Diction:
     balance:        60% Germanic / 40% Latinate
     banned (3):     utilize, leverage, robust
     preferred (5):  click → select, ...
     inheriting:     microsoft, gov-uk

   Rhythm:
     mean sentence:  15-20 words
     variation:      high — std dev around 11
     paragraph:      3-5 sentences
     one-sentence:   sparingly, for landing

   Syntax:
     em-dashes:      encouraged for parenthetical reframing
     semicolons:     rare; prefer two sentences
     ...

   Lexicon:
     pet phrases (3): let me, the boundary is, ...
     openers (2): ...
     closers (1): ...
     taboo (4): ...

   Structure:
     opening: leads with a concrete observation
     closing: ends on a single short sentence
     ...

   Never (5 rules):
     - rhetorical questions used for emphasis
     - [orwell-i] never use a stale metaphor (agent-required)
     ...

   Prose body:
     [D10 content if present]
   ```

3. With `--raw`, print the file contents verbatim (front-matter and body).

## Outputs

- One-shot console rendering. No files written. Read-only.
