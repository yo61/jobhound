"""`jh remove` subgroup — remove entries from an opportunity."""

from __future__ import annotations

from cyclopts import App

from jobhound.application import relation_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

app = App(name="remove", help="Remove a tag, contact, or link from an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="contact")
def contact(
    slug_query: str,
    /,
    *,
    name: str,
    role: str | None = None,
    channel: str | None = None,
) -> None:
    """Remove a contact."""
    _, after, _ = relation_service.remove_contact(
        _repo(),
        slug_query,
        name=name,
        role=role,
        channel=channel,
    )
    print(f"contact removed: {after.slug} {name}")


@app.command(name="tag")
def tag(
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


@app.command(name="link")
def link(slug_query: str, /, *, name: str) -> None:
    """Remove a named link."""
    _, after, _ = relation_service.remove_link(_repo(), slug_query, name=name)
    print(f"link removed: {after.slug} {name}")
