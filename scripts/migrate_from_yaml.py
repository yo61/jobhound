"""One-shot migration: YAML job-hunt store -> TOML jh store.

Usage:
    uv run --with pyyaml scripts/migrate_from_yaml.py           # dry-run
    uv run --with pyyaml scripts/migrate_from_yaml.py --apply   # write files
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from jobhound.config import load_config
from jobhound.meta_io import validate, write_meta
from jobhound.opportunities import Opportunity
from jobhound.paths import paths_from_config

SOURCE_ROOT = Path("~/Documents/Projects/Job Hunting 2026-04").expanduser()
SOURCE_OPPS = SOURCE_ROOT / "opportunities"
SOURCE_SHARED = SOURCE_ROOT / "_shared"

SKIP_NAMES = {"meta.yaml", ".DS_Store", ".gitkeep"}
SKIP_DIRS = {".claude"}


@dataclass(frozen=True)
class OppPlan:
    src: Path
    dest: Path
    opp: Opportunity
    files: tuple[Path, ...]


def _should_skip(rel: Path) -> bool:
    if rel.name in SKIP_NAMES:
        return True
    return any(part in SKIP_DIRS for part in rel.parts)


def _collect_files(src: Path) -> tuple[Path, ...]:
    """Return source-relative paths for everything that will be copied."""
    out: list[Path] = []
    for p in sorted(src.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(src)
        if _should_skip(rel):
            continue
        out.append(rel)
    return tuple(out)


def _plan_opportunity(src: Path, dest_root: Path) -> OppPlan:
    raw = yaml.safe_load((src / "meta.yaml").read_text())
    opp = validate(raw, src / "meta.yaml")
    return OppPlan(
        src=src,
        dest=dest_root / opp.slug,
        opp=opp,
        files=_collect_files(src),
    )


def _plan_shared(src: Path, dest: Path) -> tuple[Path, ...]:
    if not src.exists():
        return ()
    return tuple(
        p.relative_to(src)
        for p in sorted(src.rglob("*"))
        if p.is_file() and not _should_skip(p.relative_to(src))
    )


def _print_opp_plan(plan: OppPlan) -> None:
    o = plan.opp
    print(f"\n  {plan.src.name}")
    print(f"    -> {plan.dest}")
    print(f"    company={o.company!r} role={o.role!r}")
    print(f"    status={o.status.value} priority={o.priority.value}")
    print(f"    tags={list(o.tags)} contacts={len(o.contacts)} links={len(o.links)}")
    print(f"    files to copy ({len(plan.files)}):")
    for rel in plan.files:
        print(f"      {rel}")
    print("      meta.toml  [generated from meta.yaml]")
    if not any(rel.parts[0] == "correspondence" for rel in plan.files):
        print("      correspondence/  [empty directory ensured]")


def _execute_opp(plan: OppPlan) -> None:
    if plan.dest.exists():
        raise FileExistsError(f"destination already exists: {plan.dest}")
    plan.dest.mkdir(parents=True)
    for rel in plan.files:
        dst = plan.dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(plan.src / rel, dst)
    (plan.dest / "correspondence").mkdir(exist_ok=True)
    write_meta(plan.opp, plan.dest / "meta.toml")


def _execute_shared(src: Path, dest: Path, files: tuple[Path, ...]) -> None:
    for rel in files:
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually write files")
    args = parser.parse_args()

    cfg = load_config()
    paths = paths_from_config(cfg)

    if not SOURCE_OPPS.exists():
        print(f"ERROR: source not found: {SOURCE_OPPS}", file=sys.stderr)
        return 1

    plans: list[OppPlan] = []
    for src in sorted(SOURCE_OPPS.iterdir()):
        if not src.is_dir():
            continue
        if not (src / "meta.yaml").exists():
            print(f"  SKIP {src.name} (no meta.yaml)")
            continue
        plans.append(_plan_opportunity(src, paths.opportunities_dir))

    shared_files = _plan_shared(SOURCE_SHARED, paths.shared_dir)

    print(f"Source:      {SOURCE_ROOT}")
    print(f"Destination: {paths.db_root}")
    print(f"Mode:        {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"\nOpportunities to migrate: {len(plans)}")
    for plan in plans:
        _print_opp_plan(plan)

    print(f"\nShared files to copy: {len(shared_files)} -> {paths.shared_dir}")
    for rel in shared_files:
        print(f"  {rel}")

    existing_dests = [p.dest for p in plans if p.dest.exists()]
    if existing_dests:
        print("\nWARNING: destinations already exist (would error on apply):")
        for d in existing_dests:
            print(f"  {d}")

    if not args.apply:
        print("\nDRY RUN — no files written. Re-run with --apply.")
        return 0

    for plan in plans:
        _execute_opp(plan)
    _execute_shared(SOURCE_SHARED, paths.shared_dir, shared_files)
    print(f"\nMigrated {len(plans)} opportunities and {len(shared_files)} shared files.")
    print(
        f"Next: cd {paths.db_root} && git add -A && "
        f"git commit -m 'import: bulk migration from yaml store'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
