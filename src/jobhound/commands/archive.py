"""`jh archive` — move <slug> from opportunities/ to archive/."""

from __future__ import annotations

import shutil
import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.git import commit_change, ensure_repo
from jobhound.paths import Paths, paths_from_config
from jobhound.slug import resolve_slug


def run(
    slug_query: str,
    /,
    *,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Move an opportunity to the archive directory."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    ensure_repo(paths.db_root)
    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    dst = paths.archive_dir / opp_dir.name
    if dst.exists():
        print(f"archive target already exists: {dst}", file=sys.stderr)
        raise SystemExit(1)
    shutil.move(str(opp_dir), str(dst))
    commit_change(
        paths.db_root,
        f"archive: {opp_dir.name}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"archived: {opp_dir.name}")
