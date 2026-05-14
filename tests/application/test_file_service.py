"""Tests for application/file_service.py — reads, listing, validation."""

from __future__ import annotations

import pytest

from jobhound.application import file_service
from jobhound.application.file_service import InvalidFilenameError, MetaTomlProtectedError
from tests.storage.in_memory import InMemoryFileStore


def test_read_returns_bytes_and_revision(in_memory_store: InMemoryFileStore) -> None:
    in_memory_store.write("acme", "cv.md", b"hello\n", commit_message="seed")
    content, revision = file_service.read(in_memory_store, "acme", "cv.md")
    assert content == b"hello\n"
    assert isinstance(revision, str)


def test_read_missing_raises(in_memory_store: InMemoryFileStore) -> None:
    with pytest.raises(FileNotFoundError):
        file_service.read(in_memory_store, "acme", "missing.md")


def test_list_returns_entries(in_memory_store: InMemoryFileStore) -> None:
    in_memory_store.write("acme", "cv.md", b"a", commit_message="s")
    in_memory_store.write("acme", "notes.md", b"b", commit_message="s")
    entries = file_service.list_(in_memory_store, "acme")
    names = [e.name for e in entries]
    assert names == ["cv.md", "notes.md"]


def test_validate_rejects_meta_toml() -> None:
    with pytest.raises(MetaTomlProtectedError) as exc:
        file_service._validate_filename("meta.toml")
    assert "meta.toml" in str(exc.value)
    assert hasattr(exc.value, "use_instead")
    assert exc.value.use_instead  # non-empty


def test_validate_rejects_hidden() -> None:
    with pytest.raises(InvalidFilenameError):
        file_service._validate_filename(".DS_Store")


def test_validate_rejects_subdir_hidden() -> None:
    with pytest.raises(InvalidFilenameError):
        file_service._validate_filename("correspondence/.hidden")


def test_validate_rejects_empty() -> None:
    with pytest.raises(InvalidFilenameError):
        file_service._validate_filename("")


def test_validate_allows_normal_and_subdir() -> None:
    file_service._validate_filename("cv.md")
    file_service._validate_filename("correspondence/2026-05-01-intro.md")


def test_read_allows_meta_toml(in_memory_store: InMemoryFileStore) -> None:
    """Reads of meta.toml are explicitly allowed for diagnostics."""
    in_memory_store.write("acme", "meta.toml", b'company = "x"\n', commit_message="seed")
    content, _ = file_service.read(in_memory_store, "acme", "meta.toml")
    assert b"company" in content
