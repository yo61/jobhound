"""Tests for the tier-2 browser fetch adapter.

The real Chromium paths (`fetch`, `login`) aren't unit-tested; these cover
the extra-missing guard, the per-site profile directory, and session
status — all of which need no browser.
"""

from __future__ import annotations

import importlib.util

import pytest

from jobhound.infrastructure.fetch import browser_fetch
from jobhound.infrastructure.fetch.base import FetchError
from tests.conftest import JhEnv

_PLAYWRIGHT_INSTALLED = importlib.util.find_spec("playwright") is not None
_needs_missing_extra = pytest.mark.skipif(
    _PLAYWRIGHT_INSTALLED,
    reason="the missing-extra guard only fires when Playwright is absent",
)


@_needs_missing_extra
def test_fetch_without_playwright_raises_actionable_error() -> None:
    with pytest.raises(FetchError) as exc:
        browser_fetch.fetch("https://www.linkedin.com/jobs/view/1")

    message = str(exc.value).lower()
    assert "playwright" in message
    assert "jobhound[browser]" in message


@_needs_missing_extra
def test_login_without_playwright_raises_actionable_error() -> None:
    with pytest.raises(FetchError) as exc:
        browser_fetch.login("linkedin")

    assert "playwright" in str(exc.value).lower()


def test_profile_dir_is_keyed_by_registrable_domain(tmp_jh: JhEnv) -> None:
    # www. and uk. subdomains must share one profile so login carries over.
    www = browser_fetch.default_profile_dir("https://www.linkedin.com/jobs/view/1")
    uk = browser_fetch.default_profile_dir("https://uk.linkedin.com/jobs/view/1")

    assert www.name == "linkedin.com"
    assert www == uk
    assert "browser" in www.parts
    assert str(www).startswith(str(tmp_jh.state_home))


def test_session_status_absent_then_present(tmp_jh: JhEnv) -> None:
    status = browser_fetch.session_status("linkedin")
    assert status.exists is False

    # Simulate a completed login.
    status.profile_dir.mkdir(parents=True)
    (status.profile_dir / "Default").write_text("session")

    after = browser_fetch.session_status("linkedin")
    assert after.exists is True
    assert after.last_used is not None


def test_session_status_unknown_site_raises() -> None:
    with pytest.raises(browser_fetch.UnknownBrowserSiteError):
        browser_fetch.session_status("monster")
