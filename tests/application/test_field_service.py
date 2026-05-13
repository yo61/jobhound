"""Tests for application/field_service.py."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from jobhound.application import field_service
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.config import Config
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository

TODAY = date(2026, 5, 14)


def _git_init(db_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(db_root)], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.email", "t@t"], check=True)


def _seeded_repo(tmp_path: Path) -> OpportunityRepository:
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
            source="LinkedIn",
            location=None,
            comp_range=None,
            first_contact=None,
            applied_on=date(2026, 5, 1),
            last_activity=date(2026, 5, 10),
            next_action=None,
            next_action_due=None,
        ),
        message="seed",
    )
    return repo


def test_set_priority(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    before, after, _ = field_service.set_priority(repo, "acme", Priority.HIGH)
    assert before.priority == Priority.MEDIUM
    assert after.priority == Priority.HIGH


def test_set_company(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_company(repo, "acme", "AcmeCorp")
    assert after.company == "AcmeCorp"


def test_set_role(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_role(repo, "acme", "Staff Engineer")
    assert after.role == "Staff Engineer"


def test_set_status_bypasses_transitions(tmp_path: Path) -> None:
    """set_status writes the status directly without consulting the state machine."""
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_status(repo, "acme", Status.OFFER)
    assert after.status == Status.OFFER


def test_set_source(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_source(repo, "acme", "Referral")
    assert after.source == "Referral"
    _, after, _ = field_service.set_source(repo, "acme", None)
    assert after.source is None


def test_set_location(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_location(repo, "acme", "Remote, UK")
    assert after.location == "Remote, UK"


def test_set_comp_range(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_comp_range(repo, "acme", "£110k–£130k")  # noqa: RUF001
    assert after.comp_range == "£110k–£130k"  # noqa: RUF001


def test_set_first_contact(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_first_contact(repo, "acme", date(2026, 5, 1))
    assert after.first_contact == date(2026, 5, 1)


def test_set_applied_on(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_applied_on(repo, "acme", date(2026, 5, 2))
    assert after.applied_on == date(2026, 5, 2)


def test_set_last_activity(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_last_activity(repo, "acme", date(2026, 5, 11))
    assert after.last_activity == date(2026, 5, 11)


def test_set_next_action(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_next_action(
        repo,
        "acme",
        text="Send portfolio",
        due=date(2026, 5, 20),
    )
    assert after.next_action == "Send portfolio"
    assert after.next_action_due == date(2026, 5, 20)


def test_set_next_action_none(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = field_service.set_next_action(repo, "acme", text=None, due=None)
    assert after.next_action is None
    assert after.next_action_due is None


def test_touch_bumps_last_activity_only(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    before, after, _ = field_service.touch(repo, "acme", today=TODAY)
    assert after.last_activity == TODAY
    assert after.status == before.status
    assert after.priority == before.priority


def test_set_priority_idempotent(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    field_service.set_priority(repo, "acme", Priority.HIGH)
    before, after, _ = field_service.set_priority(repo, "acme", Priority.HIGH)
    assert before.priority == after.priority == Priority.HIGH


def test_set_priority_no_commit(tmp_path: Path) -> None:
    """`no_commit=True` must not create a new git commit."""
    repo = _seeded_repo(tmp_path)
    head_before = subprocess.run(
        ["git", "-C", str(repo.paths.db_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    field_service.set_priority(repo, "acme", Priority.HIGH, no_commit=True)
    head_after = subprocess.run(
        ["git", "-C", str(repo.paths.db_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head_before == head_after
