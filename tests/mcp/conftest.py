"""Shared fixtures for MCP adapter tests.

mcp_paths: extends query_paths (from tests/application/conftest.py) with
           a real git-init'd data root, ready for Repository writes.
repo:      an OpportunityRepository constructed from mcp_paths.

call_tool will be added in Task 9 when the first MCP tools land.
"""

from __future__ import annotations

import subprocess

import pytest

from jobhound.infrastructure.config import Config
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository


@pytest.fixture
def mcp_paths(query_paths: Paths) -> Paths:
    """query_paths with a git-init'd db_root, ready for Repository writes."""
    db = query_paths.db_root
    subprocess.run(["git", "init", "--quiet", str(db)], check=True)
    subprocess.run(
        ["git", "-C", str(db), "config", "user.name", "test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(db), "config", "user.email", "t@t"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(db), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(db), "commit", "-m", "seed", "--quiet"],
        check=True,
        capture_output=True,
    )
    return query_paths


@pytest.fixture
def repo(mcp_paths: Paths) -> OpportunityRepository:
    cfg = Config(db_path=mcp_paths.db_root, auto_commit=True, editor="")
    return OpportunityRepository(mcp_paths, cfg)
