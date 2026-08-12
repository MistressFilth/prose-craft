"""End-to-end Windows ACL test: ``prose voice draft`` leaves scratch restricted.

Skipped on POSIX because the ACL assertions require win32security.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from prose_craft.cli import app

windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows-only ACL helper")


@windows_only
def test_voice_draft_leaves_scratch_dir_restricted_to_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import win32security

    runtime = tmp_path / "run"
    runtime.mkdir()
    voices = tmp_path / "voices"
    voices.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voices))

    runner = CliRunner()
    # Any brief works; the goal is to confirm the scratch dir ends up with
    # the restrictive DACL after the run. The CLI creates the scratch file
    # (and therefore the scratch dir) before it resolves the voice, so the
    # ACL is applied even when the draft itself fails.
    result = runner.invoke(app, ["voice", "draft", "test", "Test brief for ACL coverage."])
    # The draft command may fail without a voice or model credentials; that
    # is OK — we only care about the ACL being applied regardless.
    _ = result.output  # silence unused warnings

    scratch = runtime / "prose-craft" / "scratch"
    assert scratch.is_dir(), "scratch dir must exist after voice draft run"

    sd = win32security.GetSecurityInfo(
        str(scratch),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION,
    )
    dacl = sd.GetSecurityDescriptorDacl()
    everyone_sid = win32security.ConvertStringSidToSid("S-1-1-0")
    deny_found = False
    for i in range(dacl.GetAceCount()):
        ace = dacl.GetAce(i)
        if ace[0][0] == 1 and ace[2] == everyone_sid:
            deny_found = True
            break
    assert deny_found, "scratch dir must carry a deny-Everyone ACE after voice draft"
