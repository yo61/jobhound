"""Tests for the Slug value object."""

from __future__ import annotations

from datetime import date

import pytest

from jobhound.slug_value import Slug


def test_create_accepts_valid() -> None:
    assert Slug.create("2026-05-acme-eng").value == "2026-05-acme-eng"


def test_create_rejects_path_separator() -> None:
    with pytest.raises(ValueError):
        Slug.create("a/b")
    with pytest.raises(ValueError):
        Slug.create("a\\b")


def test_create_rejects_leading_dot() -> None:
    with pytest.raises(ValueError):
        Slug.create(".hidden")


def test_create_rejects_whitespace() -> None:
    with pytest.raises(ValueError):
        Slug.create("a b")
    with pytest.raises(ValueError):
        Slug.create(" leading")
    with pytest.raises(ValueError):
        Slug.create("trailing ")


def test_create_rejects_empty() -> None:
    with pytest.raises(ValueError):
        Slug.create("")


def test_build_formats_year_month_company_role() -> None:
    slug = Slug.build(date(2026, 5, 11), "Acme Corp", "Senior Engineer")
    assert slug.value == "2026-05-acme-corp-senior-engineer"


def test_build_collapses_non_alnum() -> None:
    slug = Slug.build(date(2026, 5, 11), "A!B@C", "x")
    assert slug.value == "2026-05-a-b-c-x"


def test_str_is_value() -> None:
    assert str(Slug.create("x")) == "x"
