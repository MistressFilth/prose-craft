---
name: analyze-prose
description: Analyze the prose quality of a file or text passage. Measures rhythm, diction, cohesion, and readability. Use when evaluating writing quality, diagnosing problems, or measuring improvement.
argument-hint: "[--voice <name>] [--voice-tolerance <level>] <file-or-text>"
allowed-tools: Read Glob Bash
---

Analyze the prose quality of $ARGUMENTS.

## Flags

- `--voice <name>` — optional; name of a voice profile stored at `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md`. When provided, dispatches the voice-checker agent first and includes a voice section in the report.
- `--voice-tolerance <level>` — optional; one of `relaxed`, `normal`, or `strict`. Default: `normal` for inline text; front-matter value for files. Overrides the `voice_tolerance` declared in the file's front-matter.

## Arguments

- `<file-or-text>` — path to a markdown file, or a raw text passage passed as a string.

## Behavior

Parse `$ARGUMENTS` to extract `--voice`, `--voice-tolerance`, and the file-or-text target.

### Voice-blind path (no `--voice` flag)

When `--voice` is absent, produce the universal prose diagnostic unchanged:

1. **Diction balance:** Germanic vs Latinate word usage
2. **Sentence rhythm:** Length variation, monotony zones, pattern assessment
3. **Cohesion metrics:** Referential, causal, and temporal connectivity
4. **Readability:** Flesch score and grade level appropriateness

### Voice-mode path (`--voice <name>` provided)

1. **Validate the profile.** Check that `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` exists.
   If the profile is missing, halt and emit:

   ```
   Error: voice profile "<name>" not found at ${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md
   Run /list-voices to see available profiles.
   Run /compose-voice to create a new profile.
   ```

2. **Resolve the target.** When `$ARGUMENTS` contains a raw text passage (not a file path), write it to a temporary file with voice front-matter:

   ```
   ---
   voice: <name>
   voice_tolerance: <resolved-tolerance>
   ---

   <raw text>
   ```

   Run the voice check against the temp file, then delete the temp file.

3. **Resolve voice tolerance.** Precedence (highest to lowest):
   - `--voice-tolerance <level>` CLI flag
   - `voice_tolerance:` declared in the file's front-matter
   - Default: `normal`
   For inline text, the default is always `normal` unless `--voice-tolerance` is explicitly passed.

4. **Dispatch voice-checker first.** Run `voice_check.py <file> --voice <name> --voice-tolerance <level> --json` via Bash. Capture the violation report.
5. **Dispatch prose-analyst second.** Use the prose-analyst agent for the universal prose diagnostic.
6. **Emit the two-section report.** Voice section first, universal section second. Suppress any sub-section whose finding list is null or empty (no pattern).

```
## Voice: <name>

<voice violations and judgments>

## Universal prose

<standard prose diagnostic>
```

If no file or text is specified, ask what should be analyzed.

After the analysis, provide prioritized recommendations for improvement and ask if the user wants to proceed with editing using `/edit-prose`.
