"""`jh delete` — remove an opportunity directory."""

from __future__ import annotations

from typing import Annotated

import questionary
from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


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
    _, opp_dir = repo.find(slug_query)
    if not yes:
        confirm = questionary.confirm(f"Delete {opp_dir.name}?", default=False).ask()
        if not confirm:
            print("aborted")
            raise SystemExit(1)
    name = opp_dir.name
    repo.delete(opp_dir, no_commit=no_commit)
    print(f"deleted: {name}")
