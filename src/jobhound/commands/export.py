"""`jh export` — emit a JSON envelope of opportunities to stdout."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.application.serialization import list_envelope
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    *,
    status: Annotated[tuple[str, ...], Parameter(name=["--status"])] = (),
    priority: Annotated[tuple[str, ...], Parameter(name=["--priority"])] = (),
    slug: Annotated[str | None, Parameter(name=["--slug"])] = None,
    active_only: Annotated[bool, Parameter(name=["--active-only"])] = False,
    include_archived: Annotated[bool, Parameter(name=["--include-archived"])] = False,
) -> None:
    """Emit a JSON envelope of all matching opportunities."""
    try:
        statuses = frozenset(Status(s) for s in _split(status))
        priorities = frozenset(Priority(p) for p in _split(priority))
    except ValueError as exc:
        print(f"jh: {exc}", file=sys.stderr)
        raise SystemExit(2) from None

    filters = Filters(
        statuses=statuses,
        priorities=priorities,
        slug_substring=slug,
        active_only=active_only,
        include_archived=include_archived,
    )
    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)
    snaps = query.list(filters, now=now_utc())
    envelope = list_envelope(
        snaps,
        timestamp=datetime.now(UTC),
        db_root=paths.db_root,
    )
    print(json.dumps(envelope, indent=2))


def _split(raw: tuple[str, ...]) -> list[str]:
    """Accept comma-separated OR repeated flags, returning a flat list of values."""
    out: list[str] = []
    for chunk in raw:
        for token in chunk.split(","):
            stripped = token.strip()
            if stripped:
                out.append(stripped)
    return out
