---
#
# Voice profile — schema v1
#
# Created from _template/voice.md by /compose-voice. Edited by
# /refine-voice. The compose dialogue (`07-compose-dialogue.md` in the
# planning workspace) walks through the dimensions in fixed order:
# D1 purpose → D2 audience → D3 register → D4 diction → D5 rhythm →
# D6 syntax → D7 lexicon → D8 structure → D9 never → D10 prose body.
#
# Comments in this YAML are template guidance and may be removed when
# the file is rewritten by `voice_io.py`. For persistent notes, use the
# prose body below the closing front-matter delimiter.
#
#---------------------------
voice: <name>              # required; lowercase letters, digits, hyphens; matches directory name
version: 1                 # schema version; bumped only by future migrators
created: <YYYY-MM-DD>      # written once at first compose
updated: <YYYY-MM-DD>      # rewritten on each refine
author: <AUTHOR>           # the writer of the voice (not the agent)
imported_from: null        # set by /import-voice; freeform string describing the source
#
#---------------------------
# D1. Purpose — what this voice is for
#---------------------------
# Prose paragraph. Short. Names the kind of writing this voice serves
# and what it aims to do for readers (inform, argue, document, teach,
# persuade, disturb — pick yours).
purpose: null

#---------------------------
# D2. Audience — who this voice is for
#---------------------------
# Prose paragraph. Names a representative reader, what they already
# know, what they need from this writing.
audience: null

#---------------------------
# Audience ceilings — who is listening, and what carries to each
#---------------------------
# D2 above answers "who is this voice FOR" in prose. This block answers
# "what does the voice permit itself to render to each listener" as a
# ceiling the drafter enforces by SUBTRACTION: a ceiling can take
# admissions away from what the dial would grant; it never adds.
#
# Resolution at draft time: read the draft's `audience: <name>`
# (default `private`) when absent, look up `audiences.<name>` here, and
# apply its ceiling. When the block is absent, or the named audience is
# absent from it, the drafter treats the audience as `private` — the
# voice as designed, full register.
#
# The three starter audiences below ship as editable defaults. `private`
# is the voice at full register (keep it as-is unless you have reason to
# tighten the writer's own work). Tighten `team` and `external` to fit
# how this specific voice's surfaces carry outward; close an audience
# entirely with `closed: true` + a `reason:` when the voice's affect
# turned toward that reader reads as performative or worse.
#
# Per-audience fields (each enforced as subtraction):
#   severity_ceiling: <0..5> — hard cap on severity-keyed phrasing
#   dial_ceiling: <0.0..1.0> — hard cap on the effective dial; 0.0 closes
#                              the voice's own register and engages
#                              fallback_voice
#   fallback_voice: <name> — voice to defer to when dial_ceiling hits
#                            0.0 (typically literary-editor); null = the
#                            voice does not yield
#   never_extend: [<rule>,...] — extra never-list entries for this audience
#   surface_filter: — whitelist/blacklist over surface names;
#     { admit: [...], closes: [...] } — '*' (string) closes all surfaces;
#                                       null = filter does not engage
#   closed: true — voice does not admit drafts at this
#     reason: <prose> — audience; drafter bails with the reason
#
# Optional `rationale:` (free prose) documents why this voice's ceilings
# differ from the permissive default; it is never read as an audience name.
audiences:
  private:                  # the no-audience-declared default
    severity_ceiling: 5
    dial_ceiling: 1.0
    never_extend: []
    surface_filter: null    # all surfaces admit; the voice as designed
  team:                     # internal teammate skimming for the claim
    severity_ceiling: 3
    dial_ceiling: 1.0
    fallback_voice: null
    never_extend: []
    surface_filter: null
  external:                 # public / cross-org / customer-facing
    severity_ceiling: 2
    dial_ceiling: 0.0       # cosmic register closes; defer to fallback
    fallback_voice: literary-editor
    never_extend: []
    surface_filter: '*'     # all voice surfaces close

#---------------------------
# D3. Register — six dimensions on a 0-1 scale
#---------------------------
# Hybrid: NN/g's four (funny-serious, formal-casual,
# respectful-irreverent, enthusiastic-matter-of-fact) plus locally-
# authored certainty and density. Use mid-range values unless the
# voice genuinely lives at an extreme; NN/g's research suggests
# extremes rarely work in practice.
register:
  funny_serious: null                # 0 = funny/playful,  1 = serious
  formal_casual: null                # 0 = formal,         1 = casual
  respectful_irreverent: null        # 0 = respectful,     1 = irreverent
  enthusiastic_matter_of_fact: null  # 0 = enthusiastic,   1 = matter-of-fact
  certainty: null                    # 0 = hedged,         1 = declarative
  density: null                      # 0 = spacious,       1 = packed

#---------------------------
# D4. Diction — Saxon vs. Romance, banned words, preferred substitutions
#---------------------------
diction:
  # Plain-language summary of the voice's diction balance, e.g.,
  # "60% Germanic / 40% Latinate". Free-form; the agent reads it.
  default_balance: null

  # When this voice reaches for the Germanic word.
  # Each entry: a one-line context, e.g.,
  #   "verbs of action and decision"
  #   "anything that should land hard"
  germanic_for: []

  # When this voice reaches for the Latinate word.
  latinate_for: []

  # Words and phrases this voice never uses, regardless of context.
  # Each entry: a literal string. Voice-checker matches exactly.
  banned: []

  # Substitution pairs. Each entry: { instead_of: X, use: Y }.
  preferred: []

  # Inherit substitution rules from a shipped lexicon by name.
  # Available: microsoft, gov-uk (when their lexicon files ship).
  # The voice's own `banned` and `preferred` override inherited entries.
  inherit_lexicons: []

#---------------------------
# D5. Rhythm — sentence length, variation, paragraph shape
#---------------------------
rhythm:
  # Free-form target, e.g., "15-20 words" or "around 12 with high std dev".
  target_mean_sentence: null

  # How sharply the voice varies length, e.g., "high — std dev around 11".
  target_variation: null

  # How paragraphs are shaped, e.g., "3-5 sentences, occasionally one
  # sentence as punctuation".
  paragraph_shape: null

  # Policy on one-sentence paragraphs, e.g., "use sparingly, for landing".
  one_sentence_paragraphs: null

  # Patterns the voice never produces; voice-checker flags violations.
  # Each entry is a literal description.
  forbidden_patterns: []

#---------------------------

# D6. Syntax — punctuation and structural moves
#---------------------------
# Each value is free-form, e.g., "encouraged for parenthetical reframing"
# or "rare; prefer two sentences".
syntax:
  em_dashes: null
  colons: null
  semicolons: null
  parentheticals: null
  fragments: null
  bullets: null
  questions: null

#---------------------------
# D7. Lexicon — recognizable phrases of this voice
#---------------------------
lexicon:
  # Phrases the voice uses recognizably. 3-7 ideal; more dilutes.
  pet_phrases: []

  # Patterns sentences in this voice tend to start with.
  characteristic_openers: []

  # Patterns sentences in this voice tend to end with.
  characteristic_closers: []

  # Phrases this voice never uses, even when they would be natural
  # elsewhere (throat-clearing, padding, dead metaphors).
  taboo_phrases: []

#---------------------------
# D8. Structure — opening, closing, transitions, emphasis, citations
#---------------------------
structure:
  opening: null      # how a piece in this voice begins
  closing: null      # how it ends
  transitions: null  # how paragraphs link
  emphasis: null     # how emphasis is achieved
  citations: null    # how sources are cited

#---------------------------
# D9. Never — list of things this voice refuses to do
#---------------------------
# Entries can be plain strings ("rhetorical questions used for emphasis")
# or structured entries when a named-source preset is accepted, e.g.,
#   - { id: orwell-1, rule: "stale metaphor", detection: agent-required }
# When an Orwell preset is accepted, the composer also appends an entry
# to the `attributions:` block below — that's how the source survives
# round-trips (YAML comments do not). See `12-training-data-sources.md`.
never: []

#---------------------------
# Attributions — sources for accepted preset content
#---------------------------
# Voice-composer appends one entry per accepted named-source preset.
# Voice-stylist reads this list at draft and edit time to honor
# "attribute on first use" within drafts (§4 license-leak response).
# Each entry shape:
#   field: <yaml.path | rule-id>   # e.g., diction.preferred, never.orwell-1
#   source: <named source>          # e.g., Microsoft Writing Style Guide
#   license: <matrix tag>           # CC-BY-4.0 | OGL-3.0 | public-domain | training-data | NN/g-free
#   citation: <prose | locator>     # specific quote, page, or rule label
#   date: <YYYY-MM-DD>              # day the preset was accepted
attributions: []

#---------------------------
# Fallbacks — what governs when a dimension is silent
#---------------------------
fallbacks:
  when_voice_silent: "literary-editor output style"
  conflict_resolution: |
    When a voice rule and a literary-editor principle conflict, the
    voice wins. Note the override in the draft's commit message.

<!--
D10. Prose body — the writer's articulation of this voice

Optional. A short prose paragraph the writer adds (or that the
voice-composer agent drafts on request during /compose-voice). It
reads as guidance for everything the YAML rules above do not specify.

When the agent drafts the body, it marks the draft so you can review
or replace it:

  <!-- draft — revise or replace -->
  [drafted prose paragraph]

When this body is empty, the YAML rules and fallbacks govern alone.

A useful starter shape: 3-5 short "this voice is X" claims, each with
one sentence of elaboration. For example:

  1. This voice is plainspoken. [one-sentence elaboration]
  2. This voice is direct. [one-sentence elaboration]
  3. This voice trusts the reader. [one-sentence elaboration]

Replace this comment block with your prose paragraph (or leave the
file as-is to keep the body empty).
-->
