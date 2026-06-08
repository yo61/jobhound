"""Tests for application/notes_service.py."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.application import notes_service
from jobhound.application.notes_service import (
    EmptyBodyError,
    TitleSlugError,
)
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


def test_add_note_writes_seq_1_file(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    result = notes_service.add_note(repo, store, "acme", body="first note", now=NOW)
    assert result.seq == 1
    assert result.filename == "1.md"
    contents = (paths.opportunities_dir / "2026-05-acme" / "notes" / "1.md").read_text()
    assert "created = 2026-05-14T12:00:00Z" in contents
    assert contents.rstrip().endswith("first note")


def test_add_note_with_title_slugifies(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    result = notes_service.add_note(
        repo, store, "acme", body="hi", title="Charlotte Eyre Background", now=NOW
    )
    assert result.filename == "1-charlotte-eyre-background.md"
    notes_dir = paths.opportunities_dir / "2026-05-acme" / "notes"
    assert (notes_dir / "1-charlotte-eyre-background.md").exists()


def test_add_note_increments_notes_next_seq(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="one", now=NOW)
    _, opp_dir = repo.find("acme")
    assert (opp_dir / "notes" / "1.md").exists()
    from jobhound.infrastructure.meta_io import read_meta

    opp = read_meta(opp_dir / "meta.toml")
    assert opp.notes_next_seq == 2


def test_add_note_bumps_last_activity(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    result = notes_service.add_note(repo, store, "acme", body="x", now=NOW)
    assert result.after.last_activity == NOW


def test_add_note_rejects_empty_body(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(EmptyBodyError):
        notes_service.add_note(repo, store, "acme", body="   \n  \n", now=NOW)


def test_add_note_rejects_title_that_slugifies_empty(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(TitleSlugError):
        notes_service.add_note(repo, store, "acme", body="body", title="!!!", now=NOW)


@pytest.mark.xfail(reason="remove_note added in Task 6")
def test_add_note_seq_stable_after_delete(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="a", now=NOW)
    notes_service.add_note(repo, store, "acme", body="b", now=NOW)
    notes_service.remove_note(repo, store, "acme", 2, now=NOW)
    r = notes_service.add_note(repo, store, "acme", body="c", now=NOW)
    assert r.seq == 3  # gap at 2 stays; next is 3
