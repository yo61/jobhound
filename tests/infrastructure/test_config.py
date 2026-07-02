from __future__ import annotations

from pathlib import Path

import pytest

from jobhound.infrastructure.config import (
    InvalidConfigValueError,
    UnknownConfigKeyError,
    config_values,
    load_config,
    set_config_value,
)


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


def test_set_and_read_back_bool(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    set_config_value("allow-browser-cookie-access", "true")
    assert load_config().allow_browser_cookie_access is True
    assert config_values()["allow-browser-cookie-access"] is True


def test_set_preserves_other_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    set_config_value("editor", "vim")
    set_config_value("cookie-browser", "chrome")
    assert load_config().editor == "vim"
    assert load_config().cookie_browser == "chrome"


def test_set_unknown_key_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with pytest.raises(UnknownConfigKeyError):
        set_config_value("db-path", "/tmp/x")


def test_set_invalid_browser_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with pytest.raises(InvalidConfigValueError):
        set_config_value("cookie-browser", "netscape")


def test_set_invalid_bool_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with pytest.raises(InvalidConfigValueError):
        set_config_value("allow-browser-cookie-access", "maybe")


def test_cookie_browser_must_be_str(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _write(tmp_path / "config", "cookie_browser = 42\n")
    with pytest.raises(ValueError):
        load_config()


def test_cookie_browser_profile_must_be_str_if_set(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _write(tmp_path / "config", "cookie_browser_profile = true\n")
    with pytest.raises(ValueError):
        load_config()
