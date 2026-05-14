"""`jh edit` — open meta.toml in $EDITOR with validation loop.

Direct FS access here is an intentional exception: the $EDITOR workflow is an
interactive read-modify-write loop on a temp path that doesn't fit the
load-mutate-save shape of file_service.  See docs/specs/2026-05-14-file-management-design.md
§"Out of scope".
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.meta_io import ValidationError, read_meta
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

_ERROR_PREFIX = "# ERROR:"


def _editor_argv(cfg_editor: str) -> list[str]:
    raw = cfg_editor or os.environ.get("EDITOR") or "vi"
    return shlex.split(raw)


def _strip_error_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    idx = 0
    while idx < len(lines) and lines[idx].startswith(_ERROR_PREFIX):
        idx += 1
    if idx == 0:
        return text
    if idx < len(lines) and lines[idx].rstrip() == "#":
        idx += 1
    if idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    return "".join(lines[idx:])


def _prepend_error(path: Path, message: str) -> None:
    body = _strip_error_block(path.read_text())
    block = "".join(f"{_ERROR_PREFIX} {line}\n" for line in message.splitlines())
    path.write_text(f"{block}#\n{body}")


def _open_editor(argv: list[str], path: Path) -> None:
    subprocess.run([*argv, str(path)], check=True)


def run(
    slug_query: str,
    /,
    *,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Open meta.toml in $EDITOR; validate on save; rename on slug change."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    _, opp_dir = repo.find(slug_query)
    meta = opp_dir / "meta.toml"
    editor_argv = _editor_argv(cfg.editor)

    while True:
        before = meta.read_text()
        _open_editor(editor_argv, meta)
        after = meta.read_text()
        if after == before:
            print("No changes.")
            return
        try:
            opp = read_meta(meta)
        except ValidationError as exc:
            _prepend_error(meta, str(exc))
            continue
        cleaned = _strip_error_block(meta.read_text())
        if cleaned != after:
            meta.write_text(cleaned)
            opp = read_meta(meta)
        final_dir = repo.save(opp, opp_dir, message=f"edit: {opp.slug}", no_commit=no_commit)
        print(f"Updated {final_dir.relative_to(repo.paths.db_root)}")
        return
