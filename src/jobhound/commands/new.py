"""`jh new` — scaffold a new opportunity at status `prospect`."""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.opportunities import Opportunity
from jobhound.paths import Paths, paths_from_config
from jobhound.repository import OpportunityRepository

_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_BAD.sub("-", text.lower()).strip("-")
    return s or "untitled"


def _build_slug(today: date, company: str, role: str) -> str:
    return f"{today:%Y-%m}-{_slugify(company)}-{_slugify(role)}"


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
    slug = _build_slug(today_date, company, role)

    opp = Opportunity(
        slug=slug,
        company=company,
        role=role,
        status="prospect",
        priority="medium",
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
        opp_dir = repo.create(opp, message=f"new: {slug}", no_commit=no_commit)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Created {opp_dir.relative_to(paths.db_root)}")
