"""Map domain exceptions to MCP error response payloads.

Returns the dict shape:
    {"error": {"code": <str>, "message": <str>, "details": {...}}}
"""

from __future__ import annotations

from typing import Any

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
from jobhound.domain.slug import AmbiguousSlugError, SlugNotFoundError
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.meta_io import ValidationError


def tool_error_response(code: str, message: str, **details: Any) -> dict[str, Any]:
    """Build the MCP error response payload."""
    return {"error": {"code": code, "message": message, "details": details}}


def exception_to_response(
    exc: Exception,
    *,
    tool: str,
    invalid_param: tuple[str, str, list[str]] | None = None,
) -> dict[str, Any]:
    """Translate a domain exception into a structured MCP error response.

    `invalid_param`, when given, is a (param_name, bad_value, allowed_values)
    tuple — used by tools that catch ValueError from `Status(...)` etc.
    """
    if isinstance(exc, SlugNotFoundError):
        return tool_error_response("slug_not_found", str(exc), query=exc.query)

    if isinstance(exc, AmbiguousSlugError):
        return tool_error_response(
            "ambiguous_slug",
            str(exc).split("\n", 1)[0],
            candidates=list(exc.candidates),
        )

    if isinstance(exc, InvalidTransitionError):
        return tool_error_response(
            "invalid_transition",
            str(exc),
            verb=exc.verb,
            current_status=(exc.current_status.value if exc.current_status else None),
            legal_targets=sorted(s.value for s in exc.legal_targets),
        )

    if isinstance(exc, ValidationError):
        return tool_error_response("validation_error", str(exc))

    if isinstance(exc, MetaTomlProtectedError):
        return tool_error_response(
            "meta_toml_protected",
            str(exc),
            filename=exc.filename,
            use_instead=list(exc.use_instead),
        )

    if isinstance(exc, InvalidFilenameError):
        return tool_error_response(
            "invalid_filename",
            str(exc),
            filename=exc.filename,
            reason=exc.reason,
        )

    if isinstance(exc, FileExistsConflictError):
        return tool_error_response(
            "file_exists",
            str(exc),
            filename=exc.filename,
            current_revision=exc.current_revision,
        )

    if isinstance(exc, FileDisappearedError):
        return tool_error_response(
            "file_disappeared",
            str(exc),
            filename=exc.filename,
            base_revision=exc.base_revision,
        )

    if isinstance(exc, BinaryConflictError):
        return tool_error_response(
            "conflict_binary",
            str(exc),
            filename=exc.filename,
            base_revision=exc.base_revision,
            current_revision=exc.current_revision,
            current_size=exc.current_size,
            current_mtime=exc.current_mtime.isoformat(),
            suggested_alt_name=exc.suggested_alt_name,
        )

    if isinstance(exc, TextConflictError):
        return tool_error_response(
            "conflict_text",
            str(exc),
            filename=exc.filename,
            base_revision=exc.base_revision,
            theirs_revision=exc.theirs_revision,
            conflict_markers_output=exc.conflict_markers,
        )

    if isinstance(exc, DeleteStaleBaseError):
        return tool_error_response(
            "delete_stale_base",
            str(exc),
            filename=exc.filename,
            base_revision=exc.base_revision,
            current_revision=exc.current_revision,
        )

    if isinstance(exc, BaseRevisionUnrecoverableError):
        return tool_error_response(
            "base_revision_unrecoverable",
            str(exc),
            filename=exc.filename,
            base_revision=exc.base_revision,
        )

    if isinstance(exc, FileNotFoundError):
        return tool_error_response("file_not_found", str(exc))

    if isinstance(exc, FileExistsError):
        return tool_error_response("slug_already_exists", str(exc))

    if isinstance(exc, ValueError):
        if invalid_param is not None:
            name, value, allowed = invalid_param
            return tool_error_response(
                "invalid_value",
                str(exc),
                param=name,
                value=value,
                allowed=allowed,
            )
        if "must be inside" in str(exc):
            return tool_error_response("path_outside_opp_dir", str(exc))
        return tool_error_response("invalid_value", str(exc))

    # Fallback: unknown exception. Don't leak details.
    return tool_error_response(
        "internal_error",
        "an internal error occurred",
        tool=tool,
        exception=type(exc).__name__,
    )
