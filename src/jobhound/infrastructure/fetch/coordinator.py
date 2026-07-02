"""Two-tier fetch: unauthenticated HTTP first, cookie reuse as a gated fallback.

Tier 1 (`http_fetch`) handles the common case. On an auth wall, tier 2
(`cookie_fetch`) reuses the user's browser session cookies — but only if the
user has granted `allow_browser_cookie_access`. Otherwise the auth wall is
surfaced as an actionable error.
"""

from __future__ import annotations

from collections.abc import Callable

from jobhound.infrastructure.config import Config, load_config
from jobhound.infrastructure.fetch import http_fetch
from jobhound.infrastructure.fetch.base import (
    AuthWallError,
    BrowserCookieAccessDeniedError,
    FetchResult,
)

Tier = Callable[[str], FetchResult]


def _cookie_tier(config: Config) -> Tier:
    from jobhound.infrastructure.fetch import cookie_fetch

    def tier2(url: str) -> FetchResult:
        return cookie_fetch.fetch(
            url, browser=config.cookie_browser, profile=config.cookie_browser_profile
        )

    return tier2


def fetch(
    url: str,
    *,
    tier1: Tier | None = None,
    tier2: Tier | None = None,
    config: Config | None = None,
) -> FetchResult:
    """Fetch `url`, escalating to cookie reuse on an auth wall when permitted."""
    config = config or load_config()
    tier1 = tier1 or http_fetch.fetch
    try:
        return tier1(url)
    except AuthWallError:
        if not config.allow_browser_cookie_access:
            raise BrowserCookieAccessDeniedError() from None
        tier2 = tier2 or _cookie_tier(config)
        return tier2(url)
