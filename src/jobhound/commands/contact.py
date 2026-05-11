"""`jh contact` — append a contact entry."""

from __future__ import annotations

from dataclasses import replace
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
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add a contact to the contacts list."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    entry: dict[str, str] = {"name": name}
    if role_title is not None:
        entry["role"] = role_title
    if channel is not None:
        entry["channel"] = channel
    if company is not None:
        entry["company"] = company
    if note is not None:
        entry["note"] = note
    updated = replace(opp, contacts=(*opp.contacts, entry))
    repo.save(updated, opp_dir, message=f"contact: {opp.slug} {name}", no_commit=no_commit)
    print(f"contact added: {opp.slug} {name}")
