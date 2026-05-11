"""`jh tag` — add and/or remove tags."""

from __future__ import annotations

import sys
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
    add: list[str] | None = None,
    remove: list[str] | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add and/or remove tags."""
    add_set = set(add or [])
    remove_set = set(remove or [])
    if not add_set and not remove_set:
        print("nothing to do; pass --add and/or --remove", file=sys.stderr)
        raise SystemExit(1)

    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)
    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    opp = read_meta(opp_dir / "meta.toml")
    tags = (set(opp.tags) | add_set) - remove_set
    new_tags = tuple(sorted(tags))
    write_meta(replace(opp, tags=new_tags), opp_dir / "meta.toml")

    summary = " ".join(
        [*(f"+{t}" for t in sorted(add_set)), *(f"-{t}" for t in sorted(remove_set))]
    )
    commit_change(
        paths.db_root,
        f"tag: {opp.slug} {summary}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"tags {opp.slug}: {new_tags}")
