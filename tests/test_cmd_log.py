"""Tests for `jh log` (flag-driven path only)."""

import subprocess
from datetime import UTC, datetime

from jobhound.infrastructure.meta_io import read_meta


def _seed_applied(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    invoke(
        [
            "apply",
            "foo",
            "--next-action",
            "Wait for screen",
            "--next-action-due",
            "2026-05-15",
            "--now",
            "2026-05-05T12:00:00Z",
        ],
    )


def test_log_writes_correspondence_and_advances_status(tmp_jh, invoke, tmp_path) -> None:
    _seed_applied(invoke)
    body = tmp_path / "draft.md"
    body.write_text("Thanks for applying — let's schedule a chat.\n")
    result = invoke(
        [
            "log",
            "foo",
            "--channel",
            "email",
            "--direction",
            "from",
            "--who",
            "Joey Capper",
            "--body",
            str(body),
            "--next-status",
            "screen",
            "--next-action",
            "Confirm screening date",
            "--next-action-due",
            "2026-05-18",
            "--now",
            "2026-05-11T12:00:00Z",
        ]
    )
    assert result.exit_code == 0, result.output

    opp_dir = tmp_jh.db_path / "opportunities" / "2026-05-foo-em"
    corr = opp_dir / "correspondence" / "2026-05-11-email-from-joey-capper.md"
    assert corr.is_file()
    assert "Thanks for applying" in corr.read_text()

    opp = read_meta(opp_dir / "meta.toml")
    assert opp.status == "screen"
    assert opp.last_activity == datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    assert opp.next_action == "Confirm screening date"


def test_log_stay_keeps_status(tmp_jh, invoke, tmp_path) -> None:
    _seed_applied(invoke)
    body = tmp_path / "draft.md"
    body.write_text("FYI, will respond next week.\n")
    result = invoke(
        [
            "log",
            "foo",
            "--channel",
            "email",
            "--direction",
            "to",
            "--who",
            "Joey",
            "--body",
            str(body),
            "--next-status",
            "stay",
            "--next-action",
            "Chase after 1 week",
            "--next-action-due",
            "2026-05-19",
            "--now",
            "2026-05-12T12:00:00Z",
        ]
    )
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "applied"


def test_log_rejected_terminates(tmp_jh, invoke, tmp_path) -> None:
    _seed_applied(invoke)
    body = tmp_path / "draft.md"
    body.write_text("Sorry, not moving forward.\n")
    result = invoke(
        [
            "log",
            "foo",
            "--channel",
            "email",
            "--direction",
            "from",
            "--who",
            "Joey",
            "--body",
            str(body),
            "--next-status",
            "rejected",
            "--now",
            "2026-05-13T12:00:00Z",
        ]
    )
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "rejected"


def test_log_illegal_transition_rejected(tmp_jh, invoke, tmp_path) -> None:
    _seed_applied(invoke)
    body = tmp_path / "draft.md"
    body.write_text("hi")
    result = invoke(
        [
            "log",
            "foo",
            "--channel",
            "email",
            "--direction",
            "from",
            "--who",
            "Joey",
            "--body",
            str(body),
            "--next-status",
            "accepted",
            "--now",
            "2026-05-13T12:00:00Z",
        ]
    )
    assert result.exit_code != 0
    assert "not a legal next status" in result.output


def test_log_force_overrides_illegal(tmp_jh, invoke, tmp_path) -> None:
    _seed_applied(invoke)
    body = tmp_path / "draft.md"
    body.write_text("hi")
    result = invoke(
        [
            "log",
            "foo",
            "--channel",
            "email",
            "--direction",
            "from",
            "--who",
            "Joey",
            "--body",
            str(body),
            "--next-status",
            "interview",
            "--force",
            "--next-action",
            "Prep",
            "--next-action-due",
            "2026-05-20",
            "--now",
            "2026-05-13T12:00:00Z",
        ]
    )
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "interview"


def test_log_commit_message(tmp_jh, invoke, tmp_path) -> None:
    _seed_applied(invoke)
    body = tmp_path / "draft.md"
    body.write_text("hi")
    invoke(
        [
            "log",
            "foo",
            "--channel",
            "email",
            "--direction",
            "from",
            "--who",
            "Joey",
            "--body",
            str(body),
            "--next-status",
            "screen",
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-18",
            "--now",
            "2026-05-11T12:00:00Z",
        ]
    )
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "log: 2026-05-foo-em applied → screen" in log
