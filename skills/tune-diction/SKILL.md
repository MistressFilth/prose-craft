---
name: tune-diction
description: Analyze and tune word choice for optimal Germanic/Latinate balance. Flags pompous or flat diction and suggests concrete substitutions. Use when prose feels stuffy, flat, or mismatched to its emotional content.
argument-hint: "[--voice <name>] [--voice-tolerance <level>] <file-or-text>"
allowed-tools: Read Glob Bash
---

Analyze the diction in $ARGUMENTS.

## Flags

- `--voice <name>` — optional; name of a voice profile. When provided, dispatch voice_check.py --voice <name> <file> to obtain diction-block weighted violations, then weight substitution suggestions by the voice's diction blocks.
- `--voice-tolerance <level>` — optional; one of `relaxed`, `normal`, or `strict`. Overrides the `voice_tolerance` declared in the file's front-matter.

## Arguments

- `<file-or-text>` — path to a markdown file, or a raw text passage.

## Voice-mode dispatch

**Output format** (voice mode): produce two sections — `## Voice analysis` (violations and judgments_needed from voice_check.py) followed by `## Universal analysis` (standard diction metrics, with voice-overridden findings suppressed). The `voice_section` precedes the `universal_section`.

**Halt on missing profile**: when `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` is absent, emit: `Voice profile '<name>' not found. Run /list-voices or /compose-voice.`

When `--voice <name>` is provided:

1. Run `voice_check.py --voice <name> <file> --json` to obtain the violation report.
2. Weight substitution suggestions by the voice's diction blocks:
   - **diction.banned** — words in this list produce hard `diction.banned` violations; surface them as top-priority substitutions.
   - **diction.preferred** — words in this list produce `diction.preferred` violations; suggest the declared preferred alternative.
   - **germanic_for** — contexts declared in `germanic_for` are weighted toward Germanic vocabulary choices.
   - **latinate_for** — contexts declared in `latinate_for` mark latinate vocabulary as deliberate; these surface as `judgments_needed` items for agent review, not as hard violations. Voice-deliberate latinate vocabulary is honored, not flagged.
3. Report `violations` from the diction blocks and `judgments_needed` items from `latinate_for` separately. The `latinate_for` judgment is honored: the voice deliberately uses latinate vocabulary in those contexts, so it must not be flagged as a violation.

Use the diction-tuning skill reference for the full substitution methodology. Focus on:

1. **Identify Latinate words** that could take Germanic alternatives
2. **Flag corporate-speak**: utilize, facilitate, implement, and similar
3. **Check context**: Does the diction match the emotional content?
4. **Suggest alternatives** with before/after examples

Provide a list of suggested substitutions the user can accept or reject individually.

If no file or text is specified, ask what should be analyzed for diction.
