"""Tests for application/notes_service.py."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.application import notes_service
from jobhound.application.notes_service import (
    EmptyBodyError,
    NoteNotFoundError,
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


def test_add_note_seq_stable_after_delete(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="a", now=NOW)
    notes_service.add_note(repo, store, "acme", body="b", now=NOW)
    notes_service.remove_note(repo, store, "acme", 2, now=NOW)
    r = notes_service.add_note(repo, store, "acme", body="c", now=NOW)
    assert r.seq == 3  # gap at 2 stays; next is 3


def test_list_notes_empty(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    assert notes_service.list_notes(repo, store, "acme") == []


def test_list_notes_sorted_ascending(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="first", now=NOW)
    notes_service.add_note(repo, store, "acme", body="second", title="kickoff", now=NOW)
    notes_service.add_note(repo, store, "acme", body="third", now=NOW)
    summaries = notes_service.list_notes(repo, store, "acme")
    assert [s.seq for s in summaries] == [1, 2, 3]
    assert summaries[1].title == "kickoff"
    assert summaries[1].filename == "2-kickoff.md"


def test_list_notes_preserves_gaps_after_manual_delete(tmp_path: Path) -> None:
    """We can't use remove_note (Task 6) — simulate by deleting a file directly."""
    repo, paths, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="a", now=NOW)
    notes_service.add_note(repo, store, "acme", body="b", now=NOW)
    notes_service.add_note(repo, store, "acme", body="c", now=NOW)
    (paths.opportunities_dir / "2026-05-acme" / "notes" / "2.md").unlink()
    summaries = notes_service.list_notes(repo, store, "acme")
    assert [s.seq for s in summaries] == [1, 3]


def test_list_notes_raises_on_corrupt_filename(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="real", now=NOW)
    # Now plant a corrupt filename next to the real one
    notes_dir = paths.opportunities_dir / "2026-05-acme" / "notes"
    (notes_dir / "garbage.md").write_text("+++\ncreated = 2026-01-01T00:00:00Z\n+++\n\nx")
    from jobhound.application.notes_service import NoteFilenameError

    with pytest.raises(NoteFilenameError):
        notes_service.list_notes(repo, store, "acme")


def test_read_note_returns_full_note(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="hello there", title="greeting", now=NOW)
    note = notes_service.read_note(repo, store, "acme", 1)
    assert note.seq == 1
    assert note.filename == "1-greeting.md"
    assert note.title == "greeting"
    assert note.body == "hello there"
    assert note.created == NOW
    assert note.revision  # any non-empty Revision


def test_read_note_raises_on_missing_seq(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(NoteNotFoundError):
        notes_service.read_note(repo, store, "acme", 42)


def test_edit_note_preserves_created_and_title(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="v1", title="greeting", now=NOW)
    later = datetime(2026, 5, 15, 9, 0, tzinfo=UTC)
    notes_service.edit_note(repo, store, "acme", 1, body="v2", now=later)
    note = notes_service.read_note(repo, store, "acme", 1)
    assert note.body == "v2"
    assert note.title == "greeting"
    assert note.created == NOW


def test_edit_note_bumps_last_activity(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="v1", now=NOW)
    later = datetime(2026, 5, 15, 9, 0, tzinfo=UTC)
    _, after, _ = notes_service.edit_note(repo, store, "acme", 1, body="v2", now=later)
    assert after.last_activity == later


def test_edit_note_raises_on_missing_seq(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(NoteNotFoundError):
        notes_service.edit_note(repo, store, "acme", 99, body="x", now=NOW)


def test_edit_note_rejects_empty_body(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="ok", now=NOW)
    with pytest.raises(EmptyBodyError):
        notes_service.edit_note(repo, store, "acme", 1, body="   ", now=NOW)


def test_remove_note_deletes_file(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="x", now=NOW)
    notes_service.remove_note(repo, store, "acme", 1, now=NOW)
    assert not (paths.opportunities_dir / "2026-05-acme" / "notes" / "1.md").exists()


def test_remove_note_raises_on_missing_seq(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(NoteNotFoundError):
        notes_service.remove_note(repo, store, "acme", 5, now=NOW)


def test_remove_note_does_not_decrement_counter(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="a", now=NOW)
    notes_service.add_note(repo, store, "acme", body="b", now=NOW)
    notes_service.remove_note(repo, store, "acme", 2, now=NOW)
    _, opp_dir = repo.find("acme")
    from jobhound.infrastructure.meta_io import read_meta

    opp = read_meta(opp_dir / "meta.toml")
    assert opp.notes_next_seq == 3  # was 3 after second add; remove does not decrement
