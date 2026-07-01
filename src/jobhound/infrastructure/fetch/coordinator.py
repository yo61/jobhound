"""Two-tier fetch: cheap unauthenticated HTTP first, browser profile fallback.

Tier 1 (`http_fetch`) handles the common case with no login. Only when it
hits an auth wall does tier 2 (`browser_fetch`, an optional Playwright
extra) engage. The browser tier is imported lazily so the base install
without the `browser` extra can still use tier 1.
"""

from __future__ import annotations

from collections.abc import Callable

from jobhound.infrastructure.fetch import http_fetch
from jobhound.infrastructure.fetch.base import AuthWallError, FetchResult

Tier = Callable[[str], FetchResult]


def _browser_fetch(url: str) -> FetchResult:
    from jobhound.infrastructure.fetch import browser_fetch

    return browser_fetch.fetch(url)


def fetch(url: str, *, tier1: Tier | None = None, tier2: Tier | None = None) -> FetchResult:
    """Fetch `url`, escalating from HTTP to the browser tier on an auth wall."""
    tier1 = tier1 or http_fetch.fetch
    tier2 = tier2 or _browser_fetch
    try:
        return tier1(url)
    except AuthWallError:
        return tier2(url)
