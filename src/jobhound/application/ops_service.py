"""Ops: notes, archive, delete, git sync.

Each function (except delete and sync) accepts `no_commit: bool = False`
(keyword-only) for symmetry with the other write services.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jobhound.domain.opportunities import Opportunity
from jobhound.infrastructure.repository import OpportunityRepository


def add_note(
    repo: OpportunityRepository,
    slug: str,
    *,
    msg: str,
    today: date,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    """Append `- <today> <msg>` to notes.md and bump last_activity.

    Returns (before, after, opp_dir). `before` is the loaded opp; `after`
    is the touched opp (last_activity updated to `today`). The CLI and
    MCP tool share this contract — same notes format, same
    last_activity behavior.
    """
    before, opp_dir = repo.find(slug)
    notes_path = opp_dir / "notes.md"
    existing = notes_path.read_text() if notes_path.exists() else ""
    notes_path.write_text(existing + f"- {today.isoformat()} {msg}\n")
    after = before.touch(today=today)
    repo.save(after, opp_dir, message=f"note: {after.slug}", no_commit=no_commit)
    return before, after, opp_dir


def archive_opportunity(
    repo: OpportunityRepository,
    slug: str,
    *,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    """Move opp_dir from opportunities/ to archive/. Returns (opp, opp, new_dir)."""
    opp, opp_dir = repo.find(slug)
    repo.archive(opp_dir, no_commit=no_commit)
    new_dir = repo.paths.archive_dir / opp_dir.name
    return opp, opp, new_dir


@dataclass(frozen=True)
class DeleteResult:
    """Result of delete_opportunity. `deleted=False` is a preview, no side effects."""

    deleted: bool
    opportunity: Opportunity
    opp_dir: Path
    files: list[str]


def delete_opportunity(
    repo: OpportunityRepository,
    slug: str,
    *,
    confirm: bool,
    no_commit: bool = False,
) -> DeleteResult:
    """Return a preview when confirm=False; delete and commit when confirm=True."""
    opp, opp_dir = repo.find(slug)
    file_list = sorted(p.relative_to(opp_dir).as_posix() for p in opp_dir.rglob("*") if p.is_file())
    if not confirm:
        return DeleteResult(deleted=False, opportunity=opp, opp_dir=opp_dir, files=file_list)
    repo.delete(opp_dir, no_commit=no_commit)
    return DeleteResult(deleted=True, opportunity=opp, opp_dir=opp_dir, files=file_list)


def sync_data(repo: OpportunityRepository, *, direction: str) -> None:
    """Run `git pull`, `git push`, or both on the data root."""
    db = repo.paths.db_root
    if direction in {"pull", "both"}:
        subprocess.run(["git", "-C", str(db), "pull"], check=True)
    if direction in {"push", "both"}:
        subprocess.run(["git", "-C", str(db), "push"], check=True)
