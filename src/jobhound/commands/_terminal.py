"""Shared logic for terminal-status verbs (withdraw, ghost, accept, decline)."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date

from jobhound.config import load_config
from jobhound.git import commit_change, ensure_repo
from jobhound.meta_io import read_meta, write_meta
from jobhound.paths import paths_from_config
from jobhound.slug import resolve_slug
from jobhound.transitions import InvalidTransitionError, require_transition


def run_transition(
    *,
    slug_query: str,
    verb: str,
    target_status: str,
    today: str | None,
    no_commit: bool,
) -> None:
    """Move an opportunity to `target_status`. Used by withdraw/ghost/accept/decline."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)

    today_date = date.fromisoformat(today) if today else date.today()
    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    opp = read_meta(opp_dir / "meta.toml")

    try:
        require_transition(opp.status, target_status, verb=verb)
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    updated = replace(opp, status=target_status, last_activity=today_date)
    write_meta(updated, opp_dir / "meta.toml")
    commit_change(
        paths.db_root,
        f"{verb}: {opp.slug}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"{verb}: {opp.slug}")
