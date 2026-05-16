"""Tests for `jh add note`, `jh add contact`, `jh add tag`."""

from datetime import UTC, datetime

from jobhound.domain.contact import Contact
from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_add_note_appends_line(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(
        ["add", "note", "foo", "--msg", "Recruiter sounds keen", "--now", "2026-05-11T12:00:00Z"]
    )
    assert result.exit_code == 0, result.output
    notes = (tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "notes.md").read_text()
    assert "2026-05-11T12:00:00Z Recruiter sounds keen" in notes


def test_add_note_bumps_last_activity(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["add", "note", "foo", "--msg", "x", "--now", "2026-05-11T12:00:00Z"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.last_activity == datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


def test_add_contact_appends(tmp_jh, invoke) -> None:
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
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.contacts == (Contact(name="Jane Doe", role="Recruiter", channel="email"),)


def test_add_tag_adds_tag(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["add", "tag", "foo", "remote"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert "remote" in opp.tags


def test_add_tag_multiple(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["add", "tag", "foo", "remote"])
    invoke(["add", "tag", "foo", "uk"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert set(opp.tags) == {"remote", "uk"}
