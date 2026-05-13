"""The Opportunity dataclass and its queries."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

from jobhound.domain.contact import Contact
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.domain.transitions import require_transition

STALE_DAYS: int = 14
GHOSTED_DAYS: int = 21


@dataclass(frozen=True)
class Opportunity:
    """A single opportunity loaded from `<slug>/meta.toml`."""

    slug: str
    company: str
    role: str
    status: Status
    priority: Priority
    source: str | None
    location: str | None
    comp_range: str | None
    first_contact: date | None
    applied_on: date | None
    last_activity: date | None
    next_action: str | None
    next_action_due: date | None
    tags: tuple[str, ...] = field(default_factory=tuple)
    contacts: tuple[Contact, ...] = field(default_factory=tuple)
    links: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status.is_active

    def days_since_activity(self, today: date) -> int | None:
        if self.last_activity is None:
            return None
        return (today - self.last_activity).days

    def is_stale(self, today: date) -> bool:
        days = self.days_since_activity(today)
        return self.is_active and days is not None and days >= STALE_DAYS

    def looks_ghosted(self, today: date) -> bool:
        days = self.days_since_activity(today)
        return self.is_active and days is not None and days >= GHOSTED_DAYS

    # ---- behaviour: state transitions --------------------------------------

    def apply(
        self,
        *,
        applied_on: date,
        today: date,
        next_action: str,
        next_action_due: date,
    ) -> Opportunity:
        """Submit the application. Requires status `prospect`."""
        require_transition(self.status, Status.APPLIED, verb="apply")
        return replace(
            self,
            status=Status.APPLIED,
            applied_on=applied_on,
            last_activity=today,
            next_action=next_action,
            next_action_due=next_action_due,
        )

    def log_interaction(
        self,
        *,
        today: date,
        next_status: str,
        next_action: str | None,
        next_action_due: date | None,
        force: bool,
    ) -> Opportunity:
        """Record an interaction. `next_status='stay'` keeps the current status."""
        if not force:
            require_transition(self.status, next_status, verb="log")
        new_status = self.status if next_status == "stay" else Status(next_status)
        return replace(
            self,
            status=new_status,
            last_activity=today,
            next_action=next_action if next_action is not None else self.next_action,
            next_action_due=(
                next_action_due if next_action_due is not None else self.next_action_due
            ),
        )

    def withdraw(self, *, today: date) -> Opportunity:
        """Move to status `withdrawn`. Requires an active status."""
        require_transition(self.status, Status.WITHDRAWN, verb="withdraw")
        return replace(self, status=Status.WITHDRAWN, last_activity=today)

    def ghost(self, *, today: date) -> Opportunity:
        """Move to status `ghosted`. Requires an active status."""
        require_transition(self.status, Status.GHOSTED, verb="ghost")
        return replace(self, status=Status.GHOSTED, last_activity=today)

    def accept(self, *, today: date) -> Opportunity:
        """Move to status `accepted`. Requires status `offer`."""
        require_transition(self.status, Status.ACCEPTED, verb="accept")
        return replace(self, status=Status.ACCEPTED, last_activity=today)

    def decline(self, *, today: date) -> Opportunity:
        """Move to status `declined`. Requires status `offer`."""
        require_transition(self.status, Status.DECLINED, verb="decline")
        return replace(self, status=Status.DECLINED, last_activity=today)

    # ---- behaviour: field-shaped operations --------------------------------

    def touch(self, *, today: date) -> Opportunity:
        """Bump `last_activity` without changing status."""
        return replace(self, last_activity=today)

    def with_tags(self, *, add: set[str], remove: set[str]) -> Opportunity:
        """Apply tag add/remove deltas; resulting tag tuple is sorted and deduped."""
        tags = tuple(sorted((set(self.tags) | add) - remove))
        return replace(self, tags=tags)

    def with_priority(self, priority: Priority | str) -> Opportunity:
        """Set priority to one of high/medium/low."""
        return replace(self, priority=Priority(priority))

    def with_contact(self, contact: Contact) -> Opportunity:
        """Append a contact entry."""
        return replace(self, contacts=(*self.contacts, contact))

    def with_link(self, *, name: str, url: str) -> Opportunity:
        """Set or replace a link entry."""
        links = dict(self.links)
        links[name] = url
        return replace(self, links=links)


def opportunity_from_dict(data: dict[str, Any], path: Path | None = None) -> Opportunity:
    """Build an Opportunity from a parsed meta.toml dict."""
    raw_status = data.get("status", "prospect")
    try:
        status = Status(raw_status)
    except ValueError as exc:
        raise ValueError(f"Unknown status {raw_status!r} in {path}") from exc
    return Opportunity(
        slug=data.get("slug") or (path.parent.name if path else ""),
        company=data["company"],
        role=data["role"],
        status=status,
        priority=Priority(data.get("priority", "medium")),
        source=data.get("source"),
        location=data.get("location"),
        comp_range=data.get("comp_range"),
        first_contact=data.get("first_contact"),
        applied_on=data.get("applied_on"),
        last_activity=data.get("last_activity"),
        next_action=data.get("next_action"),
        next_action_due=data.get("next_action_due"),
        tags=tuple(data.get("tags") or ()),
        contacts=tuple(Contact.from_dict(c) for c in (data.get("contacts") or ())),
        links={k: v for k, v in (data.get("links") or {}).items() if v is not None},
    )
