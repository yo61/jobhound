"""`jh note` — append a timestamped one-liner to notes.md."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    msg: str,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Append a timestamped one-liner to <slug>/notes.md and bump last_activity."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()

    opp, opp_dir = repo.find(slug_query)
    notes = opp_dir / "notes.md"
    existing = notes.read_text() if notes.exists() else ""
    notes.write_text(existing + f"- {today_date.isoformat()} {msg}\n")

    repo.save(
        opp.touch(today=today_date),
        opp_dir,
        message=f"note: {opp.slug}",
        no_commit=no_commit,
    )
    print(f"noted: {opp.slug}")
