"""Map domain exceptions to MCP error response payloads.

Returns the dict shape:
    {"error": {"code": <str>, "message": <str>, "details": {...}}}
"""

from __future__ import annotations

import re
from typing import Any

from jobhound.domain.slug import AmbiguousSlugError, SlugNotFoundError
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.meta_io import ValidationError


def tool_error_response(code: str, message: str, **details: Any) -> dict[str, Any]:
    """Build the MCP error response payload."""
    return {"error": {"code": code, "message": message, "details": details}}


def _candidates_from_ambiguous(exc: AmbiguousSlugError) -> list[str]:
    """Pull the candidate slugs out of the AmbiguousSlugError message.

    The existing slug.py formats them with `\\n  ` between each.
    """
    msg = str(exc)
    return [line.strip() for line in msg.splitlines() if line.strip().startswith("2026-")]


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
        match = re.search(r"matches '(.+?)'", str(exc))
        query = match.group(1) if match else ""
        return tool_error_response("slug_not_found", str(exc), query=query)

    if isinstance(exc, AmbiguousSlugError):
        return tool_error_response(
            "ambiguous_slug",
            str(exc).split("\n", 1)[0],
            candidates=_candidates_from_ambiguous(exc),
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
