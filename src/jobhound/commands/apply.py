"""`jh apply` — submitted application, status → applied."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import lifecycle_service
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def _parse_date_flag(value: str) -> datetime:
    """Parse a user-supplied date flag to a UTC datetime.

    Bare dates (``2026-05-12``) are noon UTC — unambiguous across all timezones.
    ISO datetime strings (``2026-05-12T12:00:00Z``) go through ``to_utc`` normally.
    """
    dt = datetime.fromisoformat(value)
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.tzinfo is None:
        # Bare date: treat as noon UTC to preserve the calendar date in all zones.
        return dt.replace(hour=12, tzinfo=UTC)
    return to_utc(dt)


def run(
    slug_query: str,
    /,
    *,
    on: str | None = None,
    next_action: str,
    next_action_due: str,
    now: Annotated[str | None, Parameter(show=False)] = None,
) -> None:
    """Mark the application as submitted."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)

    now_obj = to_utc(datetime.fromisoformat(now)) if now else now_utc()
    applied_on = _parse_date_flag(on) if on else now_obj
    due = _parse_date_flag(next_action_due)

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
