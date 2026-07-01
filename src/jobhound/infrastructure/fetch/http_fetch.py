"""Tier-1 fetch: an unauthenticated HTTP GET with a browser User-Agent.

The cheap path — no browser binary, no login. A live probe showed the
LinkedIn guest view is reachable this way for the common case. On an auth
wall / rate limit the caller escalates to the browser tier.
"""

from __future__ import annotations

import httpx

from jobhound.infrastructure.fetch.base import AuthWallError, FetchError, FetchResult

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_TIMEOUT = 20.0
_AUTH_WALL_STATUSES = frozenset({401, 403, 429})


def fetch(url: str, *, transport: httpx.BaseTransport | None = None) -> FetchResult:
    """Fetch `url` unauthenticated.

    Raises `AuthWallError` on a block/rate-limit status (so the caller can
    escalate to the browser tier) and `FetchError` on any other HTTP or
    transport failure. `transport` is an injection point for tests.
    """
    try:
        with httpx.Client(
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        ) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc

    if response.status_code in _AUTH_WALL_STATUSES:
        raise AuthWallError(url, response.status_code)
    if response.status_code >= 400:
        raise FetchError(f"fetching {url} returned HTTP {response.status_code}")

    return FetchResult(final_url=str(response.url), html=response.text)
