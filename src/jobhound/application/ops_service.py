"""Ops: notes, archive, delete, git sync."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jobhound.application import file_service
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.timekeeping import _format_z_seconds
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.protocols import FileStore


def add_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    *,
    msg: str,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    """Append `- <timestamp> <msg>` to notes.md AND bump last_activity.

    Produces TWO commits: one from file_service.append (notes.md), one
    from repo.save (meta.toml last_activity bump). This is the deliberate
    trade-off — each mutation is a discrete, auditable git event.

    Returns (before, after, opp_dir).
    """
    before, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    timestamp = _format_z_seconds(now)
    line = f"- {timestamp} {msg}\n".encode()
    file_service.append(store, canonical, "notes.md", line)
    after = before.touch(now=now)
    repo.save(after, opp_dir, message=f"note: {after.slug}")
    return before, after, opp_dir


def archive_opportunity(
    repo: OpportunityRepository,
    slug: str,
) -> tuple[Opportunity, Opportunity, Path]:
    """Move opp_dir from opportunities/ to archive/. Returns (opp, opp, new_dir)."""
    opp, opp_dir = repo.find(slug)
    repo.archive(opp_dir)
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
) -> DeleteResult:
    """Return a preview when confirm=False; delete and commit when confirm=True."""
    opp, opp_dir = repo.find(slug)
    file_list = sorted(p.relative_to(opp_dir).as_posix() for p in opp_dir.rglob("*") if p.is_file())
    if not confirm:
        return DeleteResult(deleted=False, opportunity=opp, opp_dir=opp_dir, files=file_list)
    repo.delete(opp_dir)
    return DeleteResult(deleted=True, opportunity=opp, opp_dir=opp_dir, files=file_list)


def sync_data(repo: OpportunityRepository, *, direction: str) -> None:
    """Run `git pull`, `git push`, or both on the data root."""
    db = repo.paths.db_root
    if direction in {"pull", "both"}:
        subprocess.run(["git", "-C", str(db), "pull"], check=True)
    if direction in {"push", "both"}:
        subprocess.run(["git", "-C", str(db), "push"], check=True)
