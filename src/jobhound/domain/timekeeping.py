"""Timezone-aware datetime helpers. The only module that calls tzlocal.

`to_utc` is the boundary helper — every datetime coming in from an adapter
(CLI flag, MCP arg, file input) passes through this on the way in.
`display_local` is the boundary helper on the way out, for human output.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from tzlocal import get_localzone


def to_utc(value: datetime) -> datetime:
    """Normalise a datetime to tz-aware UTC.

    A naive datetime is interpreted as the user's local zone, then converted.
    An aware datetime (any zone) is converted to UTC by `.astimezone()`.

    Naive midnight is treated as a *bare-date hint*: the input is interpreted
    as noon-local on that date instead, then converted to UTC. This keeps the
    user's calendar date visually intact in the stored UTC string and avoids
    DST-transition edge cases (transitions happen near midnight, noon is safe).
    Practically: `datetime.fromisoformat("2026-04-29")` produces naive midnight,
    which under this rule is stored as noon-local-on-2026-04-29.
    """
    if value.tzinfo is None:
        if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
            value = value.replace(hour=12)
        value = value.replace(tzinfo=get_localzone())
    return value.astimezone(UTC)


def calendar_days_between(then_utc: datetime, now_utc: datetime) -> int:
    """Whole local-TZ calendar days between two UTC instants (≥ 0).

    Both inputs must be tz-aware. The arithmetic counts midnight
    boundaries crossed in the local zone, *not* raw UTC seconds. This
    is the correct semantic for "is this opportunity stale" — humans
    think in calendar days, not 86400-second blocks.
    """
    if then_utc.tzinfo is None or now_utc.tzinfo is None:
        raise ValueError("calendar_days_between requires tz-aware datetimes")
    tz = get_localzone()
    then_local = then_utc.astimezone(tz).date()
    now_local = now_utc.astimezone(tz).date()
    return max((now_local - then_local).days, 0)


def display_local(value: datetime, *, precision: Literal["seconds", "minutes"] = "seconds") -> str:
    """Format a UTC datetime for human display in the user's local zone.

    `precision="seconds"` → `2026-05-14 13:00:30 BST`
    `precision="minutes"` → `2026-05-14 13:00 BST`
    """
    if value.tzinfo is None:
        raise ValueError("display_local requires a tz-aware datetime")
    local = value.astimezone(get_localzone())
    if precision == "seconds":
        return local.strftime("%Y-%m-%d %H:%M:%S %Z")
    return local.strftime("%Y-%m-%d %H:%M %Z")


def now_utc() -> datetime:
    """Current instant as a tz-aware UTC datetime. Use everywhere instead of `date.today()`."""
    return datetime.now(UTC)


def to_local_date(value: datetime) -> date:
    """Convert a tz-aware UTC datetime to a calendar date in the user's local zone.

    Used by slug generation and display formatting where the calendar
    date depends on the viewer's wall-clock day, not UTC's day.
    """
    if value.tzinfo is None:
        raise ValueError("to_local_date requires a tz-aware datetime")
    return value.astimezone(get_localzone()).date()


def _format_z_seconds(value: datetime) -> str:
    """Format a tz-aware UTC datetime as ISO 8601 with Z suffix and whole seconds.

    Used for notes.md line prefixes. Rejects naive inputs.
    """
    if value.tzinfo is None:
        raise ValueError("_format_z_seconds requires a tz-aware datetime")
    value = value.astimezone(UTC).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")
