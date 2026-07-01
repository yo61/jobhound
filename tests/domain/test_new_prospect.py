"""Tests for the Opportunity.new_prospect creation factory.

The "what a freshly-created prospect looks like" invariant lives in the
domain so `jh new` and the URL-scraping service share one definition.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.slug_value import Slug
from jobhound.domain.status import Status

NOW = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def test_new_prospect_encodes_creation_invariants() -> None:
    opp = Opportunity.new_prospect(NOW, "Acme", "Staff Engineer", source="LinkedIn")

    assert opp.status == Status.PROSPECT
    assert opp.priority == Priority.MEDIUM
    assert opp.first_contact == NOW
    assert opp.last_activity == NOW
    assert opp.applied_on is None
    assert opp.next_action == "Initial review of role and company"
    assert opp.next_action_due == NOW + timedelta(days=7)
    assert opp.slug == Slug.build(NOW, "Acme", "Staff Engineer").value
    assert opp.source == "LinkedIn"


def test_new_prospect_accepts_optional_fields() -> None:
    opp = Opportunity.new_prospect(
        NOW,
        "Acme",
        "SRE",
        source="LinkedIn",
        location="Remote",
        comp_range="100k-120k",
        links={"posting": "https://example.com/1"},
    )

    assert opp.location == "Remote"
    assert opp.comp_range == "100k-120k"
    assert opp.links == {"posting": "https://example.com/1"}


def test_new_prospect_allows_next_action_override() -> None:
    due = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    opp = Opportunity.new_prospect(
        NOW,
        "Acme",
        "SRE",
        source="LinkedIn",
        next_action="Call recruiter",
        next_action_due=due,
    )

    assert opp.next_action == "Call recruiter"
    assert opp.next_action_due == due
