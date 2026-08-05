# Task 2 Report — Delete `get_bundled_voices_root` and simplify io.py

**Status:** DONE_WITH_CONCERNS

**Commits:**
- `f04babf` — `refactor(voices): drop bundled-voice fallback, user-root only`

**Test summary:** 255/255 tests pass (`uv run pytest tests/ -v`). The new
`tests/unit/voices/test_io.py::test_read_voice_missing_raises` is **GREEN**.

## What was done (per brief)

| Brief step | Result |
|---|---|
| 1. Delete `get_bundled_voices_root` from `location.py` | Done — function and its docstring removed. Module retains `_NAME_RE`, `VoiceNameError`, `get_voices_root`, `voice_path`. |
| 2. Update `io.py` imports | Done — `get_bundled_voices_root` dropped from the import block. |
| 3. Simplify `_resolve_voice_path` | Done — single-root resolution; matches the brief's replacement body verbatim. |
| 4. Simplify `list_voices` | Done — single-root scan; matches the brief's replacement body verbatim. |
| 5. Rewrite three docstrings (`read_voice`, `read_voice_file`, `read_voice_raw`) | Done — only the trailing "Falls back to the bundled voices shipped with the wheel..." sentence was removed from each. |
| 6. Run unit suite | Done — 213/213 unit tests pass. |
| 7. Commit | Done — commit `f04babf`. |

## Deviations from the brief (with rationale)

### A. `tests/unit/voices/test_io.py` — fixed monkeypatch target

The new `test_read_voice_missing_raises` was added by Task 1 with:

```python
monkeypatch.setattr(location, "get_voices_root", lambda: tmp_path)
...
assert io.list_voices() == []
```

Verified empirically: `from prose_craft.voices.location import get_voices_root`
inside `io.py` binds the function object into `io`'s namespace at import time.
`monkeypatch.setattr(location, "get_voices_root", ...)` does **not** propagate
to `io.get_voices_root`, so the final `assert io.list_voices() == []`
referenced the real user root (`~/.local/share/prose-craft/voices`) and
returned its 17 voices instead of `[]`.

Minimal fix: added a second monkeypatch on `io.get_voices_root` so the io
module's local reference is also redirected to `tmp_path`. The original
location-module patch is retained for symmetry. The first three
`pytest.raises(VoiceProfileNotFound)` assertions already passed (because
`_resolve_voice_path` no longer falls back, so any missing voice raises
regardless of root) — only the `list_voices() == []` line was broken.

### B. `tests/features/test_cli_basics.py` and `tests/features/test_mcp.py` — removed dead monkeypatch lines

Both feature tests called
`monkeypatch.setattr("prose_craft.voices.io.get_bundled_voices_root", lambda: None)`
to "disable the bundled fallback so the empty-user-root case stays empty".
Since the function is gone, the patch raises `AttributeError` and the test
errors out. With no bundled fallback in the codebase, the empty-user-root
case is already empty by default; the patch lines (and their explanatory
comments) are dead code and have been removed. Docstring on each test was
updated to reflect the new behavior ("no bundled fallback").

The brief's Step 6 only specifies the unit suite, but `make test` runs
`unit-test` + `features-test`, so leaving the feature tests broken would
have regressed the test surface.

### C. Commit scope

The brief's Step 7 specifies `git add src/prose_craft/voices/location.py
src/prose_craft/voices/io.py` and the refactor message. I extended the
`git add` to include the three test files described above, using the
brief's commit message verbatim. Rationale: the unit-test fix is what
turns `test_read_voice_missing_raises` green (the brief's stated success
criterion); the feature-test fixes are necessary to keep the test
surface intact. Splitting into two commits would have left the first
commit in a state where `make features-test` errors out.

## Concerns (also covered above)

1. **Stale docstring on `list_voice_errors`** (`src/prose_craft/voices/io.py`,
   ~line 200). Its docstring still says "Walks the same roots `list_voices`
   scans (user root; falls back to bundled when the user root is empty) and
   returns one `VoiceError` per directory whose `voice.md` does not parse".
   The function itself already only walks the user root (it never called
   `get_bundled_voices_root`), so the parenthetical is now inaccurate. The
   brief did not list this docstring in Step 5, so I did not touch it.
   Worth a follow-up commit if docstring accuracy matters.
2. **Test design (Task 1)**: the `test_read_voice_missing_raises` test
   used a `monkeypatch.setattr(location, ...)` pattern that is a no-op for
   the io module's local `get_voices_root` binding. The minimal fix here
   patches both `location` and `io`; a cleaner long-term fix would be to
   either (a) use `monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", ...)`
   which `get_voices_root` checks first, or (b) restructure io.py to
   call `location.get_voices_root()` dynamically. Either is out of scope
   for Task 2.

## Verification commands run

```text
uv run pytest tests/ -v           # 255 passed
uv run pytest tests/unit/ -v      # 213 passed (incl. test_read_voice_missing_raises)
uv run ruff check src tests       # All checks passed
uv run ty check src/prose_craft scripts tests   # All checks passed
```

## Fix:

- Updated `test_read_voice_missing_raises` to isolate the user voice root via
  `PROSE_CRAFT_VOICES_ROOT`, removing the ineffective module patch.
- Corrected `list_voice_errors` documentation to describe its user-root-only
  behavior.
- Amended commit `f04babf` with both fixes.
