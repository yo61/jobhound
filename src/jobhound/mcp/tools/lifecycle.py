"""MCP lifecycle tools — route to application/lifecycle_service."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING, Any

from jobhound.application import lifecycle_service
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.converters import mutation_response
from jobhound.mcp.errors import exception_to_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _parse_date(s: str | None, default: date) -> date:
    return date.fromisoformat(s) if s else default


def _wrap_mutation(
    tool_name: str,
    fn: Any,
    today: date,
) -> str:
    try:
        before, after, opp_dir = fn()
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool=tool_name))
    return json.dumps(mutation_response(before, after, opp_dir, today=today))


def _derive_slug(company: str, today: date) -> str:
    """Default slug like '2026-05-acme' from company + today."""
    return f"{today.strftime('%Y-%m')}-{company.lower().replace(' ', '-')}"


def new_opportunity(
    repo: OpportunityRepository,
    *,
    company: str,
    role: str,
    slug: str | None = None,
    source: str | None = None,
    priority: str = "medium",
    location: str | None = None,
    comp_range: str | None = None,
    first_contact: str | None = None,
    tags: list[str] | None = None,
    next_action: str | None = None,
    next_action_due: str | None = None,
) -> str:
    """Scaffold a new opportunity in status 'prospect'."""
    today = date.today()
    try:
        opp = Opportunity(
            slug=slug or _derive_slug(company, today),
            company=company,
            role=role,
            status=Status.PROSPECT,
            priority=Priority(priority),
            source=source,
            location=location,
            comp_range=comp_range,
            first_contact=_parse_date(first_contact, today),
            applied_on=None,
            last_activity=None,
            next_action=next_action,
            next_action_due=(date.fromisoformat(next_action_due) if next_action_due else None),
            tags=tuple(tags or ()),
        )
    except ValueError as exc:
        return json.dumps(
            exception_to_response(
                exc,
                tool="new_opportunity",
                invalid_param=("priority", priority, [p.value for p in Priority]),
            )
        )
    return _wrap_mutation(
        "new_opportunity",
        lambda: lifecycle_service.create(repo, opp),
        today,
    )


def apply_to(
    repo: OpportunityRepository,
    *,
    slug: str,
    next_action: str,
    next_action_due: str,
    applied_on: str | None = None,
    today: str | None = None,
) -> str:
    """Submit application. Requires status 'prospect'."""
    today_d = _parse_date(today, date.today())
    return _wrap_mutation(
        "apply_to",
        lambda: lifecycle_service.apply_to(
            repo,
            slug,
            applied_on=_parse_date(applied_on, today_d),
            today=today_d,
            next_action=next_action,
            next_action_due=date.fromisoformat(next_action_due),
        ),
        today_d,
    )


def log_interaction(
    repo: OpportunityRepository,
    *,
    slug: str,
    next_status: str,
    next_action: str | None = None,
    next_action_due: str | None = None,
    today: str | None = None,
    force: bool = False,
) -> str:
    """Record an interaction. next_status='stay' keeps current status."""
    today_d = _parse_date(today, date.today())
    return _wrap_mutation(
        "log_interaction",
        lambda: lifecycle_service.log_interaction(
            repo,
            slug,
            next_status=next_status,
            next_action=next_action,
            next_action_due=(date.fromisoformat(next_action_due) if next_action_due else None),
            today=today_d,
            force=force,
        ),
        today_d,
    )


def withdraw_from(
    repo: OpportunityRepository,
    *,
    slug: str,
    today: str | None = None,
) -> str:
    """Mark as withdrawn. Requires active status."""
    today_d = _parse_date(today, date.today())
    return _wrap_mutation(
        "withdraw_from",
        lambda: lifecycle_service.withdraw_from(repo, slug, today=today_d),
        today_d,
    )


def mark_ghosted(
    repo: OpportunityRepository,
    *,
    slug: str,
    today: str | None = None,
) -> str:
    """Mark as ghosted. Requires active status."""
    today_d = _parse_date(today, date.today())
    return _wrap_mutation(
        "mark_ghosted",
        lambda: lifecycle_service.mark_ghosted(repo, slug, today=today_d),
        today_d,
    )


def accept_offer(
    repo: OpportunityRepository,
    *,
    slug: str,
    today: str | None = None,
) -> str:
    """Accept an offer. Requires status 'offer'."""
    today_d = _parse_date(today, date.today())
    return _wrap_mutation(
        "accept_offer",
        lambda: lifecycle_service.accept_offer(repo, slug, today=today_d),
        today_d,
    )


def decline_offer(
    repo: OpportunityRepository,
    *,
    slug: str,
    today: str | None = None,
) -> str:
    """Decline an offer. Requires status 'offer'."""
    today_d = _parse_date(today, date.today())
    return _wrap_mutation(
        "decline_offer",
        lambda: lifecycle_service.decline_offer(repo, slug, today=today_d),
        today_d,
    )


def register(app: FastMCP, repo: OpportunityRepository) -> None:
    """Register all lifecycle tools on the given FastMCP app."""

    @app.tool(
        name="new_opportunity",
        description="Scaffold a new opportunity in status 'prospect'.",
    )
    def _new(
        company: str,
        role: str,
        slug: str | None = None,
        source: str | None = None,
        priority: str = "medium",
        location: str | None = None,
        comp_range: str | None = None,
        first_contact: str | None = None,
        tags: list[str] | None = None,
        next_action: str | None = None,
        next_action_due: str | None = None,
    ) -> str:
        return new_opportunity(
            repo,
            company=company,
            role=role,
            slug=slug,
            source=source,
            priority=priority,
            location=location,
            comp_range=comp_range,
            first_contact=first_contact,
            tags=tags,
            next_action=next_action,
            next_action_due=next_action_due,
        )

    @app.tool(
        name="apply_to",
        description="Submit application. Requires status 'prospect'.",
    )
    def _apply(
        slug: str,
        next_action: str,
        next_action_due: str,
        applied_on: str | None = None,
        today: str | None = None,
    ) -> str:
        return apply_to(
            repo,
            slug=slug,
            next_action=next_action,
            next_action_due=next_action_due,
            applied_on=applied_on,
            today=today,
        )

    @app.tool(
        name="log_interaction",
        description="Record an interaction. next_status='stay' keeps current status.",
    )
    def _log(
        slug: str,
        next_status: str,
        next_action: str | None = None,
        next_action_due: str | None = None,
        today: str | None = None,
        force: bool = False,
    ) -> str:
        return log_interaction(
            repo,
            slug=slug,
            next_status=next_status,
            next_action=next_action,
            next_action_due=next_action_due,
            today=today,
            force=force,
        )

    @app.tool(
        name="withdraw_from",
        description="Mark as withdrawn. Requires active status.",
    )
    def _withdraw(slug: str, today: str | None = None) -> str:
        return withdraw_from(repo, slug=slug, today=today)

    @app.tool(
        name="mark_ghosted",
        description="Mark as ghosted. Requires active status.",
    )
    def _ghost(slug: str, today: str | None = None) -> str:
        return mark_ghosted(repo, slug=slug, today=today)

    @app.tool(
        name="accept_offer",
        description="Accept an offer. Requires status 'offer'.",
    )
    def _accept(slug: str, today: str | None = None) -> str:
        return accept_offer(repo, slug=slug, today=today)

    @app.tool(
        name="decline_offer",
        description="Decline an offer. Requires status 'offer'.",
    )
    def _decline(slug: str, today: str | None = None) -> str:
        return decline_offer(repo, slug=slug, today=today)
