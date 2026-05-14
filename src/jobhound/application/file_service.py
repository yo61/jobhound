"""file_service — uniform file CRUD over a FileStore port.

The application layer of the file API. Depends ONLY on the FileStore
Protocol (in infrastructure/storage/protocols.py). The adapter chosen
at call time is what determines the backing (git local, S3, ...).

This module owns:
  - filename validation (path traversal, meta.toml protection, hidden files)
  - the 6-case write state machine (Task 4)
  - 3-way merge orchestration via git merge-file (Task 4)

Errors raised by this module are typed exceptions; the MCP and CLI
adapters translate them into protocol-appropriate responses.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from jobhound.application.revisions import Revision
from jobhound.infrastructure.storage.protocols import (
    FileEntryList,
    FileStore,
    RevisionReadable,
)

# Tools that the AI should call instead of write_file on meta.toml.
_META_USE_INSTEAD: tuple[str, ...] = (
    "set_status",
    "set_priority",
    "set_source",
    "set_location",
    "set_comp_range",
    "set_first_contact",
    "set_applied_on",
    "set_last_activity",
    "set_next_action",
    "apply_to",
    "log_interaction",
    "withdraw_from",
    "mark_ghosted",
    "accept_offer",
    "decline_offer",
    "add_tag",
    "remove_tag",
    "add_contact",
    "set_link",
    "archive_opportunity",
    "delete_opportunity",
)


# ---- Exceptions ---------------------------------------------------------


class FileServiceError(Exception):
    """Base class for file_service exceptions."""


class InvalidFilenameError(FileServiceError):
    """Filename failed validation (hidden, empty, traversal, etc.)."""

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(f"invalid filename {filename!r}: {reason}")
        self.filename = filename
        self.reason = reason


class MetaTomlProtectedError(FileServiceError):
    """Write attempted on meta.toml."""

    def __init__(self, filename: str = "meta.toml") -> None:
        super().__init__(
            f"{filename} is protected; use a structured tool instead",
        )
        self.filename = filename
        self.use_instead: tuple[str, ...] = _META_USE_INSTEAD


# ---- Validation ---------------------------------------------------------


def _validate_filename(filename: str, *, for_write: bool = True) -> None:
    """Reject meta.toml (for writes), hidden parts, empty names, and traversal.

    Path-traversal *resolution* happens at the adapter (GitLocalFileStore)
    via Path.resolve + is_relative_to. This function rejects the obvious
    bad shapes earlier.
    """
    if not filename:
        raise InvalidFilenameError(filename, "empty filename")
    parts = PurePosixPath(filename).parts
    if not parts:
        raise InvalidFilenameError(filename, "no path components")
    if for_write and (filename == "meta.toml" or filename.endswith("/meta.toml")):
        raise MetaTomlProtectedError(filename)
    for part in parts:
        if part.startswith("."):
            raise InvalidFilenameError(filename, f"hidden component: {part!r}")
        if part == "..":
            raise InvalidFilenameError(filename, "parent traversal")


# ---- WriteResult --------------------------------------------------------


@dataclass(frozen=True)
class WriteResult:
    """Successful write outcome."""

    revision: Revision
    merged: bool = False


# ---- Public read operations ---------------------------------------------


def read(
    store: FileStore,
    slug: str,
    filename: str,
) -> tuple[bytes, Revision]:
    """Read a file's bytes and current revision.

    Raises FileNotFoundError if the file does not exist.
    """
    _validate_filename(filename, for_write=False)
    content = store.read(slug, filename)
    revision = store.compute_revision(slug, filename)
    return content, revision


def list_(store: FileStore, slug: str) -> FileEntryList:
    """List non-hidden, non-meta.toml files under the opp dir."""
    return store.list(slug)


# ---- Write exceptions ---------------------------------------------------


class FileExistsConflictError(FileServiceError):
    """Case 2: file exists, no overwrite intent."""

    def __init__(self, filename: str, current_revision: Revision) -> None:
        super().__init__(f"file exists: {filename}")
        self.filename = filename
        self.current_revision = current_revision


class FileDisappearedError(FileServiceError):
    """Case 4: file the AI was editing no longer exists."""

    def __init__(self, filename: str, base_revision: Revision) -> None:
        super().__init__(f"file disappeared while editing: {filename}")
        self.filename = filename
        self.base_revision = base_revision


class TextConflictError(FileServiceError):
    """Case 6, text path: 3-way merge failed."""

    def __init__(
        self,
        filename: str,
        base_revision: Revision,
        theirs_revision: Revision,
        conflict_markers: str,
    ) -> None:
        super().__init__(f"text merge conflict on {filename}")
        self.filename = filename
        self.base_revision = base_revision
        self.theirs_revision = theirs_revision
        self.conflict_markers = conflict_markers


class BinaryConflictError(FileServiceError):
    """Case 6, binary path: divergent binary file, no merge possible."""

    def __init__(
        self,
        filename: str,
        base_revision: Revision,
        current_revision: Revision,
        current_size: int,
        current_mtime: datetime,
        suggested_alt_name: str,
    ) -> None:
        super().__init__(f"binary conflict on {filename}")
        self.filename = filename
        self.base_revision = base_revision
        self.current_revision = current_revision
        self.current_size = current_size
        self.current_mtime = current_mtime
        self.suggested_alt_name = suggested_alt_name


class BaseRevisionUnrecoverableError(FileServiceError):
    """Base revision bytes cannot be retrieved from the store.

    Raised when the store does not implement RevisionReadable, or when
    read_by_revision raises KeyError / FileNotFoundError (revision evicted
    or never stored). Callers should report that a merge could not be
    attempted rather than silently treating current == base.
    """

    def __init__(self, filename: str, base_revision: Revision) -> None:
        super().__init__(
            f"base revision {base_revision[:8]!r} for {filename!r} is unrecoverable;"
            " merge cannot be attempted"
        )
        self.filename = filename
        self.base_revision = base_revision


# ---- Write helpers ------------------------------------------------------


def _suggest_alt_name(filename: str) -> str:
    """E.g. 'cv.pdf' → 'cv-ai-draft.pdf'."""
    path = PurePosixPath(filename)
    return str(path.with_stem(f"{path.stem}-ai-draft"))


def _is_text(content: bytes) -> bool:
    """Heuristic: null bytes → binary (mirrors git's own test).

    Checks the first 8 KB, consistent with git's binary sniff window.
    """
    sniff = content[:8192]
    if b"\x00" in sniff:
        return False
    try:
        sniff.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _three_way_merge(base: bytes, ours: bytes, theirs: bytes) -> tuple[bytes, bool]:
    """Run `git merge-file --stdout` on the three sides.

    Returns (merged_content, clean_bool). On non-clean merges, merged_content
    contains conflict markers and clean_bool is False.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        base_p = tmpdir / "base"
        ours_p = tmpdir / "ours"
        theirs_p = tmpdir / "theirs"
        base_p.write_bytes(base)
        ours_p.write_bytes(ours)
        theirs_p.write_bytes(theirs)
        result = subprocess.run(
            ["git", "merge-file", "--stdout", str(ours_p), str(base_p), str(theirs_p)],
            capture_output=True,
        )
        return result.stdout, result.returncode == 0


def _resolve_base_content(
    store: FileStore,
    base_revision: Revision,
    filename: str,
) -> bytes:
    """Reconstruct the bytes at `base_revision`.

    Raises BaseRevisionUnrecoverableError when the store does not implement
    RevisionReadable, or when read_by_revision raises KeyError /
    FileNotFoundError (revision unknown or evicted).
    """
    if not isinstance(store, RevisionReadable):
        raise BaseRevisionUnrecoverableError(filename, base_revision)
    try:
        return store.read_by_revision(base_revision)
    except (KeyError, FileNotFoundError) as exc:
        raise BaseRevisionUnrecoverableError(filename, base_revision) from exc


# ---- Public write operation ---------------------------------------------


def write(
    store: FileStore,
    slug: str,
    filename: str,
    content: bytes,
    *,
    base_revision: Revision | None = None,
    overwrite: bool = False,
) -> WriteResult:
    """Write a file with optimistic-concurrency conflict detection.

    Implements the six-case decision matrix from the spec.
    """
    _validate_filename(filename, for_write=True)
    commit_msg = f"file: write {slug}/{filename}"

    file_exists = store.exists(slug, filename)

    if base_revision is None:
        if not file_exists:
            # Case 1: clean create
            store.write(slug, filename, content, commit_message=commit_msg)
            return WriteResult(
                revision=store.compute_revision(slug, filename),
                merged=False,
            )
        if not overwrite:
            # Case 2: refuse — file exists but caller didn't declare overwrite intent
            raise FileExistsConflictError(
                filename,
                store.compute_revision(slug, filename),
            )
        # Case 3: blind overwrite
        store.write(slug, filename, content, commit_message=commit_msg)
        return WriteResult(
            revision=store.compute_revision(slug, filename),
            merged=False,
        )

    # base_revision provided — caller is updating a file they previously read
    if not file_exists:
        # Case 4: file disappeared between read and write
        raise FileDisappearedError(filename, base_revision)

    current_revision = store.compute_revision(slug, filename)
    if current_revision == base_revision:
        # Case 5: clean edit — no concurrent modification
        store.write(slug, filename, content, commit_message=commit_msg)
        return WriteResult(
            revision=store.compute_revision(slug, filename),
            merged=False,
        )

    # Case 6: concurrent modification — branch on text vs binary
    current_content = store.read(slug, filename)
    if not _is_text(current_content):
        entries = store.list(slug)
        entry = next((e for e in entries if e.name == filename), None)
        current_size = entry.size if entry else len(current_content)
        # tz=None: fallback only; real entry always carries UTC mtime from adapter
        current_mtime = entry.mtime if entry else datetime.now(tz=None)
        raise BinaryConflictError(
            filename,
            base_revision,
            current_revision,
            current_size=current_size,
            current_mtime=current_mtime,
            suggested_alt_name=_suggest_alt_name(filename),
        )

    # Text conflict: attempt 3-way merge
    base_content = _resolve_base_content(store, base_revision, filename)
    merged, clean = _three_way_merge(base_content, content, current_content)
    if clean:
        merged_msg = (
            f"file: write {slug}/{filename}"
            f" (merged base={base_revision[:8]} theirs={current_revision[:8]})"
        )
        store.write(slug, filename, merged, commit_message=merged_msg)
        return WriteResult(
            revision=store.compute_revision(slug, filename),
            merged=True,
        )
    raise TextConflictError(
        filename,
        base_revision,
        current_revision,
        conflict_markers=merged.decode("utf-8", errors="replace"),
    )


def export(
    store: FileStore,
    slug: str,
    filename: str,
    dst_path: Path,
    *,
    overwrite: bool = False,
) -> Revision:
    """Copy a file's content to `dst_path`. Returns the revision at
    time of export (so the AI can use it as `base_revision` later).

    Auto-creates `dst_path`'s parent directory if missing.
    Raises FileExistsError if `dst_path` exists and `overwrite=False`.
    Raises FileNotFoundError if the source file doesn't exist.

    `meta.toml` is allowed (reads are unrestricted).
    """
    _validate_filename(filename, for_write=False)
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"dst_path exists: {dst_path}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    content = store.read(slug, filename)
    dst_path.write_bytes(content)
    return store.compute_revision(slug, filename)


def import_(
    store: FileStore,
    slug: str,
    filename: str,
    src_path: Path,
    *,
    base_revision: Revision | None = None,
    overwrite: bool = False,
) -> WriteResult:
    """Write a file with content read from `src_path`.

    Same six-case state machine as `write` — content source is the only
    difference. Used by MCP `import_file` (binary-safe, avoids streaming
    through the protocol) and CLI `jh file write --from <path>`.

    Raises FileNotFoundError if `src_path` does not exist or is not a
    regular file.
    """
    if not src_path.is_file():
        raise FileNotFoundError(f"src_path does not exist: {src_path}")
    content = src_path.read_bytes()
    return write(
        store,
        slug,
        filename,
        content,
        base_revision=base_revision,
        overwrite=overwrite,
    )
