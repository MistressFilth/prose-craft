# Voice Tell-Profile Authoring Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent any unqualified voice tell-profile claim ("this voice sounds less like AI")
from being asserted or transcribed anywhere in the plugin, by adding the evidence-backed rule
to every surface that actually needs it: the design guide, the voice-composer dialogue, the
voice-contract operational rules, and (added as Task 4, after the final whole-branch review
found the original three-task scope didn't actually reach two consumers) voice-author's own
inline rule copy and voice-checker's agent-required judgment table.

**Architecture:** Plain-text edits to existing files. No new files (except the one new guide
section), no new code, no new automated tests — this is a documentation-only feature (confirmed
during brainstorming: no computed tell-profile, no wiring into feature 01/02's history data).
Each task edits its file(s) and ends with its own commit.

**Task 4 provenance:** the original plan assumed (per the design spec's Architecture section)
that voice-contract's rule 7 would bind voice-stylist, voice-checker, and the voice-author
output style, because voice-contract's own frontmatter `description` claims all three load it.
The final whole-branch review after Tasks 1-3 checked the actual `skills:` frontmatter of each
file and found that claim false: only voice-stylist loads voice-contract. voice-author has no
`skills:` field at all and carries its own inline copy of the operating rules (currently 7,
ending at "After each pass, name the rules touched"); voice-checker loads only
`voice-craft-reference`. Task 4 closes this gap directly in both files rather than by making
either of them load voice-contract (voice-checker's existing 4-rule "The contract" structure is
unrelated to voice-contract's numbered operating rules, and importing the whole skill would
pull in unrelated machinery — depth files, base inheritance, audience resolution — that
voice-checker's narrow read-only job doesn't use).

**Tech Stack:** Markdown only. No scripts, no dependencies, no test runner involved.

## Global Constraints

- Plain conventional-commit messages. No `Co-Authored-By: Claude` or any AI-attribution
  trailer, in any commit, on this branch (repo owner's global instruction — strict).
- No computed tell-profile, no new schema field on `voice.md`, no wiring into feature 01/02's
  JSONL history — this feature is prose guidance only (design spec § "What v1 does not do").
- Every new rule/entry must cite `docs/voice-design-guide.md` G21 and the underlying findings
  (F4, F5, F14, F16) — never assert the claim without a citation back to the evidence.
- Work happens directly on the current branch, `feature/tell-profile-authoring-guidance`, in
  the worktree at `/home/divinefilth/code/github/DivineFilth/prose-craft/feature-tell-profile-authoring-guidance/`.
  The branch already exists and already carries the spec commit (`ae32e0b`). Do not create a
  new branch.

---

### Task 1: Add G21 to the voice design guide

**Files:**
- Modify: `docs/voice-design-guide.md:279-283` (insert a new section between the existing G20
  entry and the `---` divider that follows it)

**Interfaces:**
- Consumes: nothing from earlier tasks (this is the first task).
- Produces: the citation target `docs/voice-design-guide.md` G21, which Task 2 and Task 3 both
  reference by name. Later tasks must cite it as `` `docs/voice-design-guide.md` G21 `` — that
  exact string, so a reader can find it with a literal search.

- [ ] **Step 1: Locate the exact insertion point**

Read `docs/voice-design-guide.md` around line 279. The current content at that location reads:

```markdown
### G20 — Back up before every voice change

Voice editing is iterative and rollback is cheap. Before each change, copy the voice directory to a timestamped sibling under `${CLAUDE_PLUGIN_DATA}/voices/.backups/<timestamp>-<change-name>/`. Recover with a reverse copy. The family's iteration accumulated a backup per state change, and every one of them earned its keep at least once.

---
```

The `---` is the divider between the "Gotcha catalog" section and the "Authoring checklist"
section that follows. The new entry goes after G20's paragraph and before that `---`.

- [ ] **Step 2: Insert the new G21 entry**

Using the Edit tool, replace:

```
Voice editing is iterative and rollback is cheap. Before each change, copy the voice directory to a timestamped sibling under `${CLAUDE_PLUGIN_DATA}/voices/.backups/<timestamp>-<change-name>/`. Recover with a reverse copy. The family's iteration accumulated a backup per state change, and every one of them earned its keep at least once.

---
```

with:

```
Voice editing is iterative and rollback is cheap. Before each change, copy the voice directory to a timestamped sibling under `${CLAUDE_PLUGIN_DATA}/voices/.backups/<timestamp>-<change-name>/`. Recover with a reverse copy. The family's iteration accumulated a backup per state change, and every one of them earned its keep at least once.

### G21 — Self-description is not evidence of tell-profile

A voice's own declared register axes do not predict its measured machine-tell behavior — this has been shown twice, on two different questions, for the same voice (F4, F16). Direction can flip by genre for the same voice on the same channel (F5), and a voice's two density channels can be oppositely genre-sensitive within itself (F14). A design note or dialogue answer that says "this voice de-machines" or "this voice sounds more human" is not a well-formed claim unless it names both the genre and the channel it was measured on — and even qualified, self-report is not the measurement. See `workbench/reinhart/FINDINGS.md` F4/F5/F14/F16 for the evidence trail.

---
```

This is a pure insertion — the G20 paragraph and the trailing `---` are unchanged, the new
section lands between them.

- [ ] **Step 3: Self-review checklist**

Read the file back around lines 279-295 and confirm, one item at a time:

1. The heading reads exactly `### G21 — Self-description is not evidence of tell-profile`
   (em dash, not hyphen — matches every other entry's heading style, e.g. `### G20 — Back up
   before every voice change`).
2. The paragraph text matches the Step 2 block verbatim — no paraphrasing.
3. `### G20` immediately precedes `### G21`, and `### G21`'s paragraph is immediately followed
   by the `---` divider (i.e. nothing was accidentally duplicated or dropped).
4. Run `grep -c "^### G" docs/voice-design-guide.md` — expect `21` (one heading per gotcha,
   G1 through G21).

- [ ] **Step 4: Commit**

```bash
git add docs/voice-design-guide.md
git commit -m "docs: add G21 gotcha on tell-profile self-description"
```

---

### Task 2: Add the composer dialogue rule

**Files:**
- Modify: `agents/voice-composer.md:19` (append a new rule 6 to "The contract" section)
- Modify: `agents/voice-composer.md:383` (append a sentence to "## Reference:
  voice-design-guide")

**Interfaces:**
- Consumes: cites `docs/voice-design-guide.md` G21, produced by Task 1. Task 1 must be
  complete and committed before this task starts (so the citation target actually exists in
  the file this task's reviewer will read — though the citation is a plain string reference,
  not a working hyperlink, so there is no build-time dependency; the ordering is for review
  clarity only).
- Produces: nothing later tasks consume by name — Task 3 is independent of this task's content
  (it edits a different file and does not reference "The contract" section).

- [ ] **Step 1: Locate the exact insertion point in "The contract"**

Read `agents/voice-composer.md` lines 13-19. The current content is:

```markdown
## The contract

1. **The writer's literal answer is what gets recorded.** When she says "0.7" for a register dimension, you write 0.7. When she says "I don't know," you offer to skip the dimension and return later.
2. **Propose, never impose.** When an earlier answer correlates with a default for a later dimension, you propose the default before that dimension is reached and ask her to confirm.
3. **Skipping is fine.** Any dimension can be left `null`. The writer can fill it in later via `/refine-voice`.
4. **Resumable.** Read the existing `voice.md` first. Pick up at the next null or missing field. Do not re-ask answered questions unless the writer says "go back."
5. **No invention.** If you do not know the writer's answer, you ask. You do not produce her values from your own taste.
```

Five numbered rules, ending at rule 5. The new rule 6 appends after rule 5.

- [ ] **Step 2: Insert rule 6**

Using the Edit tool, replace:

```
5. **No invention.** If you do not know the writer's answer, you ask. You do not produce her values from your own taste.

## Inputs and outputs
```

with:

```
5. **No invention.** If you do not know the writer's answer, you ask. You do not produce her values from your own taste.
6. **Self-description is not evidence of tell-profile.** When the writer asserts an unqualified claim like "this voice sounds less like AI" or "this voice de-machines," you do not transcribe it into `voice.md` as stated. Ask her to scope the claim to a specific genre and channel she's actually observed ("less passive-heavy in memos, no different in essays"), or drop the claim from the profile. See `docs/voice-design-guide.md` G21.

## Inputs and outputs
```

- [ ] **Step 3: Locate the exact insertion point in "Reference: voice-design-guide"**

Read `agents/voice-composer.md` lines 381-384. The current content is:

```markdown
## Reference: voice-design-guide

The plugin ships a comprehensive guide at `prose/docs/voice-design-guide.md` covering 20 gotchas observed across the discordian voice family rewrite. When a writer asks "is this normal?" or "why does my voice keep producing X?", point her at the guide. The four-failure-mode discipline in this protocol is documented there in full with empirical iteration data showing the convergence ladder.
```

- [ ] **Step 4: Append the pointer sentence**

Using the Edit tool, replace:

```
The plugin ships a comprehensive guide at `prose/docs/voice-design-guide.md` covering 20 gotchas observed across the discordian voice family rewrite. When a writer asks "is this normal?" or "why does my voice keep producing X?", point her at the guide. The four-failure-mode discipline in this protocol is documented there in full with empirical iteration data showing the convergence ladder.
```

with:

```
The plugin ships a comprehensive guide at `prose/docs/voice-design-guide.md` covering 20 gotchas observed across the discordian voice family rewrite. When a writer asks "is this normal?" or "why does my voice keep producing X?", point her at the guide. The four-failure-mode discipline in this protocol is documented there in full with empirical iteration data showing the convergence ladder. G21 covers the tell-profile self-description trap specifically — point a writer there the moment she claims her voice de-machines.
```

Note: this file's guide references say "20 gotchas" and use the path `prose/docs/voice-design-guide.md` (this plugin's docs are referenced with a `prose/` prefix from the agent's perspective) — leave that count and path exactly as they are; this task only appends the new sentence, it does not correct or renumber the "20 gotchas" count, since that count describes the guide as a whole and updating it is out of scope for this task (the guide itself is the source of truth for how many gotchas it has; this sentence doesn't claim a count).

- [ ] **Step 5: Self-review checklist**

Read the file back and confirm, one item at a time:

1. Lines 1-9 (the YAML frontmatter, delimited by `---` at the top) are byte-for-byte unchanged
   — `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `skills` all still present
   with their original values.
2. "The contract" section now has exactly 6 numbered rules, in order 1 through 6, with no
   renumbering of 1-5 (only rule 6 was added).
3. Rule 6's text matches Step 2's block verbatim.
4. The "Reference: voice-design-guide" section's added sentence matches Step 4's block
   verbatim, and it is the last sentence in that paragraph (not inserted mid-paragraph).
5. Run `grep -n "^[0-9]\. \*\*" agents/voice-composer.md | head -10` and confirm the contract's
   six rules list as `1.` through `6.` with no gaps or duplicate numbers.

- [ ] **Step 6: Commit**

```bash
git add agents/voice-composer.md
git commit -m "docs: add tell-profile self-description guard to voice-composer"
```

---

### Task 3: Add the voice-contract operating rule

**Files:**
- Modify: `skills/voice-contract/SKILL.md:21` (append a new rule 7 to "Operating rules")

**Interfaces:**
- Consumes: cites `docs/voice-design-guide.md` G21, produced by Task 1. As with Task 2, this
  is a plain string citation with no build-time dependency, but Task 1 should be complete first
  for review clarity.
- Produces: nothing further — this is the last task in the plan.

- [ ] **Step 1: Locate the exact insertion point**

Read `skills/voice-contract/SKILL.md` lines 14-23. The current content is:

```markdown
## Operating rules

1. **When the document declares `voice: <name>` in front-matter,** read `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md`. That profile governs.
2. **Honor every explicit rule in the profile.** Banned words stay out. Preferred substitutions land. Target ranges (`rhythm.target_mean_sentence`, `paragraph_shape`) are met.
3. **Honor the prose body** (D10) as guidance for everything outside the YAML rule list.
4. **When the profile is silent on a dimension,** defer to `literary-editor`. The voice's `fallbacks.when_voice_silent` field names this fallback explicitly.
5. **Resolve the audience before drafting.** Read the draft's `audience: <name>` front-matter; default to `private`. Apply the audience ceiling per § "Audience resolution" below. The ceiling can take admissions away from what the dial would otherwise grant; it cannot add.
6. **After each pass, name the rules touched.** Print a short change log: which voice rules were tightest, which fell back to literary-editor, which are agent-required (interpretive). Name the resolved audience and any closures it applied.

## Voice rule precedence
```

Six numbered rules, ending at rule 6. The new rule 7 appends after rule 6.

- [ ] **Step 2: Insert rule 7**

Using the Edit tool, replace:

```
6. **After each pass, name the rules touched.** Print a short change log: which voice rules were tightest, which fell back to literary-editor, which are agent-required (interpretive). Name the resolved audience and any closures it applied.

## Voice rule precedence
```

with:

```
6. **After each pass, name the rules touched.** Print a short change log: which voice rules were tightest, which fell back to literary-editor, which are agent-required (interpretive). Name the resolved audience and any closures it applied.
7. **Self-description is not evidence.** Any tell-profile-style claim that surfaces in a change log, in drafted commentary, or in a voice's prose body must be genre-and-channel qualified (e.g., "less passive-dense in workplace memos; no measurable difference in essays") or omitted entirely. A voice's own declared register axes do not predict its measured behavior — this failed twice, on two different questions, for the same voice. Never render or honor a bare "this voice sounds more/less human" verdict. See `docs/voice-design-guide.md` G21.

## Voice rule precedence
```

- [ ] **Step 3: Self-review checklist**

Read the file back and confirm, one item at a time:

1. Lines 1-6 (the YAML frontmatter, delimited by `---` at the top) are byte-for-byte unchanged
   — `name`, `description`, `user-invocable` all still present with their original values.
2. "Operating rules" now has exactly 7 numbered rules, in order 1 through 7, with no
   renumbering of 1-6 (only rule 7 was added).
3. Rule 7's text matches Step 2's block verbatim.
4. "## Voice rule precedence" still immediately follows the rules list — nothing else was
   inserted between rule 7 and that heading.
5. Run `grep -n "^[0-9]\. \*\*" skills/voice-contract/SKILL.md | head -10` and confirm the
   operating rules list as `1.` through `7.` with no gaps or duplicate numbers.

- [ ] **Step 4: Commit**

```bash
git add skills/voice-contract/SKILL.md
git commit -m "docs: add tell-profile self-description guard to voice-contract"
```

---

### Task 4: Close the voice-author and voice-checker coverage gap

**Files:**
- Modify: `output-styles/voice-author.md:13-21` (append a new rule 8 to its inline "Operating
  rules" section)
- Modify: `agents/voice-checker.md:87-97` (add a new row to the "Agent-required judgments"
  table)

**Interfaces:**
- Consumes: cites `docs/voice-design-guide.md` G21, produced by Task 1.
- Produces: nothing further — this is the last task in the plan.

- [ ] **Step 1: Locate the exact insertion point in voice-author.md**

Read `output-styles/voice-author.md` lines 13-21. The current content is:

```markdown
## Operating rules

1. **When the document declares `voice: <name>` in front-matter**, read `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md`. That profile governs.
2. **Honor every explicit rule in the profile.** Banned words stay out. Preferred substitutions land. Target ranges (`rhythm.target_mean_sentence`, `paragraph_shape`) are met. Structural conventions are followed. Every entry in `never:` is honored.
3. **Honor the prose body** (D10) as guidance for everything not in the YAML rule list.
4. **When the profile is silent on a dimension**, defer to `literary-editor`. The voice's `fallbacks.when_voice_silent` field names this fallback explicitly.
5. **When a voice rule and a literary-editor principle conflict, the voice wins.** Note the override in the draft's commit message.
6. **Resolve the audience before drafting.** Read the draft's `audience: <name>` front-matter. When absent, default to `private`. Apply the audience ceiling per § "Audience resolution" below. The ceiling can take admissions away from what the dial would otherwise grant; it cannot add.
7. **After each pass, name the rules touched.** Print a short change-log: which voice rules were tightened, which fell back to literary-editor, which are agent-required (interpretive). Name the resolved audience and any closures it applied.
```

Seven numbered rules, ending at rule 7. This file has its own inline copy of the operating
rules (not a `skills:` reference to `voice-contract` — this file has no `skills:` frontmatter
field at all), so the new rule appends here directly as rule 8, not rule 7 as it was in
`voice-contract/SKILL.md` (that file only had 6 rules before Task 3's rule 7).

- [ ] **Step 2: Insert rule 8 in voice-author.md**

Using the Edit tool, replace:

```
7. **After each pass, name the rules touched.** Print a short change-log: which voice rules were tightened, which fell back to literary-editor, which are agent-required (interpretive). Name the resolved audience and any closures it applied.

## Depth files
```

with:

```
7. **After each pass, name the rules touched.** Print a short change-log: which voice rules were tightened, which fell back to literary-editor, which are agent-required (interpretive). Name the resolved audience and any closures it applied.
8. **Self-description is not evidence of tell-profile.** Any tell-profile-style claim that surfaces in the change log, in drafted commentary, or in a voice's prose body must be genre-and-channel qualified (e.g., "less passive-dense in workplace memos; no measurable difference in essays") or omitted entirely. A voice's own declared register axes do not predict its measured behavior — this failed twice, on two different questions, for the same voice. Never render or honor a bare "this voice sounds more/less human" verdict. See `docs/voice-design-guide.md` G21.

## Depth files
```

- [ ] **Step 3: Locate the exact insertion point in voice-checker.md**

Read `agents/voice-checker.md` lines 87-99. The current content is:

```markdown
## Agent-required judgments

For rules `voice_check.py` cannot mechanize, you exercise judgment. Examples:

| Rule | Mechanizable? | Your judgment |
|------|---------------|-----|
| `diction.banned: "utilize"` | Yes (regex) | Skip — script handles |
| `orwell-i` (stale metaphor) | No | Read each metaphor; flag the stale ones; one-line reason |
| `register.formal_casual` reading | No | Read a paragraph; flag if it reads outside the target range; one sentence per flag |
| `lexicon.pet_phrases` (was used naturally?) | No | Note where they're used and whether they feel forced |
| `never:` rules with `detection: agent_required` | No | Apply judgment per rule |

Keep judgments short. One sentence per flag. No rewrites, no suggestions, no revisions.
```

This table is voice-checker's existing pattern for exactly this class of unmechanizable
check — a tell-profile self-description claim in the voice's own D10 prose body belongs here
as a new row, not as a `skills:` import of the whole `voice-contract` file (which would pull in
unrelated machinery — depth files, base inheritance, audience resolution — that this narrow
read-only checker doesn't use).

- [ ] **Step 4: Insert the new row in voice-checker.md**

Using the Edit tool, replace:

```
| `never:` rules with `detection: agent_required` | No | Apply judgment per rule |

Keep judgments short. One sentence per flag. No rewrites, no suggestions, no revisions.
```

with:

```
| `never:` rules with `detection: agent_required` | No | Apply judgment per rule |
| tell-profile self-description in the voice's D10 prose body | No | Flag any unqualified "this voice sounds more/less human" or "de-machines" claim; a valid claim must name both a genre and a channel it was measured on. See `docs/voice-design-guide.md` G21 |

Keep judgments short. One sentence per flag. No rewrites, no suggestions, no revisions.
```

- [ ] **Step 5: Self-review checklist**

Read both files back and confirm, one item at a time:

1. `output-styles/voice-author.md` lines 1-7 (YAML frontmatter) are byte-for-byte unchanged —
   `name`, `description`, `keep-coding-instructions`, `force-for-plugin` all still present with
   their original values.
2. voice-author.md's "Operating rules" now has exactly 8 numbered rules, 1 through 8, with no
   renumbering of 1-7.
3. Rule 8's text matches Step 2's block verbatim.
4. `## Depth files` still immediately follows rule 8 — nothing else was inserted between.
5. `agents/voice-checker.md` lines 1-10 (YAML frontmatter) are byte-for-byte unchanged —
   `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`
   all still present with their original values (in particular, `skills:` still reads
   `voice-craft-reference` only — this task does NOT add `voice-contract` to it).
6. The new table row matches Step 4's block verbatim, and it is the last row before the
   "Keep judgments short." sentence — no other rows were added, removed, or reordered.
7. Run `grep -n "^[0-9]\. \*\*" output-styles/voice-author.md | head -10` and confirm rules `1.`
   through `8.` with no gaps or duplicates.
8. Run `grep -c "^|" agents/voice-checker.md` and confirm it increased by exactly 1 from before
   this task's edit (the table header + separator + 5 existing rows + 1 new row = 7 pipe-led
   lines in that table, plus 1 pipe-led line elsewhere in the file's example output blocks if
   any — read the actual grep output and reason about the count rather than assuming; the point
   is confirming exactly one row was added, not matching an exact predicted total blindly).

- [ ] **Step 6: Commit**

```bash
git add output-styles/voice-author.md agents/voice-checker.md
git commit -m "docs: close voice-author and voice-checker tell-profile coverage gap"
```
