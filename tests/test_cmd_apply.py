"""Tests for `jh apply`."""

import subprocess
from datetime import date

from jobhound.infrastructure.meta_io import read_meta


def _seed_prospect(invoke) -> None:
    """Scaffold a prospect-status opportunity via `jh new`."""
    result = invoke(
        ["new", "--company", "Foo", "--role", "EM", "--today", "2026-05-11"],
    )
    assert result.exit_code == 0, result.output


def test_apply_advances_to_applied(tmp_jh, invoke) -> None:
    _seed_prospect(invoke)
    result = invoke(
        [
            "apply",
            "foo",
            "--on",
            "2026-05-12",
            "--next-action",
            "Wait for screen",
            "--next-action-due",
            "2026-05-26",
            "--today",
            "2026-05-12",
        ]
    )
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "applied"
    assert opp.applied_on == date(2026, 5, 12)
    assert opp.last_activity == date(2026, 5, 12)
    assert opp.next_action == "Wait for screen"
    assert opp.next_action_due == date(2026, 5, 26)


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
            "--today",
            "2026-05-12",
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
            "--today",
            "2026-05-12",
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
            "--today",
            "2026-05-12",
        ]
    )
    assert result.exit_code != 0
    assert "prospect" in result.output.lower()
