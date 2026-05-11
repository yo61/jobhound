"""Tests for the date parser. Interactive helpers are not unit-tested."""

from datetime import date

import pytest

from jobhound.prompts import parse_date_input


def test_parse_iso() -> None:
    assert parse_date_input("2026-05-11", today=date(2026, 5, 1)) == date(2026, 5, 11)


def test_parse_today() -> None:
    assert parse_date_input("today", today=date(2026, 5, 11)) == date(2026, 5, 11)


def test_parse_tomorrow() -> None:
    assert parse_date_input("tomorrow", today=date(2026, 5, 11)) == date(2026, 5, 12)


def test_parse_relative_days() -> None:
    assert parse_date_input("+7d", today=date(2026, 5, 11)) == date(2026, 5, 18)


def test_parse_negative_relative_days() -> None:
    assert parse_date_input("-3d", today=date(2026, 5, 11)) == date(2026, 5, 8)


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_date_input("nonesuch", today=date(2026, 5, 11))


def test_parse_rejects_year_only() -> None:
    with pytest.raises(ValueError):
        parse_date_input("2026", today=date(2026, 5, 11))
