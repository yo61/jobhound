"""Frozen read-side dataclasses returned by OpportunityQuery.

These are pure data: no I/O, no methods that touch disk or git. Construction
is the only place where derived fields (ComputedFlags) get materialised — once
built, a snapshot is immutable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.status import Status


@dataclass(frozen=True)
class ComputedFlags:
    """Derived flags evaluated at a fixed `today` so JSON output is frozen-in-time."""

    is_active: bool
    is_stale: bool
    looks_ghosted: bool
    days_since_activity: int | None


@dataclass(frozen=True)
class OpportunitySnapshot:
    """A single opportunity plus its archive flag, absolute path, and computed flags."""

    opportunity: Opportunity
    archived: bool
    path: Path
    computed: ComputedFlags


@dataclass(frozen=True)
class FileEntry:
    """One file inside an opportunity directory. `name` is relative to the opp dir."""

    name: str
    size: int
    mtime: datetime


@dataclass(frozen=True)
class Stats:
    """Aggregate counts. `funnel` covers every Status; `sources` uses `(unspecified)` for None."""

    funnel: dict[Status, int]
    sources: dict[str, int]
