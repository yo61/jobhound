"""Tests for mcp/tools/reads.py."""

from __future__ import annotations

import json

from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.reads import (
    get_opportunity,
    get_stats,
    list_opportunities,
)


def test_list_opportunities_returns_envelope(
    mcp_paths: Paths,
    repo: OpportunityRepository,
) -> None:
    payload = json.loads(list_opportunities(repo))
    assert payload["schema_version"] == 2
    assert "timestamp" in payload
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert "2026-05-acme-em" in slugs


def test_list_opportunities_filters(
    mcp_paths: Paths,
    repo: OpportunityRepository,
) -> None:
    payload = json.loads(list_opportunities(repo, slug_substring="acme"))
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert all("acme" in s for s in slugs)


def test_get_opportunity_returns_show_envelope(
    mcp_paths: Paths,
    repo: OpportunityRepository,
) -> None:
    payload = json.loads(get_opportunity(repo, "acme"))
    assert "opportunity" in payload
    assert payload["opportunity"]["slug"] == "2026-05-acme-em"


def test_get_opportunity_unknown_slug_returns_error(
    mcp_paths: Paths,
    repo: OpportunityRepository,
) -> None:
    payload = json.loads(get_opportunity(repo, "nonexistent"))
    assert payload["error"]["code"] == "slug_not_found"


def test_get_stats(mcp_paths: Paths, repo: OpportunityRepository) -> None:
    payload = json.loads(get_stats(repo))
    assert "funnel" in payload
    assert "sources" in payload


def test_list_opportunities_returns_error_on_corrupt_meta(
    mcp_paths: Paths,
    repo: OpportunityRepository,
) -> None:
    bad = mcp_paths.opportunities_dir / "2026-05-acme-em" / "meta.toml"
    bad.write_text("this is not valid toml at all [[[")
    payload = json.loads(list_opportunities(repo))
    assert payload["error"]["code"] == "validation_error"


def test_get_stats_returns_error_on_corrupt_meta(
    mcp_paths: Paths,
    repo: OpportunityRepository,
) -> None:
    bad = mcp_paths.opportunities_dir / "2026-05-acme-em" / "meta.toml"
    bad.write_text("this is not valid toml at all [[[")
    payload = json.loads(get_stats(repo))
    assert payload["error"]["code"] == "validation_error"
