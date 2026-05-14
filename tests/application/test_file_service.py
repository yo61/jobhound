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


# ---- write tests (Task 4: 6-case state machine + 3-way merge) -----------

from jobhound.application.file_service import (  # noqa: E402
    BaseRevisionUnrecoverableError,
    BinaryConflictError,
    FileDisappearedError,
    FileExistsConflictError,
    TextConflictError,
    write,
)
from jobhound.application.revisions import Revision  # noqa: E402


def test_write_case1_clean_create(in_memory_store: InMemoryFileStore) -> None:
    """Case 1: no base_revision, file doesn't exist → clean create."""
    result = write(in_memory_store, "acme", "cv.md", b"v1")
    assert result.merged is False
    assert in_memory_store.read("acme", "cv.md") == b"v1"


def test_write_case2_file_exists_no_overwrite(in_memory_store: InMemoryFileStore) -> None:
    """Case 2: no base_revision, file exists, overwrite=False → conflict."""
    in_memory_store.write("acme", "cv.md", b"v1", commit_message="seed")
    with pytest.raises(FileExistsConflictError) as exc:
        write(in_memory_store, "acme", "cv.md", b"v2")
    assert exc.value.filename == "cv.md"
    assert exc.value.current_revision


def test_write_case3_blind_overwrite(in_memory_store: InMemoryFileStore) -> None:
    """Case 3: no base_revision, file exists, overwrite=True → succeeds."""
    in_memory_store.write("acme", "cv.md", b"v1", commit_message="seed")
    result = write(in_memory_store, "acme", "cv.md", b"v2", overwrite=True)
    assert result.merged is False
    assert in_memory_store.read("acme", "cv.md") == b"v2"


def test_write_case4_file_disappeared(in_memory_store: InMemoryFileStore) -> None:
    """Case 4: base_revision provided but file is gone."""
    fake_rev = Revision("deadbeef")
    with pytest.raises(FileDisappearedError) as exc:
        write(in_memory_store, "acme", "cv.md", b"v2", base_revision=fake_rev)
    assert exc.value.filename == "cv.md"
    assert exc.value.base_revision == "deadbeef"


def test_write_case5_clean_edit(in_memory_store: InMemoryFileStore) -> None:
    """Case 5: base_revision matches current disk → clean write."""
    in_memory_store.write("acme", "cv.md", b"v1", commit_message="seed")
    rev1 = in_memory_store.compute_revision("acme", "cv.md")
    result = write(in_memory_store, "acme", "cv.md", b"v2", base_revision=rev1)
    assert result.merged is False
    assert in_memory_store.read("acme", "cv.md") == b"v2"


def test_write_case6_text_merge_clean(in_memory_store: InMemoryFileStore) -> None:
    """Case 6, text path: 3-way merge resolves cleanly."""
    in_memory_store.write(
        "acme",
        "notes.md",
        b"line1\nline2\n",
        commit_message="seed",
    )
    rev1 = in_memory_store.compute_revision("acme", "notes.md")
    # "Other" change: append line3
    in_memory_store.write(
        "acme",
        "notes.md",
        b"line1\nline2\nline3\n",
        commit_message="other",
    )
    # AI's edit: prepend a heading on the base
    result = write(
        in_memory_store,
        "acme",
        "notes.md",
        b"# Notes\nline1\nline2\n",
        base_revision=rev1,
    )
    assert result.merged is True
    final = in_memory_store.read("acme", "notes.md")
    assert b"# Notes" in final
    assert b"line3" in final


def test_write_case6_text_merge_conflict(in_memory_store: InMemoryFileStore) -> None:
    """Case 6, text path: overlapping edits cause merge conflict."""
    in_memory_store.write(
        "acme",
        "notes.md",
        b"line1\nline2\n",
        commit_message="seed",
    )
    rev1 = in_memory_store.compute_revision("acme", "notes.md")
    # Both edits change line2 differently
    in_memory_store.write(
        "acme",
        "notes.md",
        b"line1\nline2-OTHER\n",
        commit_message="other",
    )
    with pytest.raises(TextConflictError) as exc:
        write(
            in_memory_store,
            "acme",
            "notes.md",
            b"line1\nline2-OURS\n",
            base_revision=rev1,
        )
    assert exc.value.filename == "notes.md"
    assert "<<<<<<<" in exc.value.conflict_markers


def test_write_case6_binary_conflict(in_memory_store: InMemoryFileStore) -> None:
    """Case 6, binary path: no merge, return BinaryConflictError."""
    in_memory_store.write(
        "acme",
        "cv.pdf",
        b"\x00\x01\x02v1",
        commit_message="seed",
    )
    rev1 = in_memory_store.compute_revision("acme", "cv.pdf")
    in_memory_store.write(
        "acme",
        "cv.pdf",
        b"\x00\x01\x02v2",
        commit_message="other",
    )
    with pytest.raises(BinaryConflictError) as exc:
        write(
            in_memory_store,
            "acme",
            "cv.pdf",
            b"\x00\x01\x02ai",
            base_revision=rev1,
        )
    assert exc.value.filename == "cv.pdf"
    assert exc.value.current_revision
    assert exc.value.suggested_alt_name == "cv-ai-draft.pdf"


def test_write_rejects_meta_toml(in_memory_store: InMemoryFileStore) -> None:
    with pytest.raises(MetaTomlProtectedError):
        write(in_memory_store, "acme", "meta.toml", b"x")


def test_write_rejects_hidden(in_memory_store: InMemoryFileStore) -> None:
    with pytest.raises(InvalidFilenameError):
        write(in_memory_store, "acme", ".DS_Store", b"x")


def test_write_returns_revision_on_success(in_memory_store: InMemoryFileStore) -> None:
    result = write(in_memory_store, "acme", "cv.md", b"v1")
    expected = in_memory_store.compute_revision("acme", "cv.md")
    assert result.revision == expected


def test_write_commit_message_format(in_memory_store: InMemoryFileStore) -> None:
    """Verify the file_service uses a consistent commit-message shape."""
    write(in_memory_store, "acme", "cv.md", b"v1")
    assert in_memory_store.commit_log == ["file: write acme/cv.md"]


def test_write_merged_commit_message_includes_shas(
    in_memory_store: InMemoryFileStore,
) -> None:
    """Issue 1: merged write uses a distinct commit message with short SHAs."""
    in_memory_store.write("acme", "notes.md", b"line1\nline2\n", commit_message="seed")
    rev1 = in_memory_store.compute_revision("acme", "notes.md")
    # Concurrent write — changes a different region so merge is clean
    in_memory_store.write("acme", "notes.md", b"line1\nline2\nline3\n", commit_message="other")
    current_rev = in_memory_store.compute_revision("acme", "notes.md")
    write(
        in_memory_store,
        "acme",
        "notes.md",
        b"# Notes\nline1\nline2\n",
        base_revision=rev1,
    )
    merged_commit = in_memory_store.commit_log[-1]
    assert "(merged base=" in merged_commit
    assert rev1[:8] in merged_commit
    assert current_rev[:8] in merged_commit


def test_write_base_revision_unrecoverable(
    in_memory_store: InMemoryFileStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue 2+3: when read_by_revision fails, BaseRevisionUnrecoverableError is raised."""
    in_memory_store.write("acme", "notes.md", b"line1\nline2\n", commit_message="seed")
    rev1 = in_memory_store.compute_revision("acme", "notes.md")
    # Concurrent write into a different region so it would merge cleanly
    # — but we want to confirm the error path fires before any merge attempt.
    in_memory_store.write("acme", "notes.md", b"line1\nline2\nline3\n", commit_message="other")

    def _raise(_rev: object) -> bytes:
        raise KeyError("revision evicted")

    monkeypatch.setattr(in_memory_store, "read_by_revision", _raise)
    with pytest.raises(BaseRevisionUnrecoverableError) as exc:
        write(
            in_memory_store,
            "acme",
            "notes.md",
            b"# Notes\nline1\nline2\n",
            base_revision=rev1,
        )
    assert exc.value.filename == "notes.md"
    assert exc.value.base_revision == rev1
