"""Runtime configuration: env vars, XDG TOML, defaults.

Path resolution lives in :mod:`prose_craft.paths`.

Configuration loads from five sources, in increasing priority:

1. **Defaults baked into the model** — :data:`DEFAULT_MODEL` and the
   XDG-derived :func:`prose_craft.paths.default_voices_root`.
2. **Shared XDG config files** —
   ``$XDG_CONFIG_DIRS/prose-craft/config.toml``, each in order
   (absent entries skipped; earlier entries win).
3. **The XDG config file** — ``$XDG_CONFIG_HOME/prose-craft/config.toml``,
   applied by :class:`XdgTomlSettingsSource`.
4. **Environment variables** — ``PROSE_CRAFT_MODEL`` and
   ``PROSE_CRAFT_VOICES_ROOT``, applied by
   :class:`LegacyEnvSettingsSource`.
5. **Explicit arguments** to :func:`load_settings` — win over every
   source above; used by the CLI for ``--model`` / ``--voices-root``.

The schema is strict: unknown keys, wrong-typed values, empty or
relative paths, and malformed TOML all surface as
:class:`ConfigurationError` carrying the offending file path so the
user can fix it.

The first-time configuration file is created by :func:`initialize_config`,
which writes the deterministic defaults via :func:`serialize_config` and
publishes them atomically with ``os.link`` so a half-written file can
never appear at :func:`config_file`.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
    TomlConfigSettingsSource,
)
from pydantic_core import ValidationError

from prose_craft import xdg
from prose_craft.paths import APP, default_voices_root

if sys.version_info >= (3, 11):
    import tomllib  # pragma: no cover - 3.10 is the lowest supported interpreter
else:
    import tomli as tomllib

__all__ = [
    "DEFAULT_MODEL",
    "PathsSettings",
    "ProseCraftSettings",
    "ConfigurationError",
    "ConfigAlreadyExists",
    "config_file",
    "get_model",
    "initialize_config",
    "load_settings",
    "serialize_config",
]

DEFAULT_MODEL = "anthropic:claude-opus-4-5"


def get_model() -> str:
    """Return the configured model identifier.

    Reads ``PROSE_CRAFT_MODEL`` from the environment; falls back to
    ``DEFAULT_MODEL``. Preserved as a public shim so downstream callers
    can migrate to :func:`load_settings` at their own pace; the new
    contract supersedes this once :class:`ProseCraft` callers migrate.
    """
    return os.environ.get("PROSE_CRAFT_MODEL", DEFAULT_MODEL)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class PathsSettings(BaseModel):
    """Path-shaped configuration. ``extra=forbid`` rejects unknown keys."""

    model_config = ConfigDict(extra="forbid")

    voices_root: Path | None = None

    @field_validator("voices_root", mode="before")
    @classmethod
    def validate_voices_root(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, (str, Path)):
            return value
        raw = str(value)
        if not raw:
            raise ValueError("paths.voices_root must not be empty")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise ValueError("paths.voices_root must be an absolute path")
        return path


class ProseCraftSettings(BaseSettings):
    """Top-level settings; ``extra=forbid`` and ordered custom sources."""

    model_config = SettingsConfigDict(extra="forbid")

    model: str = DEFAULT_MODEL
    paths: PathsSettings = Field(default_factory=PathsSettings)

    @field_validator("model", mode="before")
    @classmethod
    def _validate_model(cls, value: object) -> object:
        """Reject an empty or whitespace-only model from any source.

        A bare default would silently mask an explicit-but-broken override
        ("I set PROSE_CRAFT_MODEL and prose is using the default — why?");
        every source that produces a model string — TOML, environment,
        explicit kwargs — runs through the same validator so the failure
        mode is uniform. Whitespace inside the string is preserved.
        """
        if not isinstance(value, str):
            return value
        if not value.strip():
            raise ValueError("model must not be empty or whitespace-only")
        return value

    @property
    def voices_root(self) -> Path:
        """Effective voices directory: configured or XDG default."""
        return self.paths.voices_root or default_voices_root()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Order: init → env → user-toml → shared-toml(s).

        In pydantic-settings, the first source returned has the highest
        priority. The chain here, from highest to lowest:

        1. ``init_settings`` — explicit kwargs to ``load_settings``
        2. ``LegacyEnvSettingsSource`` — ``PROSE_CRAFT_*`` env vars
        3. ``XdgTomlSettingsSource`` — ``$XDG_CONFIG_HOME/prose-craft/config.toml``
        4. ``XdgSharedTomlSettingsSource`` per config-dir entry —
           ``$XDG_CONFIG_DIRS/prose-craft/config.toml`` (earlier dir wins)

        Built-in defaults on the model itself fill any field the chain
        leaves unset.
        """
        del env_settings, dotenv_settings, file_secret_settings
        from prose_craft import xdg

        shared = tuple(
            XdgSharedTomlSettingsSource(settings_cls, d / APP / "config.toml")
            for d in xdg.config_dirs()
            if (d / APP / "config.toml").is_file()
        )
        return (
            init_settings,
            LegacyEnvSettingsSource(settings_cls),
            XdgTomlSettingsSource(settings_cls),
            *shared,
        )


# ---------------------------------------------------------------------------
# Custom sources
# ---------------------------------------------------------------------------


class LegacyEnvSettingsSource(PydanticBaseSettingsSource):
    """Flat ``PROSE_CRAFT_*`` environment variables.

    ``PROSE_CRAFT_VOICES_ROOT`` is validated by :func:`prose_craft.xdg.env_path`,
    so empty / relative / unset values simply produce no entry — the
    configured default stands.
    """

    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        model = os.environ.get("PROSE_CRAFT_MODEL")
        if model is not None:
            values["model"] = model
        voices_root = xdg.env_path("PROSE_CRAFT_VOICES_ROOT")
        if voices_root is not None:
            values["paths"] = {"voices_root": voices_root}
        return values


class XdgTomlSettingsSource(TomlConfigSettingsSource):
    """The single XDG config file at :func:`config_file`."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls, toml_file=config_file())


class XdgSharedTomlSettingsSource(TomlConfigSettingsSource):
    """One ``<XDG_CONFIG_DIRS>/prose-craft/config.toml`` file.

    One instance is constructed per existing config-dir entry returned
    by :func:`prose_craft.xdg.config_dirs`, chained at the lowest
    priority in :meth:`ProseCraftSettings.settings_customise_sources`.
    Order matches ``xdg.config_dirs()`` output — earlier entries win
    over later ones, so the first config-dir on the search path takes
    precedence over the next.

    Eagerly validates the parsed TOML dict so that any
    :class:`pydantic.ValidationError` (unknown keys, wrong-typed
    values, empty/relative paths) is wrapped as
    :class:`ConfigurationError` carrying **this** file's path —
    rather than the user-config path that ``load_settings`` would
    otherwise attribute it to.
    """

    def __init__(self, settings_cls: type[BaseSettings], toml_file: Path) -> None:
        self.toml_file = toml_file
        try:
            super().__init__(settings_cls, toml_file=toml_file)
        except (tomllib.TOMLDecodeError, ValidationError, OSError) as exc:
            raise ConfigurationError(toml_file, str(exc)) from exc

    def __call__(self) -> dict[str, Any]:
        try:
            data = super().__call__()
            # Validate against the inner model-fields schema directly so
            # ``BaseSettings``'s custom init doesn't re-enter the source
            # chain and recurse. ``extra="forbid"`` reproduces the model's
            # default extras policy; the field validators on ``model`` and
            # ``paths.voices_root`` run as normal.
            TypeAdapter(
                cast("dict[str, Any]", ProseCraftSettings.__pydantic_core_schema__)["schema"]
            ).validate_python(data, extra="forbid")
            return data
        except ValidationError as exc:
            raise ConfigurationError(self.toml_file, str(exc)) from exc


# ---------------------------------------------------------------------------
# Loading boundary
# ---------------------------------------------------------------------------


class ConfigurationError(RuntimeError):
    """A config file failed validation. The offending path is on ``.path``.

    The default wording is "invalid" because the common case is a
    read-side validation failure (malformed TOML, unknown keys, wrong
    types). Write-side failures during :func:`initialize_config` pass
    ``kind="could not write"`` so the message accurately describes the
    failure mode — a permission error or a full disk is not an invalid
    configuration file.
    """

    def __init__(self, path: Path, detail: str, *, kind: str = "invalid") -> None:
        self.path = path
        super().__init__(f"{kind} configuration at {path}: {detail}")


class ConfigAlreadyExists(ConfigurationError):
    """The configuration file already exists; initialization was refused.

    The pre-existing file is left exactly as it was — :func:`initialize_config`
    does not parse it. The user can move it aside, or call
    :func:`load_settings` to inspect it.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        ConfigurationError.__init__(self, path, "configuration already exists")


def config_file() -> Path:
    """``<XDG_CONFIG_HOME>/prose-craft/config.toml``."""
    return xdg.config_home() / APP / "config.toml"


def load_settings(
    *,
    model: str | None = None,
    voices_root: Path | None = None,
) -> ProseCraftSettings:
    """Build :class:`ProseCraftSettings` honoring all four precedence layers.

    Explicit keyword arguments win over everything else; passing
    ``model=None`` does **not** mask an environment value the way an
    explicit ``model=""`` would — ``None`` means "leave this field to
    the next source down."
    """
    values: dict[str, object] = {}
    if model is not None:
        values["model"] = model
    if voices_root is not None:
        values["paths"] = {"voices_root": voices_root}
    try:
        return ProseCraftSettings(**_cast_settings_kwargs(values))
    except (SettingsError, ValidationError, tomllib.TOMLDecodeError, OSError) as exc:
        raise ConfigurationError(config_file(), str(exc)) from exc


def _cast_settings_kwargs(values: dict[str, object]) -> Any:
    """Bridge pydantic-settings' overloaded kwargs to a typed local dict.

    ``ty`` flags ``**dict[str, object]`` against each ``__init__`` overload;
    at runtime every value here is either a ``str`` or a ``PathsSettings``-
    shaped mapping, which the real ``__init__`` accepts.
    """
    return values


# ---------------------------------------------------------------------------
# First-time initialization
# ---------------------------------------------------------------------------


def serialize_config(model: str, voices_root: Path) -> str:
    """Render the configuration file body for ``(model, voices_root)``.

    ``json.dumps(..., ensure_ascii=False)`` produces a TOML basic string
    literal that is also a valid JSON string literal — escapes for
    backslashes, control characters, and the delimiter double-quote,
    with the actual UTF-8 bytes preserved for non-ASCII content.

    The non-default ``ensure_ascii=False`` is load-bearing: with
    ``ensure_ascii=True`` (the default), ``json.dumps`` encodes any
    non-ASCII code point as a UTF-16 surrogate pair (``\\uD83C\\uDF89``
    for U+1F389 🎉); TOML basic strings reject lone surrogates. The
    TOML spec mandates UTF-8 input, so writing the raw bytes is both
    safe and more readable than a hex-escape sequence.
    """
    return (
        f"model = {json.dumps(model, ensure_ascii=False)}\n\n"
        f"[paths]\nvoices_root = {json.dumps(str(voices_root), ensure_ascii=False)}\n"
    )


def initialize_config() -> Path:
    """Create the XDG config file with built-in defaults.

    Refuses to overwrite an existing file: raises :class:`ConfigAlreadyExists`
    and leaves the file untouched (it is not parsed). Publication is atomic
    via ``os.link`` so a reader either sees no file or the fully-written
    file — never a half-written one.

    Every step that touches the filesystem runs inside the ``try/except``
    boundary so a permission error at ``mkdir`` or ``mkstemp`` surfaces as
    :class:`ConfigurationError` carrying ``kind="could not write"`` and the
    CLI handler can exit 2 cleanly without printing a traceback.
    """
    target = config_file()
    if target.exists():
        raise ConfigAlreadyExists(target)
    fd = -1
    temporary: Path | None = None
    descriptor_open = False
    try:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
            )
        except OSError as exc:
            raise ConfigurationError(target, str(exc), kind="could not write") from exc
        temporary = Path(temporary_name)
        descriptor_open = True
        payload = serialize_config(DEFAULT_MODEL, default_voices_root())
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            descriptor_open = False
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ConfigAlreadyExists(target) from exc
        return target
    except ConfigAlreadyExists:
        raise
    except OSError as exc:
        raise ConfigurationError(target, str(exc), kind="could not write") from exc
    finally:
        if descriptor_open:
            os.close(fd)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
