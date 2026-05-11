"""`jh apply` — submitted application, status → applied."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import typer

from jobhound.config import load_config
from jobhound.git import commit_change, ensure_repo
from jobhound.meta_io import read_meta, write_meta
from jobhound.paths import paths_from_config
from jobhound.slug import resolve_slug
from jobhound.transitions import InvalidTransitionError, require_transition


def run(
    slug_query: str = typer.Argument(..., metavar="SLUG"),
    on: str | None = typer.Option(None, "--on", help="Date submitted (default today)."),
    next_action: str = typer.Option(..., "--next-action"),
    next_action_due: str = typer.Option(..., "--next-action-due"),
    today: str | None = typer.Option(None, "--today", hidden=True),
    no_commit: bool = typer.Option(False, "--no-commit"),
) -> None:
    """Mark the application as submitted."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)

    today_date = date.fromisoformat(today) if today else date.today()
    applied_on = date.fromisoformat(on) if on else today_date
    due = date.fromisoformat(next_action_due)

    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    opp = read_meta(opp_dir / "meta.toml")
    try:
        require_transition(opp.status, "applied", verb="apply")
    except InvalidTransitionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    updated = replace(
        opp,
        status="applied",
        applied_on=applied_on,
        last_activity=today_date,
        next_action=next_action,
        next_action_due=due,
    )
    write_meta(updated, opp_dir / "meta.toml")
    commit_change(
        paths.db_root,
        f"apply: {opp.slug}",
        enabled=cfg.auto_commit and not no_commit,
    )
    typer.echo(f"applied: {opp.slug}")
