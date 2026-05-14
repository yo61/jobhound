"""FileStore Protocol — the port between application/file_service.py and
any concrete storage backend (local git, S3, sqlite, in-memory, ...).

Every mutating method must be atomic and durable on return. Callers do
not call a separate `commit` — there is no transaction primitive.
"""

from __future__ import annotations

from typing import Protocol, TypeAlias

from jobhound.application.revisions import Revision
from jobhound.application.snapshots import FileEntry

# Module-level alias: the Protocol method `list` shadows the `list` builtin
# inside the class body, breaking static resolution of `list[FileEntry]`.
# Mirrors the same pattern in jobhound.application.query.
FileEntryList: TypeAlias = list[FileEntry]


class FileStore(Protocol):
    """Backend-agnostic file CRUD inside an opportunity directory."""

    def list(self, opp_slug: str) -> FileEntryList:
        """Return every non-hidden file under the opp's storage,
        recursive. Names relative to the opp's root."""
        ...

    def exists(self, opp_slug: str, filename: str) -> bool:
        """True iff the file exists for this opp."""
        ...

    def read(self, opp_slug: str, filename: str) -> bytes:
        """Return the raw bytes. Raises FileNotFoundError if missing."""
        ...

    def write(
        self,
        opp_slug: str,
        filename: str,
        content: bytes,
        *,
        commit_message: str,
    ) -> None:
        """Atomically replace (or create) the file with the given bytes."""
        ...

    def append(
        self,
        opp_slug: str,
        filename: str,
        content: bytes,
        *,
        commit_message: str,
    ) -> None:
        """Atomically append bytes to the file (or create if missing)."""
        ...

    def delete(
        self,
        opp_slug: str,
        filename: str,
        *,
        commit_message: str,
    ) -> None:
        """Atomically remove the file. Raises FileNotFoundError if missing."""
        ...

    def compute_revision(self, opp_slug: str, filename: str) -> Revision:
        """Return the opaque content-identity for the file as it currently
        exists. Raises FileNotFoundError if missing."""
        ...
