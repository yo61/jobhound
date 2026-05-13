"""Shared logic for terminal-status verbs (withdraw, ghost, accept, decline)."""

from __future__ import annotations

import sys
from datetime import date

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

_METHODS = {
    "withdraw": Opportunity.withdraw,
    "ghost": Opportunity.ghost,
    "accept": Opportunity.accept,
    "decline": Opportunity.decline,
}


def run_transition(
    *,
    slug_query: str,
    verb: str,
    today: str | None,
    no_commit: bool,
) -> None:
    """Move an opportunity to its terminal status via the entity method."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()
    opp, opp_dir = repo.find(slug_query)

    method = _METHODS[verb]
    try:
        updated = method(opp, today=today_date)
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    repo.save(updated, opp_dir, message=f"{verb}: {opp.slug}", no_commit=no_commit)
    print(f"{verb}: {opp.slug}")
