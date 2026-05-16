"""Tests for mcp/converters.py."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from jobhound.domain.contact import Contact
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.mcp.converters import compute_diff, mutation_response

NOON_UTC = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def _opp() -> Opportunity:
    return Opportunity(
        slug="2026-05-acme",
        company="Acme",
        role="EM",
        status=Status.APPLIED,
        priority=Priority.MEDIUM,
        source="LinkedIn",
        location=None,
        comp_range=None,
        first_contact=None,
        applied_on=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        last_activity=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
        next_action=None,
        next_action_due=None,
    )


def test_compute_diff_empty_when_identical() -> None:
    opp = _opp()
    assert compute_diff(opp, opp) == {}


def test_compute_diff_priority_change() -> None:
    before = _opp()
    after = replace(before, priority=Priority.HIGH)
    assert compute_diff(before, after) == {"priority": ["medium", "high"]}


def test_compute_diff_status_change() -> None:
    before = _opp()
    after = replace(before, status=Status.SCREEN)
    assert compute_diff(before, after) == {"status": ["applied", "screen"]}


def test_compute_diff_date_change_iso_formatted() -> None:
    before = _opp()
    after = replace(before, last_activity=NOON_UTC)
    assert compute_diff(before, after) == {
        "last_activity": ["2026-05-10T12:00:00Z", "2026-05-14T12:00:00Z"],
    }


def test_compute_diff_tags_change() -> None:
    before = _opp()
    after = replace(before, tags=("remote",))
    assert compute_diff(before, after) == {"tags": [[], ["remote"]]}


def test_compute_diff_contacts_change() -> None:
    before = _opp()
    after = replace(before, contacts=(Contact(name="Jane", role="Recruiter", channel="email"),))
    diff = compute_diff(before, after)
    assert diff == {
        "contacts": [
            [],
            [{"name": "Jane", "role": "Recruiter", "channel": "email"}],
        ],
    }


def test_compute_diff_multiple_fields() -> None:
    before = _opp()
    after = replace(before, priority=Priority.HIGH, status=Status.SCREEN)
    assert compute_diff(before, after) == {
        "priority": ["medium", "high"],
        "status": ["applied", "screen"],
    }


def test_mutation_response_carries_opportunity_and_diff(tmp_path: Path) -> None:
    before = _opp()
    after = replace(before, priority=Priority.HIGH)
    resp = mutation_response(
        before,
        after,
        tmp_path / "acme",
        now=NOON_UTC,
    )
    assert resp["changed"] == {"priority": ["medium", "high"]}
    assert resp["opportunity"]["priority"] == "high"
    assert resp["opportunity"]["slug"] == "2026-05-acme"


def test_mutation_response_new_opp_has_null_changed(tmp_path: Path) -> None:
    after = _opp()
    resp = mutation_response(
        None,
        after,
        tmp_path / "acme",
        now=NOON_UTC,
    )
    assert resp["changed"] is None
    assert resp["opportunity"]["slug"] == "2026-05-acme"
