"""Read and write voice.md profiles, preserving the prose body verbatim.

Voice profiles live at `${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md`.
Each is a single file with YAML front-matter and an optional prose
body. This module owns the split, the YAML round-trip, and the
voice-directory resolution.

Public surface
---------------

- `voices_root() -> Path` -- resolve `${CLAUDE_PLUGIN_DATA}/voices/`
- `voice_dir(name: str) -> Path` -- resolve a voice's directory
- `voice_path(name: str) -> Path` -- resolve a single voice's `voice.md`
- `import_notes_path(name: str) -> Path` -- resolve a voice's `import-notes.md`
- `read(name: str) -> Voice` -- load a profile
- `write(voice: Voice) -> None` -- write a profile, preserving the
  body and field order.
- `read_depth_file(voice_dir: Path, entry: DepthEntry) -> DepthFile` -- parse
  a depth file into front_matter and body.
- `resolve_override_chain(child: Voice) -> OverrideChain` -- return
  [parent, child] when base is set, [child] otherwise. Single-level only.
`Voice` -- a Pydantic BaseModel holding `name` (str), `front_matter` (dict),
`body` (str), optional `base` (str), and optional `depth` (list of DepthEntry).
`DepthEntry` -- a Pydantic BaseModel for depth manifest entries (path, kind, gated_by).
`DepthFile` -- a Pydantic BaseModel holding parsed depth-file front-matter and body.

Round-trip rules
-----------------

- Front-matter is split with the line-anchored regex
  `r"\\A---\\n(.*?)\\n---\\n"` (re.DOTALL). A naive `text.split('---')`
  breaks on inline `---` substrings inside backticks or comments.
- `yaml.dump` is called with a `_LiteralBlockDumper` so that
  multi-line strings are emitted as `|` literal block scalars
  (not single-quoted with `\\n` literal), sequence items indent under
  their parent key, and field order (D1 -> D10) is preserved via
  `sort_keys=False`.
- The body -- every byte after the closing `---\\n` -- is preserved
  byte-exact. The writer re-emits it verbatim.
- When the file has no body, the writer still emits a trailing newline
  after the closing `---`.
"""

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel


_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

# Named type alias for allow_new_collections = false
DepthKind = Literal[
    "bank",
    "well",
    "move-catalog",
    "dial",
    "surface-map",
    "character",
    "reference",
    "index",
    "exemplar",
]

FrontMatterDict = dict[str, Any]


class DepthEntry(BaseModel):
    """A single entry in a voice's depth manifest."""

    path: str
    kind: DepthKind
    gated_by: str | None = None


# Named type alias for depth manifest list
DepthManifest = list[DepthEntry]


class Voice(BaseModel):
    """A voice profile loaded from voice.md."""

    name: str
    front_matter: FrontMatterDict = {}
    body: str = ""
    base: str | None = None
    depth: DepthManifest | None = None

    model_config = {"arbitrary_types_allowed": True}


class DepthFile(BaseModel):
    """Parsed contents of a depth file (bank, well, etc.)."""

    front_matter: FrontMatterDict
    body: str


# Named type alias for the override chain list
OverrideChain = list[Voice]


class BankFrontmatter(BaseModel):
    """Parsed front-matter of a bank depth file (BID-0000X ISACE construct)."""

    kind: Literal["bank"]
    field: str
    selection: str | None = None
    exhaustion: str | None = None
    floor: int | None = None


class ExpandOffer(BaseModel):
    """Composer's offer record when an inline list overflows its ceiling.

    No runtime call site -- compose-voice is a markdown skill. This model
    exists to satisfy the Provides: ExpandOffer contract in primary.feature
    (BID-0000M/N/O).
    """

    overflow_field: str
    ceiling: int
    decision: Literal["accept", "decline", "defer"]


class IndexManifest(BaseModel):
    """In-memory representation of a generated INDEX.md (BID-0000P/Q).

    Each field is a list of markdown table row strings for that section.
    `generate_index()` in `_index_generator.py` builds and renders this.
    """

    banks_table: list[str] = []
    moves_table: list[str] = []
    wells_table: list[str] = []
    dials_table: list[str] = []
    surfaces_table: list[str] = []
    inheritance_table: list[str] = []


# Named type aliases per allow_new_collections = false
BankPhrases = list[str]
ViolationList = list[dict[str, Any]]


class VoiceIOError(Exception):
    pass


def voices_root() -> Path:
    """Return `${CLAUDE_PLUGIN_DATA}/voices/`.

    `CLAUDE_PLUGIN_DATA` is set by Claude Code when the plugin runs.
    Outside that environment (tests, scripts), fall back to
    `~/.claude/plugins/data/prose/voices/`.
    """
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if base:
        return Path(base) / "voices"
    return Path.home() / ".claude" / "plugins" / "data" / "prose" / "voices"


def voice_dir(name: str) -> Path:
    return voices_root() / name


def voice_path(name: str) -> Path:
    return voice_dir(name) / "voice.md"


def import_notes_path(name: str) -> Path:
    return voice_dir(name) / "import-notes.md"


def read(name: str) -> Voice:
    """Load a voice profile from ${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md.

    Raises VoiceIOError when the voice file does not exist or YAML is invalid,
    and also when a `base:` is declared but the parent voice directory is
    absent (fail-soft diagnostic for missing parent).
    """
    path = voice_path(name)
    if not path.exists():
        raise VoiceIOError(f"voice not found: {path}")
    text = path.read_text(encoding="utf-8")
    front_matter, body = _split(text, str(path))
    base = front_matter.get("base") or None
    # Normalize YAML null ("null" string or None) to Python None
    if base == "null":
        base = None

    raw_depth = front_matter.get("depth")
    depth: DepthManifest | None = None
    if isinstance(raw_depth, list) and raw_depth:
        depth = [DepthEntry(**entry) for entry in raw_depth]

    voice = Voice(
        name=name, front_matter=front_matter, body=body, base=base, depth=depth
    )

    # When base is declared, validate that the parent voice directory exists.
    # This is a fail-soft diagnostic: raise at read-time so callers do not
    # silently proceed with an unresolvable override chain.
    if base is not None:
        parent_dir = voices_root() / base
        if not parent_dir.exists():
            raise VoiceIOError(
                f"fail_soft: parent voice '{base}' not found at {parent_dir}; "
                f"voice '{name}' declares base={base}"
            )

    return voice


def read_path(path: Path) -> Voice:
    """Read a voice.md from an arbitrary path. Used by the knob to load
    a draft's declared voice and by `voice_check.py` for tests."""
    text = path.read_text(encoding="utf-8")
    front_matter, body = _split(text, str(path))
    name = front_matter.get("voice") or path.parent.name
    base = front_matter.get("base") or None
    if base == "null":
        base = None
    raw_depth = front_matter.get("depth")
    depth: DepthManifest | None = None
    if isinstance(raw_depth, list) and raw_depth:
        depth = [DepthEntry(**entry) for entry in raw_depth]
    return Voice(
        name=name, front_matter=front_matter, body=body, base=base, depth=depth
    )


def read_depth_file(vdir: Path, entry: DepthEntry) -> DepthFile:
    """Parse a depth file into front_matter and body.

    Args:
        vdir: The voice directory containing the depth file.
        entry: The DepthEntry from the depth manifest.

    Returns:
        DepthFile with parsed front_matter dict and verbatim body string.
    """
    depth_path = vdir / entry.path
    if not depth_path.exists():
        raise VoiceIOError(f"depth file not found: {depth_path}")
    text = depth_path.read_text(encoding="utf-8")
    front_matter, body = _split(text, str(depth_path))
    return DepthFile(front_matter=front_matter, body=body)


def resolve_override_chain(child: Voice) -> OverrideChain:
    """Return [parent, child] when child.base is set, else [child].

    Override semantics: total override by relative path (single-level).
    A child's depth file at the same relative path replaces the parent's
    entirely -- no merging occurs.

    Raises VoiceIOError when child.base is set but the parent voice
    directory is absent.
    """
    if child.base is None:
        return [child]

    parent_dir = voices_root() / child.base
    if not parent_dir.exists():
        raise VoiceIOError(
            f"fail_soft: parent voice '{child.base}' not found at {parent_dir}"
        )
    parent_voice_file = parent_dir / "voice.md"
    parent = read_path(parent_voice_file)
    return [parent, child]


def write(voice: Voice) -> None:
    path = voice_path(voice.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = render(voice)
    path.write_text(rendered, encoding="utf-8")


class _LiteralBlockDumper(yaml.SafeDumper):
    # Sequence items indent under their parent key (e.g. "  - id: papal")
    # rather than aligning with it ("- id: papal").
    def increase_indent(self, flow=False, indentless=False):
        _ = indentless  # always force indented sequences; override is intentional
        return super().increase_indent(flow=flow, indentless=False)


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    # Multi-line strings use | literal block style so round-trips don't
    # produce blank-line padding from single-quoted encoding.
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_LiteralBlockDumper.add_representer(str, _str_representer)


def render(voice: Voice) -> str:
    front = yaml.dump(
        voice.front_matter,
        Dumper=_LiteralBlockDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    if not front.endswith("\n"):
        front += "\n"
    return f"---\n{front}---\n{voice.body}"


def _split(text: str, source: str) -> tuple[FrontMatterDict, str]:
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        raise VoiceIOError(
            f"no YAML front-matter found in {source}; "
            f"file must start with '---\\n...---\\n'"
        )
    raw_front = match.group(1)
    body = text[match.end() :]
    try:
        front_matter = yaml.safe_load(raw_front) or {}
    except yaml.YAMLError as exc:
        raise VoiceIOError(f"invalid YAML in {source}: {exc}") from exc
    if not isinstance(front_matter, dict):
        raise VoiceIOError(
            f"front-matter in {source} must be a YAML mapping, "
            f"got {type(front_matter).__name__}"
        )
    return front_matter, body


def update_field(name: str, path: list[str], value: Any) -> None:
    """Update a single field in a voice profile in place.

    ``path`` is a list of keys, e.g. ``["diction", "banned"]``. Used
    by ``voice_init.py`` and ``voice-composer`` to set fields without
    rewriting the prose body.
    """
    voice = read(name)
    cursor: Any = voice.front_matter
    for key in path[:-1]:
        if key not in cursor or not isinstance(cursor[key], dict):
            cursor[key] = {}
        cursor = cursor[key]
    cursor[path[-1]] = value
    write(voice)


def append_attribution(name: str, entry: dict[str, Any]) -> None:
    """Append one entry to a voice's ``attributions`` list.

    Used by ``voice-composer`` when a named-source preset is accepted
    (Microsoft, GOV.UK, Williams, Orwell, Strunk, Fowler, NN/g, ...).
    The list survives ``voice_io`` round-trips because it is data, not
    YAML comments.

    Each entry should carry ``field``, ``source``, ``license``,
    ``citation``, and ``date``. Schema validation is the agent's
    responsibility -- this helper trusts the caller.
    """
    voice = read(name)
    existing = voice.front_matter.get("attributions")
    if not isinstance(existing, list):
        existing = []
    existing.append(entry)
    voice.front_matter["attributions"] = existing
    write(voice)
