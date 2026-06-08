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
from collections.abc import Iterator
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
    body = body.strip()
    if not body:
        raise EmptyBodyError()
    before, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    seq = before.notes_next_seq
    filename = _filename(seq, title)
    doc = Document(
        frontmatter=Frontmatter(created=now, title=title),
        body=body,
    )
    file_service.write(store, canonical, f"notes/{filename}", frontmatter.serialize(doc))
    after = before.bump(now=now).with_notes_next_seq(seq + 1)
    repo.save(after, opp_dir, message=f"note: {after.slug} #{seq}")
    return AddNoteResult(before=before, after=after, opp_dir=opp_dir, seq=seq, filename=filename)


# ---- Private helpers ----------------------------------------------------


def _iter_notes_dir(store: FileStore, canonical: str) -> Iterator[tuple[int, str]]:
    """Yield (seq, filename) for every valid note file. Raises NoteFilenameError
    if any file under `notes/` does not match the seq pattern.

    Hidden entries (starting with `.`) are skipped silently — git artifacts
    or editor lock files shouldn't break listing.
    """
    entries = store.list(canonical)
    for entry in entries:
        if "/" not in entry.name:
            continue
        head, _, name = entry.name.partition("/")
        if head != "notes":
            continue
        if name.startswith("."):
            continue
        seq = _parse_filename(name)
        if seq is None:
            raise NoteFilenameError(name, "does not match <seq>[-<slug>].md")
        yield seq, name


def list_notes(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
) -> list[NoteSummary]:
    """Enumerate notes under `<opp>/notes/`, sorted by seq ascending.

    Only frontmatter is read per note; bodies are not fetched.
    """
    _, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    out: list[NoteSummary] = []
    for seq, name in sorted(_iter_notes_dir(store, canonical), key=lambda t: t[0]):
        content, _ = file_service.read(store, canonical, f"notes/{name}")
        doc = frontmatter.parse(content)
        out.append(
            NoteSummary(
                seq=seq,
                filename=name,
                created=doc.frontmatter.created,
                title=doc.frontmatter.title,
            )
        )
    return out


def read_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    seq: int,
) -> Note:
    """Read one note's full content. Raises NoteNotFoundError if seq absent."""
    _, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    name: str | None = None
    for s, n in _iter_notes_dir(store, canonical):
        if s == seq:
            if name is not None:
                raise NoteFilenameError(n, f"multiple files with seq {seq}")
            name = n
    if name is None:
        raise NoteNotFoundError(slug, seq)
    content, revision = file_service.read(store, canonical, f"notes/{name}")
    doc = frontmatter.parse(content)
    return Note(
        seq=seq,
        filename=name,
        created=doc.frontmatter.created,
        title=doc.frontmatter.title,
        body=doc.body,
        revision=revision,
    )
