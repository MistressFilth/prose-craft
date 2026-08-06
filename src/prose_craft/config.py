"""Runtime configuration: env vars, XDG TOML, defaults.

Path resolution lives in :mod:`prose_craft.paths`.

Configuration loads from three sources, in increasing priority:

1. **Defaults baked into the model** — :data:`DEFAULT_MODEL` and the
   XDG-derived :func:`prose_craft.paths.default_voices_root`.
2. **The XDG config file** — ``$XDG_CONFIG_HOME/prose-craft/config.toml``,
   applied by :class:`XdgTomlSettingsSource`.
3. **Environment variables** — ``PROSE_CRAFT_MODEL`` and
   ``PROSE_CRAFT_VOICES_ROOT``, applied by
   :class:`LegacyEnvSettingsSource`.
4. **Explicit arguments** to :func:`load_settings` — win over every
   source above; used by the CLI for ``--model`` / ``--voices-root``.

The schema is strict: unknown keys, wrong-typed values, empty or
relative paths, and malformed TOML all surface as
:class:`ConfigurationError` carrying the offending file path so the
user can fix it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
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
    import tomllib
else:  # pragma: no cover - 3.11+ branch covered above
    import tomli as tomllib

__all__ = [
    "DEFAULT_MODEL",
    "PathsSettings",
    "ProseCraftSettings",
    "ConfigurationError",
    "config_file",
    "get_model",
    "load_settings",
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
        """Order: init → env → toml. Later sources lose to earlier ones."""
        del env_settings, dotenv_settings, file_secret_settings
        return (
            init_settings,
            LegacyEnvSettingsSource(settings_cls),
            XdgTomlSettingsSource(settings_cls),
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


# ---------------------------------------------------------------------------
# Loading boundary
# ---------------------------------------------------------------------------


class ConfigurationError(RuntimeError):
    """A config file failed validation. The offending path is on ``.path``."""

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        super().__init__(f"invalid configuration at {path}: {detail}")


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
