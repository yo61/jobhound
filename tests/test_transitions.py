"""Tests for the transitions module."""

import pytest

from jobhound.status import Status
from jobhound.transitions import (
    InvalidTransitionError,
    log_options,
    require_transition,
)


def test_log_forward_targets() -> None:
    # Forward transition rules now live on Status.legal_targets.
    assert Status.SCREEN in Status.APPLIED.legal_targets(verb="log")
    assert Status.INTERVIEW in Status.SCREEN.legal_targets(verb="log")
    assert Status.OFFER in Status.INTERVIEW.legal_targets(verb="log")


def test_log_options_from_applied() -> None:
    opts = log_options("applied")
    assert opts == ["screen", "rejected", "stay"]


def test_log_options_from_prospect_has_no_forward() -> None:
    opts = log_options("prospect")
    assert "applied" not in opts  # prospect→applied goes through jh apply, not jh log
    assert opts == ["rejected", "stay"]


def test_log_options_from_offer_has_no_forward() -> None:
    opts = log_options("offer")
    assert "accepted" not in opts and "declined" not in opts
    assert opts == ["rejected", "stay"]


def test_require_transition_accepts_legal() -> None:
    require_transition("applied", "screen", verb="log")


def test_require_transition_rejects_illegal() -> None:
    with pytest.raises(InvalidTransitionError):
        require_transition("applied", "accepted", verb="log")


def test_require_transition_terminal_verbs() -> None:
    # `withdraw`, `ghost` allowed from any active state.
    for active in ("prospect", "applied", "screen", "interview", "offer"):
        require_transition(active, "withdrawn", verb="withdraw")
        require_transition(active, "ghosted", verb="ghost")


def test_require_transition_accept_decline_only_from_offer() -> None:
    require_transition("offer", "accepted", verb="accept")
    require_transition("offer", "declined", verb="decline")
    with pytest.raises(InvalidTransitionError):
        require_transition("applied", "accepted", verb="accept")
