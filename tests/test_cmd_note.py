"""Tests for `jh note add`."""

from datetime import UTC, datetime

from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_note_add_writes_note_file(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(
        ["note", "add", "foo", "--msg", "Recruiter sounds keen", "--now", "2026-05-11T12:00:00Z"]
    )
    assert result.exit_code == 0, result.output
    notes_dir = tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "notes"
    assert (notes_dir / "1.md").exists()
    contents = (notes_dir / "1.md").read_text()
    assert "Recruiter sounds keen" in contents
    assert "created = 2026-05-11T12:00:00Z" in contents


def test_note_add_bumps_last_activity(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["note", "add", "foo", "--msg", "x", "--now", "2026-05-11T12:00:00Z"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.last_activity == datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
