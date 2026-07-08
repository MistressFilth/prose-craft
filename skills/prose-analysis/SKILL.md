---
name: prose-analysis
description: Analyze prose for measurable quality features including diction balance, sentence rhythm, cohesion metrics, and readability. Use when evaluating text quality, diagnosing writing problems, or measuring improvement.
user-invocable: false
---

# Prose Analysis Skill

This skill provides methods for measuring prose quality using research-backed metrics derived from computational linguistics (Coh-Metrix) and literary craft principles.

## Quick Reference: Quality Indicators

| Metric | Poor | Acceptable | Excellent |
|---|---|---|---|
| Sentence length variance | <5 | 5-12 | 8-12 |
| Germanic/Latinate balance | >70%/<30% either | 50-60% Germanic | Context-appropriate |
| Cohesion (connectives/100 words) | <2 | 2-5 | 3-4 |
| Concrete noun ratio | <30% | 30-50% | >50% (narrative) |
| Readability (Flesch) | Mismatched to audience | Within 10 of target | Within 5 of target |

## Diction Analysis

### Germanic Word Markers
Common Germanic words (prefer these for force):
- **Body**: blood, bone, skin, heart, gut, hand, foot, eye
- **Action**: kill, strike, break, hold, bring, take, give, run, fall
- **Emotion**: love, hate, fear, hope, dread, wrath, shame
- **Nature**: earth, water, fire, wind, sun, moon, storm
- **Time**: day, night, year, now, then, soon, while

### Latinate Word Markers
Common Latinate words (use for precision/formality):
- **Suffixes**: -tion, -ity, -ment, -ance/-ence, -ous, -ive, -al
- **Prefixes**: pre-, post-, trans-, con-/com-, de-, re-, ex-
- **Abstract concepts**: facilitate, demonstrate, utilize, implement

### Analysis Method

1. Sample 100-word passages throughout the text
2. Classify each content word (nouns, verbs, adjectives, adverbs)
3. Calculate percentage Germanic vs Latinate
4. Note distribution: are Latinate words clustered or spread?
5. Check context: action scenes should skew Germanic; exposition may tolerate more Latinate

### Red Flags
- "Utilize" instead of "use"
- "Facilitate" instead of "help" or "enable"
- "Implement" instead of "do" or "start"
- "Subsequently" instead of "then" or "after"
- Any -ize verb that has a simpler form

## Sentence Rhythm Analysis

### Measurement Protocol

1. Count words per sentence for a section (minimum 20 sentences)
2. Calculate: mean, standard deviation, min, max
3. Plot the distribution mentally or literally
4. Look for patterns of monotony or chaos

### Healthy Rhythm Patterns

**Tension building**:
```
Long (20+) → Medium (12-15) → Short (5-8) → Very short (1-4) → Long release
```

**Contemplative**:
```
Medium → Long → Medium → Long → Medium (consistent flow)
```

**Staccato action**:
```
Short → Short → Medium → Short → Very short
```

### Diagnosing Problems

**Monotony indicators**:
- 3+ consecutive sentences within ±2 words of each other
- Standard deviation < 5
- No sentences under 8 words in a 20-sentence span

**Chaos indicators**:
- Standard deviation > 15
- No pattern to length changes
- Reader cannot find a rhythm

## Cohesion Metrics

### Referential Cohesion
Count and evaluate:
- Pronouns with clear antecedents
- Repeated key nouns across sentences
- Synonyms and near-synonyms linking ideas

**Test**: Can you draw arrows from each pronoun to its antecedent without confusion?

### Causal Cohesion
Count instances of:
- because, since, as (causal)
- therefore, thus, so, hence (resultative)
- if...then, when...then (conditional)
- in order to, so that (purposive)

**Target**: 1-3 causal markers per paragraph in argumentative prose

### Temporal Cohesion
Count instances of:
- then, next, after, before, during, while
- meanwhile, subsequently, previously
- first, second, finally

**Target**: At least one temporal marker per scene transition in narrative

### Connective Density
All connectives (additive, adversative, causal, temporal) per 100 words:
- <2: Under-connected (choppy)
- 2-5: Normal range
- >5: Over-connected (may feel mechanical)

## Readability Assessment

### Simplified Flesch Reading Ease
- ASL = Average Sentence Length (words per sentence)
- ASW = Average Syllables per Word

### Interpretation

| Score | Description | Audience |
|---|---|---|
| 90-100 | Very Easy | 5th grade |
| 80-90 | Easy | 6th grade |
| 70-80 | Fairly Easy | 7th grade |
| 60-70 | Standard | 8th-9th grade |
| 50-60 | Fairly Difficult | High school |
| 30-50 | Difficult | College |
| 0-30 | Very Difficult | Graduate/Professional |

### Context Matters

- **Genre fiction**: Target 60-80
- **Literary fiction**: Can drop to 40-60
- **Business writing**: Target 50-70
- **Academic writing**: 30-50 acceptable
- **Children's books**: 80-100

## Concrete vs Abstract Analysis

### Concrete Words
Can be perceived through senses:
- Objects: table, car, knife
- Sensory: red, loud, rough
- Actions: run, cut, whisper

### Abstract Words
Cannot be directly perceived:
- Concepts: freedom, justice, love (as noun)
- States: confusion, happiness, potential
- Qualities: importance, significance, utility

### Analysis
1. Identify all nouns in a passage
2. Classify as concrete or abstract
3. Calculate ratio
4. For narrative: >50% concrete is usually better
5. For exposition: balance depends on subject matter

## Full Diagnostic Template

```
PROSE QUALITY ANALYSIS
=======================

Source: [filename/excerpt]
Sample size: [word count]

DICTION
-------
Germanic: [X]%
Latinate: [Y]%
Assessment: [balanced/heavy-latinate/heavy-germanic]
Specific concerns: [list problem words/passages]

RHYTHM
------
Mean sentence length: [X] words
Std deviation: [Y]
Range: [min]-[max] words
Short sentences (<10): [Z]%
Long sentences (>25): [W]%
Assessment: [varied/monotonous/chaotic]
Specific concerns: [line numbers with issues]

COHESION
--------
Referential: [strong/adequate/weak]
Causal: [strong/adequate/weak]
Temporal: [strong/adequate/weak]
Connective density: [X]/100 words
Assessment: [well-connected/choppy/over-connected]
Specific concerns: [paragraphs with issues]

READABILITY
-----------
Flesch score: [X]
Grade level: [Y]
Target audience match: [appropriate/too-easy/too-hard]

CONCRETENESS
------------
Concrete nouns: [X]%
Abstract nouns: [Y]%
Assessment: [grounded/abstract/balanced]

PRIORITY RECOMMENDATIONS
------------------------
1. [Most important fix]
2. [Second priority]
3. [Third priority]
```
