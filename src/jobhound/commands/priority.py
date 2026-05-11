"""`jh priority` — set priority to high/medium/low."""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.priority import Priority
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    to: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Set the priority of an opportunity."""
    try:
        priority = Priority(to)
    except ValueError:
        print(f"--to must be one of {[p.value for p in Priority]}", file=sys.stderr)
        raise SystemExit(1) from None
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = opp.with_priority(priority)
    repo.save(
        updated, opp_dir, message=f"priority: {opp.slug} {priority.value}", no_commit=no_commit
    )
    print(f"priority {opp.slug}: {priority.value}")
