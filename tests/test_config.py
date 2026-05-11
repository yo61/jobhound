"""Tests for config loading and XDG path resolution."""

from pathlib import Path

import pytest

from jobhound.config import load_config


@pytest.fixture
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point $XDG_CONFIG_HOME at a tmpdir and return the jh config dir."""
    config_home = tmp_path / "config"
    config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    return config_home / "jh"


def test_defaults_when_config_missing(xdg: Path) -> None:
    cfg = load_config()
    assert cfg.db_path == Path.home() / ".local" / "share" / "jh"
    assert cfg.auto_commit is True
    assert cfg.editor == ""


def test_overrides_from_config_file(xdg: Path) -> None:
    xdg.mkdir()
    (xdg / "config.toml").write_text(
        'db_path = "/tmp/foo"\nauto_commit = false\neditor = "code -w"\n'
    )
    cfg = load_config()
    assert cfg.db_path == Path("/tmp/foo")
    assert cfg.auto_commit is False
    assert cfg.editor == "code -w"


def test_tilde_in_db_path_is_expanded(xdg: Path) -> None:
    xdg.mkdir()
    (xdg / "config.toml").write_text('db_path = "~/mydata"\n')
    cfg = load_config()
    assert cfg.db_path == Path.home() / "mydata"


def test_xdg_data_home_changes_default_db_path(
    xdg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_home = tmp_path / "data"
    data_home.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    cfg = load_config()
    assert cfg.db_path == data_home / "jh"


def test_partial_config_uses_defaults_for_missing_fields(xdg: Path) -> None:
    xdg.mkdir()
    (xdg / "config.toml").write_text("auto_commit = false\n")
    cfg = load_config()
    assert cfg.auto_commit is False
    assert cfg.db_path == Path.home() / ".local" / "share" / "jh"
