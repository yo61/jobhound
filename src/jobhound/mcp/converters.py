"""Diff computation and mutation-response builder for MCP tools."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from jobhound.application.serialization import snapshot_to_dict
from jobhound.application.snapshots import ComputedFlags, OpportunitySnapshot
from jobhound.domain.opportunities import Opportunity


def _field_value(opp: Opportunity, field: str) -> Any:
    """Return the JSON-native value of one Opportunity field."""
    val = getattr(opp, field)
    if val is None:
        return None
    if hasattr(val, "isoformat"):  # date
        return val.isoformat()
    if hasattr(val, "value"):  # StrEnum
        return val.value
    if field == "tags":
        return list(val)
    if field == "contacts":
        return [{"name": c.name, "role": c.role, "channel": c.channel} for c in val]
    if field == "links":
        return dict(val)
    return val


_FIELDS = (
    "slug",
    "company",
    "role",
    "status",
    "priority",
    "source",
    "location",
    "comp_range",
    "first_contact",
    "applied_on",
    "last_activity",
    "next_action",
    "next_action_due",
    "tags",
    "contacts",
    "links",
)


def compute_diff(before: Opportunity, after: Opportunity) -> dict[str, list[Any]]:
    """Return {field: [before_value, after_value]} for every changed field.

    Empty dict means an idempotent no-op write. Values are JSON-native
    (dates as ISO strings, enums as .value, contacts as dicts).
    """
    out: dict[str, list[Any]] = {}
    for field in _FIELDS:
        b = _field_value(before, field)
        a = _field_value(after, field)
        if b != a:
            out[field] = [b, a]
    return out


def mutation_response(
    before: Opportunity | None,
    after: Opportunity,
    opp_dir: Path,
    *,
    today: date,
    archived: bool = False,
) -> dict[str, Any]:
    """Build the {opportunity, changed} payload returned by mutation tools."""
    flags = ComputedFlags(
        is_active=after.is_active,
        is_stale=after.is_stale(today),
        looks_ghosted=after.looks_ghosted(today),
        days_since_activity=after.days_since_activity(today),
    )
    snap = OpportunitySnapshot(
        opportunity=after,
        archived=archived,
        path=opp_dir,
        computed=flags,
    )
    changed = compute_diff(before, after) if before is not None else None
    return {"opportunity": snapshot_to_dict(snap), "changed": changed}
