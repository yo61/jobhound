"""The Slug value object — a validated opportunity identifier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

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
    def build(cls, today: date, company: str, role: str) -> Slug:
        """Construct the canonical `YYYY-MM-company-role` form."""
        return cls(value=f"{today:%Y-%m}-{_slugify(company)}-{_slugify(role)}")

    def __str__(self) -> str:
        return self.value
