"""`jh accept` — accepted offer, status → accepted."""

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
    """Accept the offer."""
    run_transition(
        slug_query=slug_query,
        verb="accept",
        today=today,
        no_commit=no_commit,
    )
