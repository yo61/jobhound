"""Tests for `jh new`."""

import subprocess

from jobhound.infrastructure.meta_io import read_meta


def test_new_creates_directory_and_meta(tmp_jh, invoke) -> None:
    result = invoke(
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
            "--now",
            "2026-05-11T12:00:00Z",
        ]
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


def test_new_creates_git_commit(tmp_jh, invoke) -> None:
    result = invoke(
        ["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-11T12:00:00Z"],
    )
    assert result.exit_code == 0, result.output
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "new: 2026-05-foo-em" in log
