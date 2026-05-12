"""Load `~/.config/jh/config.toml` honouring XDG environment variables."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from xdg_base_dirs import xdg_config_home, xdg_data_home


@dataclass(frozen=True)
class Config:
    """User-tunable settings for the `jh` CLI."""

    db_path: Path
    auto_commit: bool
    editor: str


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
