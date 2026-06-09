"""Tests for mcp/tools/relations.py."""

from __future__ import annotations

import json

from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.relations import (
    add_contact,
    add_tag,
    edit_contact,
    list_contacts,
    list_links,
    list_tags,
    remove_link,
    remove_tag,
    set_link,
    show_contact,
    show_link,
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


# ── Read tools ───────────────────────────────────────────────────────────


def test_list_contacts_empty(repo: OpportunityRepository) -> None:
    payload = json.loads(list_contacts(repo, slug="acme"))
    assert payload == {"slug": "acme", "contacts": []}


def test_list_contacts_returns_contacts(repo: OpportunityRepository) -> None:
    add_contact(repo, slug="acme", name="Jane Doe", role="Recruiter")
    add_contact(repo, slug="acme", name="Bob Smith")
    payload = json.loads(list_contacts(repo, slug="acme"))
    names = [c["name"] for c in payload["contacts"]]
    assert names == ["Jane Doe", "Bob Smith"]
    assert payload["contacts"][0]["role"] == "Recruiter"


def test_show_contact_returns_one(repo: OpportunityRepository) -> None:
    add_contact(repo, slug="acme", name="Jane Doe", role="Recruiter")
    payload = json.loads(show_contact(repo, slug="acme", name="Jane Doe"))
    assert payload["contact"]["name"] == "Jane Doe"
    assert payload["contact"]["role"] == "Recruiter"


def test_show_contact_missing_returns_error(repo: OpportunityRepository) -> None:
    payload = json.loads(show_contact(repo, slug="acme", name="Nobody"))
    assert payload["error"]["code"] == "contact_not_found"


def test_show_contact_ambiguous_returns_error_with_matches(repo: OpportunityRepository) -> None:
    add_contact(repo, slug="acme", name="Jane Doe", role="Recruiter")
    add_contact(repo, slug="acme", name="Jane Doe", role="HM")
    payload = json.loads(show_contact(repo, slug="acme", name="Jane Doe"))
    assert payload["error"]["code"] == "ambiguous_contact"
    assert len(payload["error"]["details"]["matches"]) == 2


def test_show_contact_match_role_disambiguates(repo: OpportunityRepository) -> None:
    add_contact(repo, slug="acme", name="Jane Doe", role="Recruiter")
    add_contact(repo, slug="acme", name="Jane Doe", role="HM")
    payload = json.loads(show_contact(repo, slug="acme", name="Jane Doe", match_role="HM"))
    assert payload["contact"]["role"] == "HM"


def test_edit_contact_updates_field(repo: OpportunityRepository) -> None:
    add_contact(repo, slug="acme", name="Jane Doe", role="Recruiter")
    payload = json.loads(edit_contact(repo, slug="acme", name="Jane Doe", new_role="Sourcer"))
    assert payload["contact"]["role"] == "Sourcer"
    assert payload["contact"]["name"] == "Jane Doe"


def test_edit_contact_renames(repo: OpportunityRepository) -> None:
    add_contact(repo, slug="acme", name="Jane Smithh")
    payload = json.loads(edit_contact(repo, slug="acme", name="Jane Smithh", new_name="Jane Smith"))
    assert payload["contact"]["name"] == "Jane Smith"


def test_edit_contact_missing_returns_error(repo: OpportunityRepository) -> None:
    payload = json.loads(edit_contact(repo, slug="acme", name="Nobody", new_role="x"))
    assert payload["error"]["code"] == "contact_not_found"


def test_list_tags_returns_tags(repo: OpportunityRepository) -> None:
    # Conftest seeds acme with tag "remote"; add one more and verify.
    add_tag(repo, slug="acme", tag="priority")
    payload = json.loads(list_tags(repo, slug="acme"))
    assert "remote" in payload["tags"]
    assert "priority" in payload["tags"]


def test_list_tags_envelope_shape(repo: OpportunityRepository) -> None:
    payload = json.loads(list_tags(repo, slug="acme"))
    assert payload["slug"] == "acme"
    assert isinstance(payload["tags"], list)


def test_list_links_empty(repo: OpportunityRepository) -> None:
    payload = json.loads(list_links(repo, slug="acme"))
    assert payload == {"slug": "acme", "links": []}


def test_list_links_returns_links(repo: OpportunityRepository) -> None:
    set_link(repo, slug="acme", name="posting", url="https://e.com/1")
    set_link(repo, slug="acme", name="company", url="https://e.com/")
    payload = json.loads(list_links(repo, slug="acme"))
    names = {link["name"] for link in payload["links"]}
    assert names == {"posting", "company"}


def test_show_link_returns_url(repo: OpportunityRepository) -> None:
    set_link(repo, slug="acme", name="posting", url="https://e.com/1")
    payload = json.loads(show_link(repo, slug="acme", name="posting"))
    assert payload == {"slug": "acme", "name": "posting", "url": "https://e.com/1"}


def test_show_link_missing_returns_error(repo: OpportunityRepository) -> None:
    payload = json.loads(show_link(repo, slug="acme", name="nonexistent"))
    assert payload["error"]["code"] == "link_not_found"
