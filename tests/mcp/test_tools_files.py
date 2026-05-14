"""Tests for mcp/tools/files.py — adapter wiring (file_service tested separately)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.files import (
    append_file,
    delete_file,
    export_file,
    import_file,
    list_files,
    read_file,
    write_file,
)


def test_list_files_returns_entries(repo: OpportunityRepository) -> None:
    # The query_paths fixture seeds acme with notes.md, cv.md, correspondence/intro.md
    payload = json.loads(list_files(repo, "acme"))
    names = sorted(e["name"] for e in payload)
    assert "notes.md" in names


def test_list_files_excludes_meta_toml(repo: OpportunityRepository) -> None:
    payload = json.loads(list_files(repo, "acme"))
    names = [e["name"] for e in payload]
    assert "meta.toml" not in names


def test_read_file_returns_revision_and_content(repo: OpportunityRepository) -> None:
    payload = json.loads(read_file(repo, "acme", "notes.md"))
    assert payload["filename"] == "notes.md"
    assert payload["content"] == "notes\n"
    assert payload["encoding"] == "utf-8"
    assert "revision" in payload
    assert "size" in payload


def test_read_file_meta_toml_allowed(repo: OpportunityRepository) -> None:
    payload = json.loads(read_file(repo, "acme", "meta.toml"))
    assert "company" in payload["content"]


def test_read_file_not_found(repo: OpportunityRepository) -> None:
    payload = json.loads(read_file(repo, "acme", "nonexistent.md"))
    assert payload["error"]["code"] == "file_not_found"


def test_write_file_clean_create(repo: OpportunityRepository) -> None:
    payload = json.loads(write_file(repo, "acme", "draft.md", "v1"))
    assert "revision" in payload
    assert payload["merged"] is False


def test_write_file_meta_toml_rejected(repo: OpportunityRepository) -> None:
    payload = json.loads(write_file(repo, "acme", "meta.toml", "x"))
    assert payload["error"]["code"] == "meta_toml_protected"


def test_write_file_invalid_filename(repo: OpportunityRepository) -> None:
    payload = json.loads(write_file(repo, "acme", ".secret", "x"))
    assert payload["error"]["code"] == "invalid_filename"


def test_write_file_exists_no_overwrite(repo: OpportunityRepository) -> None:
    write_file(repo, "acme", "draft.md", "v1")
    payload = json.loads(write_file(repo, "acme", "draft.md", "v2"))
    assert payload["error"]["code"] == "file_exists"


def test_write_file_overwrite_succeeds(repo: OpportunityRepository) -> None:
    write_file(repo, "acme", "draft.md", "v1")
    payload = json.loads(write_file(repo, "acme", "draft.md", "v2", overwrite=True))
    assert "revision" in payload


def test_append_file(repo: OpportunityRepository) -> None:
    payload = json.loads(append_file(repo, "acme", "journal.md", "first\n"))
    assert "revision" in payload
    payload2 = json.loads(append_file(repo, "acme", "journal.md", "second\n"))
    assert payload2["revision"] != payload["revision"]


def test_delete_file(repo: OpportunityRepository) -> None:
    write_file(repo, "acme", "draft.md", "x")
    payload = json.loads(delete_file(repo, "acme", "draft.md"))
    assert "revision_before_delete" in payload


def test_delete_file_not_found(repo: OpportunityRepository) -> None:
    payload = json.loads(delete_file(repo, "acme", "missing.md"))
    assert payload["error"]["code"] == "file_not_found"


def test_import_file_clean_create(repo: OpportunityRepository, tmp_path: Path) -> None:
    src = tmp_path / "draft.md"
    src.write_bytes(b"v1 from path")
    payload = json.loads(import_file(repo, "acme", "imported.md", str(src)))
    assert "revision" in payload


def test_export_file_writes_to_dst(repo: OpportunityRepository, tmp_path: Path) -> None:
    write_file(repo, "acme", "draft.md", "exportme")
    dst = tmp_path / "out.md"
    payload = json.loads(export_file(repo, "acme", "draft.md", str(dst)))
    assert "revision" in payload
    assert dst.read_text() == "exportme"


def test_read_file_binary_returns_base64(repo: OpportunityRepository, tmp_path: Path) -> None:
    src = tmp_path / "binary.bin"
    src.write_bytes(b"\x00\x01\x02\xff")
    import_file(repo, "acme", "blob.bin", str(src))
    payload = json.loads(read_file(repo, "acme", "blob.bin"))
    assert payload["encoding"] == "base64"
    assert base64.b64decode(payload["content"]) == b"\x00\x01\x02\xff"
