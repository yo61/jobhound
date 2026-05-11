"""Tests for `jh new`."""

import subprocess

from typer.testing import CliRunner

from jobhound.cli import app
from jobhound.meta_io import read_meta


def test_new_creates_directory_and_meta(tmp_jh) -> None:
    result = CliRunner().invoke(
        app,
        [
            "new",
            "--company",
            "Foo Corp",
            "--role",
            "Engineering Manager",
            "--source",
            "LinkedIn",
            "--next-action",
            "Initial review",
            "--next-action-due",
            "2026-05-18",
            "--today",
            "2026-05-11",
        ],
    )
    assert result.exit_code == 0, result.output
    opp_dir = tmp_jh.db_path / "opportunities" / "2026-05-foo-corp-engineering-manager"
    assert opp_dir.is_dir()
    assert (opp_dir / "notes.md").exists()
    assert (opp_dir / "research.md").exists()
    assert (opp_dir / "correspondence").is_dir()

    opp = read_meta(opp_dir / "meta.toml")
    assert opp.company == "Foo Corp"
    assert opp.role == "Engineering Manager"
    assert opp.status == "prospect"
    assert opp.source == "LinkedIn"


def test_new_creates_git_commit(tmp_jh) -> None:
    result = CliRunner().invoke(
        app,
        ["new", "--company", "Foo", "--role", "EM", "--today", "2026-05-11"],
    )
    assert result.exit_code == 0, result.output
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "new: 2026-05-foo-em" in log


def test_new_no_commit_flag_skips_git(tmp_jh) -> None:
    result = CliRunner().invoke(
        app,
        ["new", "--company", "Foo", "--role", "EM", "--today", "2026-05-11", "--no-commit"],
    )
    assert result.exit_code == 0, result.output
    # No commit was made: git log exits non-zero when there are no commits.
    log_result = subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert "new:" not in log_result.stdout
