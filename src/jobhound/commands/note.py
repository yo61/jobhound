"""`jh note` subgroup — manage notes on an opportunity."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from jobhound.application import frontmatter, notes_service
from jobhound.application.frontmatter import Document, Frontmatter
from jobhound.application.notes_service import (
    EmptyBodyError,
    NoteFilenameError,
    NoteNotFoundError,
    TitleSlugError,
)
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

app = App(name="note", help="Manage notes on an opportunity.")


def _repo_and_store() -> tuple[OpportunityRepository, GitLocalFileStore]:
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    return repo, GitLocalFileStore(repo.paths)


def _resolve_body(body: str | None, from_: str | None) -> str:
    if body is not None and from_ is not None:
        print("error: cannot use both positional BODY and --from", file=sys.stderr)
        raise SystemExit(1)
    if body is not None:
        return body
    if from_ is None:
        print("error: must provide either positional BODY or --from PATH|-", file=sys.stderr)
        raise SystemExit(1)
    if from_ == "-":
        return sys.stdin.read()
    return Path(from_).read_text()


def _handle_error(exc: Exception, *, verb: str) -> None:
    if isinstance(exc, (NoteNotFoundError, EmptyBodyError, NoteFilenameError, TitleSlugError)):
        print(f"{verb}: {exc}", file=sys.stderr)
    else:
        print(f"{verb}: error: {exc}", file=sys.stderr)
    raise SystemExit(1)


@app.command(name="add")
def add(
    slug_query: str,
    body: str | None = None,
    /,
    *,
    title: Annotated[str | None, Parameter(name=["--title"])] = None,
    from_: Annotated[str | None, Parameter(name=["--from"])] = None,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Write a new note. BODY is positional; use --from PATH|- to read instead."""
    body_text = _resolve_body(body, from_)
    repo, store = _repo_and_store()
    now_obj = to_utc(now) if now else now_utc()
    try:
        result = notes_service.add_note(
            repo, store, slug_query, body=body_text, title=title, now=now_obj
        )
    except Exception as exc:
        _handle_error(exc, verb="add")
        return
    suffix = f" ({title})" if title else ""
    print(f"noted: {result.after.slug} #{result.seq}{suffix}")


@app.command(name="list")
def list_(
    slug_query: str,
    /,
    *,
    reverse: Annotated[bool, Parameter(name=["--reverse"], negative=())] = False,
) -> None:
    """List notes on an opportunity."""
    repo, store = _repo_and_store()
    try:
        notes = notes_service.list_notes(repo, store, slug_query)
    except Exception as exc:
        _handle_error(exc, verb="list")
        return
    if not notes:
        print("(no notes)", file=sys.stderr)
        return
    if reverse:
        notes = list(reversed(notes))
    print(f"{'#':>4}  {'CREATED':<20}  TITLE")
    for n in notes:
        title = n.title if n.title else "—"
        created = n.created.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"{n.seq:>4}  {created:<20}  {title}")


@app.command(name="show")
def show(
    slug_query: str,
    seq: int,
    /,
    *,
    with_frontmatter: Annotated[bool, Parameter(name=["--with-frontmatter"], negative=())] = False,
) -> None:
    """Print one note's body (default) or full file (--with-frontmatter)."""
    repo, store = _repo_and_store()
    try:
        note = notes_service.read_note(repo, store, slug_query, seq)
    except Exception as exc:
        _handle_error(exc, verb="show")
        return
    if with_frontmatter:
        doc = Document(
            frontmatter=Frontmatter(created=note.created, title=note.title),
            body=note.body,
        )
        sys.stdout.write(frontmatter.serialize(doc).decode("utf-8"))
    else:
        print(note.body)


def _editor_loop(initial_body: str) -> str:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w+", delete=False, encoding="utf-8") as tf:
        tf.write(initial_body)
        path = tf.name
    try:
        result = subprocess.run([editor, path])
        if result.returncode != 0:
            print("editor exited non-zero, aborting", file=sys.stderr)
            raise SystemExit(1)
        new_body = Path(path).read_text()
    except FileNotFoundError:
        print(f"editor not found: {editor}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        Path(path).unlink(missing_ok=True)
    if new_body.strip() == initial_body.strip():
        print("note unchanged, no write", file=sys.stderr)
        raise SystemExit(1)
    return new_body


@app.command(name="edit")
def edit(
    slug_query: str,
    seq: int,
    /,
    *,
    from_: Annotated[str | None, Parameter(name=["--from"])] = None,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Rewrite a note's body. Uses --from PATH|- or opens $EDITOR."""
    repo, store = _repo_and_store()
    now_obj = to_utc(now) if now else now_utc()
    try:
        note = notes_service.read_note(repo, store, slug_query, seq)
    except Exception as exc:
        _handle_error(exc, verb="edit")
        return
    if from_ == "-":
        new_body = sys.stdin.read()
    elif from_ is not None:
        new_body = Path(from_).read_text()
    else:
        new_body = _editor_loop(note.body)
    try:
        notes_service.edit_note(repo, store, slug_query, seq, body=new_body, now=now_obj)
    except Exception as exc:
        _handle_error(exc, verb="edit")
        return
    print(f"edited: {slug_query} #{seq}")


@app.command(name="remove")
def remove(
    slug_query: str,
    seq: int,
    /,
    *,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Delete a note. Permanent — the seq stays gone."""
    repo, store = _repo_and_store()
    now_obj = to_utc(now) if now else now_utc()
    try:
        notes_service.remove_note(repo, store, slug_query, seq, now=now_obj)
    except Exception as exc:
        _handle_error(exc, verb="remove")
        return
    print(f"removed: {slug_query} #{seq}")
