"""The Slug value object — a validated opportunity identifier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from tzlocal import get_localzone

from jobhound.domain.timekeeping import to_utc

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _NON_ALNUM.sub("-", text.lower()).strip("-")
    return s or "untitled"


@dataclass(frozen=True)
class Slug:
    """An opportunity slug. Construct via `Slug.create()` or `Slug.build()`."""

    value: str

    @classmethod
    def create(cls, raw: str) -> Slug:
        """Validate and wrap an existing slug string."""
        if not raw:
            raise ValueError("slug is empty")
        if raw != raw.strip():
            raise ValueError(f"slug {raw!r} has surrounding whitespace")
        if "/" in raw or "\\" in raw:
            raise ValueError(f"slug {raw!r} contains a path separator")
        if raw.startswith("."):
            raise ValueError(f"slug {raw!r} starts with '.'")
        if any(ch.isspace() for ch in raw):
            raise ValueError(f"slug {raw!r} contains whitespace")
        return cls(value=raw)

    @classmethod
    def build(cls, now: datetime, company: str, role: str) -> Slug:
        """Build a slug from current instant, company, and role.

        The date prefix uses the user's local-zone calendar date (slugs are
        human-readable filesystem identifiers, not UTC instants).
        """
        now_utc_value = to_utc(now)
        local_date = now_utc_value.astimezone(get_localzone()).date()
        prefix = f"{local_date:%Y-%m}"
        return cls(value=f"{prefix}-{_slugify(company)}-{_slugify(role)}")

    def __str__(self) -> str:
        return self.value
