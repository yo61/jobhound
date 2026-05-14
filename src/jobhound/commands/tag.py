"""`jh tag` — add and/or remove tags."""

from __future__ import annotations

import sys

from jobhound.application import relation_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
) -> None:
    """Add and/or remove tags."""
    add_set = set(add or [])
    remove_set = set(remove or [])
    if not add_set and not remove_set:
        print("nothing to do; pass --add and/or --remove", file=sys.stderr)
        raise SystemExit(1)

    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    _, after, _ = relation_service.set_tags(
        repo,
        slug_query,
        add=add_set,
        remove=remove_set,
    )
    print(f"tags {after.slug}: {after.tags}")
