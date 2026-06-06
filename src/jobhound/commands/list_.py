"""`jh list` — one-line summary of opportunities, optionally filtered."""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.domain.status import Status
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    *,
    all_: Annotated[bool, Parameter(name=["--all", "-a"])] = False,
    archived: Annotated[bool, Parameter(name=["--archived", "-A"])] = False,
    status: Annotated[list[str] | None, Parameter(name=["--status", "-s"])] = None,
) -> None:
    """List opportunities."""
    if all_ and archived:
        print("jh: --all and --archived are mutually exclusive", file=sys.stderr)
        raise SystemExit(2)

    statuses = _parse_statuses(status)

    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)
    filters = Filters(statuses=statuses, include_archived=(all_ or archived))
    snaps = query.list(filters, now=now_utc())
    if archived:
        snaps = [s for s in snaps if s.archived]

    for snap in snaps:
        opp = snap.opportunity
        mark = " *" if snap.archived else ""
        print(f"{opp.slug:<55} {opp.status:<12} {opp.priority:<8}{mark}".rstrip())


def _parse_statuses(raw: list[str] | None) -> frozenset[Status]:
    """Accept repeated `--status` and comma-separated values."""
    if not raw:
        return frozenset()
    tokens = [t.strip() for chunk in raw for t in chunk.split(",") if t.strip()]
    try:
        return frozenset(Status(t) for t in tokens)
    except ValueError as exc:
        print(f"jh: unknown status: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
