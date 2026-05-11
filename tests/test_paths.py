"""Tests for the Paths dataclass derived from Config."""

from pathlib import Path

import pytest

from jobhound.config import Config
from jobhound.paths import Paths, paths_from_config


def test_paths_layout(tmp_path: Path) -> None:
    cfg = Config(db_path=tmp_path / "db", auto_commit=True, editor="")
    paths = paths_from_config(cfg)
    assert paths.db_root == tmp_path / "db"
    assert paths.opportunities_dir == tmp_path / "db" / "opportunities"
    assert paths.archive_dir == tmp_path / "db" / "archive"
    assert paths.shared_dir == tmp_path / "db" / "_shared"


def test_paths_cache_uses_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    cfg = Config(db_path=tmp_path / "db", auto_commit=True, editor="")
    paths = paths_from_config(cfg)
    assert paths.cache_dir == tmp_path / "cache" / "jh"


def test_paths_state_uses_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    cfg = Config(db_path=tmp_path / "db", auto_commit=True, editor="")
    paths = paths_from_config(cfg)
    assert paths.state_dir == tmp_path / "state" / "jh"


def test_ensure_creates_required_dirs(tmp_path: Path) -> None:
    cfg = Config(db_path=tmp_path / "db", auto_commit=True, editor="")
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    assert paths.opportunities_dir.is_dir()
    assert paths.archive_dir.is_dir()
    assert paths.shared_dir.is_dir()
