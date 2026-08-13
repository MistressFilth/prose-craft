"""Prose-craft's directory layout, composed from resolved roots.

Every application directory is defined here and nowhere else. This is
the module the rest of the codebase imports; :mod:`prose_craft.xdg` is
an implementation detail behind it.

The layout, by role:

=========================  ============================================
Voice profiles (data)      ``<data_root>/prose-craft/voices/``
Composer memory (state)    ``<state_root>/prose-craft/composer-state/``
Draft scratch (runtime)    ``<runtime_root>/prose-craft/scratch/``
=========================  ============================================

Only Linux gives each role its own root. macOS folds config and state
into the data directory; Windows folds all four into ``%LOCALAPPDATA%``.
Where they coincide, ``voices/`` and ``composer-state/`` end up
siblings. That is native behavior and is fine: the point of separating
them was to keep agent memory out of the voice library, and
``list_voices()`` globs ``<voices_root>/*/voice.md``, which never
matches a sibling.

The voices root honors ``PROSE_CRAFT_VOICES_ROOT`` and the XDG config
chain through :mod:`prose_craft.config`; this module only owns the
XDG-derived default. ``--voices-root`` is the per-invocation
equivalent.
"""

from __future__ import annotations

import os
from pathlib import Path

from prose_craft import xdg

APP = "prose-craft"

__all__ = [
    "APP",
    "app_data_dir",
    "app_runtime_dir",
    "app_state_dir",
    "composer_state_dir",
    "default_voices_root",
    "scratch_dir",
]


def app_data_dir() -> Path:
    """``<data_root>/prose-craft``. Not created."""
    return xdg.data_home() / APP


def app_state_dir() -> Path:
    """``<state_root>/prose-craft``. Not created."""
    return xdg.state_home() / APP


def app_runtime_dir() -> Path:
    """``<runtime_root>/prose-craft``, created.

    If the advertised runtime root cannot be used, fall back to
    ``<state_root>/prose-craft/run``. Environments routinely export
    ``XDG_RUNTIME_DIR`` without creating it — WSL, containers, cron, and
    ssh sessions with no login session all do — and the specification
    sanctions a replacement directory rather than a hard failure.

    Mode ``0700`` is applied on POSIX, where the specification asks for
    it, and is re-applied on every call so a loosened directory heals
    itself. It is skipped on Windows: ``os.chmod`` there honors only the
    read-only bit, so calling it would imply a guarantee that does not
    hold.
    """
    path = xdg.runtime_dir() / APP
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = xdg.state_home() / APP / "run"
        path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        _apply_owner_only_dacl(path)
    else:
        path.chmod(0o700)
    return path


def _apply_owner_only_dacl(path: Path) -> None:
    """Restrict ``path`` on Windows so only the current user can access it.

    POSIX has ``chmod(0o700)``; Windows honors only the read-only bit
    on ``os.chmod``, so we apply an explicit DACL via ctypes calling
    ``advapi32.dll`` directly. ``win32security`` is still imported
    for the SID lookups and the ``SE_FILE_OBJECT`` /
    ``DACL_SECURITY_INFORMATION`` constants, which work everywhere;
    the ``ACL`` wrapper is not used because ``AddAccessAllowedAce``
    returns error 1306 (revision mismatch) on the Python+pywin32
    builds this project supports — even when ``ACL().rev`` reports
    the revision we passed in.

    The runtime directory is created with this ACL so child dirs
    (``scratch/``) and files inherit the restriction: ACE 2 and ACE 4
    carry ``OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE | INHERIT_ONLY_ACE``
    so the allow and deny pair propagate onto every child created
    inside the directory.

    Raises :class:`RuntimeError` if any required module cannot be
    imported (Windows is rare enough that a missing wheel is a
    real possibility). Failure to apply the ACL raises
    :class:`OSError` rather than silently leaving the directory
    world-readable.
    """
    try:
        import ctypes  # type: ignore[import-not-found]
        from ctypes import wintypes  # type: ignore[import-not-found]
        import win32api  # type: ignore[import-not-found]  # ty: ignore[unresolved-import]
        import win32security  # type: ignore[import-not-found]  # ty: ignore[unresolved-import]
    except ImportError as exc:
        raise RuntimeError(
            "Windows runtime ACL requires pywin32 (win32api, win32security) and ctypes; "
            "install with `uv pip install 'prose-craft[windows]'` or `pip install pywin32`"
        ) from exc

    OBJECT_INHERIT_ACE = 0x1
    CONTAINER_INHERIT_ACE = 0x2
    INHERIT_ONLY_ACE = 0x8
    FILE_ALL_ACCESS = 0x1F01FF

    user_sid, _, _ = win32security.LookupAccountName(None, win32api.GetUserName())
    everyone_sid = win32security.ConvertStringSidToSid("S-1-1-0")

    user_bytes = bytes(user_sid)
    everyone_bytes = bytes(everyone_sid)

    advapi32 = ctypes.windll.advapi32  # ty: ignore[unresolved-attribute]

    # Build a DACL entirely via ctypes. The four ACEs are:
    # 1) access-allowed (owner, FILE_ALL_ACCESS) on the directory itself,
    # 2) access-allowed (owner, inherit-only) on future children,
    # 3) access-denied (Everyone, FILE_ALL_ACCESS) on the directory itself,
    # 4) access-denied (Everyone, inherit-only) on future children.
    acl_buf = (ctypes.c_byte * 4096)()
    user_buf = (ctypes.c_byte * len(user_bytes))(*user_bytes)
    everyone_buf = (ctypes.c_byte * len(everyone_bytes))(*everyone_bytes)

    advapi32.InitializeAcl.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
    advapi32.InitializeAcl.restype = wintypes.BOOL
    # ``AddAccessAllowedAceEx`` / ``AddAccessDeniedAceEx`` are the
    # *Ex variants that accept ``dwAceFlags``. Plain ``AddAccessAllowedAce``
    # has no flags parameter, so passing inheritance flags to it
    # silently writes them to the AccessMask slot instead. Always
    # using the Ex variants keeps the call shape uniform.
    advapi32.AddAccessAllowedAceEx.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    advapi32.AddAccessAllowedAceEx.restype = wintypes.BOOL
    advapi32.AddAccessDeniedAceEx.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    advapi32.AddAccessDeniedAceEx.restype = wintypes.BOOL

    ok = advapi32.InitializeAcl(acl_buf, len(acl_buf), 2)
    if not ok:
        last_err = ctypes.GetLastError()  # ty: ignore[unresolved-attribute]
        raise OSError(f"InitializeAcl failed: {last_err}")
    acl_ptr = ctypes.cast(acl_buf, ctypes.c_void_p)
    user_ptr = ctypes.cast(user_buf, ctypes.c_void_p)
    everyone_ptr = ctypes.cast(everyone_buf, ctypes.c_void_p)

    flags_child = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE | INHERIT_ONLY_ACE
    for fn, sid_ptr, flags in (
        (advapi32.AddAccessAllowedAceEx, user_ptr, 0),
        (advapi32.AddAccessAllowedAceEx, user_ptr, flags_child),
        (advapi32.AddAccessDeniedAceEx, everyone_ptr, 0),
        (advapi32.AddAccessDeniedAceEx, everyone_ptr, flags_child),
    ):
        ok = fn(acl_ptr, 2, flags, FILE_ALL_ACCESS, sid_ptr)
        if not ok:
            last_err = ctypes.GetLastError()  # ty: ignore[unresolved-attribute]
            raise OSError(f"AddAce failed: {last_err}")

    # Apply via SetNamedSecurityInfoW, NOT SetSecurityInfo. The ANSI
    # variant marshals the path string and rejects the ctypes buffer
    # with ERROR_INVALID_HANDLE; the W variant is what works.
    advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD
    err = advapi32.SetNamedSecurityInfoW(
        str(path),
        win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        acl_ptr,
        None,
    )
    if err != 0:
        raise OSError(f"SetNamedSecurityInfoW failed: error {err} on {path}")


# ACE type constants from winnt.h — mirrored here so test code does
# not have to import winnt headers just to interpret the integer type.
_ACE_TYPE_ACCESS_ALLOWED = 0
_ACE_TYPE_ACCESS_DENIED = 1
_ACE_TYPE_FLAGS_CHILD = 0x1 | 0x2 | 0x8  # OBJECT | CONTAINER | INHERIT_ONLY

# ACE_HEADER layout:
#   BYTE AceType
#   BYTE AceFlags
#   USHORT AceSize
# Followed by ACCESS_MASK (DWORD) and the SID. Full structure sizes:
#   ACCESS_ALLOWED_ACE = ACE_HEADER (4) + mask (4) + SID var
#   ACE_HEADER        : offset 0, size 4
#   ACCESS_MASK       : offset 4, size 4
#   SID start         : offset 8
_ACE_HEADER_SIZE = 4
_ACE_MASK_OFFSET = 4
_ACE_MASK_SIZE = 4
_ACE_SID_OFFSET = 8


def _read_dacl_ace_records(path: Path) -> list[tuple[int, int, int, str]]:
    """Return ``[(ace_type, ace_flags, mask, sid_string), ...]`` for ``path``'s DACL.

    Read-side counterpart to :func:`_apply_owner_only_dacl`. Mirrors
    the same ctypes approach because pywin32's ``ACL`` wrapper is
    unreliable for writing. Used by unit tests that need to verify
    the on-disk ACL after a code path runs.
    """
    import struct

    import ctypes
    from ctypes import wintypes
    import win32security  # type: ignore[import-not-found]  # ty: ignore[unresolved-import]

    advapi32 = ctypes.windll.advapi32  # ty: ignore[unresolved-attribute]

    # 1) Read the security descriptor's DACL pointer.
    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    p_owner = ctypes.c_void_p()
    p_group = ctypes.c_void_p()
    p_dacl = ctypes.c_void_p()
    p_sacl = ctypes.c_void_p()
    info = (
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION
    )
    err = advapi32.GetNamedSecurityInfoW(
        str(path),
        win32security.SE_FILE_OBJECT,
        info,
        ctypes.byref(p_owner),
        ctypes.byref(p_group),
        ctypes.byref(p_dacl),
        ctypes.byref(p_sacl),
    )
    if err != 0:
        raise OSError(f"GetNamedSecurityInfoW failed: error {err} on {path}")
    if not p_dacl.value:
        return []
    # NOTE: GetNamedSecurityInfoW returns the DACL pointer alongside
    # an internally-allocated SECURITY_DESCRIPTOR; the caller never
    # receives the SD handle, so the buffer cannot be LocalFree'd
    # safely. ``GetNamedSecurityInfoW`` documents freeing the SD via
    # LocalFree on a handle the function never exposes. We leak the
    # SD per call to stay correct (the components live inside the
    # self-relative SD; freeing the DACL pointer alone corrupts the
    # heap). The leak is bounded by test count and acceptable for a
    # test helper. A long-running caller would need a different
    # design.

    # 2) Read the ACL size information — class 2 = AclSizeInformation.
    # The structure is three DWORDs: AceCount, AclBytesInUse, AclBytesFree.
    advapi32.GetAclInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    advapi32.GetAclInformation.restype = wintypes.BOOL
    info_buf = (ctypes.c_byte * 12)()
    ok = advapi32.GetAclInformation(p_dacl, info_buf, 12, 2)
    if not ok:
        last_err = ctypes.GetLastError()  # ty: ignore[unresolved-attribute]
        raise OSError(f"GetAclInformation failed: {last_err}")
    ace_count = struct.unpack("<I", bytes(info_buf[:4]))[0]

    # 3) Walk each ACE: header (4 bytes), mask (4 bytes), SID (var).
    advapi32.GetAce.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetAce.restype = wintypes.BOOL
    records: list[tuple[int, int, int, str]] = []
    for i in range(ace_count):
        ace_ptr = ctypes.c_void_p()
        ok = advapi32.GetAce(p_dacl, i, ctypes.byref(ace_ptr))
        if not ok:
            last_err = ctypes.GetLastError()  # ty: ignore[unresolved-attribute]
            raise OSError(f"GetAce({i}) failed: {last_err}")
        # GetAce returns a pointer into the DACL buffer. Use ``c_void_p``
        # for byte arithmetic — ``LP_c_byte + int`` raises TypeError on
        # CPython 3.13+, so ``void_p`` is the only path that works on
        # every supported runtime.
        ace_addr = ace_ptr.value or 0
        header = (ctypes.c_byte * _ACE_HEADER_SIZE)()
        ctypes.memmove(header, ace_ptr, _ACE_HEADER_SIZE)
        ace_type = header[0]
        ace_flags = header[1]
        ace_size = struct.unpack("<H", bytes(header[2:4]))[0]

        mask_buf = (ctypes.c_byte * _ACE_MASK_SIZE)()
        ctypes.memmove(
            mask_buf,
            ctypes.c_void_p(ace_addr + _ACE_MASK_OFFSET),
            _ACE_MASK_SIZE,
        )
        mask = struct.unpack("<I", bytes(mask_buf))[0]

        sid_len = ace_size - _ACE_SID_OFFSET
        sid_buf = (ctypes.c_byte * sid_len)()
        ctypes.memmove(
            sid_buf,
            ctypes.c_void_p(ace_addr + _ACE_SID_OFFSET),
            sid_len,
        )
        # ``pywin32``'s ``ConvertSidToStringSid`` rejects a ctypes
        # void_p with ``TypeError: The object is not a PySID object``;
        # it accepts a ``PySID`` (constructed from raw bytes) or the
        # empty SID wrapper. Round-trip through ``bytes(sid_buf)`` to
        # keep the SID string comparison straightforward.
        sid_str = win32security.ConvertSidToStringSid(win32security.SID(bytes(sid_buf)))
        records.append((ace_type, ace_flags, mask, sid_str))
    return records


def default_voices_root() -> Path:
    """Return the XDG-derived default voice profile store without creating it."""
    return app_data_dir() / "voices"


def composer_state_dir() -> Path:
    """The composer agent's ``FileStore`` root. Not created."""
    return app_state_dir() / "composer-state"


def scratch_dir() -> Path:
    """Short-lived working files, created on demand."""
    path = app_runtime_dir() / "scratch"
    path.mkdir(parents=True, exist_ok=True)
    return path
