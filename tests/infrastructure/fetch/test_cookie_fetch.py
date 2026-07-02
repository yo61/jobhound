# tests/infrastructure/fetch/test_cookie_fetch.py
from __future__ import annotations

import httpx
import pytest

from jobhound.infrastructure.fetch import cookie_fetch
from jobhound.infrastructure.fetch.base import FetchError, NoBrowserSessionError


def _transport(handler):
    return httpx.MockTransport(handler)


def test_replays_cookies_and_returns_html() -> None:
    seen = {}

    def reader(domain, browser, profile):
        seen["domain"] = domain
        return {"li_at": "SECRET"}

    def handler(request):
        seen["cookie_header"] = request.headers.get("cookie")
        return httpx.Response(200, text="<html>authed</html>")

    result = cookie_fetch.fetch(
        "https://www.linkedin.com/jobs/view/1",
        browser="chrome",
        read_cookies=reader,
        transport=_transport(handler),
    )

    assert result.html == "<html>authed</html>"
    assert seen["domain"] == "linkedin.com"  # registrable domain, not the host
    assert "li_at=SECRET" in seen["cookie_header"]


def test_no_cookies_raises_no_browser_session() -> None:
    def reader(domain, browser, profile):
        return {}

    with pytest.raises(NoBrowserSessionError):
        cookie_fetch.fetch(
            "https://www.linkedin.com/jobs/view/1",
            browser="chrome",
            profile="Work",
            read_cookies=reader,
            transport=_transport(lambda r: httpx.Response(200, text="x")),
        )


def test_reader_failure_wrapped_as_fetch_error() -> None:
    def reader(domain, browser, profile):
        raise RuntimeError("keychain denied")

    with pytest.raises(FetchError):
        cookie_fetch.fetch(
            "https://www.linkedin.com/jobs/view/1",
            browser="chrome",
            read_cookies=reader,
            transport=_transport(lambda r: httpx.Response(200, text="x")),
        )
