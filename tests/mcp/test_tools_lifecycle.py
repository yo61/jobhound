"""Tests for mcp/tools/lifecycle.py — adapter wiring."""

from __future__ import annotations

import json

from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.lifecycle import (
    accept_opportunity,
    apply_to_opportunity,
    create_opportunity,
    decline_opportunity,
    ghost_opportunity,
    log_interaction,
    withdraw_from_opportunity,
)


def test_create_opportunity_returns_null_changed(repo: OpportunityRepository) -> None:
    payload = json.loads(
        create_opportunity(
            repo,
            company="Newco",
            role="Eng",
            source="LinkedIn",
            priority="high",
        )
    )
    assert payload["changed"] is None
    assert payload["opportunity"]["company"] == "Newco"
    assert payload["opportunity"]["priority"] == "high"


def test_apply_to_opportunity_returns_diff(repo: OpportunityRepository) -> None:
    # The seeded acme-em is already APPLIED. Make a fresh prospect.
    create_opportunity(
        repo,
        company="Z",
        role="Y",
        slug="2026-05-prospect",
        priority="medium",
    )
    payload = json.loads(
        apply_to_opportunity(
            repo,
            slug="2026-05-prospect",
            next_action="follow up",
            next_action_due="2026-06-01",
        )
    )
    assert payload["changed"]["status"] == ["prospect", "applied"]


def test_apply_to_opportunity_invalid_transition_returns_error(
    repo: OpportunityRepository,
) -> None:
    # acme is already APPLIED — applying again is illegal
    payload = json.loads(
        apply_to_opportunity(
            repo,
            slug="acme",
            next_action="x",
            next_action_due="2026-06-01",
        )
    )
    assert payload["error"]["code"] == "invalid_transition"


def test_log_interaction_advances(repo: OpportunityRepository) -> None:
    payload = json.loads(
        log_interaction(
            repo,
            slug="acme",
            next_status="screen",
        )
    )
    assert payload["changed"]["status"] == ["applied", "screen"]


def test_withdraw_from_opportunity_marks_withdrawn(repo: OpportunityRepository) -> None:
    payload = json.loads(withdraw_from_opportunity(repo, slug="acme"))
    assert payload["opportunity"]["status"] == "withdrawn"


def test_ghost_opportunity(repo: OpportunityRepository) -> None:
    payload = json.loads(ghost_opportunity(repo, slug="acme"))
    assert payload["opportunity"]["status"] == "ghosted"


def test_accept_opportunity_requires_offer_status(
    repo: OpportunityRepository,
) -> None:
    # acme is APPLIED, not OFFER
    payload = json.loads(accept_opportunity(repo, slug="acme"))
    assert payload["error"]["code"] == "invalid_transition"


def test_decline_opportunity_requires_offer_status(
    repo: OpportunityRepository,
) -> None:
    payload = json.loads(decline_opportunity(repo, slug="acme"))
    assert payload["error"]["code"] == "invalid_transition"
