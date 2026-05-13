"""Tests for application/serialization.py — JSON-native dict converters."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from jobhound.application.serialization import (
    SCHEMA_VERSION,
    file_entry_to_dict,
    snapshot_to_dict,
    stats_to_dict,
)
from jobhound.application.snapshots import (
    ComputedFlags,
    FileEntry,
    OpportunitySnapshot,
    Stats,
)
from jobhound.domain.contact import Contact
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status


def _snapshot(**opp_overrides: Any) -> OpportunitySnapshot:
    base: dict[str, Any] = dict(
        slug="2026-05-acme-em",
        company="Acme Corp",
        role="Engineering Manager",
        status=Status.APPLIED,
        priority=Priority.HIGH,
        source="LinkedIn",
        location="Remote, UK",
        comp_range=None,
        first_contact=None,
        applied_on=date(2026, 5, 3),
        last_activity=date(2026, 5, 10),
        next_action="Follow up",
        next_action_due=date(2026, 5, 17),
        tags=("remote", "fintech"),
    )
    base.update(opp_overrides)
    opp = Opportunity(**base)
    return OpportunitySnapshot(
        opportunity=opp,
        archived=False,
        path=Path("/Users/test/.local/share/jh/opportunities/2026-05-acme-em"),
        computed=ComputedFlags(
            is_active=True,
            is_stale=False,
            looks_ghosted=False,
            days_since_activity=2,
        ),
    )


def test_schema_version_is_one() -> None:
    assert SCHEMA_VERSION == 1


def test_snapshot_to_dict_top_level_shape() -> None:
    snap = _snapshot()
    d = snapshot_to_dict(snap)

    assert d["slug"] == "2026-05-acme-em"
    assert d["company"] == "Acme Corp"
    assert d["status"] == "applied"
    assert d["priority"] == "high"
    assert d["applied_on"] == "2026-05-03"
    assert d["last_activity"] == "2026-05-10"

    assert d["archived"] is False
    assert d["path"] == "/Users/test/.local/share/jh/opportunities/2026-05-acme-em"

    assert d["computed"] == {
        "is_active": True,
        "is_stale": False,
        "looks_ghosted": False,
        "days_since_activity": 2,
    }


def test_snapshot_to_dict_omits_none_raw_fields() -> None:
    snap = _snapshot(comp_range=None, first_contact=None)
    d = snapshot_to_dict(snap)
    assert "comp_range" not in d
    assert "first_contact" not in d


def test_snapshot_to_dict_preserves_empty_collections() -> None:
    snap = _snapshot(tags=(), contacts=(), links={})
    d = snapshot_to_dict(snap)
    assert d["tags"] == []
    assert d["contacts"] == []
    assert d["links"] == {}


def test_snapshot_to_dict_serialises_contacts() -> None:
    snap = _snapshot(
        contacts=(Contact(name="Jane Doe", role="Recruiter", channel="email"),),
    )
    d = snapshot_to_dict(snap)
    assert d["contacts"] == [
        {"name": "Jane Doe", "role": "Recruiter", "channel": "email"},
    ]


def test_snapshot_to_dict_computed_days_can_be_null() -> None:
    snap = _snapshot()
    snap = OpportunitySnapshot(
        opportunity=snap.opportunity,
        archived=snap.archived,
        path=snap.path,
        computed=ComputedFlags(
            is_active=True,
            is_stale=False,
            looks_ghosted=False,
            days_since_activity=None,
        ),
    )
    d = snapshot_to_dict(snap)
    assert d["computed"]["days_since_activity"] is None


def test_file_entry_to_dict() -> None:
    entry = FileEntry(
        name="correspondence/2026-05-01-intro.md",
        size=982,
        mtime=datetime(2026, 5, 1, 15, 33, 10, tzinfo=UTC),
    )
    assert file_entry_to_dict(entry) == {
        "name": "correspondence/2026-05-01-intro.md",
        "size": 982,
        "mtime": "2026-05-01T15:33:10Z",
    }


def test_stats_to_dict_funnel_uses_string_keys() -> None:
    funnel = {status: 0 for status in Status}
    funnel[Status.APPLIED] = 3
    funnel[Status.SCREEN] = 1
    stats = Stats(funnel=funnel, sources={"LinkedIn": 4, "(unspecified)": 1})
    d = stats_to_dict(stats)
    assert d["funnel"]["applied"] == 3
    assert d["funnel"]["screen"] == 1
    assert d["sources"] == {"LinkedIn": 4, "(unspecified)": 1}


def test_snapshot_to_dict_is_json_dumpable() -> None:
    """The whole point: no `default` hook needed."""
    snap = _snapshot(
        contacts=(Contact(name="J", role="R", channel="email"),),
        links={"posting": "https://x"},
    )
    text = json.dumps(snapshot_to_dict(snap))
    assert "2026-05-acme-em" in text
