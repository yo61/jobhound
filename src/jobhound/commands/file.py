"""`jh file` subcommand group — peer of the MCP file tools.

The CLI calls into the same `file_service` that the MCP server uses,
which is the point: the FileStore Protocol abstraction is meaningless
unless BOTH adapters route through it. With a non-FS backend (S3,
sqlite, remote git), the user couldn't `ls`/`cat`/`cp`/`rm` directly —
the CLI mediates.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import questionary
from cyclopts import App, Parameter

from jobhound.application import file_service
from jobhound.application.file_service import (
    BaseRevisionUnrecoverableError,
    BinaryConflictError,
    DeleteStaleBaseError,
    FileDisappearedError,
    FileExistsConflictError,
    InvalidFilenameError,
    MetaTomlProtectedError,
    TextConflictError,
)
from jobhound.application.revisions import Revision
from jobhound.domain.slug import resolve_slug
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

app = App(name="file", help="Manage files inside an opportunity.")


def _store_and_slug(slug_query: str) -> tuple[GitLocalFileStore, str]:
    """Resolve user's slug input + construct the store."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    canonical_dir = resolve_slug(slug_query, paths.opportunities_dir)
    return GitLocalFileStore(paths), canonical_dir.name


def _handle_error(exc: Exception) -> None:
    """Convert a file_service exception into a friendly stderr message + exit non-zero."""
    if isinstance(exc, MetaTomlProtectedError):
        tools = ", ".join(exc.use_instead[:6]) + ", ..."
        print(f"jh: meta.toml is protected; use one of: {tools}", file=sys.stderr)
    elif isinstance(exc, InvalidFilenameError):
        print(f"jh: invalid filename: {exc.reason}", file=sys.stderr)
    elif isinstance(exc, FileExistsConflictError):
        rev = exc.current_revision[:8] if exc.current_revision else "?"
        print(
            f"jh: file already exists: {exc.filename} (revision {rev}); pass --overwrite",
            file=sys.stderr,
        )
    elif isinstance(exc, FileDisappearedError):
        print(f"jh: file disappeared while editing: {exc.filename}", file=sys.stderr)
    elif isinstance(exc, BinaryConflictError):
        print(
            f"jh: binary conflict on {exc.filename}; suggested alt name: {exc.suggested_alt_name}",
            file=sys.stderr,
        )
    elif isinstance(exc, TextConflictError):
        print(f"jh: text conflict on {exc.filename}:", file=sys.stderr)
        print(exc.conflict_markers, file=sys.stderr)
    elif isinstance(exc, DeleteStaleBaseError):
        print(
            f"jh: stale base revision; current is {exc.current_revision[:8]}",
            file=sys.stderr,
        )
    elif isinstance(exc, BaseRevisionUnrecoverableError):
        print(
            f"jh: base revision {exc.base_revision[:8]} could not be reconstructed",
            file=sys.stderr,
        )
    elif isinstance(exc, FileNotFoundError):
        print(f"jh: {exc}", file=sys.stderr)
    else:
        print(f"jh: error: {exc}", file=sys.stderr)
    raise SystemExit(1)


@app.command(name="list")
def list_(slug: str, /) -> None:
    """List files inside an opportunity."""
    try:
        store, canonical = _store_and_slug(slug)
        entries = file_service.list_(store, canonical)
    except Exception as exc:
        _handle_error(exc)
        return
    for e in entries:
        print(f"  {e.name:50s}  {e.size:>8d}  {e.mtime.isoformat()}")


@app.command(name="show")
def show(
    slug: str,
    name: str,
    /,
    *,
    out: Annotated[Path | None, Parameter(name=["--out"])] = None,
    overwrite: Annotated[bool, Parameter(name=["--overwrite"], negative=())] = False,
) -> None:
    """Show a file's content. With --out <path>, export it instead."""
    try:
        store, canonical = _store_and_slug(slug)
        if out is not None:
            file_service.export(store, canonical, name, out, overwrite=overwrite)
            print(f"exported: {name} → {out}")
        else:
            content, _ = file_service.read(store, canonical, name)
            sys.stdout.buffer.write(content)
    except Exception as exc:
        _handle_error(exc)


@app.command(name="write")
def write(
    slug: str,
    name: str,
    /,
    *,
    content: Annotated[str | None, Parameter(name=["--content"])] = None,
    from_: Annotated[Path | None, Parameter(name=["--from"])] = None,
    overwrite: Annotated[bool, Parameter(name=["--overwrite"], negative=())] = False,
    base_revision: Annotated[str | None, Parameter(name=["--base-revision"])] = None,
) -> None:
    """Write a file. Provide --content <str> XOR --from <path>."""
    if (content is None) == (from_ is None):
        print("jh: provide exactly one of --content or --from", file=sys.stderr)
        raise SystemExit(2)
    rev = Revision(base_revision) if base_revision else None
    try:
        store, canonical = _store_and_slug(slug)
        if from_ is not None:
            result = file_service.import_(
                store,
                canonical,
                name,
                from_,
                base_revision=rev,
                overwrite=overwrite,
            )
        else:
            assert content is not None
            result = file_service.write(
                store,
                canonical,
                name,
                content.encode("utf-8"),
                base_revision=rev,
                overwrite=overwrite,
            )
    except Exception as exc:
        _handle_error(exc)
        return
    print(f"wrote: {name} (revision {result.revision[:8]}, merged={result.merged})")


@app.command(name="append")
def append(
    slug: str,
    name: str,
    /,
    *,
    content: Annotated[str | None, Parameter(name=["--content"])] = None,
    from_: Annotated[Path | None, Parameter(name=["--from"])] = None,
) -> None:
    """Append to a file (or create if missing). Provide --content XOR --from."""
    if (content is None) == (from_ is None):
        print("jh: provide exactly one of --content or --from", file=sys.stderr)
        raise SystemExit(2)
    if content is not None:
        payload = content.encode("utf-8")
    else:
        assert from_ is not None
        payload = from_.read_bytes()
    try:
        store, canonical = _store_and_slug(slug)
        rev = file_service.append(store, canonical, name, payload)
    except Exception as exc:
        _handle_error(exc)
        return
    print(f"appended: {name} (revision {rev[:8]})")


@app.command(name="delete")
def delete(
    slug: str,
    name: str,
    /,
    *,
    base_revision: Annotated[str | None, Parameter(name=["--base-revision"])] = None,
    yes: Annotated[bool, Parameter(name=["--yes"], negative=())] = False,
) -> None:
    """Delete a file. --yes skips the confirmation prompt."""
    if not yes and not questionary.confirm(f"Delete {slug}/{name}?", default=False).ask():
        print("aborted")
        raise SystemExit(1)
    rev = Revision(base_revision) if base_revision else None
    try:
        store, canonical = _store_and_slug(slug)
        last_rev = file_service.delete(store, canonical, name, base_revision=rev)
    except Exception as exc:
        _handle_error(exc)
        return
    print(f"deleted: {name} (was at revision {last_rev[:8]})")
