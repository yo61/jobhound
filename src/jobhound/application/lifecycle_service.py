"""State-transition use cases.

Each function loads via the repository, mutates via a domain method on the
aggregate, then saves with an auto-generated commit message. Returns
(before, after, opp_dir) so adapters (CLI, MCP) can format the result.

For `create`, `before` is None — there is no prior state.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jobhound.domain.opportunities import Opportunity
from jobhound.infrastructure.repository import OpportunityRepository


def create(
    repo: OpportunityRepository,
    opp: Opportunity,
) -> tuple[None, Opportunity, Path]:
    """Scaffold a new opportunity directory and write its meta.toml."""
    opp_dir = repo.create(opp, message=f"new: {opp.slug}")
    return None, opp, opp_dir


def apply_to(
    repo: OpportunityRepository,
    slug: str,
    *,
    applied_on: datetime,
    now: datetime,
    next_action: str,
    next_action_due: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    """Submit the application. Requires status `prospect`."""
    before, opp_dir = repo.find(slug)
    after = before.apply(
        applied_on=applied_on,
        now=now,
        next_action=next_action,
        next_action_due=next_action_due,
    )
    repo.save(after, opp_dir, message=f"apply: {after.slug}")
    return before, after, opp_dir


def log_interaction(
    repo: OpportunityRepository,
    slug: str,
    *,
    next_status: str,
    next_action: str | None,
    next_action_due: datetime | None,
    now: datetime,
    force: bool,
) -> tuple[Opportunity, Opportunity, Path]:
    """Record an interaction. `next_status='stay'` keeps the current status."""
    before, opp_dir = repo.find(slug)
    after = before.log_interaction(
        now=now,
        next_status=next_status,
        next_action=next_action,
        next_action_due=next_action_due,
        force=force,
    )
    arrow = (
        f"{before.status} → {after.status}"
        if after.status != before.status
        else "(no status change)"
    )
    repo.save(after, opp_dir, message=f"log: {after.slug} {arrow}")
    return before, after, opp_dir


def withdraw_from(
    repo: OpportunityRepository,
    slug: str,
    *,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    """Withdraw from the opportunity. Requires an active status."""
    before, opp_dir = repo.find(slug)
    after = before.withdraw(now=now)
    repo.save(after, opp_dir, message=f"withdraw: {after.slug}")
    return before, after, opp_dir


def mark_ghosted(
    repo: OpportunityRepository,
    slug: str,
    *,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    """Mark the opportunity as ghosted. Requires an active status."""
    before, opp_dir = repo.find(slug)
    after = before.ghost(now=now)
    repo.save(after, opp_dir, message=f"ghost: {after.slug}")
    return before, after, opp_dir


def accept_offer(
    repo: OpportunityRepository,
    slug: str,
    *,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    """Accept the offer. Requires status `offer`."""
    before, opp_dir = repo.find(slug)
    after = before.accept(now=now)
    repo.save(after, opp_dir, message=f"accept: {after.slug}")
    return before, after, opp_dir


def decline_offer(
    repo: OpportunityRepository,
    slug: str,
    *,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    """Decline the offer. Requires status `offer`."""
    before, opp_dir = repo.find(slug)
    after = before.decline(now=now)
    repo.save(after, opp_dir, message=f"decline: {after.slug}")
    return before, after, opp_dir
