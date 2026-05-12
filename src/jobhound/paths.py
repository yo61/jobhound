"""Directory layout derived from Config."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from xdg_base_dirs import xdg_cache_home, xdg_state_home

from jobhound.config import Config


@dataclass(frozen=True)
class Paths:
    """Resolved directory layout for a `jh` invocation."""

    db_root: Path
    opportunities_dir: Path
    archive_dir: Path
    shared_dir: Path
    cache_dir: Path
    state_dir: Path

    @staticmethod
    def ensure(paths: Paths) -> None:
        """Create the data-root directory tree if missing. Safe to call repeatedly."""
        for d in (paths.opportunities_dir, paths.archive_dir, paths.shared_dir):
            d.mkdir(parents=True, exist_ok=True)


def paths_from_config(cfg: Config) -> Paths:
    """Build a Paths instance from a Config."""
    return Paths(
        db_root=cfg.db_path,
        opportunities_dir=cfg.db_path / "opportunities",
        archive_dir=cfg.db_path / "archive",
        shared_dir=cfg.db_path / "_shared",
        cache_dir=xdg_cache_home() / "jh",
        state_dir=xdg_state_home() / "jh",
    )
