"""`jh contact` — append a contact entry."""

from __future__ import annotations

from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.contact import Contact
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    name: str,
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add a contact to the contacts list."""
    contact = Contact(
        name=name,
        role=role_title,
        channel=channel,
        company=company,
        note=note,
    )
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = opp.with_contact(contact)
    repo.save(updated, opp_dir, message=f"contact: {opp.slug} {name}", no_commit=no_commit)
    print(f"contact added: {opp.slug} {name}")
