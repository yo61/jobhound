"""Tests for `jh remove tag` and `jh remove contact`."""

from jobhound.domain.contact import Contact
from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


# ---------------------------------------------------------------------------
# remove tag
# ---------------------------------------------------------------------------


def test_remove_tag_removes_existing_tag(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["add", "tag", "foo", "remote"])
    invoke(["add", "tag", "foo", "uk"])
    result = invoke(["remove", "tag", "foo", "uk"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.tags == ("remote",)


def test_remove_tag_nonexistent_tag_is_noop(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["add", "tag", "foo", "remote"])
    result = invoke(["remove", "tag", "foo", "nonexistent"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.tags == ("remote",)


# ---------------------------------------------------------------------------
# remove contact
# ---------------------------------------------------------------------------


def test_remove_contact_removes_matching_contact(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(
        [
            "add",
            "contact",
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
            "add",
            "contact",
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
            "remove",
            "contact",
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


def test_remove_contact_leaves_other_contacts_intact(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["add", "contact", "foo", "--name", "Alice", "--role-title", "CTO"])
    invoke(["add", "contact", "foo", "--name", "Bob"])
    invoke(["remove", "contact", "foo", "--name", "Alice", "--role", "CTO"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert len(opp.contacts) == 1
    assert opp.contacts[0].name == "Bob"


def test_remove_contact_not_found_raises(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["add", "contact", "foo", "--name", "Jane"])
    result = invoke(["remove", "contact", "foo", "--name", "Nobody"])
    assert result.exit_code != 0
