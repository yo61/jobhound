"""The Status value object for an Opportunity.

`Status` is a `StrEnum` so existing string-equality comparisons keep
working while we migrate call sites (`Status.APPLIED == "applied"` is True).
`STAY` is a separate sentinel because `jh log --next-status stay` is a
meta-target — keep current status — not a real Status.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Final


class Status(StrEnum):
    PROSPECT = "prospect"
    APPLIED = "applied"
    SCREEN = "screen"
    INTERVIEW = "interview"
    OFFER = "offer"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    GHOSTED = "ghosted"

    @property
    def is_active(self) -> bool:
        return self in _ACTIVE

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL

    def legal_targets(self, *, verb: str) -> frozenset[Status]:
        """All Status values that `verb` may move `self` to. Empty = illegal."""
        rule = _VERB_RULES.get(verb)
        if rule is None:
            raise ValueError(f"unknown verb {verb!r}")
        return rule(self)


_ACTIVE: Final[frozenset[Status]] = frozenset(
    {
        Status.PROSPECT,
        Status.APPLIED,
        Status.SCREEN,
        Status.INTERVIEW,
        Status.OFFER,
    }
)
_TERMINAL: Final[frozenset[Status]] = frozenset(
    {
        Status.ACCEPTED,
        Status.DECLINED,
        Status.REJECTED,
        Status.WITHDRAWN,
        Status.GHOSTED,
    }
)
_LOG_FORWARD: Final[dict[Status, Status]] = {
    Status.APPLIED: Status.SCREEN,
    Status.SCREEN: Status.INTERVIEW,
    Status.INTERVIEW: Status.OFFER,
}


def _log_targets(status: Status) -> frozenset[Status]:
    if not status.is_active:
        return frozenset()
    targets: set[Status] = {Status.REJECTED}
    forward = _LOG_FORWARD.get(status)
    if forward is not None:
        targets.add(forward)
    return frozenset(targets)


_VERB_RULES: Final[dict[str, Callable[[Status], frozenset[Status]]]] = {
    "apply": lambda s: frozenset({Status.APPLIED}) if s is Status.PROSPECT else frozenset(),
    "log": _log_targets,
    "withdraw": lambda s: frozenset({Status.WITHDRAWN}) if s.is_active else frozenset(),
    "ghost": lambda s: frozenset({Status.GHOSTED}) if s.is_active else frozenset(),
    "accept": lambda s: frozenset({Status.ACCEPTED}) if s is Status.OFFER else frozenset(),
    "decline": lambda s: frozenset({Status.DECLINED}) if s is Status.OFFER else frozenset(),
}

STAY: Final[str] = "stay"
"""Meta-target for `jh log --next-status stay` — keep the current status."""
