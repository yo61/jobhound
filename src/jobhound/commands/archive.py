"""`jh archive` — move <slug> from opportunities/ to archive/."""

from __future__ import annotations

import sys

from jobhound.application import ops_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import Paths, paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
) -> None:
    """Move an opportunity to the archive directory."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    try:
        _, _, new_dir = ops_service.archive_opportunity(repo, slug_query)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"archived: {new_dir.name}")
