"""User-input helpers — questionary wrappers + date parsing."""

from __future__ import annotations

import re
from datetime import date, timedelta

import questionary

_RELATIVE_DAYS = re.compile(r"^([+-]?\d+)d$")


def parse_date_input(value: str, *, today: date) -> date:
    """Parse a user-supplied date string.

    Accepts ISO `YYYY-MM-DD`, the keywords `today` and `tomorrow`, and
    `+Nd`/`-Nd` (signed days from today).
    """
    s = value.strip().lower()
    if s == "today":
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    m = _RELATIVE_DAYS.match(s)
    if m:
        return today + timedelta(days=int(m.group(1)))
    try:
        return date.fromisoformat(value)
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


def ask_date(message: str, *, default: date) -> date:
    """Prompt for a date with the default shown in the prompt."""
    while True:
        raw = questionary.text(f"{message} [{default.isoformat()}]:", default="").ask()
        if raw is None:
            raise KeyboardInterrupt
        if raw == "":
            return default
        try:
            return parse_date_input(raw, today=date.today())
        except ValueError as exc:
            questionary.print(f"  ✗ {exc}", style="fg:red")


def ask_confirm(message: str, *, default: bool = True) -> bool:
    """Prompt for a yes/no answer."""
    result = questionary.confirm(message, default=default).ask()
    if result is None:
        raise KeyboardInterrupt
    return result
