"""Slug resolution: turn user input into a real opportunity directory."""

from __future__ import annotations

from pathlib import Path


class SlugNotFoundError(Exception):
    """Raised when no opportunity matches the user's input."""

    def __init__(self, message: str, *, query: str = "") -> None:
        super().__init__(message)
        self.query = query


class AmbiguousSlugError(Exception):
    """Raised when more than one opportunity matches."""

    def __init__(self, message: str, *, candidates: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.candidates = candidates


def resolve_slug(query: str, opportunities_dir: Path) -> Path:
    """Map a user-supplied query to a single opportunity directory.

    Resolution order:
      1. Exact match against a folder name.
      2. Substring/prefix match across all folder names; if exactly one matches, use it.
      3. Multiple matches → AmbiguousSlugError. No matches → SlugNotFoundError.
    """
    candidates = sorted(p for p in opportunities_dir.iterdir() if p.is_dir())
    exact = [p for p in candidates if p.name == query]
    if len(exact) == 1:
        return exact[0]
    substring = [p for p in candidates if query in p.name]
    if len(substring) == 1:
        return substring[0]
    if not substring:
        raise SlugNotFoundError(f"no opportunity matches {query!r}", query=query)
    matches = "\n  ".join(p.name for p in substring)
    raise AmbiguousSlugError(
        f"{query!r} matches multiple opportunities:\n  {matches}",
        candidates=tuple(p.name for p in substring),
    )
