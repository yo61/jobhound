"""Tests for jh note, jh priority, jh tag."""

from jobhound.meta_io import read_meta
from jobhound.priority import Priority


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--today", "2026-05-01"])


def test_note_appends_line(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["note", "foo", "--msg", "Recruiter sounds keen", "--today", "2026-05-11"])
    assert result.exit_code == 0, result.output
    notes = (tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "notes.md").read_text()
    assert "2026-05-11 Recruiter sounds keen" in notes


def test_note_bumps_last_activity(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "foo", "--msg", "x", "--today", "2026-05-11"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.last_activity.isoformat() == "2026-05-11"


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
