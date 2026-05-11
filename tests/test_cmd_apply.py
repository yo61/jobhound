"""Tests for `jh apply`."""

import subprocess

from typer.testing import CliRunner

from jobhound.cli import app
from jobhound.meta_io import read_meta


def _seed_prospect(tmp_jh, slug: str = "2026-05-foo-em") -> None:
    """Scaffold a prospect-status opportunity via `jh new`."""
    result = CliRunner().invoke(
        app,
        ["new", "--company", "Foo", "--role", "EM", "--today", "2026-05-11"],
    )
    assert result.exit_code == 0, result.output


def test_apply_advances_to_applied(tmp_jh) -> None:
    _seed_prospect(tmp_jh)
    result = CliRunner().invoke(
        app,
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
        ],
    )
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "applied"
    assert opp.applied_on.isoformat() == "2026-05-12"
    assert opp.last_activity.isoformat() == "2026-05-12"
    assert opp.next_action == "Wait for screen"
    assert opp.next_action_due.isoformat() == "2026-05-26"


def test_apply_commits(tmp_jh) -> None:
    _seed_prospect(tmp_jh)
    CliRunner().invoke(
        app,
        [
            "apply",
            "foo",
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-26",
            "--today",
            "2026-05-12",
        ],
    )
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "apply: 2026-05-foo-em" in log


def test_apply_refuses_when_not_prospect(tmp_jh) -> None:
    _seed_prospect(tmp_jh)
    # First call moves to applied; second call should fail.
    CliRunner().invoke(
        app,
        [
            "apply",
            "foo",
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-26",
            "--today",
            "2026-05-12",
        ],
    )
    result = CliRunner().invoke(
        app,
        [
            "apply",
            "foo",
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-26",
            "--today",
            "2026-05-12",
        ],
    )
    assert result.exit_code != 0
    assert "prospect" in result.output.lower()
