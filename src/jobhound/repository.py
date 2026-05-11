"""OpportunityRepository — the single persistence + git-commit surface.

Wraps `slug.resolve_slug`, `meta_io.{read,write}_meta`, `git.{ensure_repo,
commit_change}`, plus the on-disk skeleton scaffolding and rename/archive/
delete moves. Every command goes through this class; nothing else should
call meta_io directly.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

from jobhound.config import Config
from jobhound.git import commit_change, ensure_repo
from jobhound.meta_io import read_meta, write_meta
from jobhound.opportunities import Opportunity
from jobhound.paths import Paths
from jobhound.slug import resolve_slug


class OpportunityRepository:
    """Persistence + git-commit surface for `Opportunity` aggregates."""

    def __init__(self, paths: Paths, cfg: Config) -> None:
        self.paths = paths
        self.cfg = cfg
        ensure_repo(self.paths.db_root)

    def find(self, slug_query: str) -> tuple[Opportunity, Path]:
        """Resolve `slug_query` and return (Opportunity, opp_dir)."""
        opp_dir = resolve_slug(slug_query, self.paths.opportunities_dir)
        opp = read_meta(opp_dir / "meta.toml")
        return opp, opp_dir

    def all(self) -> Iterator[Opportunity]:
        """Yield every Opportunity under `opportunities_dir`, sorted by slug."""
        if not self.paths.opportunities_dir.exists():
            return
        for sub in sorted(self.paths.opportunities_dir.iterdir()):
            if not sub.is_dir():
                continue
            yield read_meta(sub / "meta.toml")

    def create(self, opp: Opportunity, *, message: str, no_commit: bool = False) -> Path:
        """Scaffold a new opportunity directory and write `opp`."""
        opp_dir = self.paths.opportunities_dir / opp.slug
        if opp_dir.exists():
            raise FileExistsError(f"opportunity already exists: {opp_dir}")
        opp_dir.mkdir(parents=True)
        (opp_dir / "notes.md").write_text("")
        (opp_dir / "research.md").write_text(
            "# Research\n\n## Company\n\n## Role\n\n## Why apply\n\n## Why not\n"
        )
        (opp_dir / "correspondence").mkdir()
        write_meta(opp, opp_dir / "meta.toml")
        self._commit(message, no_commit=no_commit)
        return opp_dir

    def save(
        self,
        opp: Opportunity,
        opp_dir: Path,
        *,
        message: str,
        no_commit: bool = False,
    ) -> Path:
        """Persist `opp`. Renames the directory if `opp.slug` no longer matches."""
        if opp_dir.name != opp.slug:
            dst = opp_dir.parent / opp.slug
            if dst.exists():
                raise FileExistsError(f"target folder already exists: {dst}")
            opp_dir.rename(dst)
            opp_dir = dst
        write_meta(opp, opp_dir / "meta.toml")
        self._commit(message, no_commit=no_commit)
        return opp_dir

    def archive(self, opp_dir: Path, *, no_commit: bool = False) -> None:
        """Move `opp_dir` from opportunities/ to archive/."""
        dst = self.paths.archive_dir / opp_dir.name
        if dst.exists():
            raise FileExistsError(f"archive target already exists: {dst}")
        self.paths.archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(opp_dir, dst)
        self._commit(f"archive: {opp_dir.name}", no_commit=no_commit)

    def delete(self, opp_dir: Path, *, no_commit: bool = False) -> None:
        """Remove `opp_dir` from disk."""
        name = opp_dir.name
        shutil.rmtree(opp_dir)
        self._commit(f"delete: {name}", no_commit=no_commit)

    def _commit(self, message: str, *, no_commit: bool) -> None:
        commit_change(
            self.paths.db_root,
            message,
            enabled=self.cfg.auto_commit and not no_commit,
        )
