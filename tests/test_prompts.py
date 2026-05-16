"""Tests for the date parser. Interactive helpers are not unit-tested."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from jobhound.prompts import parse_datetime_input

# Fixed "now" for tests: noon UTC on 2026-05-11.
# In Europe/London (BST = UTC+1) the local date is also 2026-05-11.
_NOW = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
_LONDON = ZoneInfo("Europe/London")


@pytest.fixture(autouse=True)
def patch_localzone(monkeypatch):
    """Pin the local timezone to Europe/London (BST, UTC+1) for all tests."""
    monkeypatch.setattr("jobhound.prompts.get_localzone", lambda: _LONDON)


def test_parse_iso() -> None:
    # 2026-05-11 midnight BST = 2026-05-10 23:00 UTC
    assert parse_datetime_input("2026-05-11", now=_NOW) == datetime(2026, 5, 10, 23, 0, tzinfo=UTC)


def test_parse_today() -> None:
    # local today = 2026-05-11, midnight BST = 2026-05-10 23:00 UTC
    assert parse_datetime_input("today", now=_NOW) == datetime(2026, 5, 10, 23, 0, tzinfo=UTC)


def test_parse_tomorrow() -> None:
    # local tomorrow = 2026-05-12, midnight BST = 2026-05-11 23:00 UTC
    assert parse_datetime_input("tomorrow", now=_NOW) == datetime(2026, 5, 11, 23, 0, tzinfo=UTC)


def test_parse_relative_days() -> None:
    # local today + 7 = 2026-05-18, midnight BST = 2026-05-17 23:00 UTC
    assert parse_datetime_input("+7d", now=_NOW) == datetime(2026, 5, 17, 23, 0, tzinfo=UTC)


def test_parse_negative_relative_days() -> None:
    # local today - 3 = 2026-05-08, midnight BST = 2026-05-07 23:00 UTC
    assert parse_datetime_input("-3d", now=_NOW) == datetime(2026, 5, 7, 23, 0, tzinfo=UTC)


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_datetime_input("nonesuch", now=_NOW)


def test_parse_rejects_year_only() -> None:
    with pytest.raises(ValueError):
        parse_datetime_input("2026", now=_NOW)
