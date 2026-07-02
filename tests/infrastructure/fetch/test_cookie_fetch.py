# tests/infrastructure/fetch/test_cookie_fetch.py
from __future__ import annotations

import httpx
import pytest

from jobhound.infrastructure.fetch import cookie_fetch
from jobhound.infrastructure.fetch.base import FetchError, NoBrowserSessionError
from jobhound.infrastructure.fetch.cookie_fetch import BrowserCookie


def _transport(handler):
    return httpx.MockTransport(handler)


def test_replays_cookies_and_returns_html() -> None:
    seen: dict[str, object] = {}

    def reader(domain, browser, profile):
        seen["domain"] = domain
        return [BrowserCookie(name="li_at", value="SECRET", domain=".linkedin.com", path="/")]

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
    assert "li_at=SECRET" in str(seen["cookie_header"])


def test_no_cookies_raises_no_browser_session() -> None:
    def reader(domain, browser, profile):
        return []

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


def test_cross_domain_cookies_are_filtered_out() -> None:
    """Cookies whose domain does not match the target host are never sent."""
    seen: dict[str, str | None] = {}

    def reader(domain, browser, profile):
        return [
            BrowserCookie(name="li_at", value="SECRET", domain=".linkedin.com", path="/"),
            BrowserCookie(name="evil_tok", value="EVIL", domain=".evil.com", path="/"),
        ]

    def handler(request):
        seen["cookie_header"] = request.headers.get("cookie")
        return httpx.Response(200, text="<html>ok</html>")

    cookie_fetch.fetch(
        "https://www.linkedin.com/jobs/view/1",
        browser="chrome",
        read_cookies=reader,
        transport=_transport(handler),
    )

    assert "li_at=SECRET" in (seen["cookie_header"] or "")
    assert "evil_tok" not in (seen["cookie_header"] or "")


def test_no_cookie_leak_on_cross_domain_redirect() -> None:
    """Session cookies are NOT forwarded when following a redirect to a different domain."""
    evil_cookie_header: list[str | None] = []

    def reader(domain, browser, profile):
        return [BrowserCookie(name="li_at", value="SECRET", domain=".linkedin.com", path="/")]

    def handler(request):
        if "linkedin.com" in request.url.host:
            return httpx.Response(301, headers={"Location": "https://evil.com/y"})
        # Record what cookie header (if any) evil.com receives
        evil_cookie_header.append(request.headers.get("cookie"))
        return httpx.Response(200, text="<html>evil</html>")

    cookie_fetch.fetch(
        "https://www.linkedin.com/x",
        browser="chrome",
        read_cookies=reader,
        transport=_transport(handler),
    )

    assert evil_cookie_header, "evil.com handler was never called"
    assert evil_cookie_header[0] is None, (
        f"Session cookie was leaked to evil.com: {evil_cookie_header[0]!r}"
    )
