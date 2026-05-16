"""MCP file tools — route to application/file_service.

Owns 8 tools: list_files, read_file (both moved here from reads.py),
write_file, import_file, export_file, append_file, delete_file, open_file.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TYPE_CHECKING

from jobhound.application import file_service
from jobhound.application.file_launcher import open_in_default_app
from jobhound.application.revisions import Revision
from jobhound.application.serialization import file_entry_to_dict
from jobhound.domain.slug import resolve_slug
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore
from jobhound.infrastructure.storage.protocols import FileStore
from jobhound.mcp.errors import exception_to_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _store(repo: OpportunityRepository) -> FileStore:
    return GitLocalFileStore(repo.paths)


def _resolve(repo: OpportunityRepository, slug: str) -> str:
    """Resolve a fuzzy slug query to the canonical directory name."""
    opp_dir = resolve_slug(slug, repo.paths.opportunities_dir)
    return opp_dir.name


def list_files(repo: OpportunityRepository, slug: str) -> str:
    try:
        resolved = _resolve(repo, slug)
        entries = file_service.list_(_store(repo), resolved)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_files"))
    return json.dumps([file_entry_to_dict(e) for e in entries])


def read_file(repo: OpportunityRepository, slug: str, name: str) -> str:
    try:
        resolved = _resolve(repo, slug)
        content, revision = file_service.read(_store(repo), resolved, name)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="read_file"))
    try:
        text = content.decode("utf-8")
        return json.dumps(
            {
                "filename": name,
                "content": text,
                "encoding": "utf-8",
                "revision": str(revision),
                "size": len(content),
            }
        )
    except UnicodeDecodeError:
        return json.dumps(
            {
                "filename": name,
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64",
                "revision": str(revision),
                "size": len(content),
            }
        )


def write_file(
    repo: OpportunityRepository,
    slug: str,
    name: str,
    content: str,
    base_revision: str | None = None,
    overwrite: bool = False,
) -> str:
    try:
        resolved = _resolve(repo, slug)
        result = file_service.write(
            _store(repo),
            resolved,
            name,
            content.encode("utf-8"),
            base_revision=Revision(base_revision) if base_revision else None,
            overwrite=overwrite,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="write_file"))
    return json.dumps({"revision": str(result.revision), "merged": result.merged})


def import_file(
    repo: OpportunityRepository,
    slug: str,
    name: str,
    src_path: str,
    base_revision: str | None = None,
    overwrite: bool = False,
) -> str:
    try:
        resolved = _resolve(repo, slug)
        result = file_service.import_(
            _store(repo),
            resolved,
            name,
            Path(src_path),
            base_revision=Revision(base_revision) if base_revision else None,
            overwrite=overwrite,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="import_file"))
    return json.dumps({"revision": str(result.revision), "merged": result.merged})


def export_file(
    repo: OpportunityRepository,
    slug: str,
    name: str,
    dst_path: str,
    overwrite: bool = False,
) -> str:
    try:
        resolved = _resolve(repo, slug)
        revision = file_service.export(
            _store(repo),
            resolved,
            name,
            Path(dst_path),
            overwrite=overwrite,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="export_file"))
    return json.dumps({"revision": str(revision)})


def append_file(
    repo: OpportunityRepository,
    slug: str,
    name: str,
    content: str,
) -> str:
    try:
        resolved = _resolve(repo, slug)
        revision = file_service.append(
            _store(repo),
            resolved,
            name,
            content.encode("utf-8"),
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="append_file"))
    return json.dumps({"revision": str(revision)})


def delete_file(
    repo: OpportunityRepository,
    slug: str,
    name: str,
    base_revision: str | None = None,
) -> str:
    try:
        resolved = _resolve(repo, slug)
        revision = file_service.delete(
            _store(repo),
            resolved,
            name,
            base_revision=Revision(base_revision) if base_revision else None,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="delete_file"))
    return json.dumps({"revision_before_delete": str(revision)})


def open_file(repo: OpportunityRepository, slug: str, name: str) -> str:
    """Materialise a file to a temp dir and launch the user's default app for it."""
    try:
        resolved = _resolve(repo, slug)
        tmp_path = open_in_default_app(_store(repo), resolved, name)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="open_file"))
    return json.dumps({"opened": True, "filename": name, "temp_path": str(tmp_path)})


def register(app: FastMCP, repo: OpportunityRepository) -> None:
    @app.tool(
        name="list_files",
        description="List files in an opportunity.",
    )
    def _l(slug: str) -> str:
        return list_files(repo, slug)

    @app.tool(
        name="read_file",
        description="Read a file's content.",
    )
    def _r(slug: str, name: str) -> str:
        return read_file(repo, slug, name)

    @app.tool(
        name="write_file",
        description="Write content to a file.",
    )
    def _w(
        slug: str,
        name: str,
        content: str,
        base_revision: str | None = None,
        overwrite: bool = False,
    ) -> str:
        return write_file(repo, slug, name, content, base_revision, overwrite)

    @app.tool(
        name="import_file",
        description="Import a file from a local path.",
    )
    def _i(
        slug: str,
        name: str,
        src_path: str,
        base_revision: str | None = None,
        overwrite: bool = False,
    ) -> str:
        return import_file(repo, slug, name, src_path, base_revision, overwrite)

    @app.tool(
        name="export_file",
        description="Export a file to a local path.",
    )
    def _e(
        slug: str,
        name: str,
        dst_path: str,
        overwrite: bool = False,
    ) -> str:
        return export_file(repo, slug, name, dst_path, overwrite)

    @app.tool(
        name="append_file",
        description="Append content to a file.",
    )
    def _a(slug: str, name: str, content: str) -> str:
        return append_file(repo, slug, name, content)

    @app.tool(
        name="delete_file",
        description="Delete a file.",
    )
    def _d(slug: str, name: str, base_revision: str | None = None) -> str:
        return delete_file(repo, slug, name, base_revision)

    @app.tool(
        name="open_file",
        description=(
            "Open a file in the user's default app. "
            "The MCP server runs locally; the file opens on the user's actual desktop."
        ),
    )
    def _o(slug: str, name: str) -> str:
        return open_file(repo, slug=slug, name=name)
