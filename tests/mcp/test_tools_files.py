"""Tests for mcp/tools/files.py — adapter wiring (file_service tested separately)."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.tools.files import (
    append_file,
    delete_file,
    export_file,
    import_file,
    list_files,
    open_file,
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


# ── open_file ────────────────────────────────────────────────────────────────


def test_open_file_darwin_returns_opened(
    repo: OpportunityRepository, monkeypatch: MagicMock
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch("jobhound.application.file_launcher.subprocess.run") as mock_run:
        payload = json.loads(open_file(repo, "acme", "notes.md"))
    assert payload["opened"] is True
    assert payload["filename"] == "notes.md"
    assert "temp_path" in payload
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "open"
    assert cmd[1].endswith("notes.md")


def test_open_file_linux_calls_xdg_open(
    repo: OpportunityRepository, monkeypatch: MagicMock
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    with patch("jobhound.application.file_launcher.subprocess.run") as mock_run:
        payload = json.loads(open_file(repo, "acme", "notes.md"))
    assert payload["opened"] is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "xdg-open"


def test_open_file_win32_calls_startfile(
    repo: OpportunityRepository, monkeypatch: MagicMock
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    mock_startfile = MagicMock()
    with patch("jobhound.application.file_launcher.os.startfile", mock_startfile, create=True):
        payload = json.loads(open_file(repo, "acme", "notes.md"))
    assert payload["opened"] is True
    assert mock_startfile.called
    assert mock_startfile.call_args[0][0].endswith("notes.md")


def test_open_file_temp_file_has_correct_content(
    repo: OpportunityRepository, monkeypatch: MagicMock
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    captured_path: list[Path] = []
    real_run = subprocess.run

    def _capture_open(cmd, **kwargs):
        # Only intercept the OS launcher call; let git calls through
        if cmd and cmd[0] == "open":
            captured_path.append(Path(cmd[1]))
            return None
        return real_run(cmd, **kwargs)

    with patch("jobhound.application.file_launcher.subprocess.run", side_effect=_capture_open):
        payload = json.loads(open_file(repo, "acme", "notes.md"))

    assert payload["opened"] is True
    assert captured_path
    tmp_path = captured_path[0]
    assert tmp_path.name == "notes.md"
    assert tmp_path.exists()
    assert tmp_path.read_bytes() == b"notes\n"


def test_open_file_not_found_returns_error(
    repo: OpportunityRepository, monkeypatch: MagicMock
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch("jobhound.application.file_launcher.subprocess.run"):
        payload = json.loads(open_file(repo, "acme", "nonexistent.md"))
    assert "error" in payload
    assert payload["error"]["code"] == "file_not_found"


def test_open_file_launcher_failure_returns_error(
    repo: OpportunityRepository, monkeypatch: MagicMock
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch(
        "jobhound.application.file_launcher.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "open"),
    ):
        payload = json.loads(open_file(repo, "acme", "notes.md"))
    assert "error" in payload
