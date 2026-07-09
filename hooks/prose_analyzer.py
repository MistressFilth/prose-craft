#!/usr/bin/env python3
"""
Prose Quality Analyzer Hook
Surfaces voice-rule violations on edits made by the prose plugin's subagents.

Scope and behavior:

- Runs only inside the plugin's subagents (gated on `agent_type`), so
  feedback appears only for user-requested prose work routed through a
  prose skill or agent.
- Emits a finding only when the draft's front-matter names a voice
  (`voice: <name>`): the hook runs scripts/voice_check.py and renders
  the violations. With no named voice, it exits silently.
- Universal prose statistics (sentence length, diction balance, Flesch,
  cohesion) are available on request through the analyze-prose and
  prose-analysis skills; the hook no longer emits them automatically.

`voice_tolerance: strict | normal | relaxed` (optional; default
`normal`) is read directly by voice_check from the draft's front-matter;
see 03-architecture.md § Hook integration for the override mapping.
"""

import json
import sys
import re
import os
import subprocess
from collections import Counter
from pathlib import Path

# Common Germanic words (Old English / Norse origin) -- sample set
GERMANIC_MARKERS = {
    # Body
    "blood",
    "bone",
    "skin",
    "heart",
    "gut",
    "hand",
    "foot",
    "eye",
    "ear",
    "head",
    "arm",
    "leg",
    "finger",
    "mouth",
    "tooth",
    "hair",
    "back",
    "neck",
    # Action
    "kill",
    "strike",
    "break",
    "hold",
    "bring",
    "take",
    "give",
    "run",
    "fall",
    "walk",
    "go",
    "come",
    "get",
    "put",
    "make",
    "see",
    "know",
    "think",
    "feel",
    "say",
    "tell",
    "ask",
    "hear",
    "find",
    "show",
    "let",
    "leave",
    "keep",
    "begin",
    "end",
    "stand",
    "sit",
    "lie",
    "sleep",
    "wake",
    "eat",
    "drink",
    "die",
    "live",
    # Emotion
    "love",
    "hate",
    "fear",
    "dread",
    "hope",
    "wrath",
    "shame",
    "glad",
    "sad",
    # Nature
    "earth",
    "water",
    "fire",
    "wind",
    "sun",
    "moon",
    "storm",
    "rain",
    "snow",
    "sky",
    "sea",
    "land",
    "wood",
    "stone",
    "hill",
    "field",
    # Common
    "man",
    "woman",
    "child",
    "house",
    "home",
    "door",
    "window",
    "bed",
    "food",
    "day",
    "night",
    "year",
    "time",
    "life",
    "death",
    "word",
    "thing",
    "way",
    "good",
    "bad",
    "great",
    "small",
    "old",
    "new",
    "long",
    "short",
    "high",
    "low",
    "true",
    "dark",
    "light",
    "cold",
    "warm",
    "hard",
    "soft",
    "fast",
    "slow",
}

# Common Latinate suffixes
LATINATE_SUFFIXES = [
    "tion",
    "sion",
    "ment",
    "ity",
    "ance",
    "ence",
    "ous",
    "ious",
    "ive",
    "ative",
    "itive",
    "al",
    "ial",
    "ical",
    "able",
    "ible",
    "fy",
    "ify",
    "ize",
    "ate",
]

# Common Latinate words
LATINATE_MARKERS = {
    "utilize",
    "facilitate",
    "implement",
    "demonstrate",
    "indicate",
    "sufficient",
    "require",
    "obtain",
    "provide",
    "attempt",
    "commence",
    "conclude",
    "inquire",
    "respond",
    "observe",
    "reside",
    "purchase",
    "additional",
    "approximately",
    "subsequently",
    "concerning",
    "regarding",
    "assist",
    "construct",
    "manufacture",
    "transportation",
    "deceased",
    "perspiration",
    "consume",
    "endeavor",
    "numerous",
    "terminate",
    "initiate",
    "constitute",
    "establish",
    "determine",
    "significant",
    "appropriate",
    "sufficient",
    "necessary",
    "available",
    "possible",
}

# Causal connectives
CAUSAL_WORDS = {
    "because",
    "since",
    "therefore",
    "thus",
    "hence",
    "so",
    "consequently",
    "accordingly",
    "as a result",
    "for this reason",
    "due to",
}

# Temporal connectives
TEMPORAL_WORDS = {
    "then",
    "next",
    "after",
    "before",
    "during",
    "while",
    "meanwhile",
    "subsequently",
    "previously",
    "finally",
    "eventually",
    "first",
    "second",
    "last",
    "when",
    "until",
}

# Additive/adversative connectives
OTHER_CONNECTIVES = {
    "and",
    "also",
    "moreover",
    "furthermore",
    "however",
    "but",
    "yet",
    "although",
    "though",
    "nevertheless",
    "nonetheless",
    "instead",
    "otherwise",
    "similarly",
    "likewise",
    "conversely",
}


def count_syllables(word):
    """Rough syllable count based on vowel groups."""
    word = word.lower()
    count = 0
    vowels = "aeiouy"
    prev_was_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel

    # Adjust for silent e
    if word.endswith("e") and count > 1:
        count -= 1

    return max(1, count)


def tokenize_sentences(text):
    """Split text into sentences."""
    # Simple sentence splitting
    text = re.sub(r"\s+", " ", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def tokenize_words(text):
    """Extract words from text."""
    return re.findall(r"\b[a-zA-Z]+\b", text.lower())


def classify_word_origin(word):
    """Classify word as likely Germanic or Latinate."""
    word = word.lower()

    # Check explicit lists first
    if word in GERMANIC_MARKERS:
        return "germanic"
    if word in LATINATE_MARKERS:
        return "latinate"

    # Check suffixes
    for suffix in LATINATE_SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return "latinate"

    # Short words (1-4 letters) are more likely Germanic
    if len(word) <= 4:
        return "germanic"

    # Words with many syllables are more likely Latinate
    if count_syllables(word) >= 4:
        return "latinate"

    return "unknown"


def analyze_prose(text):
    """Full prose analysis."""
    sentences = tokenize_sentences(text)
    words = tokenize_words(text)

    if not sentences or not words:
        return None

    # Sentence statistics
    sent_lengths = [len(tokenize_words(s)) for s in sentences]

    if not sent_lengths:
        return None

    mean_sent_len = sum(sent_lengths) / len(sent_lengths)
    variance = sum((length - mean_sent_len) ** 2 for length in sent_lengths) / len(
        sent_lengths
    )
    std_dev = variance**0.5

    short_sents = sum(1 for length in sent_lengths if length < 10)
    long_sents = sum(1 for length in sent_lengths if length > 25)

    # Word origin analysis
    origins = [classify_word_origin(w) for w in words if len(w) > 2]
    origin_counts = Counter(origins)
    total_classified = origin_counts["germanic"] + origin_counts["latinate"]

    germanic_pct = (
        (origin_counts["germanic"] / total_classified * 100)
        if total_classified > 0
        else 50
    )
    latinate_pct = (
        (origin_counts["latinate"] / total_classified * 100)
        if total_classified > 0
        else 50
    )

    # Syllable analysis
    syllables = [count_syllables(w) for w in words]
    avg_syllables = sum(syllables) / len(syllables) if syllables else 2
    polysyllabic = (
        sum(1 for s in syllables if s >= 3) / len(syllables) * 100 if syllables else 0
    )

    # Flesch Reading Ease
    flesch = 206.835 - (1.015 * mean_sent_len) - (84.6 * avg_syllables)
    flesch = max(0, min(100, flesch))

    # Cohesion markers
    text_lower = text.lower()
    causal_count = sum(1 for w in CAUSAL_WORDS if w in text_lower)
    temporal_count = sum(1 for w in TEMPORAL_WORDS if w in text_lower)
    other_conn_count = sum(1 for w in OTHER_CONNECTIVES if w in text_lower)
    total_connectives = causal_count + temporal_count + other_conn_count
    conn_per_100 = (total_connectives / len(words) * 100) if words else 0

    # Monotony check (consecutive similar-length sentences)
    monotony_zones = []
    streak = 1
    for i in range(1, len(sent_lengths)):
        if abs(sent_lengths[i] - sent_lengths[i - 1]) <= 3:
            streak += 1
        else:
            if streak >= 4:
                monotony_zones.append((i - streak + 1, i))
            streak = 1
    if streak >= 4:
        monotony_zones.append((len(sent_lengths) - streak + 1, len(sent_lengths)))

    return {
        "sentence_count": len(sentences),
        "word_count": len(words),
        "mean_sentence_length": round(mean_sent_len, 1),
        "sentence_length_std": round(std_dev, 1),
        "short_sentences_pct": round(short_sents / len(sentences) * 100, 1),
        "long_sentences_pct": round(long_sents / len(sentences) * 100, 1),
        "germanic_pct": round(germanic_pct, 1),
        "latinate_pct": round(latinate_pct, 1),
        "avg_syllables_per_word": round(avg_syllables, 2),
        "polysyllabic_pct": round(polysyllabic, 1),
        "flesch_reading_ease": round(flesch, 1),
        "connectives_per_100_words": round(conn_per_100, 2),
        "causal_markers": causal_count,
        "temporal_markers": temporal_count,
        "monotony_zones": len(monotony_zones),
    }


def get_grade_level(flesch):
    """Convert Flesch score to approximate grade level."""
    if flesch >= 90:
        return "5th grade (Very Easy)"
    elif flesch >= 80:
        return "6th grade (Easy)"
    elif flesch >= 70:
        return "7th grade (Fairly Easy)"
    elif flesch >= 60:
        return "8th-9th grade (Standard)"
    elif flesch >= 50:
        return "High school (Fairly Difficult)"
    elif flesch >= 30:
        return "College (Difficult)"
    else:
        return "Graduate (Very Difficult)"


def assess_quality(stats):
    """Generate quality assessment and recommendations."""
    issues = []

    # Rhythm assessment
    if stats["sentence_length_std"] < 5:
        issues.append(
            "LOW RHYTHM VARIANCE: Sentences too uniform in length. Mix short punchy sentences with longer flowing ones."
        )
    elif stats["sentence_length_std"] > 15:
        issues.append(
            "HIGH RHYTHM VARIANCE: Sentence lengths may feel chaotic. Consider smoothing transitions."
        )

    if stats["monotony_zones"] > 0:
        issues.append(
            f"MONOTONY DETECTED: {stats['monotony_zones']} zone(s) of consecutive similar-length sentences."
        )

    # Diction assessment
    if stats["latinate_pct"] > 45:
        issues.append(
            "HEAVY LATINATE: Consider replacing abstract/formal words with concrete Germanic alternatives for more impact."
        )

    if stats["polysyllabic_pct"] > 30:
        issues.append(
            "WORD COMPLEXITY: High proportion of polysyllabic words may slow reading."
        )

    # Cohesion assessment
    if stats["connectives_per_100_words"] < 1.5:
        issues.append(
            "LOW COHESION: Prose may feel choppy. Consider adding transitional words or building reference chains."
        )
    elif stats["connectives_per_100_words"] > 5:
        issues.append(
            "OVER-CONNECTED: Too many connectives may feel mechanical. Trust the reader more."
        )

    return issues


# Prose-plugin subagents. When the hook fires inside a subagent, the
# harness supplies 'agent_type' on stdin (the agent's frontmatter
# 'name'). We run only for these names; any other subagent's edits fall
# outside the prose plugin's scope. Plugin subagents ignore 'hooks:'
# frontmatter for security reasons (see Claude Code sub-agents docs), so
# this runtime gate is the scoping mechanism available to a plugin.
PROSE_AGENTS = {
    "prose-analyst",
    "prose-architect",
    "prose-editor",
    "voice-checker",
    "voice-composer",
    "voice-stylist",
}


_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def parse_front_matter(content):
    """Return (front_matter_dict, body) using the line-anchored regex.

    Avoids a YAML library: the only keys we care about for dispatch
    are `voice` and `voice_tolerance`, both of which are simple
    `key: value` lines. When a line we care about is missing or
    malformed, we return an empty dict and let the universal-prose
    branch handle the body.
    """
    m = _FRONT_MATTER_RE.match(content)
    if not m:
        return {}, content
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        value = raw.strip().strip('"').strip("'")
        if key:
            fm[key] = value
    return fm, content[m.end() :]


def render_universal(stats, issues):
    """Render the existing universal-prose section as a markdown block."""
    lines = []
    lines.append("# Universal prose")
    lines.append("")
    lines.append(f"Words: {stats['word_count']}  Sentences: {stats['sentence_count']}")
    lines.append("")
    lines.append("**Rhythm**")
    lines.append(f"- Mean sentence length: {stats['mean_sentence_length']} words")
    lines.append(
        f"- Variation (std dev): {stats['sentence_length_std']} (target: 8-12)"
    )
    lines.append(
        f"- Short (<10 words): {stats['short_sentences_pct']}%  Long (>25): {stats['long_sentences_pct']}%"
    )
    lines.append("")
    lines.append("**Diction**")
    lines.append(
        f"- Germanic: {stats['germanic_pct']}%  Latinate: {stats['latinate_pct']}%"
    )
    lines.append(
        f"- Avg syllables/word: {stats['avg_syllables_per_word']}  Polysyllabic: {stats['polysyllabic_pct']}%"
    )
    lines.append("")
    lines.append("**Readability**")
    lines.append(
        f"- Flesch: {stats['flesch_reading_ease']} ({get_grade_level(stats['flesch_reading_ease'])})"
    )
    lines.append("")
    lines.append("**Cohesion**")
    lines.append(
        f"- Connectives/100 words: {stats['connectives_per_100_words']} (target: 2-4)"
    )
    lines.append(
        f"- Causal: {stats['causal_markers']}  Temporal: {stats['temporal_markers']}"
    )
    if issues:
        lines.append("")
        lines.append("**Issues**")
        for issue in issues:
            lines.append(f"- {issue}")
    return "\n".join(lines)


def voice_root():
    """Resolve `${CLAUDE_PLUGIN_DATA}/voices/`, with a fallback for
    tests outside the plugin runtime."""
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if base:
        return Path(base) / "voices"
    return Path.home() / ".claude" / "plugins" / "data" / "prose" / "voices"


def run_voice_check(file_path, voice_name):
    """Invoke voice_check.py as a subprocess. Returns (report_dict | None,
    error_str | None). The script reads `voice_tolerance` directly
    from the draft's front-matter; the hook does not need to forward
    it. The script is in ${CLAUDE_PLUGIN_ROOT}/scripts/.

    When a sibling `<file_path>.brief.md` exists, the hook forwards
    it via `--brief` so the TEX-shape detector can score the
    content half of the strip-test against the brief's vocabulary.
    The script also auto-detects sibling briefs on its own; the hook
    forwards explicitly so the report makes the brief path
    auditable in the JSON output.
    """
    plugin_root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(__file__))
    )
    script = Path(plugin_root) / "scripts" / "voice_check.py"
    if not script.exists():
        return None, f"voice_check.py not found at {script}"
    profile_path = voice_root() / voice_name / "voice.md"
    if not profile_path.exists():
        return None, f'voice profile "{voice_name}" not found at {profile_path}'

    # Resolve sibling brief: <draft>.brief.md next to the draft. When
    # absent, the script falls through to its structural-only
    # strip-test pass-rate.
    cmd = [sys.executable, str(script), file_path, "--voice", voice_name, "--json"]
    draft_path = Path(file_path)
    sibling_brief = draft_path.parent / f"{draft_path.stem}.brief.md"
    if sibling_brief.is_file():
        cmd.extend(["--brief", str(sibling_brief)])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None, "voice_check.py timed out"
    except Exception as exc:
        return None, f"voice_check.py failed: {exc}"
    if proc.returncode not in (0, 1):
        # 0 = clean, 1 = violations found, anything else = error.
        return None, proc.stderr.strip() or f"voice_check exited {proc.returncode}"
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, f"voice_check produced invalid JSON: {exc}"
    return report, None


def find_dispersion_siblings(file_path: str, voice_name: str) -> list[str]:
    """Find same-directory, same-voice drafts written earlier than
    `file_path`, for the v1 cross-draft dispersion checker (session-only,
    same-directory-same-voice grouping -- see
    docs/superpowers/specs/2026-07-09-dispersion-checker-design.md).

    Returns absolute paths as strings, sorted oldest-to-newest, excluding
    `file_path` itself. Siblings that fail to read or parse are skipped
    silently, matching the tolerance this hook already applies elsewhere.
    """
    target = Path(file_path).resolve()
    directory = target.parent
    try:
        target_mtime = target.stat().st_mtime
    except OSError:
        return []

    siblings: list[tuple[float, str]] = []
    for ext in ("*.md", "*.txt"):
        for candidate in directory.glob(ext):
            candidate = candidate.resolve()
            if candidate == target:
                continue
            try:
                mtime = candidate.stat().st_mtime
            except OSError:
                continue
            if mtime >= target_mtime:
                continue
            try:
                content = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            fm, _ = parse_front_matter(content)
            if fm.get("voice") != voice_name:
                continue
            siblings.append((mtime, str(candidate)))

    siblings.sort(key=lambda pair: pair[0])
    return [path for _, path in siblings]


def run_dispersion_check(new_draft_path: str, sibling_paths: list[str]):
    """Invoke dispersion_check.py as a subprocess, mirroring
    run_voice_check's subprocess contract. Returns (profile_dict | None,
    error_str | None)."""
    plugin_root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT", os.path.dirname(os.path.dirname(__file__))
    )
    script = Path(plugin_root) / "scripts" / "dispersion_check.py"
    if not script.exists():
        return None, f"dispersion_check.py not found at {script}"

    cmd = [sys.executable, str(script), new_draft_path, *sibling_paths, "--json"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None, "dispersion_check.py timed out"
    except Exception as exc:
        return None, f"dispersion_check.py failed: {exc}"
    if proc.returncode != 0:
        return None, proc.stderr.strip() or f"dispersion_check exited {proc.returncode}"
    try:
        profile = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return None, f"dispersion_check produced invalid JSON: {exc}"
    return profile, None


def render_dispersion(profile, error):
    """Render the Dispersion section. Returns '' when there is nothing to
    report (no error and no profile) -- silence matches render_voice's
    convention for a clean draft with no siblings to compare against.

    Reports every raw signal from measure_set()'s altitude_1/altitude_2
    blocks. No threshold, no flag, no "collapsed"/"converged" verdict
    language anywhere -- see this feature's non-negotiable constraint #3.
    """
    if error:
        return f"# Dispersion\n\n> {error}"
    if not profile:
        return ""
    a1 = profile["altitude_1"]
    a2 = profile["altitude_2"]
    lines = [
        "# Dispersion",
        "",
        f"Compared against {profile['n'] - 1} prior same-brief draft(s) "
        f"(n={profile['n']} total).",
        "",
        "## Altitude 1 -- lexical",
        f"- content_jaccard: {a1['content_jaccard']:.3f}",
        f"- trigram_jaccard: {a1['trigram_jaccard']:.3f}",
        f"- shared_mass: {a1['shared_mass']:.3f}",
        f"- dispersion_index: {a1['dispersion_index']:.3f}",
        "",
        "## Altitude 2 -- frame/structure",
        f"- distinct_opener_frames_fraction: {a2['distinct_opener_frames_fraction']:.3f}",
        f"- mean_opener_similarity: {a2['mean_opener_similarity']:.3f}",
        f"- distinct_structure_sigs_fraction: {a2['distinct_structure_sigs_fraction']:.3f}",
        f"- mean_structural_similarity: {a2['mean_structural_similarity']:.3f}",
        f"- dispersion_index: {a2['dispersion_index']:.3f}",
    ]
    return "\n".join(lines)


def render_voice(report, file_path, voice_name, error):
    """Render the voice section. Returns '' when the voice check found
    nothing (silence is the strongest possible "this draft is fine").

    Sub-sections (Mechanical / Statistical / Notes) appear only when
    their list is non-empty, per 03-architecture.md.
    """
    if error:
        return f"# Voice — {voice_name}\n\n> {error}"
    if not report:
        return ""
    mechanical = [
        v for v in report.get("violations", []) if v.get("category") == "mechanical"
    ]
    statistical = [
        v for v in report.get("violations", []) if v.get("category") == "statistical"
    ]
    judgments = report.get("judgments_needed", [])
    if not mechanical and not statistical and not judgments:
        return ""
    lines = [f"# Voice — {voice_name}"]
    if mechanical:
        lines.append("")
        lines.append(f"## Mechanical violations ({len(mechanical)})")
        for v in mechanical:
            line = v.get("line")
            col = v.get("col")
            loc = f"{file_path}:{line}:{col}" if line and col else file_path
            lines.append(f"- {loc}  **{v.get('rule')}** — {v.get('message')}")
    if statistical:
        lines.append("")
        lines.append(f"## Statistical findings ({len(statistical)})")
        for v in statistical:
            measured = v.get("measured")
            target = v.get("target")
            band = v.get("band")
            tail = ""
            if band:
                tail = f" (band {band})"
            lines.append(
                f"- **{v.get('rule')}** — measured {measured}, target {target}{tail}"
            )
    if judgments:
        lines.append("")
        lines.append(f"## Notes (agent-required, {len(judgments)})")
        # Fold the per-rule prompts into a one-line summary plus details.
        rules = sorted({j.get("rule", "?") for j in judgments})
        lines.append(f"- Rules awaiting agent verdict: {', '.join(rules)}")
    return "\n".join(lines)


def main():
    try:
        input_data = json.load(sys.stdin)

        # Scope analysis to user-requested prose work. The plugin's
        # skills (draft-in-voice, edit-prose, analyze-prose, ...) do
        # their writing by dispatching the prose subagents, so a
        # user-initiated prose request always runs inside one of those
        # agents, where the harness sends `agent_type`. Run only for
        # those names; exit silently for every other subagent AND for
        # main-thread edits (absent `agent_type`), so incidental prose
        # edits the user did not route through the plugin get nothing.
        # Plugin subagents ignore `hooks:` frontmatter for security
        # reasons (Claude Code sub-agents docs), so this runtime gate is
        # the scoping mechanism available to a plugin.
        if input_data.get("agent_type") not in PROSE_AGENTS:
            sys.exit(0)

        tool_input = input_data.get("tool_input", {})
        file_path = tool_input.get("file_path") or tool_input.get("path", "")

        prose_extensions = [".txt", ".md", ".mdx", ".rst", ".tex"]
        if not any(file_path.endswith(ext) for ext in prose_extensions):
            sys.exit(0)

        if not os.path.exists(file_path):
            sys.exit(0)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        front_matter, _ = parse_front_matter(content)
        voice_name = front_matter.get("voice")

        # The hook emits voice-rule violations only. Universal prose
        # statistics (rhythm, diction balance, Flesch, cohesion) stay
        # available on request through the analyze-prose / prose-analysis
        # skills, which dispatch their own agents; the automatic readout
        # was noise. With no named voice profile there is nothing to
        # check, so exit silently.
        if not voice_name:
            sys.exit(0)

        report, error = run_voice_check(file_path, voice_name)
        voice_section = render_voice(report, file_path, voice_name, error)

        dispersion_section = ""
        sibling_paths = find_dispersion_siblings(file_path, voice_name)
        if sibling_paths:
            profile, disp_error = run_dispersion_check(file_path, sibling_paths)
            dispersion_section = render_dispersion(profile, disp_error)

        sections = [s for s in (voice_section, dispersion_section) if s]
        if not sections:
            sys.exit(0)

        header = f"**prose — {os.path.basename(file_path)}**"
        message = header + "\n\n" + "\n\n".join(sections)
        print(json.dumps({"systemMessage": message}))

    except Exception:
        # Silent failure — don't disrupt the workflow
        sys.exit(0)


if __name__ == "__main__":
    main()
