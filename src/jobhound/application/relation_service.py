"""Relation operations: tags, contacts, links."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from jobhound.domain.contact import Contact
from jobhound.domain.opportunities import Opportunity
from jobhound.infrastructure.repository import OpportunityRepository


class RelationServiceError(Exception):
    """Base class for relation_service exceptions."""


class ContactNotFoundError(RelationServiceError):
    """No contact matched the given name/role/channel."""

    def __init__(self, slug: str, name: str) -> None:
        super().__init__(f"no contact named {name!r} in {slug}")
        self.slug = slug
        self.name = name


class AmbiguousContactError(RelationServiceError):
    """More than one contact matched; caller must disambiguate."""

    def __init__(self, slug: str, name: str, matches: tuple[Contact, ...]) -> None:
        super().__init__(
            f"{len(matches)} contacts named {name!r} in {slug}; "
            f"pass --match-role and/or --match-channel"
        )
        self.slug = slug
        self.name = name
        self.matches = matches


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


def list_contacts(
    repo: OpportunityRepository,
    slug: str,
) -> tuple[Opportunity, tuple[Contact, ...]]:
    """Return the opp's contacts in their stored order."""
    opp, _ = repo.find(slug)
    return opp, opp.contacts


def find_contact(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
    match_role: str | None = None,
    match_channel: str | None = None,
) -> tuple[Opportunity, Contact, Path]:
    """Look up a single contact by name (+ optional disambiguators).

    Raises ContactNotFoundError if zero match, AmbiguousContactError if
    multiple match.
    """
    opp, opp_dir = repo.find(slug)
    matches = opp.find_contacts(name, match_role=match_role, match_channel=match_channel)
    if not matches:
        raise ContactNotFoundError(slug, name)
    if len(matches) > 1:
        raise AmbiguousContactError(slug, name, matches)
    return opp, matches[0], opp_dir


def edit_contact(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
    match_role: str | None = None,
    match_channel: str | None = None,
    new_name: str | None = None,
    new_role: str | None = None,
    new_channel: str | None = None,
    new_company: str | None = None,
    new_note: str | None = None,
) -> tuple[Opportunity, Opportunity, Contact, Path]:
    """Update one contact's fields. `None` means "leave unchanged".

    Pass any of the `new_*` fields to replace that field's value. Returns
    (before, after, updated_contact, opp_dir). Raises ContactNotFoundError
    or AmbiguousContactError if the addressing fails.
    """
    before, current, opp_dir = find_contact(
        repo,
        slug,
        name=name,
        match_role=match_role,
        match_channel=match_channel,
    )
    updates: dict[str, str | None] = {}
    if new_name is not None:
        updates["name"] = new_name
    if new_role is not None:
        updates["role"] = new_role
    if new_channel is not None:
        updates["channel"] = new_channel
    if new_company is not None:
        updates["company"] = new_company
    if new_note is not None:
        updates["note"] = new_note
    if not updates:
        # No changes — return without writing.
        return before, before, current, opp_dir
    updated = replace(current, **updates)
    after = before.replace_contact(current, updated)
    summary = ", ".join(f"{k}={v!r}" for k, v in updates.items())
    repo.save(after, opp_dir, message=f"contact: edit {after.slug} {name} {summary}")
    return before, after, updated, opp_dir


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


def remove_link(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
) -> tuple[Opportunity, Opportunity, Path]:
    """Remove a named link from an opportunity. Raises if the link doesn't exist."""
    before, opp_dir = repo.find(slug)
    after = before.without_link(name=name)
    repo.save(after, opp_dir, message=f"link: {after.slug} -{name}")
    return before, after, opp_dir
