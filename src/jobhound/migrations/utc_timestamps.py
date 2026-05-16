"""Migrate bare-date lifecycle fields → tz-aware UTC datetimes.

Idempotent. Safe to re-run. Operates on raw TOML so it doesn't depend on
the post-migration Opportunity type assertions.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, date, datetime, time, tzinfo
from pathlib import Path

import tomli_w
from tzlocal import get_localzone

LIFECYCLE_FIELDS = (
    "first_contact",
    "applied_on",
    "last_activity",
    "next_action_due",
)


def _maybe_convert(value: object, tz: tzinfo) -> datetime | None:
    """Convert a bare date to noon-local→UTC; passthrough for None / datetime.

    Returns None when no conversion is needed (already a datetime or None).
    Returns a datetime when conversion happened.

    Uses noon-local (not midnight-local) so the stored UTC value's calendar
    date matches the original bare date in raw form. Midnight-local can shift
    the visible date by one in the stored UTC string (e.g. 2026-04-29 BST
    midnight stores as 2026-04-28 23:00 UTC), which surprises readers. Noon
    is also safely outside DST transition windows.

    Note: datetime is a subclass of date, so the isinstance(value, datetime)
    check must come before isinstance(value, date).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return None  # already migrated
    if isinstance(value, date):
        local_noon = datetime.combine(value, time(12, 0), tzinfo=tz)
        return local_noon.astimezone(UTC)
    return None


def _migrate_one(path: Path, tz: tzinfo) -> bool:
    """Migrate a single meta.toml. Returns True if anything changed."""
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    changed = False
    for name in LIFECYCLE_FIELDS:
        converted = _maybe_convert(data.get(name), tz)
        if converted is not None:
            data[name] = converted
            changed = True

    if changed:
        with path.open("wb") as fh:
            tomli_w.dump(data, fh)
    return changed


def migrate_data_root(root: Path) -> int:
    """Walk a data root, migrate every meta.toml. Returns count of files changed."""
    tz = get_localzone()
    count = 0
    for subdir in ("opportunities", "archive"):
        base = root / subdir
        if not base.is_dir():
            continue
        for meta in base.glob("*/meta.toml"):
            if _migrate_one(meta, tz):
                count += 1
    return count
