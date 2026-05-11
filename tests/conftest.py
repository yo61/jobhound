"""Shared fixtures for CLI tests.

`tmp_jh` sets up an XDG-isolated environment and a freshly-initialised
data root, so each test gets a real `Paths` to operate on.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class JhEnv:
    config_home: Path
    data_home: Path
    cache_home: Path
    state_home: Path
    db_path: Path


@pytest.fixture
def tmp_jh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JhEnv:
    """Set up XDG dirs, a config that points at a tmp db, and `git init` the db."""
    config_home = tmp_path / "config"
    data_home = tmp_path / "data"
    cache_home = tmp_path / "cache"
    state_home = tmp_path / "state"
    for d in (config_home, data_home, cache_home, state_home):
        d.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))

    db_path = data_home / "jh"
    db_path.mkdir()
    subprocess.run(["git", "init", "--quiet", str(db_path)], check=True)
    subprocess.run(["git", "-C", str(db_path), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_path), "config", "user.email", "t@t"], check=True)
    (db_path / "opportunities").mkdir()
    (db_path / "archive").mkdir()
    (db_path / "_shared").mkdir()
    return JhEnv(config_home, data_home, cache_home, state_home, db_path)
