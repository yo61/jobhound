"""Unit tests for behaviour methods on the Opportunity entity."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.domain.transitions import InvalidTransitionError

NOON_UTC = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
MAY_5 = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
MAY_6 = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
MAY_7 = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
MAY_8 = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
MAY_9 = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
MAY_10 = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)
MAY_12 = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)


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
        first_contact=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        applied_on=None,
        last_activity=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        next_action="follow up",
        next_action_due=MAY_8,
    )


def test_apply_sets_all_fields_atomically() -> None:
    opp = _prospect()
    after = opp.apply(
        applied_on=NOON_UTC,
        now=NOON_UTC,
        next_action="wait",
        next_action_due=MAY_10,
    )
    assert after.status == "applied"
    assert after.applied_on == NOON_UTC
    assert after.last_activity == NOON_UTC
    assert after.next_action == "wait"
    assert after.next_action_due == MAY_10


def test_apply_rejects_non_prospect() -> None:
    opp = _prospect().apply(
        applied_on=NOON_UTC,
        now=NOON_UTC,
        next_action="wait",
        next_action_due=MAY_10,
    )
    with pytest.raises(InvalidTransitionError):
        opp.apply(
            applied_on=NOON_UTC,
            now=NOON_UTC,
            next_action="x",
            next_action_due=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
        )


def test_log_interaction_stay() -> None:
    opp = _prospect().apply(
        applied_on=NOON_UTC,
        now=NOON_UTC,
        next_action="wait",
        next_action_due=MAY_10,
    )
    after = opp.log_interaction(
        now=MAY_5,
        next_status="stay",
        next_action=None,
        next_action_due=None,
        force=False,
    )
    assert after.status == "applied"
    assert after.last_activity == MAY_5
    assert after.next_action == "wait"  # carries over


def test_log_interaction_advances_stage() -> None:
    opp = _prospect().apply(
        applied_on=NOON_UTC,
        now=NOON_UTC,
        next_action="wait",
        next_action_due=MAY_10,
    )
    after = opp.log_interaction(
        now=MAY_6,
        next_status="screen",
        next_action="prep",
        next_action_due=MAY_12,
        force=False,
    )
    assert after.status == "screen"
    assert after.next_action == "prep"


def test_log_interaction_rejects_illegal_jump_without_force() -> None:
    opp = _prospect().apply(
        applied_on=NOON_UTC,
        now=NOON_UTC,
        next_action="wait",
        next_action_due=MAY_10,
    )
    with pytest.raises(InvalidTransitionError):
        opp.log_interaction(
            now=MAY_6,
            next_status="offer",
            next_action=None,
            next_action_due=None,
            force=False,
        )


def test_log_interaction_force_allows_anything() -> None:
    opp = _prospect()
    after = opp.log_interaction(
        now=MAY_6,
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    assert after.status == "offer"


def test_withdraw_from_active() -> None:
    opp = _prospect()
    after = opp.withdraw(now=MAY_6)
    assert after.status == "withdrawn"
    assert after.last_activity == MAY_6


def test_withdraw_rejects_terminal() -> None:
    opp = _prospect().withdraw(now=MAY_6)
    with pytest.raises(InvalidTransitionError):
        opp.withdraw(now=MAY_7)


def test_ghost_from_active() -> None:
    opp = _prospect()
    after = opp.ghost(now=MAY_6)
    assert after.status == "ghosted"


def test_accept_requires_offer() -> None:
    opp = _prospect()
    with pytest.raises(InvalidTransitionError):
        opp.accept(now=MAY_6)


def test_accept_from_offer() -> None:
    opp = _prospect().log_interaction(
        now=MAY_6,
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    after = opp.accept(now=MAY_7)
    assert after.status == "accepted"


def test_decline_from_offer() -> None:
    opp = _prospect().log_interaction(
        now=MAY_6,
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    after = opp.decline(now=MAY_7)
    assert after.status == "declined"


def test_ghost_rejects_terminal() -> None:
    opp = _prospect().ghost(now=MAY_6)
    with pytest.raises(InvalidTransitionError):
        opp.ghost(now=MAY_7)


def test_decline_rejects_non_offer() -> None:
    opp = _prospect()
    with pytest.raises(InvalidTransitionError):
        opp.decline(now=MAY_6)


def test_touch_bumps_last_activity_only() -> None:
    opp = _prospect()
    after = opp.touch(now=MAY_9)
    assert after.last_activity == MAY_9
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
    from jobhound.domain.contact import Contact

    opp = _prospect()
    after = opp.with_contact(Contact(name="Jane", role="Recruiter"))
    assert after.contacts == (Contact(name="Jane", role="Recruiter"),)


def test_with_contact_requires_name() -> None:
    from jobhound.domain.contact import Contact

    with pytest.raises(ValueError):
        Contact(name="")


def test_with_link_sets_or_overwrites() -> None:
    opp = _prospect()
    after = opp.with_link(name="jd", url="https://example.com/jd")
    assert after.links == {"jd": "https://example.com/jd"}
    after2 = after.with_link(name="jd", url="https://example.com/jd2")
    assert after2.links == {"jd": "https://example.com/jd2"}
