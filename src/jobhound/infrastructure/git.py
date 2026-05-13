"""Auto-commit helper. Every mutating subcommand ends with `commit_change`."""

from __future__ import annotations

import subprocess
from pathlib import Path


def ensure_repo(db_path: Path) -> None:
    """Initialise `db_path` as a git repo if it isn't already."""
    db_path.mkdir(parents=True, exist_ok=True)
    if (db_path / ".git").is_dir():
        return
    subprocess.run(["git", "init", "--quiet", str(db_path)], check=True)
    # Local config so commits work without global identity. Override your own
    # user.name/user.email manually if you want different attribution.
    subprocess.run(
        ["git", "-C", str(db_path), "config", "user.name", "jh"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(db_path), "config", "user.email", "jh@localhost"],
        check=True,
    )


def _has_changes(db_path: Path) -> bool:
    """Return True if `git status --porcelain` lists any changes."""
    result = subprocess.run(
        ["git", "-C", str(db_path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())


def commit_change(db_path: Path, message: str, *, enabled: bool) -> None:
    """Stage everything in `db_path` and commit with `message`. No-op if disabled or clean."""
    if not enabled:
        return
    if not _has_changes(db_path):
        return
    subprocess.run(["git", "-C", str(db_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "--quiet", "-m", message],
        check=True,
    )
