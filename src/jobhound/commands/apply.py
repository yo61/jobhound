"""`jh apply` — submitted application, status → applied."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import lifecycle_service
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    on: datetime | None = None,
    next_action: str,
    next_action_due: datetime,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Apply to an opportunity."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)

    now_obj = to_utc(now) if now else now_utc()
    applied_on = to_utc(on) if on else now_obj
    due = to_utc(next_action_due)

    try:
        _, after, _ = lifecycle_service.apply_to(
            repo,
            slug_query,
            applied_on=applied_on,
            now=now_obj,
            next_action=next_action,
            next_action_due=due,
        )
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"applied: {after.slug}")
