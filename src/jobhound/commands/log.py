"""`jh log` — record an interaction; default next status advances one stage."""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.git import commit_change, ensure_repo
from jobhound.meta_io import read_meta, write_meta
from jobhound.paths import paths_from_config
from jobhound.slug import resolve_slug
from jobhound.transitions import InvalidTransitionError, require_transition

_NAME_SLUG = re.compile(r"[^a-z0-9]+")


def _name_slug(who: str) -> str:
    return _NAME_SLUG.sub("-", who.lower()).strip("-") or "unknown"


def _correspondence_filename(when: date, channel: str, direction: str, who: str) -> str:
    return f"{when.isoformat()}-{channel}-{direction}-{_name_slug(who)}.md"


def run(
    slug_query: str,
    /,
    *,
    channel: str,
    direction: str,
    who: str,
    body: Path,
    next_status: str = "stay",
    next_action: str | None = None,
    next_action_due: str | None = None,
    force: bool = False,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Record an interaction (correspondence) and update status + next action."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)

    today_date = date.fromisoformat(today) if today else date.today()

    if direction not in {"from", "to"}:
        print(f"--direction must be 'from' or 'to', got {direction!r}", file=sys.stderr)
        raise SystemExit(1)

    if not body.is_file():
        print(f"--body file not found: {body}", file=sys.stderr)
        raise SystemExit(1)

    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    opp = read_meta(opp_dir / "meta.toml")

    if not force:
        try:
            require_transition(opp.status, next_status, verb="log")
        except InvalidTransitionError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

    corr_dir = opp_dir / "correspondence"
    corr_dir.mkdir(exist_ok=True)
    corr_path = corr_dir / _correspondence_filename(today_date, channel, direction, who)
    corr_path.write_text(body.read_text())

    new_status = opp.status if next_status == "stay" else next_status

    due = date.fromisoformat(next_action_due) if next_action_due else opp.next_action_due
    action = next_action if next_action is not None else opp.next_action

    updated = replace(
        opp,
        status=new_status,
        last_activity=today_date,
        next_action=action,
        next_action_due=due,
    )
    write_meta(updated, opp_dir / "meta.toml")

    arrow = f"{opp.status} → {new_status}" if new_status != opp.status else "(no status change)"
    commit_change(
        paths.db_root,
        f"log: {opp.slug} {arrow}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"logged: {opp.slug} {arrow}")
