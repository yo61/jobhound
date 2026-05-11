"""Tests for OpportunityRepository — the persistence + git-commit surface."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from jobhound.config import Config
from jobhound.opportunities import Opportunity
from jobhound.paths import Paths, paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.slug import SlugNotFoundError
from jobhound.status import Status


def _make_config(tmp_path: Path) -> Config:
    return Config(db_path=tmp_path / "db", auto_commit=False, editor="")


def _make_opp(slug: str = "2026-05-acme-eng") -> Opportunity:
    return Opportunity(
        slug=slug,
        company="Acme",
        role="Engineer",
        status=Status.PROSPECT,
        priority="medium",
        source=None,
        location=None,
        comp_range=None,
        first_contact=date(2026, 5, 1),
        applied_on=None,
        last_activity=date(2026, 5, 1),
        next_action="follow up",
        next_action_due=date(2026, 5, 8),
    )


def test_create_writes_meta_and_scaffolds_artefacts(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    opp = _make_opp()
    opp_dir = repo.create(opp, message=f"new: {opp.slug}", no_commit=True)

    assert opp_dir.name == opp.slug
    assert (opp_dir / "meta.toml").is_file()
    assert (opp_dir / "notes.md").is_file()
    assert (opp_dir / "research.md").is_file()
    assert (opp_dir / "correspondence").is_dir()


def test_find_returns_opp_and_dir(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)

    opp, opp_dir = repo.find("acme")
    assert opp.company == "Acme"
    assert opp_dir.name == "2026-05-acme-eng"


def test_find_raises_when_missing(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    with pytest.raises(SlugNotFoundError):
        repo.find("nope")


def test_save_persists_changes(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    opp, opp_dir = repo.find("acme")

    updated = replace(opp, priority="high")
    repo.save(updated, opp_dir, message="priority: acme high", no_commit=True)

    reloaded, _ = repo.find("acme")
    assert reloaded.priority == "high"


def test_save_renames_dir_when_slug_changes(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    opp, opp_dir = repo.find("acme")

    renamed = replace(opp, slug="2026-05-acme-senior-eng")
    new_dir = repo.save(renamed, opp_dir, message="edit", no_commit=True)

    assert not opp_dir.exists()
    assert new_dir.name == "2026-05-acme-senior-eng"
    assert (new_dir / "meta.toml").is_file()


def test_save_rejects_rename_collision(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp("2026-05-acme-eng"), message="new", no_commit=True)
    repo.create(_make_opp("2026-05-beta-eng"), message="new", no_commit=True)
    opp, opp_dir = repo.find("acme")

    collision = replace(opp, slug="2026-05-beta-eng")
    with pytest.raises(FileExistsError):
        repo.save(collision, opp_dir, message="edit", no_commit=True)


def test_all_iterates_opportunities(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp("2026-05-acme-eng"), message="new", no_commit=True)
    repo.create(_make_opp("2026-05-beta-eng"), message="new", no_commit=True)

    slugs = sorted(o.slug for o in repo.all())
    assert slugs == ["2026-05-acme-eng", "2026-05-beta-eng"]


def test_archive_moves_dir(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    _, opp_dir = repo.find("acme")

    repo.archive(opp_dir, no_commit=True)
    assert not opp_dir.exists()
    assert (paths.archive_dir / "2026-05-acme-eng" / "meta.toml").is_file()


def test_delete_removes_dir(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    _, opp_dir = repo.find("acme")

    repo.delete(opp_dir, no_commit=True)
    assert not opp_dir.exists()


def test_create_rejects_duplicate(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)

    with pytest.raises(FileExistsError):
        repo.create(_make_opp(), message="new", no_commit=True)


def test_archive_rejects_collision(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    _, opp_dir = repo.find("acme")
    repo.archive(opp_dir, no_commit=True)

    # Re-create with the same slug, then try to archive again — target exists.
    repo.create(_make_opp(), message="new", no_commit=True)
    _, opp_dir2 = repo.find("acme")
    with pytest.raises(FileExistsError):
        repo.archive(opp_dir2, no_commit=True)


def test_all_empty_dir(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    assert list(repo.all()) == []
