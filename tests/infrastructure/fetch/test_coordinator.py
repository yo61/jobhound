"""Tests for the two-tier fetch coordinator.

The tier functions are injected so the escalation logic is tested without
any real HTTP or browser — HTTP first, browser tier only on an auth wall.
"""

from __future__ import annotations

import pytest

from jobhound.infrastructure.fetch import coordinator
from jobhound.infrastructure.fetch.base import AuthWallError, FetchError, FetchResult


def test_returns_tier1_result_when_tier1_succeeds() -> None:
    calls: list[str] = []

    def tier1(url: str) -> FetchResult:
        calls.append("t1")
        return FetchResult(final_url=url, html="tier1 html")

    def tier2(url: str) -> FetchResult:
        calls.append("t2")
        return FetchResult(final_url=url, html="tier2 html")

    result = coordinator.fetch("https://example.com/1", tier1=tier1, tier2=tier2)

    assert result.html == "tier1 html"
    assert calls == ["t1"]  # tier2 must not be called


def test_escalates_to_tier2_on_auth_wall() -> None:
    def tier1(url: str) -> FetchResult:
        raise AuthWallError(url, 403)

    def tier2(url: str) -> FetchResult:
        return FetchResult(final_url=url, html="tier2 html")

    result = coordinator.fetch("https://example.com/1", tier1=tier1, tier2=tier2)

    assert result.html == "tier2 html"


def test_non_auth_wall_error_propagates_without_escalating() -> None:
    called: list[str] = []

    def tier1(url: str) -> FetchResult:
        raise FetchError("server error")

    def tier2(url: str) -> FetchResult:
        called.append("t2")
        return FetchResult(final_url=url, html="tier2 html")

    with pytest.raises(FetchError):
        coordinator.fetch("https://example.com/1", tier1=tier1, tier2=tier2)

    assert called == []  # a non-auth-wall failure is terminal
