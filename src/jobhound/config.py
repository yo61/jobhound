"""Load `~/.config/jh/config.toml` honouring XDG environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """User-tunable settings for the `jh` CLI."""

    db_path: Path
    auto_commit: bool
    editor: str


def _xdg_dir(env_var: str, fallback: str) -> Path:
    """Return $env_var if set, else $HOME/<fallback>. Strict XDG semantics."""
    value = os.environ.get(env_var)
    if value:
        return Path(value)
    return Path.home() / fallback


def xdg_config_home() -> Path:
    return _xdg_dir("XDG_CONFIG_HOME", ".config")


def xdg_data_home() -> Path:
    return _xdg_dir("XDG_DATA_HOME", ".local/share")


def xdg_cache_home() -> Path:
    return _xdg_dir("XDG_CACHE_HOME", ".cache")


def xdg_state_home() -> Path:
    return _xdg_dir("XDG_STATE_HOME", ".local/state")


def default_db_path() -> Path:
    return xdg_data_home() / "jh"


def config_file_path() -> Path:
    return xdg_config_home() / "jh" / "config.toml"


def load_config() -> Config:
    """Read config.toml (if present) and return a Config with defaults filled in."""
    path = config_file_path()
    data: dict[str, object] = {}
    if path.exists():
        with path.open("rb") as fh:
            data = tomllib.load(fh)

    raw_db_path = data.get("db_path")
    db_path = Path(raw_db_path).expanduser() if isinstance(raw_db_path, str) else default_db_path()

    auto_commit = data.get("auto_commit", True)
    if not isinstance(auto_commit, bool):
        raise ValueError(f"config.toml: auto_commit must be a boolean, got {auto_commit!r}")

    editor = data.get("editor", "")
    if not isinstance(editor, str):
        raise ValueError(f"config.toml: editor must be a string, got {editor!r}")

    return Config(db_path=db_path, auto_commit=auto_commit, editor=editor)
