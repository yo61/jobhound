"""Load `~/.config/jh/config.toml` honouring XDG environment variables."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w
from xdg_base_dirs import xdg_config_home, xdg_data_home


@dataclass(frozen=True)
class Config:
    """User-tunable settings for the `jh` CLI."""

    db_path: Path
    auto_commit: bool
    editor: str
    allow_browser_cookie_access: bool = False
    cookie_browser: str = "auto"
    cookie_browser_profile: str | None = None


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

    allow_cookies = data.get("allow_browser_cookie_access", False)
    if not isinstance(allow_cookies, bool):
        raise ValueError(
            f"config.toml: allow_browser_cookie_access must be a boolean, got {allow_cookies!r}"
        )

    cookie_browser = data.get("cookie_browser", "auto")
    if not isinstance(cookie_browser, str):
        raise ValueError(f"config.toml: cookie_browser must be a string, got {cookie_browser!r}")

    cookie_profile = data.get("cookie_browser_profile")
    if cookie_profile is not None and not isinstance(cookie_profile, str):
        raise ValueError(
            f"config.toml: cookie_browser_profile must be a string, got {cookie_profile!r}"
        )

    return Config(
        db_path=db_path,
        auto_commit=auto_commit,
        editor=editor,
        allow_browser_cookie_access=allow_cookies,
        cookie_browser=cookie_browser,
        cookie_browser_profile=cookie_profile,
    )


KNOWN_BROWSERS: frozenset[str] = frozenset(
    {"auto", "chrome", "chromium", "brave", "edge", "firefox", "safari", "opera", "vivaldi"}
)

# CLI kebab key -> TOML snake key. db_path is intentionally omitted.
SETTABLE_KEYS: dict[str, str] = {
    "allow-browser-cookie-access": "allow_browser_cookie_access",
    "cookie-browser": "cookie_browser",
    "cookie-browser-profile": "cookie_browser_profile",
    "auto-commit": "auto_commit",
    "editor": "editor",
}
_BOOL_KEYS: frozenset[str] = frozenset({"allow-browser-cookie-access", "auto-commit"})


class UnknownConfigKeyError(ValueError):
    def __init__(self, key: str) -> None:
        allowed = ", ".join(sorted(SETTABLE_KEYS))
        super().__init__(f"unknown config key {key!r}; settable keys: {allowed}")
        self.key = key


class InvalidConfigValueError(ValueError):
    def __init__(self, key: str, value: str, reason: str) -> None:
        super().__init__(f"invalid value {value!r} for {key}: {reason}")
        self.key = key
        self.value = value


def config_values() -> dict[str, object]:
    """Effective config as a kebab-keyed dict (includes db-path, read-only)."""
    cfg = load_config()
    return {
        "db-path": str(cfg.db_path),
        "auto-commit": cfg.auto_commit,
        "editor": cfg.editor,
        "allow-browser-cookie-access": cfg.allow_browser_cookie_access,
        "cookie-browser": cfg.cookie_browser,
        "cookie-browser-profile": cfg.cookie_browser_profile,
    }


def _coerce(key: str, value: str) -> bool | str:
    if key in _BOOL_KEYS:
        if value.lower() in ("true", "1", "yes"):
            return True
        if value.lower() in ("false", "0", "no"):
            return False
        raise InvalidConfigValueError(key, value, "expected true or false")
    if key == "cookie-browser" and value not in KNOWN_BROWSERS:
        raise InvalidConfigValueError(
            key, value, f"expected one of {', '.join(sorted(KNOWN_BROWSERS))}"
        )
    return value


def set_config_value(key: str, value: str) -> None:
    """Validate `value` for `key` and persist it to config.toml (preserving other keys)."""
    if key not in SETTABLE_KEYS:
        raise UnknownConfigKeyError(key)
    coerced = _coerce(key, value)
    path = config_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {}
    if path.exists():
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    data[SETTABLE_KEYS[key]] = coerced
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)
