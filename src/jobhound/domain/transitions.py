"""Thin transition-rule layer. The rules themselves live on `Status`."""

from __future__ import annotations

from jobhound.domain.status import STAY, Status


class InvalidTransitionError(Exception):
    """Raised when a verb tries an illegal status change."""

    def __init__(
        self,
        message: str,
        *,
        verb: str = "",
        current_status: Status | None = None,
        legal_targets: frozenset[Status] = frozenset(),
    ) -> None:
        super().__init__(message)
        self.verb = verb
        self.current_status = current_status
        self.legal_targets = legal_targets


def log_options(current: Status | str) -> list[str]:
    """Return the legal `--next-status` values for `jh log` from `current`.

    Order: forward stage (if any), then `rejected`, then `stay`.
    """
    cur = Status(current) if not isinstance(current, Status) else current
    options: list[str] = []
    targets = cur.legal_targets(verb="log")
    # Forward stage (not rejected) goes first
    forward = next((t.value for t in targets if t is not Status.REJECTED), None)
    if forward is not None:
        options.append(forward)
    if Status.REJECTED in targets:
        options.append(Status.REJECTED.value)
    options.append(STAY)
    return options


def _legal_sources(verb: str) -> list[str]:
    """Return sorted list of Status values that are valid source states for `verb`."""
    return sorted(s.value for s in Status if s.legal_targets(verb=verb))


def require_transition(current: Status | str, target: Status | str, *, verb: str) -> None:
    """Raise InvalidTransitionError unless `current → target` is legal for `verb`."""
    if verb == "log" and target == STAY:
        return
    cur = Status(current) if not isinstance(current, Status) else current
    try:
        tgt = Status(target) if not isinstance(target, Status) else target
    except ValueError as exc:
        legal_set = cur.legal_targets(verb=verb)
        legal = sorted(t.value for t in legal_set) + ([STAY] if verb == "log" else [])
        raise InvalidTransitionError(
            f"jh {verb} from {cur.value!r}: {target!r} is not a legal next status (legal: {legal})",
            verb=verb,
            current_status=cur,
            legal_targets=frozenset(legal_set),
        ) from exc
    legal_targets = cur.legal_targets(verb=verb)
    if tgt not in legal_targets:
        if verb == "log":
            legal = [*sorted(t.value for t in legal_targets), STAY]
            raise InvalidTransitionError(
                f"jh {verb} from {cur.value!r}: {tgt.value!r} is not a legal next status "
                f"(legal: {legal}). Use --force to override.",
                verb=verb,
                current_status=cur,
                legal_targets=frozenset(legal_targets),
            )
        # For non-log verbs, distinguish "wrong source" from "wrong target".
        sources = _legal_sources(verb)
        if not legal_targets:
            # current is not a legal source status for this verb.
            raise InvalidTransitionError(
                f"jh {verb} requires status in {sources} (was {cur.value!r})",
                verb=verb,
                current_status=cur,
                legal_targets=frozenset(),
            )
        legal = sorted(t.value for t in legal_targets)
        raise InvalidTransitionError(
            f"jh {verb} from {cur.value!r}: {tgt.value!r} is not a legal target (legal: {legal})",
            verb=verb,
            current_status=cur,
            legal_targets=frozenset(legal_targets),
        )
