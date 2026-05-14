"""Tests for mcp/errors.py."""

from __future__ import annotations

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
