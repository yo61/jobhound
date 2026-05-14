"""`jh apply` — submitted application, status → applied."""

from __future__ import annotations

import sys
from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import lifecycle_service
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    on: str | None = None,
    next_action: str,
    next_action_due: str,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Mark the application as submitted."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)

    today_date = date.fromisoformat(today) if today else date.today()
    applied_on = date.fromisoformat(on) if on else today_date
    due = date.fromisoformat(next_action_due)

    try:
        _, after, _ = lifecycle_service.apply_to(
            repo,
            slug_query,
            applied_on=applied_on,
            today=today_date,
            next_action=next_action,
            next_action_due=due,
            no_commit=no_commit,
        )
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"applied: {after.slug}")
