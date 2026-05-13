"""`jh new` — scaffold a new opportunity at status `prospect`."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Annotated

from cyclopts import Parameter

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.slug_value import Slug
from jobhound.domain.status import Status
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import Paths, paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    *,
    company: str,
    role: str,
    source: str = "(unspecified)",
    next_action: str = "Initial review of role and company",
    next_action_due: str | None = None,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Create a new opportunity at status `prospect`."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    today_date = date.fromisoformat(today) if today else date.today()
    due = date.fromisoformat(next_action_due) if next_action_due else today_date + timedelta(days=7)
    slug = Slug.build(today_date, company, role)

    opp = Opportunity(
        slug=slug.value,
        company=company,
        role=role,
        status=Status.PROSPECT,
        priority=Priority.MEDIUM,
        source=source,
        location=None,
        comp_range=None,
        first_contact=today_date,
        applied_on=None,
        last_activity=today_date,
        next_action=next_action,
        next_action_due=due,
    )
    try:
        opp_dir = repo.create(opp, message=f"new: {slug.value}", no_commit=no_commit)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Created {opp_dir.relative_to(paths.db_root)}")
