"""`jh apply` — submitted application, status → applied."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError, require_transition


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
        require_transition(opp.status, "applied", verb="apply")
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    updated = replace(
        opp,
        status="applied",
        applied_on=applied_on,
        last_activity=today_date,
        next_action=next_action,
        next_action_due=due,
    )
    repo.save(updated, opp_dir, message=f"apply: {opp.slug}", no_commit=no_commit)
    print(f"applied: {opp.slug}")
