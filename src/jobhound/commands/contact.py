"""`jh contact` subgroup — manage contacts on an opportunity."""

from __future__ import annotations

import json
import sys
from typing import Annotated

from cyclopts import App, Parameter

from jobhound.application import relation_service
from jobhound.application.relation_service import (
    AmbiguousContactError,
    ContactNotFoundError,
)
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

app = App(name="contact", help="Manage contacts on an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


def _handle_error(exc: Exception, *, verb: str) -> None:
    if isinstance(exc, ContactNotFoundError):
        print(f"{verb}: {exc}", file=sys.stderr)
    elif isinstance(exc, AmbiguousContactError):
        print(f"{verb}: {exc}", file=sys.stderr)
        for m in exc.matches:
            role = m.role or "—"
            channel = m.channel or "—"
            print(f"    {m.name}  role={role}  channel={channel}", file=sys.stderr)
    else:
        print(f"{verb}: error: {exc}", file=sys.stderr)
    raise SystemExit(1)


@app.command(name="add")
def add(
    slug_query: str,
    /,
    *,
    name: str,
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
) -> None:
    """Add a contact."""
    _, after, _ = relation_service.add_contact(
        _repo(),
        slug_query,
        name=name,
        role=role_title,
        channel=channel,
        company=company,
        note=note,
    )
    print(f"contact added: {after.slug} {name}")


@app.command(name="remove")
def remove(
    slug_query: str,
    /,
    *,
    name: str,
    role: str | None = None,
    channel: str | None = None,
) -> None:
    """Remove a contact."""
    _, after, _ = relation_service.remove_contact(
        _repo(),
        slug_query,
        name=name,
        role=role,
        channel=channel,
    )
    print(f"contact removed: {after.slug} {name}")


@app.command(name="list")
def list_(
    slug_query: str,
    /,
    *,
    as_json: Annotated[bool, Parameter(name=["--json"], negative=())] = False,
) -> None:
    """List contacts on an opportunity."""
    try:
        _, contacts = relation_service.list_contacts(_repo(), slug_query)
    except Exception as exc:
        _handle_error(exc, verb="list")
        return
    if as_json:
        print(json.dumps([c.to_dict() for c in contacts]))
        return
    if not contacts:
        print("(no contacts)", file=sys.stderr)
        return
    print(f"{'NAME':<28}  {'ROLE':<20}  {'CHANNEL':<14}  COMPANY")
    for c in contacts:
        role = c.role or "—"
        channel = c.channel or "—"
        company = c.company or "—"
        print(f"{c.name:<28}  {role:<20}  {channel:<14}  {company}")


@app.command(name="show")
def show(
    slug_query: str,
    name: str,
    /,
    *,
    match_role: Annotated[str | None, Parameter(name=["--match-role"])] = None,
    match_channel: Annotated[str | None, Parameter(name=["--match-channel"])] = None,
    as_json: Annotated[bool, Parameter(name=["--json"], negative=())] = False,
) -> None:
    """Show one contact's full details."""
    try:
        _, contact, _ = relation_service.find_contact(
            _repo(),
            slug_query,
            name=name,
            match_role=match_role,
            match_channel=match_channel,
        )
    except Exception as exc:
        _handle_error(exc, verb="show")
        return
    if as_json:
        print(json.dumps(contact.to_dict()))
        return
    print(f"name:    {contact.name}")
    for label, value in (
        ("role", contact.role),
        ("channel", contact.channel),
        ("company", contact.company),
        ("note", contact.note),
    ):
        if value is not None:
            print(f"{label}:    {value}")


@app.command(name="edit")
def edit(
    slug_query: str,
    name: str,
    /,
    *,
    match_role: Annotated[str | None, Parameter(name=["--match-role"])] = None,
    match_channel: Annotated[str | None, Parameter(name=["--match-channel"])] = None,
    new_name: Annotated[str | None, Parameter(name=["--new-name"])] = None,
    role: Annotated[str | None, Parameter(name=["--role"])] = None,
    channel: Annotated[str | None, Parameter(name=["--channel"])] = None,
    company: Annotated[str | None, Parameter(name=["--company"])] = None,
    note: Annotated[str | None, Parameter(name=["--note"])] = None,
) -> None:
    """Update fields on an existing contact.

    Renames are allowed via `--new-name`. After a rename, the contact must
    be addressed by its new name in subsequent commands.
    """
    try:
        _, after, updated, _ = relation_service.edit_contact(
            _repo(),
            slug_query,
            name=name,
            match_role=match_role,
            match_channel=match_channel,
            new_name=new_name,
            new_role=role,
            new_channel=channel,
            new_company=company,
            new_note=note,
        )
    except Exception as exc:
        _handle_error(exc, verb="edit")
        return
    if new_name and new_name != name:
        print(f"contact edited: {after.slug} {name} → {updated.name}")
    else:
        print(f"contact edited: {after.slug} {updated.name}")
