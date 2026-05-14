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

from dataclasses import dataclass
from pathlib import PurePosixPath

from jobhound.application.revisions import Revision
from jobhound.infrastructure.storage.protocols import FileEntryList, FileStore

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
