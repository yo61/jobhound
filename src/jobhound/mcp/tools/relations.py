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
