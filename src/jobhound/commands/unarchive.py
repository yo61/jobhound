"""`jh unarchive` — restore an archived opportunity."""

from __future__ import annotations

import sys

from jobhound.application import ops_service
from jobhound.domain.slug import SlugNotFoundError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import Paths, paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
) -> None:
    """Unarchive an opportunity."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    try:
        _, _, new_dir = ops_service.unarchive_opportunity(repo, slug_query)
    except SlugNotFoundError:
        print(
            f"jh: no archived opportunity matches {slug_query!r}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"unarchived: {new_dir.name}")
