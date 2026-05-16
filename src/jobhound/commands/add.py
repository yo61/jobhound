"""`jh add` subgroup — append contacts, notes, and tags to an opportunity."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from cyclopts import App, Parameter

from jobhound.application import ops_service, relation_service
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

app = App(name="add", help="Add a tag, contact, or note to an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="contact")
def contact(
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


@app.command(name="note")
def note(
    slug_query: str,
    /,
    *,
    msg: str,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Add a timestamped note."""
    repo = _repo()
    store = GitLocalFileStore(repo.paths)
    now_obj = to_utc(now) if now else now_utc()
    _, after, _ = ops_service.add_note(repo, store, slug_query, msg=msg, now=now_obj)
    print(f"noted: {after.slug}")


@app.command(name="tag")
def tag(
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
