"""Read, write, and validate `meta.toml` files."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from jobhound.opportunities import Opportunity, opportunity_from_dict


class ValidationError(Exception):
    """Raised when a meta.toml fails parsing or schema validation."""


_FIELD_ORDER: tuple[str, ...] = (
    "company",
    "role",
    "slug",
    "source",
    "status",
    "priority",
    "first_contact",
    "applied_on",
    "last_activity",
    "next_action",
    "next_action_due",
    "location",
    "comp_range",
    "tags",
    "contacts",
    "links",
)


def _check_slug_safe(slug: str) -> None:
    if "/" in slug or "\\" in slug:
        raise ValidationError(f"slug {slug!r} contains a path separator")
    if slug.startswith(".") or slug != slug.strip():
        raise ValidationError(f"slug {slug!r} starts with '.' or has surrounding whitespace")
    if not slug or any(ch.isspace() for ch in slug):
        raise ValidationError(f"slug {slug!r} contains whitespace or is empty")


def validate(data: dict[str, Any], path: Path | None) -> Opportunity:
    """Parse a meta.toml dict and return the Opportunity (or raise ValidationError)."""
    if not isinstance(data, dict):
        raise ValidationError("meta.toml must be a table at the top level")
    try:
        opp = opportunity_from_dict(data, path)
    except KeyError as exc:
        raise ValidationError(f"missing required field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    _check_slug_safe(opp.slug)
    return opp


def read_meta(path: Path) -> Opportunity:
    """Load `path` and return an Opportunity. Raises ValidationError on any failure."""
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError(f"meta.toml is not valid TOML: {exc}") from exc
    return validate(data, path)


def _as_serializable(opp: Opportunity) -> dict[str, Any]:
    """Build the dict that tomli_w will write, in stable field order, dropping None."""
    raw: dict[str, Any] = {
        "company": opp.company,
        "role": opp.role,
        "slug": opp.slug,
        "source": opp.source,
        "status": opp.status.value,
        "priority": opp.priority,
        "first_contact": opp.first_contact,
        "applied_on": opp.applied_on,
        "last_activity": opp.last_activity,
        "next_action": opp.next_action,
        "next_action_due": opp.next_action_due,
        "location": opp.location,
        "comp_range": opp.comp_range,
        "tags": list(opp.tags) if opp.tags else None,
        "contacts": [dict(c) for c in opp.contacts] if opp.contacts else None,
        "links": dict(opp.links) if opp.links else None,
    }
    return {k: raw[k] for k in _FIELD_ORDER if raw.get(k) is not None}


def write_meta(opp: Opportunity, path: Path) -> None:
    """Write `opp` to `path` as TOML with stable field order. None fields are omitted."""
    data = _as_serializable(opp)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)
