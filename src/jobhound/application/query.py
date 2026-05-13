"""The read-only public surface over the jh data root.

OpportunityQuery is a CQRS sibling of OpportunityRepository: same data, no
writes, no git side-effects on construction. A future HTTP daemon's read
endpoints will inject the same class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypeAlias

from jobhound.application.snapshots import ComputedFlags, FileEntry, OpportunitySnapshot
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.slug import SlugNotFoundError, resolve_slug
from jobhound.domain.status import Status
from jobhound.infrastructure.meta_io import read_meta
from jobhound.infrastructure.paths import Paths

# Module-level aliases: the public method `list` would shadow the `list` builtin
# inside the class body, breaking static type resolution of `list[X]` annotations.
SnapshotList: TypeAlias = list[OpportunitySnapshot]
FileEntryList: TypeAlias = list[FileEntry]


@dataclass(frozen=True)
class Filters:
    """Optional read-time filters. Empty/None = no filter on that dimension."""

    statuses: frozenset[Status] = field(default_factory=frozenset)
    priorities: frozenset[Priority] = field(default_factory=frozenset)
    slug_substring: str | None = None
    active_only: bool = False
    include_archived: bool = False


_NO_FILTERS = Filters()


class OpportunityQuery:
    """Read-only view over the data root. The public read surface of `jh`."""

    def __init__(self, paths: Paths) -> None:
        self._paths = paths

    def _resolve_opp_dir(self, slug: str) -> tuple[Path, bool]:
        """Find `slug` in opportunities/ first, then archive/. Returns (dir, archived)."""
        opps_dir = self._paths.opportunities_dir
        if opps_dir.exists():
            try:
                return resolve_slug(slug, opps_dir), False
            except SlugNotFoundError:
                pass
        arch_dir = self._paths.archive_dir
        if arch_dir.exists():
            return resolve_slug(slug, arch_dir), True
        raise SlugNotFoundError(f"no opportunity matches {slug!r}")

    def _snapshot(
        self,
        opp: Opportunity,
        opp_dir: Path,
        archived: bool,
        today: date,
    ) -> OpportunitySnapshot:
        flags = ComputedFlags(
            is_active=opp.is_active,
            is_stale=opp.is_stale(today),
            looks_ghosted=opp.looks_ghosted(today),
            days_since_activity=opp.days_since_activity(today),
        )
        return OpportunitySnapshot(
            opportunity=opp,
            archived=archived,
            path=opp_dir,
            computed=flags,
        )

    def _walk_root(self, root: Path, *, archived: bool, today: date) -> SnapshotList:
        if not root.exists():
            return []
        snaps: SnapshotList = []
        for sub in sorted(root.iterdir()):
            if not sub.is_dir():
                continue
            meta = sub / "meta.toml"
            if not meta.exists():
                continue
            opp = read_meta(meta)
            snaps.append(self._snapshot(opp, sub, archived, today))
        return snaps

    def _matches(self, snap: OpportunitySnapshot, filters: Filters) -> bool:
        opp = snap.opportunity
        return (
            (not filters.statuses or opp.status in filters.statuses)
            and (not filters.priorities or opp.priority in filters.priorities)
            and (not filters.active_only or opp.is_active)
            and (filters.slug_substring is None or filters.slug_substring in opp.slug)
        )

    def find(self, slug: str, *, today: date) -> OpportunitySnapshot:
        """Resolve `slug` (supports prefix/substring) and return its snapshot."""
        opp_dir, archived = self._resolve_opp_dir(slug)
        opp = read_meta(opp_dir / "meta.toml")
        return self._snapshot(opp, opp_dir, archived, today)

    def list(
        self,
        filters: Filters = _NO_FILTERS,
        *,
        today: date,
    ) -> SnapshotList:
        """Return all snapshots matching `filters`, sorted by slug."""
        snaps = self._walk_root(self._paths.opportunities_dir, archived=False, today=today)
        if filters.include_archived:
            snaps += self._walk_root(self._paths.archive_dir, archived=True, today=today)
        snaps = [s for s in snaps if self._matches(s, filters)]
        snaps.sort(key=lambda s: s.opportunity.slug)
        return snaps

    def files(self, slug: str) -> FileEntryList:
        """List every non-hidden file inside the opp dir, recursive. Names are relative."""
        opp_dir, _ = self._resolve_opp_dir(slug)
        entries: FileEntryList = []
        for path in sorted(opp_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(opp_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            stat = path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            entries.append(FileEntry(name=rel.as_posix(), size=stat.st_size, mtime=mtime))
        return entries

    def read_file(self, slug: str, filename: str) -> bytes:
        """Read the bytes of `filename` inside the opp dir. Rejects path traversal."""
        opp_dir, _ = self._resolve_opp_dir(slug)
        opp_root = opp_dir.resolve()
        target = (opp_dir / filename).resolve()
        if not target.is_relative_to(opp_root):
            raise ValueError(
                f"filename must be inside the opportunity directory: {filename}",
            )
        return target.read_bytes()
