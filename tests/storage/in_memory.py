"""InMemoryFileStore — fast deterministic FileStore for tests.

Used by application-layer tests. Proves the port abstraction is real:
if the application layer leaks any git-specific assumption, tests
running against this adapter will fail.

Not exported as production code; this lives under tests/storage/.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from jobhound.application.revisions import Revision
from jobhound.application.snapshots import FileEntry
from jobhound.infrastructure.storage.protocols import FileEntryList


class InMemoryFileStore:
    """Dict-backed FileStore. Each (slug, filename) → bytes."""

    def __init__(self) -> None:
        self._files: dict[tuple[str, str], bytes] = {}
        self._mtimes: dict[tuple[str, str], datetime] = {}
        self.commit_log: list[str] = []  # observable for tests

    def list(self, opp_slug: str) -> FileEntryList:
        out: FileEntryList = []
        for (slug, name), content in self._files.items():
            if slug != opp_slug:
                continue
            out.append(
                FileEntry(
                    name=name,
                    size=len(content),
                    mtime=self._mtimes[(slug, name)],
                )
            )
        out.sort(key=lambda e: e.name)
        return out

    def exists(self, opp_slug: str, filename: str) -> bool:
        return (opp_slug, filename) in self._files

    def read(self, opp_slug: str, filename: str) -> bytes:
        try:
            return self._files[(opp_slug, filename)]
        except KeyError:
            raise FileNotFoundError(f"{opp_slug}/{filename}") from None

    def write(
        self,
        opp_slug: str,
        filename: str,
        content: bytes,
        *,
        commit_message: str,
    ) -> None:
        self._files[(opp_slug, filename)] = content
        self._mtimes[(opp_slug, filename)] = datetime.now(UTC)
        self.commit_log.append(commit_message)

    def append(
        self,
        opp_slug: str,
        filename: str,
        content: bytes,
        *,
        commit_message: str,
    ) -> None:
        existing = self._files.get((opp_slug, filename), b"")
        self._files[(opp_slug, filename)] = existing + content
        self._mtimes[(opp_slug, filename)] = datetime.now(UTC)
        self.commit_log.append(commit_message)

    def delete(
        self,
        opp_slug: str,
        filename: str,
        *,
        commit_message: str,
    ) -> None:
        if (opp_slug, filename) not in self._files:
            raise FileNotFoundError(f"{opp_slug}/{filename}")
        del self._files[(opp_slug, filename)]
        del self._mtimes[(opp_slug, filename)]
        self.commit_log.append(commit_message)

    def compute_revision(self, opp_slug: str, filename: str) -> Revision:
        if (opp_slug, filename) not in self._files:
            raise FileNotFoundError(f"{opp_slug}/{filename}")
        content = self._files[(opp_slug, filename)]
        return Revision(hashlib.sha1(content).hexdigest())
