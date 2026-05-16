"""Relation operations: tags, contacts, links."""

from __future__ import annotations

from pathlib import Path

from jobhound.domain.contact import Contact
from jobhound.domain.opportunities import Opportunity
from jobhound.infrastructure.repository import OpportunityRepository


def add_tag(
    repo: OpportunityRepository,
    slug: str,
    tag: str,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_tags(add={tag}, remove=set())
    repo.save(after, opp_dir, message=f"tag: {after.slug} +{tag}")
    return before, after, opp_dir


def remove_tag(
    repo: OpportunityRepository,
    slug: str,
    tag: str,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_tags(add=set(), remove={tag})
    repo.save(after, opp_dir, message=f"tag: {after.slug} -{tag}")
    return before, after, opp_dir


def set_tags(
    repo: OpportunityRepository,
    slug: str,
    *,
    add: set[str],
    remove: set[str],
) -> tuple[Opportunity, Opportunity, Path]:
    """Apply add/remove tag deltas in one save. Matches `jh tag`'s batched form."""
    before, opp_dir = repo.find(slug)
    after = before.with_tags(add=add, remove=remove)
    summary = " ".join([*(f"+{t}" for t in sorted(add)), *(f"-{t}" for t in sorted(remove))])
    repo.save(after, opp_dir, message=f"tag: {after.slug} {summary}")
    return before, after, opp_dir


def add_contact(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
    role: str | None,
    channel: str | None,
    company: str | None = None,
    note: str | None = None,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_contact(
        Contact(
            name=name,
            role=role,
            channel=channel,
            company=company,
            note=note,
        )
    )
    repo.save(after, opp_dir, message=f"contact: {after.slug} {name}")
    return before, after, opp_dir


def remove_contact(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
    role: str | None,
    channel: str | None,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.without_contact(name=name, role=role, channel=channel)
    repo.save(after, opp_dir, message=f"contact: {after.slug} -{name}")
    return before, after, opp_dir


def set_link(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
    url: str,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_link(name=name, url=url)
    repo.save(after, opp_dir, message=f"link: {after.slug} {name}")
    return before, after, opp_dir
