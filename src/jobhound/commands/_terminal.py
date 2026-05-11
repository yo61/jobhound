"""Shared logic for terminal-status verbs (withdraw, ghost, accept, decline)."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
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
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()
    opp, opp_dir = repo.find(slug_query)

    try:
        require_transition(opp.status, target_status, verb=verb)
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    updated = replace(opp, status=target_status, last_activity=today_date)
    repo.save(updated, opp_dir, message=f"{verb}: {opp.slug}", no_commit=no_commit)
    print(f"{verb}: {opp.slug}")
