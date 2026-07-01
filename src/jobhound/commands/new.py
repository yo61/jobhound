"""`jh new` — scaffold a new opportunity at status `prospect`.

By hand (`--company`/`--role`) or scraped from a job-posting URL (`--url`).
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import lifecycle_service, scrape_service
from jobhound.domain.opportunities import DEFAULT_NEXT_ACTION, Opportunity
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.fetch.base import FetchError
from jobhound.infrastructure.paths import Paths, paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore


def run(
    *,
    company: str | None = None,
    role: str | None = None,
    url: str | None = None,
    source: str = "(unspecified)",
    next_action: str = DEFAULT_NEXT_ACTION,
    next_action_due: datetime | None = None,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Create a new opportunity, by hand or scraped from a job-posting URL."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    if url is not None:
        _create_from_url(repo, paths, url)
        return

    if company is None or role is None:
        print("jh: provide --url, or both --company and --role", file=sys.stderr)
        raise SystemExit(2)

    now_obj = to_utc(now) if now else now_utc()
    due = to_utc(next_action_due) if next_action_due else None
    opp = Opportunity.new_prospect(
        now_obj,
        company,
        role,
        source=source,
        next_action=next_action,
        next_action_due=due,
    )
    try:
        _, _, opp_dir = lifecycle_service.create(repo, opp)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Created {opp_dir.relative_to(paths.db_root)}")


def _create_from_url(repo: OpportunityRepository, paths: Paths, url: str) -> None:
    store = GitLocalFileStore(paths)
    try:
        result = scrape_service.create_from_url(repo, store, url)
    except (scrape_service.ScrapeServiceError, FetchError) as exc:
        print(f"jh: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Created {result.slug} from {url}")
    if result.missing:
        print(f"jh: note — couldn't determine: {', '.join(result.missing)}", file=sys.stderr)
