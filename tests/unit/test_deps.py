"""Direct-dependency regression tests.

Catches transitive-only dep chains that break in non-dev environments
(MCP server runtime, uv-tool installs). Each test imports a module in
a fresh subprocess so the dev venv's transitive deps don't mask the
regression.
"""

from __future__ import annotations

import subprocess
import sys


def test_rich_is_a_direct_dependency():
    """rich must be importable in a fresh subprocess; transitive-only is fragile.

    Engine imports ``rich.console`` and ``rich.markdown`` directly
    (src/prose_craft/cli.py). ``pydantic-ai-harness`` (already a direct
    dep) imports ``rich.traceback`` in its agent-execution path.

    If ``rich`` is declared as a transitive-only dep (via ``typer``),
    the MCP server's runtime env may not have it installed — and the
    harness fails with ``No module named 'rich.traceback'``.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import rich.console, rich.markdown, rich.traceback"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"rich not importable in fresh subprocess: {result.stderr}"
