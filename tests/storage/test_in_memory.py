"""Smoke tests for InMemoryFileStore — confirms it satisfies the
FileStore Protocol's behavioural contract."""

from __future__ import annotations

import pytest

from tests.storage.in_memory import InMemoryFileStore


def test_write_then_read_round_trips() -> None:
    store = InMemoryFileStore()
    store.write("acme", "cv.md", b"hello\n", commit_message="x")
    assert store.read("acme", "cv.md") == b"hello\n"


def test_exists_reflects_writes_and_deletes() -> None:
    store = InMemoryFileStore()
    assert not store.exists("acme", "cv.md")
    store.write("acme", "cv.md", b"x", commit_message="write")
    assert store.exists("acme", "cv.md")
    store.delete("acme", "cv.md", commit_message="delete")
    assert not store.exists("acme", "cv.md")


def test_append_concatenates() -> None:
    store = InMemoryFileStore()
    store.append("acme", "notes.md", b"line1\n", commit_message="a")
    store.append("acme", "notes.md", b"line2\n", commit_message="b")
    assert store.read("acme", "notes.md") == b"line1\nline2\n"


def test_revision_changes_with_content() -> None:
    store = InMemoryFileStore()
    store.write("acme", "x", b"a", commit_message="x")
    r1 = store.compute_revision("acme", "x")
    store.write("acme", "x", b"b", commit_message="x")
    r2 = store.compute_revision("acme", "x")
    assert r1 != r2


def test_revision_stable_for_identical_content() -> None:
    store = InMemoryFileStore()
    store.write("acme", "x", b"hello", commit_message="x")
    store.write("acme", "y", b"hello", commit_message="x")
    assert store.compute_revision("acme", "x") == store.compute_revision("acme", "y")


def test_read_missing_raises_file_not_found() -> None:
    store = InMemoryFileStore()
    with pytest.raises(FileNotFoundError):
        store.read("acme", "missing.md")


def test_list_sorted_and_scoped_to_slug() -> None:
    store = InMemoryFileStore()
    store.write("acme", "b.md", b"x", commit_message="x")
    store.write("acme", "a.md", b"x", commit_message="x")
    store.write("beta", "z.md", b"x", commit_message="x")
    names = [e.name for e in store.list("acme")]
    assert names == ["a.md", "b.md"]


def test_commit_log_observable() -> None:
    store = InMemoryFileStore()
    store.write("acme", "x", b"a", commit_message="msg1")
    store.append("acme", "x", b"b", commit_message="msg2")
    assert store.commit_log == ["msg1", "msg2"]
