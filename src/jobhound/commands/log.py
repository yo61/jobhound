"""`jh log` — record an interaction; default next status advances one stage."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import file_service, lifecycle_service
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

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
    store = GitLocalFileStore(repo.paths)
    today_date = date.fromisoformat(today) if today else date.today()

    if direction not in {"from", "to"}:
        print(f"--direction must be 'from' or 'to', got {direction!r}", file=sys.stderr)
        raise SystemExit(1)
    if not body.is_file():
        print(f"--body file not found: {body}", file=sys.stderr)
        raise SystemExit(1)

    due = date.fromisoformat(next_action_due) if next_action_due else None

    _, opp_dir = repo.find(slug_query)
    corr_name = _correspondence_filename(today_date, channel, direction, who)
    file_service.write(
        store,
        opp_dir.name,
        f"correspondence/{corr_name}",
        body.read_bytes(),
    )

    try:
        before, after, _ = lifecycle_service.log_interaction(
            repo,
            slug_query,
            next_status=next_status,
            next_action=next_action,
            next_action_due=due,
            today=today_date,
            force=force,
            no_commit=no_commit,
        )
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    arrow = (
        f"{before.status} → {after.status}"
        if after.status != before.status
        else "(no status change)"
    )
    print(f"logged: {after.slug} {arrow}")
