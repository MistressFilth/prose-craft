"""Bootstrap a new voice profile.

Called by `skills/compose-voice` at the start of a compose session.
Copies `${CLAUDE_PLUGIN_ROOT}/voices/_template/voice.md` into
`${CLAUDE_PLUGIN_DATA}/voices/<name>/voice.md` and fills the
metadata placeholders (`voice`, `created`, `updated`,
`author`).

Usage::

    python3 voice_init.py <name> [--author <author>] [--force]

Exits non-zero if the voice already exists and `--force` is not
given.
"""

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel

import _index_generator
import voice_io

# Named type alias per allow_new_collections = false
DepthFilePaths = list[str]


class MigrationResult(BaseModel):
    """Result of voice_init --migrate-extensions operation."""

    depth_files_written: DepthFilePaths
    inline_block_stripped: bool
    depth_manifest_added: bool
    index_generated: bool


def template_path() -> Path:
    """Resolve `${CLAUDE_PLUGIN_ROOT}/voices/_template/voice.md`.

    Falls back to walking up from this file when the env var is unset
    (script-mode execution outside Claude Code)."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        return Path(root) / "voices" / "_template" / "voice.md"
    here = Path(__file__).resolve().parent
    return here.parent / "voices" / "_template" / "voice.md"


def init(
    name: str,
    author: str | None = None,
    force: bool = False,
    imported_from: str | None = None,
) -> Path:
    if not _valid_name(name):
        raise SystemExit(
            f"invalid voice name {name!r}: "
            f"use lowercase letters, digits, and hyphens only"
        )

    target = voice_io.voice_path(name)
    if target.exists() and not force:
        raise SystemExit(
            f"voice already exists: {target}\n"
            f"use --force to overwrite, or /refine-voice {name} to edit"
        )

    template = template_path()
    if not template.exists():
        raise SystemExit(f"template missing: {template}")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = template.read_text(encoding="utf-8")
    today = dt.date.today().isoformat()
    text = _fill_placeholder(text, "voice", name)
    text = _fill_placeholder(text, "created", today)
    text = _fill_placeholder(text, "updated", today)
    text = _fill_placeholder(
        text, "author", author or os.environ.get("USER", "<unknown>")
    )
    target.write_text(text, encoding="utf-8")
    if imported_from is not None:
        voice_io.update_field(name, ["imported_from"], imported_from)
    return target


def _valid_name(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*", name))


def _fill_placeholder(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:\s*<[^>]*>", re.MULTILINE)
    return pattern.sub(f"{key}: {value}", text, count=1)


def _slugify(text: str) -> str:
    """Convert arbitrary text to a safe filename slug (lowercase, hyphens)."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    return slug.strip("-")


def _write_depth_file(vdir: Path, rel_path: str, front: dict, body: str = "") -> None:
    """Write a depth file with the supplied front-matter dict and optional body."""
    file_path = vdir / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.dump(
        front, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    file_path.write_text(f"---\n{rendered}---\n{body}", encoding="utf-8")


# Per-kind dispatch helpers each return a list of (rel_path, kind, gated_by)
# tuples so the caller can append entries to the depth manifest.


def _extract_serves(drafting: str) -> str | None:
    """Find a 'TEX-N' reference in drafting guidance prose; None when absent."""
    m = re.search(r"\bTEX-\d+\b", drafting or "")
    return m.group(0) if m else None


def _extract_load_bearing(drafting: str) -> list[str]:
    """Extract TEX-N moves named as load-bearing in drafting guidance."""
    if not drafting:
        return []
    out: list[str] = []
    for m in re.finditer(r"\bTEX-(\d+)\b[.,]?load-bearing", drafting):
        out.append(f"TEX-{m.group(1)}")
    if not out:
        for m in re.finditer(r"load-bearing[.,]+\bTEX-(\d+)\b", drafting):
            out.append(f"TEX-{m.group(1)}")
    return list(dict.fromkeys(out))


def _build_dial_body(name: str, ext: dict) -> str:
    parts = [f"# {name} dial -- 0.0 to 1.0", ""]
    drafting = (ext.get("drafting_guidance") or "").rstrip()
    if drafting:
        parts.extend(["## Drafting guidance", "", drafting, ""])
    check = (ext.get("check_judgment") or "").rstrip()
    if check:
        parts.extend(["## Check criteria", "", check, ""])
    return "\n".join(parts)


def _build_well_body(well_name: str, well_config: dict) -> str:
    parts = [f"# {well_name.title()} well", ""]
    examples = well_config.get("examples") or []
    if examples:
        parts.extend(["## Phrases", ""])
        for i, ex in enumerate(examples, 1):
            parts.append(f"{i}. {ex}")
        parts.append("")
    ladder = well_config.get("ladder") or []
    if ladder:
        parts.extend(["## Admission ladder", "", "| Phrase | Min dial |", "|---|---|"])
        for entry in ladder:
            if isinstance(entry, dict):
                parts.append(f"| {entry.get('phrase', '')} | {entry.get('min', '')} |")
        parts.append("")
    return "\n".join(parts)


def _build_moves_body(moves: list, ext: dict) -> str:
    parts = ["# Texture moves", ""]
    for move in moves:
        if not isinstance(move, dict):
            continue
        mid = move.get("id", "")
        role = move.get("role", "")
        parts.extend([f"## {mid} -- {role}", ""])
        examples = move.get("examples") or []
        if examples:
            parts.append("**Examples:**")
            for ex in examples:
                parts.append(f"- {ex}")
            parts.append("")
    drafting = (ext.get("drafting_guidance") or "").rstrip()
    if drafting:
        parts.extend(["## Drafting guidance", "", drafting, ""])
    check = (ext.get("check_judgment") or "").rstrip()
    if check:
        parts.extend(["## Check criteria", "", check, ""])
    return "\n".join(parts)


def _build_surface_body(surfaces: dict, ext: dict) -> str:
    parts = ["# Surface profiles", "", "| Surface | Dial value |", "|---|---|"]
    for name, value in surfaces.items():
        parts.append(f"| {name} | {value} |")
    parts.append("")
    drafting = (ext.get("drafting_guidance") or "").rstrip()
    if drafting:
        parts.extend(["## Drafting guidance", "", drafting, ""])
    check = (ext.get("check_judgment") or "").rstrip()
    if check:
        parts.extend(["## Check criteria", "", check, ""])
    return "\n".join(parts)


def _migrate_scalar_dial(vdir: Path, ext: dict) -> list[tuple[str, str, str | None]]:
    """scalar_dial -> dials/<id>.md (kind: dial)."""
    name = ext.get("id") or "dial"
    config = ext.get("config") or {}
    front: dict = {"kind": "dial", "name": name}
    for key in ("default", "range", "ceiling"):
        if key in config:
            front[key] = config[key]
    body = _build_dial_body(name, ext)
    rel_path = f"dials/{_slugify(name)}.md"
    _write_depth_file(vdir, rel_path, front, body)
    return [(rel_path, "dial", None)]


def _migrate_vocabulary_well(
    vdir: Path, ext: dict
) -> list[tuple[str, str, str | None]]:
    """vocabulary_well -> one wells/<name>.md per nested well (kind: well)."""
    config = ext.get("config") or {}
    wells = config.get("wells") or {}
    parent_drafting = ext.get("drafting_guidance") or ""
    serves = _extract_serves(parent_drafting) or "TEX-1"

    out: list[tuple[str, str, str | None]] = []
    for well_name, well_config in wells.items():
        if not isinstance(well_config, dict):
            continue
        front: dict = {"kind": "well", "name": str(well_name), "serves": serves}
        gated_dial = well_config.get("gated_by")
        gated_path: str | None = None
        if gated_dial:
            gated_path = f"dials/{_slugify(str(gated_dial))}.md"
            front["gated_by"] = gated_path
        mv = well_config.get("minimum_value")
        if mv is not None:
            front["minimum_value"] = mv
        else:
            front["gated_by"] = None
        front["selection"] = "random-dedup"
        body = _build_well_body(str(well_name), well_config)
        rel_path = f"wells/{_slugify(str(well_name))}.md"
        _write_depth_file(vdir, rel_path, front, body)
        out.append((rel_path, "well", gated_path))
    return out


def _migrate_texture_catalog(
    vdir: Path, ext: dict
) -> list[tuple[str, str, str | None]]:
    """texture_catalog -> moves.md (kind: move-catalog)."""
    config = ext.get("config") or {}
    moves = config.get("moves") or []
    density = config.get("density_rule") or ""
    drafting = ext.get("drafting_guidance") or ""
    load_bearing = _extract_load_bearing(drafting)

    front: dict = {"kind": "move-catalog"}
    if density:
        front["density_rule"] = density
    if load_bearing:
        front["load_bearing"] = load_bearing

    body = _build_moves_body(moves, ext)
    rel_path = "moves.md"
    _write_depth_file(vdir, rel_path, front, body)
    return [(rel_path, "move-catalog", None)]


def _migrate_surface_profile(
    vdir: Path, ext: dict
) -> list[tuple[str, str, str | None]]:
    """surface_profile -> surfaces.md (kind: surface-map)."""
    config = ext.get("config") or {}
    governs = config.get("governs", "")
    surfaces = config.get("surfaces") or {}

    front: dict = {"kind": "surface-map"}
    if governs:
        front["governs"] = f"dials/{_slugify(str(governs))}.md"

    body = _build_surface_body(surfaces, ext)
    rel_path = "surfaces.md"
    _write_depth_file(vdir, rel_path, front, body)
    return [(rel_path, "surface-map", None)]


def _migrate_unknown(vdir: Path, ext: dict) -> list[tuple[str, str, str | None]]:
    """Unknown kind -> banks/<id>.md (kind: bank). Generic fallback."""
    name = ext.get("id") or "extension"
    front: dict = {"kind": "bank"}
    for k, v in ext.items():
        if k != "kind":
            front[k] = v
    rel_path = f"banks/{_slugify(name)}.md"
    _write_depth_file(vdir, rel_path, front, "")
    return [(rel_path, "bank", None)]


_KIND_DISPATCH = {
    "scalar_dial": _migrate_scalar_dial,
    "vocabulary_well": _migrate_vocabulary_well,
    "texture_catalog": _migrate_texture_catalog,
    "surface_profile": _migrate_surface_profile,
}


def migrate_extensions(voice_dir_str: str) -> MigrationResult:
    """Migrate a voice.md's inline `extensions:` block to depth files.

    Returns:
        MigrationResult with depth_files_written, inline_block_stripped,
        depth_manifest_added, and index_generated fields.
    """
    vdir = Path(voice_dir_str)
    voice_md_path = vdir / "voice.md"

    text = voice_md_path.read_text(encoding="utf-8")
    front_matter, body = voice_io._split(text, str(voice_md_path))

    raw_extensions = front_matter.get("extensions")
    extensions: list = raw_extensions if isinstance(raw_extensions, list) else []

    written: DepthFilePaths = []
    depth_entries: list[dict] = []

    for ext in extensions:
        if not isinstance(ext, dict):
            continue
        ext_kind = str(ext.get("kind", ""))
        handler = _KIND_DISPATCH.get(ext_kind, _migrate_unknown)
        for rel_path, kind, gated in handler(vdir, ext):
            entry: dict = {"path": rel_path, "kind": kind}
            if gated:
                entry["gated_by"] = gated
            written.append(rel_path)
            depth_entries.append(entry)

    # Strip extensions from front-matter
    inline_block_stripped = "extensions" in front_matter
    if inline_block_stripped:
        del front_matter["extensions"]

    # Add depth manifest
    front_matter["depth"] = depth_entries
    depth_manifest_added = bool(depth_entries)

    # Write rewritten voice.md
    rendered_front = yaml.dump(
        front_matter, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    voice_md_path.write_text(f"---\n{rendered_front}---\n{body}", encoding="utf-8")

    # Generate INDEX.md when 3+ depth files
    index_generated = False
    if len(written) >= 3:
        _index_generator.generate_index(
            vdir, depth_entries, base=front_matter.get("base")
        )
        index_generated = True

    return MigrationResult(
        depth_files_written=written,
        inline_block_stripped=inline_block_stripped,
        depth_manifest_added=depth_manifest_added,
        index_generated=index_generated,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="voice_init",
        description="Create a new voice profile from the bundled template.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # Default: create a new voice
    create_parser = subparsers.add_parser("create", help="create a new voice profile")
    create_parser.add_argument("name", help="voice name (lowercase, hyphens)")
    create_parser.add_argument("--author", help="author name to record in front-matter")
    create_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite if a profile with this name already exists",
    )
    create_parser.add_argument(
        "--from",
        dest="imported_from",
        help="one-line description of the source material (sets imported_from in front-matter)",
    )

    # Top-level flags for backward compatibility (no subcommand)
    parser.add_argument("name", nargs="?", help="voice name (lowercase, hyphens)")
    parser.add_argument("--author", help="author name to record in front-matter")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite if a profile with this name already exists",
    )
    parser.add_argument(
        "--from",
        dest="imported_from",
        help="one-line description of the source material (sets imported_from in front-matter)",
    )
    parser.add_argument(
        "--migrate-extensions",
        metavar="VOICE_DIR",
        help="migrate inline extensions block to separate depth files in VOICE_DIR",
    )

    args = parser.parse_args(argv)

    if args.migrate_extensions:
        result = migrate_extensions(args.migrate_extensions)
        print(f"depth_files_written: {result.depth_files_written}")
        print(f"inline_block_stripped: {result.inline_block_stripped}")
        print(f"depth_manifest_added: {result.depth_manifest_added}")
        print(f"index_generated: {result.index_generated}")
        return 0

    if not args.name:
        parser.error("name is required when --migrate-extensions is not set")

    target = init(args.name, args.author, args.force, args.imported_from)
    print(f"created: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
