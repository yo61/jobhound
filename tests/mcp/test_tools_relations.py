"""Tests for mcp/tools/relations.py."""

from __future__ import annotations

import json

from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.relations import (
    add_contact,
    add_tag,
    remove_link,
    remove_tag,
    set_link,
)


def test_add_tag(repo: OpportunityRepository) -> None:
    payload = json.loads(add_tag(repo, slug="acme", tag="remote"))
    assert "remote" in payload["opportunity"]["tags"]


def test_remove_tag(repo: OpportunityRepository) -> None:
    add_tag(repo, slug="acme", tag="remote")
    payload = json.loads(remove_tag(repo, slug="acme", tag="remote"))
    assert "remote" not in payload["opportunity"]["tags"]


def test_add_contact(repo: OpportunityRepository) -> None:
    payload = json.loads(
        add_contact(
            repo,
            slug="acme",
            name="Jane Doe",
            role="Recruiter",
            channel="email",
        )
    )
    contacts = payload["opportunity"]["contacts"]
    assert contacts[0]["name"] == "Jane Doe"


def test_set_link(repo: OpportunityRepository) -> None:
    payload = json.loads(
        set_link(
            repo,
            slug="acme",
            name="posting",
            url="https://x",
        )
    )
    assert payload["opportunity"]["links"]["posting"] == "https://x"


def test_remove_link(repo: OpportunityRepository) -> None:
    set_link(repo, slug="acme", name="posting", url="https://x")
    set_link(repo, slug="acme", name="company", url="https://acme.com")
    payload = json.loads(remove_link(repo, slug="acme", name="posting"))
    assert "posting" not in payload["opportunity"]["links"]
    assert payload["opportunity"]["links"]["company"] == "https://acme.com"


def test_remove_link_not_found_returns_error(repo: OpportunityRepository) -> None:
    payload = json.loads(remove_link(repo, slug="acme", name="nonexistent"))
    assert payload.get("error") is not None
