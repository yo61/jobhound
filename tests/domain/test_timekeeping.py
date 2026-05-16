"""Unit tests for domain/timekeeping.py."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from jobhound.domain.timekeeping import (
    _format_z_seconds,
    calendar_days_between,
    display_local,
    now_utc,
    to_utc,
)


class TestToUtc:
    def test_naive_input_treated_as_local(self, monkeypatch):
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        naive = datetime(2026, 5, 14, 13, 0)
        result = to_utc(naive)
        assert result.tzinfo == UTC
        # 13:00 BST (UTC+1) → 12:00 UTC
        assert result.hour == 12

    def test_aware_utc_passthrough(self):
        aware = datetime(2026, 5, 14, 13, 0, tzinfo=UTC)
        assert to_utc(aware) == aware

    def test_aware_non_utc_converted(self):
        aware = datetime(2026, 5, 14, 13, 0, tzinfo=ZoneInfo("America/New_York"))
        result = to_utc(aware)
        assert result.tzinfo == UTC
        # 13:00 EDT (UTC-4) → 17:00 UTC
        assert result.hour == 17


class TestCalendarDaysBetween:
    def test_same_instant_is_zero(self):
        t = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
        assert calendar_days_between(t, t) == 0

    def test_negative_clamped_to_zero(self):
        earlier = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
        later = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
        assert calendar_days_between(later, earlier) == 0

    def test_midnight_boundary_crossing(self, monkeypatch):
        """10 minutes of wall-clock, but a calendar boundary crossed."""
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        # 23:55 BST = 22:55 UTC. 00:05 next-day BST = 23:05 UTC.
        then = datetime(2026, 5, 14, 22, 55, tzinfo=UTC)
        now = datetime(2026, 5, 14, 23, 5, tzinfo=UTC)
        assert calendar_days_between(then, now) == 1

    def test_same_local_day_returns_zero(self, monkeypatch):
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        then = datetime(2026, 5, 14, 9, 0, tzinfo=UTC)  # 10:00 BST
        now = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)  # 22:00 BST
        assert calendar_days_between(then, now) == 0

    def test_naive_input_rejected(self):
        naive = datetime(2026, 5, 14, 12, 0)
        aware = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="tz-aware"):
            calendar_days_between(naive, aware)
        with pytest.raises(ValueError, match="tz-aware"):
            calendar_days_between(aware, naive)


class TestDisplayLocal:
    def test_seconds_precision(self, monkeypatch):
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        value = datetime(2026, 5, 14, 12, 0, 30, 123456, tzinfo=UTC)
        # 12:00:30 UTC → 13:00:30 BST
        assert display_local(value, precision="seconds") == "2026-05-14 13:00:30 BST"

    def test_minutes_precision(self, monkeypatch):
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        value = datetime(2026, 5, 14, 12, 0, 30, 123456, tzinfo=UTC)
        assert display_local(value, precision="minutes") == "2026-05-14 13:00 BST"


class TestNowUtc:
    def test_returns_utc_aware(self):
        result = now_utc()
        assert result.tzinfo == UTC


class TestFormatZSeconds:
    def test_z_suffix_whole_seconds(self):
        value = datetime(2026, 5, 14, 12, 0, 30, 123456, tzinfo=UTC)
        assert _format_z_seconds(value) == "2026-05-14T12:00:30Z"

    def test_naive_rejected(self):
        naive = datetime(2026, 5, 14, 12, 0)
        with pytest.raises(ValueError, match="tz-aware"):
            _format_z_seconds(naive)
