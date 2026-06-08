"""`jh contact` subgroup — manage contacts on an opportunity."""

from __future__ import annotations

from cyclopts import App

from jobhound.application import relation_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

app = App(name="contact", help="Manage contacts on an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="add")
def add(
    slug_query: str,
    /,
    *,
    name: str,
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
) -> None:
    """Add a contact."""
    _, after, _ = relation_service.add_contact(
        _repo(),
        slug_query,
        name=name,
        role=role_title,
        channel=channel,
        company=company,
        note=note,
    )
    print(f"contact added: {after.slug} {name}")


@app.command(name="remove")
def remove(
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
