"""Tests for jh note, jh priority, jh tag."""

from datetime import UTC, datetime

from jobhound.domain.priority import Priority
from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_note_appends_line(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(
        ["note", "foo", "--msg", "Recruiter sounds keen", "--now", "2026-05-11T12:00:00Z"]
    )
    assert result.exit_code == 0, result.output
    notes = (tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "notes.md").read_text()
    assert "2026-05-11T12:00:00Z Recruiter sounds keen" in notes


def test_note_bumps_last_activity(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "foo", "--msg", "x", "--now", "2026-05-11T12:00:00Z"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.last_activity == datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


def test_priority_sets_value(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["priority", "foo", "--to", "high"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.priority == Priority.HIGH


def test_priority_rejects_invalid_value(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["priority", "foo", "--to", "ultra"])
    assert result.exit_code != 0


def test_tag_add_and_remove(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["tag", "foo", "--add", "remote", "--add", "uk"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert set(opp.tags) == {"remote", "uk"}
    invoke(["tag", "foo", "--remove", "uk"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.tags == ("remote",)
