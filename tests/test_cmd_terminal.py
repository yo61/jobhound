"""Tests for terminal verbs (withdraw, ghost, accept, decline)."""

import subprocess

from jobhound.infrastructure.meta_io import read_meta


def _seed(tmp_path, invoke, target_status: str) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--today", "2026-05-01"])
    if target_status == "prospect":
        return
    invoke(
        [
            "apply",
            "foo",
            "--next-action",
            "x",
            "--next-action-due",
            "2026-05-20",
            "--today",
            "2026-05-05",
        ]
    )
    if target_status == "applied":
        return
    body_path = tmp_path / "body.md"
    body_path.write_text("hi")
    transitions = {
        "screen": [("screen", "2026-05-10")],
        "interview": [("screen", "2026-05-10"), ("interview", "2026-05-11")],
        "offer": [("screen", "2026-05-10"), ("interview", "2026-05-11"), ("offer", "2026-05-12")],
    }
    for to_status, step_date in transitions[target_status]:
        invoke(
            [
                "log",
                "foo",
                "--channel",
                "email",
                "--direction",
                "from",
                "--who",
                "x",
                "--body",
                str(body_path),
                "--next-status",
                to_status,
                "--next-action",
                "x",
                "--next-action-due",
                "2026-05-20",
                "--today",
                step_date,
            ]
        )


def test_withdraw_from_active(tmp_jh, tmp_path, invoke) -> None:
    _seed(tmp_path, invoke, "applied")
    result = invoke(["withdraw", "foo", "--today", "2026-05-15"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "withdrawn"
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "withdraw: 2026-05-foo-em" in log


def test_ghost_from_active(tmp_jh, tmp_path, invoke) -> None:
    _seed(tmp_path, invoke, "applied")
    result = invoke(["ghost", "foo", "--today", "2026-06-01"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "ghosted"


def test_accept_only_from_offer(tmp_jh, tmp_path, invoke) -> None:
    _seed(tmp_path, invoke, "applied")
    result = invoke(["accept", "foo", "--today", "2026-05-15"])
    assert result.exit_code != 0
    assert "offer" in result.output


def test_accept_from_offer(tmp_jh, tmp_path, invoke) -> None:
    _seed(tmp_path, invoke, "offer")
    result = invoke(["accept", "foo", "--today", "2026-05-15"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "accepted"


def test_decline_from_offer(tmp_jh, tmp_path, invoke) -> None:
    _seed(tmp_path, invoke, "offer")
    result = invoke(["decline", "foo", "--today", "2026-05-15"])
    assert result.exit_code == 0, result.output
    opp = read_meta(tmp_jh.db_path / "opportunities" / "2026-05-foo-em" / "meta.toml")
    assert opp.status == "declined"
