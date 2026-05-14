"""MCP read tools — route to OpportunityQuery from Phase 3a."""

from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.application.serialization import (
    file_entry_to_dict,
    list_envelope,
    show_envelope,
    stats_to_dict,
)
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.errors import exception_to_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _query(repo: OpportunityRepository) -> OpportunityQuery:
    return OpportunityQuery(repo.paths)


def _build_filters(
    statuses: list[str] | None,
    priorities: list[str] | None,
    slug_substring: str | None,
    active_only: bool,
    include_archived: bool,
) -> Filters | dict[str, Any]:
    try:
        s = frozenset(Status(x) for x in (statuses or []))
        p = frozenset(Priority(x) for x in (priorities or []))
    except ValueError as exc:
        return exception_to_response(
            exc,
            tool="list_opportunities",
            invalid_param=(
                "status_or_priority",
                str(exc),
                [v.value for v in Status],
            ),
        )
    return Filters(
        statuses=s,
        priorities=p,
        slug_substring=slug_substring,
        active_only=active_only,
        include_archived=include_archived,
    )


def list_opportunities(
    repo: OpportunityRepository,
    statuses: list[str] | None = None,
    priorities: list[str] | None = None,
    slug_substring: str | None = None,
    active_only: bool = False,
    include_archived: bool = False,
) -> str:
    """List opportunities, optionally filtered. Returns JSON envelope."""
    f = _build_filters(
        statuses,
        priorities,
        slug_substring,
        active_only,
        include_archived,
    )
    if isinstance(f, dict):  # error response
        return json.dumps(f)
    try:
        snaps = _query(repo).list(f, today=date.today())
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_opportunities"))
    envelope = list_envelope(
        snaps,
        timestamp=datetime.now(UTC),
        db_root=repo.paths.db_root,
    )
    return json.dumps(envelope)


def get_opportunity(repo: OpportunityRepository, slug: str) -> str:
    """Show one opportunity by slug (fuzzy match). Returns JSON envelope."""
    try:
        snap = _query(repo).find(slug, today=date.today())
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="get_opportunity"))
    envelope = show_envelope(
        snap,
        timestamp=datetime.now(UTC),
        db_root=repo.paths.db_root,
    )
    return json.dumps(envelope)


def get_stats(
    repo: OpportunityRepository,
    statuses: list[str] | None = None,
    priorities: list[str] | None = None,
    slug_substring: str | None = None,
    active_only: bool = False,
    include_archived: bool = False,
) -> str:
    """Aggregate funnel + sources counts, optionally filtered. Returns JSON."""
    f = _build_filters(
        statuses,
        priorities,
        slug_substring,
        active_only,
        include_archived,
    )
    if isinstance(f, dict):
        return json.dumps(f)
    try:
        stats = _query(repo).stats(f)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="get_stats"))
    return json.dumps(stats_to_dict(stats))


def list_files(repo: OpportunityRepository, slug: str) -> str:
    """List every non-hidden file in the opp's directory. Returns JSON array."""
    try:
        entries = _query(repo).files(slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_files"))
    return json.dumps([file_entry_to_dict(e) for e in entries])


def read_file(repo: OpportunityRepository, slug: str, filename: str) -> str:
    """Read a file from the opp's dir. Returns utf-8 text or base64 JSON."""
    try:
        raw = _query(repo).read_file(slug, filename)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="read_file"))
    try:
        text = raw.decode("utf-8")
        return json.dumps(
            {
                "filename": filename,
                "content": text,
                "encoding": "utf-8",
                "size": len(raw),
            }
        )
    except UnicodeDecodeError:
        return json.dumps(
            {
                "filename": filename,
                "content": base64.b64encode(raw).decode("ascii"),
                "encoding": "base64",
                "size": len(raw),
            }
        )


def register(app: FastMCP, repo: OpportunityRepository) -> None:
    """Register all read tools on the given FastMCP app."""

    @app.tool(
        name="list_opportunities",
        description="List opportunities, optionally filtered.",
    )
    def _list(
        statuses: list[str] | None = None,
        priorities: list[str] | None = None,
        slug_substring: str | None = None,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> str:
        return list_opportunities(
            repo,
            statuses,
            priorities,
            slug_substring,
            active_only,
            include_archived,
        )

    @app.tool(
        name="get_opportunity",
        description="Show one opportunity by slug (fuzzy match).",
    )
    def _get(slug: str) -> str:
        return get_opportunity(repo, slug)

    @app.tool(
        name="get_stats",
        description="Aggregate funnel + sources counts, optionally filtered.",
    )
    def _stats(
        statuses: list[str] | None = None,
        priorities: list[str] | None = None,
        slug_substring: str | None = None,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> str:
        return get_stats(
            repo,
            statuses,
            priorities,
            slug_substring,
            active_only,
            include_archived,
        )

    @app.tool(
        name="list_files",
        description="List every non-hidden file in the opp's directory.",
    )
    def _files(slug: str) -> str:
        return list_files(repo, slug)

    @app.tool(
        name="read_file",
        description="Read a file from the opp's dir. Returns utf-8 text or base64.",
    )
    def _read(slug: str, filename: str) -> str:
        return read_file(repo, slug, filename)
