"""`jh clear` subgroup — clear nullable fields on an opportunity."""

from __future__ import annotations

from cyclopts import App

from jobhound.application import field_service
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

app = App(name="clear", help="Clear a nullable field on an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="source")
def source(slug_query: str, /) -> None:
    """Clear source."""
    _, after, _ = field_service.set_source(_repo(), slug_query, None)
    print(f"source {after.slug}: cleared")


@app.command(name="location")
def location(slug_query: str, /) -> None:
    """Clear location."""
    _, after, _ = field_service.set_location(_repo(), slug_query, None)
    print(f"location {after.slug}: cleared")


@app.command(name="comp-range")
def comp_range(slug_query: str, /) -> None:
    """Clear comp-range."""
    _, after, _ = field_service.set_comp_range(_repo(), slug_query, None)
    print(f"comp_range {after.slug}: cleared")


@app.command(name="first-contact")
def first_contact(slug_query: str, /) -> None:
    """Clear first-contact."""
    _, after, _ = field_service.set_first_contact(_repo(), slug_query, None)
    print(f"first_contact {after.slug}: cleared")


@app.command(name="applied-on")
def applied_on(slug_query: str, /) -> None:
    """Clear applied-on."""
    _, after, _ = field_service.set_applied_on(_repo(), slug_query, None)
    print(f"applied_on {after.slug}: cleared")


@app.command(name="last-activity")
def last_activity(slug_query: str, /) -> None:
    """Clear last-activity."""
    _, after, _ = field_service.set_last_activity(_repo(), slug_query, None)
    print(f"last_activity {after.slug}: cleared")


@app.command(name="next-action")
def next_action(slug_query: str, /) -> None:
    """Clear next-action and its due date."""
    _, after, _ = field_service.set_next_action(_repo(), slug_query, text=None, due=None)
    print(f"next_action {after.slug}: cleared")
