"""`jh browser` subgroup — manage the persistent browser login profile.

Used only for the tier-2 authenticated fetch fallback: when `jh new --url`
hits an auth wall, a one-time `jh browser login` saves a session that later
headless fetches reuse.
"""

from __future__ import annotations

import sys

from cyclopts import App

from jobhound.infrastructure.fetch import browser_fetch
from jobhound.infrastructure.fetch.base import FetchError
from jobhound.infrastructure.fetch.browser_fetch import UnknownBrowserSiteError

app = App(name="browser", help="Manage the browser login profile for authenticated scraping.")


@app.command(name="login")
def login(*, site: str = "linkedin") -> None:
    """Open a browser to log in once; the session persists for later fetches."""
    try:
        profile_dir = browser_fetch.login(site)
    except (UnknownBrowserSiteError, FetchError) as exc:
        print(f"browser: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Saved {site} session to {profile_dir}")


@app.command(name="status")
def status(*, site: str = "linkedin") -> None:
    """Report whether a logged-in browser session exists for a site."""
    try:
        result = browser_fetch.session_status(site)
    except UnknownBrowserSiteError as exc:
        print(f"browser: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if result.exists:
        when = result.last_used.isoformat() if result.last_used else "unknown"
        print(f"{site}: session present (last used {when})")
    else:
        print(f"{site}: no session; run `jh browser login --site {site}`")
