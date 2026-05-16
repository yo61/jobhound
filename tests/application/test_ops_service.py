"""Tests for application/ops_service.py."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.application import ops_service
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.config import Config
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

NOW = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def _git_init(db_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(db_root)], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.email", "t@t"], check=True)


def _seeded(tmp_path: Path) -> tuple[OpportunityRepository, Paths, GitLocalFileStore]:
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
    store = GitLocalFileStore(paths)
    return repo, paths, store


def test_add_note_appends_dated_entry(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    ops_service.add_note(repo, store, "acme", msg="recruiter mentioned hybrid", now=NOW)
    notes = (paths.opportunities_dir / "2026-05-acme" / "notes.md").read_text()
    assert "- 2026-05-14T12:00:00Z recruiter mentioned hybrid" in notes


def test_add_note_bumps_last_activity(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    _, after, _ = ops_service.add_note(repo, store, "acme", msg="x", now=NOW)
    assert after.last_activity == NOW


def test_archive_moves_to_archive_dir(tmp_path: Path) -> None:
    repo, paths, _ = _seeded(tmp_path)
    ops_service.archive_opportunity(repo, "acme")
    assert not (paths.opportunities_dir / "2026-05-acme").exists()
    assert (paths.archive_dir / "2026-05-acme").exists()


def test_delete_requires_confirm(tmp_path: Path) -> None:
    repo, paths, _ = _seeded(tmp_path)
    preview = ops_service.delete_opportunity(repo, "acme", confirm=False)
    assert preview.deleted is False
    assert preview.opp_dir == paths.opportunities_dir / "2026-05-acme"
    assert (paths.opportunities_dir / "2026-05-acme").exists()


def test_delete_with_confirm_removes_dir(tmp_path: Path) -> None:
    repo, paths, _ = _seeded(tmp_path)
    result = ops_service.delete_opportunity(repo, "acme", confirm=True)
    assert result.deleted is True
    assert not (paths.opportunities_dir / "2026-05-acme").exists()


def test_sync_runs_git_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the right git command was attempted — don't actually push/pull."""
    repo, _, _ = _seeded(tmp_path)
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kw: object) -> subprocess.CompletedProcess:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ops_service.sync_data(repo, direction="pull")
    assert any("pull" in c for c in calls)
