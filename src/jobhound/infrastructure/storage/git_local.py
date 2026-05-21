"""GitLocalFileStore — the git-backed FileStore adapter.

Files live under <paths.opportunities_dir>/<slug>/ inside a git-tracked
data root. Every mutation produces one git commit. Revision is the git
blob SHA via `git hash-object`.

Path-traversal is rejected at the adapter boundary by resolving the
target and confirming it lies under the opp dir.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from jobhound.application.revisions import Revision
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.storage.protocols import FileEntryList


class GitCommandError(subprocess.CalledProcessError):
    """A git subprocess exited non-zero. ``str()`` includes git's stderr.

    Inherits from ``subprocess.CalledProcessError`` so existing
    ``except subprocess.CalledProcessError`` handlers keep working — they
    just get a richer message that names the actual failure (stale
    index.lock, missing object, bad ref, etc.) instead of bare exit code.
    """

    def __str__(self) -> str:
        base = super().__str__()
        stderr = self.stderr
        if not stderr:
            return base
        if isinstance(stderr, bytes | bytearray):
            stderr_text = bytes(stderr).decode("utf-8", errors="replace")
        else:
            stderr_text = str(stderr)
        stderr_text = stderr_text.strip()
        if not stderr_text:
            return base
        return f"{base}\nstderr: {stderr_text}"


def _run_git(cmd: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a git subprocess, raising GitCommandError with stderr on failure."""
    result = subprocess.run(list(cmd), capture_output=True, check=False)
    if result.returncode != 0:
        raise GitCommandError(
            returncode=result.returncode,
            cmd=list(cmd),
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


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
        return _run_git(["git", "-C", str(self._paths.db_root), *args])

    # ---- FileStore interface --------------------------------------------

    def list(self, opp_slug: str) -> FileEntryList:
        from jobhound.application.snapshots import FileEntry

        opp = self._opp_dir(opp_slug)
        if not opp.exists():
            return []
        entries: FileEntryList = []
        for path in sorted(opp.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(opp)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if rel.name == "meta.toml":  # excluded from file-API listing
                continue
            stat = path.stat()
            entries.append(
                FileEntry(
                    name=rel.as_posix(),
                    size=stat.st_size,
                    mtime=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                )
            )
        return entries

    def exists(self, opp_slug: str, filename: str) -> bool:
        return self._resolve(opp_slug, filename).is_file()

    def read(self, opp_slug: str, filename: str) -> bytes:
        target = self._resolve(opp_slug, filename)
        if not target.is_file():
            raise FileNotFoundError(f"{opp_slug}/{filename}")
        return target.read_bytes()

    def write(
        self,
        opp_slug: str,
        filename: str,
        content: bytes,
        *,
        commit_message: str,
    ) -> None:
        target = self._resolve(opp_slug, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        self._git("add", str(target))
        self._git("commit", "-m", commit_message)

    def append(
        self,
        opp_slug: str,
        filename: str,
        content: bytes,
        *,
        commit_message: str,
    ) -> None:
        target = self._resolve(opp_slug, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab") as fh:
            fh.write(content)
        self._git("add", str(target))
        self._git("commit", "-m", commit_message)

    def delete(
        self,
        opp_slug: str,
        filename: str,
        *,
        commit_message: str,
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
        result = _run_git(["git", "hash-object", str(target)])
        return Revision(result.stdout.decode("utf-8").strip())

    def read_by_revision(self, revision: Revision) -> bytes:
        """Resolve blob content via `git cat-file -p <sha>`.

        Works for any blob SHA that has ever been committed in the repo.
        """
        result = _run_git(
            ["git", "-C", str(self._paths.db_root), "cat-file", "-p", str(revision)],
        )
        return result.stdout
