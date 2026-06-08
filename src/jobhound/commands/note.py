"""`jh note` subgroup — manage notes on an opportunity."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from cyclopts import App, Parameter

from jobhound.application import notes_service
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

app = App(name="note", help="Manage notes on an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="add")
def add(
    slug_query: str,
    /,
    *,
    msg: str,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Add a timestamped note."""
    repo = _repo()
    store = GitLocalFileStore(repo.paths)
    now_obj = to_utc(now) if now else now_utc().replace(microsecond=0)
    result = notes_service.add_note(repo, store, slug_query, body=msg, now=now_obj)
    print(f"noted: {result.after.slug}")
