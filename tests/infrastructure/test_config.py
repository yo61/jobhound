from __future__ import annotations

from pathlib import Path

import pytest

from jobhound.infrastructure.config import load_config


def _write(cfg_home: Path, body: str) -> None:
    d = cfg_home / "jh"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.toml").write_text(body)


def test_cookie_fields_default_when_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    cfg = load_config()
    assert cfg.allow_browser_cookie_access is False
    assert cfg.cookie_browser == "auto"
    assert cfg.cookie_browser_profile is None


def test_cookie_fields_read_from_toml(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _write(
        tmp_path / "config",
        'allow_browser_cookie_access = true\ncookie_browser = "firefox"\n'
        'cookie_browser_profile = "Work"\n',
    )
    cfg = load_config()
    assert cfg.allow_browser_cookie_access is True
    assert cfg.cookie_browser == "firefox"
    assert cfg.cookie_browser_profile == "Work"


def test_allow_browser_cookie_access_must_be_bool(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _write(tmp_path / "config", 'allow_browser_cookie_access = "yes"\n')
    with pytest.raises(ValueError):
        load_config()
