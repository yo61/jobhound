"""Tests for the tier-1 unauthenticated HTTP fetch adapter.

An httpx MockTransport is injected so these exercise the adapter's real
request configuration (browser UA, redirect following) with no network.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from jobhound.infrastructure.fetch import http_fetch
from jobhound.infrastructure.fetch.base import AuthWallError, FetchError

Handler = Callable[[httpx.Request], httpx.Response]


def _transport(handler: Handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_returns_html_and_final_url_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>ok</html>")

    result = http_fetch.fetch("https://example.com/jobs/1", transport=_transport(handler))

    assert result.html == "<html>ok</html>"
    assert result.final_url == "https://example.com/jobs/1"


def test_sends_a_browser_user_agent() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent")
        return httpx.Response(200, text="ok")

    http_fetch.fetch("https://example.com/1", transport=_transport(handler))

    assert seen["ua"] is not None and "Mozilla" in seen["ua"]


def test_follows_redirects_and_reports_final_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/short":
            return httpx.Response(301, headers={"location": "https://example.com/full"})
        return httpx.Response(200, text="ok")

    result = http_fetch.fetch("https://example.com/short", transport=_transport(handler))

    assert result.final_url == "https://example.com/full"


@pytest.mark.parametrize("status", [401, 403, 429])
def test_auth_wall_statuses_raise_auth_wall_error(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="blocked")

    with pytest.raises(AuthWallError):
        http_fetch.fetch("https://www.linkedin.com/jobs/view/1", transport=_transport(handler))


def test_server_error_raises_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(FetchError):
        http_fetch.fetch("https://example.com/1", transport=_transport(handler))


def test_transport_failure_raises_fetch_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(FetchError):
        http_fetch.fetch("https://example.com/1", transport=_transport(handler))
