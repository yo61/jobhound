"""Tests run git against their own temp repos, never the repo running them.

A git hook (e.g. the pre-push pytest hook) exports `GIT_DIR`, `GIT_INDEX_FILE`
and friends. Inherited by the suite, they redirect every `git -C <tmp>` call
into the outer repository.
"""

from __future__ import annotations

import os
import subprocess


def test_no_repo_local_git_env_vars_reach_tests() -> None:
    local_vars = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()

    leaked = sorted(name for name in local_vars if name in os.environ)

    assert leaked == []
