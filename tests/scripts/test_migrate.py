"""Migration script: bare-date meta.toml → tz-aware UTC datetime."""

from __future__ import annotations

import tomllib
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.migrate_dates_to_datetimes import migrate_data_root


def _write_meta(path: Path, applied_on: object) -> None:
    """Write a minimal meta.toml with a single applied_on field."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(applied_on, datetime | date):
        applied_on_str = applied_on.isoformat()
    else:
        applied_on_str = str(applied_on)
    path.write_text(
        f'company = "Acme"\nrole = "Engineer"\nstatus = "applied"\n'
        f'slug = "2026-05-14-acme-eng"\npriority = "medium"\n'
        f"applied_on = {applied_on_str}\n"
    )


def test_migration_converts_bare_date(tmp_path, monkeypatch):
    """Bare date is converted to noon-local→UTC."""
    london = ZoneInfo("Europe/London")
    monkeypatch.setattr("jobhound.migrations.utc_timestamps.get_localzone", lambda: london)
    meta = tmp_path / "opportunities" / "2026-05-14-acme-eng" / "meta.toml"
    _write_meta(meta, date(2026, 5, 14))

    changes = migrate_data_root(tmp_path)
    assert changes == 1

    with meta.open("rb") as fh:
        data = tomllib.load(fh)
    assert isinstance(data["applied_on"], datetime)
    assert data["applied_on"].tzinfo is not None
    # Europe/London is UTC+1 in BST (May), so noon local = 11:00 UTC same day.
    # Storing as noon-local (not midnight-local) keeps the calendar date intact
    # in the raw UTC string and is DST-safe.
    assert data["applied_on"] == datetime(2026, 5, 14, 11, 0, tzinfo=UTC)


def test_migration_idempotent(tmp_path, monkeypatch):
    """Already-migrated datetimes are not modified on re-run."""
    monkeypatch.setattr(
        "jobhound.migrations.utc_timestamps.get_localzone",
        lambda: ZoneInfo("Europe/London"),
    )
    meta = tmp_path / "opportunities" / "2026-05-14-acme-eng" / "meta.toml"
    _write_meta(meta, datetime(2026, 5, 14, 0, 0, tzinfo=UTC))

    changes = migrate_data_root(tmp_path)
    assert changes == 0
