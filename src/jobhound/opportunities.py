"""The Opportunity dataclass and its queries.

Ported from the old repo's `opportunities.py`. The TOML layer hands us native
`datetime.date` values, so the old `_coerce_date` helper is gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
