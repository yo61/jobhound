"""Tests for `jh bump`."""

from datetime import UTC, datetime

from jobhound.infrastructure.meta_io import read_meta


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_bump_updates_last_activity(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["bump", "foo"])
    assert result.exit_code == 0, result.output
    assert "bumped" in result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    today = datetime.now(UTC).date()
    assert opp.last_activity is not None
    assert opp.last_activity.date() == today


def test_bump_does_not_change_status(tmp_jh, invoke) -> None:
    _seed(invoke)
    invoke(["bump", "foo"])
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status.value == "prospect"
