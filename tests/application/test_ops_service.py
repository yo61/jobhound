"""Tests for application/ops_service.py."""

from __future__ import annotations

import subprocess
from pathlib import Path

from jobhound.application import ops_service
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.config import Config
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository


def _git_init(db_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(db_root)], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.email", "t@t"], check=True)


def _seeded(tmp_path: Path) -> tuple[OpportunityRepository, Paths]:
    db_root = tmp_path / "db"
    for d in ("opportunities", "archive", "_shared"):
        (db_root / d).mkdir(parents=True)
    _git_init(db_root)
    paths = Paths(
        db_root=db_root,
        opportunities_dir=db_root / "opportunities",
        archive_dir=db_root / "archive",
        shared_dir=db_root / "_shared",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )
    repo = OpportunityRepository(paths, Config(db_path=db_root, auto_commit=True, editor=""))
    repo.create(
        Opportunity(
            slug="2026-05-acme",
            company="Acme",
            role="EM",
            status=Status.APPLIED,
            priority=Priority.MEDIUM,
            source=None,
            location=None,
            comp_range=None,
            first_contact=None,
            applied_on=None,
            last_activity=None,
            next_action=None,
            next_action_due=None,
        ),
        message="seed",
    )
    return repo, paths


def test_archive_moves_to_archive_dir(tmp_path: Path) -> None:
    repo, paths = _seeded(tmp_path)
    ops_service.archive_opportunity(repo, "acme")
    assert not (paths.opportunities_dir / "2026-05-acme").exists()
    assert (paths.archive_dir / "2026-05-acme").exists()


def test_delete_requires_confirm(tmp_path: Path) -> None:
    repo, paths = _seeded(tmp_path)
    preview = ops_service.delete_opportunity(repo, "acme", confirm=False)
    assert preview.deleted is False
    assert preview.opp_dir == paths.opportunities_dir / "2026-05-acme"
    assert (paths.opportunities_dir / "2026-05-acme").exists()


def test_delete_with_confirm_removes_dir(tmp_path: Path) -> None:
    repo, paths = _seeded(tmp_path)
    result = ops_service.delete_opportunity(repo, "acme", confirm=True)
    assert result.deleted is True
    assert not (paths.opportunities_dir / "2026-05-acme").exists()


def test_unarchive_moves_back_to_opportunities(tmp_path: Path) -> None:
    repo, paths = _seeded(tmp_path)
    ops_service.archive_opportunity(repo, "acme")
    assert (paths.archive_dir / "2026-05-acme").exists()

    _, _, new_dir = ops_service.unarchive_opportunity(repo, "acme")

    assert not (paths.archive_dir / "2026-05-acme").exists()
    assert (paths.opportunities_dir / "2026-05-acme").exists()
    assert new_dir == paths.opportunities_dir / "2026-05-acme"
