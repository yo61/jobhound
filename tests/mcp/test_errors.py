"""Tests for mcp/errors.py."""

from __future__ import annotations

from datetime import datetime, timezone

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
from jobhound.domain.slug import AmbiguousSlugError, SlugNotFoundError
from jobhound.domain.status import Status
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.meta_io import ValidationError
from jobhound.mcp.errors import exception_to_response, tool_error_response


def test_tool_error_response_shape() -> None:
    resp = tool_error_response("slug_not_found", "no match", query="acm")
    assert resp == {
        "error": {
            "code": "slug_not_found",
            "message": "no match",
            "details": {"query": "acm"},
        },
    }


def test_slug_not_found() -> None:
    exc = SlugNotFoundError("no opportunity matches 'acm'", query="acm")
    resp = exception_to_response(exc, tool="get_opportunity")
    assert resp["error"]["code"] == "slug_not_found"
    assert resp["error"]["details"]["query"] == "acm"


def test_ambiguous_slug_includes_candidates() -> None:
    exc = AmbiguousSlugError(
        "'acme' matches multiple opportunities:\n  2026-05-acme-em\n  2026-04-acme-staff",
        candidates=("2026-05-acme-em", "2026-04-acme-staff"),
    )
    resp = exception_to_response(exc, tool="get_opportunity")
    assert resp["error"]["code"] == "ambiguous_slug"
    cands = resp["error"]["details"]["candidates"]
    assert "2026-05-acme-em" in cands
    assert "2026-04-acme-staff" in cands


def test_invalid_transition_includes_legal_targets() -> None:
    exc = InvalidTransitionError(
        "cannot apply when status is 'applied'",
        verb="apply",
        current_status=Status.APPLIED,
        legal_targets=frozenset({Status.SCREEN, Status.REJECTED}),
    )
    resp = exception_to_response(exc, tool="apply_to")
    assert resp["error"]["code"] == "invalid_transition"
    targets = set(resp["error"]["details"]["legal_targets"])
    assert targets == {"screen", "rejected"}


def test_invalid_value_includes_allowed() -> None:
    resp = exception_to_response(
        ValueError("'urgent' is not a valid Priority"),
        tool="set_priority",
        invalid_param=("level", "urgent", ["high", "medium", "low"]),
    )
    assert resp["error"]["code"] == "invalid_value"
    assert resp["error"]["details"]["allowed"] == ["high", "medium", "low"]


def test_validation_error_code() -> None:
    resp = exception_to_response(
        ValidationError("missing required field: company"),
        tool="get_opportunity",
    )
    assert resp["error"]["code"] == "validation_error"


def test_path_traversal_error() -> None:
    resp = exception_to_response(
        ValueError("filename must be inside the opportunity directory: ../passwd"),
        tool="read_file",
    )
    assert resp["error"]["code"] == "path_outside_opp_dir"


def test_file_exists_error() -> None:
    resp = exception_to_response(
        FileExistsError("opportunity already exists: /tmp/foo"),
        tool="new_opportunity",
    )
    assert resp["error"]["code"] == "slug_already_exists"


def test_internal_error_for_unknown_exception() -> None:
    resp = exception_to_response(RuntimeError("kaboom"), tool="add_note")
    assert resp["error"]["code"] == "internal_error"
    assert resp["error"]["details"]["tool"] == "add_note"
    # no PII leaks
    assert "kaboom" not in resp["error"]["details"].get("message", "")


def test_meta_toml_protected_error() -> None:
    resp = exception_to_response(MetaTomlProtectedError(), tool="write_file")
    assert resp["error"]["code"] == "meta_toml_protected"
    assert "set_status" in resp["error"]["details"]["use_instead"]
    assert "apply_to" in resp["error"]["details"]["use_instead"]


def test_invalid_filename_error() -> None:
    resp = exception_to_response(
        InvalidFilenameError(".secret", "hidden component: '.secret'"),
        tool="write_file",
    )
    assert resp["error"]["code"] == "invalid_filename"
    assert resp["error"]["details"]["filename"] == ".secret"
    assert "hidden" in resp["error"]["details"]["reason"]


def test_file_exists_conflict_error() -> None:
    resp = exception_to_response(
        FileExistsConflictError("cv.md", Revision("abc123")),
        tool="write_file",
    )
    assert resp["error"]["code"] == "file_exists"
    assert resp["error"]["details"]["filename"] == "cv.md"
    assert resp["error"]["details"]["current_revision"] == "abc123"


def test_file_disappeared_error() -> None:
    resp = exception_to_response(
        FileDisappearedError("cv.md", Revision("abc123")),
        tool="write_file",
    )
    assert resp["error"]["code"] == "file_disappeared"
    assert resp["error"]["details"]["filename"] == "cv.md"
    assert resp["error"]["details"]["base_revision"] == "abc123"


def test_binary_conflict_error() -> None:
    resp = exception_to_response(
        BinaryConflictError(
            filename="cv.pdf",
            base_revision=Revision("aaa"),
            current_revision=Revision("bbb"),
            current_size=124388,
            current_mtime=datetime(2026, 5, 14, 14, 32, tzinfo=timezone.utc),  # noqa: UP017
            suggested_alt_name="cv-ai-draft.pdf",
        ),
        tool="write_file",
    )
    d = resp["error"]
    assert d["code"] == "conflict_binary"
    assert d["details"]["filename"] == "cv.pdf"
    assert d["details"]["base_revision"] == "aaa"
    assert d["details"]["current_revision"] == "bbb"
    assert d["details"]["current_size"] == 124388
    assert "2026-05-14" in d["details"]["current_mtime"]
    assert d["details"]["suggested_alt_name"] == "cv-ai-draft.pdf"


def test_text_conflict_error() -> None:
    resp = exception_to_response(
        TextConflictError(
            filename="notes.md",
            base_revision=Revision("aaa"),
            theirs_revision=Revision("bbb"),
            conflict_markers="<<<<<<< ours\nfoo\n=======\nbar\n>>>>>>> theirs\n",
        ),
        tool="write_file",
    )
    d = resp["error"]
    assert d["code"] == "conflict_text"
    assert d["details"]["filename"] == "notes.md"
    assert "<<<<<<<" in d["details"]["conflict_markers_output"]


def test_delete_stale_base_error() -> None:
    resp = exception_to_response(
        DeleteStaleBaseError("cv.md", Revision("aaa"), Revision("bbb")),
        tool="delete_file",
    )
    assert resp["error"]["code"] == "delete_stale_base"
    assert resp["error"]["details"]["base_revision"] == "aaa"
    assert resp["error"]["details"]["current_revision"] == "bbb"


def test_base_revision_unrecoverable_error() -> None:
    resp = exception_to_response(
        BaseRevisionUnrecoverableError("cv.md", Revision("aaa")),
        tool="write_file",
    )
    assert resp["error"]["code"] == "base_revision_unrecoverable"
    assert resp["error"]["details"]["filename"] == "cv.md"
    assert resp["error"]["details"]["base_revision"] == "aaa"


def test_file_not_found_error() -> None:
    resp = exception_to_response(
        FileNotFoundError("missing.md"),
        tool="read_file",
    )
    assert resp["error"]["code"] == "file_not_found"
