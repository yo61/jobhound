"""`jh tag` — add and/or remove tags."""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add and/or remove tags."""
    add_set = set(add or [])
    remove_set = set(remove or [])
    if not add_set and not remove_set:
        print("nothing to do; pass --add and/or --remove", file=sys.stderr)
        raise SystemExit(1)

    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    tags = tuple(sorted((set(opp.tags) | add_set) - remove_set))
    updated = replace(opp, tags=tags)

    summary = " ".join(
        [*(f"+{t}" for t in sorted(add_set)), *(f"-{t}" for t in sorted(remove_set))]
    )
    repo.save(updated, opp_dir, message=f"tag: {opp.slug} {summary}", no_commit=no_commit)
    print(f"tags {opp.slug}: {tags}")
