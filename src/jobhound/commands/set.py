"""`jh set` subgroup — single-field setters for an opportunity."""

from __future__ import annotations

import sys

from cyclopts import App

from jobhound.application import field_service, relation_service
from jobhound.domain.priority import Priority
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

app = App(name="set", help="Set a single field on an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="priority")
def priority(
    slug_query: str,
    /,
    *,
    to: str,
) -> None:
    """Set priority (high, medium, low)."""
    try:
        p = Priority(to)
    except ValueError:
        print(f"--to must be one of {[pv.value for pv in Priority]}", file=sys.stderr)
        raise SystemExit(1) from None
    _, after, _ = field_service.set_priority(_repo(), slug_query, p)
    print(f"priority {after.slug}: {after.priority.value}")


@app.command(name="link")
def link(
    slug_query: str,
    /,
    *,
    name: str,
    url: str,
) -> None:
    """Set or replace a named link."""
    _, after, _ = relation_service.set_link(_repo(), slug_query, name=name, url=url)
    print(f"link {after.slug}: {name} = {url}")
