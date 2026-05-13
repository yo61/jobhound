"""Tests for the Opportunity dataclass and its queries."""

from datetime import date

import pytest

from jobhound.domain.opportunities import (
    GHOSTED_DAYS,
    STALE_DAYS,
    Opportunity,
    opportunity_from_dict,
)
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status


def _make(**overrides: object) -> Opportunity:
    base: dict[str, object] = {
        "company": "Foo",
        "role": "Engineer",
        "status": "applied",
        "slug": "2026-05-foo-engineer",
    }
    base.update(overrides)
    return opportunity_from_dict(base)


def test_required_fields_only() -> None:
    opp = _make()
    assert opp.company == "Foo"
    assert opp.role == "Engineer"
    assert opp.status == "applied"
    assert opp.priority == Priority.MEDIUM  # default


def test_unknown_status_raises() -> None:
    with pytest.raises(ValueError, match="Unknown status"):
        opportunity_from_dict({"company": "F", "role": "E", "status": "bogus"})


def test_missing_required_field_raises() -> None:
    with pytest.raises(KeyError):
        opportunity_from_dict({"role": "E", "status": "applied"})


def test_is_active() -> None:
    for status in Status:
        opp = _make(status=status.value)
        assert opp.is_active is status.is_active


def test_days_since_activity() -> None:
    opp = _make(last_activity=date(2026, 5, 1))
    assert opp.days_since_activity(date(2026, 5, 11)) == 10


def test_is_stale_threshold() -> None:
    today = date(2026, 5, 30)
    assert not _make(last_activity=date(2026, 5, 17)).is_stale(today)  # 13 days
    assert _make(last_activity=date(2026, 5, 16)).is_stale(today)  # 14 days
    assert STALE_DAYS == 14


def test_looks_ghosted_threshold() -> None:
    today = date(2026, 5, 30)
    assert not _make(last_activity=date(2026, 5, 10)).looks_ghosted(today)  # 20 days
    assert _make(last_activity=date(2026, 5, 9)).looks_ghosted(today)  # 21 days
    assert GHOSTED_DAYS == 21


def test_closed_status_never_stale() -> None:
    today = date(2026, 5, 30)
    opp = _make(status="rejected", last_activity=date(2026, 1, 1))
    assert not opp.is_stale(today)
    assert not opp.looks_ghosted(today)


def test_native_date_passthrough() -> None:
    opp = opportunity_from_dict(
        {
            "company": "F",
            "role": "E",
            "status": "applied",
            "applied_on": date(2026, 5, 1),
        }
    )
    assert opp.applied_on == date(2026, 5, 1)
