# Voice contract reference

The voice profile is the writer's authored constitution. Schema D1-D10.

## Front-matter order (fixed)

1. voice
2. version
3. created
4. updated
5. authors
6. imported_from
7. voice_persona
8. purpose (D1)
9. audience (D2)
10. audiences (D2.5)
11. register (D3)
12. diction (D4)
13. rhythm (D5)
14. syntax (D6)
15. lexicon (D7)
16. structure (D8)
17. never (D9)
18. attributions

## Rule taxonomy

- **Mechanical** — string/regex match (`diction.banned`, `lexicon.taboo_phrases` literal hits, `never` with `detection: mechanical`)
- **Statistical** — count and compare to target (`rhythm.target_mean_sentence`, every `syntax.*`)
- **Agent-required** — model judges (`purpose`, every `register.*` axis, `structure.*`)

## Audience ceiling enforcement

The ceiling is subtraction only. `dial_ceiling: 0.0` engages `fallback_voice`. `closed: true` rejects the audience outright.
