"""`jh link` — add or update an entry in the links table."""

from __future__ import annotations

from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    name: str,
    url: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add or update a link."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = opp.with_link(name=name, url=url)
    repo.save(updated, opp_dir, message=f"link: {opp.slug} {name}", no_commit=no_commit)
    print(f"link {opp.slug}: {name} = {url}")
