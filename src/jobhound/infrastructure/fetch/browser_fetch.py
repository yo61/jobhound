"""Tier-2 fetch: authenticated fetch via a persistent Playwright profile.

The fallback path, engaged only when tier 1 hits an auth wall. Playwright
is an optional extra (`jobhound[browser]`), imported lazily so the base
install can still use tier 1; a missing extra raises an actionable error.

The persistent profile lives under the XDG state dir, keyed by the site's
registrable domain, so a one-time `jh browser login` on www.linkedin.com
carries over to a later headless fetch on uk.linkedin.com.

The real browser paths (`fetch`, `login`) are not unit-tested (they drive
a live Chromium); they are exercised by an opt-in smoke test and manual
verification. The guard and session/profile logic are unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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

# Sites whose postings sit behind a login. Keyed by the `--site` argument.
_LOGIN_URLS: dict[str, str] = {
    "linkedin": "https://www.linkedin.com/login",
}


class UnknownBrowserSiteError(ValueError):
    """The requested `--site` has no known login flow."""

    def __init__(self, site: str) -> None:
        known = ", ".join(sorted(_LOGIN_URLS)) or "(none)"
        super().__init__(f"unknown browser site {site!r}; known sites: {known}")
        self.site = site


@dataclass(frozen=True)
class SessionStatus:
    """Whether a browser profile exists for a site, and when it was last used."""

    site: str
    profile_dir: Path
    exists: bool
    last_used: datetime | None


def _sync_playwright() -> Any:
    """Import Playwright lazily; raise an actionable error if the extra is absent."""
    try:
        # Optional `browser` extra — resolved at runtime, not in the base install.
        from playwright.sync_api import sync_playwright  # ty: ignore[unresolved-import]
    except ImportError as exc:
        raise FetchError(_EXTRA_MISSING) from exc
    return sync_playwright


def _registrable_domain(host: str) -> str:
    labels = host.lower().split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _profile_dir_for_host(host: str) -> Path:
    paths = paths_from_config(load_config())
    return paths.state_dir / "browser" / _registrable_domain(host or "unknown")


def default_profile_dir(url: str) -> Path:
    """The persistent Playwright profile directory for `url`'s site."""
    return _profile_dir_for_host(urlparse(url).hostname or "unknown")


def _login_url(site: str) -> str:
    try:
        return _LOGIN_URLS[site]
    except KeyError as exc:
        raise UnknownBrowserSiteError(site) from exc


def session_status(site: str) -> SessionStatus:
    """Report whether a logged-in profile exists for `site` and when last used."""
    host = urlparse(_login_url(site)).hostname or ""
    profile_dir = _profile_dir_for_host(host)
    exists = profile_dir.is_dir() and any(profile_dir.iterdir())
    last_used = (
        datetime.fromtimestamp(profile_dir.stat().st_mtime, tz=UTC)
        if profile_dir.exists()
        else None
    )
    return SessionStatus(site=site, profile_dir=profile_dir, exists=exists, last_used=last_used)


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


def login(site: str) -> Path:
    """Open a headed browser at `site`'s login page; block until the user closes it.

    Returns the profile directory the session was saved to.
    """
    sync_playwright = _sync_playwright()
    login_url = _login_url(site)
    user_data_dir = _profile_dir_for_host(urlparse(login_url).hostname or "")
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(str(user_data_dir), headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(login_url)
        try:
            # Block until the user finishes and closes the window.
            page.wait_for_event("close", timeout=0)
        finally:
            context.close()
    return user_data_dir
