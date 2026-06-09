"""MCP relation tools — route to application/relation_service."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from jobhound.application import relation_service
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.converters import mutation_response
from jobhound.mcp.errors import exception_to_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _wrap(tool_name: str, fn: Callable[[], Any]) -> str:
    try:
        before, after, opp_dir = fn()
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool=tool_name))
    return json.dumps(mutation_response(before, after, opp_dir, now=now_utc()))


def add_tag(repo: OpportunityRepository, *, slug: str, tag: str) -> str:
    return _wrap("add_tag", lambda: relation_service.add_tag(repo, slug, tag))


def remove_tag(repo: OpportunityRepository, *, slug: str, tag: str) -> str:
    return _wrap("remove_tag", lambda: relation_service.remove_tag(repo, slug, tag))


def add_contact(
    repo: OpportunityRepository,
    *,
    slug: str,
    name: str,
    role: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
) -> str:
    return _wrap(
        "add_contact",
        lambda: relation_service.add_contact(
            repo,
            slug,
            name=name,
            role=role,
            channel=channel,
            company=company,
            note=note,
        ),
    )


def remove_contact(
    repo: OpportunityRepository,
    *,
    slug: str,
    name: str,
    role: str | None = None,
    channel: str | None = None,
) -> str:
    return _wrap(
        "remove_contact",
        lambda: relation_service.remove_contact(
            repo,
            slug,
            name=name,
            role=role,
            channel=channel,
        ),
    )


def set_link(
    repo: OpportunityRepository,
    *,
    slug: str,
    name: str,
    url: str,
) -> str:
    return _wrap(
        "set_link",
        lambda: relation_service.set_link(repo, slug, name=name, url=url),
    )


def remove_link(repo: OpportunityRepository, *, slug: str, name: str) -> str:
    return _wrap("remove_link", lambda: relation_service.remove_link(repo, slug, name=name))


# ── Read tools (no mutation, custom payload shape) ───────────────────────


def list_contacts(repo: OpportunityRepository, *, slug: str) -> str:
    """List contacts on an opportunity. Returns {slug, contacts: [...]}"""
    try:
        _, contacts = relation_service.list_contacts(repo, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_contacts"))
    return json.dumps({"slug": slug, "contacts": [c.to_dict() for c in contacts]})


def show_contact(
    repo: OpportunityRepository,
    *,
    slug: str,
    name: str,
    match_role: str | None = None,
    match_channel: str | None = None,
) -> str:
    """Show one contact. Returns {slug, contact: {...}} or an error envelope."""
    try:
        _, contact, _ = relation_service.find_contact(
            repo,
            slug,
            name=name,
            match_role=match_role,
            match_channel=match_channel,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="show_contact"))
    return json.dumps({"slug": slug, "contact": contact.to_dict()})


def edit_contact(
    repo: OpportunityRepository,
    *,
    slug: str,
    name: str,
    match_role: str | None = None,
    match_channel: str | None = None,
    new_name: str | None = None,
    new_role: str | None = None,
    new_channel: str | None = None,
    new_company: str | None = None,
    new_note: str | None = None,
) -> str:
    """Update fields on a contact. Returns mutation_response + `contact` block."""
    try:
        before, after, updated, opp_dir = relation_service.edit_contact(
            repo,
            slug,
            name=name,
            match_role=match_role,
            match_channel=match_channel,
            new_name=new_name,
            new_role=new_role,
            new_channel=new_channel,
            new_company=new_company,
            new_note=new_note,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="edit_contact"))
    payload = mutation_response(before, after, opp_dir, now=now_utc())
    payload["contact"] = updated.to_dict()
    return json.dumps(payload)


def list_tags(repo: OpportunityRepository, *, slug: str) -> str:
    """List tags. Returns {slug, tags: [...]}"""
    try:
        _, tags = relation_service.list_tags(repo, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_tags"))
    return json.dumps({"slug": slug, "tags": list(tags)})


def list_links(repo: OpportunityRepository, *, slug: str) -> str:
    """List named links. Returns {slug, links: [{name, url}, ...]}"""
    try:
        _, links = relation_service.list_links(repo, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_links"))
    return json.dumps({"slug": slug, "links": [{"name": n, "url": u} for n, u in links.items()]})


def show_link(repo: OpportunityRepository, *, slug: str, name: str) -> str:
    """Show one link. Returns {slug, name, url} or an error envelope."""
    try:
        _, url = relation_service.find_link(repo, slug, name=name)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="show_link"))
    return json.dumps({"slug": slug, "name": name, "url": url})


def register(app: FastMCP, repo: OpportunityRepository) -> None:
    @app.tool(name="add_tag", description="Add a tag to an opportunity.")
    def _at(slug: str, tag: str) -> str:
        return add_tag(repo, slug=slug, tag=tag)

    @app.tool(name="remove_tag", description="Remove a tag from an opportunity.")
    def _rt(slug: str, tag: str) -> str:
        return remove_tag(repo, slug=slug, tag=tag)

    @app.tool(name="add_contact", description="Add a contact to an opportunity.")
    def _ac(
        slug: str,
        name: str,
        role: str | None = None,
        channel: str | None = None,
        company: str | None = None,
        note: str | None = None,
    ) -> str:
        return add_contact(
            repo,
            slug=slug,
            name=name,
            role=role,
            channel=channel,
            company=company,
            note=note,
        )

    @app.tool(name="remove_contact", description="Remove a contact from an opportunity.")
    def _rc(
        slug: str,
        name: str,
        role: str | None = None,
        channel: str | None = None,
    ) -> str:
        return remove_contact(repo, slug=slug, name=name, role=role, channel=channel)

    @app.tool(name="set_link", description="Set or replace a named link.")
    def _sl(slug: str, name: str, url: str) -> str:
        return set_link(repo, slug=slug, name=name, url=url)

    @app.tool(name="remove_link", description="Remove a named link from an opportunity.")
    def _rl(slug: str, name: str) -> str:
        return remove_link(repo, slug=slug, name=name)

    # ── Read tools ───────────────────────────────────────────────────────

    @app.tool(name="list_contacts", description="List contacts on an opportunity.")
    def _lc(slug: str) -> str:
        return list_contacts(repo, slug=slug)

    @app.tool(
        name="show_contact",
        description=(
            "Show one contact's full details. Address by name; "
            "disambiguate ambiguous matches with match_role / match_channel."
        ),
    )
    def _sc(
        slug: str,
        name: str,
        match_role: str | None = None,
        match_channel: str | None = None,
    ) -> str:
        return show_contact(
            repo,
            slug=slug,
            name=name,
            match_role=match_role,
            match_channel=match_channel,
        )

    @app.tool(
        name="edit_contact",
        description=(
            "Update fields on a contact. Renames via new_name. After a rename "
            "the contact must be addressed by its new name in subsequent calls."
        ),
    )
    def _ec(
        slug: str,
        name: str,
        match_role: str | None = None,
        match_channel: str | None = None,
        new_name: str | None = None,
        new_role: str | None = None,
        new_channel: str | None = None,
        new_company: str | None = None,
        new_note: str | None = None,
    ) -> str:
        return edit_contact(
            repo,
            slug=slug,
            name=name,
            match_role=match_role,
            match_channel=match_channel,
            new_name=new_name,
            new_role=new_role,
            new_channel=new_channel,
            new_company=new_company,
            new_note=new_note,
        )

    @app.tool(name="list_tags", description="List tags on an opportunity.")
    def _lt(slug: str) -> str:
        return list_tags(repo, slug=slug)

    @app.tool(name="list_links", description="List named links on an opportunity.")
    def _ll(slug: str) -> str:
        return list_links(repo, slug=slug)

    @app.tool(name="show_link", description="Show one named link's URL.")
    def _shl(slug: str, name: str) -> str:
        return show_link(repo, slug=slug, name=name)
