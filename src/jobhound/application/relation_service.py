"""Relation operations: tags, contacts, links.

Each function accepts `no_commit: bool = False` (keyword-only) so callers
can opt out of the auto-commit (mirrors OpportunityRepository.save's flag).
"""

from __future__ import annotations

from pathlib import Path

from jobhound.domain.contact import Contact
from jobhound.domain.opportunities import Opportunity
from jobhound.infrastructure.repository import OpportunityRepository


def add_tag(
    repo: OpportunityRepository,
    slug: str,
    tag: str,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_tags(add={tag}, remove=set())
    repo.save(after, opp_dir, message=f"tag: {after.slug} +{tag}", no_commit=no_commit)
    return before, after, opp_dir


def remove_tag(
    repo: OpportunityRepository,
    slug: str,
    tag: str,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_tags(add=set(), remove={tag})
    repo.save(after, opp_dir, message=f"tag: {after.slug} -{tag}", no_commit=no_commit)
    return before, after, opp_dir


def add_contact(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
    role: str | None,
    channel: str | None,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_contact(Contact(name=name, role=role, channel=channel))
    repo.save(after, opp_dir, message=f"contact: {after.slug} {name}", no_commit=no_commit)
    return before, after, opp_dir


def set_link(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
    url: str,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_link(name=name, url=url)
    repo.save(after, opp_dir, message=f"link: {after.slug} {name}", no_commit=no_commit)
    return before, after, opp_dir
