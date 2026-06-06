"""Tests for mcp/tools/ops.py."""

from __future__ import annotations

import json

from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.ops import (
    add_note,
    archive_opportunity,
    delete_opportunity,
    unarchive_opportunity,
)


def test_add_note(repo: OpportunityRepository, mcp_paths: Paths) -> None:
    payload = json.loads(add_note(repo, slug="acme", msg="follow-up Mon"))
    assert "opportunity" in payload
    notes = (mcp_paths.opportunities_dir / "2026-05-acme-em" / "notes.md").read_text()
    assert "follow-up Mon" in notes


def test_archive_moves_dir(
    repo: OpportunityRepository,
    mcp_paths: Paths,
) -> None:
    payload = json.loads(archive_opportunity(repo, slug="acme"))
    assert payload["opportunity"]["archived"] is True
    assert (mcp_paths.archive_dir / "2026-05-acme-em").exists()


def test_delete_without_confirm_is_preview(
    repo: OpportunityRepository,
    mcp_paths: Paths,
) -> None:
    payload = json.loads(delete_opportunity(repo, slug="acme", confirm=False))
    assert payload["preview"] is True
    assert "files" in payload
    assert (mcp_paths.opportunities_dir / "2026-05-acme-em").exists()


def test_delete_with_confirm_removes(
    repo: OpportunityRepository,
    mcp_paths: Paths,
) -> None:
    payload = json.loads(delete_opportunity(repo, slug="acme", confirm=True))
    assert payload["deleted"] is True
    assert not (mcp_paths.opportunities_dir / "2026-05-acme-em").exists()


def test_unarchive_round_trips_archive(
    repo: OpportunityRepository,
    mcp_paths: Paths,
) -> None:
    archive_payload = json.loads(archive_opportunity(repo, slug="acme"))
    assert archive_payload["opportunity"]["archived"] is True

    unarchive_payload = json.loads(unarchive_opportunity(repo, slug="acme"))
    assert unarchive_payload["opportunity"]["archived"] is False
    assert (mcp_paths.opportunities_dir / "2026-05-acme-em").exists()
    assert not (mcp_paths.archive_dir / "2026-05-acme-em").exists()
