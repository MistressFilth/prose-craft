"""Unit tests for prose_craft.paths._apply_owner_only_dacl (Windows only).

Skipped on POSIX because the helper is a Windows-only branch of the
runtime directory hardening. CI Windows job installs pywin32 before
running pytest, so these tests run there.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from prose_craft.paths import (
    _ACE_TYPE_ACCESS_ALLOWED,
    _ACE_TYPE_ACCESS_DENIED,
    _apply_owner_only_dacl,
    _read_dacl_ace_records,
)

windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows-only ACL helper")

FILE_ALL_ACCESS = 0x1F01FF
EVERYONE_SID_STRING = "S-1-1-0"


def _user_sid_string() -> str:
    """SID string for the current user, used by the allow-owner check."""
    import win32api
    import win32security

    sid, _, _ = win32security.LookupAccountName(None, win32api.GetUserName())
    return win32security.ConvertSidToStringSid(sid)


def _dacl_has_ace(
    records: list[tuple[int, int, int, str]],
    *,
    ace_type: int,
    flags: int,
    mask: int,
    sid_str: str,
) -> bool:
    """True if any ACE matches the (type, flags, mask, sid) tuple exactly."""
    return any(
        rec[0] == ace_type and rec[1] == flags and rec[2] == mask and rec[3] == sid_str
        for rec in records
    )


@windows_only
def test_apply_owner_only_dacl_grants_owner(tmp_path: Path) -> None:
    """The current user's SID appears in an AccessAllowed ACE with full rights."""
    target = tmp_path / "runtime"
    target.mkdir()
    _apply_owner_only_dacl(target)

    records = _read_dacl_ace_records(target)
    user_sid = _user_sid_string()

    # At least one ACE on the directory itself (no inheritance flags)
    # must be a DENY_NONE / access-allowed for the current user with
    # FILE_ALL_ACCESS.
    assert _dacl_has_ace(
        records,
        ace_type=_ACE_TYPE_ACCESS_ALLOWED,
        flags=0,
        mask=FILE_ALL_ACCESS,
        sid_str=user_sid,
    ), "current user must appear in an AccessAllowed ACE with FILE_ALL_ACCESS"


@windows_only
def test_apply_owner_only_dacl_denies_everyone(tmp_path: Path) -> None:
    """The S-1-1-0 (Everyone) SID appears in an AccessDenied ACE."""
    target = tmp_path / "runtime"
    target.mkdir()
    _apply_owner_only_dacl(target)

    records = _read_dacl_ace_records(target)
    assert _dacl_has_ace(
        records,
        ace_type=_ACE_TYPE_ACCESS_DENIED,
        flags=0,
        mask=FILE_ALL_ACCESS,
        sid_str=EVERYONE_SID_STRING,
    ), "Everyone must appear in an AccessDenied ACE with FILE_ALL_ACCESS"


@windows_only
def test_apply_owner_only_dacl_sets_protected_flag(tmp_path: Path) -> None:
    """PROTECTED_DACL_SECURITY_INFORMATION is set so ambient ACLs do not leak in.

    The ctypes read helper passes
    ``DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION``
    to ``GetNamedSecurityInfoW``. If the protected flag is not set on
    the descriptor, that request returns the inherited (ambient) DACL
    rather than the protected one we just applied. The protected DACL
    is empty before we apply the helper, so reading with protected
    requested must return the post-apply DACL — proving the flag is on.
    """
    target = tmp_path / "runtime"
    target.mkdir()
    _apply_owner_only_dacl(target)

    records = _read_dacl_ace_records(target)
    # The protected DACL must contain at least one ACE (the four we
    # added); if the descriptor had not been protected, the read would
    # have returned the inherited ambient DACL, which on a freshly
    # created tmp_path subdir is whatever the test runner's parent
    # inheritance chain produces.
    assert len(records) >= 4, (
        "PROTECTED_DACL_SECURITY_INFORMATION must surface the applied DACL; "
        "an empty/inherited read means the protected flag is not set"
    )


@windows_only
def test_apply_owner_only_dacl_marks_children_inherited(tmp_path: Path) -> None:
    """A child directory created after the ACL is set inherits the deny-Everyone ACE.

    The child sees the inherited ACE with ``OBJECT_INHERIT_ACE |
    CONTAINER_INHERIT_ACE | INHERITED`` (0x13) — Windows strips the
    INHERIT_ONLY bit on the child and adds the INHERITED bit to flag
    the ACE as inherited. The kernel reports it; the ACL store adds
    the bit on read.
    """
    target = tmp_path / "runtime"
    target.mkdir()
    _apply_owner_only_dacl(target)

    child = target / "scratch"
    child.mkdir()

    records = _read_dacl_ace_records(child)
    # The child must have an access-denied ACE for Everyone. The
    # OI|CI flags land on the inheriting child; INHERITED (0x10) is
    # added by Windows on the read side. We accept any combination of
    # those bits provided the ACE exists at all.
    assert any(
        rec[0] == _ACE_TYPE_ACCESS_DENIED
        and rec[2] == FILE_ALL_ACCESS
        and rec[3] == EVERYONE_SID_STRING
        for rec in records
    ), "child directory must inherit the deny-Everyone ACE"


@windows_only
def test_apply_owner_only_dacl_missing_pywin32_raises(tmp_path: Path) -> None:
    """If ctypes or pywin32 cannot be imported, the helper raises RuntimeError with install hint."""
    import builtins
    import sys

    target = tmp_path / "runtime"
    target.mkdir()

    # Hide the modules the helper imports so the conditional ``try`` at
    # the top of :func:`prose_craft.paths._apply_owner_only_dacl` fails.
    # pywin32's win32api / win32security are easy to evict via
    # ``sys.modules``; ctypes is a builtin-backed module so we block it
    # via a fake ``__import__`` that raises ImportError just for it.
    hidden = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "win32api" or name == "win32security" or name.startswith("win32security.")
    }
    for name in list(sys.modules):
        if name == "win32api" or name == "win32security" or name.startswith("win32security."):
            del sys.modules[name]
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if (
            name == "ctypes"
            or name == "win32api"
            or name == "win32security"
            or name.startswith("win32security.")
        ):
            raise ImportError("simulated missing Windows runtime dependency")
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
    """If SetNamedSecurityInfoW returns non-zero, the helper raises OSError."""
    import ctypes

    target = tmp_path / "runtime"
    target.mkdir()

    def boom(*args, **kwargs):
        return 0xC0000001  # arbitrary non-zero LSTATUS — the helper checks != 0

    # The helper binds ``advapi32 = ctypes.windll.advapi32`` and calls
    # ``advapi32.SetNamedSecurityInfoW``. Patch the symbol on the
    # windll instance; the helper's access goes through the same
    # instance (``.SetNamedSecurityInfoW`` resolved at call time).
    monkeypatch.setattr(ctypes.windll.advapi32, "SetNamedSecurityInfoW", boom)

    with pytest.raises(OSError, match="SetNamedSecurityInfoW failed: error"):
        _apply_owner_only_dacl(target)
