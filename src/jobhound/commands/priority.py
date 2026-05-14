"""`jh priority` — set priority to high/medium/low."""

from __future__ import annotations

import sys

from jobhound.application import field_service
from jobhound.domain.priority import Priority
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    to: str,
) -> None:
    """Set the priority of an opportunity."""
    try:
        priority = Priority(to)
    except ValueError:
        print(f"--to must be one of {[p.value for p in Priority]}", file=sys.stderr)
        raise SystemExit(1) from None
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    _, after, _ = field_service.set_priority(repo, slug_query, priority)
    print(f"priority {after.slug}: {after.priority.value}")
