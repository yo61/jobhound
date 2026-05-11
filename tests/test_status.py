"""Tests for the Status value object."""

from __future__ import annotations

import pytest

from jobhound.status import STAY, Status


def test_string_equality_holds() -> None:
    assert Status.APPLIED == "applied"
    assert str(Status.APPLIED.value) == "applied"


def test_construct_from_string() -> None:
    assert Status("applied") is Status.APPLIED


def test_construct_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        Status("zombie")


def test_is_active() -> None:
    assert Status.PROSPECT.is_active
    assert Status.OFFER.is_active
    assert not Status.WITHDRAWN.is_active
    assert not Status.ACCEPTED.is_active


def test_is_terminal() -> None:
    assert Status.WITHDRAWN.is_terminal
    assert Status.ACCEPTED.is_terminal
    assert not Status.APPLIED.is_terminal


def test_legal_targets_apply() -> None:
    assert Status.PROSPECT.legal_targets(verb="apply") == frozenset({Status.APPLIED})
    assert Status.APPLIED.legal_targets(verb="apply") == frozenset()


def test_legal_targets_log() -> None:
    # `stay` is excluded — it's a meta-target, not a Status
    assert Status.PROSPECT.legal_targets(verb="log") == frozenset({Status.REJECTED})
    assert Status.APPLIED.legal_targets(verb="log") == frozenset({Status.SCREEN, Status.REJECTED})
    assert Status.SCREEN.legal_targets(verb="log") == frozenset({Status.INTERVIEW, Status.REJECTED})
    assert Status.INTERVIEW.legal_targets(verb="log") == frozenset({Status.OFFER, Status.REJECTED})
    assert Status.OFFER.legal_targets(verb="log") == frozenset({Status.REJECTED})
    assert Status.WITHDRAWN.legal_targets(verb="log") == frozenset()


def test_legal_targets_withdraw_ghost() -> None:
    for s in (Status.PROSPECT, Status.APPLIED, Status.SCREEN, Status.INTERVIEW, Status.OFFER):
        assert s.legal_targets(verb="withdraw") == frozenset({Status.WITHDRAWN})
        assert s.legal_targets(verb="ghost") == frozenset({Status.GHOSTED})
    assert Status.ACCEPTED.legal_targets(verb="withdraw") == frozenset()


def test_legal_targets_accept_decline() -> None:
    assert Status.OFFER.legal_targets(verb="accept") == frozenset({Status.ACCEPTED})
    assert Status.OFFER.legal_targets(verb="decline") == frozenset({Status.DECLINED})
    assert Status.APPLIED.legal_targets(verb="accept") == frozenset()


def test_stay_sentinel() -> None:
    assert STAY == "stay"


def test_legal_targets_unknown_verb_raises() -> None:
    with pytest.raises(ValueError, match="unknown verb"):
        Status.APPLIED.legal_targets(verb="zombify")
