"""`jh set` subgroup — single-field setters for an opportunity."""

from __future__ import annotations

import sys
from datetime import datetime

from cyclopts import App

from jobhound.application import field_service, relation_service
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.domain.timekeeping import to_utc
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


@app.command(name="company")
def company(slug_query: str, value: str, /) -> None:
    """Set company name."""
    _, after, _ = field_service.set_company(_repo(), slug_query, value)
    print(f"company {after.slug}: {after.company}")


@app.command(name="role")
def role(slug_query: str, value: str, /) -> None:
    """Set role title."""
    _, after, _ = field_service.set_role(_repo(), slug_query, value)
    print(f"role {after.slug}: {after.role}")


@app.command(name="status")
def status(slug_query: str, value: str, /) -> None:
    """Set status directly (bypasses transition rules)."""
    try:
        s = Status(value)
    except ValueError:
        print(f"value must be one of {[sv.value for sv in Status]}", file=sys.stderr)
        raise SystemExit(1) from None
    _, after, _ = field_service.set_status(_repo(), slug_query, s)
    print(f"status {after.slug}: {after.status.value}")


@app.command(name="source")
def source(slug_query: str, value: str, /) -> None:
    """Set source."""
    _, after, _ = field_service.set_source(_repo(), slug_query, value)
    print(f"source {after.slug}: {after.source}")


@app.command(name="location")
def location(slug_query: str, value: str, /) -> None:
    """Set location."""
    _, after, _ = field_service.set_location(_repo(), slug_query, value)
    print(f"location {after.slug}: {after.location}")


@app.command(name="comp-range")
def comp_range(slug_query: str, value: str, /) -> None:
    """Set compensation range."""
    _, after, _ = field_service.set_comp_range(_repo(), slug_query, value)
    print(f"comp_range {after.slug}: {after.comp_range}")


@app.command(name="first-contact")
def first_contact(slug_query: str, when: datetime, /) -> None:
    """Set first-contact timestamp."""
    _, after, _ = field_service.set_first_contact(_repo(), slug_query, to_utc(when))
    print(f"first_contact {after.slug}: {after.first_contact}")


@app.command(name="applied-on")
def applied_on(slug_query: str, when: datetime, /) -> None:
    """Set applied-on timestamp."""
    _, after, _ = field_service.set_applied_on(_repo(), slug_query, to_utc(when))
    print(f"applied_on {after.slug}: {after.applied_on}")


@app.command(name="last-activity")
def last_activity(slug_query: str, when: datetime, /) -> None:
    """Set last-activity timestamp."""
    _, after, _ = field_service.set_last_activity(_repo(), slug_query, to_utc(when))
    print(f"last_activity {after.slug}: {after.last_activity}")


@app.command(name="next-action")
def next_action(slug_query: str, text: str, due: datetime, /) -> None:
    """Set next-action text and due timestamp."""
    _, after, _ = field_service.set_next_action(_repo(), slug_query, text=text, due=to_utc(due))
    print(f"next_action {after.slug}: {after.next_action} (due {after.next_action_due})")
