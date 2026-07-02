"""Tests for the URL-scraping MCP tools (create_from_url, browser_status).

The fetch tiers are monkeypatched so these run with no network or browser.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from jobhound.infrastructure.fetch.base import FetchResult
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.lifecycle import browser_status, create_from_url

_CANONICAL = "https://uk.linkedin.com/jobs/view/staff-eng-at-liveflow-77"
_HTML = (
    "<html><head>"
    '<meta property="og:title" content="LiveFlow hiring Staff Engineer in Remote | LinkedIn">'
    f'<link rel="canonical" href="{_CANONICAL}">'
    "</head><body>"
    '<div class="show-more-less-html__markup">Work at LiveFlow.</div>'
    "</body></html>"
)


def _patch_tier1(monkeypatch: pytest.MonkeyPatch, fn: Callable[[str], FetchResult]) -> None:
    monkeypatch.setattr("jobhound.infrastructure.fetch.http_fetch.fetch", fn)


def test_create_from_url_creates_and_reports_missing(
    repo: OpportunityRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_tier1(monkeypatch, lambda url: FetchResult(final_url=url, html=_HTML))

    payload = json.loads(create_from_url(repo, url="https://www.linkedin.com/jobs/view/77?trk=x"))

    assert payload["changed"] is None
    assert payload["opportunity"]["company"] == "LiveFlow"
    assert payload["opportunity"]["source"] == "LinkedIn"
    assert "comp_range" in payload["missing"]


def test_create_from_url_duplicate_returns_actionable_error(
    repo: OpportunityRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_tier1(monkeypatch, lambda url: FetchResult(final_url=url, html=_HTML))
    create_from_url(repo, url="https://www.linkedin.com/jobs/view/77")

    payload = json.loads(create_from_url(repo, url="https://www.linkedin.com/jobs/view/77?trk=y"))

    assert payload["error"]["code"] == "duplicate_posting"


def test_create_from_url_access_denied_returns_error(
    repo: OpportunityRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jobhound.infrastructure.config import Config
    from jobhound.infrastructure.fetch.base import AuthWallError

    def _authwall(url: str):
        raise AuthWallError(url, 403)

    _patch_tier1(monkeypatch, _authwall)
    monkeypatch.setattr(
        "jobhound.infrastructure.fetch.coordinator.load_config",
        lambda: Config(db_path=repo.paths.db_root, auto_commit=True, editor=""),
    )

    payload = json.loads(create_from_url(repo, url="https://www.linkedin.com/jobs/view/1"))
    assert payload["error"]["code"] == "browser_cookie_access_denied"


def test_create_from_url_no_session_returns_error(
    repo: OpportunityRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jobhound.infrastructure.config import Config
    from jobhound.infrastructure.fetch.base import AuthWallError, NoBrowserSessionError

    def _authwall(url: str):
        raise AuthWallError(url, 403)

    def _no_session(url: str, **_kwargs: object) -> None:
        raise NoBrowserSessionError("chrome")

    _patch_tier1(monkeypatch, _authwall)
    monkeypatch.setattr(
        "jobhound.infrastructure.fetch.coordinator.load_config",
        lambda: Config(
            db_path=repo.paths.db_root,
            auto_commit=True,
            editor="",
            allow_browser_cookie_access=True,
        ),
    )
    monkeypatch.setattr("jobhound.infrastructure.fetch.cookie_fetch.fetch", _no_session)

    payload = json.loads(create_from_url(repo, url="https://www.linkedin.com/jobs/view/1"))
    assert payload["error"]["code"] == "no_browser_session"


def test_browser_status_reports_no_session(
    repo: OpportunityRepository, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    payload = json.loads(browser_status(site="linkedin"))

    assert payload["site"] == "linkedin"
    assert payload["session_present"] is False


def test_browser_status_unknown_site_returns_error(repo: OpportunityRepository) -> None:
    payload = json.loads(browser_status(site="monster"))

    assert "error" in payload
