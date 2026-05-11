"""`jh log` — record an interaction; default next status advances one stage."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError

_NAME_SLUG = re.compile(r"[^a-z0-9]+")


def _name_slug(who: str) -> str:
    return _NAME_SLUG.sub("-", who.lower()).strip("-") or "unknown"


def _correspondence_filename(when: date, channel: str, direction: str, who: str) -> str:
    return f"{when.isoformat()}-{channel}-{direction}-{_name_slug(who)}.md"


def run(
    slug_query: str,
    /,
    *,
    channel: str,
    direction: str,
    who: str,
    body: Path,
    next_status: str = "stay",
    next_action: str | None = None,
    next_action_due: str | None = None,
    force: bool = False,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Record an interaction (correspondence) and update status + next action."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()

    if direction not in {"from", "to"}:
        print(f"--direction must be 'from' or 'to', got {direction!r}", file=sys.stderr)
        raise SystemExit(1)
    if not body.is_file():
        print(f"--body file not found: {body}", file=sys.stderr)
        raise SystemExit(1)

    opp, opp_dir = repo.find(slug_query)
    due = date.fromisoformat(next_action_due) if next_action_due else None
    try:
        updated = opp.log_interaction(
            today=today_date,
            next_status=next_status,
            next_action=next_action,
            next_action_due=due,
            force=force,
        )
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    corr_dir = opp_dir / "correspondence"
    corr_dir.mkdir(exist_ok=True)
    corr_path = corr_dir / _correspondence_filename(today_date, channel, direction, who)
    corr_path.write_text(body.read_text())

    arrow = (
        f"{opp.status} → {updated.status}" if updated.status != opp.status else "(no status change)"
    )
    repo.save(updated, opp_dir, message=f"log: {opp.slug} {arrow}", no_commit=no_commit)
    print(f"logged: {opp.slug} {arrow}")
