"""`jh remove` subgroup — remove entries from an opportunity."""

from __future__ import annotations

from cyclopts import App

from jobhound.application import relation_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

app = App(name="remove", help="Remove a tag or other entry from an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="tag")
def tag(
    slug_query: str,
    tag_name: str,
    /,
) -> None:
    """Remove a tag from an opportunity."""
    _, after, _ = relation_service.set_tags(
        _repo(),
        slug_query,
        add=set(),
        remove={tag_name},
    )
    print(f"tags {after.slug}: {after.tags}")
