"""`jh bump <slug>` — bump last_activity to now without changing status."""

from __future__ import annotations

from jobhound.application import field_service
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(slug_query: str, /) -> None:
    """Bump last-activity to now."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    _, after, _ = field_service.bump(repo, slug_query, now=now_utc())
    print(f"bumped: {after.slug}")
