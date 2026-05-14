"""`jh note` — append a timestamped one-liner to notes.md."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.application import ops_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    msg: str,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Append a dated one-liner to <slug>/notes.md and bump last_activity."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()
    _, after, _ = ops_service.add_note(
        repo,
        slug_query,
        msg=msg,
        today=today_date,
        no_commit=no_commit,
    )
    print(f"noted: {after.slug}")
