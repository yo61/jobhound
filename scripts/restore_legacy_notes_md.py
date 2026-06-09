"""Restore a deleted legacy `notes.md` from the per-opp migration commit.

Usage:
    uv run scripts/restore_legacy_notes_md.py SLUG

Looks up the most recent commit titled
`migrate: notes.md → notes/ for <slug>` in the data repo, finds its
parent, and writes that parent's `notes.md` back to the working tree.

The new per-note files under `notes/` are NOT touched. To fully roll
back you must also `rm -rf <opp>/notes/` and revert the meta.toml
change; this script is a recovery aid, not an undo button.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from jobhound.domain.slug import resolve_slug
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def find_migration_commit(db_root: Path, slug: str) -> str | None:
    """Return the commit SHA of the migration commit for `slug`, or None."""
    msg = f"migrate: notes.md → notes/ for {slug}"
    result = subprocess.run(
        ["git", "-C", str(db_root), "log", "--grep", msg, "-1", "--format=%H"],
        capture_output=True,
        text=True,
        check=True,
    )
    sha = result.stdout.strip()
    return sha or None


def restore_notes_md(db_root: Path, opp_dir: Path, slug: str) -> int:
    """Restore `<opp_dir>/notes.md` from the parent of the migration commit.

    Returns 0 on success, non-zero on failure.
    """
    sha = find_migration_commit(db_root, slug)
    if sha is None:
        print(f"no migration commit found for {slug}", file=sys.stderr)
        return 1

    parent = f"{sha}^"
    rel_path = opp_dir.relative_to(db_root) / "notes.md"
    # `git show <parent>:<relpath>` produces the pre-migration bytes.
    result = subprocess.run(
        ["git", "-C", str(db_root), "show", f"{parent}:{rel_path.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"could not retrieve notes.md from {parent}:{rel_path}: "
            f"{result.stderr.decode('utf-8', errors='replace')}",
            file=sys.stderr,
        )
        return 1

    target = opp_dir / "notes.md"
    if target.exists():
        print(f"{target} already exists; refusing to overwrite", file=sys.stderr)
        return 1

    target.write_bytes(result.stdout)
    print(f"restored: {target} from {parent[:8]}")
    print("note: the new `notes/` directory and `notes_next_seq` are unchanged.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", help="Slug query (substring matches one opp).")
    args = parser.parse_args(argv)

    cfg = load_config()
    paths = paths_from_config(cfg)
    opp_dir = resolve_slug(args.slug, paths.opportunities_dir)
    return restore_notes_md(paths.db_root, opp_dir, opp_dir.name)


if __name__ == "__main__":
    sys.exit(main())
