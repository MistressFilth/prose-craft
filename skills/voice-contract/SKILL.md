---
name: voice-contract
description: Operational contract for drafting and editing in a designed voice. Owns the operating rules, voice rule precedence, depth-file protocol (with per-kind deployment notes and bank selection/exhaustion discipline), effective dial computation, base inheritance, and lexicon inheritance. Loaded by voice-author (output style), voice-stylist, voice-checker, and voice-composer (subagents) via the `skills:` frontmatter array. Sole source of truth — every consumer reads this file rather than holding its own copy.
user-invocable: false

---

# Voice contract

The voice profile is constitution within the rules it states; literary-editor principles apply only as fallback.

This skill is the **operational** ground truth — how to honor the voice when drafting and editing. The voice schema (front-matter shape, the D1-D10 dimensions, file layout) lives in `voice-craft-reference` and is loaded separately. Use both: schema first, then this contract for operational discipline.

## Operating rules

1. **When the document declares `voice: <name>` in front-matter,** read `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md`. That profile governs.
2. **Honor every explicit rule in the profile.** Banned words stay out. Preferred substitutions land. Target ranges (`rhythm.target_mean_sentence`, `paragraph_shape`) are met.
3. **Honor the prose body** (D10) as guidance for everything outside the YAML rule list.
4. **When the profile is silent on a dimension,** defer to `literary-editor`. The voice's `fallbacks.when_voice_silent` field names this fallback explicitly.
5. **Resolve the audience before drafting.** Read the draft's `audience: <name>` front-matter; default to `private`. Apply the audience ceiling per § "Audience resolution" below. The ceiling can take admissions away from what the dial would otherwise grant; it cannot add.
6. **After each pass, name the rules touched.** Print a short change log: which voice rules were tightest, which fell back to literary-editor, which are agent-required (interpretive). Name the resolved audience and any closures it applied.

## Voice rule precedence

When you have to choose between conflicting guidance, follow this order from highest to lowest precedence:

1. **Voice's `never:` blocks** — absolute. A `never:` rule is non-negotiable.
2. **Voice's structured rulesets** — `diction.banned`, `lexicon.taboo_phrases`, `rhythm.forbidden_patterns`, etc. Honor exactly.
3. **Voice's targets** — `rhythm.target_mean_sentence`, `register.*` values, `diction.default_balance`. Aim for; small deviations are fine when they serve clarity.
4. **Voice's prose body** — guidance for cases the YAML doesn't cover.
5. **Literary-editor output style** — fallback for silent dimensions.
6. **Universal-prose principles** — Strunk-style "use specific words, prefer short sentences, vary length" — what `prose_analyzer.py` measures. Lowest precedence; the voice can override any of these.

When (1) or (2) is violated by writing the prose the writer's brief asks for, write the prose anyway and flag the override in the change log: "Brief asked for X; voice says never X; chose to honor brief; flagging."

## Reading and using the voice

The voice profile loads as YAML. Treat each block as a directive:

| Block | What you do with it |
|---|---|
| `purpose` | Frames the kind of writing you produce |
| `audience` | Anchors who you're addressing — register and diction calibrate to them |
| `register.*` | Six 0-1 values you aim for. Nudge each axis toward its contrast pole (formal-casual transformations; contractions, register softening, hedging additions) tells you how to dial each axis |
| `diction.default_balance` | Saxon vs. Romance balance |
| `diction.banned` | Hard avoid; never write these words |
| `diction.preferred` | Substitution table; use `instead_of` instead of using the substitution's `use` value |
| `diction.inherit_lexicons` | Load each named lexicon from `${CLAUDE_PLUGIN_DATA}/voices/_lexicons/<name>.yaml` and treat its substitutions as additions to the voice's own |
| `rhythm.*` | Sentence-length and variation targets. `forbidden_patterns` is hard |
| `syntax.*` | Punctuation policy; the writer set each value |
| `lexicon.pet_phrases` | Use sparingly, where they fit naturally; force nothing |
| `lexicon.taboo_phrases` | Hard avoid |
| `lexicon.characteristic_openers/closers` | Patterns to lean into when shaping sentences |
| `structure.*` | How pieces in this voice begin, end, and connect |
| `never.*` | Absolute prohibitions |
| `fallbacks` | What governs when the voice is silent |
| `base` | Names a parent voice to inherit from. Single-level only; the parent's `base` is null or absent. Load the parent's `voice.md` and depth files first, then apply this voice's overrides per § "Base inheritance" |
| `depth` | Manifest of depth files this voice ships. Each entry has `path` (relative to the voice directory), `kind` (one of the eight depth kinds), and optional `gated_by` (a dial-file path). Walk it after reading `voice.md` and `INDEX.md`; dispatch on `kind` per § "Per-kind protocols" |

## Depth files

A simple voice ships one `voice.md`. A deep voice ships `voice.md` plus depth files alongside it under `${CLAUDE_PLUGIN_DATA}/voices/<name>/`. When `voice.md` declares either `base:` or `depth:`, follow this procedure at draft time:

1. **Read `voice.md` first.** Load both YAML rules and prose body as usual.
2. **Read `INDEX.md` next when present.** The index lists every depth file with its kind, purpose, and entry count. Read it before walking the manifest so you know what is there.
3. **Follow the base chain when `base:` is set.** Read the parent voice at `${CLAUDE_PLUGIN_DATA}/voices/<parent-name>/voice.md` and its depth files before reading the child's depth files. Single-level inheritance only — the parent's `base` is null or absent. Apply override-by-path per § "Base inheritance" below.
4. **Read each `depth:` entry by `kind`.** For each entry in the manifest, read the sibling file at its declared path, not by load order; read what you need when you need it. Order per § "Per-kind protocols" below for documentation.
5. **Compute the effective dial from the surface and any draft override.** When the voice ships a `kind: surface_map` depth file, read its calibration table. When the draft's front-matter sets `surface:` or `voice_tolerance:`, look up the mapped value as the effective dial. When no override is set, default to `default:`.
6. **Admit or refuse `gated_by:` depth entries against the effective dial.** When a depth entry (typically a well) declares `gated_by: dials/<dial>.md`, look up the gating threshold in the named dial's calibration table. When the effective dial clears the threshold, admit the entry's content into the draft's working set. Otherwise treat that depth entry as closed for this draft.

## Per-kind protocols

Each depth kind has its own front-matter shape and its own draft-time discipline. Eight kinds are admitted; new kinds require a follow-up redesign.

| Kind | What you do with it |
|---|---|
| `bank` | A phrase pool backing a single `field:` path (e.g. `lexicon.pet_phrases`). The bank is the source of truth for that field once it exists; the inline list at that path is empty by design. Sample per `selection:` & `exhaustion:` on full traversal. The `flavor:` field is a compose-time cue — skip it at draft time. |
| `well` | Vocabulary source for one or more named texture waves declared in `serves:` (e.g. `serves: TEX-1`). Read the well's deployment note (the prose body) before drawing — it tells you when the well is appropriate to the artifact. When `gated_by:` is set, admit the well only when the effective dial clears the threshold. |
| `move-catalog` | Repertoire of named sentence-level moves with definitions and examples. Obey the catalog's `density_rule:` (e.g. "no more than one move per sentence"). Every move named in `load_bearing:` should appear at least once in any draft of meaningful length — its absence compromises the voice. |
| `character` | Self-contained mood spec (`identity:`, `palette:`, vocabulary overrides table, deep-lore adaptations, and an output-style voice section). When the brief invokes the character (or the voice ships this character for the rest of the voice), apply its vocabulary substitutions, frame, and address style on top of the rest of the voice. |
| `reference` | Axis-by-variant tables, comparison matrices, severity scaling, override chains, etc. Treatment depends on the reference's declared `usage:` field (front-matter or first section). `usage: binding` (or absent) -- read as ground truth for whatever dimension the table documents (severity tables, dial calibrations, override chains, etc.). `usage: illustrative` -- register exemplars and lore samples that the drafter MAY consult or ignore, never a phrase pool, never a constraint that limits the drafter's improvisation. When `usage:` is absent, default to binding (preserves prior behavior). |
| `index` | The manifest itself. Read it first at the table of contents (see Depth files step 2). |
| `exemplar` | A **register-anchor**: a pre-draft read artifact that names the training-data territories the drafter activates for this surface and the placement principle that anchors the artifact's specific facts. Ships no finished prose; the drafter improvises every beat against this draft's occasion. The four failure modes specific to the artifact-type (verbatim retrieval, family-pattern retrieval, catch-all-frame retrieval, form-dropping at the opener). When the exemplar carries a register-translation-note, honor the register shift for the target surface. The earlier "finished piece, absorb shape" interpretation produced drafts that fit the exemplar's specific structure beat-for-beat; the register-anchor shape replaces it. See `voice-craft-reference` § "Exemplar shape" for the authoring template and `prose/docs/voice-design-guide.md` G17 for the rationale. |

When a voice ships a depth entry whose `kind` is unfamiliar, treat it as `reference` for reading purposes and surface the unknown kind in the change log.

## Bank selection and exhaustion discipline

Banks declare a `selection:` field and an `exhaustion:` field. Honor both at draft time.

**Selection** — how to draw from the bank:

- **`selection: random`** — pick any entry freely; track no dedup state.
- **`selection: random-dedup`** — within a single drafting session, reuse an entry only after every other entry in the bank has been used at least once. Track which entries you have drawn within the session and exclude them from each subsequent draw.
- **`selection: weighted-dedup`** — same dedup constraint as `random-dedup`, weighted by any per-entry weight declared in the bank body. When the bank declares no weights, treat it as `random-dedup`.

**Exhaustion** — what to do when every entry has been drawn:

- **`exhaustion: cycle`** — prepend a cycle marker (e.g. `[cycle 2]`) to signal a new pass, then restart from the full entry set.
- **`exhaustion: vice-prefix`** — restart from the full entry set with a prefix marker (e.g. `Vice-`) attached to each reused entry. This is the role-bank variant — when out of unique titles, prepend `Vice-` to the next reuse.
- **`exhaustion: error`** — stop drafting and surface the bank's exhaustion to the writer in the change log. A bank with `exhaustion: error` should remain unexhausted within one session.

The mechanical floor — the per-1k-word density check in `voice_check.py` — still applies. The selection and exhaustion rules layer on top: they govern which entries you draw, leaving the per-thousand-word density target separate. `voice_check.py` unions inline phrases with banked phrases via `effective_diction()` before running the density check, so the density target sees the full pool, not just what's drafting.

For inline phrase fields under `lexicon.*`, `voice_check.py` walks the same chain: when the child has a bank for a field, the bank wins; when the child has no bank for the field, union with the parent's banked phrases (when any) with the child's inline phrases. Consume the unioned set; recomputing it is unnecessary.

### Bank-from-start guidance

From the start: ship the bank, encode `selection: random-dedup` in its front-matter, and let the stylist's bank-protocol discipline carry the rotation.

The honest exception is form-fixed phrases (1-3 entries that ARE the voice's signature and SHOULD recur), like a sonnet's 14 lines or tsundere's `Tch.`. These stay inline; the recurrence is the point.

See `voice-craft-reference` § "Lexicon shape: form vs. rotation" and `prose/docs/voice-design-guide.md` G2/G12/G16.

## Effective dial

When the voice ships a `dial` and a `surface_map`, compute the effective dial each draft:

1. Start at the dial's `default:`.
2. When the brief names an artifact type and the surface map lists it, take the mapped value.
3. When the draft's front-matter sets `surface:` or `voice_tolerance:`, that override wins over the surface map.

Then admit or refuse every `gated_by:` depth entry against the effective dial. When the dial clears the gating threshold, draw from that depth entry. Otherwise treat it as closed for this draft.

## Base inheritance

When `voice.md` declares `base: <parent>`, read the parent voice and its depth files first, then apply the child voice's overrides. Single-level only — the parent's `base` is null or absent.

Override is by relative path. Override is total; nothing merges.

| Situation | Behavior |
|---|---|
| Parent has `banks/pet_phrases.md`, child has `banks/pet_phrases.md` | Child's bank wins entirely. Draw only from the child's bank. |
| Parent has `banks/pet_phrases.md`, child has no file at that path | Child inherits the parent's bank. Draw from the parent's bank as if it were the child's own. |
| Child has `banks/local_only.md`, parent has no file at that path | Child contributes a new file. The parent contributes nothing at that path. |

Inline phrase fields union with banked phrases the same way: when the child has a bank for a field, the bank wins; when the child has no bank for the field, the parent's banked phrases contribute. `voice_check.py` performs this union via `effective_diction()`; consume the unioned set.

Single-level only. Discovering a need for three levels is a follow-up redesign, not a draft-time accommodation.

## Inheritance: lexicons

When `diction.inherit_lexicons` lists a lexicon, load `${CLAUDE_PLUGIN_ROOT}/voices/_lexicons/<name>.yaml` and treat its `banned` and `preferred` entries as additions — both apply when both are declared. The voice's own entries override the lexicon's. Lexicon inheritance is independent of `base:` chain inheritance.

## Audience resolution

Voice answers "who is speaking?" Audience answers "who is listening?" The two are perpendicular. The dial encodes register intensity; the audience encodes which surfaces and which moves carry safely to the listener. A dial-1.0 dandere is the warmest dandere; a dial-1.0 dandere with `audience: team` is still warm but its postcard form has closed. The voice does not change. The dial does not move. What the audience will permit itself to render does.

The audience ceiling is enforced as **subtraction only**: the audience can take admissions away from what the dial would otherwise grant; it cannot add. A `severity_ceiling: 3` means "no severity-4 or severity-5 phrasing in this draft," even when the surface map points to it." A `dial_ceiling: 0.0` means "fall back to the named `fallback_voice` entirely."

### Resolution procedure

At draft time, before any rule fires:

1. **Read draft front-matter `audience: <name>`.** When absent, default to `private`. The default preserves the voice as designed (full register, severity ceiling 5, no closures).
2. **Read the voice's own `audiences:` block.** The block lives in the voice profile front-matter (`voice.md`), already loaded as constitution. Look up `audiences.<name>` for this draft's audience.
3. **Apply the `private` fallback when the lookup misses.** When the voice declares no `audiences:` block, or the block omits the requested audience name, treat the audience as `private`: full register, severity ceiling 5, dial ceiling 1.0, no `surface_filter`. The fallback is total and terminating — every voice resolves to a defined ceiling without consulting any central registry.
4. **Honor `closed: true`.** When the resolved entry declares `closed: true`, the voice does not admit drafts at this audience. Bail with a clear error, name the `reason:`, and suggest either a different audience or a different voice.
5. **Apply the resolved ceiling.** Five fields, each enforced as subtraction:

| Field | Behavior |
|---|---|
| `severity_ceiling: <0..5>` | Hard cap on the severity row used for the close (and any other severity-keyed phrasing). When the draft declares `severity: 5` and the audience ceiling is `3`, draft at severity 3 and surface the cap in the change log. |
| `dial_ceiling: <0.0..1.0>` | Hard cap on the effective dial. When the ceiling is below the effective dial, clamp to the ceiling. When the ceiling is `0.0`, the cosmic register closes entirely; engage `fallback_voice`. |
| `fallback_voice: <name>` | Names the voice (typically `literary-editor`) to defer to when the cosmic register has been closed by `dial_ceiling: 0.0`. The voice's diction lexicon (banned/preferred) still binds; the texture machine does not. When `null`, the voice does not yield. |
| `never_extend: [<rule>,...]` | Additional never-list entries layered on top of the voice's own. Each entry is enforced exactly like a `voice.never:` entry, as an absolute prohibition for this draft. |
| `surface_filter: { admit: [...], closes: [...] }` | Whitelist/blacklist over surface names. When `admit` is set, ONLY listed surfaces admit. When `closes` is set, those surfaces close. When both are set, both rules apply (admit first, then close). When `surface_filter` is `null` (string form, not an object), all surfaces close. |

### Resolution interaction with the rest of the contract

- The audience ceiling applies AFTER the effective dial is computed. Compute the dial per § "Effective dial," then clamp by `dial_ceiling`. The clamped value is what governs `gated_by:` admission.
- The audience ceiling does NOT modify the voice's own `never:`, `diction.banned`, or `lexicon.taboo_phrases`. Those remain absolute regardless of audience. New entries are added as if declared inline on the voice.
- When the audience closes a surface, the surface map's other entries still apply for surface names not in the closure list. The drafter falls back to the voice's most surface-neutral form.
- The change log names the resolved audience, the ceiling source (the voice's own `audiences:` block, or the `private` fallback when the block omits the audience), and every ceiling that constrained the draft.

Each voice carries its own audience ceilings inline in `voice.md`. A voice ships the three starter audiences (`private`, `team`, `external`) from `/compose-voice` and `/import-voice`; the writer tightens `team` and `external` per voice, or closes either with `closed: true` + `reason:`. To widen or narrow a voice's audience behavior, edit that voice's `audiences:` block directly with `/refine-voice` — the ceiling travels with the voice, the way `diction` and `never:` already do.

