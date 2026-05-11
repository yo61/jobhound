"""`jh ghost` — no response, status → ghosted."""

from __future__ import annotations

from typing import Annotated

from cyclopts import Parameter

from jobhound.commands._terminal import run_transition


def run(
    slug_query: str,
    /,
    *,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Mark this opportunity as ghosted (no response, giving up)."""
    run_transition(
        slug_query=slug_query,
        verb="ghost",
        today=today,
        no_commit=no_commit,
    )
