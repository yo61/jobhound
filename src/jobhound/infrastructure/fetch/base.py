"""Shared fetch result type and error taxonomy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FetchResult:
    """The HTML of a fetched page plus the URL it finally resolved to."""

    final_url: str
    html: str


class FetchError(Exception):
    """Base class for fetch failures."""


class AuthWallError(FetchError):
    """Tier-1 fetch was blocked (auth wall / rate limit); escalate to tier 2."""

    def __init__(self, url: str, status: int | None = None) -> None:
        super().__init__(f"auth wall fetching {url}" + (f" (HTTP {status})" if status else ""))
        self.url = url
        self.status = status


class BrowserCookieAccessDeniedError(FetchError):
    """Tier-1 was blocked, but reading browser cookies is not permitted."""

    def __init__(self) -> None:
        super().__init__(
            "this posting needs a login; enable with "
            "`jh config set allow-browser-cookie-access true`"
        )


class NoBrowserSessionError(FetchError):
    """Cookie access is permitted, but no session cookies were found."""

    def __init__(self, browser: str, profile: str | None = None) -> None:
        where = browser + (f" (profile {profile})" if profile else "")
        super().__init__(
            f"no session cookies found in {where}; log in there, or set "
            "cookie-browser / cookie-browser-profile"
        )
        self.browser = browser
        self.profile = profile


class SessionRequiredError(FetchError):
    """Tier-2 fetch needs a logged-in browser profile that isn't present."""

    def __init__(self, site: str) -> None:
        super().__init__(f"no valid {site} session; run `jh browser login`")
        self.site = site
