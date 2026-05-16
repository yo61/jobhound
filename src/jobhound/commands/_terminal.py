"""Shared logic for terminal-status verbs (withdraw, ghost, accept, decline)."""

from __future__ import annotations

import sys
from datetime import datetime

from jobhound.application import lifecycle_service
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

_SERVICES = {
    "withdraw": lifecycle_service.withdraw_from,
    "ghost": lifecycle_service.mark_ghosted,
    "accept": lifecycle_service.accept_offer,
    "decline": lifecycle_service.decline_offer,
}


def run_transition(
    *,
    slug_query: str,
    verb: str,
    now: datetime | None,
) -> None:
    """Move an opportunity to its terminal status via the application service."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    now_obj = to_utc(now) if now else now_utc()

    service_fn = _SERVICES[verb]
    try:
        _, after, _ = service_fn(repo, slug_query, now=now_obj)
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"{verb}: {after.slug}")
