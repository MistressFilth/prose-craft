---
name: voice-craft-reference
description: Schema and design vocabulary for designed voices. Loaded by voice-composer, voice-stylist, and voice-checker as their reference for the voice profile structure, the six-axis register, the diction and rhythm targets, the never-list shape, and the lexicon and never-list inheritance rules.
user-invocable: false

---

# Voice-craft reference

Reference-only skill. Read by the three voice agents
(`voice-composer`, `voice-stylist`, `voice-checker`) as their schema
of record. The compose dialogue and the rule taxonomy live in the
planning workspace; this file is the runtime ground truth that
agents load.

## Voice profile schema

Every voice lives at `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md`
as a single file with YAML front-matter and an optional prose body.
Agents read and write the front-matter via `scripts/voice_io.py`
(pyyaml preserves the prose body verbatim).

Top-level keys, in fixed order:

```yaml
voice: <name>              # required; lowercase; matches directory name
version: 1                 # schema version; bump only via migrator
created: YYYY-MM-DD
updated: YYYY-MM-DD
authors: <author>
imported_from: null        # set by /import-voice; freeform string identifying the source bundle

voice_persona: <prose | null>   # optional — training-data prior the drafter activates
                            # before any rule fires. One paragraph the
                            # author/voice whose comedic or rhetorical engine
                            # this voice channels. Read by voice-stylist Step 1a
                            # before the rule corpus enters scope; re-cited at
                            # the top of Step 4a (generation phase) so it stays
                            # in working memory when the first sentence is
                            # written. Operates by directing the drafter to a
                            # richer training-data slice than a rule corpus can
                            # describe. Voices without an authorial signature
                            # to channel may omit this key — the prose body of
                            # voice.md substitutes.

purpose: <prose>            # D1 — what this voice is for
audience: <prose>           # D2 — who reads it

audiences:                  # D2.5 — per-voice audience ceilings (see § "Audience ceilings")
  private: { severity_ceiling: 5, dial_ceiling: 1.0, never_extend: [], surface_filter: null }
  team: { severity_ceiling: <0..5>, dial_ceiling: <0.0..1.0>, ... }
  external: { closed: true, reason: <prose> }  # or a full ceiling
                            # optional 'rationale: <prose>' documents why ceilings differ from default

register:                   # D3 — six axes, floats in [0, 1]
  funny_serious:              <float | null>  # 0=funny, 1=serious
  formal_casual:               <float | null>  # 0=formal, 1=casual
  respectful_irreverent:       <float | null>  # 0=respectful, 1=irreverent
  enthusiastic_matter_of_fact: <float | null>  # 0=enthusiastic, 1=matter-of-fact
  certainty:                   <float | null>  # 0=hedged, 1=declarative
  density:                     <float | null>  # 0=spacious, 1=packed

diction:                    # D4
  default_balance: <prose>            # e.g., "60% Germanic / 40% Latinate"
  germanic_for: [<context>, ...]      # contexts the voice reaches Germanic
  latinate_for: [<context>, ...]      # contexts the voice reaches Latinate
  banned: [<literal>, ...]            # word-boundary regex match
  preferred:                          # substitution pairs
    - { instead_of: <word>, use: <word>, note: <prose> }
  inherit_lexicons: [<name>, ...]     # microsoft, gov-uk

rhythm:                     # D5
  target_mean_sentence: <prose>       # e.g., "15-20 words"
  target_variation: <prose>           # e.g., "high — std dev around 11"
  paragraph_shape: <prose>            # e.g., "3-5 sentences"
  one_sentence_paragraphs: <prose>    # policy
  forbidden_patterns: [<prose>, ...]  # prefix 're:' for mechanical regex

syntax:                     # D6 — free-form policy per sub-field
  em_dashes:      <prose | null>
  colons:         <prose | null>
  semicolons:     <prose | null>
  parentheticals: <prose | null>
  fragments:      <prose | null>
  bullets:        <prose | null>
  questions:      <prose | null>

lexicon:                     # D7
  pet_phrases: [<phrase>, ...]              # 3-7 ideal
  characteristic_openers: [<phrase>, ...]
  characteristic_closers: [<phrase>, ...]
  taboo_phrases: [<phrase>, ...]             # never-use phrases

structure:                   # D8 — free-form per sub-field; see § "Structure shape" below
  opening: <prose | null>     # for any voice with a recurring artifact form
                               # the four-failure-mode escalator template
                               # (see § "Structure shape: opener discipline")
                               # is the recommended shape
  closing: <prose | null>
  transitions: <prose | null>
  emphasis: <prose | null>
  citations: <prose | null>

never:                      # D9 — list of plain strings or structured entries
                             # agent-required
  - <prose>
  - { id: <slug>, rule: <prose>, detection: <kind> }  # mechanical / statistical / agent-required
```

  license: <matrix tag>              # CC-BY-4.0 | OGL-3.0 | public-domain | training-data | NN/g-free
  citation: <prose | locator>        # specific quote, page, rule label
  date: <YYYY-MM-DD>                 # the day the preset was accepted

fallbacks:
  when_voice_silent: "literary-editor output style"
  conflict_resolution: |
    When a voice rule and a literary-editor principle conflict, the
    voice wins. Note the override in the draft's commit message.
```

After the closing `---`, an optional prose body (D10) holds the
writer's articulation of the voice — short "this voice is X" claims
with one-sentence elaborations. The body is guidance the agents
read; the YAML is what `voice_check.py` checks.

## Structure shape: opener discipline

For any voice that produces a recurring artifact form (postcards,
memos, dispatches, letters, retros, decrees, reports, transmissions —
any surface where the same artifact-type recurs across drafts), the
recommended `structure.opening:` shape is the **four-failure-mode
escalator**. This shape was developed across four iterative rounds in
the discordian voice family and applied to all 16 mood voices that
ship with the plugin. It addresses a real architectural constraint:
the `voice-stylist` agent has no cross-draft awareness, so the only
mechanism preventing rotation/family-pattern convergence at recurring
beats is what the voice profile names as a failure mode.

**Authoring template.** Use this shape in `structure.opening:` for
any voice with a recurring artifact form:

```yaml
structure:
  opening: |
    <opener-form description in this voice's register, composed for
    this draft's specific occasion. **Every <surface-name> opens
    with a <opening-move-name>.** A <opening-move-name> is a sentence
    whose primary work is <what-the-form-requires>. <Define what
    counts as body narration for this voice — 2-3 specific
    not-an-opener examples.>

    The drafter composes the <opening-move-name> for this draft. The
    register is <named-register-attributes>. The drafter draws on
    the <surface-register>'s full repertoire of <opening-territory>
    without retrieving any specific phrase or pattern.

    Four failure modes apply, in escalating severity:

    1. **Verbatim retrieval.** Two <surface-plural> whose
       <opening-moves> share a literal phrase have failed the
       discipline.
    2. **Family-pattern retrieval at the noun-slot level.** Two
       <surface-plural> whose opening-moves share a frame
       (`<example-frame>` filled differently per draft) have failed
       the discipline at one level up.
    3. **Catch-all "<voice-tinted>" frame retrieval.** Two
       <surface-plural> whose opening-moves share a general-purpose
       <voice-tinted> frame — a frame that could attach to any
       subject and does the opening-move's structural work without
       naming this draft's specific occasion — have failed the
       discipline at the next level up. <Name 2-3 specific
       catch-all frames this voice is prone to.> The diagnostic is
       the same as the noun-slot test, run on the framing rather
       than the slot: would this same frame open a different
       <surface-name> about a different subject?
    4. **Form-dropping.** A <surface-name> whose first sentence is
       body narration rather than a <opening-move-name> has lost
       the form's required opening move. <Name 2-3 specific
       body-narration openers that count as form-drop for this
       voice.>
```

**Voice-specific structural envelopes.** When the voice has a fixed
structural envelope at the opener (a rhythm shape, an affect-pivot, a
bimodal oscillation), state the envelope as preserved alongside the
four failure modes:

> "The <envelope-name> is structural and remains fixed across drafts.
> The four failure modes operate on the phrase the drafter writes
> WITHIN the <envelope-name>, not on the envelope itself."

The discordian-dandere voice (rhythm shape), discordian-tsundere voice
(affect-pivot), and discordian-yandere voice (bimodality) ship as
worked examples.

**Voice-specific multi-form latitude.** When the voice's opener has
multiple canonical forms (e.g. classic Pope: sacred warning / OOOO
code / Pope-card / cosmological subject), the four-failure-mode
discipline operates on the choice among the forms AND the composition
within the chosen form. Name the latitude explicitly so the next
reader knows it is intentional:

> "The <N> canonical opener forms remain available — the discipline
> is about the choice among them and the composition within the
> chosen form, not about narrowing the form."

For the full rationale, the empirical iteration data, and the
gotcha catalog, see `prose/docs/voice-design-guide.md` (gotchas
G3-G5 cover the convergence ladder, G17 covers the exemplar shape,
G19 names the deredere case as the canonical worked example).

## Lexicon shape: form vs. rotation


The lexicon fields (`pet_phrases`, `characteristic_openers`,
`characteristic_closers`, `taboo_phrases`) accept inline-phrase
lists, but the right shape depends on whether the phrases are «form»
(recur by design as the voice's signature, like a sonnet's 14 lines
or tsundere's `Tch.`) or «rotation» (recur by reflex when the model
retrieves them as a pool).

**For form-fixed phrases** (1-3 entries that ARE the voice's
signature and SHOULD recur): inline list in `lexicon.<field>` is
fine. The phrase is the form; recurrence is intentional.

**For rotation-prone phrases** (3+ that should be drawn from
without recurring): ship as a `kind: bank` depth file from the start
with `selection: random-dedup` and `exhaustion: cycle`. Inline lists
of 3+ entries get retrieved as a pool by the model — the writer's
intent that they should rotate is invisible in YAML alone. The bank
form encodes the rotation discipline in the depth file's front-matter
where the stylist agent honors it.

The composer's "expand-offer protocol" historically fired only at
overflow (when the inline list exceeded the 7-item ceiling). The
recommended shape now is **proactive bank-from-start** for any
lexicon field with 3+ rotation-prone entries. See
`prose/docs/voice-design-guide.md` G2 (inline example phrases get
seeded as a pool), G12 (selection protocol is session-scoped), and
G16 (voice identity lives in register, not phrases).

## Exemplar shape: register-anchor, not finished prose

The `kind: exemplar` depth file is a **register-anchor**: it names the
training-data territories the drafter activates and the placement
principle. It ships **no finished prose** that the drafter could fit
to as a template.

The earlier interpretation — `kind: exemplar` as "a finished piece
used as compositional ground truth, absorb shape" — produced drafts
that fit the exemplar's specific structure beat-for-beat. The
discordian voice family rewrote all 16 exemplars to the
register-anchor shape and the convergence pattern dissolved.

**Authoring template:**

```markdown
---
voice: <voice-name>
surface: <surface-name>
severity: 0
kind: exemplar
artifact_type: <description>
description: >
  Register-anchor for the <voice-name> voice's <surface-name> form.
  Names the training-data territories the drafter activates and the
  placement principle. Ships no finished prose; the drafter improvises
  every beat against this draft's specific occasion.
---

# What a <surface-name> sounds like in this voice

This file is a register-anchor. It does not enumerate which beats
the <surface-name> deploys, nor in what order; that decision belongs
to «this artifact»'s facts.

<2-3 paragraphs naming the voice's character at this surface — the
register's mood, what the form requires, what it does not.>

## The improvisation discipline applies to every beat

<Three paragraphs naming the verbatim/family-pattern/catch-all-frame
disciplines and the structural-requirement for the opener.>

### How to compose each beat

<Paragraph per beat — opener, body, key textures, close — naming the
register the drafter activates and the diagnostic question.>

## Registers the drafter activates

<List the named registers — the training-data territories the
drafter draws on. Cite specific authors/works/idioms when relevant.>

## Placement principle

<One paragraph: where the move attaches to the artifact's facts.>

## Failure modes specific to this artifact-type

- **Form retrieved verbatim across drafts.**
- **Form retrieved as a family pattern across drafts.**
- **Catch-all "voice-tinted" frame retrieval.**
- **Form-dropping at the opener.**
- **Inventory pattern-matched from a previous artifact.**
- <Voice-specific failure modes — decoration, register confusion,
  the never-list expansions specific to this artifact-type.>
```

The 16 register-anchor exemplars in the discordian voice family
(`/Users/MistressFilth/.claude/plugins/data/prose/voices/discordian-*/exemplars/`)
ship as worked examples. See `prose/docs/voice-design-guide.md` G17.

When a voice was bootstrapped via `/import-voice`, a sibling
`import-notes.md` in the same directory records the per-dimension
citation trail (`field: <value> ← intake §N` or `<path>:<lines>` or
`← compose-fallback`) and the full candidate lists for narrowed fields.
`import-notes.md` is a pure audit document

`voice-stylist`, and `voice-checker` do not read it. The
`imported_from:` field in the profile is the only provenance signal
those tools see.

## Six-axis register

Hybrid model: NN/g's four research-backed axes plus two locally
authored axes (`certainty`, `density`).

| Axis | 0 pole | 1 pole |
|---|---|---|
| `funny_serious` | Funny / playful | Serious |
| `formal_casual` | Formal | Casual |
| `respectful_irreverent` | Respectful | Irreverent |
| `enthusiastic_matter_of_fact` | Enthusiastic | Matter-of-fact |
| `certainty` | Hedged | Declarative |
| `density` | Spacious | Packed |

Use mid-range values unless the voice genuinely lives at an extreme.
NN/g's research finds extremes rarely work in practice.

## Attributions

The top-level `attributions:` list is the canonical record of which YAML fields or rule IDs came from which named third-party source. Voice-composer appends
one entry per accepted preset; voice-stylist reads the list at draft time to honor "attribute on first use" within drafts.

YAML comments in `voice.md` (e.g. `# Source: Microsoft`) do not round-trip through `voice_io.py` — pyyaml's `safe_dump` strips them. The structured
`attributions:` list is the only attribution form that persists.

A voice with an empty or missing `attributions:` list is treated as fully writer-authored; voice-stylist falls back to its own judgment from the License
matrix and Named-source attribution sections of this prompt.

## Inheritance: lexicons and never-lists

Two shipped collections:

- `${CLAUDE_PLUGIN_ROOT}/voices/_lexicons/<name>.yaml` — substitution
  dictionaries with `banned`, `preferred`, and optional `taboo_phrases`.
  A voice references a lexicon by name in `diction.inherit_lexicons`;
  the voice's own entries override.
- `${CLAUDE_PLUGIN_ROOT}/voices/_never_lists/<name>.yaml` — starter
  never-list entries. A voice loads them by **copying** the entries
  it wants into its own `never:` block. There is no inherit field for
  never-lists; copy-on-use keeps every entry under the voice's own
  control.

Available shipped lexicons:

- `microsoft` — CC BY 4.0; substitutions adapted from the Microsoft
  Writing Style Guide.
- `gov-uk` — Open Government Licence v3.0; substitutions adapted from
  the GOV.UK style guide "Words to avoid" list.

Available shipped never-lists:

- `microsoft-simple-human` — CC BY 4.0; 13 starter rules from
  Microsoft's brand-voice principles.

When voice-composer offers a preset to a writer during compose
dialogue, the agent attributes the source on first use:

> "Substitutions adapted from the Microsoft Writing Style Guide
> (CC BY 4.0)."


## Audience ceilings (inline `audiences:` block)

```yaml
private:
  severity_ceiling: 5        # Never read as an audience name;
                              # the no-audience-declared default
  dial_ceiling: 1.0
  never_extend: []
  surface_filter: null
team:
  severity_ceiling: 3
  dial_ceiling: 1.0
  fallback_voice: null
  never_extend: [...]
  surface_filter: { admit: [...], closes: [...] }
external:
  closed: true                # voice does not admit drafts here
  reason: <prose>             # surfaced when the drafter bails
```

Per-audience fields, each enforced by **subtraction** (a
ceiling removes admissions the dial would grant; it never adds):

- `severity_ceiling: <0..5>` — hard cap on severity-keyed phrasing.
- `dial_ceiling: <0.0..1.0>` — hard cap on the effective dial; `0.0`
  closes the voice's own register and engages `fallback_voice`.
- `fallback_voice: <name>` — voice to defer to at `dial_ceiling: 0.0`
  (typically `literary-editor`); `null` means the voice does not yield.
- `never_extend: [<rule>,...]` — extra never-list entries for this audience.
- `surface_filter: { admit: [...], closes: [...] }` — whitelist/blacklist
  over surface names; the string `'*'` closes all surfaces; `null` means
  the filter does not engage.
- `closed: true` + `reason:` — the voice does not admit this audience;
  the drafter bails with the reason.

Resolution at draft time: read the draft's `audience: <name>` (default
`private`), look up `audiences.<name>` in the voice profile, and apply
its ceiling. When the voice declares no `audiences:` block, or the block
omits the requested audience, the drafter treats the audience as
`private` — full register, the voice as designed. `/compose-voice` and
`/import-voice` ship the three starter audiences from
`_template/voice.md`; the writer tightens them per voice, and
`/refine-voice` edits them later. The full resolution protocol lives in
the `voice-contract` skill § "Audience resolution."

## Rule taxonomy summary

`scripts/voice_check.py` classifies every YAML field as **mechanical**
(string/regex match), **statistical** (count and compare to target),
or **agent-required** (model judges). The full taxonomy lives in the
planning workspace at `05-voice-checker-rules.md` and is replicated
here for runtime reference:

- **Mechanical**: `diction.banned`, `diction.preferred`,
  `lexicon.characteristic_openers`, `lexicon.characteristic_closers`,
  `lexicon.taboo_phrases` (literal hits), `never[i]` with
  `detection: mechanical`, `rhythm.forbidden_patterns` entries
  prefixed with `re:`.
- **Statistical**: `rhythm.target_mean_sentence`,
  `rhythm.target_variation`, `rhythm.paragraph_shape`, count and
  density, every `syntax.<sub>`, `lexicon.pet_phrases` density,
  `never[i]` with `detection: statistical`.
- **Agent-required**: `purpose`, `audience`, every `register.*` axis,
  `diction.default_balance`, `diction.germanic_for`,
  `diction.latinate_for`, `rhythm.one_sentence_paragraphs` policy,
  `rhythm.forbidden_patterns` prose entries, every `syntax.<sub>`
  policy verdict, `lexicon.taboo_phrases` paraphrase scan, every
  `structure.*` sub-field, `never[i]` with `detection: agent-required`.

The script emits a JSON violation report; the hook surfaces it in a
combined `systemMessage`. Voice-checker reads the report's
`judgments_needed` placeholders and supplies one-sentence verdicts.

## Front-matter convention for drafts

A draft declares its voice in front-matter:

```markdown
---
voice: MistressFilth
voice_tolerance: normal   # optional: strict | normal | relaxed
---

# Draft body
```

Absence of `voice:` means no voice check fires; only the
universal-prose check runs (Q-default).

## Agent contract recap

| Agent | Model | Role | Write access |
|---|---|---|---|
| `voice-composer` | Opus | Run compose dialogue; populate `voice.md` | yes (voice-profile only) |
| `voice-stylist` | Sonnet | Draft and edit prose against a profile | yes (draft files) |
| `voice-checker` | Haiku | Read-only rule check; supply agent verdicts | no |

When a dimension is silent, the voice-stylist falls back to the
`literary-editor` output style. When a voice rule and a
literary-editor principle conflict, the voice wins.

