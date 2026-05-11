"""`jh note` — append a timestamped one-liner to notes.md."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
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
    msg: str,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Append a timestamped one-liner to <slug>/notes.md and bump last_activity."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)
    today_date = date.fromisoformat(today) if today else date.today()

    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
    notes = opp_dir / "notes.md"
    existing = notes.read_text() if notes.exists() else ""
    line = f"- {today_date.isoformat()} {msg}\n"
    notes.write_text(existing + line)

    opp = read_meta(opp_dir / "meta.toml")
    write_meta(replace(opp, last_activity=today_date), opp_dir / "meta.toml")
    commit_change(
        paths.db_root,
        f"note: {opp.slug}",
        enabled=cfg.auto_commit and not no_commit,
    )
    print(f"noted: {opp.slug}")
