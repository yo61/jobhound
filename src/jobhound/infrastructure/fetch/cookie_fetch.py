"""Tier-2 fetch: replay the user's existing browser session cookies via httpx.

Reads cookies scoped to the target site's registrable domain from a
configured browser/profile and replays them with the tier-1 httpx client.
The session token is used transiently and never persisted.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from jobhound.infrastructure.fetch.base import FetchError, FetchResult, NoBrowserSessionError
from jobhound.infrastructure.fetch.default_browser import detect_default_browser

CookieReader = Callable[[str, str, str | None], dict[str, str]]

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_TIMEOUT = 20.0


def _registrable_domain(host: str) -> str:
    labels = host.lower().split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _resolve_browser(browser: str) -> str:
    if browser != "auto":
        return browser
    detected = detect_default_browser()
    if detected is None:
        raise FetchError("could not detect the default browser; set `cookie-browser`")
    return detected


def _default_read_cookies(domain: str, browser: str, profile: str | None) -> dict[str, str]:
    import browser_cookie3 as bc3  # lazy: pulls pycryptodomex

    func = getattr(bc3, browser, None)
    if func is None:
        raise FetchError(f"unsupported cookie browser: {browser!r}")
    try:
        jar = func(domain_name=domain)
    except Exception as exc:  # browser_cookie3 raises many types
        raise FetchError(f"could not read {browser} cookies: {exc}") from exc
    return {c.name: c.value for c in jar if c.value}


def fetch(
    url: str,
    *,
    browser: str,
    profile: str | None = None,
    read_cookies: CookieReader | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FetchResult:
    """Fetch `url` authenticated with reused browser cookies for its domain."""
    read_cookies = read_cookies or _default_read_cookies
    resolved = _resolve_browser(browser)
    domain = _registrable_domain(urlparse(url).hostname or "")

    try:
        cookies = read_cookies(domain, resolved, profile)
    except FetchError:
        raise
    except Exception as exc:
        raise FetchError(f"could not read {resolved} cookies: {exc}") from exc

    if not cookies:
        raise NoBrowserSessionError(resolved, profile)

    try:
        with httpx.Client(
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        ) as client:
            response = client.get(url, cookies=cookies)
    except httpx.HTTPError as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc

    return FetchResult(final_url=str(response.url), html=response.text)
