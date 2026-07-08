---
name: architect-prose
description: Deep structural analysis and rewriting for critical passages. Uses Opus for highest-quality work on voice, architecture, and polish. Use for high-stakes passages that lighter editing cannot fix.
argument-hint: "[--voice <name>] [--voice-tolerance <level>] <file-or-text>"
model: opus
allowed-tools: Read Glob Edit Bash
---

Perform deep structural analysis of $ARGUMENTS using the prose-architect agent (Opus).

## Flags

- `--voice <name>` — optional; name of a voice profile. When provided, dispatches the voice-checker agent first and runs prose-architect in enforcement mode with voice-discovery prompts suppressed.
- `--voice-tolerance <level>` — optional; one of `relaxed`, `normal`, or `strict`. Overrides the `voice_tolerance` declared in the file's front-matter.

## Arguments

- `<file-or-text>` — path to a markdown file, or a raw text passage.

## Behavior

**Voice mode** (when `--voice <name>` is present):

1. **Validate profile**: confirm `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` exists. When absent, halt: "Voice profile '<name>' not found. Run /list-voices or /compose-voice."
2. **Enforcement mode**: dispatch prose-architect with the voice-checker violation map. Voice-discovery prompts are suppressed — the voice profile governs register, rhythm, and diction already. The `## Voice analysis` output section is replaced by voice-checker's findings verbatim.
3. **Reconstruction proposals** satisfy all entries in the voice's `never:` list and declared `register.*` and `rhythm.*` targets.
4. **Output format**: `## Voice analysis` (voice-checker findings) followed by `## Structural analysis` and proposals.

**Voice-blind mode**: standard structural analysis and reconstruction.

This is for high-stakes work requiring:

1. **Voice analysis**: Identify authentic voice markers, best sentences, voice breaks
2. **Structural diagnosis**: Paragraph architecture, scene structure, argument flow
3. **Deep issues**: Fundamental problems requiring structural solutions
4. **Reconstruction**: If needed, complete rewriting from core intent

This agent uses Opus for maximum capability. Reserve for:
- Critical opening/closing passages
- Passages that `/edit-prose` cannot solve
- Voice development and establishment
- Final polish on important documents

If no file or text is specified, ask what needs deep work.
