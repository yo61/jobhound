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


# ── list ─────────────────────────────────────────────────────────────────


def test_contact_list_empty(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["contact", "list", "foo"])
    assert result.exit_code == 0


def test_contact_list_table_columns(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane Doe", "--role-title", "Recruiter"])
    invoke(["contact", "add", "foo", "--name", "Bob Smith", "--channel", "linkedin"])
    result = invoke(["contact", "list", "foo"])
    assert result.exit_code == 0
    assert "NAME" in result.output
    assert "ROLE" in result.output
    assert "Jane Doe" in result.output
    assert "Recruiter" in result.output
    assert "Bob Smith" in result.output
    assert "linkedin" in result.output


def test_contact_list_json(tmp_jh, invoke) -> None:
    import json

    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane Doe", "--role-title", "Recruiter"])
    result = invoke(["contact", "list", "foo", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data == [{"name": "Jane Doe", "role": "Recruiter"}]


# ── show ─────────────────────────────────────────────────────────────────


def test_contact_show_prints_fields(tmp_jh, invoke) -> None:
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
    result = invoke(["contact", "show", "foo", "Jane Doe"])
    assert result.exit_code == 0
    assert "Jane Doe" in result.output
    assert "Recruiter" in result.output
    assert "email" in result.output


def test_contact_show_missing(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["contact", "show", "foo", "Nobody"])
    assert result.exit_code != 0


def test_contact_show_ambiguous(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane Doe", "--role-title", "Recruiter"])
    invoke(["contact", "add", "foo", "--name", "Jane Doe", "--role-title", "HM"])
    result = invoke(["contact", "show", "foo", "Jane Doe"])
    assert result.exit_code != 0


def test_contact_show_disambiguates_with_match_role(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane Doe", "--role-title", "Recruiter"])
    invoke(["contact", "add", "foo", "--name", "Jane Doe", "--role-title", "HM"])
    result = invoke(["contact", "show", "foo", "Jane Doe", "--match-role", "HM"])
    assert result.exit_code == 0
    assert "HM" in result.output


def test_contact_show_json(tmp_jh, invoke) -> None:
    import json

    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane Doe", "--role-title", "Recruiter"])
    result = invoke(["contact", "show", "foo", "Jane Doe", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    assert data == {"name": "Jane Doe", "role": "Recruiter"}


# ── edit ─────────────────────────────────────────────────────────────────


def test_contact_edit_updates_role(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane Doe", "--role-title", "Recruiter"])
    result = invoke(["contact", "edit", "foo", "Jane Doe", "--role", "Sourcer"])
    assert result.exit_code == 0
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.contacts[0].role == "Sourcer"
    assert opp.contacts[0].name == "Jane Doe"  # name unchanged


def test_contact_edit_renames(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane Smithh"])
    result = invoke(["contact", "edit", "foo", "Jane Smithh", "--new-name", "Jane Smith"])
    assert result.exit_code == 0
    assert "→" in result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.contacts[0].name == "Jane Smith"


def test_contact_edit_missing(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["contact", "edit", "foo", "Nobody", "--role", "x"])
    assert result.exit_code != 0


def test_contact_edit_preserves_position_in_tuple(tmp_jh, invoke) -> None:
    """Edit replaces in-place; the contact's index doesn't change."""
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Alice"])
    invoke(["contact", "add", "foo", "--name", "Bob"])
    invoke(["contact", "add", "foo", "--name", "Carol"])
    invoke(["contact", "edit", "foo", "Bob", "--role", "PM"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert [c.name for c in opp.contacts] == ["Alice", "Bob", "Carol"]
    assert opp.contacts[1].role == "PM"


def test_contact_edit_no_change_no_commit(tmp_jh, invoke) -> None:
    """Edit with no `new_*` fields is a no-op."""
    _seed(invoke)
    invoke(["contact", "add", "foo", "--name", "Jane"])
    result = invoke(["contact", "edit", "foo", "Jane"])
    assert result.exit_code == 0
