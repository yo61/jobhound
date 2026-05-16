"""Validate `meta_io` rejects naive datetimes and bare dates in lifecycle fields."""

from __future__ import annotations

from datetime import UTC, date, datetime
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


def test_aware_utc_applied_on_accepted():
    data = _base_data()
    data["applied_on"] = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    opp = validate(data, Path("/tmp/fake.toml"))
    assert opp.applied_on == datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def test_bare_date_rejected_with_migration_prompt():
    """Bare date (pre-v0.7.0 schema) surfaces a clear migration instruction."""
    data = _base_data()
    data["applied_on"] = date(2026, 5, 14)
    with pytest.raises(ValidationError, match="jh migrate utc-timestamps"):
        validate(data, Path("/tmp/fake.toml"))


def test_bare_date_error_includes_field_name_and_value():
    """Error message names the offending field and its value for debuggability."""
    data = _base_data()
    data["last_activity"] = date(2026, 4, 29)
    with pytest.raises(ValidationError, match=r"last_activity is a bare date \(2026-04-29\)"):
        validate(data, Path("/tmp/fake.toml"))
