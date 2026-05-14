"""Tests for application/relation_service.py."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from jobhound.application import relation_service
from jobhound.domain.contact import Contact
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
            source=None,
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


def test_add_tag(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = relation_service.add_tag(repo, "acme", "remote")
    assert "remote" in after.tags


def test_add_tag_deduped_sorted(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    relation_service.add_tag(repo, "acme", "remote")
    _, after, _ = relation_service.add_tag(repo, "acme", "remote")
    assert after.tags == ("remote",)
    _, after, _ = relation_service.add_tag(repo, "acme", "fintech")
    assert after.tags == ("fintech", "remote")


def test_remove_tag(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    relation_service.add_tag(repo, "acme", "remote")
    relation_service.add_tag(repo, "acme", "fintech")
    _, after, _ = relation_service.remove_tag(repo, "acme", "remote")
    assert after.tags == ("fintech",)


def test_set_tags_batched(tmp_path: Path) -> None:
    """set_tags applies add+remove in one save with summary commit message."""
    repo = _seeded_repo(tmp_path)
    relation_service.add_tag(repo, "acme", "remote")
    relation_service.add_tag(repo, "acme", "fintech")
    _, after, _ = relation_service.set_tags(
        repo,
        "acme",
        add={"senior"},
        remove={"fintech"},
    )
    assert "senior" in after.tags
    assert "fintech" not in after.tags
    assert "remote" in after.tags


def test_add_contact_with_company_and_note(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = relation_service.add_contact(
        repo,
        "acme",
        name="Jane Doe",
        role="Recruiter",
        channel="email",
        company="Acme HR",
        note="warm intro",
    )
    c = after.contacts[0]
    assert c.name == "Jane Doe"
    assert c.company == "Acme HR"
    assert c.note == "warm intro"


def test_add_contact_appends(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = relation_service.add_contact(
        repo,
        "acme",
        name="Jane Doe",
        role="Recruiter",
        channel="email",
    )
    assert after.contacts == (Contact(name="Jane Doe", role="Recruiter", channel="email"),)
    _, after, _ = relation_service.add_contact(
        repo,
        "acme",
        name="Bob",
        role=None,
        channel=None,
    )
    assert len(after.contacts) == 2


def test_set_link_overwrites(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = relation_service.set_link(repo, "acme", name="posting", url="https://x")
    assert after.links == {"posting": "https://x"}
    _, after, _ = relation_service.set_link(repo, "acme", name="posting", url="https://y")
    assert after.links == {"posting": "https://y"}
    _, after, _ = relation_service.set_link(repo, "acme", name="careers", url="https://z")
    assert after.links == {"posting": "https://y", "careers": "https://z"}


def test_add_tag_no_commit(tmp_path: Path) -> None:
    """`no_commit=True` must not create a new git commit."""
    repo = _seeded_repo(tmp_path)
    head_before = subprocess.run(
        ["git", "-C", str(repo.paths.db_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    relation_service.add_tag(repo, "acme", "remote", no_commit=True)
    head_after = subprocess.run(
        ["git", "-C", str(repo.paths.db_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head_before == head_after
