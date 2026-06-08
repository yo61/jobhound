"""MCP ops tools — route to application/ops_service."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from jobhound.application import ops_service
from jobhound.application.serialization import snapshot_to_dict
from jobhound.application.snapshots import ComputedFlags, OpportunitySnapshot
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.mcp.converters import mutation_response
from jobhound.mcp.errors import exception_to_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _note_dict(note_or_summary: Any) -> dict[str, Any]:
    """Shared shape for note metadata in MCP responses (works for NoteSummary or Note)."""
    return {
        "seq": note_or_summary.seq,
        "filename": note_or_summary.filename,
        "created": note_or_summary.created.isoformat().replace("+00:00", "Z"),
        "title": note_or_summary.title,
    }


def add_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    body: str,
    title: str | None = None,
    today: str | None = None,
) -> str:
    from jobhound.application import notes_service
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    now = datetime(*(date.fromisoformat(today).timetuple()[:3]), tzinfo=UTC) if today else now_utc()
    store = GitLocalFileStore(repo.paths)
    try:
        result = notes_service.add_note(repo, store, slug, body=body, title=title, now=now)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="add_note"))
    payload = mutation_response(result.before, result.after, result.opp_dir, now=now)
    payload["note"] = {
        "seq": result.seq,
        "filename": result.filename,
        "created": result.created.isoformat().replace("+00:00", "Z"),
        "title": title,
    }
    return json.dumps(payload)


def list_notes(repo: OpportunityRepository, *, slug: str) -> str:
    from jobhound.application import notes_service
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    store = GitLocalFileStore(repo.paths)
    try:
        summaries = notes_service.list_notes(repo, store, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_notes"))
    return json.dumps(
        {
            "slug": slug,
            "notes": [_note_dict(s) for s in summaries],
        }
    )


def read_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    seq: int,
    with_frontmatter: bool = False,
) -> str:
    from jobhound.application import frontmatter as fm_module
    from jobhound.application import notes_service
    from jobhound.application.frontmatter import Document, Frontmatter
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    store = GitLocalFileStore(repo.paths)
    try:
        note = notes_service.read_note(repo, store, slug, seq)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="read_note"))
    if with_frontmatter:
        doc = Document(
            frontmatter=Frontmatter(created=note.created, title=note.title),
            body=note.body,
        )
        body_out = fm_module.serialize(doc).decode("utf-8")
    else:
        body_out = note.body
    return json.dumps(
        {
            "slug": slug,
            "note": {
                **_note_dict(note),
                "body": body_out,
                "revision": str(note.revision),
            },
        }
    )


def edit_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    seq: int,
    body: str,
    base_revision: str | None = None,
    today: str | None = None,
) -> str:
    from jobhound.application import notes_service
    from jobhound.application.revisions import Revision
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    now = datetime(*(date.fromisoformat(today).timetuple()[:3]), tzinfo=UTC) if today else now_utc()
    store = GitLocalFileStore(repo.paths)
    rev: Revision | None = Revision(base_revision) if base_revision else None
    try:
        before, after, refreshed = notes_service.edit_note(
            repo, store, slug, seq, body=body, base_revision=rev, now=now
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="edit_note"))
    _, opp_dir = repo.find(slug)
    payload = mutation_response(before, after, opp_dir, now=now)
    payload["note"] = {
        **_note_dict(refreshed),
        "body": refreshed.body,
        "revision": str(refreshed.revision),
    }
    return json.dumps(payload)


def remove_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    seq: int,
    today: str | None = None,
) -> str:
    from jobhound.application import notes_service
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    now = datetime(*(date.fromisoformat(today).timetuple()[:3]), tzinfo=UTC) if today else now_utc()
    store = GitLocalFileStore(repo.paths)
    try:
        before, after, removed_seq = notes_service.remove_note(repo, store, slug, seq, now=now)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="remove_note"))
    _, opp_dir = repo.find(slug)
    payload = mutation_response(before, after, opp_dir, now=now)
    payload["removed_seq"] = removed_seq
    return json.dumps(payload)


def archive_opportunity(repo: OpportunityRepository, *, slug: str) -> str:
    try:
        before, after, new_dir = ops_service.archive_opportunity(repo, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="archive_opportunity"))
    return json.dumps(
        mutation_response(
            before,
            after,
            new_dir,
            now=now_utc(),
            archived=True,
        )
    )


def unarchive_opportunity(repo: OpportunityRepository, *, slug: str) -> str:
    try:
        before, after, new_dir = ops_service.unarchive_opportunity(repo, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="unarchive_opportunity"))
    return json.dumps(
        mutation_response(
            before,
            after,
            new_dir,
            now=now_utc(),
            archived=False,
        )
    )


def delete_opportunity(
    repo: OpportunityRepository,
    *,
    slug: str,
    confirm: bool = False,
) -> str:
    try:
        result = ops_service.delete_opportunity(repo, slug, confirm=confirm)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="delete_opportunity"))
    now = now_utc()
    flags = ComputedFlags(
        is_active=result.opportunity.is_active,
        is_stale=result.opportunity.is_stale(now),
        looks_ghosted=result.opportunity.looks_ghosted(now),
        days_since_activity=result.opportunity.days_since_activity(now),
    )
    snap = OpportunitySnapshot(
        opportunity=result.opportunity,
        archived=False,
        path=result.opp_dir,
        computed=flags,
    )
    payload: dict[str, Any] = {
        "opportunity": snapshot_to_dict(snap),
        "files": result.files,
    }
    if result.deleted:
        payload["deleted"] = True
        payload["changed"] = None
    else:
        payload["preview"] = True
    return json.dumps(payload)


def register(app: FastMCP, repo: OpportunityRepository) -> None:
    @app.tool(
        name="add_note",
        description="Write a new note on an opportunity. Returns the assigned seq.",
    )
    def _add(slug: str, body: str, title: str | None = None, today: str | None = None) -> str:
        return add_note(repo, slug=slug, body=body, title=title, today=today)

    @app.tool(
        name="list_notes",
        description="List notes on an opportunity (metadata only, no bodies).",
    )
    def _ln(slug: str) -> str:
        return list_notes(repo, slug=slug)

    @app.tool(
        name="read_note",
        description="Read one note's body and metadata.",
    )
    def _rn(slug: str, seq: int, with_frontmatter: bool = False) -> str:
        return read_note(repo, slug=slug, seq=seq, with_frontmatter=with_frontmatter)

    @app.tool(
        name="edit_note",
        description="Rewrite a note's body. Preserves created and title.",
    )
    def _en(
        slug: str,
        seq: int,
        body: str,
        base_revision: str | None = None,
        today: str | None = None,
    ) -> str:
        return edit_note(
            repo,
            slug=slug,
            seq=seq,
            body=body,
            base_revision=base_revision,
            today=today,
        )

    @app.tool(
        name="remove_note",
        description="Delete a note. Permanent — gap stays in the seq sequence.",
    )
    def _del_note(slug: str, seq: int, today: str | None = None) -> str:
        return remove_note(repo, slug=slug, seq=seq, today=today)

    @app.tool(
        name="archive_opportunity",
        description="Archive an opportunity.",
    )
    def _a(slug: str) -> str:
        return archive_opportunity(repo, slug=slug)

    @app.tool(
        name="unarchive_opportunity",
        description="Restore an archived opportunity.",
    )
    def _u(slug: str) -> str:
        return unarchive_opportunity(repo, slug=slug)

    @app.tool(
        name="delete_opportunity",
        description=(
            "Delete an opportunity permanently. Requires confirm=True; otherwise returns a preview."
        ),
    )
    def _d(slug: str, confirm: bool = False) -> str:
        return delete_opportunity(repo, slug=slug, confirm=confirm)
