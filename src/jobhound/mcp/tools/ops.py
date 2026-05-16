"""MCP ops tools — route to application/ops_service."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from jobhound.application import ops_service
from jobhound.application.serialization import snapshot_to_dict
from jobhound.application.snapshots import ComputedFlags, OpportunitySnapshot
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.converters import mutation_response
from jobhound.mcp.errors import exception_to_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def add_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    msg: str,
    today: str | None = None,
) -> str:
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    now = datetime(*(date.fromisoformat(today).timetuple()[:3]), tzinfo=UTC) if today else now_utc()
    store = GitLocalFileStore(repo.paths)
    try:
        before, after, opp_dir = ops_service.add_note(repo, store, slug, msg=msg, now=now)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="add_note"))
    return json.dumps(mutation_response(before, after, opp_dir, now=now))


def archive_opportunity(repo: OpportunityRepository, *, slug: str) -> str:
    try:
        before, after, new_dir = ops_service.archive_opportunity(repo, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="archive_opportunity"))
    return json.dumps(
        mutation_response(
            before,
            after,
            new_dir,
            now=now_utc(),
            archived=True,
        )
    )


def delete_opportunity(
    repo: OpportunityRepository,
    *,
    slug: str,
    confirm: bool = False,
) -> str:
    try:
        result = ops_service.delete_opportunity(repo, slug, confirm=confirm)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="delete_opportunity"))
    now = now_utc()
    flags = ComputedFlags(
        is_active=result.opportunity.is_active,
        is_stale=result.opportunity.is_stale(now),
        looks_ghosted=result.opportunity.looks_ghosted(now),
        days_since_activity=result.opportunity.days_since_activity(now),
    )
    snap = OpportunitySnapshot(
        opportunity=result.opportunity,
        archived=False,
        path=result.opp_dir,
        computed=flags,
    )
    payload: dict[str, Any] = {
        "opportunity": snapshot_to_dict(snap),
        "files": result.files,
    }
    if result.deleted:
        payload["deleted"] = True
        payload["changed"] = None
    else:
        payload["preview"] = True
    return json.dumps(payload)


def register(app: FastMCP, repo: OpportunityRepository) -> None:
    @app.tool(
        name="add_note",
        description="Append a timestamped note to an opportunity's notes.md.",
    )
    def _n(slug: str, msg: str, today: str | None = None) -> str:
        return add_note(repo, slug=slug, msg=msg, today=today)

    @app.tool(
        name="archive_opportunity",
        description="Archive an opportunity.",
    )
    def _a(slug: str) -> str:
        return archive_opportunity(repo, slug=slug)

    @app.tool(
        name="delete_opportunity",
        description=(
            "Delete an opportunity permanently. "
            "Requires confirm=True; otherwise returns a preview."
        ),
    )
    def _d(slug: str, confirm: bool = False) -> str:
        return delete_opportunity(repo, slug=slug, confirm=confirm)
