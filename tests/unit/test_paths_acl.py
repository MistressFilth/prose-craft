"""Unit tests for prose_craft.paths._apply_owner_only_dacl (Windows only).

Skipped on POSIX because the helper is a Windows-only branch of the
runtime directory hardening. CI Windows job installs pywin32 before
running pytest, so these tests run there.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from prose_craft.paths import _apply_owner_only_dacl

windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows-only ACL helper")


@windows_only
def test_apply_owner_only_dacl_grants_owner(tmp_path: Path) -> None:
    """The current user's SID appears in an AccessAllowed ACE with full rights."""
    import win32security

    target = tmp_path / "runtime"
    target.mkdir()
    _apply_owner_only_dacl(target)

    sd = win32security.GetSecurityInfo(
        str(target),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION,
    )
    dacl = sd.GetSecurityDescriptorDacl()
    user_sid, _, _ = win32security.LookupAccountName(None, win32security.GetUserName())
    ace_found = False
    for i in range(dacl.GetAceCount()):
        ace = dacl.GetAce(i)
        ace_sid = ace[2]
        ace_type = ace[0][0]
        if ace_type == 0 and ace_sid == user_sid and ace[1] == win32security.FILE_ALL_ACCESS:
            ace_found = True
            break
    assert ace_found, "current user must appear in an AccessAllowed ACE with FILE_ALL_ACCESS"


@windows_only
def test_apply_owner_only_dacl_denies_everyone(tmp_path: Path) -> None:
    """The S-1-1-0 (Everyone) SID appears in an AccessDenied ACE."""
    import win32security

    target = tmp_path / "runtime"
    target.mkdir()
    _apply_owner_only_dacl(target)

    sd = win32security.GetSecurityInfo(
        str(target),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION,
    )
    dacl = sd.GetSecurityDescriptorDacl()
    everyone_sid = win32security.ConvertStringSidToSid("S-1-1-0")
    deny_found = False
    for i in range(dacl.GetAceCount()):
        ace = dacl.GetAce(i)
        ace_sid = ace[2]
        ace_type = ace[0][0]
        if ace_type == 1 and ace_sid == everyone_sid and ace[1] == win32security.FILE_ALL_ACCESS:
            deny_found = True
            break
    assert deny_found, "Everyone must appear in an AccessDenied ACE with FILE_ALL_ACCESS"


@windows_only
def test_apply_owner_only_dacl_sets_protected_flag(tmp_path: Path) -> None:
    """PROTECTED_DACL_SECURITY_INFORMATION is set so ambient ACLs do not leak in."""
    import win32security

    target = tmp_path / "runtime"
    target.mkdir()
    _apply_owner_only_dacl(target)

    # Re-read with the protected flag in the info request; if the flag is
    # set on the descriptor, GetSecurityInfo returns the protected DACL.
    sd = win32security.GetSecurityInfo(
        str(target),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
    )
    control = sd.GetSecurityDescriptorControl()
    # bit 12 (0x1000) of the control word is SE_DACL_PROTECTED.
    assert control & 0x1000, "SE_DACL_PROTECTED must be set on the security descriptor"


@windows_only
def test_apply_owner_only_dacl_marks_children_inherited(tmp_path: Path) -> None:
    """A child directory created after the ACL is set inherits the allow+deny pair."""
    import win32security

    target = tmp_path / "runtime"
    target.mkdir()
    _apply_owner_only_dacl(target)

    child = target / "scratch"
    child.mkdir()

    sd = win32security.GetSecurityInfo(
        str(child),
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
    assert deny_found, "child directory must inherit the deny-Everyone ACE"


@windows_only
def test_apply_owner_only_dacl_missing_pywin32_raises(tmp_path: Path) -> None:
    """If win32security cannot be imported, the helper raises RuntimeError with install hint."""
    import builtins
    import sys

    target = tmp_path / "runtime"
    target.mkdir()

    # Hide the pywin32 modules so the conditional import inside the helper fails.
    hidden = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "win32security" or name.startswith("win32security.")
    }
    for name in list(sys.modules):
        if name == "win32security" or name.startswith("win32security."):
            del sys.modules[name]
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "win32security" or name.startswith("win32security."):
            raise ImportError("simulated missing pywin32")
        return real_import(name, globals, locals, fromlist, level)

    builtins.__import__ = fake_import
    try:
        with pytest.raises(RuntimeError, match="pywin32"):
            _apply_owner_only_dacl(target)
    finally:
        builtins.__import__ = real_import
        for name, mod in hidden.items():
            sys.modules[name] = mod


@windows_only
def test_apply_owner_only_dacl_propagates_setsecurityinfo_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If SetSecurityInfo raises, the exception propagates unchanged."""
    import win32security

    target = tmp_path / "runtime"
    target.mkdir()

    def boom(*args, **kwargs):
        raise OSError("simulated SetSecurityInfo failure")

    monkeypatch.setattr(win32security, "SetSecurityInfo", boom)

    with pytest.raises(OSError, match="simulated SetSecurityInfo failure"):
        _apply_owner_only_dacl(target)
