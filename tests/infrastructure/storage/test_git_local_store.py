"""Tests for GitLocalFileStore — the git-backed FileStore adapter."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.storage.git_local import GitLocalFileStore


def _git_init(db_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(db_root)], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.email", "t@t"], check=True)


def _seeded(tmp_path: Path) -> tuple[GitLocalFileStore, Paths]:
    db_root = tmp_path / "db"
    for d in ("opportunities", "archive", "_shared"):
        (db_root / d).mkdir(parents=True)
    _git_init(db_root)
    opp_dir = db_root / "opportunities" / "2026-05-acme"
    opp_dir.mkdir()
    (opp_dir / ".gitkeep").touch()  # git ignores empty dirs; need a trackable file
    subprocess.run(["git", "-C", str(db_root), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_root), "commit", "-m", "seed", "--quiet"],
        check=True,
        capture_output=True,
    )
    paths = Paths(
        db_root=db_root,
        opportunities_dir=db_root / "opportunities",
        archive_dir=db_root / "archive",
        shared_dir=db_root / "_shared",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )
    return GitLocalFileStore(paths), paths


def _head_sha(db_root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(db_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_write_creates_file_and_commits(tmp_path: Path) -> None:
    store, paths = _seeded(tmp_path)
    head_before = _head_sha(paths.db_root)
    store.write("2026-05-acme", "cv.md", b"hello\n", commit_message="file: write acme/cv.md")
    head_after = _head_sha(paths.db_root)
    assert head_before != head_after
    assert (paths.opportunities_dir / "2026-05-acme" / "cv.md").read_bytes() == b"hello\n"
    msg = subprocess.run(
        ["git", "-C", str(paths.db_root), "log", "-1", "--format=%s"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert msg == "file: write acme/cv.md"


def test_read_returns_bytes(tmp_path: Path) -> None:
    store, _ = _seeded(tmp_path)
    store.write("2026-05-acme", "cv.md", b"raw\n", commit_message="x")
    assert store.read("2026-05-acme", "cv.md") == b"raw\n"


def test_append_preserves_existing_and_commits(tmp_path: Path) -> None:
    store, paths = _seeded(tmp_path)
    store.write("2026-05-acme", "notes.md", b"a\n", commit_message="x")
    store.append("2026-05-acme", "notes.md", b"b\n", commit_message="x")
    assert (paths.opportunities_dir / "2026-05-acme" / "notes.md").read_bytes() == b"a\nb\n"


def test_delete_removes_file_and_commits(tmp_path: Path) -> None:
    store, paths = _seeded(tmp_path)
    store.write("2026-05-acme", "cv.md", b"x", commit_message="x")
    store.delete("2026-05-acme", "cv.md", commit_message="rm")
    assert not (paths.opportunities_dir / "2026-05-acme" / "cv.md").exists()


def test_revision_matches_git_hash_object(tmp_path: Path) -> None:
    store, paths = _seeded(tmp_path)
    store.write("2026-05-acme", "cv.md", b"hello\n", commit_message="x")
    revision = store.compute_revision("2026-05-acme", "cv.md")
    expected = subprocess.run(
        ["git", "hash-object", str(paths.opportunities_dir / "2026-05-acme" / "cv.md")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert revision == expected


def test_subdirectory_write_creates_parent(tmp_path: Path) -> None:
    store, paths = _seeded(tmp_path)
    store.write(
        "2026-05-acme",
        "correspondence/2026-05-01-intro.md",
        b"hi\n",
        commit_message="x",
    )
    target = paths.opportunities_dir / "2026-05-acme" / "correspondence" / "2026-05-01-intro.md"
    assert target.read_bytes() == b"hi\n"


def test_list_returns_file_entries(tmp_path: Path) -> None:
    store, _ = _seeded(tmp_path)
    store.write("2026-05-acme", "cv.md", b"a", commit_message="x")
    store.write("2026-05-acme", "notes.md", b"b", commit_message="x")
    entries = store.list("2026-05-acme")
    names = sorted(e.name for e in entries)
    assert names == ["cv.md", "notes.md"]
    for e in entries:
        assert e.size > 0
        assert e.mtime is not None


def test_path_traversal_rejected(tmp_path: Path) -> None:
    store, _ = _seeded(tmp_path)
    with pytest.raises(ValueError, match="must be inside"):
        store.write("2026-05-acme", "../../escape.md", b"x", commit_message="x")
