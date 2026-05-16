"""Tests for reading, writing, and validating meta.toml."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.domain.contact import Contact
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.meta_io import ValidationError, read_meta, validate, write_meta

NOON_UTC = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def _full_opp(slug: str = "2026-05-foo-engineer") -> Opportunity:
    return Opportunity(
        slug=slug,
        company="Foo",
        role="Engineer",
        status=Status.APPLIED,
        priority=Priority.MEDIUM,
        source="LinkedIn",
        location="UK",
        comp_range="£100k",
        first_contact=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        applied_on=datetime(2026, 5, 5, 12, 0, tzinfo=UTC),
        last_activity=datetime(2026, 5, 5, 12, 0, tzinfo=UTC),
        next_action="Wait for response",
        next_action_due=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        tags=("remote", "uk"),
        contacts=(Contact(name="Jane Doe", channel="email"),),
        links={"posting": "https://example.com/job"},
    )


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    opp = _full_opp()
    path = tmp_path / "meta.toml"
    write_meta(opp, path)
    loaded = read_meta(path)
    assert loaded.company == opp.company
    assert loaded.status is Status.APPLIED
    assert loaded.applied_on == opp.applied_on
    assert loaded.tags == opp.tags
    assert loaded.contacts == opp.contacts
    assert loaded.links == opp.links


def test_datetimes_round_trip_as_offset_datetime(tmp_path: Path) -> None:
    opp = _full_opp()
    path = tmp_path / "meta.toml"
    write_meta(opp, path)
    text = path.read_text()
    # TOML offset date-times are written with +00:00, not quoted.
    # tomli_w uses space separator (TOML spec allows both T and space).
    assert "applied_on = 2026-05-05 12:00:00+00:00" in text
    assert '"2026-05-05"' not in text


def test_validate_rejects_unknown_status(tmp_path: Path) -> None:
    path = tmp_path / "meta.toml"
    path.write_text('company = "F"\nrole = "E"\nstatus = "bogus"\n')
    with pytest.raises(ValidationError, match="Unknown status"):
        read_meta(path)


def test_validate_rejects_missing_required(tmp_path: Path) -> None:
    path = tmp_path / "meta.toml"
    path.write_text('role = "E"\nstatus = "applied"\n')
    with pytest.raises(ValidationError, match="missing required field"):
        read_meta(path)


def test_validate_rejects_unsafe_slug() -> None:
    with pytest.raises(ValidationError, match="path separator"):
        validate(
            {"company": "F", "role": "E", "status": "applied", "slug": "foo/bar"},
            Path("/tmp/foo/meta.toml"),
        )


def test_write_omits_none_fields(tmp_path: Path) -> None:
    opp = Opportunity(
        slug="s",
        company="F",
        role="E",
        status=Status.APPLIED,
        priority=Priority.MEDIUM,
        source=None,
        location=None,
        comp_range=None,
        first_contact=None,
        applied_on=None,
        last_activity=None,
        next_action=None,
        next_action_due=None,
    )
    path = tmp_path / "meta.toml"
    write_meta(opp, path)
    text = path.read_text()
    assert "source" not in text
    assert "applied_on" not in text
