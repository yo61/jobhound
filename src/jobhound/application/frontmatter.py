"""TOML-frontmatter parser/serializer for per-item file streams.

Pure module: no FS, no store, no git. Bytes in, dataclass out (and
vice versa). Shared by notes (#102) and correspondence (#105).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import tomli_w

DELIMITER = b"+++"


class FrontmatterError(Exception):
    """Parse or validation failure on a frontmatter block."""


@dataclass(frozen=True)
class Frontmatter:
    """Typed view over the frontmatter table.

    `created` is mandatory and tz-aware UTC. `title` is optional.
    `extras` carries any other top-level keys verbatim (used by
    correspondence for `channel`/`direction`/`who`, and forward-
    compatible with future streams).
    """

    created: datetime
    title: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Document:
    """A parsed file: frontmatter plus the bare-markdown body."""

    frontmatter: Frontmatter
    body: str


def _format_datetime(dt: datetime) -> str:
    """Format a tz-aware datetime as a TOML-compatible UTC offset datetime string."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def serialize(doc: Document) -> bytes:
    """Render a Document to canonical bytes."""
    dt = doc.frontmatter.created
    if dt.tzinfo is None:
        raise FrontmatterError("created must be tz-aware UTC")
    if dt.utcoffset() != timedelta(0):
        raise FrontmatterError("created must be UTC")
    if dt.microsecond != 0:
        raise FrontmatterError("created must not carry microseconds")
    # Build the frontmatter lines manually for created to get `Z` suffix.
    created_line = f"created = {_format_datetime(doc.frontmatter.created)}\n".encode()
    extras: dict[str, Any] = {}
    if doc.frontmatter.title is not None:
        extras["title"] = doc.frontmatter.title
    for k, v in doc.frontmatter.extras.items():
        extras[k] = v
    extras_bytes = tomli_w.dumps(extras).encode() if extras else b""
    body = (doc.body.rstrip("\n") + "\n").encode()
    return DELIMITER + b"\n" + created_line + extras_bytes + DELIMITER + b"\n\n" + body


def parse(content: bytes) -> Document:
    """Parse canonical-shape bytes. Raises FrontmatterError on invalid input."""
    if not content:
        raise FrontmatterError("empty document")
    if not content.startswith(DELIMITER + b"\n"):
        raise FrontmatterError("missing opening +++ delimiter on line 1")
    rest = content[len(DELIMITER) + 1 :]
    end_marker = b"\n" + DELIMITER + b"\n"
    idx = rest.find(end_marker)
    if idx < 0:
        # Allow trailing +++ without newline (EOF case)
        eof_marker = b"\n" + DELIMITER
        if rest.endswith(eof_marker):
            idx = len(rest) - len(eof_marker)
            fm_raw = rest[:idx].decode("utf-8")
            body_raw = ""
        else:
            raise FrontmatterError("unclosed frontmatter: no closing +++ found")
    else:
        fm_raw = rest[:idx].decode("utf-8")
        after_marker = rest[idx + len(end_marker) :]
        # serialize() places a blank line between the closing +++ and the body;
        # strip exactly that one leading newline so body roundtrips cleanly.
        stripped = after_marker[1:] if after_marker.startswith(b"\n") else after_marker
        body_raw = stripped.decode("utf-8")
    try:
        fm_data = tomllib.loads(fm_raw)
    except tomllib.TOMLDecodeError as exc:
        raise FrontmatterError(f"invalid TOML in frontmatter: {exc}") from exc
    if "created" not in fm_data:
        raise FrontmatterError("missing required field: created")
    created = fm_data.pop("created")
    if not isinstance(created, datetime):
        raise FrontmatterError(f"created must be a TOML datetime, got: {type(created).__name__}")
    if created.tzinfo is None:
        raise FrontmatterError("created must be tz-aware UTC")
    title = fm_data.pop("title", None)
    if title is not None and not isinstance(title, str):
        raise FrontmatterError("title must be a string")
    return Document(
        frontmatter=Frontmatter(created=created, title=title, extras=fm_data),
        body=body_raw.rstrip("\n"),
    )


def parse_or_synthesize(content: bytes, fallback_created: datetime) -> Document:
    """Parse `content`; if it has no frontmatter, treat as bare markdown."""
    if content.startswith(DELIMITER + b"\n"):
        return parse(content)
    return Document(
        frontmatter=Frontmatter(created=fallback_created),
        body=content.decode("utf-8").rstrip("\n"),
    )
