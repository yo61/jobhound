"""Tests for `jh contact add` and `jh contact remove`."""

from jobhound.domain.contact import Contact
from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_contact_add_appends(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(
        [
            "contact",
            "add",
            "foo",
            "--name",
            "Jane Doe",
            "--role-title",
            "Recruiter",
            "--channel",
            "email",
        ]
    )
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.contacts == (Contact(name="Jane Doe", role="Recruiter", channel="email"),)


def test_contact_remove_removes_matching_contact(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(
        [
            "contact",
            "add",
            "foo",
            "--name",
            "Jane Doe",
            "--role-title",
            "Recruiter",
            "--channel",
            "email",
        ]
    )
    invoke(
        [
            "contact",
            "add",
            "foo",
            "--name",
            "Bob Smith",
            "--role-title",
            "HM",
            "--channel",
            "linkedin",
        ]
    )
    result = invoke(
        [
            "contact",
            "remove",
            "foo",
            "--name",
            "Jane Doe",
            "--role",
            "Recruiter",
            "--channel",
            "email",
        ]
    )
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.contacts == (Contact(name="Bob Smith", role="HM", channel="linkedin"),)


def test_contact_remove_leaves_other_contacts_intact(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Alice", "--role-title", "CTO"])
    invoke(["contact", "add", "foo", "--name", "Bob"])
    invoke(["contact", "remove", "foo", "--name", "Alice", "--role", "CTO"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert len(opp.contacts) == 1
    assert opp.contacts[0].name == "Bob"


def test_contact_remove_not_found_raises(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane"])
    result = invoke(["contact", "remove", "foo", "--name", "Nobody"])
    assert result.exit_code != 0
