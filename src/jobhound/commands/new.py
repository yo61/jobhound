"""`jh new` — scaffold a new opportunity at status `prospect`."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import lifecycle_service
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.slug_value import Slug
from jobhound.domain.status import Status
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import Paths, paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def _parse_date_flag(value: str) -> datetime:
    """Parse a user-supplied date flag to a UTC datetime.

    Bare dates (``2026-05-18``) are noon UTC — unambiguous across all timezones.
    ISO datetime strings (``2026-05-18T12:00:00Z``) go through ``to_utc`` normally.
    """
    dt = datetime.fromisoformat(value)
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.tzinfo is None:
        return dt.replace(hour=12, tzinfo=UTC)
    return to_utc(dt)


def run(
    *,
    company: str,
    role: str,
    source: str = "(unspecified)",
    next_action: str = "Initial review of role and company",
    next_action_due: str | None = None,
    now: Annotated[str | None, Parameter(show=False)] = None,
) -> None:
    """Create a new opportunity at status `prospect`."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    now_obj = to_utc(datetime.fromisoformat(now)) if now else now_utc()
    due = _parse_date_flag(next_action_due) if next_action_due else now_obj + timedelta(days=7)
    slug = Slug.build(now_obj, company, role)

    opp = Opportunity(
        slug=slug.value,
        company=company,
        role=role,
        status=Status.PROSPECT,
        priority=Priority.MEDIUM,
        source=source,
        location=None,
        comp_range=None,
        first_contact=now_obj,
        applied_on=None,
        last_activity=now_obj,
        next_action=next_action,
        next_action_due=due,
    )
    try:
        _, _, opp_dir = lifecycle_service.create(repo, opp)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Created {opp_dir.relative_to(paths.db_root)}")
