# Prose Toolkit

A Claude Code plugin for writing and editing high-quality prose. Two halves work together:

- **Universal prose analysis.** Computational-linguistics-grounded measurement (Coh-Metrix and literary craft), a three-tier agent system scaled by task complexity, and modular skills covering diction, rhythm, cohesion, and readability. Works on any prose.
- **Voice-craft (v1.1).** Designed voices as authored artifacts. The writer composes a voice through guided dialogue, drafts and edits prose against it, and the hook flags violations on every save. Voices are designed, not derived from sample corpora — no stylometry, no fingerprinting.

## Installation

Install as a Claude Code plugin:

```
/plugin install /path/to/prose
```

Or from a published source:

```
/plugin install prose
```

## Quick Start

1. Activate literary-editor mode (optional but recommended):
```
/output-style literary-editor
```

2. Get a diagnostic:
```
/analyze-prose chapter.md
```

3. Edit with feedback:
```
/edit-prose chapter.md
```

4. For critical passages, use Opus:
```
/architect-prose opening.md
```

## Automated Hook

After every Write or Edit on a prose file (`.txt`, `.md`, `.adoc`, `.rst`, `.tex`), the hook automatically runs and injects prose metrics as a system message. Files under 50 words are skipped.

The hook measures:

- **Sentence statistics** — count, mean length, standard deviation, short/long percentages
- **Word origin** — Germanic vs. Latinate classification using explicit word lists, suffix detection (e.g., `-tion`, `-ment`, `-ity`), and syllable heuristics
- **Syllable profile** — average syllables per word, polysyllabic percentage
- **Readability** — Flesch Reading Ease score
- **Cohesion markers** — causal, temporal, and additive connectives per 100 words
- **Monotony detection** — flags zones of 4+ consecutive sentences within ±3 words of each other

Example output:

```
📊 PROSE ANALYSIS: chapter-one.md
―――――――――――――――――――――――――――――――――――
Words: 1247 | Sentences: 67

RHYTHM
  Mean sentence length: 18.6 words
  Variation (std dev): 9.2 (target: 8-12)
  Short (<10 words): 22.4%
  Long (>25 words): 14.9%

DICTION
  Germanic: 58.3% | Latinate: 41.7%
  Avg syllables/word: 1.48
  Polysyllabic words: 18.2%

READABILITY
  Flesch score: 62.4 (8th-9th grade (Standard))

COHESION
  Connectives/100 words: 3.21 (target: 2-4)
  Causal markers: 8
  Temporal markers: 12

✅ Prose metrics look healthy
```

## Slash Commands

### `/analyze-prose [--voice <name>] [--voice-tolerance <level>] [file-or-text]`

Full diagnostic without edits. Use this before editing to understand what needs attention.

Produces:
- Diction balance (Germanic vs. Latinate percentages)
- Rhythm profile (mean sentence length, variance, short/long ratios)
- Cohesion score (connective density)
- Readability approximation (Flesch score)
- Priority issues with specific line references

When `--voice` is supplied, `voice_check.py` runs first and a Voice section is prepended to the universal output. Findings the voice profile explicitly overrides are removed from the universal section.

This command is read-only — it diagnoses but never rewrites.

## Flags

| Flag | Values | Default | Effect |

```
/analyze-prose draft.md
/analyze-prose --voice claire draft.md
/analyze-prose --voice claire --voice-tolerance strict draft.md
/analyze-prose "She was extremely tired and exhausted after the long and difficult day."
```

### `/edit-prose [--voice <name>] [--voice-tolerance <level>] [file-or-text]`

Implements prose improvements using a four-pass editing process:

1. **Structural** — paragraph order, flow, weak openings and closings
2. **Sentence-level** — length variation, throat-clearing removal, rhythm
3. **Word-level** — weak verbs, adverbs, clichés, nominalizations
4. **Sound** — unintentional rhyme, consonant clusters, stressed syllables

When `--voice` is supplied, the voice-stylist agent runs first in edit mode, then the prose-editor four-pass runs second. The change-log enumerates rules
honored, fallback dimensions, and agent-required entries.

Shows before/after for significant changes with brief explanations.

#### Flags

| Flag | Values | Default | Effect |
|---|---|---|---|
| `--voice <name>` | any voice profile name | _(none)_ | Run voice-stylist edit mode before the four-pass prose-editor |
| `--voice-tolerance <level>` | `relaxed`, `normal`, `strict` | `normal` (or front-matter value) | Override the tolerance level for voice-check band widths |

```
/edit-prose chapter-three.md
/edit-prose --voice claire chapter-three.md
/edit-prose --voice claire --voice-tolerance strict chapter-three.md
/edit-prose "The utilization of this approach will facilitate better outcomes."
```

### `/tune-diction [--voice <name>] [--voice-tolerance <level>] [file-or-text]`

Focused word choice pass. Identifies Latinate words that could take Germanic alternatives, flags corporate-speak, checks whether diction matches emotional
content, and suggests specific substitutions you can accept or reject individually.

When `--voice` is supplied, substitution suggestions are weighted by the voice's diction blocks (`banned`, `preferred`, `germanic_for`, `latinate_for`).
Voice-deliberate vocabulary is honored, not flagged.

#### Flags

| Flag | Values | Default | Effect |
|---|---|---|---|
| `--voice <name>` | any voice profile name | _(none)_ | Weight substitution suggestions by the voice's diction blocks |
| `--voice-tolerance <level>` | `relaxed`, `normal`, `strict` | `normal` (or front-matter value) | Override the tolerance level for voice-check band widths |

```
/tune-diction proposal.md
/tune-diction --voice claire proposal.md
```

### `/architect-prose [--voice <name>] [--voice-tolerance <level>] [file-or-text]`

Deep structural work using Opus. Reserve this for:

- Critical opening and closing passages
- Passages that `/edit-prose` cannot solve
- Voice development and establishment
- Final polish on important documents

When `--voice` is supplied, voice-checker runs first and produces a violation map. The prose-architect then runs in enforcement mode with voice-discovery
prompts suppressed. Reconstruction proposals satisfy the voice's never-list and register and rhythm targets.

Produces: voice analysis, structural diagnosis, deep issues, and a reconstruction proposal. Runs on `claude-opus-4-5` — the most capable model in the system.

#### Flags

| Flag | Values | Default | Effect |
|---|---|---|---|
| `--voice <name>` | any voice profile name | _(none)_ | Run voice-checker first; architect enforces voice constraints in reconstruction |
| `--voice-tolerance <level>` | `relaxed`, `normal`, `strict` | `normal` (or front-matter value) | Override the tolerance level for voice-check band widths |

```
/architect-prose opening.md
/architect-prose --voice claire opening.md
```

## Voice-craft

Six commands let a writer design a voice and write prose under its rules. Voices live at `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` (one file per voice,
YAML front-matter plus optional prose body). Drafts declare their voice in front-matter:

```markdown
---
voice: dnova
voice_tolerance: normal  # optional: strict | normal | relaxed
---

# Draft body
```

When `voice:` is absent, only the universal-prose check runs (no default voice is assumed).

### `/compose-voice <name>`

Author a new voice through guided dialogue. The voice-composer agent (Opus) walks the writer through ten dimensions in fixed order:

| D1 | purpose |
| D2 | audience |
| D3 | register (six axes — funny-serious, formal-casual, respectful-irreverent, enthusiastic-matter-of-fact, certainty, density) |
| D4 | diction (Saxon/Romance balance, banned words, preferred substitutions, lexicon inheritance) |
| D5 | rhythm (sentence length, variation, preferred paragraph shape) |
| D6 | syntax (em-dashes, colons, semicolons, parentheticals, fragments, bullets, questions) |
| D7 | lexicon (pet phrases, characteristic openers/closers, taboo phrases) |
| D8 | structure (opening, closing, transitions, emphasis, citations) |
| D9 | never-list |
| D10 | optional prose body |

The dialogue is resumable. The agent proposes, never imposes. Six named-source presets (Fowler, Williams, Strunk, Microsoft, Orwell, generic prose-body shape) can be accepted, modified, or declined at the relevant dimensions.

### `/refine-voice <name> [dim]`

Iterate on an existing profile. With no dimension argument, walks all unanswered fields. With a named dimension (`purpose`, `register`, `diction`, ...), focuses on that dimension only.

### `/draft-in-voice <name> <brief>`

Generate prose against a voice. The voice-stylist agent (Sonnet) reads the profile as constitution, drafts against the brief, and runs one revision pass with `voice_check.py` before returning. The draft is written with `voice: <name>` front-matter; the hook fires on save.

### `/show-voice <name>` and `/list-voices`

Read-only inspection. `/show-voice` renders a human-friendly summary; `/show-voice --raw` prints the file contents verbatim. `/list-voices` enumerates voices in `${CLAUDE_PLUGIN_DATA}/voices/`.

### Voice-aware hook

The PostToolUse hook reads each saved draft's front-matter and dispatches:

- **No `voice:` key** — universal prose analysis only (existing behavior).
- **`voice: <name>`** — runs `voice_check.py` and prepends a Voice section to the universal section. Mechanical violations carry `file:line:col` for click-through; statistical findings carry measured-vs-target; agent-required notes are folded.
- **Profile not found** — emits a single warning line; universal prose still runs.

Sub-sections (Mechanical / Statistical / Notes) appear only when their list is non-empty. Silence on a dimension means it's healthy.

`voice_tolerance: relaxed` widens statistical bands 2x and suppresses over-saturation findings. `strict` tightens edge-of-band findings.

### Shipped lexicons and never-lists

Two derived lexicons ship under `${CLAUDE_PLUGIN_ROOT}/voices/_lexicons/`. A voice references them in `diction.inherit_lexicons`.

| Lexicon | Source | License |
|---|---|---|
| `microsoft` | Microsoft Writing Style Guide A-Z | CC BY 4.0 |
| `gov-uk` | GOV.UK style guide "Words to avoid" | Open Government License v3.0 |

One starter never-list ships under `${CLAUDE_PLUGIN_ROOT}/voices/_never_lists/`.

| Never-list | Source | License |
|---|---|---|
| `microsoft-simple-human` | Microsoft brand-voice principles | CC BY 4.0 |

Never-lists are loaded by **copying** the entries you want into a voice's `never:` block — no inheritance field, since never-rules are too voice-specific to inherit silently.

### Voice-author output style

```
/output-style voice-author
```

Activates voice-aware authoring mode. The active voice profile is constitution; `literary-editor` principles apply only as fallback for dimensions the profile does not specify. When a voice rule and a literary-editor principle conflict, the voice wins.

## Output Style

### `literary-editor`

```
/output-style literary-editor
```

Activates a master literary editor mode. Transforms how the model approaches all prose work in the session.

**When editing:** Read the whole passage first, identify what works, diagnose before prescribing, preserve the writer's authentic voice, show before/after comparisons.

**When writing:** Match the existing register, default on Germanic vocabulary, vary sentence rhythm deliberately, build invisible cohesion, and strong.

**When analyzing:** Use measurable criteria, provide specific examples, prioritize the two or three most important issues, explain why — not just what.

The five principles this mode enforces:

1. The writer's voice is sacred — strengthen authenticity, don't impose preference
2. Economy is not poverty — cut what doesn't earn its place, but some passages need to breathe
3. Rhythm is meaning — sentence length, paragraph structure, and emphasis encode emotion
4. Concrete over abstract — a specific image beats a general statement
5. Trust the reader — don't explain what you've shown

## Agents

These specialized subagents for different tasks of prose work. Slash commands use these agents automatically. You can also invoke them directly for more explicit control.

### `prose-analyst` — Haiku

Model: `claude-haiku-4-5-20251001`

Skills: prose-analysis

Fast diagnostic. Measures rhythm, diction, cohesion, and readability. Diagnoses only — no rewriting.

Use directly when you want a quick, targeted diagnostic without triggering a full edit-pass:

```
Use the prose-analyst agent to evaluate the opening three paragraphs of chapter.md.
```

### `prose-editor` — Sonnet

Model: `claude-sonnet-4-5`
Tools: Read, Edit, Write, Grep, Glob, Bash
Skills: prose-analysis, diction-tuning, rhythm-mastery

Main editing workhorse. Handles sentence and paragraph-level revision, diction tuning, rhythm variation.

The six principles the editor applies:

1. **Economy Without Poverty** — cut ruthlessly but not recklessly
2. **Concrete Over Abstract** — replace abstractions with specifics
3. **Strong Verbs, Weak Modifiers** — kill adverbs, strengthen action words
4. **Germanic for Force, Latinate for Precision** — match diction to context
5. **Rhythm Is Meaning** — sentence length encodes emotion
6. **Trust the Reader** — don't explain what you've shown

Use directly when you want to give the editor a specific brief:

```
Use the prose-editor agent to tighten this paragraph: [paste text]
Use the prose-editor agent to reduce Latinate density in the third section of essay.md.
```

### `prose-architect` — Opus

Model: `claude-opus-4-5`
Tools: Read, Edit, Write, Grep, Glob, Bash
Skills: prose-analysis, diction-tuning, rhythm-mastery, cohesion-craft

Deep structural work, voice development, high-stakes polish. Reserve for critical passages.

Works by the iceberg principle: every word choice excludes a thousand others; the visible text rests on invisible decisions. The five-step rewrite protocol:

1. Identify core intent — what must this passage accomplish?
2. Find the best sentence — what works? Build from there.
3. Rebuild from principle — start fresh, keep only what earns its place
4. Check against original — preserve intent, voice, best bits
5. Read aloud — does it move?

Use directly when you need deep structural analysis without immediate rewriting:

```
Use the prose-architect agent to develop a consistent voice for this essay.
Use the prose-architect agent to analyze the argument architecture of introduction.md.
```

## Reference Skills

Four knowledge modules that load automatically and inform agent behavior. These are not user-invocable slash commands — they operate in the background, providing the computational and craft framework the agents draw on.

### `prose-analysis`

Measurement methodology grounded in computational linguistics (Coh-Metrix) and literary craft. Defines quality benchmarks, diagnostic templates, and the interpretation of all metrics the system produces.

Quality benchmarks:

| Metric | Poor | Acceptable | Excellent |
|---|---|---|---|
| Sentence length variance (std dev) | <5 | 5-12 | 8-12 |
| Latinate % | >70% | <50% | Context-appropriate |
| Connectives per 100 words | <2 | 2-5 | 3-4 |
| Polysyllabic words | >35% | 20-35% | <25% |

### `diction-tuning`

The Germanic/Latinate vocabulary system. English has two vocabularies: Germanic (body, home, heart — short, concrete, hard) and Latinate (court, academy, church — longer, abstract, softer). Knowing which to reach for is a core craft skill.

**Use Germanic for:** emotional intensity, physical action, concrete description, dialogue, death/violence/sex

**Use Latinate for:** technical precision, formal register, softening and distance, abstract concepts

The skill includes 40+ common substitutions:

| Latinate | Germanic |
|---|---|
| utilize | use |
| facilitate | help |
| demonstrate | show |
| significant | large / big |
| approximately | about |
| commence | begin / start |
| terminate | end / stop |
| attempt (v.) | try |
| sufficient | enough |
| regarding | about |

Quick test for Latinate overload: multiple `-tion`, `-ment`, `-ity` endings in a sentence; a bureaucratic feel; the sense that you need a dictionary.

### `rhythm-mastery`

Readers unconsciously synchronize with prose rhythm. Sentence length encodes emotion; variance encodes energy.

Sentence length categories:

| Length | Words | Effect |
|---|---|---|
| Very short | 1-5 | Shock, emphasis, finality |
| Short | 6-12 | Direct, clear, strong |
| Medium | 13-20 | Balanced, comfortable, flexible |
| Long | 21-35 | Flowing, complex, immersive |
| Very long | 36+ | Overwhelming, breathless, accumulating |

Five common rhythm problems:

- **The Plateau** — all sentences the same length; flat, numbing
- **The Sawtooth** — alternating long/short/long/short; predictable
- **The Run-On** — consecutive long sentences; reader loses the thread
- **The Stutter** — consecutive short sentences outside of intentional staccato
- **The Wrong Energy** — sentence rhythm contradicts emotional content

### `cohesion-craft`

Cohesion is the explicit linguistic glue between sentences and paragraphs. Four types of connections, each with different density targets:

| Connective type | Examples |
|---|---|
| Additive | and, also, moreover, in addition, furthermore |
| Adversative | but, however, yet, although, on the other hand |
| Causal | because, since, therefore, thus, hence, so, consequently |
| Temporal | then, next, after, before, during, meanwhile, subsequently |

Connective density guide:

| Density | Effect |
|---|---|
| <1 per 100 words | Choppy, disconnected |
| 1-2 per 100 words | Taut, fast-paced |
| 2-4 per 100 words | Balanced, natural |
| 4-6 per 100 words | Logical, careful |
| >6 per 100 words | Mechanical, heavy |


## Core Principles

Three measurable targets, grounded in both research and craft:

**Diction — target ≤45% Latinate.** Germanic words land harder. Latinate words carry precision and register. Most strong prose runs 55-60% Germanic. Above 45% Latinate, text starts to feel bureaucratic.

**Rhythm — target standard deviation of 8-12 words.** A low std dev means monotonous length; a high one means chaotic energy. The 8-12 range produces the feeling of controlled variation — purposeful rather than accidental.

**Cohesion — target 2-4 connectives per 100 words.** Below 2 and prose feels choppy; above 4 and it starts to feel mechanical, over-explained. The 2-4 range lets the logical connections do invisible work.

## Metrics Reference

| Metric | Threshold | Flag |
|---|---|---|
| Rhythm variance (std dev) | <5 | LOW VARIATION — monotonous |
| Rhythm variance (std dev) | >15 | HIGH VARIATION — chaotic |
| Latinate % | >45% | HEAVY LATINATE |
| Polysyllabic words | >30% | WORD COMPLEXITY |
| Connectives per 100 words | <1.5 | LOW COHESION |
| Connectives per 100 words | >5 | OVER-CONNECTED |

Flesch Reading Ease:

| Score | Grade | Audience |
|---|---|---|
| 90-100 | 5th grade | Very easy |
| 70-80 | 6th grade | Easy |
| 60-70 | 8th-9th grade | Standard |
| 50-60 | 10th-12th grade | Fairly difficult |
| 30-50 | College | Difficult |
| 0-30 | Graduate | Very difficult |

## File Structure

```
prose/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   ├── prose-analyst.md
│   ├── prose-editor.md
│   ├── prose-architect.md
│   ├── voice-composer.md         (Opus, runs compose dialogue)
│   ├── voice-stylist.md          (Sonnet, drafts and edits in voice)
│   └── voice-checker.md          (Haiku, read-only rule check)
├── skills/
│   ├── analyze-prose/SKILL.md    (slash command)
│   ├── edit-prose/SKILL.md       (slash command)
│   ├── architect-prose/SKILL.md  (slash command)
│   ├── tune-diction/SKILL.md     (slash command)
│   ├── compose-voice/SKILL.md    (slash command)
│   ├── refine-voice/SKILL.md     (slash command)
│   ├── draft-in-voice/SKILL.md   (slash command)
│   ├── show-voice/SKILL.md       (slash command)
│   ├── list-voices/SKILL.md      (slash command)
│   ├── prose-analysis/SKILL.md   (reference, auto-loaded)
│   ├── diction-tuning/SKILL.md   (reference, auto-loaded)
│   ├── rhythm-mastery/SKILL.md   (reference, auto-loaded)
│   ├── cohesion-craft/SKILL.md   (reference, auto-loaded)
│   └── voice-craft-reference/SKILL.md (reference, auto-loaded)
├── output-styles/
│   ├── literary-editor.md
│   └── voice-author.md
├── hooks/
│   ├── hooks.json
│   └── prose_analyzer.py         (universal prose + voice-aware branch)
├── scripts/
│   ├── _counting.py              (sentence/word/paragraph helpers)
│   ├── voice_io.py               (voice.md read/write, pyyaml round-trip)
│   ├── voice_init.py             (copy _template/voice.md to data dir)
│   └── voice_check.py            (rule check, JSON violation report)
└── voices/
    ├── _template/voice.md        (blank template, copied by voice_init)
    ├── _lexicons/
    │   ├── microsoft.yaml        (CC BY 4.0)
    │   └── gov-uk.yaml           (OGL v3.0)
    └── _never_lists/
        └── microsoft-simple-human.yaml (CC BY 4.0)
```

The writer's voices live under `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` — separate from the plugin's bundled assets, persistent across plugin updates.
