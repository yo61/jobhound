"""JSON-native dict converters for read-side snapshots.

Functions in this module return only JSON-native types (str, int, bool, None,
list, dict). Dates, datetimes, Path, and StrEnum values are converted
explicitly here so callers can use `json.dumps(...)` without a `default` hook.

This is the single source of truth for the wire shape. The CLI, the future
HTTP daemon, and any future export format share these helpers.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from jobhound.application.snapshots import (
    FileEntry,
    OpportunitySnapshot,
    Stats,
)

SCHEMA_VERSION: int = 2


def _date_or_none(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _datetime_or_none(value: datetime | None) -> str | None:
    return _datetime_to_z(value) if value is not None else None


def _datetime_to_z(value: datetime) -> str:
    """Format a tz-aware UTC datetime as ISO 8601 with `Z` suffix."""
    return value.isoformat().replace("+00:00", "Z")


def snapshot_to_dict(snap: OpportunitySnapshot) -> dict[str, Any]:
    """Serialise an OpportunitySnapshot to JSON-native dict per the spec."""
    opp = snap.opportunity
    raw: dict[str, Any] = {
        "slug": opp.slug,
        "company": opp.company,
        "role": opp.role,
        "status": opp.status.value,
        "priority": opp.priority.value,
        "source": opp.source,
        "location": opp.location,
        "comp_range": opp.comp_range,
        "first_contact": _datetime_or_none(opp.first_contact),
        "applied_on": _datetime_or_none(opp.applied_on),
        "last_activity": _datetime_or_none(opp.last_activity),
        "next_action": opp.next_action,
        "next_action_due": _datetime_or_none(opp.next_action_due),
    }
    out: dict[str, Any] = {k: v for k, v in raw.items() if v is not None}

    out["tags"] = list(opp.tags)
    out["contacts"] = [{"name": c.name, "role": c.role, "channel": c.channel} for c in opp.contacts]
    out["links"] = dict(opp.links)

    out["archived"] = snap.archived
    out["path"] = str(snap.path)
    out["computed"] = {
        "is_active": snap.computed.is_active,
        "is_stale": snap.computed.is_stale,
        "looks_ghosted": snap.computed.looks_ghosted,
        "days_since_activity": snap.computed.days_since_activity,
    }
    return out


def file_entry_to_dict(entry: FileEntry) -> dict[str, Any]:
    """Serialise a FileEntry to JSON-native dict."""
    return {
        "name": entry.name,
        "size": entry.size,
        "mtime": _datetime_to_z(entry.mtime),
    }


def stats_to_dict(stats: Stats) -> dict[str, Any]:
    """Serialise Stats to JSON-native dict with string status keys."""
    return {
        "funnel": {status.value: count for status, count in stats.funnel.items()},
        "sources": dict(stats.sources),
    }


def list_envelope(
    snapshots: list[OpportunitySnapshot],
    *,
    timestamp: datetime,
    db_root: Path,
) -> dict[str, Any]:
    """Build the bulk-export envelope (jh export)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": _datetime_to_z(timestamp),
        "db_root": str(db_root),
        "opportunities": [snapshot_to_dict(s) for s in snapshots],
    }


def show_envelope(
    snapshot: OpportunitySnapshot,
    *,
    timestamp: datetime,
    db_root: Path,
) -> dict[str, Any]:
    """Build the single-opportunity envelope (jh show --json)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": _datetime_to_z(timestamp),
        "db_root": str(db_root),
        "opportunity": snapshot_to_dict(snapshot),
    }
