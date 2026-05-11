"""The Opportunity dataclass and its queries.

Ported from the old repo's `opportunities.py`. The TOML layer hands us native
`datetime.date` values, so the old `_coerce_date` helper is gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

ACTIVE_STATUSES: tuple[str, ...] = (
    "prospect",
    "applied",
    "screen",
    "interview",
    "offer",
)
CLOSED_STATUSES: tuple[str, ...] = (
    "accepted",
    "declined",
    "rejected",
    "withdrawn",
    "ghosted",
)
ALL_STATUSES: tuple[str, ...] = ACTIVE_STATUSES + CLOSED_STATUSES

STALE_DAYS: int = 14
GHOSTED_DAYS: int = 21

_PRIORITIES: frozenset[str] = frozenset({"high", "medium", "low"})


def _require_transition(current: str, target: str, *, verb: str) -> None:
    """Local indirection that defers the import of `transitions.require_transition`.

    The module-level cycle (transitions.py imports ACTIVE_STATUSES from here) means
    we can't import at module top. Each call is cached by sys.modules after the
    first hit, so the overhead is negligible.
    """
    from jobhound.transitions import require_transition

    require_transition(current, target, verb=verb)


@dataclass(frozen=True)
class Opportunity:
    """A single opportunity loaded from `<slug>/meta.toml`."""

    slug: str
    company: str
    role: str
    status: str
    priority: str
    source: str | None
    location: str | None
    comp_range: str | None
    first_contact: date | None
    applied_on: date | None
    last_activity: date | None
    next_action: str | None
    next_action_due: date | None
    tags: tuple[str, ...] = field(default_factory=tuple)
    contacts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    links: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

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
        _require_transition(self.status, "applied", verb="apply")
        return replace(
            self,
            status="applied",
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
            _require_transition(self.status, next_status, verb="log")
        new_status = self.status if next_status == "stay" else next_status
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
        _require_transition(self.status, "withdrawn", verb="withdraw")
        return replace(self, status="withdrawn", last_activity=today)

    def ghost(self, *, today: date) -> Opportunity:
        """Move to status `ghosted`. Requires an active status."""
        _require_transition(self.status, "ghosted", verb="ghost")
        return replace(self, status="ghosted", last_activity=today)

    def accept(self, *, today: date) -> Opportunity:
        """Move to status `accepted`. Requires status `offer`."""
        _require_transition(self.status, "accepted", verb="accept")
        return replace(self, status="accepted", last_activity=today)

    def decline(self, *, today: date) -> Opportunity:
        """Move to status `declined`. Requires status `offer`."""
        _require_transition(self.status, "declined", verb="decline")
        return replace(self, status="declined", last_activity=today)

    # ---- behaviour: field-shaped operations --------------------------------

    def touch(self, *, today: date) -> Opportunity:
        """Bump `last_activity` without changing status."""
        return replace(self, last_activity=today)

    def with_tags(self, *, add: set[str], remove: set[str]) -> Opportunity:
        """Apply tag add/remove deltas; resulting tag tuple is sorted and deduped."""
        tags = tuple(sorted((set(self.tags) | add) - remove))
        return replace(self, tags=tags)

    def with_priority(self, priority: str) -> Opportunity:
        """Set priority to one of high/medium/low."""
        if priority not in _PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(_PRIORITIES)}, got {priority!r}")
        return replace(self, priority=priority)

    def with_contact(self, contact: dict[str, str]) -> Opportunity:
        """Append a contact entry. `name` is required and non-empty."""
        name = contact.get("name")
        if not name:
            raise ValueError("contact must have a non-empty 'name'")
        return replace(self, contacts=(*self.contacts, dict(contact)))

    def with_link(self, *, name: str, url: str) -> Opportunity:
        """Set or replace a link entry."""
        links = dict(self.links)
        links[name] = url
        return replace(self, links=links)


def opportunity_from_dict(data: dict[str, Any], path: Path | None = None) -> Opportunity:
    """Build an Opportunity from a parsed meta.toml dict."""
    status = data.get("status", "prospect")
    if status not in ALL_STATUSES:
        raise ValueError(f"Unknown status {status!r} in {path}")
    return Opportunity(
        slug=data.get("slug") or (path.parent.name if path else ""),
        company=data["company"],
        role=data["role"],
        status=status,
        priority=data.get("priority", "medium"),
        source=data.get("source"),
        location=data.get("location"),
        comp_range=data.get("comp_range"),
        first_contact=data.get("first_contact"),
        applied_on=data.get("applied_on"),
        last_activity=data.get("last_activity"),
        next_action=data.get("next_action"),
        next_action_due=data.get("next_action_due"),
        tags=tuple(data.get("tags") or ()),
        contacts=tuple(data.get("contacts") or ()),
        links=dict(data.get("links") or {}),
        path=path,
    )
