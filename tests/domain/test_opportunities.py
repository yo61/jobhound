"""Tests for Opportunity.notes_next_seq field and its helper."""

from __future__ import annotations

import pytest

from jobhound.domain.opportunities import Opportunity, opportunity_from_dict


def _opp() -> Opportunity:
    return opportunity_from_dict(
        {
            "company": "Foo",
            "role": "Engineer",
            "status": "prospect",
            "slug": "2026-06-foo-engineer",
        }
    )


def test_notes_next_seq_defaults_to_1() -> None:
    opp = _opp()
    assert opp.notes_next_seq == 1


def test_with_notes_next_seq_returns_updated_instance() -> None:
    opp = _opp()
    updated = opp.with_notes_next_seq(7)
    assert updated.notes_next_seq == 7
    assert opp.notes_next_seq == 1  # original unchanged (frozen dataclass)


def test_with_notes_next_seq_rejects_zero() -> None:
    opp = _opp()
    with pytest.raises(ValueError):
        opp.with_notes_next_seq(0)


def test_with_notes_next_seq_rejects_negative() -> None:
    opp = _opp()
    with pytest.raises(ValueError):
        opp.with_notes_next_seq(-1)
