"""MCP field tools — route to application/field_service."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from jobhound.application import field_service
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.converters import mutation_response
from jobhound.mcp.errors import exception_to_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _wrap(tool_name: str, fn: Callable[[], Any], now: datetime) -> str:
    try:
        before, after, opp_dir = fn()
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool=tool_name))
    return json.dumps(mutation_response(before, after, opp_dir, now=now))


def _parse_date_optional(s: str | None) -> datetime | None:
    if s is None:
        return None
    d = date.fromisoformat(s)
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def set_company(
    repo: OpportunityRepository,
    *,
    slug: str,
    value: str,
) -> str:
    return _wrap(
        "set_company",
        lambda: field_service.set_company(repo, slug, value),
        now_utc(),
    )


def set_role(
    repo: OpportunityRepository,
    *,
    slug: str,
    value: str,
) -> str:
    return _wrap(
        "set_role",
        lambda: field_service.set_role(repo, slug, value),
        now_utc(),
    )


def set_priority(
    repo: OpportunityRepository,
    *,
    slug: str,
    level: str,
) -> str:
    try:
        p = Priority(level)
    except ValueError as exc:
        return json.dumps(
            exception_to_response(
                exc,
                tool="set_priority",
                invalid_param=("level", level, [v.value for v in Priority]),
            )
        )
    return _wrap(
        "set_priority",
        lambda: field_service.set_priority(repo, slug, p),
        now_utc(),
    )


def set_status(
    repo: OpportunityRepository,
    *,
    slug: str,
    status: str,
) -> str:
    try:
        s = Status(status)
    except ValueError as exc:
        return json.dumps(
            exception_to_response(
                exc,
                tool="set_status",
                invalid_param=("status", status, [v.value for v in Status]),
            )
        )
    return _wrap(
        "set_status",
        lambda: field_service.set_status(repo, slug, s),
        now_utc(),
    )


def set_source(
    repo: OpportunityRepository,
    *,
    slug: str,
    value: str | None,
) -> str:
    return _wrap(
        "set_source",
        lambda: field_service.set_source(repo, slug, value),
        now_utc(),
    )


def set_location(
    repo: OpportunityRepository,
    *,
    slug: str,
    value: str | None,
) -> str:
    return _wrap(
        "set_location",
        lambda: field_service.set_location(repo, slug, value),
        now_utc(),
    )


def set_comp_range(
    repo: OpportunityRepository,
    *,
    slug: str,
    value: str | None,
) -> str:
    return _wrap(
        "set_comp_range",
        lambda: field_service.set_comp_range(repo, slug, value),
        now_utc(),
    )


def set_first_contact(
    repo: OpportunityRepository,
    *,
    slug: str,
    value: str | None,
) -> str:
    return _wrap(
        "set_first_contact",
        lambda: field_service.set_first_contact(
            repo,
            slug,
            _parse_date_optional(value),
        ),
        now_utc(),
    )


def set_applied_on(
    repo: OpportunityRepository,
    *,
    slug: str,
    value: str | None,
) -> str:
    return _wrap(
        "set_applied_on",
        lambda: field_service.set_applied_on(
            repo,
            slug,
            _parse_date_optional(value),
        ),
        now_utc(),
    )


def set_last_activity(
    repo: OpportunityRepository,
    *,
    slug: str,
    value: str | None,
) -> str:
    return _wrap(
        "set_last_activity",
        lambda: field_service.set_last_activity(
            repo,
            slug,
            _parse_date_optional(value),
        ),
        now_utc(),
    )


def set_next_action(
    repo: OpportunityRepository,
    *,
    slug: str,
    text: str | None,
    due: str | None = None,
) -> str:
    return _wrap(
        "set_next_action",
        lambda: field_service.set_next_action(
            repo,
            slug,
            text=text,
            due=_parse_date_optional(due),
        ),
        now_utc(),
    )


def touch(
    repo: OpportunityRepository,
    *,
    slug: str,
    today: str | None = None,
) -> str:
    now = datetime(*(date.fromisoformat(today).timetuple()[:3]), tzinfo=UTC) if today else now_utc()
    return _wrap(
        "touch",
        lambda: field_service.touch(repo, slug, now=now),
        now,
    )


def register(app: FastMCP, repo: OpportunityRepository) -> None:
    """Register all field tools on the given FastMCP app.

    Each handler uses explicit-typed params (not **kw) so FastMCP can
    build the right JSON schema — matches the pattern from reads.py and
    lifecycle.py.
    """

    @app.tool(name="set_company", description="Change the company name.")
    def _co(slug: str, value: str) -> str:
        return set_company(repo, slug=slug, value=value)

    @app.tool(name="set_role", description="Change the role title.")
    def _r(slug: str, value: str) -> str:
        return set_role(repo, slug=slug, value=value)

    @app.tool(name="set_priority", description="Set priority: high/medium/low.")
    def _p(slug: str, level: str) -> str:
        return set_priority(repo, slug=slug, level=level)

    @app.tool(
        name="set_status",
        description=(
            "Write status directly, bypassing transitions. "
            "Use log_interaction for state-machine-checked changes."
        ),
    )
    def _s(slug: str, status: str) -> str:
        return set_status(repo, slug=slug, status=status)

    @app.tool(
        name="set_source",
        description="Set or clear the source field (where you heard about it).",
    )
    def _src(slug: str, value: str | None = None) -> str:
        return set_source(repo, slug=slug, value=value)

    @app.tool(name="set_location", description="Set or clear the location field.")
    def _loc(slug: str, value: str | None = None) -> str:
        return set_location(repo, slug=slug, value=value)

    @app.tool(
        name="set_comp_range",
        description="Set or clear the compensation range field.",
    )
    def _comp(slug: str, value: str | None = None) -> str:
        return set_comp_range(repo, slug=slug, value=value)

    @app.tool(
        name="set_first_contact",
        description="Set or clear the first-contact date (ISO YYYY-MM-DD).",
    )
    def _fc(slug: str, value: str | None = None) -> str:
        return set_first_contact(repo, slug=slug, value=value)

    @app.tool(
        name="set_applied_on",
        description="Set or clear the applied-on date (ISO YYYY-MM-DD).",
    )
    def _ao(slug: str, value: str | None = None) -> str:
        return set_applied_on(repo, slug=slug, value=value)

    @app.tool(
        name="set_last_activity",
        description="Set or clear the last-activity date (ISO YYYY-MM-DD).",
    )
    def _la(slug: str, value: str | None = None) -> str:
        return set_last_activity(repo, slug=slug, value=value)

    @app.tool(
        name="set_next_action",
        description="Set the next-action text + due date together (or clear both).",
    )
    def _na(slug: str, text: str | None, due: str | None = None) -> str:
        return set_next_action(repo, slug=slug, text=text, due=due)

    @app.tool(
        name="touch",
        description="Bump last_activity to today without other change.",
    )
    def _t(slug: str, today: str | None = None) -> str:
        return touch(repo, slug=slug, today=today)
