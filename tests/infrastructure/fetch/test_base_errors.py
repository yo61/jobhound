from __future__ import annotations

from jobhound.infrastructure.fetch.base import (
    BrowserCookieAccessDeniedError,
    FetchError,
    NoBrowserSessionError,
)


def test_access_denied_is_fetch_error_with_actionable_message() -> None:
    exc = BrowserCookieAccessDeniedError()
    assert isinstance(exc, FetchError)
    assert "allow-browser-cookie-access" in str(exc)


def test_no_session_names_browser_and_profile() -> None:
    exc = NoBrowserSessionError("chrome", "Profile 1")
    assert isinstance(exc, FetchError)
    assert exc.browser == "chrome"
    assert exc.profile == "Profile 1"
    assert "chrome" in str(exc)
