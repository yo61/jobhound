"""`jh link` — add or update an entry in the links table."""

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
    url: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add or update a link."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)
    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    opp = read_meta(opp_dir / "meta.toml")
    links = dict(opp.links)
    links[name] = url
    write_meta(replace(opp, links=links), opp_dir / "meta.toml")
    commit_change(
        paths.db_root,
        f"link: {opp.slug} {name}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"link {opp.slug}: {name} = {url}")
