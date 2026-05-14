"""`jh delete` — remove an opportunity directory."""

from __future__ import annotations

from typing import Annotated

import questionary
from cyclopts import Parameter

from jobhound.application import ops_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    yes: bool = False,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Delete an opportunity directory (e.g. a duplicate scaffold).

    --yes: skip the confirmation prompt.
    """
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    if not yes:
        _, opp_dir = repo.find(slug_query)
        confirm = questionary.confirm(f"Delete {opp_dir.name}?", default=False).ask()
        if not confirm:
            print("aborted")
            raise SystemExit(1)
    result = ops_service.delete_opportunity(
        repo,
        slug_query,
        confirm=True,
        no_commit=no_commit,
    )
    print(f"deleted: {result.opp_dir.name}")
