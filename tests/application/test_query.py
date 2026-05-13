"""Tests for OpportunityQuery."""

from __future__ import annotations

import pytest

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.application.snapshots import OpportunitySnapshot
from jobhound.domain.priority import Priority
from jobhound.domain.slug import SlugNotFoundError
from jobhound.domain.status import Status
from jobhound.infrastructure.paths import Paths
from tests.application.conftest import TODAY


def test_find_returns_snapshot(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("acme", today=TODAY)
    assert isinstance(snap, OpportunitySnapshot)
    assert snap.opportunity.slug == "2026-05-acme-em"
    assert snap.archived is False
    assert snap.path == query_paths.opportunities_dir / "2026-05-acme-em"
    assert snap.computed.is_active is True
    assert snap.computed.is_stale is False
    assert snap.computed.days_since_activity == 2


def test_find_marks_stale(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("beta", today=TODAY)
    assert snap.computed.is_stale is True
    assert snap.computed.days_since_activity == 33


def test_find_resolves_archived_opportunity(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("gamma", today=TODAY)
    assert snap.archived is True
    assert snap.path == query_paths.archive_dir / "2026-03-gamma-staff"


def test_find_raises_on_unknown_slug(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    with pytest.raises(SlugNotFoundError):
        q.find("nonexistent", today=TODAY)


def test_list_returns_all_non_archived_by_default(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(today=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert slugs == ["2026-04-beta-eng", "2026-05-acme-em"]
    assert all(s.archived is False for s in snaps)


def test_list_include_archived(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(include_archived=True), today=TODAY)
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
    snaps = q.list(Filters(statuses=frozenset({Status.APPLIED})), today=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_filter_by_priority(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(priorities=frozenset({Priority.HIGH})), today=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_filter_by_slug_substring(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(slug_substring="acme"), today=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_active_only_excludes_terminal(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(active_only=True, include_archived=True), today=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert "2026-03-gamma-staff" not in slugs


def test_list_active_only_intersects_with_statuses(query_paths: Paths) -> None:
    """active_only AND explicit statuses = intersection (per spec)."""
    q = OpportunityQuery(query_paths)
    snaps = q.list(
        Filters(active_only=True, statuses=frozenset({Status.APPLIED})),
        today=TODAY,
    )
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]
    snaps = q.list(
        Filters(
            active_only=True,
            statuses=frozenset({Status.REJECTED}),
            include_archived=True,
        ),
        today=TODAY,
    )
    assert snaps == []


def test_list_returns_sorted_by_slug(query_paths: Paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(today=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert slugs == sorted(slugs)
