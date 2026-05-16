"""User-input helpers — questionary wrappers + date parsing."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

import questionary
from tzlocal import get_localzone

from jobhound.domain.timekeeping import now_utc, to_utc

_RELATIVE_DAYS = re.compile(r"^([+-]?\d+)d$")


def _midnight_local_to_utc(d: date) -> datetime:
    """Return the UTC instant for midnight-local on calendar date `d`."""
    return to_utc(datetime.combine(d, time.min, tzinfo=get_localzone()))


def parse_datetime_input(value: str, *, now: datetime) -> datetime:
    """Parse user-typed datetime/date input.

    Accepts ISO `YYYY-MM-DD`, the keywords `today` and `tomorrow`, and
    `+Nd`/`-Nd` (signed days from today). Returns a tz-aware UTC datetime.
    Relative inputs are evaluated against `now`'s local-zone calendar date.
    Bare dates are treated as midnight in the user's local zone, then converted
    to UTC.
    """
    s = value.strip().lower()
    local_today = now.astimezone(get_localzone()).date()

    if s == "today":
        return _midnight_local_to_utc(local_today)
    if s == "tomorrow":
        return _midnight_local_to_utc(local_today + timedelta(days=1))
    m = _RELATIVE_DAYS.match(s)
    if m:
        return _midnight_local_to_utc(local_today + timedelta(days=int(m.group(1))))
    try:
        return _midnight_local_to_utc(date.fromisoformat(value))
    except ValueError as exc:
        raise ValueError(
            f"could not parse {value!r}; expected ISO date, 'today', 'tomorrow', or '+Nd'"
        ) from exc


def ask_text(message: str, *, default: str = "") -> str:
    """Prompt for free-text input."""
    result = questionary.text(message, default=default).ask()
    if result is None:  # user hit Ctrl-C
        raise KeyboardInterrupt
    return result


def ask_select(message: str, choices: list[str], *, default: str | None = None) -> str:
    """Prompt the user to pick one of `choices`."""
    result = questionary.select(message, choices=choices, default=default).ask()
    if result is None:
        raise KeyboardInterrupt
    return result


def ask_date(message: str, *, default: datetime) -> datetime:
    """Prompt for a date with the default shown in the prompt."""
    from jobhound.domain.timekeeping import display_local

    while True:
        raw = questionary.text(
            f"{message} [{display_local(default, precision='minutes')}]:", default=""
        ).ask()
        if raw is None:
            raise KeyboardInterrupt
        if raw == "":
            return default
        try:
            return parse_datetime_input(raw, now=now_utc())
        except ValueError as exc:
            questionary.print(f"  ✗ {exc}", style="fg:red")


def ask_confirm(message: str, *, default: bool = True) -> bool:
    """Prompt for a yes/no answer."""
    result = questionary.confirm(message, default=default).ask()
    if result is None:
        raise KeyboardInterrupt
    return result
