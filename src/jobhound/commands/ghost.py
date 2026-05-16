"""`jh ghost` — no response, status → ghosted."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from cyclopts import Parameter

from jobhound.commands._terminal import run_transition


def run(
    slug_query: str,
    /,
    *,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Mark this opportunity as ghosted (no response, giving up)."""
    run_transition(
        slug_query=slug_query,
        verb="ghost",
        now=now,
    )
