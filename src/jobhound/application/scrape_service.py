"""scrape_service — create an opportunity from a job-posting URL.

Orchestrates the pipeline: fetch (injected, so the network boundary is
mockable) → extract via the site registry → build an Opportunity →
create → write the JD body as a file. The posting link and scalar fields
are set on the Opportunity at creation, so one write persists them all.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from jobhound.application import file_service, lifecycle_service
from jobhound.application.extract import registry
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.fetch.base import FetchResult
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.protocols import FileStore

Fetch = Callable[[str], FetchResult]

JD_FILENAME = "job-description.md"


class ScrapeServiceError(Exception):
    """Base class for scrape_service exceptions."""


class IncompleteScrapeError(ScrapeServiceError):
    """The scrape did not yield the required fields (company and role)."""

    def __init__(self, url: str, missing: tuple[str, ...]) -> None:
        super().__init__(f"could not extract {', '.join(missing)} from {url}")
        self.url = url
        self.missing = missing


class DuplicatePostingError(ScrapeServiceError):
    """An opportunity already links to this posting's canonical URL."""

    def __init__(self, canonical_url: str, existing_slug: str) -> None:
        super().__init__(f"{existing_slug} already links to {canonical_url}")
        self.canonical_url = canonical_url
        self.existing_slug = existing_slug


@dataclass(frozen=True)
class CreateFromUrlResult:
    """Outcome of a create-from-URL: the new slug plus what was/wasn't scraped."""

    slug: str
    opp: Opportunity
    missing: tuple[str, ...]


def create_from_url(
    repo: OpportunityRepository,
    store: FileStore,
    url: str,
    *,
    fetch: Fetch,
    now: datetime | None = None,
) -> CreateFromUrlResult:
    """Scrape `url` and scaffold a `prospect` opportunity from it."""
    now_obj = to_utc(now) if now else now_utc()
    extractor = registry.extractor_for(url)
    site = registry.site_name_for(url)

    result = fetch(url)
    job = extractor(result.html)

    if not job.company or not job.role:
        required = tuple(f for f in ("company", "role") if not getattr(job, f))
        raise IncompleteScrapeError(url, required)

    canonical = job.canonical_url or result.final_url
    # Dedup against active opportunities only; a previously-archived posting
    # re-scraped is treated as a fresh opportunity by design.
    for existing in repo.all():
        if existing.links.get("posting") == canonical:
            raise DuplicatePostingError(canonical, existing.slug)

    opp = Opportunity.new_prospect(
        now_obj,
        job.company,
        job.role,
        source=site,
        location=job.location,
        comp_range=job.comp_range,
        links={"posting": canonical},
    )
    _, created, _ = lifecycle_service.create(repo, opp)

    if job.jd_body:
        file_service.write(store, created.slug, JD_FILENAME, job.jd_body.encode("utf-8"))

    return CreateFromUrlResult(slug=created.slug, opp=created, missing=job.missing)
