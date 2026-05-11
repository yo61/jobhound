"""`jh contact` — append a contact entry."""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.git import commit_change, ensure_repo
from jobhound.meta_io import read_meta, write_meta
from jobhound.paths import paths_from_config
from jobhound.slug import resolve_slug


def run(
    slug_query: str,
    /,
    *,
    name: str,
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add a contact to the contacts list."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)
    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    opp = read_meta(opp_dir / "meta.toml")
    entry: dict[str, str] = {"name": name}
    if role_title is not None:
        entry["role"] = role_title
    if channel is not None:
        entry["channel"] = channel
    if company is not None:
        entry["company"] = company
    if note is not None:
        entry["note"] = note
    contacts = (*opp.contacts, entry)
    write_meta(replace(opp, contacts=contacts), opp_dir / "meta.toml")
    commit_change(
        paths.db_root,
        f"contact: {opp.slug} {name}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"contact added: {opp.slug} {name}")
