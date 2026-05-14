# File Management API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a uniform file-management API over a swappable `FileStore` port — application service (`file_service.py`), git-local adapter, 7 MCP tools, 5 CLI subcommands — and migrate the two scattered direct-FS callers (`ops_service.add_note`, `commands/log.py`) to use it.

**Architecture:** DDD ports-and-adapters. The application layer (`file_service.py`) depends only on a `FileStore` Protocol declared in `infrastructure/storage/protocols.py`. The first concrete adapter is `GitLocalFileStore`; tests use `InMemoryFileStore`. Conflict detection uses a six-case state machine plus `git merge-file` for text 3-way merges. The CLI and MCP server are peer adapters, both calling `file_service`.

**Tech Stack:** Python 3.12+, stdlib + existing deps. No new runtime deps. `git merge-file` and `git hash-object` shelled out via subprocess (git is already required).

**Spec:** `docs/specs/2026-05-14-file-management-design.md` is the contract; this plan is the execution.

**Branch:** `feat/file-management-design` (already created; spec commit + amendment are the starting point).

**PR shape:** Two PRs — PR A covers Tasks 1–11 (foundations + MCP tools + CLI subcommands; AI and CLI gain the file API). PR B covers Tasks 12–14 (migrations + audit + docs).

---

## File Structure

### New files

**Foundations / port + adapters:**
- `src/jobhound/application/revisions.py` — `Revision` NewType
- `src/jobhound/application/file_service.py` — orchestration service
- `src/jobhound/infrastructure/storage/__init__.py`
- `src/jobhound/infrastructure/storage/protocols.py` — `FileStore` Protocol
- `src/jobhound/infrastructure/storage/git_local.py` — `GitLocalFileStore`

**MCP + CLI peers:**
- `src/jobhound/mcp/tools/files.py` — 7 file tools
- `src/jobhound/commands/file.py` — `jh file` subcommand group

**Test scaffolding + tests:**
- `tests/storage/__init__.py`
- `tests/storage/in_memory.py` — `InMemoryFileStore` test adapter
- `tests/application/test_revisions.py`
- `tests/application/test_file_service.py`
- `tests/infrastructure/__init__.py`
- `tests/infrastructure/storage/__init__.py`
- `tests/infrastructure/storage/test_git_local_store.py`
- `tests/mcp/test_tools_files.py`
- `tests/test_cmd_file.py`

### Modified files (PR A)

- `src/jobhound/mcp/tools/reads.py` — `list_files` and `read_file` MOVE OUT to `mcp/tools/files.py`
- `src/jobhound/mcp/server.py` — register new `files` module, drop the moved-out registrations
- `src/jobhound/mcp/errors.py` — add 8 new error codes + mapping for `FileServiceError` subclasses
- `src/jobhound/cli.py` — register `jh file` subcommand group
- `tests/mcp/test_tools_reads.py` — remove test cases for moved tools (they're tested in `test_tools_files.py`)
- `tests/mcp/conftest.py` — add `in_memory_store` fixture

### Modified files (PR B — migrations)

- `src/jobhound/application/ops_service.py` — `add_note` delegates to `file_service.append`
- `src/jobhound/commands/log.py` — correspondence-write delegates to `file_service.write`
- `src/jobhound/application/query.py` — `list_files` / `read_file` delegate to `file_service` (or stay as thin Phase 3a wrappers; see Task 13's note)
- `README.md` — document `jh file` subcommands and the MCP file tools

---

## Task 1: Foundations — `Revision`, `FileStore` Protocol, `InMemoryFileStore`

**Goal:** Set up the type vocabulary and a test fixture that proves the port abstraction works without any real storage. Nothing else changes — this task ships green tests but no production behaviour yet.

**Files:**
- Create: `src/jobhound/application/revisions.py`
- Create: `src/jobhound/infrastructure/storage/__init__.py`
- Create: `src/jobhound/infrastructure/storage/protocols.py`
- Create: `tests/storage/__init__.py`
- Create: `tests/storage/in_memory.py`
- Create: `tests/application/test_revisions.py`

- [ ] **Step 1: Write the failing tests for `Revision`**

Create `tests/application/test_revisions.py`:

```python
"""Tests for application/revisions.py — Revision NewType."""

from __future__ import annotations

from jobhound.application.revisions import Revision


def test_revision_is_str() -> None:
    r = Revision("abc123")
    assert r == "abc123"
    assert isinstance(r, str)


def test_revision_equality() -> None:
    a = Revision("abc123")
    b = Revision("abc123")
    c = Revision("def456")
    assert a == b
    assert a != c
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/application/test_revisions.py -v
```

Expected: ModuleNotFoundError on `jobhound.application.revisions`.

- [ ] **Step 3: Create `revisions.py`**

```python
# src/jobhound/application/revisions.py
"""Opaque content-identity for files inside an opportunity directory.

`Revision` is a NewType over `str`. Callers MUST NOT inspect its
structure — they only compare two revisions for equality. The concrete
representation depends on the FileStore adapter:

  - GitLocalFileStore: git blob SHA (`git hash-object`)
  - S3FileStore (future): S3 ETag
  - InMemoryFileStore (tests): sha1 of content

Adapters compute revisions via `FileStore.compute_revision`. The
application layer never computes a revision itself — that decision is
deliberately the adapter's.
"""

from __future__ import annotations

from typing import NewType

Revision = NewType("Revision", str)
```

- [ ] **Step 4: Run revision tests to verify pass**

```bash
uv run pytest tests/application/test_revisions.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Create the storage subpackage with the Protocol**

Create `src/jobhound/infrastructure/storage/__init__.py` (empty).

Create `src/jobhound/infrastructure/storage/protocols.py`:

```python
"""FileStore Protocol — the port between application/file_service.py and
any concrete storage backend (local git, S3, sqlite, in-memory, ...).

Every mutating method must be atomic and durable on return. Callers do
not call a separate `commit` — there is no transaction primitive.
"""

from __future__ import annotations

from typing import Protocol

from jobhound.application.revisions import Revision
from jobhound.application.snapshots import FileEntry


class FileStore(Protocol):
    """Backend-agnostic file CRUD inside an opportunity directory."""

    def list(self, opp_slug: str) -> list[FileEntry]:
        """Return every non-hidden file under the opp's storage,
        recursive. Names relative to the opp's root."""
        ...

    def exists(self, opp_slug: str, filename: str) -> bool:
        """True iff the file exists for this opp."""
        ...

    def read(self, opp_slug: str, filename: str) -> bytes:
        """Return the raw bytes. Raises FileNotFoundError if missing."""
        ...

    def write(
        self,
        opp_slug: str,
        filename: str,
        content: bytes,
        *,
        commit_message: str,
    ) -> None:
        """Atomically replace (or create) the file with the given bytes."""
        ...

    def append(
        self,
        opp_slug: str,
        filename: str,
        content: bytes,
        *,
        commit_message: str,
    ) -> None:
        """Atomically append bytes to the file (or create if missing)."""
        ...

    def delete(
        self,
        opp_slug: str,
        filename: str,
        *,
        commit_message: str,
    ) -> None:
        """Atomically remove the file. Raises FileNotFoundError if missing."""
        ...

    def compute_revision(self, opp_slug: str, filename: str) -> Revision:
        """Return the opaque content-identity for the file as it currently
        exists. Raises FileNotFoundError if missing."""
        ...
```

- [ ] **Step 6: Create the `InMemoryFileStore` test fixture**

Create `tests/storage/__init__.py` (empty).

Create `tests/storage/in_memory.py`:

```python
"""InMemoryFileStore — fast deterministic FileStore for tests.

Used by application-layer tests (`tests/application/test_file_service.py`,
`tests/mcp/test_tools_files.py`). Proves the port abstraction is real:
if the application layer leaks any git-specific assumption, tests
running against this adapter will fail.

Not exported as production code; this lives under tests/storage/.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from jobhound.application.revisions import Revision
from jobhound.application.snapshots import FileEntry


class InMemoryFileStore:
    """Dict-backed FileStore. Each (slug, filename) → bytes."""

    def __init__(self) -> None:
        self._files: dict[tuple[str, str], bytes] = {}
        self._mtimes: dict[tuple[str, str], datetime] = {}
        self.commit_log: list[str] = []  # observable for tests

    def list(self, opp_slug: str) -> list[FileEntry]:
        out: list[FileEntry] = []
        for (slug, name), content in self._files.items():
            if slug != opp_slug:
                continue
            out.append(FileEntry(
                name=name, size=len(content),
                mtime=self._mtimes[(slug, name)],
            ))
        out.sort(key=lambda e: e.name)
        return out

    def exists(self, opp_slug: str, filename: str) -> bool:
        return (opp_slug, filename) in self._files

    def read(self, opp_slug: str, filename: str) -> bytes:
        try:
            return self._files[(opp_slug, filename)]
        except KeyError:
            raise FileNotFoundError(f"{opp_slug}/{filename}") from None

    def write(
        self, opp_slug: str, filename: str, content: bytes,
        *, commit_message: str,
    ) -> None:
        self._files[(opp_slug, filename)] = content
        self._mtimes[(opp_slug, filename)] = datetime.now(UTC)
        self.commit_log.append(commit_message)

    def append(
        self, opp_slug: str, filename: str, content: bytes,
        *, commit_message: str,
    ) -> None:
        existing = self._files.get((opp_slug, filename), b"")
        self._files[(opp_slug, filename)] = existing + content
        self._mtimes[(opp_slug, filename)] = datetime.now(UTC)
        self.commit_log.append(commit_message)

    def delete(
        self, opp_slug: str, filename: str,
        *, commit_message: str,
    ) -> None:
        if (opp_slug, filename) not in self._files:
            raise FileNotFoundError(f"{opp_slug}/{filename}")
        del self._files[(opp_slug, filename)]
        del self._mtimes[(opp_slug, filename)]
        self.commit_log.append(commit_message)

    def compute_revision(self, opp_slug: str, filename: str) -> Revision:
        if (opp_slug, filename) not in self._files:
            raise FileNotFoundError(f"{opp_slug}/{filename}")
        content = self._files[(opp_slug, filename)]
        return Revision(hashlib.sha1(content).hexdigest())  # noqa: S324
```

- [ ] **Step 7: Add a smoke test for `InMemoryFileStore`**

Create `tests/storage/test_in_memory.py`:

```python
"""Smoke tests for InMemoryFileStore — confirms it satisfies the
FileStore Protocol's behavioural contract."""

from __future__ import annotations

import pytest

from tests.storage.in_memory import InMemoryFileStore


def test_write_then_read_round_trips() -> None:
    store = InMemoryFileStore()
    store.write("acme", "cv.md", b"hello\n", commit_message="x")
    assert store.read("acme", "cv.md") == b"hello\n"


def test_exists_reflects_writes_and_deletes() -> None:
    store = InMemoryFileStore()
    assert not store.exists("acme", "cv.md")
    store.write("acme", "cv.md", b"x", commit_message="write")
    assert store.exists("acme", "cv.md")
    store.delete("acme", "cv.md", commit_message="delete")
    assert not store.exists("acme", "cv.md")


def test_append_concatenates() -> None:
    store = InMemoryFileStore()
    store.append("acme", "notes.md", b"line1\n", commit_message="a")
    store.append("acme", "notes.md", b"line2\n", commit_message="b")
    assert store.read("acme", "notes.md") == b"line1\nline2\n"


def test_revision_changes_with_content() -> None:
    store = InMemoryFileStore()
    store.write("acme", "x", b"a", commit_message="x")
    r1 = store.compute_revision("acme", "x")
    store.write("acme", "x", b"b", commit_message="x")
    r2 = store.compute_revision("acme", "x")
    assert r1 != r2


def test_revision_stable_for_identical_content() -> None:
    store = InMemoryFileStore()
    store.write("acme", "x", b"hello", commit_message="x")
    store.write("acme", "y", b"hello", commit_message="x")
    assert store.compute_revision("acme", "x") == store.compute_revision("acme", "y")


def test_read_missing_raises_file_not_found() -> None:
    store = InMemoryFileStore()
    with pytest.raises(FileNotFoundError):
        store.read("acme", "missing.md")


def test_list_sorted_and_scoped_to_slug() -> None:
    store = InMemoryFileStore()
    store.write("acme", "b.md", b"x", commit_message="x")
    store.write("acme", "a.md", b"x", commit_message="x")
    store.write("beta", "z.md", b"x", commit_message="x")
    names = [e.name for e in store.list("acme")]
    assert names == ["a.md", "b.md"]


def test_commit_log_observable() -> None:
    store = InMemoryFileStore()
    store.write("acme", "x", b"a", commit_message="msg1")
    store.append("acme", "x", b"b", commit_message="msg2")
    assert store.commit_log == ["msg1", "msg2"]
```

- [ ] **Step 8: Run all foundation tests + full suite**

```bash
uv run pytest tests/application/test_revisions.py tests/storage/test_in_memory.py -v
uv run pytest -q
```

Expected: 10 new tests pass; full suite is 307 + 10 = 317.

- [ ] **Step 9: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/revisions.py src/jobhound/infrastructure/storage/ \
        tests/storage/ tests/application/test_revisions.py
git commit -m "feat(storage): add Revision NewType + FileStore Protocol + InMemoryFileStore"
```

---

## Task 2: `GitLocalFileStore` adapter

**Goal:** The first (today's only) concrete `FileStore` adapter. Backs every operation with a git commit. Revision is `git hash-object` blob SHA.

**Files:**
- Create: `src/jobhound/infrastructure/storage/git_local.py`
- Create: `tests/infrastructure/__init__.py`
- Create: `tests/infrastructure/storage/__init__.py`
- Create: `tests/infrastructure/storage/test_git_local_store.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/infrastructure/__init__.py` and `tests/infrastructure/storage/__init__.py` (both empty).

Create `tests/infrastructure/storage/test_git_local_store.py`:

```python
"""Tests for GitLocalFileStore — the git-backed FileStore adapter."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from jobhound.infrastructure.config import Config
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository
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
    # Seed an empty opp dir
    (db_root / "opportunities" / "2026-05-acme").mkdir()
    subprocess.run(["git", "-C", str(db_root), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_root), "commit", "-m", "seed", "--quiet"],
        check=True, capture_output=True,
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
        capture_output=True, text=True, check=True,
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
        capture_output=True, text=True, check=True,
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
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert revision == expected


def test_subdirectory_write_creates_parent(tmp_path: Path) -> None:
    store, paths = _seeded(tmp_path)
    store.write(
        "2026-05-acme", "correspondence/2026-05-01-intro.md",
        b"hi\n", commit_message="x",
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/infrastructure/storage/test_git_local_store.py -v
```

Expected: ModuleNotFoundError on `jobhound.infrastructure.storage.git_local`.

- [ ] **Step 3: Implement `GitLocalFileStore`**

Create `src/jobhound/infrastructure/storage/git_local.py`:

```python
"""GitLocalFileStore — the git-backed FileStore adapter.

Files live under <paths.opportunities_dir>/<slug>/ inside a git-tracked
data root. Every mutation produces one git commit. Revision is the git
blob SHA via `git hash-object`.

Path-traversal is rejected at the adapter boundary by resolving the
target and confirming it lies under the opp dir.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from jobhound.application.revisions import Revision
from jobhound.application.snapshots import FileEntry
from jobhound.infrastructure.paths import Paths


class GitLocalFileStore:
    """FileStore backed by the local git data root."""

    def __init__(self, paths: Paths) -> None:
        self._paths = paths

    # ---- helpers --------------------------------------------------------

    def _opp_dir(self, slug: str) -> Path:
        return self._paths.opportunities_dir / slug

    def _resolve(self, slug: str, filename: str) -> Path:
        """Resolve to an absolute path under the opp dir. Rejects traversal."""
        opp = self._opp_dir(slug)
        opp_root = opp.resolve()
        target = (opp / filename).resolve()
        if not target.is_relative_to(opp_root):
            raise ValueError(
                f"filename must be inside the opportunity directory: {filename}",
            )
        return target

    def _git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(self._paths.db_root), *args],
            check=True, capture_output=True,
        )

    # ---- FileStore interface --------------------------------------------

    def list(self, opp_slug: str) -> list[FileEntry]:
        opp = self._opp_dir(opp_slug)
        if not opp.exists():
            return []
        entries: list[FileEntry] = []
        for path in sorted(opp.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(opp)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if rel.name == "meta.toml":  # excluded from file-API listing
                continue
            stat = path.stat()
            entries.append(FileEntry(
                name=rel.as_posix(),
                size=stat.st_size,
                mtime=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            ))
        return entries

    def exists(self, opp_slug: str, filename: str) -> bool:
        return self._resolve(opp_slug, filename).is_file()

    def read(self, opp_slug: str, filename: str) -> bytes:
        target = self._resolve(opp_slug, filename)
        if not target.is_file():
            raise FileNotFoundError(f"{opp_slug}/{filename}")
        return target.read_bytes()

    def write(
        self, opp_slug: str, filename: str, content: bytes,
        *, commit_message: str,
    ) -> None:
        target = self._resolve(opp_slug, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        self._git("add", str(target))
        self._git("commit", "-m", commit_message)

    def append(
        self, opp_slug: str, filename: str, content: bytes,
        *, commit_message: str,
    ) -> None:
        target = self._resolve(opp_slug, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab") as fh:
            fh.write(content)
        self._git("add", str(target))
        self._git("commit", "-m", commit_message)

    def delete(
        self, opp_slug: str, filename: str,
        *, commit_message: str,
    ) -> None:
        target = self._resolve(opp_slug, filename)
        if not target.is_file():
            raise FileNotFoundError(f"{opp_slug}/{filename}")
        target.unlink()
        self._git("add", "-A", str(target))
        self._git("commit", "-m", commit_message)

    def compute_revision(self, opp_slug: str, filename: str) -> Revision:
        target = self._resolve(opp_slug, filename)
        if not target.is_file():
            raise FileNotFoundError(f"{opp_slug}/{filename}")
        result = subprocess.run(
            ["git", "hash-object", str(target)],
            capture_output=True, text=True, check=True,
        )
        return Revision(result.stdout.strip())
```

- [ ] **Step 4: Run tests + full suite**

```bash
uv run pytest tests/infrastructure/storage/test_git_local_store.py -v
uv run pytest -q
```

Expected: 8 new tests pass; full suite 317 + 8 = 325.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/infrastructure/storage/git_local.py tests/infrastructure/
git commit -m "feat(storage): add GitLocalFileStore — git-backed FileStore adapter"
```

---

## Task 3: `file_service` — read, list, foundations

**Goal:** The cheap half of `file_service.py` — `read`, `list`, the `WriteResult` dataclass, and a `_validate_filename` helper (rejects `meta.toml`, hidden files, traversal). No state machine yet; that lands in Task 4.

**Files:**
- Create: `src/jobhound/application/file_service.py`
- Create: `tests/application/test_file_service.py`
- Create: `tests/application/conftest.py` (add `in_memory_store` fixture if not already there from earlier work — check first)

- [ ] **Step 1: Check/add the `in_memory_store` fixture**

Read `tests/application/conftest.py`. If it doesn't already have an `in_memory_store` fixture, append:

```python
import pytest

from tests.storage.in_memory import InMemoryFileStore


@pytest.fixture
def in_memory_store() -> InMemoryFileStore:
    return InMemoryFileStore()
```

(`query_paths` is already promoted to `tests/conftest.py` from Phase 4; nothing else to do.)

- [ ] **Step 2: Write the failing tests**

Create `tests/application/test_file_service.py`:

```python
"""Tests for application/file_service.py — reads, listing, validation."""

from __future__ import annotations

import pytest

from jobhound.application import file_service
from jobhound.application.file_service import InvalidFilenameError, MetaTomlProtectedError
from jobhound.application.revisions import Revision
from tests.storage.in_memory import InMemoryFileStore


def test_read_returns_bytes_and_revision(in_memory_store: InMemoryFileStore) -> None:
    in_memory_store.write("acme", "cv.md", b"hello\n", commit_message="seed")
    content, revision = file_service.read(in_memory_store, "acme", "cv.md")
    assert content == b"hello\n"
    assert isinstance(revision, str)


def test_read_missing_raises(in_memory_store: InMemoryFileStore) -> None:
    with pytest.raises(FileNotFoundError):
        file_service.read(in_memory_store, "acme", "missing.md")


def test_list_returns_entries(in_memory_store: InMemoryFileStore) -> None:
    in_memory_store.write("acme", "cv.md", b"a", commit_message="s")
    in_memory_store.write("acme", "notes.md", b"b", commit_message="s")
    entries = file_service.list_(in_memory_store, "acme")
    names = [e.name for e in entries]
    assert names == ["cv.md", "notes.md"]


def test_validate_rejects_meta_toml(in_memory_store: InMemoryFileStore) -> None:
    with pytest.raises(MetaTomlProtectedError) as exc:
        file_service._validate_filename("meta.toml")
    assert "meta.toml" in str(exc.value)
    # use_instead should be populated for the MCP adapter to surface
    assert hasattr(exc.value, "use_instead")
    assert exc.value.use_instead  # non-empty list of suggested tools


def test_validate_rejects_hidden(in_memory_store: InMemoryFileStore) -> None:
    with pytest.raises(InvalidFilenameError):
        file_service._validate_filename(".DS_Store")


def test_validate_rejects_subdir_hidden() -> None:
    with pytest.raises(InvalidFilenameError):
        file_service._validate_filename("correspondence/.hidden")


def test_validate_rejects_empty() -> None:
    with pytest.raises(InvalidFilenameError):
        file_service._validate_filename("")


def test_validate_allows_normal_and_subdir() -> None:
    file_service._validate_filename("cv.md")
    file_service._validate_filename("correspondence/2026-05-01-intro.md")
```

- [ ] **Step 3: Run to confirm fail**

```bash
uv run pytest tests/application/test_file_service.py -v
```

Expected: ModuleNotFoundError on `jobhound.application.file_service`.

- [ ] **Step 4: Implement the foundations of `file_service.py`**

Create `src/jobhound/application/file_service.py`:

```python
"""file_service — uniform file CRUD over a FileStore port.

The application layer of the file API. Depends ONLY on the FileStore
Protocol (in infrastructure/storage/protocols.py). The adapter chosen
at call time is what determines the backing (git local, S3, ...).

This module owns:
  - filename validation (path traversal, meta.toml protection, hidden files)
  - the 6-case write state machine (Task 4)
  - 3-way merge orchestration via git merge-file (Task 4)

Errors raised by this module are typed exceptions; the MCP and CLI
adapters translate them into protocol-appropriate responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from jobhound.application.revisions import Revision
from jobhound.application.snapshots import FileEntry
from jobhound.infrastructure.storage.protocols import FileStore


# Tools that the AI should call instead of write_file on meta.toml.
_META_USE_INSTEAD: tuple[str, ...] = (
    "set_status", "set_priority", "set_source", "set_location",
    "set_comp_range", "set_first_contact", "set_applied_on",
    "set_last_activity", "set_next_action",
    "apply_to", "log_interaction", "withdraw_from", "mark_ghosted",
    "accept_offer", "decline_offer",
    "add_tag", "remove_tag", "add_contact", "set_link",
    "archive_opportunity", "delete_opportunity",
)


# ---- Exceptions ---------------------------------------------------------


class FileServiceError(Exception):
    """Base class for file_service exceptions."""


class InvalidFilenameError(FileServiceError):
    """Filename failed validation (hidden, empty, traversal, etc.)."""

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(f"invalid filename {filename!r}: {reason}")
        self.filename = filename
        self.reason = reason


class MetaTomlProtectedError(FileServiceError):
    """Write attempted on meta.toml."""

    def __init__(self, filename: str = "meta.toml") -> None:
        super().__init__(
            f"{filename} is protected; use a structured tool instead",
        )
        self.filename = filename
        self.use_instead: tuple[str, ...] = _META_USE_INSTEAD


# ---- Validation ---------------------------------------------------------


def _validate_filename(filename: str) -> None:
    """Reject meta.toml, hidden parts, empty names, and traversal patterns.

    Path-traversal *resolution* happens at the adapter (GitLocalFileStore)
    via Path.resolve + is_relative_to. This function rejects the obvious
    bad shapes earlier.
    """
    if not filename:
        raise InvalidFilenameError(filename, "empty filename")
    parts = PurePosixPath(filename).parts
    if not parts:
        raise InvalidFilenameError(filename, "no path components")
    if filename == "meta.toml" or filename.endswith("/meta.toml"):
        raise MetaTomlProtectedError(filename)
    for part in parts:
        if part.startswith("."):
            raise InvalidFilenameError(filename, f"hidden component: {part!r}")
        if part in ("..",):
            raise InvalidFilenameError(filename, "parent traversal")


# ---- WriteResult --------------------------------------------------------


@dataclass(frozen=True)
class WriteResult:
    """Successful write outcome."""

    revision: Revision
    merged: bool = False


# ---- Public read operations ---------------------------------------------


def read(
    store: FileStore, slug: str, filename: str,
) -> tuple[bytes, Revision]:
    """Read a file's bytes and current revision.

    Raises FileNotFoundError if the file does not exist.
    """
    _validate_filename(filename)  # rejects meta.toml etc. even for reads
    content = store.read(slug, filename)
    revision = store.compute_revision(slug, filename)
    return content, revision


def list_(store: FileStore, slug: str) -> list[FileEntry]:
    """List non-hidden, non-meta.toml files under the opp dir."""
    return store.list(slug)
```

Note: `_validate_filename` rejects `meta.toml` for both reads and writes, which is **stricter than the spec.** The spec allows `meta.toml` reads for diagnostics; we'll relax this in Task 4 when writes land. For now, the stricter form keeps Task 3 self-contained.

Actually — re-reading the spec, it says `meta.toml` reads stay allowed. Let me adjust the implementation: split validation into `_validate_filename_for_read` (no meta.toml block) and `_validate_filename_for_write` (with block). Or pass a flag.

Simplest: take a `for_write: bool = True` kwarg.

Update `_validate_filename`:

```python
def _validate_filename(filename: str, *, for_write: bool = True) -> None:
    if not filename:
        raise InvalidFilenameError(filename, "empty filename")
    parts = PurePosixPath(filename).parts
    if not parts:
        raise InvalidFilenameError(filename, "no path components")
    if for_write and (filename == "meta.toml" or filename.endswith("/meta.toml")):
        raise MetaTomlProtectedError(filename)
    for part in parts:
        if part.startswith("."):
            raise InvalidFilenameError(filename, f"hidden component: {part!r}")
        if part == "..":
            raise InvalidFilenameError(filename, "parent traversal")
```

Then `read()` calls `_validate_filename(filename, for_write=False)`.

Update the test for read to remove the `meta.toml` rejection (or add a separate `test_read_allows_meta_toml`).

- [ ] **Step 5: Add a meta.toml-read-allowed test**

Append to `tests/application/test_file_service.py`:

```python
def test_read_allows_meta_toml(in_memory_store: InMemoryFileStore) -> None:
    """Reads of meta.toml are explicitly allowed for diagnostics."""
    in_memory_store.write("acme", "meta.toml", b'company = "x"\n', commit_message="seed")
    content, _ = file_service.read(in_memory_store, "acme", "meta.toml")
    assert b"company" in content
```

- [ ] **Step 6: Run, confirm pass**

```bash
uv run pytest tests/application/test_file_service.py -v
uv run pytest -q
```

Expected: 9 file_service tests pass; full suite 325 + 9 = 334.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/file_service.py tests/application/test_file_service.py \
        tests/application/conftest.py
git commit -m "feat(application): scaffold file_service with read/list/validation"
```

---

## Task 4: `file_service.write` — 6-case state machine + 3-way merge

**Goal:** The big one. Implements the conflict-detection state machine and `git merge-file`-based 3-way merge for text files. Adds all the conflict exception types.

**Files:**
- Modify: `src/jobhound/application/file_service.py` (extend)
- Modify: `tests/application/test_file_service.py` (add ~12 tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/application/test_file_service.py`:

```python
from jobhound.application.file_service import (
    BinaryConflictError,
    FileDisappearedError,
    FileExistsConflictError,
    TextConflictError,
    write,
)


def test_write_case1_clean_create(in_memory_store: InMemoryFileStore) -> None:
    """Case 1: no base_revision, file doesn't exist → clean create."""
    result = write(in_memory_store, "acme", "cv.md", b"v1")
    assert result.merged is False
    assert in_memory_store.read("acme", "cv.md") == b"v1"


def test_write_case2_file_exists_no_overwrite(in_memory_store: InMemoryFileStore) -> None:
    """Case 2: no base_revision, file exists, overwrite=False → conflict."""
    in_memory_store.write("acme", "cv.md", b"v1", commit_message="seed")
    with pytest.raises(FileExistsConflictError) as exc:
        write(in_memory_store, "acme", "cv.md", b"v2")
    assert exc.value.filename == "cv.md"
    assert exc.value.current_revision  # populated


def test_write_case3_blind_overwrite(in_memory_store: InMemoryFileStore) -> None:
    """Case 3: no base_revision, file exists, overwrite=True → succeeds."""
    in_memory_store.write("acme", "cv.md", b"v1", commit_message="seed")
    result = write(in_memory_store, "acme", "cv.md", b"v2", overwrite=True)
    assert result.merged is False
    assert in_memory_store.read("acme", "cv.md") == b"v2"


def test_write_case4_file_disappeared(in_memory_store: InMemoryFileStore) -> None:
    """Case 4: base_revision provided but file is gone."""
    fake_rev = Revision("deadbeef")
    with pytest.raises(FileDisappearedError) as exc:
        write(in_memory_store, "acme", "cv.md", b"v2", base_revision=fake_rev)
    assert exc.value.filename == "cv.md"
    assert exc.value.base_revision == "deadbeef"


def test_write_case5_clean_edit(in_memory_store: InMemoryFileStore) -> None:
    """Case 5: base_revision matches current disk → clean write."""
    in_memory_store.write("acme", "cv.md", b"v1", commit_message="seed")
    rev1 = in_memory_store.compute_revision("acme", "cv.md")
    result = write(in_memory_store, "acme", "cv.md", b"v2", base_revision=rev1)
    assert result.merged is False
    assert in_memory_store.read("acme", "cv.md") == b"v2"


def test_write_case6_text_merge_clean(in_memory_store: InMemoryFileStore) -> None:
    """Case 6, text path: 3-way merge resolves cleanly."""
    in_memory_store.write(
        "acme", "notes.md", b"line1\nline2\n", commit_message="seed",
    )
    rev1 = in_memory_store.compute_revision("acme", "notes.md")
    # "Other" change: append line3
    in_memory_store.write(
        "acme", "notes.md", b"line1\nline2\nline3\n", commit_message="other",
    )
    # AI's edit: prepend a heading on the base
    result = write(
        in_memory_store, "acme", "notes.md",
        b"# Notes\nline1\nline2\n",
        base_revision=rev1,
    )
    assert result.merged is True
    final = in_memory_store.read("acme", "notes.md")
    assert b"# Notes" in final
    assert b"line3" in final


def test_write_case6_text_merge_conflict(in_memory_store: InMemoryFileStore) -> None:
    """Case 6, text path: overlapping edits cause merge conflict."""
    in_memory_store.write(
        "acme", "notes.md", b"line1\nline2\n", commit_message="seed",
    )
    rev1 = in_memory_store.compute_revision("acme", "notes.md")
    # Both edits change line2 differently
    in_memory_store.write(
        "acme", "notes.md", b"line1\nline2-OTHER\n", commit_message="other",
    )
    with pytest.raises(TextConflictError) as exc:
        write(
            in_memory_store, "acme", "notes.md",
            b"line1\nline2-OURS\n",
            base_revision=rev1,
        )
    assert exc.value.filename == "notes.md"
    assert "<<<<<<<" in exc.value.conflict_markers


def test_write_case6_binary_conflict(in_memory_store: InMemoryFileStore) -> None:
    """Case 6, binary path: no merge, return BinaryConflictError."""
    in_memory_store.write(
        "acme", "cv.pdf", b"\x00\x01\x02v1", commit_message="seed",
    )
    rev1 = in_memory_store.compute_revision("acme", "cv.pdf")
    in_memory_store.write(
        "acme", "cv.pdf", b"\x00\x01\x02v2", commit_message="other",
    )
    with pytest.raises(BinaryConflictError) as exc:
        write(
            in_memory_store, "acme", "cv.pdf",
            b"\x00\x01\x02ai",
            base_revision=rev1,
        )
    assert exc.value.filename == "cv.pdf"
    assert exc.value.current_revision  # populated
    assert exc.value.suggested_alt_name == "cv-ai-draft.pdf"


def test_write_rejects_meta_toml(in_memory_store: InMemoryFileStore) -> None:
    with pytest.raises(MetaTomlProtectedError):
        write(in_memory_store, "acme", "meta.toml", b"x")


def test_write_rejects_hidden(in_memory_store: InMemoryFileStore) -> None:
    with pytest.raises(InvalidFilenameError):
        write(in_memory_store, "acme", ".DS_Store", b"x")


def test_write_returns_revision_on_success(in_memory_store: InMemoryFileStore) -> None:
    result = write(in_memory_store, "acme", "cv.md", b"v1")
    expected = in_memory_store.compute_revision("acme", "cv.md")
    assert result.revision == expected


def test_write_commit_message_format(in_memory_store: InMemoryFileStore) -> None:
    """Verify the file_service uses a consistent commit-message shape."""
    write(in_memory_store, "acme", "cv.md", b"v1")
    assert in_memory_store.commit_log == ["file: write acme/cv.md"]
```

- [ ] **Step 2: Run, confirm tests fail**

```bash
uv run pytest tests/application/test_file_service.py -v -k "case or rejects or returns_revision or commit_message"
```

Expected: collection fails on the new error class imports (they don't exist yet).

- [ ] **Step 3: Add the exception types + `write` function**

Append to `src/jobhound/application/file_service.py`:

```python
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


class FileExistsConflictError(FileServiceError):
    """Case 2: file exists, no overwrite intent."""

    def __init__(self, filename: str, current_revision: Revision) -> None:
        super().__init__(f"file exists: {filename}")
        self.filename = filename
        self.current_revision = current_revision


class FileDisappearedError(FileServiceError):
    """Case 4: file the AI was editing no longer exists."""

    def __init__(self, filename: str, base_revision: Revision) -> None:
        super().__init__(
            f"file disappeared while editing: {filename}",
        )
        self.filename = filename
        self.base_revision = base_revision


class TextConflictError(FileServiceError):
    """Case 6, text path: 3-way merge failed."""

    def __init__(
        self, filename: str,
        base_revision: Revision, theirs_revision: Revision,
        conflict_markers: str,
    ) -> None:
        super().__init__(f"text merge conflict on {filename}")
        self.filename = filename
        self.base_revision = base_revision
        self.theirs_revision = theirs_revision
        self.conflict_markers = conflict_markers


class BinaryConflictError(FileServiceError):
    """Case 6, binary path: divergent binary file, no merge possible."""

    def __init__(
        self, filename: str,
        base_revision: Revision, current_revision: Revision,
        current_size: int, current_mtime: datetime,
        suggested_alt_name: str,
    ) -> None:
        super().__init__(f"binary conflict on {filename}")
        self.filename = filename
        self.base_revision = base_revision
        self.current_revision = current_revision
        self.current_size = current_size
        self.current_mtime = current_mtime
        self.suggested_alt_name = suggested_alt_name


def _suggest_alt_name(filename: str) -> str:
    """Compute a 'safe alt' name for the AI's version on a binary conflict."""
    path = PurePosixPath(filename)
    return str(path.with_stem(f"{path.stem}-ai-draft"))


def _is_text(content: bytes) -> bool:
    """utf-8-decodable → treat as text."""
    try:
        content.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _three_way_merge(base: bytes, ours: bytes, theirs: bytes) -> tuple[bytes, bool]:
    """Run `git merge-file --stdout` on the three sides. Returns
    (merged_content, clean_bool). On non-clean merges, merged_content
    contains conflict markers and clean_bool is False.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        base_p = tmpdir / "base"
        ours_p = tmpdir / "ours"
        theirs_p = tmpdir / "theirs"
        base_p.write_bytes(base)
        ours_p.write_bytes(ours)
        theirs_p.write_bytes(theirs)
        result = subprocess.run(
            ["git", "merge-file", "--stdout", str(ours_p), str(base_p), str(theirs_p)],
            capture_output=True,
        )
        return result.stdout, result.returncode == 0


def write(
    store: FileStore,
    slug: str,
    filename: str,
    content: bytes,
    *,
    base_revision: Revision | None = None,
    overwrite: bool = False,
) -> WriteResult:
    """Write a file with optimistic-concurrency conflict detection.

    Implements the six-case decision matrix from the spec.
    """
    _validate_filename(filename, for_write=True)
    commit_msg = f"file: write {slug}/{filename}"

    file_exists = store.exists(slug, filename)

    if base_revision is None:
        if not file_exists:
            # Case 1: clean create
            store.write(slug, filename, content, commit_message=commit_msg)
            return WriteResult(
                revision=store.compute_revision(slug, filename), merged=False,
            )
        if not overwrite:
            # Case 2: refuse
            raise FileExistsConflictError(
                filename, store.compute_revision(slug, filename),
            )
        # Case 3: blind overwrite
        store.write(slug, filename, content, commit_message=commit_msg)
        return WriteResult(
            revision=store.compute_revision(slug, filename), merged=False,
        )

    # base_revision provided
    if not file_exists:
        # Case 4: disappeared
        raise FileDisappearedError(filename, base_revision)

    current_revision = store.compute_revision(slug, filename)
    if current_revision == base_revision:
        # Case 5: clean edit
        store.write(slug, filename, content, commit_message=commit_msg)
        return WriteResult(
            revision=store.compute_revision(slug, filename), merged=False,
        )

    # Case 6: conflict — branch on text vs binary
    current_content = store.read(slug, filename)
    if not _is_text(current_content):
        # binary conflict
        entries = store.list(slug)
        entry = next((e for e in entries if e.name == filename), None)
        if entry is None:
            # Should not happen — file exists but list didn't return it.
            # Treat as binary conflict with zero size / current time.
            raise BinaryConflictError(
                filename, base_revision, current_revision,
                current_size=len(current_content),
                current_mtime=datetime.now(),  # noqa: DTZ005 — fallback
                suggested_alt_name=_suggest_alt_name(filename),
            )
        raise BinaryConflictError(
            filename, base_revision, current_revision,
            current_size=entry.size,
            current_mtime=entry.mtime,
            suggested_alt_name=_suggest_alt_name(filename),
        )

    # text conflict: try 3-way merge
    # Reconstruct base content: in real FileStore this would require the
    # store to retain old revisions. For InMemoryFileStore and
    # GitLocalFileStore, we shell out to git for the base content if
    # the store supports it; otherwise we approximate by treating
    # `base` == `ours` (degenerate case → conflict).
    base_content = _resolve_base_content(store, base_revision, current_content)
    merged, clean = _three_way_merge(base_content, content, current_content)
    if clean:
        store.write(slug, filename, merged, commit_message=commit_msg)
        return WriteResult(
            revision=store.compute_revision(slug, filename), merged=True,
        )
    raise TextConflictError(
        filename, base_revision, current_revision,
        conflict_markers=merged.decode("utf-8", errors="replace"),
    )


def _resolve_base_content(
    store: FileStore, base_revision: Revision, current_content: bytes,
) -> bytes:
    """Reconstruct the bytes at `base_revision`.

    The Protocol doesn't (yet) expose a `read_by_revision` method, so this
    helper resolves backend-specifically:
      - GitLocalFileStore: `git cat-file -p <blob_sha>` works because the
        revision IS the blob SHA.
      - InMemoryFileStore (tests): retain a history map keyed by
        revision; see tests/storage/in_memory.py update in this task.

    If the adapter can't reconstruct, we return `current_content` as a
    fallback. That degrades the merge: base == theirs → ours wins
    cleanly via merge-file. Not optimal but safe.
    """
    if hasattr(store, "read_by_revision"):
        try:
            return store.read_by_revision(base_revision)  # type: ignore[attr-defined]
        except Exception:
            return current_content
    return current_content
```

The `_resolve_base_content` helper is the awkward bit: the Protocol as defined in Task 1 doesn't have a way to read content at a specific past revision. We have two options:

**Option A (chosen for v1):** Add `read_by_revision(revision: Revision) -> bytes` as an OPTIONAL Protocol method. Both `GitLocalFileStore` and `InMemoryFileStore` implement it. `file_service` checks `hasattr` and falls back to `current_content` if missing.

**Option B:** Make it a required Protocol method. Cleaner contract but forces every backend to maintain a revision-keyed content cache (might be expensive for some).

Going with Option A as a v1 pragmatism. Future spec revision can promote it to required.

- [ ] **Step 4: Implement `read_by_revision` on both adapters**

Append to `tests/storage/in_memory.py`:

```python
# In __init__:
self._content_by_revision: dict[str, bytes] = {}

# Update write and append to record revisions:
def write(self, ...):
    ...
    self._files[(opp_slug, filename)] = content
    self._mtimes[(opp_slug, filename)] = datetime.now(UTC)
    self._content_by_revision[hashlib.sha1(content).hexdigest()] = content
    self.commit_log.append(commit_message)

def append(self, ...):
    ...
    self._files[(opp_slug, filename)] = existing + content
    new_content = self._files[(opp_slug, filename)]
    self._content_by_revision[hashlib.sha1(new_content).hexdigest()] = new_content
    ...

def read_by_revision(self, revision: Revision) -> bytes:
    return self._content_by_revision[revision]
```

Add to `src/jobhound/infrastructure/storage/git_local.py`:

```python
def read_by_revision(self, revision: Revision) -> bytes:
    """Resolve `git cat-file -p <blob_sha>` — works for any revision
    that's ever been committed in the repo."""
    result = subprocess.run(
        ["git", "-C", str(self._paths.db_root), "cat-file", "-p", str(revision)],
        capture_output=True, check=True,
    )
    return result.stdout
```

- [ ] **Step 5: Run all file_service tests + full suite**

```bash
uv run pytest tests/application/test_file_service.py tests/infrastructure/storage/ tests/storage/ -v
uv run pytest -q
```

Expected: ~20 file_service tests pass, ~8 git_local tests pass, ~8 in_memory tests pass; full suite ~346 (334 + 12 new write tests).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/file_service.py \
        src/jobhound/infrastructure/storage/git_local.py \
        tests/storage/in_memory.py tests/application/test_file_service.py
git commit -m "feat(application): file_service.write — 6-case state machine + 3-way merge"
```

---

## Tasks 5–8: `import_`, `export`, `append`, `delete`

Each follows the same TDD-per-step pattern as Tasks 3–4. The code is much smaller than `write` (no state machine for export/append; small 3-case for delete). Each task adds 4–6 tests.

### Task 5: `file_service.import_` (path-based write)

Same state machine as `write`, but content comes from a path. Implementation:

```python
def import_(
    store: FileStore, slug: str, filename: str, src_path: Path,
    *, base_revision: Revision | None = None, overwrite: bool = False,
) -> WriteResult:
    """Write a file from a local path (server reads src_path). Identical
    state machine to write()."""
    _validate_filename(filename, for_write=True)
    if not src_path.is_file():
        raise FileNotFoundError(f"src_path does not exist: {src_path}")
    content = src_path.read_bytes()
    return write(
        store, slug, filename, content,
        base_revision=base_revision, overwrite=overwrite,
    )
```

Tests: 4 cases (clean create, file_exists conflict, clean edit, src_path missing). Commit:
```
feat(application): file_service.import_ — path-based write
```

### Task 6: `file_service.export` (server copies to AI's path)

```python
def export(
    store: FileStore, slug: str, filename: str, dst_path: Path,
    *, overwrite: bool = False,
) -> Revision:
    """Copy file content to dst_path. Returns revision at time of read.

    If dst_path exists and overwrite=False, raises FileExistsError.
    """
    _validate_filename(filename, for_write=False)
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"dst_path exists: {dst_path}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    content = store.read(slug, filename)
    dst_path.write_bytes(content)
    return store.compute_revision(slug, filename)
```

Tests: 3 (happy path, dst overwrite, missing source). Commit:
```
feat(application): file_service.export — server copies to AI's path
```

### Task 7: `file_service.append` (conflict-free additive)

```python
def append(
    store: FileStore, slug: str, filename: str, content: bytes,
) -> Revision:
    """Append bytes to a file (create if missing). No conflict detection."""
    _validate_filename(filename, for_write=True)
    commit_msg = f"file: append {slug}/{filename}"
    store.append(slug, filename, content, commit_message=commit_msg)
    return store.compute_revision(slug, filename)
```

Tests: 3 (append to existing, create-on-missing, meta.toml rejected). Commit:
```
feat(application): file_service.append — additive write, no conflicts
```

### Task 8: `file_service.delete` (3-case)

```python
class DeleteStaleBaseError(FileServiceError):
    def __init__(
        self, filename: str,
        base_revision: Revision, current_revision: Revision,
    ) -> None:
        super().__init__(f"delete with stale base revision: {filename}")
        self.filename = filename
        self.base_revision = base_revision
        self.current_revision = current_revision


def delete(
    store: FileStore, slug: str, filename: str,
    *, base_revision: Revision | None = None,
) -> Revision:
    """Delete a file. Returns the last revision before delete.

    With base_revision: refuse if revisions don't match (DeleteStaleBaseError).
    Without base_revision: delete unconditionally if file exists.
    """
    _validate_filename(filename, for_write=True)
    if not store.exists(slug, filename):
        raise FileNotFoundError(f"{slug}/{filename}")
    current = store.compute_revision(slug, filename)
    if base_revision is not None and base_revision != current:
        raise DeleteStaleBaseError(filename, base_revision, current)
    store.delete(slug, filename, commit_message=f"file: delete {slug}/{filename}")
    return current
```

Tests: 5 (no base + exists → succeeds, no base + missing → FileNotFoundError, base matches → succeeds, base mismatches → DeleteStaleBaseError, meta.toml rejected). Commit:
```
feat(application): file_service.delete — 3-case decision
```

---

## Task 9: MCP error mapping for file_service exceptions

**Goal:** Wire all the new exception types into `mcp/errors.py` so the MCP adapter returns structured responses with the AI-recovery hints from the spec.

**Files:**
- Modify: `src/jobhound/mcp/errors.py`
- Modify: `tests/mcp/test_errors.py`

- [ ] **Step 1: Add the new mappings**

In `src/jobhound/mcp/errors.py`, in `exception_to_response`, add branches for each new file_service exception. Each maps to its spec-defined error code with the structured details payload.

```python
# Imports
from jobhound.application.file_service import (
    BinaryConflictError, DeleteStaleBaseError, FileDisappearedError,
    FileExistsConflictError, InvalidFilenameError,
    MetaTomlProtectedError, TextConflictError,
)

# Inside exception_to_response(), add (before the generic ValueError branch):

if isinstance(exc, MetaTomlProtectedError):
    return tool_error_response(
        "meta_toml_protected", str(exc),
        filename=exc.filename, use_instead=list(exc.use_instead),
    )
if isinstance(exc, InvalidFilenameError):
    return tool_error_response(
        "invalid_filename", str(exc),
        filename=exc.filename, reason=exc.reason,
    )
if isinstance(exc, FileExistsConflictError):
    return tool_error_response(
        "file_exists", str(exc),
        filename=exc.filename, current_revision=exc.current_revision,
    )
if isinstance(exc, FileDisappearedError):
    return tool_error_response(
        "file_disappeared", str(exc),
        filename=exc.filename, base_revision=exc.base_revision,
    )
if isinstance(exc, BinaryConflictError):
    return tool_error_response(
        "conflict_binary", str(exc),
        filename=exc.filename,
        base_revision=exc.base_revision,
        current_revision=exc.current_revision,
        current_size=exc.current_size,
        current_mtime=exc.current_mtime.isoformat(),
        suggested_alt_name=exc.suggested_alt_name,
    )
if isinstance(exc, TextConflictError):
    return tool_error_response(
        "conflict_text", str(exc),
        filename=exc.filename,
        base_revision=exc.base_revision,
        theirs_revision=exc.theirs_revision,
        conflict_markers_output=exc.conflict_markers,
    )
if isinstance(exc, DeleteStaleBaseError):
    return tool_error_response(
        "delete_stale_base", str(exc),
        filename=exc.filename,
        base_revision=exc.base_revision,
        current_revision=exc.current_revision,
    )
if isinstance(exc, FileNotFoundError):
    # generic file_not_found — used by read/export/delete
    return tool_error_response("file_not_found", str(exc))
```

- [ ] **Step 2: Add tests in `test_errors.py`**

8 new tests, one per exception type. Each constructs the exception, runs `exception_to_response`, and asserts the code + key fields.

Example for `MetaTomlProtectedError`:
```python
def test_meta_toml_protected_error() -> None:
    resp = exception_to_response(MetaTomlProtectedError(), tool="write_file")
    assert resp["error"]["code"] == "meta_toml_protected"
    assert "set_status" in resp["error"]["details"]["use_instead"]
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/mcp/test_errors.py -v
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/mcp/errors.py tests/mcp/test_errors.py
git commit -m "feat(mcp): map file_service exceptions to MCP error codes"
```

Expected: 8 new error tests pass; full suite ~360.

---

## Task 10: MCP file tools

**Goal:** Implement the 7 MCP file tools (5 new + 2 moved). Update `mcp/server.py` to register them.

**Files:**
- Create: `src/jobhound/mcp/tools/files.py`
- Modify: `src/jobhound/mcp/tools/reads.py` — remove `list_files`, `read_file` (moved out)
- Modify: `src/jobhound/mcp/server.py` — register `files` module
- Create: `tests/mcp/test_tools_files.py`
- Modify: `tests/mcp/test_tools_reads.py` — drop tests for moved tools

- [ ] **Step 1: Create `mcp/tools/files.py`**

Skeleton matching the spec's tool table. Each tool follows the established Phase 4 pattern (call file_service, wrap in try/except, route exceptions through `exception_to_response`).

```python
# src/jobhound/mcp/tools/files.py
"""MCP file tools — route to application/file_service.

Owns 7 tools: list_files, read_file (moved here from reads.py),
write_file, import_file, export_file, append_file, delete_file.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jobhound.application import file_service
from jobhound.application.revisions import Revision
from jobhound.application.serialization import file_entry_to_dict
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore
from jobhound.infrastructure.storage.protocols import FileStore
from jobhound.mcp.errors import exception_to_response

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _store(repo: OpportunityRepository) -> FileStore:
    return GitLocalFileStore(repo.paths)


def list_files(repo: OpportunityRepository, slug: str) -> str:
    try:
        entries = file_service.list_(_store(repo), slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_files"))
    return json.dumps([file_entry_to_dict(e) for e in entries])


def read_file(repo: OpportunityRepository, slug: str, name: str) -> str:
    try:
        content, revision = file_service.read(_store(repo), slug, name)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="read_file"))
    try:
        text = content.decode("utf-8")
        return json.dumps({
            "filename": name, "content": text, "encoding": "utf-8",
            "revision": str(revision), "size": len(content),
        })
    except UnicodeDecodeError:
        return json.dumps({
            "filename": name,
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
            "revision": str(revision), "size": len(content),
        })


def write_file(
    repo: OpportunityRepository, slug: str, name: str,
    content: str,
    base_revision: str | None = None, overwrite: bool = False,
) -> str:
    try:
        result = file_service.write(
            _store(repo), slug, name, content.encode("utf-8"),
            base_revision=Revision(base_revision) if base_revision else None,
            overwrite=overwrite,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="write_file"))
    return json.dumps({"revision": str(result.revision), "merged": result.merged})


def import_file(
    repo: OpportunityRepository, slug: str, name: str,
    src_path: str,
    base_revision: str | None = None, overwrite: bool = False,
) -> str:
    try:
        result = file_service.import_(
            _store(repo), slug, name, Path(src_path),
            base_revision=Revision(base_revision) if base_revision else None,
            overwrite=overwrite,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="import_file"))
    return json.dumps({"revision": str(result.revision), "merged": result.merged})


def export_file(
    repo: OpportunityRepository, slug: str, name: str,
    dst_path: str, overwrite: bool = False,
) -> str:
    try:
        revision = file_service.export(
            _store(repo), slug, name, Path(dst_path), overwrite=overwrite,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="export_file"))
    return json.dumps({"revision": str(revision)})


def append_file(
    repo: OpportunityRepository, slug: str, name: str, content: str,
) -> str:
    try:
        revision = file_service.append(
            _store(repo), slug, name, content.encode("utf-8"),
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="append_file"))
    return json.dumps({"revision": str(revision)})


def delete_file(
    repo: OpportunityRepository, slug: str, name: str,
    base_revision: str | None = None,
) -> str:
    try:
        revision = file_service.delete(
            _store(repo), slug, name,
            base_revision=Revision(base_revision) if base_revision else None,
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="delete_file"))
    return json.dumps({"revision_before_delete": str(revision)})


def register(app: "FastMCP", repo: OpportunityRepository) -> None:
    @app.tool(name="list_files", description="List every non-hidden, non-meta file in the opp's directory.")
    def _l(slug: str) -> str:
        return list_files(repo, slug)

    @app.tool(name="read_file", description="Read a file. Returns utf-8 text or base64.")
    def _r(slug: str, name: str) -> str:
        return read_file(repo, slug, name)

    @app.tool(name="write_file",
              description="Write a file (utf-8 string content). Pass base_revision for safe edits; overwrite=True to clobber existing without base_revision.")
    def _w(slug: str, name: str, content: str,
           base_revision: str | None = None, overwrite: bool = False) -> str:
        return write_file(repo, slug, name, content, base_revision, overwrite)

    @app.tool(name="import_file",
              description="Write a file by importing from a local path. Same semantics as write_file but binary-safe and avoids streaming bytes through MCP.")
    def _i(slug: str, name: str, src_path: str,
           base_revision: str | None = None, overwrite: bool = False) -> str:
        return import_file(repo, slug, name, src_path, base_revision, overwrite)

    @app.tool(name="export_file",
              description="Export a file by copying it to a local path the AI provides. Returns the revision at time of export.")
    def _e(slug: str, name: str, dst_path: str, overwrite: bool = False) -> str:
        return export_file(repo, slug, name, dst_path, overwrite)

    @app.tool(name="append_file",
              description="Append utf-8 string content to a file. Conflict-free; no base_revision.")
    def _a(slug: str, name: str, content: str) -> str:
        return append_file(repo, slug, name, content)

    @app.tool(name="delete_file",
              description="Delete a file. Pass base_revision for safety; otherwise deletes unconditionally if the file exists.")
    def _d(slug: str, name: str, base_revision: str | None = None) -> str:
        return delete_file(repo, slug, name, base_revision)
```

- [ ] **Step 2: Update `reads.py` to drop the moved tools**

In `src/jobhound/mcp/tools/reads.py`:
- Remove `list_files`, `read_file` (the module functions)
- Remove their `@app.tool` registrations from `register`

- [ ] **Step 3: Update `server.py`**

In `src/jobhound/mcp/server.py`, after `reads.register(...)`, add:
```python
from jobhound.mcp.tools import files
files.register(app, repo)
```

- [ ] **Step 4: Add MCP tool tests**

Create `tests/mcp/test_tools_files.py` with ~15 tests covering one happy + one error per tool. Use the existing `repo` and `mcp_paths` fixtures.

Example:
```python
def test_write_file_clean_create(mcp_paths, repo):
    payload = json.loads(write_file(repo, "acme", "draft.md", "v1"))
    assert "revision" in payload
    assert payload["merged"] is False

def test_write_file_meta_toml_rejected(mcp_paths, repo):
    payload = json.loads(write_file(repo, "acme", "meta.toml", "x"))
    assert payload["error"]["code"] == "meta_toml_protected"
```

- [ ] **Step 5: Update `test_tools_reads.py` — drop moved tools**

Remove the tests that exercised `list_files` and `read_file` from `tests/mcp/test_tools_reads.py` (they live in `test_tools_files.py` now).

- [ ] **Step 6: Run + commit**

```bash
uv run pytest tests/mcp/ -v
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/mcp/tools/files.py src/jobhound/mcp/tools/reads.py \
        src/jobhound/mcp/server.py \
        tests/mcp/test_tools_files.py tests/mcp/test_tools_reads.py
git commit -m "feat(mcp): add file tools (write/import/export/append/delete); move list/read"
```

Expected: ~15 new file-tool tests; tool count 32 → 37; full suite ~375.

---

## Task 11: CLI `jh file` subcommand group

**Goal:** Peer adapter of the MCP server. Same `file_service` underneath; same conflict surface; CLI ergonomics on top.

**Files:**
- Create: `src/jobhound/commands/file.py`
- Modify: `src/jobhound/cli.py` — register `jh file` subcommand group
- Create: `tests/test_cmd_file.py`

- [ ] **Step 1: Implement `commands/file.py` with all 5 subcommands**

Cyclopts supports sub-apps via `App(name="file")` and nesting. Construction:

```python
# src/jobhound/commands/file.py
"""`jh file` subcommand group — peer of the MCP file tools."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from jobhound.application import file_service
from jobhound.application.file_service import (
    BinaryConflictError, DeleteStaleBaseError, FileDisappearedError,
    FileExistsConflictError, InvalidFilenameError,
    MetaTomlProtectedError, TextConflictError,
)
from jobhound.application.revisions import Revision
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

app = App(name="file", help="Manage files inside an opportunity directory.")


def _store():
    cfg = load_config()
    paths = paths_from_config(cfg)
    return GitLocalFileStore(paths)


def _handle(exc: Exception) -> None:
    """Print an error message and exit non-zero."""
    if isinstance(exc, MetaTomlProtectedError):
        tools = ", ".join(exc.use_instead[:6]) + ", ..."
        print(f"jh: meta.toml is protected; use one of: {tools}", file=sys.stderr)
    elif isinstance(exc, InvalidFilenameError):
        print(f"jh: invalid filename: {exc.reason}", file=sys.stderr)
    elif isinstance(exc, FileExistsConflictError):
        print(f"jh: file already exists: {exc.filename} (revision {exc.current_revision[:8]}); pass --overwrite", file=sys.stderr)
    elif isinstance(exc, FileDisappearedError):
        print(f"jh: file disappeared while editing: {exc.filename}", file=sys.stderr)
    elif isinstance(exc, BinaryConflictError):
        print(f"jh: binary conflict on {exc.filename}; suggested alt name: {exc.suggested_alt_name}", file=sys.stderr)
    elif isinstance(exc, TextConflictError):
        print(f"jh: text conflict on {exc.filename}:", file=sys.stderr)
        print(exc.conflict_markers, file=sys.stderr)
    elif isinstance(exc, DeleteStaleBaseError):
        print(f"jh: stale base revision; current is {exc.current_revision[:8]}", file=sys.stderr)
    elif isinstance(exc, FileNotFoundError):
        print(f"jh: file not found: {exc}", file=sys.stderr)
    else:
        print(f"jh: error: {exc}", file=sys.stderr)
    raise SystemExit(1)


@app.command(name="list")
def list_(slug: str) -> None:
    """List files inside an opportunity directory."""
    try:
        entries = file_service.list_(_store(), slug)
    except Exception as exc:
        _handle(exc)
        return
    for e in entries:
        print(f"  {e.name:50s}  {e.size:>8d}  {e.mtime.isoformat()}")


@app.command(name="show")
def show(
    slug: str, name: str, /,
    *, out: Annotated[Path | None, Parameter(name=["--out"])] = None,
) -> None:
    """Show a file's content (or export it to a path)."""
    try:
        if out is not None:
            file_service.export(_store(), slug, name, out)
            print(f"exported: {name} → {out}")
        else:
            content, _ = file_service.read(_store(), slug, name)
            sys.stdout.buffer.write(content)
    except Exception as exc:
        _handle(exc)


@app.command(name="write")
def write(
    slug: str, name: str, /,
    *,
    content: Annotated[str | None, Parameter(name=["--content"])] = None,
    from_: Annotated[Path | None, Parameter(name=["--from"])] = None,
    overwrite: Annotated[bool, Parameter(name=["--overwrite"], negative=())] = False,
    base_revision: Annotated[str | None, Parameter(name=["--base-revision"])] = None,
) -> None:
    """Write a file. Provide --content <str> XOR --from <path>."""
    if (content is None) == (from_ is None):
        print("jh: provide exactly one of --content or --from", file=sys.stderr)
        raise SystemExit(2)
    rev = Revision(base_revision) if base_revision else None
    try:
        if from_ is not None:
            result = file_service.import_(
                _store(), slug, name, from_,
                base_revision=rev, overwrite=overwrite,
            )
        else:
            result = file_service.write(
                _store(), slug, name, content.encode("utf-8"),
                base_revision=rev, overwrite=overwrite,
            )
    except Exception as exc:
        _handle(exc)
        return
    print(f"wrote: {name} (revision {result.revision[:8]}, merged={result.merged})")


@app.command(name="append")
def append(
    slug: str, name: str, /,
    *,
    content: Annotated[str | None, Parameter(name=["--content"])] = None,
    from_: Annotated[Path | None, Parameter(name=["--from"])] = None,
) -> None:
    """Append to a file (or create if missing). Provide --content XOR --from."""
    if (content is None) == (from_ is None):
        print("jh: provide exactly one of --content or --from", file=sys.stderr)
        raise SystemExit(2)
    payload = content.encode("utf-8") if content is not None else from_.read_bytes()
    try:
        rev = file_service.append(_store(), slug, name, payload)
    except Exception as exc:
        _handle(exc)
        return
    print(f"appended: {name} (revision {rev[:8]})")


@app.command(name="delete")
def delete(
    slug: str, name: str, /,
    *,
    base_revision: Annotated[str | None, Parameter(name=["--base-revision"])] = None,
    yes: Annotated[bool, Parameter(name=["--yes"], negative=())] = False,
) -> None:
    """Delete a file. --yes skips the confirmation prompt."""
    if not yes:
        import questionary
        if not questionary.confirm(f"Delete {slug}/{name}?", default=False).ask():
            print("aborted")
            raise SystemExit(1)
    rev = Revision(base_revision) if base_revision else None
    try:
        last_rev = file_service.delete(_store(), slug, name, base_revision=rev)
    except Exception as exc:
        _handle(exc)
        return
    print(f"deleted: {name} (was at revision {last_rev[:8]})")
```

- [ ] **Step 2: Register the sub-app in `cli.py`**

In `src/jobhound/cli.py`, after the other `app.command(...)` registrations, add:

```python
from jobhound.commands.file import app as file_app
app.command(file_app)  # cyclopts nests the sub-app
```

(If cyclopts requires a different registration pattern, adjust accordingly; the cyclopts docs show `app.command(other_app)` for nesting.)

- [ ] **Step 3: Tests in `tests/test_cmd_file.py`**

~10 tests covering: list, show (stdout + --out), write (--content, --from), append (--content), delete (--yes), and one error case each for write (file_exists), delete (stale base), meta.toml rejection.

Use the existing `tmp_jh` and `invoke` fixtures from `tests/conftest.py`.

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_cmd_file.py -v
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/commands/file.py src/jobhound/cli.py tests/test_cmd_file.py
git commit -m "feat(cli): add jh file subcommand group (list/show/write/append/delete)"
```

Expected: ~10 new CLI tests; full suite ~385.

---

## **End of PR A.**

Open the first PR at this point — the API surface is complete. Both AI (MCP) and CLI users can use the file API. Existing code still works (Phase 4 callers untouched).

**PR A title:** `feat: file management API + FileStore port (PR 1/2)`

---

## Task 12: Migrate `ops_service.add_note`

**Goal:** Drop direct FS access from `add_note`; delegate to `file_service.append`. Accept the two-commits-per-call cost.

**Files:**
- Modify: `src/jobhound/application/ops_service.py`
- Modify: `src/jobhound/mcp/tools/ops.py` (passes a store to ops_service)
- Modify: `src/jobhound/commands/note.py` (passes a store)
- Modify: `tests/application/test_ops_service.py` (update fixtures and any commit-count assertions)

- [ ] **Step 1: Update `ops_service.add_note` signature + body**

```python
def add_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    *,
    msg: str,
    today: date,
) -> tuple[Opportunity, Opportunity, Path]:
    """Append `- <today> <msg>` to notes.md and bump last_activity.

    Produces TWO commits: one from file_service.append (notes.md),
    one from repo.save (meta.toml last_activity bump).
    """
    line = f"- {today.isoformat()} {msg}\n".encode("utf-8")
    file_service.append(store, slug, "notes.md", line)
    before, opp_dir = repo.find(slug)
    after = before.touch(today=today)
    repo.save(after, opp_dir, message=f"note: {after.slug}")
    return before, after, opp_dir
```

- [ ] **Step 2: Update callers (`commands/note.py`, `mcp/tools/ops.py`)** to construct and pass a `GitLocalFileStore`.

- [ ] **Step 3: Update tests**

Existing `test_ops_service.py::test_add_note_*` tests need to pass a store and accept two-commit behaviour. Use the `in_memory_store` fixture for application tests.

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/ -v -k "note"
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/ops_service.py src/jobhound/mcp/tools/ops.py \
        src/jobhound/commands/note.py tests/application/test_ops_service.py
git commit -m "refactor(application): ops_service.add_note delegates to file_service.append"
```

---

## Task 13: Migrate `commands/log.py` correspondence-write

**Goal:** Drop direct FS access from `log.py`'s correspondence write; delegate to `file_service.write`. Accept the two-commits-per-call cost (correspondence + meta).

**Files:**
- Modify: `src/jobhound/commands/log.py`
- Modify: any test that asserted on commit count of `jh log`

- [ ] **Step 1: Update `log.py`**

Replace the inline `corr_path.write_text(body.read_text())` block with:

```python
store = GitLocalFileStore(paths_from_config(cfg))
corr_name = f"correspondence/{_correspondence_filename(today_date, channel, direction, who)}"
file_service.write(
    store, slug_query, corr_name, body.read_bytes(),
    base_revision=None, overwrite=False,
)
```

(Add the imports for `file_service`, `GitLocalFileStore`.)

- [ ] **Step 2: Run + commit**

```bash
uv run pytest tests/test_cmd_log.py -v
uv run pytest -q
git add src/jobhound/commands/log.py
git commit -m "refactor(commands): log.py correspondence write delegates to file_service"
```

Note: `OpportunityQuery.list_files` / `read_file` may also be migrated to delegate to `file_service` here. Skip for now — they were Phase 3a's read API, separate concern. Leave as-is unless the audit in Task 14 surfaces a duplication concern.

---

## Task 14: Audit + README docs

**Goal:** Confirm no direct-FS access remains inside `commands/` or `application/` (except the documented `repository.create` scaffolding exception). Update README.

**Files:**
- Modify: `README.md`
- Optionally modify: any file the audit surfaces

- [ ] **Step 1: Audit grep**

```bash
cd /Users/robin/code/github/yo61/jobhound
rg "\.write_text\(|\.write_bytes\(|\.read_text\(|\.read_bytes\(|\.unlink\(|shutil\.move|shutil\.rmtree" \
   src/jobhound/commands src/jobhound/application
```

For each hit (excluding `src/jobhound/infrastructure/storage/git_local.py`, which is the legitimate adapter site):
- If it's in `repository.create` scaffolding → confirm a code comment points at this spec; if not, add one.
- Else → migrate to `file_service` or document why it can't be migrated.

- [ ] **Step 2: Update README**

Add an "AI integration (MCP)" subsection or extend the existing one to mention the file tools. Add a "Files" subsection to the CLI usage section mentioning `jh file list/show/write/append/delete`.

- [ ] **Step 3: Final full suite + lint**

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
```

Expected: all tests pass; only the pre-existing `yaml` baseline ty diagnostic remains.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document jh file commands + MCP file tools"
```

---

## After Task 14

**PR B title:** `refactor: migrate add_note + log.py correspondence to file_service (PR 2/2)`

After PR B merges, release-please proposes a minor bump (likely 0.6.0) given the user-facing CLI/MCP surface additions.

## Spec → task crosswalk

| Spec section | Task |
|---|---|
| `Revision` NewType + `compute_revision` abstraction | 1 |
| `FileStore` Protocol + atomicity contract | 1 |
| `GitLocalFileStore` adapter (today's only adapter) | 2 |
| `InMemoryFileStore` test fixture | 1 |
| `repository.create` scaffolding stays direct | 14 (audit confirms documented exception) |
| `file_service.read` + `list` + validation + `meta.toml` protection | 3 |
| `file_service.write` + 6-case state machine + 3-way merge | 4 |
| `file_service.import_/export/append/delete` | 5, 6, 7, 8 |
| New MCP error codes + mapping | 9 |
| 7 MCP file tools (5 new + 2 moved) | 10 |
| 5 `jh file` CLI subcommands | 11 |
| Migrate `ops_service.add_note` | 12 |
| Migrate `commands/log.py` correspondence-write | 13 |
| Audit remaining direct-FS access | 14 |
| README updates | 14 |
