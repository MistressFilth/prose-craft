"""INDEX.md generation policy for depth-touching skills.

Emission policy:
- When a voice's depth manifest contains three or more entries, generate INDEX.md
  in the voice directory listing every depth file with kind, purpose, and entry count.
- When the depth manifest has fewer than three entries, omit INDEX.md (the manifest
  fits inline in voice.md).
- Regenerate unconditionally on any depth-touching skill invocation — prior
  hand-edited INDEX.md content is overwritten without warning.

Public surface
--------------
- `generate_index(voice_dir, depth_entries, *, base)` — apply the emission policy
  and write (or skip) INDEX.md.
- `GENERATION_THRESHOLD` — the minimum depth-entry count that triggers generation.

Section names use the `_table` suffix to match the IndexManifest contract declared
in voice_io.py: banks_table, moves_table, wells_table, dials_table, surfaces_table,
inheritance_table.
"""

import pathlib

GENERATION_THRESHOLD: int = 3

DepthEntryDict = dict[str, str]


def _count_entries_in_file(depth_file: pathlib.Path) -> int:
    """Count numbered list entries in a depth file body."""
    if not depth_file.exists():
        return 0
    lines = depth_file.read_text(encoding="utf-8").splitlines()
    in_frontmatter = False
    past_frontmatter = False
    count = 0
    for line in lines:
        stripped = line.strip()
        if not past_frontmatter:
            if stripped == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    past_frontmatter = True
            continue
        if stripped and stripped[0].isdigit() and ". " in stripped:
            count += 1
    return count


def _build_table_rows(
    entries: list[DepthEntryDict], voice_dir: pathlib.Path
) -> list[str]:
    """Build markdown table rows (header + data) for a group of depth entries."""
    rows: list[str] = ["| Path | Purpose | Entries |", "|------|---------|---------|"]
    for entry in entries:
        path = entry.get("path", "")
        purpose = entry.get("purpose", "")
        entry_count = _count_entries_in_file(voice_dir / path)
        rows.append(f"| {path} | {purpose} | {entry_count} |")
    return rows


def generate_index(
    voice_dir: pathlib.Path | str,
    depth_entries: list[DepthEntryDict],
    *,
    base: str | None = None,
) -> None:
    """Apply the INDEX.md emission policy for a voice directory.

    When ``len(depth_entries) >= GENERATION_THRESHOLD``, writes INDEX.md into
    ``voice_dir`` listing every depth entry grouped by kind. When below the
    threshold, ensures INDEX.md is absent.

    Args:
        voice_dir: Absolute or relative path to the voice's directory.
        depth_entries: Sequence of depth-manifest entry dicts, each with at
            minimum ``path`` and ``kind`` keys, and optionally ``purpose``.
        base: Parent voice name for the inheritance_table section, or None.
    """
    voice_dir = pathlib.Path(voice_dir)
    index_path = voice_dir / "INDEX.md"

    if len(depth_entries) < GENERATION_THRESHOLD:
        if index_path.exists():
            index_path.unlink()
        return

    # Build IndexManifest rows by kind
    grouped: dict[str, list[DepthEntryDict]] = {}
    for entry in depth_entries:
        kind = entry.get("kind", "reference")
        grouped.setdefault(kind, []).append(entry)

    banks = _build_table_rows(grouped.get("bank", []), voice_dir)
    moves = _build_table_rows(grouped.get("move-catalog", []), voice_dir)
    wells = _build_table_rows(grouped.get("well", []), voice_dir)
    dials = _build_table_rows(grouped.get("dial", []), voice_dir)
    surfaces = _build_table_rows(grouped.get("surface-map", []), voice_dir)

    # Inheritance table
    if base:
        inh_rows: list[str] = [
            "| Role | Name |",
            "|------|------|",
            f"| base | {base} |",
        ]
        for entry in depth_entries:
            path = entry.get("path", "")
            kind = entry.get("kind", "")
            inh_rows.append(f"| override | {path} ({kind}) |")
    else:
        inh_rows = ["_(none)_"]

    # Render sections
    sections: list[str] = [
        "# Voice Depth Index\n",
        "Generated automatically by depth-touching skills. "
        "Edit via git history if prior content is needed.\n",
    ]

    def _section(header: str, rows: list[str]) -> str:
        return f"## {header}\n\n" + "\n".join(rows)

    if banks:
        sections.append(_section("banks_table", banks))
    if moves:
        sections.append(_section("moves_table", moves))
    if wells:
        sections.append(_section("wells_table", wells))
    if dials:
        sections.append(_section("dials_table", dials))
    if surfaces:
        sections.append(_section("surfaces_table", surfaces))

    # Remaining kinds (character, reference, etc.)
    emitted = {"bank", "move-catalog", "well", "dial", "surface-map"}
    for kind, entries in grouped.items():
        if kind not in emitted and kind != "index":
            label = kind.replace("-", "_") + "_table"
            sections.append(_section(label, _build_table_rows(entries, voice_dir)))

    sections.append(_section("inheritance_table", inh_rows))

    content = "\n\n".join(sections) + "\n"
    index_path.write_text(content, encoding="utf-8")
