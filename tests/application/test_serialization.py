"""Tests for application/serialization.py — JSON-native dict converters."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jobhound.application.serialization import (
    SCHEMA_VERSION,
    file_entry_to_dict,
    list_envelope,
    show_envelope,
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
        applied_on=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
        last_activity=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
        next_action="Follow up",
        next_action_due=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
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


def test_schema_version_is_two() -> None:
    assert SCHEMA_VERSION == 2


def test_snapshot_to_dict_top_level_shape() -> None:
    snap = _snapshot()
    d = snapshot_to_dict(snap)

    assert d["slug"] == "2026-05-acme-em"
    assert d["company"] == "Acme Corp"
    assert d["status"] == "applied"
    assert d["priority"] == "high"
    assert d["applied_on"].startswith("2026-05-03T12:00:00")
    assert d["applied_on"].endswith("Z")
    assert d["last_activity"].startswith("2026-05-10T12:00:00")
    assert d["last_activity"].endswith("Z")

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


def test_list_envelope_shape() -> None:
    snap = _snapshot()
    ts = datetime(2026, 5, 12, 14, 23, 45, 121000, tzinfo=UTC)
    db_root = Path("/Users/test/.local/share/jh")
    env = list_envelope([snap], timestamp=ts, db_root=db_root)
    assert env["schema_version"] == SCHEMA_VERSION  # 2
    assert env["timestamp"] == "2026-05-12T14:23:45.121000Z"
    assert env["db_root"] == "/Users/test/.local/share/jh"
    assert isinstance(env["opportunities"], list)
    assert env["opportunities"][0]["slug"] == "2026-05-acme-em"


def test_list_envelope_empty_opportunities() -> None:
    ts = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
    env = list_envelope([], timestamp=ts, db_root=Path("/x"))
    assert env["opportunities"] == []


def test_show_envelope_uses_singular_key() -> None:
    snap = _snapshot()
    ts = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
    env = show_envelope(snap, timestamp=ts, db_root=Path("/x"))
    assert "opportunity" in env
    assert "opportunities" not in env
    assert env["opportunity"]["slug"] == "2026-05-acme-em"


def test_envelopes_are_json_dumpable() -> None:
    snap = _snapshot()
    ts = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
    list_text = json.dumps(list_envelope([snap], timestamp=ts, db_root=Path("/x")))
    show_text = json.dumps(show_envelope(snap, timestamp=ts, db_root=Path("/x")))
    assert "2026-05-acme-em" in list_text
    assert "2026-05-acme-em" in show_text
