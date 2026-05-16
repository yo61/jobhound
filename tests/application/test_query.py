"""Tests for OpportunityQuery."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.application.snapshots import OpportunitySnapshot, Stats
from jobhound.domain.priority import Priority
from jobhound.domain.slug import SlugNotFoundError
from jobhound.domain.status import Status
from jobhound.infrastructure.paths import Paths
from tests.application.conftest import TODAY


def test_find_returns_snapshot(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("acme", now=TODAY)
    assert isinstance(snap, OpportunitySnapshot)
    assert snap.opportunity.slug == "2026-05-acme-em"
    assert snap.archived is False
    assert snap.path == query_paths.opportunities_dir / "2026-05-acme-em"
    assert snap.computed.is_active is True
    assert snap.computed.is_stale is False
    assert snap.computed.days_since_activity == 2


def test_find_marks_stale(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("beta", now=TODAY)
    assert snap.computed.is_stale is True
    assert snap.computed.days_since_activity == 33


def test_find_resolves_archived_opportunity(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("gamma", now=TODAY)
    assert snap.archived is True
    assert snap.path == query_paths.archive_dir / "2026-03-gamma-staff"


def test_find_raises_on_unknown_slug(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    with pytest.raises(SlugNotFoundError):
        q.find("nonexistent", now=TODAY)


def test_list_returns_all_non_archived_by_default(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(now=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert slugs == ["2026-04-beta-eng", "2026-05-acme-em"]
    assert all(s.archived is False for s in snaps)


def test_list_include_archived(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(include_archived=True), now=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert slugs == ["2026-03-gamma-staff", "2026-04-beta-eng", "2026-05-acme-em"]
    archived = {s.opportunity.slug: s.archived for s in snaps}
    assert archived == {
        "2026-03-gamma-staff": True,
        "2026-04-beta-eng": False,
        "2026-05-acme-em": False,
    }


def test_list_filter_by_status(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(statuses=frozenset({Status.APPLIED})), now=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_filter_by_priority(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(priorities=frozenset({Priority.HIGH})), now=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_filter_by_slug_substring(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(slug_substring="acme"), now=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_active_only_excludes_terminal(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(active_only=True, include_archived=True), now=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert "2026-03-gamma-staff" not in slugs


def test_list_active_only_intersects_with_statuses(query_paths: Paths) -> None:
    """active_only AND explicit statuses = intersection (per spec)."""
    q = OpportunityQuery(query_paths)
    snaps = q.list(
        Filters(active_only=True, statuses=frozenset({Status.APPLIED})),
        now=TODAY,
    )
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]
    snaps = q.list(
        Filters(
            active_only=True,
            statuses=frozenset({Status.REJECTED}),
            include_archived=True,
        ),
        now=TODAY,
    )
    assert snaps == []


def test_list_returns_sorted_by_slug(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(now=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert slugs == sorted(slugs)


def test_files_lists_top_level_and_correspondence(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    entries = q.files("acme")
    names = sorted(e.name for e in entries)
    assert names == ["correspondence/intro.md", "cv.md", "meta.toml", "notes.md"]
    for e in entries:
        assert e.size > 0
        assert e.mtime.tzinfo is not None
        # tz-aware UTC: offset matches UTC's
        assert e.mtime.utcoffset() == datetime.now(UTC).utcoffset()


def test_files_only_meta_when_dir_minimal(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    entries = q.files("beta")
    names = sorted(e.name for e in entries)
    assert names == ["meta.toml"]


def test_files_excludes_hidden_files(query_paths: Paths) -> None:
    (query_paths.opportunities_dir / "2026-05-acme-em" / ".DS_Store").write_text("noise")
    q = OpportunityQuery(query_paths)
    names = {e.name for e in q.files("acme")}
    assert ".DS_Store" not in names


def test_read_file_returns_bytes(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    data = q.read_file("acme", "notes.md")
    assert isinstance(data, bytes)
    assert data == b"notes\n"


def test_read_file_correspondence_subpath(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    data = q.read_file("acme", "correspondence/intro.md")
    assert data == b"hi\n"


def test_read_file_rejects_traversal_dotdot(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    with pytest.raises(ValueError, match="must be inside"):
        q.read_file("acme", "../../../etc/passwd")


def test_read_file_rejects_absolute_path(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    with pytest.raises(ValueError, match="must be inside"):
        q.read_file("acme", "/etc/passwd")


def test_read_file_rejects_symlink_escape(query_paths: Paths, tmp_path: Path) -> None:
    """A symlink pointing outside the opp dir is rejected even with a plain filename."""
    secret = tmp_path / "secret.txt"
    secret.write_text("nope")
    link = query_paths.opportunities_dir / "2026-05-acme-em" / "evil"
    link.symlink_to(secret)
    q = OpportunityQuery(query_paths)
    with pytest.raises(ValueError, match="must be inside"):
        q.read_file("acme", "evil")


def test_stats_funnel_includes_every_status(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    stats = q.stats()
    assert isinstance(stats, Stats)
    assert set(stats.funnel.keys()) == set(Status)
    assert stats.funnel[Status.APPLIED] == 1
    assert stats.funnel[Status.SCREEN] == 1
    assert stats.funnel[Status.REJECTED] == 0


def test_stats_sources(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    stats = q.stats()
    assert stats.sources == {"LinkedIn": 1, "Referral": 1}


def test_stats_marks_unspecified_source(query_paths: Paths) -> None:
    new_dir = query_paths.opportunities_dir / "2026-05-no-source"
    new_dir.mkdir()
    (new_dir / "meta.toml").write_text(
        'company = "X"\nrole = "Y"\nslug = "2026-05-no-source"\n'
        'status = "applied"\npriority = "medium"\n',
    )
    q = OpportunityQuery(query_paths)
    stats = q.stats()
    assert stats.sources["(unspecified)"] == 1


def test_stats_respects_filters(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    stats = q.stats(Filters(statuses=frozenset({Status.APPLIED})))
    assert stats.funnel[Status.APPLIED] == 1
    assert stats.funnel[Status.SCREEN] == 0
    assert stats.sources == {"LinkedIn": 1}


def test_stats_include_archived(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    stats = q.stats(Filters(include_archived=True))
    assert stats.funnel[Status.REJECTED] == 1
