"""Tests for the auto-commit helper."""

import subprocess
from pathlib import Path

import pytest

from jobhound.infrastructure.git import commit_change, ensure_repo


def _git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    ensure_repo(tmp_path)
    return tmp_path


def test_ensure_repo_initialises_when_missing(tmp_path: Path) -> None:
    assert not (tmp_path / ".git").exists()
    ensure_repo(tmp_path)
    assert (tmp_path / ".git").is_dir()


def test_ensure_repo_idempotent(tmp_path: Path) -> None:
    ensure_repo(tmp_path)
    head_before = _git("rev-parse", "--git-dir", cwd=tmp_path)
    ensure_repo(tmp_path)
    head_after = _git("rev-parse", "--git-dir", cwd=tmp_path)
    assert head_before == head_after


def test_commit_change_creates_commit(repo: Path) -> None:
    (repo / "hello.txt").write_text("hi\n")
    commit_change(repo, "test: first commit", enabled=True)
    log = _git("log", "--oneline", cwd=repo)
    assert "test: first commit" in log


def test_commit_change_disabled_does_nothing(repo: Path) -> None:
    (repo / "hello.txt").write_text("hi\n")
    commit_change(repo, "should not appear", enabled=False)
    log_result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert "should not appear" not in log_result.stdout


def test_commit_change_noop_when_clean(repo: Path) -> None:
    (repo / "hello.txt").write_text("hi\n")
    commit_change(repo, "first", enabled=True)
    commit_change(repo, "second", enabled=True)
    log = _git("log", "--oneline", cwd=repo)
    assert log.count("\n") == 1  # one commit, not two
