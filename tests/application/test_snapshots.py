"""Tests for application/snapshots.py — frozen read-side dataclasses."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from jobhound.application.snapshots import (
    ComputedFlags,
    FileEntry,
    OpportunitySnapshot,
    Stats,
)
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status


def _opp(**overrides: Any) -> Opportunity:
    base: dict[str, Any] = dict(
        slug="2026-05-acme-em",
        company="Acme",
        role="EM",
        status=Status.APPLIED,
        priority=Priority.HIGH,
        source="LinkedIn",
        location=None,
        comp_range=None,
        first_contact=None,
        applied_on=date(2026, 5, 3),
        last_activity=date(2026, 5, 10),
        next_action=None,
        next_action_due=None,
    )
    base.update(overrides)
    return Opportunity(**base)


def test_computed_flags_is_frozen() -> None:
    flags = ComputedFlags(
        is_active=True, is_stale=False, looks_ghosted=False, days_since_activity=2
    )
    with pytest.raises((AttributeError, TypeError)):
        flags.is_active = False  # ty: ignore[invalid-assignment]


def test_snapshot_carries_opportunity_path_and_flags(tmp_path: Path) -> None:
    opp = _opp()
    snap = OpportunitySnapshot(
        opportunity=opp,
        archived=False,
        path=tmp_path,
        computed=ComputedFlags(
            is_active=True, is_stale=False, looks_ghosted=False, days_since_activity=2
        ),
    )
    assert snap.opportunity is opp
    assert snap.archived is False
    assert snap.path == tmp_path
    assert snap.computed.is_active is True


def test_snapshot_is_frozen(tmp_path: Path) -> None:
    snap = OpportunitySnapshot(
        opportunity=_opp(),
        archived=False,
        path=tmp_path,
        computed=ComputedFlags(True, False, False, 0),
    )
    with pytest.raises((AttributeError, TypeError)):
        snap.archived = True  # ty: ignore[invalid-assignment]


def test_file_entry_fields() -> None:
    mtime = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
    entry = FileEntry(name="meta.toml", size=412, mtime=mtime)
    assert entry.name == "meta.toml"
    assert entry.size == 412
    assert entry.mtime == mtime
    assert entry.mtime.tzinfo is UTC


def test_stats_fields() -> None:
    stats = Stats(
        funnel={Status.APPLIED: 3, Status.SCREEN: 1},
        sources={"LinkedIn": 2, "(unspecified)": 1},
    )
    assert stats.funnel[Status.APPLIED] == 3
    assert stats.sources["LinkedIn"] == 2
