"""`jh apply` — submitted application, status → applied."""

from __future__ import annotations

import sys
from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError


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

    opp, opp_dir = repo.find(slug_query)
    try:
        updated = opp.apply(
            applied_on=applied_on,
            today=today_date,
            next_action=next_action,
            next_action_due=due,
        )
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    repo.save(updated, opp_dir, message=f"apply: {opp.slug}", no_commit=no_commit)
    print(f"applied: {opp.slug}")
