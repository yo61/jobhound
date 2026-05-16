"""Tests for `jh apply`."""

import subprocess
from datetime import UTC, datetime

import pytest

from jobhound.infrastructure.meta_io import read_meta


def _seed_prospect(invoke) -> None:
    """Scaffold a prospect-status opportunity via `jh new`."""
    result = invoke(
        ["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-11T12:00:00Z"],
    )
    assert result.exit_code == 0, result.output


def test_apply_advances_to_applied(tmp_jh, invoke) -> None:
    _seed_prospect(invoke)
    result = invoke(
        [
            "apply",
            "foo",
            "--on",
            "2026-05-12T12:00:00Z",
            "--next-action",
            "Wait for screen",
            "--next-action-due",
            "2026-05-26T12:00:00Z",
            "--now",
            "2026-05-12T12:00:00Z",
        ]
    )
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "applied"
    assert opp.applied_on == datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    assert opp.last_activity == datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    assert opp.next_action == "Wait for screen"
    assert opp.next_action_due == datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def test_apply_commits(tmp_jh, invoke) -> None:
    _seed_prospect(invoke)
    invoke(
        [
            "apply",
            "foo",
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-26",
            "--now",
            "2026-05-12T12:00:00Z",
        ]
    )
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "apply: 2026-05-foo-em" in log


def test_apply_refuses_when_not_prospect(tmp_jh, invoke) -> None:
    _seed_prospect(invoke)
    invoke(
        [
            "apply",
            "foo",
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-26",
            "--now",
            "2026-05-12T12:00:00Z",
        ]
    )
    result = invoke(
        [
            "apply",
            "foo",
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-26",
            "--now",
            "2026-05-12T12:00:00Z",
        ]
    )
    assert result.exit_code != 0
    assert "prospect" in result.output.lower()


@pytest.mark.parametrize(
    "value",
    [
        "2026-05-14",
        "2026-05-14T13:42:00",
        "2026-05-14 13:42:00",
        "2026-05-14T13:42:00+01:00",
        "2026-05-14T13:42:00.123456",
        "2026-05-14T13:42:00.123456+01:00",
    ],
)
def test_apply_accepts_iso_formats(tmp_jh, invoke, value: str) -> None:
    """All six Python 3.11+ fromisoformat forms are accepted by cyclopts."""
    _seed_prospect(invoke)
    result = invoke(
        [
            "apply",
            "foo",
            "--on",
            value,
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-26T12:00:00Z",
            "--now",
            "2026-05-14T12:00:00Z",
        ]
    )
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.applied_on is not None and opp.applied_on.tzinfo is not None


def test_apply_rejects_garbage_date(tmp_jh, invoke) -> None:
    """A malformed --next-action-due value produces a non-zero exit."""
    _seed_prospect(invoke)
    result = invoke(
        [
            "apply",
            "foo",
            "--next-action",
            "x",
            "--next-action-due",
            "garbage",
            "--now",
            "2026-05-12T12:00:00Z",
        ]
    )
    assert result.exit_code != 0
