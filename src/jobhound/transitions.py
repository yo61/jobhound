"""The legal status-transition graph for each verb."""

from __future__ import annotations

from jobhound.opportunities import ACTIVE_STATUSES


class InvalidTransitionError(Exception):
    """Raised when a verb tries an illegal status change."""


# Forward transitions available via `jh log`.
LOG_FORWARD: dict[str, str] = {
    "applied": "screen",
    "screen": "interview",
    "interview": "offer",
}


def log_options(current: str) -> list[str]:
    """Return the legal `--next-status` values for `jh log` from `current`.

    Order: forward stage (if any), then `rejected`, then `stay`.
    """
    options: list[str] = []
    if current in LOG_FORWARD:
        options.append(LOG_FORWARD[current])
    if current in ACTIVE_STATUSES:
        options.append("rejected")
    options.append("stay")
    return options


def require_transition(current: str, target: str, *, verb: str) -> None:
    """Raise InvalidTransitionError unless `current → target` is legal for `verb`."""
    if verb == "apply":
        if current != "prospect" or target != "applied":
            raise InvalidTransitionError(
                f"jh apply requires status `prospect` → `applied` (was {current!r})"
            )
        return
    if verb == "log":
        if target == "stay":
            return
        legal = log_options(current)
        if target not in legal:
            raise InvalidTransitionError(
                f"jh log from {current!r}: {target!r} is not a legal next status "
                f"(legal: {legal}). Use --force to override."
            )
        return
    if verb == "withdraw":
        if current not in ACTIVE_STATUSES or target != "withdrawn":
            raise InvalidTransitionError(f"jh withdraw requires an active status (was {current!r})")
        return
    if verb == "ghost":
        if current not in ACTIVE_STATUSES or target != "ghosted":
            raise InvalidTransitionError(f"jh ghost requires an active status (was {current!r})")
        return
    if verb in {"accept", "decline"}:
        expected_target = "accepted" if verb == "accept" else "declined"
        if current != "offer" or target != expected_target:
            raise InvalidTransitionError(
                f"jh {verb} requires status `offer` → `{expected_target}` (was {current!r})"
            )
        return
    raise InvalidTransitionError(f"unknown verb {verb!r}")
