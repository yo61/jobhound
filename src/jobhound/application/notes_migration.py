"""Migration: per-opp `notes.md` → per-note files under `<opp>/notes/`.

Pure module: takes paths, returns typed results. The CLI script
(`scripts/migrate_notes_to_directory.py`) and the auto-migration hook
in `cli.py` both call into here.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import tomli_w

from jobhound.application.frontmatter import Document, Frontmatter, serialize

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
    - `- YYYY-MM-DDTHH:MM:SSZ message` (bullet from `jh add note`)

    Pre-first-marker content is discarded. Whitespace-only bodies are skipped.
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


def find_legacy_opps(opportunities_dir: Path, archive_dir: Path) -> list[Path]:
    """Return opp dirs that still have a legacy `notes.md` file."""
    out: list[Path] = []
    for root in (opportunities_dir, archive_dir):
        if not root.exists():
            continue
        for opp_dir in sorted(root.iterdir()):
            if not opp_dir.is_dir():
                continue
            if (opp_dir / "notes.md").exists():
                out.append(opp_dir)
    return out


def auto_migrate(opportunities_dir: Path, archive_dir: Path, db_root: Path) -> int:
    """Run legacy-notes migration on every opp with a `notes.md`.

    Called from `cli.py:main()` on every `jh` invocation. Returns the count
    of opps migrated. Fail-fast: raises the first per-opp error and lets the
    caller surface it; partially-migrated state stays committed.

    No-op when no legacy files exist (the common case after first migration).
    """
    legacy = find_legacy_opps(opportunities_dir, archive_dir)
    if not legacy:
        return 0

    print(
        f"jh: legacy notes.md found in {len(legacy)} opp(s); migrating to notes/ ...",
        file=sys.stderr,
    )

    migrated = 0
    for opp_dir in legacy:
        result = migrate_one(opp_dir, apply=True)
        if result.status != "migrated":
            raise RuntimeError(f"auto-migration: {opp_dir.name}: {result.status} ({result.detail})")
        subprocess.run(["git", "-C", str(db_root), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(db_root),
                "commit",
                "-q",
                "-m",
                f"migrate: notes.md → notes/ for {result.slug}",
            ],
            check=True,
        )
        print(
            f"jh:   {result.slug}: {result.count} notes migrated",
            file=sys.stderr,
        )
        migrated += 1
    print(f"jh: migration complete ({migrated} opp(s))", file=sys.stderr)
    return migrated
