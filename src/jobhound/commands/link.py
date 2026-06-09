"""`jh link` subgroup — manage named links on an opportunity."""

from __future__ import annotations

import sys

from cyclopts import App

from jobhound.application import relation_service
from jobhound.application.relation_service import LinkNotFoundError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

app = App(name="link", help="Manage named links on an opportunity.")


def _repo() -> OpportunityRepository:
    cfg = load_config()
    return OpportunityRepository(paths_from_config(cfg), cfg)


@app.command(name="set")
def set_(
    slug_query: str,
    /,
    *,
    name: str,
    url: str,
) -> None:
    """Set or replace a named link."""
    _, after, _ = relation_service.set_link(_repo(), slug_query, name=name, url=url)
    print(f"link {after.slug}: {name} = {url}")


@app.command(name="remove")
def remove(slug_query: str, /, *, name: str) -> None:
    """Remove a named link."""
    _, after, _ = relation_service.remove_link(_repo(), slug_query, name=name)
    print(f"link removed: {after.slug} {name}")


@app.command(name="list")
def list_(slug_query: str, /) -> None:
    """List named links on an opportunity."""
    _, links = relation_service.list_links(_repo(), slug_query)
    if not links:
        print("(no links)", file=sys.stderr)
        return
    for name, url in links.items():
        print(f"{name}  {url}")


@app.command(name="show")
def show(slug_query: str, name: str, /) -> None:
    """Print one link's URL (pipe-friendly: URL only)."""
    try:
        _, url = relation_service.find_link(_repo(), slug_query, name=name)
    except LinkNotFoundError as exc:
        print(f"show: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(url)
