"""Ops: archive, delete."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.slug import resolve_slug
from jobhound.infrastructure.meta_io import read_meta
from jobhound.infrastructure.repository import OpportunityRepository


def archive_opportunity(
    repo: OpportunityRepository,
    slug: str,
) -> tuple[Opportunity, Opportunity, Path]:
    """Move opp_dir from opportunities/ to archive/. Returns (opp, opp, new_dir)."""
    opp, opp_dir = repo.find(slug)
    repo.archive(opp_dir)
    new_dir = repo.paths.archive_dir / opp_dir.name
    return opp, opp, new_dir


def unarchive_opportunity(
    repo: OpportunityRepository,
    slug: str,
) -> tuple[Opportunity, Opportunity, Path]:
    """Restore an archived opportunity. Returns (opp, opp, new_dir)."""
    opp_dir = resolve_slug(slug, repo.paths.archive_dir)
    opp = read_meta(opp_dir / "meta.toml")
    repo.unarchive(opp_dir)
    new_dir = repo.paths.opportunities_dir / opp_dir.name
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
