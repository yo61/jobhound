"""`jh delete` — remove an opportunity directory."""

from __future__ import annotations

import shutil
from typing import Annotated

import questionary
from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.git import commit_change, ensure_repo
from jobhound.paths import paths_from_config
from jobhound.slug import resolve_slug


def run(
    slug_query: str,
    /,
    *,
    yes: bool = False,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Delete an opportunity directory (e.g. a duplicate scaffold).

    --yes: skip the confirmation prompt.
    """
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)
    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    if not yes:
        confirm = questionary.confirm(f"Delete {opp_dir.name}?", default=False).ask()
        if not confirm:
            print("aborted")
            raise SystemExit(1)
    shutil.rmtree(opp_dir)
    commit_change(
        paths.db_root,
        f"delete: {opp_dir.name}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"deleted: {opp_dir.name}")
