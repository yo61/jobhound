"""One-shot migration: per-opp `notes.md` → per-note files under `notes/`.

Usage:
    uv run scripts/migrate_notes_to_directory.py            # dry-run
    uv run scripts/migrate_notes_to_directory.py --apply
    uv run scripts/migrate_notes_to_directory.py --only acme,menlo

Auto-migration: this same logic runs on every `jh` invocation via
`cli.py:main()`. This script is the manual escape hatch — useful for
dry-run inspection or for re-running after fixing an error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from jobhound.application.notes_migration import (
    MigrateResult,
    migrate_one,
    parse_notes_md,  # noqa: F401 — re-exported; tests call m.parse_notes_md via this module
)
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def _git_commit(db_root: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(db_root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db_root), "commit", "-q", "-m", message], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run).")
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated slug substrings to restrict the run.",
    )
    args = parser.parse_args(argv)

    cfg = load_config()
    paths = paths_from_config(cfg)

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    targets: list[Path] = []
    for root in (paths.opportunities_dir, paths.archive_dir):
        if not root.exists():
            continue
        for opp_dir in sorted(root.iterdir()):
            if not opp_dir.is_dir():
                continue
            if only and not any(s in opp_dir.name for s in only):
                continue
            targets.append(opp_dir)

    results: list[MigrateResult] = []
    for opp_dir in targets:
        try:
            r = migrate_one(opp_dir, apply=args.apply)
        except Exception as exc:
            results.append(MigrateResult(status="error", slug=opp_dir.name, detail=str(exc)))
            print(f"=== {opp_dir.name} === ERROR: {exc}", file=sys.stderr)
            continue
        results.append(r)
        if r.status == "migrated":
            print(f"=== {r.slug} ===  {r.count} notes -> notes/{{1..{r.count}}}.md")
        elif r.status == "skipped":
            print(f"=== {r.slug} ===  skipped ({r.detail})")

        if args.apply and r.status == "migrated":
            _git_commit(paths.db_root, f"migrate: notes.md → notes/ for {r.slug}")

    migrated = sum(1 for r in results if r.status == "migrated")
    skipped = sum(1 for r in results if r.status == "skipped")
    errored = sum(1 for r in results if r.status == "error")
    total_notes = sum(r.count for r in results)

    print()
    print("Summary:")
    print(f"  {len(results)} opps scanned")
    print(f"  {migrated} opps migrated ({total_notes} notes)")
    print(f"  {skipped} opps skipped")
    print(f"  {errored} opps errored")
    if not args.apply:
        print()
        print("Dry-run — no files changed. Re-run with --apply to write.")

    return 0 if errored == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
