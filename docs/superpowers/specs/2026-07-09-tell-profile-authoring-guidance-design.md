# Voice tell-profile authoring guidance — design (v1)

**Source:** `workbench/reinhart/features/03-voice-tell-profile-authoring-guidance.md`, backed by
findings F4, F5, F14, F16 in `workbench/reinhart/FINDINGS.md`. This is feature 3 of 3 in the
plugin's sequenced Reinhart-derived feature candidates; feature 1 (cross-draft dispersion
checker) shipped as PR #1, feature 2 (clause-density diagnostic) shipped as PR #2. See
`workbench/reinhart/features/README.md` for the sequence and ground rules.

## Problem

"Use a designed voice" does not automatically mean "sound less like an LLM," and the plugin
currently has no mechanism to say otherwise. Three findings make an unqualified tell-profile
claim actively wrong, not just imprecise:

- **Direction flips by genre, for the same voice, on the same channel.** `classic` and
  `deredere` both sit below the unvoiced baseline on one brief and above it on another — a
  mirror-image swing (F5).
- **A voice's two density channels can be oppositely genre-sensitive within itself.**
  `kuudere`'s `ppc` range across genres is the widest of all four voices tested; its
  `agentless_passive` range is the narrowest (F14). "This voice is stable" is not well-formed
  without naming which channel.
- **A voice's own declared self-description does not predict its measured behavior — twice.**
  `kuudere` reads as clipped and spare by its own profile; it measures as a nominalization-density
  outlier above even a human anchor text (F4). Extended to genre-stability specifically:
  `kuudere`'s profile implies steadiness; it measures as the most volatile voice in the dataset
  on `ppc` while being the most stable on `passive` (F16).

## Scope for v1

Resolved during brainstorming:

- **Documentation-only caution, not a computed feature.** Producing an honest per-voice
  tell-profile would require a multi-genre corpus and a validated instrument per voice — the
  measurement pipeline this investigation built, not something most user-authored voices will
  ever accumulate. This feature adds no script, no new data, no wiring into feature 01/02's
  history. It adds rules and copy that prevent an unqualified tell claim from being asserted or
  transcribed anywhere in the plugin.
- **Three surfaces, all of them, redundant by design.** The unqualified claim can surface in
  three different conversations — composing a voice, drafting/editing in one, or reading the
  design guide for reference — so the guardrail has to live in all three: `voice-composer`'s
  dialogue, `voice-contract`'s operational rules (binding every consumer that loads it), and
  `voice-design-guide` as the cited evidence trail.
- **Composer trigger: any turn, not one dimension.** The danger is the unqualified claim
  appearing anywhere in the session — D1 purpose, D10 prose body, or free conversation — not
  just one dialogue step. The guard is a standing contract rule, not a single checklist item
  gated to D10.

## Architecture

Three edits, no new files except the guide entry (which is one new section in an existing
file):

1. **`docs/voice-design-guide.md`** — new entry in the existing Gotcha catalog, immediately
   after G20:

   ```markdown
   ### G21 — Self-description is not evidence of tell-profile

   A voice's own declared register axes do not predict its measured machine-tell behavior —
   this has been shown twice, on two different questions, for the same voice (F4, F16).
   Direction can flip by genre for the same voice on the same channel (F5), and a voice's two
   density channels can be oppositely genre-sensitive within itself (F14). A design note or
   dialogue answer that says "this voice de-machines" or "this voice sounds more human" is not
   a well-formed claim unless it names both the genre and the channel it was measured on — and
   even qualified, self-report is not the measurement. See `workbench/reinhart/FINDINGS.md`
   F4/F5/F14/F16 for the evidence trail.
   ```

   This is the reference anchor; the other two surfaces cite it rather than re-deriving it.

2. **`agents/voice-composer.md`** — new rule 6 in "The contract" section (currently five
   numbered rules; this becomes the sixth):

   ```markdown
   6. **Self-description is not evidence of tell-profile.** When the writer asserts an
      unqualified claim like "this voice sounds less like AI" or "this voice de-machines," you
      do not transcribe it into `voice.md` as stated. Ask her to scope the claim to a specific
      genre and channel she's actually observed ("less passive-heavy in memos, no different in
      essays"), or drop the claim from the profile. See `docs/voice-design-guide.md` G21.
   ```

   Plus one added sentence at the end of the existing "Reference: voice-design-guide" section:
   "G21 covers the tell-profile self-description trap specifically — point a writer there the
   moment she claims her voice de-machines."

3. **`skills/voice-contract/SKILL.md`** — new rule 7 in "Operating rules" (currently six
   numbered rules; this becomes the seventh):

   ```markdown
   7. **Self-description is not evidence.** Any tell-profile-style claim that surfaces in a
      change log, in drafted commentary, or in a voice's prose body must be genre-and-channel
      qualified (e.g., "less passive-dense in workplace memos; no measurable difference in
      essays") or omitted entirely. A voice's own declared register axes do not predict its
      measured behavior — this failed twice, on two different questions, for the same voice.
      Never render or honor a bare "this voice sounds more/less human" verdict. See
      `docs/voice-design-guide.md` G21.
   ```

   **Correction, added after the final whole-branch review of the implementation:** this
   paragraph originally claimed `voice-stylist`, `voice-checker`, and the `voice-author` output
   style all load `voice-contract` via their `skills:` frontmatter array, and that rule 7 alone
   would therefore bind all three. That claim was checked against the actual frontmatter of
   each file and found false — only `voice-stylist` loads `voice-contract`. `voice-checker`'s
   `skills:` field lists only `voice-craft-reference`, and `voice-author` (an output style, not
   an agent) has no `skills:` field at all; it carries its own inline copy of the operating
   rules. A fourth task (Task 4 in the implementation plan) closes this gap directly: it adds
   an equivalent rule inline to `voice-author.md`'s own numbered rule list, and adds a new row
   to `voice-checker.md`'s existing "Agent-required judgments" table (the established pattern
   that file already uses for unmechanizable checks like the Orwell stale-metaphor rule),
   rather than making either file load the whole `voice-contract` skill.

## Integration points

No data flows — these three files cite each other by G-number and rule number, not by any
runtime mechanism. G21 carries the evidence trail (F4/F5/F14/F16 citations); the composer and
contract rules state the behavioral consequence inline, so an agent reading only one of the
three still gets the actionable rule without needing to fetch the guide.

## Error handling

Not applicable — no runtime behavior changes.

## Testing

No automated tests — nothing executable changes. Self-review checklist instead:

- The three files state the same underlying claim without contradicting each other.
- G21 is the next unused gotcha number (confirmed: highest existing is G20).
- YAML frontmatter in `agents/voice-composer.md` and `skills/voice-contract/SKILL.md` is
  untouched and still parses (both files keep their existing `name`/`description`/etc. keys;
  only body prose changes).
- Existing numbered rules in both files are renumbered correctly if any insertion shifts a
  later rule (verify by re-reading the full rule list after editing, not just the diff).

## What v1 does not do

- **No computed tell-profile of any kind**, for any voice, under any circumstance. This is the
  explicit fork resolved during brainstorming — see "Scope for v1."
- **No wiring into feature 01/02's history data.** The clause-density and dispersion JSONL logs
  are not read by anything this feature adds.
- **No new taxonomy or schema field** (e.g. no `tell_profile:` key added to `voice.md`'s
  schema). The caution is prose guidance, not a structured field.
- **No lint/check pass over existing voice.md files** for prior unqualified claims. This
  feature prevents new ones going forward; auditing the existing voice library is out of scope.
