"""Tests for the Contact value object."""

from __future__ import annotations

import pytest

from jobhound.contact import Contact


def test_required_name() -> None:
    with pytest.raises(ValueError):
        Contact(name="")


def test_to_dict_drops_none() -> None:
    c = Contact(name="Jane", role="Recruiter", channel=None, company=None, note=None)
    assert c.to_dict() == {"name": "Jane", "role": "Recruiter"}


def test_to_dict_includes_all_set() -> None:
    c = Contact(name="Jane", role="Recruiter", channel="email", company="Acme", note="warm")
    assert c.to_dict() == {
        "name": "Jane",
        "role": "Recruiter",
        "channel": "email",
        "company": "Acme",
        "note": "warm",
    }


def test_from_dict_roundtrip() -> None:
    raw = {"name": "Jane", "role": "Recruiter"}
    assert Contact.from_dict(raw).to_dict() == raw


def test_from_dict_requires_name() -> None:
    with pytest.raises(ValueError):
        Contact.from_dict({"role": "Recruiter"})
