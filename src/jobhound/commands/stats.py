"""`jh stats` — show aggregate funnel and source counts."""

from __future__ import annotations

import json
import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.application.serialization import stats_to_dict
from jobhound.application.snapshots import OpportunitySnapshot, Stats
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    *,
    json_out: Annotated[bool, Parameter(name=["--json", "-j"])] = False,
    all_: Annotated[bool, Parameter(name=["--all", "-a"])] = False,
    archived: Annotated[bool, Parameter(name=["--archived", "-A"])] = False,
    status: Annotated[list[str] | None, Parameter(name=["--status", "-s"])] = None,
    priority: Annotated[list[str] | None, Parameter(name=["--priority", "-p"])] = None,
    slug_substring: Annotated[str | None, Parameter(name=["--slug-substring", "-q"])] = None,
) -> None:
    """Show pipeline stats."""
    if all_ and archived:
        print("jh: --all and --archived are mutually exclusive", file=sys.stderr)
        raise SystemExit(2)

    statuses = _parse_statuses(status)
    priorities = _parse_priorities(priority)

    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)

    if archived:
        # Active+archived then drop active rows. Filters has no archived-only mode;
        # this keeps the read API unchanged.
        snaps = [
            s
            for s in query.list(
                Filters(
                    statuses=statuses,
                    priorities=priorities,
                    slug_substring=slug_substring,
                    include_archived=True,
                ),
                now=now_utc(),
            )
            if s.archived
        ]
        stats = _aggregate(snaps)
    else:
        stats = query.stats(
            Filters(
                statuses=statuses,
                priorities=priorities,
                slug_substring=slug_substring,
                include_archived=all_,
            ),
        )

    if json_out:
        print(json.dumps(stats_to_dict(stats), indent=2))
    else:
        _print_human(stats_to_dict(stats))


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


def _parse_priorities(raw: list[str] | None) -> frozenset[Priority]:
    """Accept repeated `--priority` and comma-separated values."""
    if not raw:
        return frozenset()
    tokens = [t.strip() for chunk in raw for t in chunk.split(",") if t.strip()]
    try:
        return frozenset(Priority(t) for t in tokens)
    except ValueError as exc:
        print(f"jh: unknown priority: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


def _aggregate(snaps: list[OpportunitySnapshot]) -> Stats:
    """Build a Stats aggregate from a snapshot list (used for --archived only)."""
    funnel: dict[Status, int] = dict.fromkeys(Status, 0)
    sources: dict[str, int] = {}
    for snap in snaps:
        funnel[snap.opportunity.status] += 1
        key = snap.opportunity.source or "(unspecified)"
        sources[key] = sources.get(key, 0) + 1
    return Stats(funnel=funnel, sources=sources)


def _print_human(data: dict) -> None:
    print("Funnel:")
    for status, count in data.get("funnel", {}).items():
        if count:
            print(f"  {status:<20s} {count}")
    sources = data.get("sources", {})
    if sources:
        print()
        print("Sources:")
        for source, count in sorted(sources.items()):
            print(f"  {source:<20s} {count}")
