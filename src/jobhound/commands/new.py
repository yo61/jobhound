"""`jh new` — scaffold a new opportunity at status `prospect`."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import typer

from jobhound.config import load_config
from jobhound.git import commit_change, ensure_repo
from jobhound.meta_io import write_meta
from jobhound.opportunities import Opportunity
from jobhound.paths import Paths, paths_from_config

_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_BAD.sub("-", text.lower()).strip("-")
    return s or "untitled"


def _build_slug(today: date, company: str, role: str) -> str:
    return f"{today:%Y-%m}-{_slugify(company)}-{_slugify(role)}"


def _write_skeletons(opp_dir: Path) -> None:
    (opp_dir / "notes.md").write_text("")
    (opp_dir / "research.md").write_text(
        "# Research\n\n## Company\n\n## Role\n\n## Why apply\n\n## Why not\n"
    )
    (opp_dir / "correspondence").mkdir()


def run(
    company: str = typer.Option(..., "--company", help="Company name."),
    role: str = typer.Option(..., "--role", help="Role title."),
    source: str = typer.Option("(unspecified)", "--source"),
    next_action: str = typer.Option("Initial review of role and company", "--next-action"),
    next_action_due: str | None = typer.Option(None, "--next-action-due"),
    today: str | None = typer.Option(
        None, "--today", hidden=True, help="Override today's date (testing only)."
    ),
    no_commit: bool = typer.Option(False, "--no-commit"),
) -> None:
    """Create a new opportunity at status `prospect`."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    ensure_repo(paths.db_root)

    today_date = date.fromisoformat(today) if today else date.today()
    due = date.fromisoformat(next_action_due) if next_action_due else today_date + timedelta(days=7)
    slug = _build_slug(today_date, company, role)
    opp_dir = paths.opportunities_dir / slug
    if opp_dir.exists():
        typer.echo(f"opportunity already exists: {opp_dir}", err=True)
        raise typer.Exit(code=1)
    opp_dir.mkdir(parents=True)
    _write_skeletons(opp_dir)

    opp = Opportunity(
        slug=slug,
        company=company,
        role=role,
        status="prospect",
        priority="medium",
        source=source,
        location=None,
        comp_range=None,
        first_contact=today_date,
        applied_on=None,
        last_activity=today_date,
        next_action=next_action,
        next_action_due=due,
    )
    write_meta(opp, opp_dir / "meta.toml")
    commit_change(paths.db_root, f"new: {slug}", enabled=cfg.auto_commit and not no_commit)
    typer.echo(f"Created {opp_dir.relative_to(paths.db_root)}")
