"""`jh contact` — append a contact entry."""

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
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
) -> None:
    """Add a contact to the contacts list."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    _, after, _ = relation_service.add_contact(
        repo,
        slug_query,
        name=name,
        role=role_title,
        channel=channel,
        company=company,
        note=note,
    )
    print(f"contact added: {after.slug} {name}")
