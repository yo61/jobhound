"""`jh sync` — git push to the configured remote, if one exists."""

from __future__ import annotations

import subprocess
import sys

from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run() -> None:
    """Push the data root's git repo to its remote."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    remotes = subprocess.run(
        ["git", "-C", str(paths.db_root), "remote"],
        capture_output=True,
        text=True,
        check=True,
    )
    if not remotes.stdout.strip():
        print(
            "no remote configured; set one with `git -C <db> remote add origin <url>`",
            file=sys.stderr,
        )
        raise SystemExit(1)
    result = subprocess.run(
        ["git", "-C", str(paths.db_root), "push"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr or "push failed", file=sys.stderr)
        raise SystemExit(result.returncode)
    print("pushed.")
