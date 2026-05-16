"""Materialise a file from the store to a temp dir and hand off to the OS launcher."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from jobhound.application import file_service
from jobhound.infrastructure.storage.protocols import FileStore


def open_in_default_app(store: FileStore, slug: str, name: str) -> Path:
    """Read `name` from `slug`'s store, write to a temp dir, launch in OS default app.

    Returns the path of the temp file. The temp dir is intentionally not deleted —
    the launched app may keep the file open after this returns, and there's no
    portable way to detect close. Temp files accumulate in the system temp dir.
    """
    content, _revision = file_service.read(store, slug, name)
    tmp_dir = Path(tempfile.mkdtemp(prefix="jh-file-"))
    tmp_path = tmp_dir / name
    tmp_path.write_bytes(content)
    _launch(tmp_path)
    return tmp_path


def _launch(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=True)
    elif sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=True)
