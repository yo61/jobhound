"""Tests for application/scrape_service.py.

Only the network boundary is faked (a `fetch` callable returning canned
HTML). The repository, file store, and extractors are real, so these
tests exercise the whole create → write-JD → set-link → scalars path.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.application import file_service, scrape_service
from jobhound.domain.status import Status
from jobhound.infrastructure.config import Config
from jobhound.infrastructure.fetch.base import FetchResult
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

NOW = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def _repo_and_store(tmp_path: Path) -> tuple[OpportunityRepository, GitLocalFileStore, Paths]:
    db_root = tmp_path / "db"
    for d in ("opportunities", "archive", "_shared"):
        (db_root / d).mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(db_root)], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.email", "t@t"], check=True)
    paths = Paths(
        db_root=db_root,
        opportunities_dir=db_root / "opportunities",
        archive_dir=db_root / "archive",
        shared_dir=db_root / "_shared",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )
    config = Config(db_path=db_root, auto_commit=True, editor="")
    return OpportunityRepository(paths, config), GitLocalFileStore(paths), paths


_CANONICAL = (
    "https://uk.linkedin.com/jobs/view/graduate-platform-engineer-growth-at-liveflow-4383908452"
)


def _linkedin_html(
    *,
    title: str = (
        "LiveFlow hiring Graduate Platform Engineer - Growth "
        "in London, England, United Kingdom | LinkedIn"
    ),
    canonical: str = _CANONICAL,
    jd_body: str = "About LiveFlow. We are hiring engineers.",
) -> str:
    return (
        "<html><head>"
        f'<meta property="og:title" content="{title}">'
        f'<link rel="canonical" href="{canonical}">'
        "</head><body>"
        f'<div class="show-more-less-html__markup">{jd_body}</div>'
        "</body></html>"
    )


def _fetch(html: str):
    def fetch(url: str) -> FetchResult:
        return FetchResult(final_url=url, html=html)

    return fetch


def test_creates_opportunity_with_scraped_fields(tmp_path: Path) -> None:
    repo, store, _ = _repo_and_store(tmp_path)

    result = scrape_service.create_from_url(
        repo,
        store,
        "https://www.linkedin.com/jobs/view/4383908452?trk=share",
        fetch=_fetch(_linkedin_html()),
        now=NOW,
    )

    opp, _ = repo.find(result.slug)
    assert opp.company == "LiveFlow"
    assert opp.role == "Graduate Platform Engineer - Growth"
    assert opp.location == "London, England, United Kingdom"
    assert opp.source == "LinkedIn"
    assert opp.status == Status.PROSPECT


def test_stores_canonical_url_as_posting_link(tmp_path: Path) -> None:
    repo, store, _ = _repo_and_store(tmp_path)

    result = scrape_service.create_from_url(
        repo,
        store,
        "https://www.linkedin.com/jobs/view/4383908452?trk=share&refId=abc",
        fetch=_fetch(_linkedin_html()),
        now=NOW,
    )

    opp, _ = repo.find(result.slug)
    # Tracking params in the input are inert; the page's canonical URL is stored.
    assert opp.links["posting"] == _CANONICAL


def test_missing_company_or_role_raises_incomplete_scrape(tmp_path: Path) -> None:
    repo, store, _ = _repo_and_store(tmp_path)
    # An unparseable page yields no company/role.
    html = "<html><head><title>Sign in | LinkedIn</title></head><body></body></html>"

    with pytest.raises(scrape_service.IncompleteScrapeError):
        scrape_service.create_from_url(
            repo,
            store,
            "https://www.linkedin.com/jobs/view/1",
            fetch=_fetch(html),
            now=NOW,
        )


def test_duplicate_canonical_url_raises(tmp_path: Path) -> None:
    repo, store, _ = _repo_and_store(tmp_path)
    scrape_service.create_from_url(
        repo,
        store,
        "https://www.linkedin.com/jobs/view/4383908452",
        fetch=_fetch(_linkedin_html()),
        now=NOW,
    )

    # A different input URL that resolves to the same canonical posting.
    with pytest.raises(scrape_service.DuplicatePostingError):
        scrape_service.create_from_url(
            repo,
            store,
            "https://www.linkedin.com/jobs/view/4383908452?trk=another-share-link",
            fetch=_fetch(_linkedin_html()),
            now=NOW,
        )


def test_writes_job_description_file(tmp_path: Path) -> None:
    repo, store, _ = _repo_and_store(tmp_path)

    result = scrape_service.create_from_url(
        repo,
        store,
        "https://www.linkedin.com/jobs/view/4383908452",
        fetch=_fetch(_linkedin_html(jd_body="About LiveFlow. Join our platform team.")),
        now=NOW,
    )

    content, _ = file_service.read(store, result.slug, "job-description.md")
    assert b"About LiveFlow" in content
    assert b"Join our platform team" in content
