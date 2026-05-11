"""`jh priority` — set priority to high/medium/low."""

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

_VALID = {"high", "medium", "low"}


def run(
    slug_query: str,
    /,
    *,
    to: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Set the priority of an opportunity."""
    if to not in _VALID:
        print(f"--to must be one of {sorted(_VALID)}", file=sys.stderr)
        raise SystemExit(1)
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)
    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    opp = read_meta(opp_dir / "meta.toml")
    write_meta(replace(opp, priority=to), opp_dir / "meta.toml")
    commit_change(
        paths.db_root,
        f"priority: {opp.slug} {to}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"priority {opp.slug}: {to}")
