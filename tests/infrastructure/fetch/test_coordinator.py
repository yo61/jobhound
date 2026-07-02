"""Tests for the two-tier fetch coordinator (cookie tier-2, config-gated)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobhound.infrastructure.config import Config
from jobhound.infrastructure.fetch import coordinator
from jobhound.infrastructure.fetch.base import (
    AuthWallError,
    BrowserCookieAccessDeniedError,
    FetchResult,
)


def _config(*, allow: bool) -> Config:
    return Config(
        db_path=Path("/tmp/x"), auto_commit=True, editor="", allow_browser_cookie_access=allow
    )


def test_tier1_success_skips_escalation() -> None:
    calls = []

    def tier1(url):
        calls.append("t1")
        return FetchResult(final_url=url, html="guest")

    def tier2(url):
        calls.append("t2")
        return FetchResult(final_url=url, html="auth")

    result = coordinator.fetch("https://x/1", tier1=tier1, tier2=tier2, config=_config(allow=True))
    assert result.html == "guest"
    assert calls == ["t1"]


def test_auth_wall_with_permission_escalates_to_cookie_tier() -> None:
    def tier1(url):
        raise AuthWallError(url, 403)

    def tier2(url):
        return FetchResult(final_url=url, html="auth")

    result = coordinator.fetch("https://x/1", tier1=tier1, tier2=tier2, config=_config(allow=True))
    assert result.html == "auth"


def test_auth_wall_without_permission_raises_access_denied() -> None:
    called = []

    def tier1(url):
        raise AuthWallError(url, 403)

    def tier2(url):
        called.append("t2")
        return FetchResult(final_url=url, html="auth")

    with pytest.raises(BrowserCookieAccessDeniedError):
        coordinator.fetch("https://x/1", tier1=tier1, tier2=tier2, config=_config(allow=False))
    assert called == []
