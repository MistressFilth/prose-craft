# Voice Design Guide

How to design a voice that holds up across many drafts — grounded in the discordian voice family, the seventeen voices that ship as the plugin's worked example.

**Where this sits.** Three documents govern voice work, and they divide the labor cleanly:

- `voice-craft-reference` — the **schema**. Every key, every dimension, the front-matter order. Read it to learn what a `voice.md` may contain.
- `voice-contract` — the **operations**. Rule precedence, the depth-file walk, dial computation, inheritance, audience resolution. Read it to learn how the drafter honors a voice.
- This guide — the **design wisdom**. The patterns that survive contact with the model, the mistakes worth naming once so you skip them, and the live family as a reference you can open and read.

Read the first two for ground truth. Read this one to design well.

---

## Orientation

A voice profile is a constitution. The `voice-stylist` agent treats every rule the profile states as binding and falls back to the `literary-editor` output style wherever the profile stays silent.

Three layers carry the work:

1. **The voice profile** — `voice.md` plus optional depth files, living at `${CLAUDE_PLUGIN_DATA}/voices/<name>/`. This is where you write the constitution.
2. **The skills** — `/draft-in-voice` and the `voice-contract` it loads. They run one drafting session: read the profile, pass the brief to the stylist, run `voice_check.py` after.
3. **The agents** — `voice-composer` authors profiles (Opus), `voice-stylist` drafts and edits (Opus), `voice-checker` reports violations read-only (Sonnet).

One fact about this architecture governs every design decision below: **the stylist composes one draft at a time and remembers nothing of the drafts before it.** Each draft meets the constitution fresh. Every convergence problem in this guide traces back to that single fact, and so does every fix.

---

## The family as a worked example

The plugin ships seventeen voices under `${CLAUDE_PLUGIN_DATA}/voices/discordian-*/`. Open them; they are the clearest teacher this guide can point to.

**Shape.** One parent, `discordian-base`, and sixteen children — `deredere`, `tsundere`, `yandere`, `kuudere`, `dandere`, `kawaii`, `goth`, `fairy`, `cryptid`, `surfer`, `alien`, `bureaucratic`, `classic`, `composed`, `fnord`, `saturated`. Every child declares `base: discordian-base`. The base declares `base: null`. The tree is flat — parent and children, one level, because the schema permits exactly one.

**What the base holds.** Family infrastructure that every mood inherits: the six-axis register baseline, the diction defaults, the shared `never:` list, one `move-catalog` (`moves.md`), twenty `reference` files, one `exemplar`, the `lore_corpus` activation policy, and a permissive `audiences:` block. The base is the common ground; it produces no prose of its own.

**What a child overrides.** Read `discordian-deredere/voice.md` against the base and the override pattern is plain. Deredere keeps the base's structure but resets the register (`funny_serious` 0.7 where base sits at 0.2; `density` 0.55 where base packs to 0.65), tightens the rhythm (12-word mean, low variation, where base runs 16 words and high), shifts the diction (75% Germanic for warmth, where base holds 65%), and ships its own depth files: a `dial`, a `surface-map`, two `reference` files, and a postcard `exemplar`. Override is **by path and total** — the child's `dials/papal.md` replaces the base's entirely; a file the child omits, it inherits whole.

This is the structure to imitate. Shared infrastructure rises to a base; mood-specific calibration lives in the child.

---

## Two models for voice inventory

A voice needs a way to reach for the right words. The plugin supports two, and the choice shapes everything downstream. Decide early.

### Model A — the phrase pool (banks and wells)

The schema-native path. A voice ships phrase lists as depth files the drafter draws from:

- A **bank** backs one lexicon field (`lexicon.pet_phrases`, say). It declares `selection:` (`random` / `random-dedup` / `weighted-dedup`) and `exhaustion:` (`cycle` / `vice-prefix` / `error`). The drafter samples per those rules; `voice_check.py` unions banked phrases with inline ones through `effective_diction()` before its density pass, so the checker sees the same pool the drafter draws from.
- A **well** is a register vocabulary pool feeding the texture moves it names in `serves:`. When it also declares `gated_by:`, its vocabulary enters the draft's working set only once the effective dial clears that threshold.

Use this model when the voice has signature phrases that should **rotate** — variety across drafts, governed mechanically.

### Model B — activation (lore_corpus and voice_persona)

The path the discordian family actually took. Instead of phrase pools, the voice names the training-data territory the drafter should activate, then trusts it to improvise against the artifact's own facts. The base voice states the policy plainly:

> "The drafter ACTIVATES training-data territory rather than selecting from phrase pools. There are no banks and no wells in this voice family."

Two keys carry it, both read by the agents as prose (they are freeform front-matter, outside the checked schema — `voice_check.py` does not parse them):

- **`voice_persona:`** — one paragraph naming the author or register whose engine the voice channels. It is a training-data prior, not an instruction set. "Channel Mary Ruefle's notes plus the warmer corners of Annie Dillard" activates more than a page of rules (see G18).
- **`lore_corpus:`** — the family's structured territory map: named registers, source corpora, and the improvisation constraints that keep activation from sliding into retrieval.

Use this model when the voice's identity lives in **register** rather than in any fixed set of phrases — when you want the drafter inventing fresh language each time, not cycling a list.

### Choosing

| Your situation | Model |
|---|---|
| The voice has 1-3 signature phrases that SHOULD recur (a sonnet's 14 lines, tsundere's `Tch.`) | Inline `lexicon.*` — recurrence is the point |
| The voice has a pool of phrases that should rotate without repeating back-to-back | **Model A** — a `bank` with `selection: random-dedup`, `exhaustion: cycle` |
| The voice's character lives in a register the model already knows deeply | **Model B** — `voice_persona` + `lore_corpus`, improvise every beat |

The models compose: a voice can activate a register through `voice_persona` and still bank one rotating field. Both are legitimate; the discordian family simply found activation carried its moods better than any phrase pool could.

---

## Audience ceilings

A voice answers *who is speaking*. An audience answers *who is listening*. The two are perpendicular, and the plugin keeps them so.

This is the part of the architecture that moved. Audience configuration now lives **inline** in each `voice.md`, as a top-level `audiences:` block in the front-matter — the same place `diction:` and `never:` live. There is no central registry to consult, no separate file to keep in sync.

### How it reads

The block maps audience names to ceilings, and every ceiling is enforced by **subtraction**: it takes admissions away from what the register would otherwise grant; it never adds.

Here is deredere's real block, lightly trimmed:

```yaml
audiences:
  rationale: |-
    Deredere is the warmest voice; the postcard form is intimate.
    Team admits a narrow stripe; external closes entirely.
  private:
    severity_ceiling: 5              # the-no-audience-declared default
    dial_ceiling: 1.0
    never_extend: []
    surface_filter: null
  team:
    severity_ceiling: 2              # internal teammate reading for the claim
    dial_ceiling: 1.0
    never_extend:
      - postcard salutations ("Hi! It's me, Eris")
      - XOXO closes
    surface_filter:
      admit: [team_friday_note, encouragement_brief, retro_with_warmth]
      close: [postcard, love_letter, gratitude_note]
  external:
    closed: true                    # public / cross-org / customer-facing
    reason: |-
      Terms of affection render as inappropriate intimacy
      outside the writer's own work.
```

### The fields

| Field | What it does |
|---|---|
| `severity_ceiling: <0..5>` | Caps severity-keyed phrasing. A ceiling of 2 forbids severity-3-and-up, even when the draft asks for more. |
| `dial_ceiling: <0.0..1.0>` | Caps the effective dial. At `0.0` the voice's own register closes and `fallback_voice` takes over. |
| `fallback_voice: <name>` | The voice to defer to when `dial_ceiling` hits `0.0` — typically `literary-editor`. `null` means the voice declines to yield. |
| `never_extend: [rule...]` | Extra never-list entries for this audience, enforced exactly like the voice's own `never:`. |
| `surface_filter:` | `{ admit: [...], close: [...] }` over surface names; admit-list whitelists, close-list blacklists, the string `'*'` closes all, `null` disengages. |
| `closed: true` + `reason:` | The voice refuses this audience; the drafter bails and reports the reason. |

### Resolution

At draft time, before any rule fires: read the draft's `audience: <name>` front-matter; default to `private` when absent; look up `audiences.<name>` in the profile; apply its ceiling. When the block is missing or omits the name, the drafter treats the audience as `private` — full register, the voice as designed. The fallback is total and terminating: every voice resolves to a defined ceiling without consulting anything outside itself.

`/compose-voice` and `/import-voice` ship the three starter audiences (`private`, `team`, `external`) from the template. Tighten `team` and `external` per voice with `/refine-voice`; close either with `closed: true` and a `reason:` when the voice's affect toward that reader would read as performative. The full procedure lives in `voice-contract` § "Audience resolution."

---

## The four-failure-mode opener discipline

This is the load-bearing pattern. Any voice that produces a recurring artifact form — postcards, memos, dispatches, decrees, retros — needs it at the opener, because the opener is where the model's convergence shows first and worst.

### The problem it solves

Close one level of repetition and the model finds the next. The deredere voice was tested across four rounds, and the ladder it climbed is the clearest evidence in the project:

| Round | What converged at the greeting |
|---|---|
| 1 (canonical phrase present) | The literal phrase `Hi! It's me, Eris.` — 5 of 6 drafts |
| 2 (canonical removed) | A noun-slot frame: `Sweetest <noun>,` — 5 of 6 |
| 3 (noun-slot named) | A catch-all warmth-frame: `Look at you, ...` — 4 of 6 |
| 4 (catch-all named) | A speaker-act frame: `I <verb> <to-you>` — 4 of 6 |

Each fix worked, and each pushed the convergence one rung more abstract. The ladder does not terminate inside the constitution. So you name all four rungs at once, at design time, and skip the iteration.

### The four modes, in escalating severity

1. **Verbatim retrieval.** Two openers share a literal phrase — `<adjective> <noun>,` filled differently each time. The slot varies; the frame recurs.
2. **Family-pattern retrieval.** Two openers share a general-purpose frame that does the opener's structural work without naming this draft's occasion. The slot has widened; the discipline is identical.
3. **Catch-all-frame retrieval.** Two openers share a general-purpose frame that does the opener's structural work without naming this draft's occasion. The slot has widened; the discipline is identical. Diagnostic: *would this same frame open a different artifact about a different subject?*
4. **Form-dropping.** The opener is body narration — a date-line, a "you did X" sentence — and the form's required opening move is simply gone.

State the structural requirement **first and in bold** (`**Every postcard opens with a greeting.**`), define what counts as body narration with two or three concrete examples, then list the four modes. The full authoring template lives in `voice-craft-reference` § "Structure shape: opener discipline"; `discordian-deredere/voice.md` ships it in production form.

### Envelopes and latitude

Some voices fix a structure at the opener that the discipline must operate *within*, not erase. Name it explicitly:

- **dandere** — a progressive rhythm shape (terse → fuller → full-sentence close). The discipline governs the phrase; the rhythm is fixed.
- **tsundere** — a sharp-dismissal-into-technical-care pivot. The discipline governs the phrase inside the pivot; the pivot is fixed.
- **yandere** — a sweet/fury bimodality. The discipline governs both the choice among them and the composition within the chosen one.
- **classic** (The Pope) — four canonical opener forms. The discipline governs both the choice among them and the composition within the chosen one.

When your voice has a fixed envelope or multiple canonical forms, write the preserve-statement into `structure.opening:` so the next reader knows the latitude is deliberate, not a hole.

---

## Texture and the strip test

Strong prose in these voices carries texture — small structural moves that do emotional work. The base voice's `moves.md` catalogs them and sets density floors the checker reads:

```yaml
kind: move-catalog
density_rule: one work per move; distinct-work stacking is ok and lands well; restate-stacking falls flat
load_bearing:
  - TEX-11
density_floor: 3
load_bearing_floor: 1
density_ceiling: 10          # at most this many TEX moves per 1k words
strip_test_pass_rate: 0.7    # >=70% of deployed moves must pass the strip test
```

`voice_check.py` counts candidates for four shapes — **TEX-1** (the em-dash aside), **TEX-7** (the terminal triplet, "X, Y, and Z"), **TEX-8** (the anaphoric build, "not this, not that, but the thing itself"), and **TEX-9** (the aphoristic close, a short sentence after a long one) — then asks the harder question with three diagnostics:

- **The strip test.** Remove the sentence. If a literally-true claim about the subject still lands, the sentence was decoration. If the draft loses something true, it was load-bearing. The checker reports a `strip_test_pass_rate`; the floor above wants 0.7.
- **Bold overlap.** Cosmic register belongs on small subjects, not on the document's main claim — which earns the bold. A textured sentence sitting inside a bold span is a near-certain misplacement.
- **Brief overlap.** Texture that merely re-says the brief's own vocabulary is annotation, not invention.

These counts feed your judgment; they do not gate the draft. The strip test is a writer's diagnostic whose *findings* belong in the constitution — name the decoration patterns your voice is prone to in its `never:` list or its exemplar's failure modes.

---

## Gotcha catalog

Each entry names a mistake and the fix that held.

### G1 — The constitution cannot solve cross-draft convergence alone

The stylist sees one draft and no others. Each rule you add closes one level of repetition; the model finds the level above. Apply the four-failure-mode discipline once, completely, at design time. Past that, the remaining convergence is either acceptable voice signature (ship it) or it needs the skill layer (see "When to extend"). Patching the constitution past round four does not converge.

### G2 — Listing example phrases seeds them

Put `"Sweetest one,"` in `pet_phrases` to convey the register and every draft reaches for it. The model reads inline examples as a pool to retrieve, not a register to describe. **Describe the register; do not name the phrases.** When phrases must rotate, ship them in a `bank` with `random-dedup` (Model A) or activate the register through `lore_corpus` (Model B). The honest exception is a form-fixed signature — `Status: nominal.` for kuudere — which recurs by design.

### G3-G5 — The convergence ladder

Closing the verbatim phrase produces a noun-slot frame (`Sweetest <noun>,`). Closing that produces a catch-all frame (`Look at you, ...`). Closing *that* produces a speaker-act frame (`I came over to tell you ...`). Each rung is more abstract; the discipline is the same. Name all the rungs your voice is prone to at design time. The diagnostic that catches every rung: *would this frame open a different artifact about a different subject?*

### G6 — Form-dropping is invisible until you require the form

Remove the canonical greeting and the next batch opens with body narration — the greeting form vanishes entirely. State the requirement explicitly and in bold before you name what to avoid. When something is non-negotiable, say so; the model honors stated rules and reasonably fills silence.

### G7 — The unicode em-dash glyph leaks through `sed` rewrites

A never-rule that *shows* the forbidden `—` glyph defeats itself the moment a global `sed 's/—/--/g'` rewrites the rule's own text. **Describe the glyph, do not show it:** "Use of the unicode em-dash glyph. Always render as two hyphens (`--`)." To audit, grep for the glyph excluding the rule line.

### G8 — `grep -F` on a YAML block scalar fails across line breaks

A `|` block scalar preserves newlines, so an authored phrase can wrap across two lines and a line-oriented `grep` returns zero even though the text is present. Trust the harness's file-state tracking after `Edit`/`Write`; when you must verify, read the file or flatten the scalar with `awk` first.

### G9 — The stylist receives no prior-draft context

`/draft-in-voice` passes one brief; it never globs sibling drafts, and `voice_check.py` reads one file. Within a session, bank rotation (`random-dedup`) holds. Across sessions, it does not — that is genuinely net-new architecture (glob prior drafts, extract the recurring beat, pass it as an anti-pattern). Do not expect the voice profile alone to rotate across invocations.

### G10 — Banks are positive pools; there is no anti-bank

The nine `DepthKind`s are all positive — pools to draw from, not pools to avoid. For permanent prohibitions, use `lexicon.taboo_phrases`, which the checker flags. A *dynamic* anti-bank — phrases auto-collected from prior drafts — needs the skill-layer work in G9.

### G11 — Inheritance is single-level; promote shared infrastructure to the base

A child's `base:` names exactly one parent, and that parent's `base:` is null. When two siblings need the same move-catalog or reference, promote it to the common ancestor. The discordian family did exactly this: the TEX move-catalog, the Principia and koan references, and the lore-corpus policy all live in `discordian-base`, so sixteen children inherit them through one level.

### G12 — Bank rotation is session-scoped

`selection: random-dedup` deduplicates within one drafting session and forgets when the dispatch ends. It is agent judgment, not persistent runtime state. For across-session rotation, see G9.

### G13 — Iterating without a clean baseline buries the signal

Edit, re-run, and you cannot tell whether your edit helped or variance did. Run a fixed set of 5-6 briefs each round, in fresh agent contexts, with explicit instruction not to read sibling drafts, and track results in a per-round table. Back up the voice directory before each change (G20).

### G14 — Iteration loops asymptote; stop at round four

Past round four you are measuring the model's training-data prior on the register, which the constitution cannot enumerate its way around. Stop unless the new pattern is qualitatively different — a loss of recognizability, not just another frame. Frame the round-four result as a decision: signature (ship) or defect (extend the architecture).

### G15 — The strip test diagnoses decoration

Strip a sentence; if a true claim about the subject survives elsewhere, the sentence was performing voice rather than carrying it. Name the decoration patterns your voice is prone to — "imagery deployed without occasion" — in the never-list or the exemplar.

### G16 — Recognizability lives in register, not phrases

Deredere's round-2 drafts were unmistakably deredere with every canonical phrase removed: the warmth, the present-tense intimate address, the brave-attempt frame carried the identity. What carries a voice: diction tilt, rhythm, structural beats, the writer-reader relationship. What does not: any specific phrase. Describe register; prescribe failure modes.

### G17 — The exemplar is a register-anchor, not a template

Ship a finished sample and drafts match its structure beat for beat. Ship a **register-anchor** instead: name the training-data territories the drafter activates, the placement principle, and the artifact-specific failure modes — and no finished prose. The family rewrote all sixteen exemplars to this shape and the convergence dissolved. Template in `voice-craft-reference` § "Exemplar shape."

### G18 — `voice_persona` is a prior, not an instruction set

A long persona that reads like directions ("write like X, never do Y") produces flat drafts that hit the rules and miss the character. A persona that names a literary register ("Channel Robert Anton Wilson's cosmic-stakes-on-routine-operations register") activates a richer slice of the model's prior. Cite authors, works, idioms, eras. Leave the constraints to `never:` and `diction.preferred:`.

### G19 — Deredere is the canonical worked example

To see the discipline in production, read in order:

1. `${CLAUDE_PLUGIN_DATA}/voices/discordian-deredere/voice.md` — the `structure.opening:` escalator with its preserved register description.
2. `${CLAUDE_PLUGIN_DATA}/voices/discordian-deredere/exemplars/postcard.md` — the register-anchor with the matching failure-mode list.

Deredere was the test subject for all four rounds; the other fifteen voices received the discipline as a one-shot rollout. Author it from the start and your voice skips the iteration entirely.

### G20 — Back up before every voice change

Voice editing is iterative and rollback is cheap. Before each change, copy the voice directory to a timestamped sibling under `${CLAUDE_PLUGIN_DATA}/voices/.backups/<timestamp>-<change-name>/`. Recover with a reverse copy. The family's iteration accumulated a backup per state change, and every one of them earned its keep at least once.

### G21 — Self-description is not evidence of tell-profile

A voice's own declared register axes do not predict its measured machine-tell behavior — this has been shown twice, on two different questions, for the same voice (F4, F16). Direction can flip by genre for the same voice on the same channel (F5), and a voice's two density channels can be oppositely genre-sensitive within itself (F14). A design note or dialogue answer that says "this voice de-machines" or "this voice sounds more human" is not a well-formed claim unless it names both the genre and the channel it was measured on — and even qualified, self-report is not the measurement. See `workbench/reinhart/FINDINGS.md` F4/F5/F14/F16 for the evidence trail.

---

## Authoring checklist

Run this when designing a voice from scratch.

1. **Name the primary surface and its opener form.** What artifact does this voice produce by default? One opener form, several, or a fixed envelope?
2. **Choose the inventory model.** Phrase pools (Model A) or activation (Model B)? Author `voice_persona` as a register-anchor either way — cite registers, authors, idioms; name the writer-reader relationship.
3. **Set all six `register:` axes.** `funny_serious`, `formal_casual`, `respectful_irreverent`, `enthusiastic_matter_of_fact`, `certainty`, `density`. Leave none null. Prefer mid-range unless the voice genuinely lives at an extreme.
4. **Set `diction:`.** The Germanic/Latinate balance, the `germanic_for:` and `latinate_for:` contexts, the `banned:` list, the `preferred:` substitutions. Inherit `microsoft` or `gov-uk` when they fit.
5. **Set `rhythm:`.** Mean sentence length, variation, paragraph shape, one-sentence-paragraph policy, and the `forbidden_patterns:` that break the voice.
6. **Set `structure:`** — the load-bearing block. In `opening:`, state the structural requirement first, then the four failure modes (verbatim → noun-slot → catch-all → form-drop), then define body narration. Mirror the shape in `closing:` when the close converges too.
7. **Set `never:`.** Universal prohibitions first (render the em-dash rule by description, per G7), then voice-specific ones. Use structured entries — `{ id, rule, detection }` with a `string:` added for `detection: mechanical` — when the checker should catch them.
8. **Write the `audiences:` block.** Keep `private` at full register. Tighten `team` and `external` to fit how this voice carries outward; close an audience with `closed: true` + `reason:` when its affect would read as performative.
9. **Author the primary exemplar as a register-anchor.** No finished prose; the four-failure-mode list; the placement principle (G17).
10. **Set the `depth:` manifest.** Register each depth file with its `kind`. The family uses five: `dial`, `surface-map`, `move-catalog`, `reference`, `exemplar`. Banks and wells (Model A) are available when you need rotating phrase pools.
11. **Run `/show-voice <name>`** to confirm the profile renders without schema error.
12. **Run a 6-draft test batch** against varied briefs in fresh agent contexts. Audit: opener present in all six (form-drop)? Any literal recurrence (verbatim)? Any frame recurrence (family-pattern, catch-all)? Voice recognizable throughout?
13. **If the audit shows convergence**, confirm the constitution names the level it converges at. Named already → you have hit signature-or-extend (G14). Unnamed → add the failure mode and re-run.
14. **Stop at round four** (G14).
15. **Document the voice's quirks** — fixed envelope, multi-form latitude — directly in `voice.md` so the next reader sees the latitude is intentional.

---

## When to extend the architecture

The constitution layer has a ceiling. These signals mean you have reached it, and the fix lives in the skill or schema layer rather than another rule:

| Signal | Extension |
|---|---|
| Round 4+ keeps producing a fresh family pattern | Cross-draft awareness in `/draft-in-voice`: glob prior drafts, pass their openers as anti-patterns |
| You want to forbid "phrases used in the last N drafts" | A dynamic anti-bank: a prior-draft log the stylist reads as anti-pattern |
| You want `random-dedup` to span sessions | Persistent per-voice dedup state a skill reads at dispatch |
| Shared infrastructure that single-level inheritance cannot promote | More aggressive promotion to the base, or a second inheritance level |
| The checker should detect frame-level recurrence | Pattern detection extended in `voice_check.py` |

Pursue these when a writer's real experience proves the ceiling, not before. The deredere iteration reached the ceiling at round four and named cross-draft awareness as the next step — but the reading experience said the residual recurrence read as signature, so the family shipped without the extension. Do the same calculus for your voice.

---

## When to add to this guide

Add a section when you hit a failure mode the gotchas do not name, discover an architectural constraint the docs miss, design a voice with a structural shape worth showing as an example, or extend the architecture in a way that changes how voices are designed. The aim holds: future writers should inherit the lessons rather than relearn them.

---

## See also

- `prose/skills/voice-craft-reference/SKILL.md` — the schema: D1-D10, the six-axis register, the depth-kind list, the exemplar and lexicon shapes.
- `prose/skills/voice-contract/SKILL.md` — the operations: rule precedence, the depth-file walk, dial computation, base inheritance, audience resolution.
- `prose/scripts/voice_io.py` — the `Voice` model, the `DepthKind` literal, the override chain.
- `prose/scripts/voice_check.py` — the mechanical, statistical, and TEX-shape checks; the `effective_diction()` bank union.
- `prose/agents/voice-stylist.md`, `voice-composer.md`, `voice-checker.md` — the agent definitions and their drafting protocols.
- `${CLAUDE_PLUGIN_DATA}/voices/discordian-*/` — the seventeen-voice family this guide draws its examples from; `discordian-base` for inheritance, `discordian-deredere` for the opener discipline.

