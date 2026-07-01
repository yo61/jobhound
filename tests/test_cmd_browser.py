"""Tests for the `jh browser` command group."""

from __future__ import annotations

import importlib.util

import pytest

_PLAYWRIGHT_INSTALLED = importlib.util.find_spec("playwright") is not None


def test_browser_status_reports_no_session(tmp_jh, invoke) -> None:
    result = invoke(["browser", "status"])

    assert result.exit_code == 0, result.output
    assert "no session" in result.output.lower()


def test_browser_status_unknown_site_errors(tmp_jh, invoke) -> None:
    result = invoke(["browser", "status", "--site", "monster"])

    assert result.exit_code == 1
    assert "unknown browser site" in result.output.lower()


@pytest.mark.skipif(
    _PLAYWRIGHT_INSTALLED,
    reason="login opens a real browser when Playwright is installed",
)
def test_browser_login_without_extra_reports_actionable_error(tmp_jh, invoke) -> None:
    result = invoke(["browser", "login"])

    assert result.exit_code == 1
    assert "playwright" in result.output.lower()
