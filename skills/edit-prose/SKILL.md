---
name: edit-prose
description: Edit prose for clarity, rhythm, and impact. Tightens sentences, improves diction, flow, or cutting fat from writing. Use when revising a draft, improving argument-hint: "[--voice <name>] [--voice-tolerance <level>] <file-or-text>"
allowed-tools: Read, Glob, Edit, Bash
---

Edit the prose in $ARGUMENTS.

## Flags

- `--voice <name>` — optional; name of a voice profile. When provided, dispatches the voice-stylist agent in edit mode first, then runs the prose-editor four-pass edit.
- `--voice-tolerance <level>` — optional; one of `relaxed`, `normal`, or `strict`. Overrides the `voice_tolerance` declared in the file's front-matter.

## Arguments

- `<file-or-text>` — path to a markdown file, or a raw text passage.

## Behavior

Parse `$ARGUMENTS` to extract `--voice`, `--voice-tolerance`, and the file-or-text target.

**Voice mode** (when `--voice <name>` is present):

1. **Validate profile:** confirm `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` exists. When absent, halt: "Voice profile '<name>' not found. Run /list-voices or /compose-voice."
2. **Inline text:** when the target is a raw string, write it to a temp file with `---\nvoice: <name>\n[voice_tolerance: <level>]\n---\n` front-matter, run voice_check, then delete the temp file.
3. **CLI flag wins:** when both `--voice <name>` and front-matter `voice: X` are present, the CLI flag takes precedence.
4. **voice_tolerance precedence:** front-matter `voice_tolerance:` is used unless `--voice-tolerance` overrides it. Inline text defaults to `normal`.
5. **Dispatch prose-editor** in voice mode. The agent runs voice-stylist (edit mode) first for voice-rule compliance, then applies the four-pass craft edit on dimensions the profile leaves silent.
6. **Change-logs:** the agent emits three labeled sections — `rules_honored`, `fallback_dimensions`, and `agent_required`.
7. **Preserve front-matter:** the file's `voice:` key is kept intact after editing.

**Voice-blind mode** (no `--voice` flag): dispatch prose-editor for the standard four-pass craft edit.

Use the prose-editor agent and the diction-tuning, rhythm-mastery, and cohesion-craft skill references for methodology. Focus on:

1. **Cutting fat:** Remove unnecessary words, redundancies, and throat-clearing.
2. **Strengthening verbs:** Replace weak verbs and nominalizations with strong action.
3. **Tuning diction:** Prefer Germanic words for force, Latinate for precision.
4. **Varying rhythm:** Ensure sentence length variety matches emotional content.
5. **Building cohesion:** Maintain clear reference chains and appropriate connectivity.

Show before/after for significant changes with brief explanations. Preserve the author's voice while improving clarity and impact.

If no file or text is specified, ask what should be edited.
