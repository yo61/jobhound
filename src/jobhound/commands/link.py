"""`jh link` — add or update an entry in the links table."""

from __future__ import annotations

from jobhound.application import relation_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    name: str,
    url: str,
) -> None:
    """Add or update a link."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    _, after, _ = relation_service.set_link(repo, slug_query, name=name, url=url)
    print(f"link {after.slug}: {name} = {url}")
