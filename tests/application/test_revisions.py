"""Tests for application/revisions.py — Revision NewType."""

from __future__ import annotations

from jobhound.application.revisions import Revision


def test_revision_is_str() -> None:
    r = Revision("abc123")
    assert r == "abc123"
    assert isinstance(r, str)


def test_revision_equality() -> None:
    a = Revision("abc123")
    b = Revision("abc123")
    c = Revision("def456")
    assert a == b
    assert a != c
