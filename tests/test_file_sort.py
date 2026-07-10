"""Unit tests for `jh file list` sort ordering (`_sort_entries`)."""

from __future__ import annotations

from datetime import UTC, datetime

from jobhound.application.snapshots import FileEntry
from jobhound.commands.file import FileSortKey, _sort_entries

# Three entries whose name, size, and mtime orderings are all distinct, so a
# test can tell which key actually drove the sort. Names mix case to exercise
# case-insensitive collation (byte order would put every uppercase before
# every lowercase).
_ALPHA = FileEntry(name="Alpha.md", size=30, mtime=datetime(2026, 1, 1, tzinfo=UTC))
_BRAVO = FileEntry(name="bravo.md", size=10, mtime=datetime(2026, 2, 1, tzinfo=UTC))
_CHARLIE = FileEntry(name="Charlie.md", size=20, mtime=datetime(2026, 3, 1, tzinfo=UTC))
_ENTRIES = [_CHARLIE, _ALPHA, _BRAVO]  # deliberately unsorted input


def _names(entries: list[FileEntry]) -> list[str]:
    return [e.name for e in entries]


def test_name_sorts_case_insensitively_ascending_by_default() -> None:
    result = _sort_entries(_ENTRIES, FileSortKey.NAME, reverse=False)
    assert _names(result) == ["Alpha.md", "bravo.md", "Charlie.md"]


def test_name_reverse_flips_to_descending() -> None:
    result = _sort_entries(_ENTRIES, FileSortKey.NAME, reverse=True)
    assert _names(result) == ["Charlie.md", "bravo.md", "Alpha.md"]


def test_name_case_sensitive_uses_byte_order() -> None:
    """Opt-in byte order: every uppercase name sorts before every lowercase."""
    result = _sort_entries(_ENTRIES, FileSortKey.NAME, reverse=False, case_sensitive=True)
    assert _names(result) == ["Alpha.md", "Charlie.md", "bravo.md"]


def test_size_defaults_to_largest_first() -> None:
    result = _sort_entries(_ENTRIES, FileSortKey.SIZE, reverse=False)
    assert _names(result) == ["Alpha.md", "Charlie.md", "bravo.md"]


def test_size_reverse_is_smallest_first() -> None:
    result = _sort_entries(_ENTRIES, FileSortKey.SIZE, reverse=True)
    assert _names(result) == ["bravo.md", "Charlie.md", "Alpha.md"]


def test_date_defaults_to_newest_first() -> None:
    result = _sort_entries(_ENTRIES, FileSortKey.DATE, reverse=False)
    assert _names(result) == ["Charlie.md", "bravo.md", "Alpha.md"]


def test_date_reverse_is_oldest_first() -> None:
    result = _sort_entries(_ENTRIES, FileSortKey.DATE, reverse=True)
    assert _names(result) == ["Alpha.md", "bravo.md", "Charlie.md"]


def test_does_not_mutate_input() -> None:
    original = list(_ENTRIES)
    _sort_entries(_ENTRIES, FileSortKey.NAME, reverse=False)
    assert original == _ENTRIES
