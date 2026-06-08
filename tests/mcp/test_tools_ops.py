"""Tests for mcp/tools/ops.py."""

from __future__ import annotations

import json

from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.ops import (
    add_note,
    archive_opportunity,
    delete_opportunity,
    edit_note,
    list_notes,
    read_note,
    remove_note,
    unarchive_opportunity,
)


def test_add_note_returns_note_block(repo: OpportunityRepository, mcp_paths: Paths) -> None:
    payload = json.loads(add_note(repo, slug="acme", body="hello there"))
    assert "opportunity" in payload
    assert payload["note"]["seq"] == 1
    assert payload["note"]["filename"] == "1.md"
    assert payload["note"]["title"] is None
    notes_dir = mcp_paths.opportunities_dir / "2026-05-acme-em" / "notes"
    assert (notes_dir / "1.md").exists()


def test_add_note_with_title(repo: OpportunityRepository, mcp_paths: Paths) -> None:
    payload = json.loads(add_note(repo, slug="acme", body="x", title="Charlotte Prep"))
    assert payload["note"]["filename"] == "1-charlotte-prep.md"
    assert payload["note"]["title"] == "Charlotte Prep"


def test_add_note_empty_body_returns_error(repo: OpportunityRepository) -> None:
    payload = json.loads(add_note(repo, slug="acme", body="   "))
    assert payload["error"]["code"] == "empty_body"


def test_list_notes_empty(repo: OpportunityRepository) -> None:
    payload = json.loads(list_notes(repo, slug="acme"))
    assert payload["slug"] == "acme"
    assert payload["notes"] == []


def test_list_notes_after_adds(repo: OpportunityRepository) -> None:
    add_note(repo, slug="acme", body="a")
    add_note(repo, slug="acme", body="b", title="kickoff")
    payload = json.loads(list_notes(repo, slug="acme"))
    assert [n["seq"] for n in payload["notes"]] == [1, 2]
    assert payload["notes"][1]["title"] == "kickoff"
    # list response excludes body field
    assert "body" not in payload["notes"][0]


def test_read_note_returns_body_and_revision(repo: OpportunityRepository) -> None:
    add_note(repo, slug="acme", body="hello there")
    payload = json.loads(read_note(repo, slug="acme", seq=1))
    assert payload["note"]["body"] == "hello there"
    assert payload["note"]["revision"]  # non-empty


def test_read_note_with_frontmatter(repo: OpportunityRepository) -> None:
    add_note(repo, slug="acme", body="hello")
    payload = json.loads(read_note(repo, slug="acme", seq=1, with_frontmatter=True))
    assert "+++" in payload["note"]["body"]
    assert "created" in payload["note"]["body"]


def test_read_note_missing_returns_error(repo: OpportunityRepository) -> None:
    payload = json.loads(read_note(repo, slug="acme", seq=99))
    assert payload["error"]["code"] == "note_not_found"
    assert payload["error"]["details"]["seq"] == 99


def test_edit_note_preserves_metadata(repo: OpportunityRepository) -> None:
    add_note(repo, slug="acme", body="v1", title="greeting")
    edit_note(repo, slug="acme", seq=1, body="v2")
    payload = json.loads(read_note(repo, slug="acme", seq=1))
    assert payload["note"]["title"] == "greeting"
    assert payload["note"]["body"] == "v2"


def test_edit_note_returns_note_block(repo: OpportunityRepository) -> None:
    add_note(repo, slug="acme", body="v1")
    payload = json.loads(edit_note(repo, slug="acme", seq=1, body="v2"))
    assert "opportunity" in payload
    assert payload["note"]["body"] == "v2"


def test_remove_note(repo: OpportunityRepository, mcp_paths: Paths) -> None:
    add_note(repo, slug="acme", body="x")
    payload = json.loads(remove_note(repo, slug="acme", seq=1))
    assert payload["removed_seq"] == 1


def test_remove_note_missing_returns_error(repo: OpportunityRepository) -> None:
    payload = json.loads(remove_note(repo, slug="acme", seq=42))
    assert payload["error"]["code"] == "note_not_found"


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
