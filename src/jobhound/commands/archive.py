"""`jh archive` — move <slug> from opportunities/ to archive/."""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import Paths, paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Move an opportunity to the archive directory."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    _, opp_dir = repo.find(slug_query)
    try:
        repo.archive(opp_dir, no_commit=no_commit)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"archived: {opp_dir.name}")
