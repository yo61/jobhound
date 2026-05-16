"""Validate `meta_io` rejects naive datetimes in lifecycle fields."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.infrastructure.meta_io import ValidationError, validate


def _base_data() -> dict:
    return {
        "slug": "2026-05-14-acme-eng",
        "company": "Acme",
        "role": "Engineer",
        "status": "applied",
        "priority": "medium",
    }


def test_naive_applied_on_rejected():
    data = _base_data()
    data["applied_on"] = datetime(2026, 5, 14, 12, 0)  # naive
    with pytest.raises(ValidationError, match="timezone-naive"):
        validate(data, Path("/tmp/fake.toml"))


@pytest.mark.xfail(
    strict=False,
    reason="A5 changes Opportunity.applied_on type to datetime; passes after that lands",
)
def test_aware_utc_applied_on_accepted():
    data = _base_data()
    data["applied_on"] = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    opp = validate(data, Path("/tmp/fake.toml"))
    assert opp.applied_on == datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
