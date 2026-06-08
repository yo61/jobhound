"""`jh tag` subgroup — manage tags on an opportunity."""

from __future__ import annotations

from cyclopts import App

from jobhound.application import relation_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

app = App(name="tag", help="Manage tags on an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="add")
def add(
    slug_query: str,
    tag_name: str,
    /,
) -> None:
    """Add a tag."""
    _, after, _ = relation_service.set_tags(
        _repo(),
        slug_query,
        add={tag_name},
        remove=set(),
    )
    print(f"tags {after.slug}: {after.tags}")


@app.command(name="remove")
def remove(
    slug_query: str,
    tag_name: str,
    /,
) -> None:
    """Remove a tag."""
    _, after, _ = relation_service.set_tags(
        _repo(),
        slug_query,
        add=set(),
        remove={tag_name},
    )
    print(f"tags {after.slug}: {after.tags}")
