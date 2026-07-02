"""`jh config` — read and set jobhound configuration (config.toml)."""

from __future__ import annotations

import sys

from cyclopts import App

from jobhound.infrastructure.config import (
    InvalidConfigValueError,
    UnknownConfigKeyError,
    config_values,
    set_config_value,
)

app = App(name="config", help="Read and set jobhound configuration.")


@app.command(name="get")
def get(key: str | None = None, /) -> None:
    """Print one config value, or all of them."""
    values = config_values()
    if key is None:
        for name, value in values.items():
            print(f"{name} = {value!r}")
        return
    if key not in values:
        print(f"config: unknown config key {key!r}", file=sys.stderr)
        raise SystemExit(1)
    print(values[key])


@app.command(name="set")
def set_(key: str, value: str, /) -> None:
    """Set a config value (persisted to config.toml)."""
    try:
        set_config_value(key, value)
    except (UnknownConfigKeyError, InvalidConfigValueError) as exc:
        print(f"config: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"{key} = {config_values()[key]!r}")
