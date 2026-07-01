"""Tier-2 fetch: authenticated fetch via a persistent Playwright profile.

The fallback path, engaged only when tier 1 hits an auth wall. Playwright
is an optional extra (`jobhound[browser]`), imported lazily so the base
install can still use tier 1; a missing extra raises an actionable error.

The persistent profile lives under the XDG state dir, one per host, so a
one-time `jh browser login` carries over to later headless fetches.

The real browser path is not unit-tested (it drives a live Chromium); it
is exercised by an opt-in smoke test and manual verification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.fetch.base import FetchError, FetchResult
from jobhound.infrastructure.paths import paths_from_config

_EXTRA_MISSING = (
    "the browser fetch tier needs Playwright. Install it with "
    '"pip install \'jobhound[browser]\'" then run "playwright install chromium".'
)
_NAV_TIMEOUT_MS = 30_000


def _sync_playwright() -> Any:
    """Import Playwright lazily; raise an actionable error if the extra is absent."""
    try:
        # Optional `browser` extra — resolved at runtime, not in the base install.
        from playwright.sync_api import sync_playwright  # ty: ignore[unresolved-import]
    except ImportError as exc:
        raise FetchError(_EXTRA_MISSING) from exc
    return sync_playwright


def default_profile_dir(url: str) -> Path:
    """The persistent Playwright profile directory for `url`'s host."""
    host = (urlparse(url).hostname or "unknown").lower()
    paths = paths_from_config(load_config())
    return paths.state_dir / "browser" / host


def fetch(url: str, *, profile_dir: Path | None = None) -> FetchResult:
    """Fetch `url` headless against the persistent browser profile."""
    sync_playwright = _sync_playwright()
    user_data_dir = profile_dir or default_profile_dir(url)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(str(user_data_dir), headless=True)
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
            return FetchResult(final_url=page.url, html=page.content())
        finally:
            context.close()
