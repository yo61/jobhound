"""Tests for mcp/tools/fields.py — adapter wiring."""

from __future__ import annotations

import json
from datetime import date

from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.fields import (
    set_applied_on,
    set_comp_range,
    set_company,
    set_first_contact,
    set_last_activity,
    set_location,
    set_next_action,
    set_priority,
    set_role,
    set_source,
    set_status,
    touch,
)


def test_set_priority(repo: OpportunityRepository) -> None:
    # acme seed has priority="high"; set to medium to verify the diff
    payload = json.loads(set_priority(repo, slug="acme", level="medium"))
    assert payload["changed"]["priority"] == ["high", "medium"]


def test_set_priority_invalid(repo: OpportunityRepository) -> None:
    payload = json.loads(set_priority(repo, slug="acme", level="urgent"))
    assert payload["error"]["code"] == "invalid_value"


def test_set_status_bypasses_transitions(repo: OpportunityRepository) -> None:
    """set_status writes the status directly even from incompatible states."""
    payload = json.loads(set_status(repo, slug="acme", status="offer"))
    assert payload["opportunity"]["status"] == "offer"


def test_set_status_invalid(repo: OpportunityRepository) -> None:
    payload = json.loads(set_status(repo, slug="acme", status="bogus"))
    assert payload["error"]["code"] == "invalid_value"


def test_set_company(repo: OpportunityRepository) -> None:
    payload = json.loads(set_company(repo, slug="acme", value="AcmeCorp"))
    assert payload["opportunity"]["company"] == "AcmeCorp"


def test_set_role(repo: OpportunityRepository) -> None:
    payload = json.loads(set_role(repo, slug="acme", value="Staff Engineer"))
    assert payload["opportunity"]["role"] == "Staff Engineer"


def test_set_source(repo: OpportunityRepository) -> None:
    payload = json.loads(set_source(repo, slug="acme", value="Referral"))
    assert payload["opportunity"]["source"] == "Referral"


def test_set_source_none(repo: OpportunityRepository) -> None:
    payload = json.loads(set_source(repo, slug="acme", value=None))
    assert "source" not in payload["opportunity"]


def test_set_location(repo: OpportunityRepository) -> None:
    payload = json.loads(set_location(repo, slug="acme", value="Remote, UK"))
    assert payload["opportunity"]["location"] == "Remote, UK"


def test_set_comp_range(repo: OpportunityRepository) -> None:
    payload = json.loads(set_comp_range(repo, slug="acme", value="£110k-£130k"))
    assert payload["opportunity"]["comp_range"] == "£110k-£130k"


def test_set_first_contact(repo: OpportunityRepository) -> None:
    payload = json.loads(set_first_contact(repo, slug="acme", value="2026-05-01"))
    assert payload["opportunity"]["first_contact"] == "2026-05-01"


def test_set_applied_on(repo: OpportunityRepository) -> None:
    payload = json.loads(set_applied_on(repo, slug="acme", value="2026-05-02"))
    assert payload["opportunity"]["applied_on"] == "2026-05-02"


def test_set_last_activity(repo: OpportunityRepository) -> None:
    payload = json.loads(set_last_activity(repo, slug="acme", value="2026-05-12"))
    assert payload["opportunity"]["last_activity"] == "2026-05-12"


def test_set_next_action(repo: OpportunityRepository) -> None:
    payload = json.loads(
        set_next_action(
            repo,
            slug="acme",
            text="Send portfolio",
            due="2026-05-20",
        )
    )
    assert payload["opportunity"]["next_action"] == "Send portfolio"
    assert payload["opportunity"]["next_action_due"] == "2026-05-20"


def test_touch(repo: OpportunityRepository) -> None:
    payload = json.loads(touch(repo, slug="acme"))
    assert payload["opportunity"]["last_activity"] == date.today().isoformat()


def test_idempotent_set_returns_empty_changed(
    repo: OpportunityRepository,
) -> None:
    # acme seed has priority="high"; setting to medium changes it, then repeat is a no-op
    set_priority(repo, slug="acme", level="medium")
    payload = json.loads(set_priority(repo, slug="acme", level="medium"))
    assert payload["changed"] == {}
