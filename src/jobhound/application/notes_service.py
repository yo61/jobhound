"""Notes use-cases over a FileStore + OpportunityRepository.

CRUD on per-note files under `<opp>/notes/<seq>[-<title-slug>].md`.
Sequence is held in `opp.notes_next_seq` (meta.toml) and never
decrements — deletes leave permanent gaps so note IDs are stable.

This module's surface is read by both the CLI (commands/note.py)
and the MCP tools (mcp/tools/ops.py). Errors are typed exceptions
that the adapters translate to protocol-specific responses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jobhound.application import file_service, frontmatter
from jobhound.application.frontmatter import Document, Frontmatter
from jobhound.application.revisions import Revision
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.slug import slugify
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.protocols import FileStore

# ---- Exceptions ---------------------------------------------------------


class NotesServiceError(Exception):
    """Base class for notes_service exceptions."""


class NoteNotFoundError(NotesServiceError):
    def __init__(self, slug: str, seq: int) -> None:
        super().__init__(f"note #{seq} not found in {slug}")
        self.slug = slug
        self.seq = seq


class NoteFilenameError(NotesServiceError):
    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(f"invalid note filename {filename!r}: {reason}")
        self.filename = filename
        self.reason = reason


class EmptyBodyError(NotesServiceError):
    def __init__(self) -> None:
        super().__init__("note body is empty")


class TitleSlugError(NotesServiceError):
    def __init__(self, title: str, reason: str) -> None:
        super().__init__(f"invalid --title {title!r}: {reason}")
        self.title = title
        self.reason = reason


# ---- Data classes -------------------------------------------------------


@dataclass(frozen=True)
class NoteSummary:
    """Metadata only — what `list_notes` returns. No body fetched."""

    seq: int
    filename: str
    created: datetime
    title: str | None


@dataclass(frozen=True)
class Note:
    """Full note — what `read_note` and `edit_note` return."""

    seq: int
    filename: str
    created: datetime
    title: str | None
    body: str
    revision: Revision


@dataclass(frozen=True)
class AddNoteResult:
    before: Opportunity
    after: Opportunity
    opp_dir: Path
    seq: int
    filename: str


# ---- Filename helpers ---------------------------------------------------


_NOTE_FILENAME = re.compile(r"^(\d+)(?:-[a-z0-9-]+)?\.md$")


def _filename(seq: int, title: str | None) -> str:
    """Construct a note's filename from seq + optional title."""
    if title is None:
        return f"{seq}.md"
    slug = slugify(title)
    if not slug:
        raise TitleSlugError(title, "slugifies to empty")
    return f"{seq}-{slug}.md"


def _parse_filename(name: str) -> int | None:
    """Extract seq from a valid note filename; return None if it doesn't match."""
    m = _NOTE_FILENAME.match(name)
    return int(m.group(1)) if m else None


# ---- Public API ---------------------------------------------------------


def add_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    *,
    body: str,
    title: str | None = None,
    now: datetime,
) -> AddNoteResult:
    """Write a new note. Returns the assigned seq and resulting filename.

    Two commits per call: one from file_service.write for the new note
    file, one from repo.save for the meta.toml update (last_activity
    bump + notes_next_seq increment).
    """
    if not body.strip():
        raise EmptyBodyError()
    before, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    seq = before.notes_next_seq
    filename = _filename(seq, title)
    doc = Document(
        frontmatter=Frontmatter(created=now, title=title),
        body=body.strip(),
    )
    file_service.write(store, canonical, f"notes/{filename}", frontmatter.serialize(doc))
    after = before.bump(now=now).with_notes_next_seq(seq + 1)
    repo.save(after, opp_dir, message=f"note: {after.slug} #{seq}")
    return AddNoteResult(before=before, after=after, opp_dir=opp_dir, seq=seq, filename=filename)
