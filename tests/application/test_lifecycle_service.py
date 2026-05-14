"""Tests for application/lifecycle_service.py."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from jobhound.application import lifecycle_service
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.config import Config
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository

TODAY = date(2026, 5, 14)


def _git_init(db_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(db_root)], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.email", "t@t"], check=True)


def _repo(tmp_path: Path) -> tuple[OpportunityRepository, Paths]:
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
    return OpportunityRepository(paths, Config(db_path=db_root, auto_commit=True, editor="")), paths


def _seed_prospect(repo: OpportunityRepository, slug: str = "2026-05-acme") -> Opportunity:
    opp = Opportunity(
        slug=slug,
        company="Acme",
        role="EM",
        status=Status.PROSPECT,
        priority=Priority.MEDIUM,
        source=None,
        location=None,
        comp_range=None,
        first_contact=None,
        applied_on=None,
        last_activity=None,
        next_action=None,
        next_action_due=None,
    )
    repo.create(opp, message=f"seed: {slug}")
    return opp


def test_create_returns_none_before_and_opp_dir(tmp_path: Path) -> None:
    repo, paths = _repo(tmp_path)
    opp = Opportunity(
        slug="2026-05-new",
        company="X",
        role="Y",
        status=Status.PROSPECT,
        priority=Priority.MEDIUM,
        source=None,
        location=None,
        comp_range=None,
        first_contact=None,
        applied_on=None,
        last_activity=None,
        next_action=None,
        next_action_due=None,
    )
    before, after, opp_dir = lifecycle_service.create(repo, opp)
    assert before is None
    assert after == opp
    assert opp_dir == paths.opportunities_dir / "2026-05-new"


def test_apply_to_loads_mutates_saves(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    _seed_prospect(repo)
    before, after, _ = lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="Follow up",
        next_action_due=date(2026, 5, 20),
    )
    assert before.status == Status.PROSPECT
    assert after.status == Status.APPLIED
    assert after.applied_on == date(2026, 5, 10)
    assert after.last_activity == TODAY
    assert after.next_action == "Follow up"


def test_apply_to_raises_invalid_transition_when_not_prospect(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    with pytest.raises(InvalidTransitionError):
        lifecycle_service.apply_to(
            repo,
            "acme",
            applied_on=date(2026, 5, 10),
            today=TODAY,
            next_action="x",
            next_action_due=date(2026, 5, 20),
        )


def test_log_interaction_commit_message_format(tmp_path: Path) -> None:
    """Commit message must match the CLI's existing format."""
    repo, paths = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="screen",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    msg = subprocess.run(
        ["git", "-C", str(paths.db_root), "log", "-1", "--format=%s"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert msg == "log: 2026-05-acme applied → screen"

    # Use a different `today` so the stay call has a real diff (last_activity bumps)
    # — otherwise the write is idempotent and no new commit lands.
    lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="stay",
        next_action=None,
        next_action_due=None,
        today=date(2026, 5, 15),
        force=False,
    )
    msg = subprocess.run(
        ["git", "-C", str(paths.db_root), "log", "-1", "--format=%s"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert msg == "log: 2026-05-acme (no status change)"


def test_log_interaction_advances_status(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    before, after, _ = lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="screen",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    assert before.status == Status.APPLIED
    assert after.status == Status.SCREEN


def test_log_interaction_stay_keeps_status(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    _, after, _ = lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="stay",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    assert after.status == Status.APPLIED


def test_withdraw_from_marks_withdrawn(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    _, after, _ = lifecycle_service.withdraw_from(repo, "acme", today=TODAY)
    assert after.status == Status.WITHDRAWN


def test_mark_ghosted(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    _, after, _ = lifecycle_service.mark_ghosted(repo, "acme", today=TODAY)
    assert after.status == Status.GHOSTED


def test_accept_offer(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    # advance to offer
    lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="screen",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="interview",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="offer",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    _, after, _ = lifecycle_service.accept_offer(repo, "acme", today=TODAY)
    assert after.status == Status.ACCEPTED


def test_decline_offer(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo,
        "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="screen",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="interview",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    lifecycle_service.log_interaction(
        repo,
        "acme",
        next_status="offer",
        next_action=None,
        next_action_due=None,
        today=TODAY,
        force=False,
    )
    _, after, _ = lifecycle_service.decline_offer(repo, "acme", today=TODAY)
    assert after.status == Status.DECLINED
