"""Tier-2 fetch: replay the user's existing browser session cookies via httpx.

Reads cookies scoped to the target site's registrable domain from a
configured browser/profile and replays them with the tier-1 httpx client.
Cookie scoping uses each cookie's own domain attribute (RFC 6265), so only
cookies whose domain matches the target host are sent — including on redirects.
The session token is used transiently and never persisted.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from jobhound.infrastructure.fetch.base import FetchError, FetchResult, NoBrowserSessionError
from jobhound.infrastructure.fetch.default_browser import detect_default_browser


@dataclass(frozen=True)
class BrowserCookie:
    """A single browser cookie carrying its own domain/path scope."""

    name: str
    value: str
    domain: str
    path: str


CookieReader = Callable[[str, str, str | None], list[BrowserCookie]]

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_TIMEOUT = 20.0


def _registrable_domain(host: str) -> str:
    """Return a coarse registrable-domain hint used only as a read filter for browser_cookie3."""
    labels = host.lower().split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _matches_domain(host: str, cookie_domain: str) -> bool:
    """RFC 6265 §5.1.3 domain-match: host matches cookie_domain."""
    d = cookie_domain.lstrip(".")
    if not d:
        return False
    return host == d or host.endswith("." + d)


def _resolve_browser(browser: str) -> str:
    if browser != "auto":
        return browser
    detected = detect_default_browser()
    if detected is None:
        raise FetchError("could not detect the default browser; set `cookie-browser`")
    return detected


def _default_read_cookies(domain: str, browser: str, profile: str | None) -> list[BrowserCookie]:
    import browser_cookie3 as bc3  # lazy: pulls pycryptodomex

    func = getattr(bc3, browser, None)
    if func is None:
        raise FetchError(f"unsupported cookie browser: {browser!r}")
    try:
        jar = func(domain_name=domain)
    except Exception as exc:  # browser_cookie3 raises many types
        raise FetchError(f"could not read {browser} cookies: {exc}") from exc
    return [
        BrowserCookie(
            name=c.name,
            value=c.value,
            domain=c.domain or "",
            path=c.path or "/",
        )
        for c in jar
        if c.value
    ]


def fetch(
    url: str,
    *,
    browser: str,
    profile: str | None = None,
    read_cookies: CookieReader | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FetchResult:
    """Fetch `url` authenticated with reused browser cookies for its domain.

    Cookies are filtered to those whose domain attribute (per RFC 6265) matches
    the target host before building the httpx jar, so cross-domain cookies and
    redirect targets outside the origin domain never receive session credentials.
    """
    read_cookies = read_cookies or _default_read_cookies
    resolved = _resolve_browser(browser)
    host = urlparse(url).hostname or ""
    domain = _registrable_domain(host)  # coarse hint for browser_cookie3, not a security boundary

    try:
        raw_cookies = read_cookies(domain, resolved, profile)
    except FetchError:
        raise
    except Exception as exc:
        raise FetchError(f"could not read {resolved} cookies: {exc}") from exc

    # Security: keep only cookies whose domain the target host matches (RFC 6265 §5.1.3).
    # httpx enforces the same check on every redirect hop via the client-level jar.
    filtered = [c for c in raw_cookies if _matches_domain(host, c.domain)]

    if not filtered:
        raise NoBrowserSessionError(resolved, profile)

    jar = httpx.Cookies()
    for c in filtered:
        jar.set(c.name, c.value, domain=c.domain, path=c.path)

    try:
        with httpx.Client(
            transport=transport,
            cookies=jar,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        ) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc

    return FetchResult(final_url=str(response.url), html=response.text)
