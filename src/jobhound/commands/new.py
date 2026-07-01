"""`jh new` — scaffold a new opportunity at status `prospect`."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import lifecycle_service
from jobhound.domain.opportunities import DEFAULT_NEXT_ACTION, Opportunity
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import Paths, paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    *,
    company: str,
    role: str,
    source: str = "(unspecified)",
    next_action: str = DEFAULT_NEXT_ACTION,
    next_action_due: datetime | None = None,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Create a new opportunity."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

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
