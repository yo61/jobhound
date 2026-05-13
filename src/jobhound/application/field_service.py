"""Single-field setters. Replace the role `jh edit` plays interactively.

Each function does load → replace one field → save. All return
(before, after, opp_dir). All accept `no_commit: bool = False` so future
callers can opt out of the auto-commit (matches existing
OpportunityRepository.save / .create behavior).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
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
    *,
    no_commit: bool,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = replace(before, **{field_name: value})
    repo.save(after, opp_dir, message=f"{commit_label}: {after.slug}", no_commit=no_commit)
    return before, after, opp_dir


def set_company(
    repo: OpportunityRepository,
    slug: str,
    value: str,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "company", value, "company", no_commit=no_commit)


def set_role(
    repo: OpportunityRepository,
    slug: str,
    value: str,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "role", value, "role", no_commit=no_commit)


def set_priority(
    repo: OpportunityRepository,
    slug: str,
    level: Priority,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(
        repo,
        slug,
        "priority",
        level,
        f"priority {level.value}",
        no_commit=no_commit,
    )


def set_status(
    repo: OpportunityRepository,
    slug: str,
    status: Status,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    """Bypass transitions — write the status directly. Equivalent to `jh log --force`."""
    return _set_field(
        repo,
        slug,
        "status",
        status,
        f"status {status.value}",
        no_commit=no_commit,
    )


def set_source(
    repo: OpportunityRepository,
    slug: str,
    value: str | None,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "source", value, "source", no_commit=no_commit)


def set_location(
    repo: OpportunityRepository,
    slug: str,
    value: str | None,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "location", value, "location", no_commit=no_commit)


def set_comp_range(
    repo: OpportunityRepository,
    slug: str,
    value: str | None,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "comp_range", value, "comp_range", no_commit=no_commit)


def set_first_contact(
    repo: OpportunityRepository,
    slug: str,
    value: date | None,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "first_contact", value, "first_contact", no_commit=no_commit)


def set_applied_on(
    repo: OpportunityRepository,
    slug: str,
    value: date | None,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "applied_on", value, "applied_on", no_commit=no_commit)


def set_last_activity(
    repo: OpportunityRepository,
    slug: str,
    value: date | None,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "last_activity", value, "last_activity", no_commit=no_commit)


def set_next_action(
    repo: OpportunityRepository,
    slug: str,
    *,
    text: str | None,
    due: date | None,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    """Set both `next_action` and `next_action_due` in one go (they travel together)."""
    before, opp_dir = repo.find(slug)
    after = replace(before, next_action=text, next_action_due=due)
    repo.save(after, opp_dir, message=f"next_action: {after.slug}", no_commit=no_commit)
    return before, after, opp_dir


def touch(
    repo: OpportunityRepository,
    slug: str,
    *,
    today: date,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    """Bump last_activity to today without changing anything else."""
    before, opp_dir = repo.find(slug)
    after = before.touch(today=today)
    repo.save(after, opp_dir, message=f"touch: {after.slug}", no_commit=no_commit)
    return before, after, opp_dir
