"""One-shot migration: per-opp `notes.md` → per-note files under `notes/`.

Usage:
    uv run scripts/migrate_notes_to_directory.py            # dry-run
    uv run scripts/migrate_notes_to_directory.py --apply
    uv run scripts/migrate_notes_to_directory.py --only acme,menlo
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import tomli_w

from jobhound.application.frontmatter import Document, Frontmatter, serialize
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config

DATE_MARKER_H2 = re.compile(r"^## (\d{4}-\d{2}-\d{2})(?: — .*)?$")
DATE_MARKER_BUL = re.compile(r"^- (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) (.*)$")


@dataclass
class MarkerNote:
    created: datetime
    body: str


@dataclass
class MigrateResult:
    status: str  # "migrated" | "skipped" | "error"
    slug: str = ""
    count: int = 0
    detail: str = ""


def parse_notes_md(content: str) -> list[MarkerNote]:
    """Parse a notes.md file into individual notes per the decision grammar.

    Two marker shapes:
    - `## YYYY-MM-DD[ — suffix]` (H2 day header; created at T00:00:00Z)
    - `- YYYY-MM-DDTHH:MM:SSZ message` (bullet from `jh add note`; created from ISO ts)

    Pre-first-marker content is discarded. Bodies are stripped; whitespace-only
    bodies are skipped (not migrated).
    """
    notes: list[MarkerNote] = []
    current_created: datetime | None = None
    current_body_lines: list[str] = []

    def flush() -> None:
        if current_created is None:
            return
        body = "\n".join(current_body_lines).strip()
        if body:
            notes.append(MarkerNote(created=current_created, body=body))

    for line in content.splitlines():
        m_h2 = DATE_MARKER_H2.match(line)
        m_bul = DATE_MARKER_BUL.match(line)
        if m_h2 is not None:
            flush()
            current_created = datetime.strptime(m_h2.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
            current_body_lines = []
        elif m_bul is not None:
            flush()
            current_created = datetime.strptime(m_bul.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=UTC
            )
            current_body_lines = [m_bul.group(2)]
        else:
            if current_created is not None:
                current_body_lines.append(line)
            # else: pre-first-marker preamble → discard
    flush()
    return notes


def _read_meta_raw(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _write_meta_raw(path: Path, data: dict) -> None:
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)


def migrate_one(opp_dir: Path, *, apply: bool) -> MigrateResult:
    """Migrate a single opp directory. Returns a typed result record."""
    slug = opp_dir.name
    notes_md = opp_dir / "notes.md"
    notes_dir = opp_dir / "notes"
    meta_path = opp_dir / "meta.toml"

    if not notes_md.exists():
        # Either already migrated, or never had notes — both are skips.
        if apply and not notes_dir.exists():
            notes_dir.mkdir(exist_ok=True)
            data = _read_meta_raw(meta_path)
            data.setdefault("notes_next_seq", 1)
            _write_meta_raw(meta_path, data)
        return MigrateResult(status="skipped", slug=slug, detail="no notes.md")

    if notes_dir.exists() and any(notes_dir.iterdir()):
        return MigrateResult(
            status="skipped",
            slug=slug,
            detail="notes/ already exists with content; refusing to merge",
        )

    notes = parse_notes_md(notes_md.read_text())
    notes.sort(key=lambda n: n.created)

    if not apply:
        return MigrateResult(status="migrated", slug=slug, count=len(notes), detail="dry-run")

    notes_dir.mkdir(exist_ok=True)
    for seq, note in enumerate(notes, start=1):
        doc = Document(
            frontmatter=Frontmatter(created=note.created),
            body=note.body,
        )
        (notes_dir / f"{seq}.md").write_bytes(serialize(doc))

    notes_md.unlink()

    data = _read_meta_raw(meta_path)
    data["notes_next_seq"] = len(notes) + 1
    _write_meta_raw(meta_path, data)

    return MigrateResult(status="migrated", slug=slug, count=len(notes))


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
