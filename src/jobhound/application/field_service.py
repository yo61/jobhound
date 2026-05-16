"""Single-field setters for opportunities.

Each function does load → replace one field → save. All return
(before, after, opp_dir).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.repository import OpportunityRepository


def _set_field(
    repo: OpportunityRepository,
    slug: str,
    field_name: str,
    value: object,
    commit_label: str,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = replace(before, **{field_name: value})
    repo.save(after, opp_dir, message=f"{commit_label}: {after.slug}")
    return before, after, opp_dir


def set_company(
    repo: OpportunityRepository,
    slug: str,
    value: str,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "company", value, "company")


def set_role(
    repo: OpportunityRepository,
    slug: str,
    value: str,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "role", value, "role")


def set_priority(
    repo: OpportunityRepository,
    slug: str,
    level: Priority,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = replace(before, priority=level)
    repo.save(after, opp_dir, message=f"priority: {after.slug} {level.value}")
    return before, after, opp_dir


def set_status(
    repo: OpportunityRepository,
    slug: str,
    status: Status,
) -> tuple[Opportunity, Opportunity, Path]:
    """Bypass transitions — write the status directly. Equivalent to `jh log --force`."""
    before, opp_dir = repo.find(slug)
    after = replace(before, status=status)
    repo.save(after, opp_dir, message=f"status: {after.slug} {status.value}")
    return before, after, opp_dir


def set_source(
    repo: OpportunityRepository,
    slug: str,
    value: str | None,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "source", value, "source")


def set_location(
    repo: OpportunityRepository,
    slug: str,
    value: str | None,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "location", value, "location")


def set_comp_range(
    repo: OpportunityRepository,
    slug: str,
    value: str | None,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "comp_range", value, "comp_range")


def set_first_contact(
    repo: OpportunityRepository,
    slug: str,
    value: datetime | None,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "first_contact", value, "first_contact")


def set_applied_on(
    repo: OpportunityRepository,
    slug: str,
    value: datetime | None,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "applied_on", value, "applied_on")


def set_last_activity(
    repo: OpportunityRepository,
    slug: str,
    value: datetime | None,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "last_activity", value, "last_activity")


def set_next_action(
    repo: OpportunityRepository,
    slug: str,
    *,
    text: str | None,
    due: datetime | None,
) -> tuple[Opportunity, Opportunity, Path]:
    """Set both `next_action` and `next_action_due` in one go (they travel together)."""
    before, opp_dir = repo.find(slug)
    after = replace(before, next_action=text, next_action_due=due)
    repo.save(after, opp_dir, message=f"next_action: {after.slug}")
    return before, after, opp_dir


def bump(
    repo: OpportunityRepository,
    slug: str,
    *,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    """Bump last_activity to `now` without changing anything else."""
    before, opp_dir = repo.find(slug)
    after = before.bump(now=now)
    repo.save(after, opp_dir, message=f"bump: {after.slug}")
    return before, after, opp_dir
