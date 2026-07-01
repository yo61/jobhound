from __future__ import annotations


def test_config_set_then_get(tmp_jh, invoke) -> None:
    r = invoke(["config", "set", "cookie-browser", "chrome"])
    assert r.exit_code == 0, r.output
    r = invoke(["config", "get", "cookie-browser"])
    assert r.exit_code == 0, r.output
    assert "chrome" in r.output


def test_config_get_all_lists_cookie_keys(tmp_jh, invoke) -> None:
    r = invoke(["config", "get"])
    assert r.exit_code == 0, r.output
    assert "allow-browser-cookie-access" in r.output


def test_config_set_unknown_key_errors(tmp_jh, invoke) -> None:
    r = invoke(["config", "set", "db-path", "/tmp/x"])
    assert r.exit_code == 1
    assert "unknown config key" in r.output.lower()
