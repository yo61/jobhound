"""`jh note` — append a timestamped one-liner to notes.md."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import ops_service
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore


def run(
    slug_query: str,
    /,
    *,
    msg: str,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Append a dated one-liner to <slug>/notes.md and bump last_activity."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    store = GitLocalFileStore(repo.paths)
    now_obj = to_utc(now) if now else now_utc()
    _, after, _ = ops_service.add_note(repo, store, slug_query, msg=msg, now=now_obj)
    print(f"noted: {after.slug}")
