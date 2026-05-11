"""Unit tests for behaviour methods on the Opportunity entity."""

from __future__ import annotations

from datetime import date

import pytest

from jobhound.opportunities import Opportunity
from jobhound.priority import Priority
from jobhound.status import Status
from jobhound.transitions import InvalidTransitionError


def _prospect() -> Opportunity:
    return Opportunity(
        slug="2026-05-acme-eng",
        company="Acme",
        role="Engineer",
        status=Status.PROSPECT,
        priority=Priority.MEDIUM,
        source=None,
        location=None,
        comp_range=None,
        first_contact=date(2026, 5, 1),
        applied_on=None,
        last_activity=date(2026, 5, 1),
        next_action="follow up",
        next_action_due=date(2026, 5, 8),
    )


def test_apply_sets_all_fields_atomically() -> None:
    opp = _prospect()
    after = opp.apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    assert after.status == "applied"
    assert after.applied_on == date(2026, 5, 3)
    assert after.last_activity == date(2026, 5, 3)
    assert after.next_action == "wait"
    assert after.next_action_due == date(2026, 5, 10)


def test_apply_rejects_non_prospect() -> None:
    opp = _prospect().apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    with pytest.raises(InvalidTransitionError):
        opp.apply(
            applied_on=date(2026, 5, 3),
            today=date(2026, 5, 3),
            next_action="x",
            next_action_due=date(2026, 5, 4),
        )


def test_log_interaction_stay() -> None:
    opp = _prospect().apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    after = opp.log_interaction(
        today=date(2026, 5, 5),
        next_status="stay",
        next_action=None,
        next_action_due=None,
        force=False,
    )
    assert after.status == "applied"
    assert after.last_activity == date(2026, 5, 5)
    assert after.next_action == "wait"  # carries over


def test_log_interaction_advances_stage() -> None:
    opp = _prospect().apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    after = opp.log_interaction(
        today=date(2026, 5, 6),
        next_status="screen",
        next_action="prep",
        next_action_due=date(2026, 5, 12),
        force=False,
    )
    assert after.status == "screen"
    assert after.next_action == "prep"


def test_log_interaction_rejects_illegal_jump_without_force() -> None:
    opp = _prospect().apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    with pytest.raises(InvalidTransitionError):
        opp.log_interaction(
            today=date(2026, 5, 6),
            next_status="offer",
            next_action=None,
            next_action_due=None,
            force=False,
        )


def test_log_interaction_force_allows_anything() -> None:
    opp = _prospect()
    after = opp.log_interaction(
        today=date(2026, 5, 6),
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    assert after.status == "offer"


def test_withdraw_from_active() -> None:
    opp = _prospect()
    after = opp.withdraw(today=date(2026, 5, 6))
    assert after.status == "withdrawn"
    assert after.last_activity == date(2026, 5, 6)


def test_withdraw_rejects_terminal() -> None:
    opp = _prospect().withdraw(today=date(2026, 5, 6))
    with pytest.raises(InvalidTransitionError):
        opp.withdraw(today=date(2026, 5, 7))


def test_ghost_from_active() -> None:
    opp = _prospect()
    after = opp.ghost(today=date(2026, 5, 6))
    assert after.status == "ghosted"


def test_accept_requires_offer() -> None:
    opp = _prospect()
    with pytest.raises(InvalidTransitionError):
        opp.accept(today=date(2026, 5, 6))


def test_accept_from_offer() -> None:
    opp = _prospect().log_interaction(
        today=date(2026, 5, 6),
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    after = opp.accept(today=date(2026, 5, 7))
    assert after.status == "accepted"


def test_decline_from_offer() -> None:
    opp = _prospect().log_interaction(
        today=date(2026, 5, 6),
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    after = opp.decline(today=date(2026, 5, 7))
    assert after.status == "declined"


def test_ghost_rejects_terminal() -> None:
    opp = _prospect().ghost(today=date(2026, 5, 6))
    with pytest.raises(InvalidTransitionError):
        opp.ghost(today=date(2026, 5, 7))


def test_decline_rejects_non_offer() -> None:
    opp = _prospect()
    with pytest.raises(InvalidTransitionError):
        opp.decline(today=date(2026, 5, 6))


def test_touch_bumps_last_activity_only() -> None:
    opp = _prospect()
    after = opp.touch(today=date(2026, 5, 9))
    assert after.last_activity == date(2026, 5, 9)
    assert after.status == opp.status


def test_with_tags_adds_and_removes() -> None:
    opp = _prospect()
    after = opp.with_tags(add={"remote", "uk"}, remove=set())
    assert after.tags == ("remote", "uk")
    after2 = after.with_tags(add=set(), remove={"uk"})
    assert after2.tags == ("remote",)


def test_with_tags_dedupes_and_sorts() -> None:
    opp = _prospect()
    # Apply tags in two passes to verify the result is deduped and sorted.
    after = opp.with_tags(add={"b", "a"}, remove=set())
    after2 = after.with_tags(add={"b"}, remove=set())
    assert after2.tags == ("a", "b")


def test_with_priority_rejects_unknown() -> None:
    opp = _prospect()
    with pytest.raises(ValueError):
        opp.with_priority("urgent")


def test_with_priority_sets_value() -> None:
    opp = _prospect()
    after = opp.with_priority("high")
    assert after.priority == Priority.HIGH


def test_with_contact_appends() -> None:
    opp = _prospect()
    after = opp.with_contact({"name": "Jane", "role": "Recruiter"})
    assert after.contacts == ({"name": "Jane", "role": "Recruiter"},)


def test_with_contact_requires_name() -> None:
    opp = _prospect()
    with pytest.raises(ValueError):
        opp.with_contact({"role": "Recruiter"})


def test_with_link_sets_or_overwrites() -> None:
    opp = _prospect()
    after = opp.with_link(name="jd", url="https://example.com/jd")
    assert after.links == {"jd": "https://example.com/jd"}
    after2 = after.with_link(name="jd", url="https://example.com/jd2")
    assert after2.links == {"jd": "https://example.com/jd2"}
