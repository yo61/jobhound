"""`jh edit` — open meta.toml in $EDITOR with validation loop.

Ported from internals/scripts/edit_opportunity.py in the old repo; same
validation-loop pattern, but reading/writing TOML and using slug resolution.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.git import commit_change, ensure_repo
from jobhound.meta_io import ValidationError, read_meta, write_meta
from jobhound.paths import paths_from_config
from jobhound.slug import resolve_slug

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


def _maybe_rename(opp_dir: Path, new_slug: str) -> Path:
    if opp_dir.name == new_slug:
        return opp_dir
    dst = opp_dir.parent / new_slug
    if dst.exists():
        raise FileExistsError(f"target folder already exists: {dst}")
    opp_dir.rename(dst)
    return dst


def run(
    slug_query: str,
    /,
    *,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Open meta.toml in $EDITOR; validate on save; rename on slug change."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    ensure_repo(paths.db_root)

    opp_dir = resolve_slug(slug_query, paths.opportunities_dir)
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
        final_dir = _maybe_rename(opp_dir, opp.slug)
        if final_dir is not opp_dir:
            write_meta(replace(opp, slug=opp.slug), final_dir / "meta.toml")
        commit_change(
            paths.db_root,
            f"edit: {opp.slug}",
            enabled=cfg.auto_commit and not no_commit,
        )
        print(f"Updated {final_dir.relative_to(paths.db_root)}")
        return
