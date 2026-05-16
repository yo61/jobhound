# `jh file open` — Design Spec

Date: 2026-05-15
Status: Draft, awaiting review
Branch: `feat/file-open` (not yet created; cut off `main`)

**Revision 2026-05-16:** This spec originally proposed CLI-only. Amended
to include an MCP equivalent (`open_file`) — the MCP server runs locally
alongside Claude Desktop/Code, so launching the OS handler opens the file
on the user's actual desktop. The "remote agent" framing of the original
spec didn't fit. Implementation shares the read-bytes + write-temp + OS-launch
logic via a new `application/file_launcher.py` helper.

Add a CLI command that fetches a file from an opportunity, writes it to a
temp location, and opens it in the OS's associated application.

Independent of the UTC timestamps work on `feat/utc-timestamps-design`.

## Goal

```
jh file open <slug> <filename>
```

End state: the file's current revision is materialised on local disk under a
temp path and handed to the OS launcher (`open` on macOS, `xdg-open` on
Linux, `os.startfile` on Windows). Control returns to the shell immediately;
the OS owns the file lifetime from that point.

Both CLI (`jh file open`) and MCP (`open_file`) — the MCP server runs locally
alongside Claude Desktop/Code, so the OS handler launches on the user's actual
desktop. Agents that prefer raw bytes on disk (no GUI launch) still use
`export_file`.

## Why route through `file_service`

`GitLocalFileStore` happens to be filesystem-backed today, so it would be
tempting to just `subprocess.run(["open", str(real_path_in_repo)])`. Don't.
Two reasons:

1. The FileStore Protocol is the abstraction the whole `file/` subcommand
   group commits to (see `src/jobhound/commands/file.py:1-8`). A future
   non-FS backend (S3, remote git, sqlite) breaks the shortcut.
2. The repo path *is* the working tree of the opportunity's git store.
   Opening that file in an editor risks the user saving edits that land in
   the working tree without going through `file_service.write` — bypassing
   conflict detection, revision tracking, and the commit step.

So: always read bytes via `file_service.read()` and write a fresh copy to
a temp path. The temp file is intentionally disconnected from the store.

## Design decisions to make

1. **Temp file lifetime.** Two viable options:
   - **(a)** `tempfile.mkdtemp(prefix="jh-file-")` then write the file inside
     it with the original filename preserved. Don't delete — the launched
     app may keep the file open after `jh` exits, and there's no portable
     way to know when it's closed. Files accumulate; document this and
     suggest `trash ~/Library/Caches/jh-file-*` or similar.
   - **(b)** Use `tempfile.NamedTemporaryFile(delete=False, suffix=<ext>)`.
     Same accumulation problem, but the random part is in the basename
     rather than a wrapping dir, which means the app's "recent files" list
     shows `tmpa8s9f.pdf` instead of `cover-letter.pdf`. Worse UX.

   **Recommended: (a).** Wrapping dir preserves the original filename for
   app association (extension) and for the user's recent-files list.

2. **Where do temp dirs live?** `tempfile.gettempdir()` (defaults to
   `/var/folders/...` on macOS, `/tmp` on Linux) is fine. Optionally expose
   `--out <dir>` for users who want them somewhere stable (e.g. `~/Downloads`).
   v1: just use the default. Skip the flag unless asked.

3. **Platform launch dispatch.** `sys.platform` switch:
   - `darwin`: `subprocess.run(["open", path], check=True)`
   - `win32`: `os.startfile(path)`
   - everything else: `subprocess.run(["xdg-open", path], check=True)`

   Consider `click.launch(path)` (from the click library) as a one-liner
   alternative — but jobhound uses `cyclopts`, not click, so pulling in
   click just for this isn't justified. Roll the 8-line dispatch.

4. **Run synchronously or detached?** macOS `open` returns immediately
   (the GUI app is launched in the background). `xdg-open` is the same.
   `os.startfile` is non-blocking by design. So `subprocess.run` with no
   special flags is fine on all three — no need for `Popen` + detach.

5. **Error surface.** Reuse `_handle_error` in `file.py`. The only new
   failure mode is "no associated app for this extension", which surfaces
   as a non-zero exit from `open`/`xdg-open` — print a friendly message
   pointing the user at their OS file-association settings.

6. **`open` shadows the builtin.** Name the cyclopts handler `open_`
   internally; register with `@app.command(name="open")`. Same pattern as
   `list_` at `src/jobhound/commands/file.py:87-88`.

## Shared helper: `application/file_launcher.py`

Both adapters call into one helper that does the read + materialise + launch
sequence. Adapter code wraps it in surface-specific framing (CLI exit codes,
MCP JSON response).

```python
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
    portable way to detect close. Temp files accumulate; document this for users.
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
```

The function returns the temp path so adapters can format their response
("opened: cover-letter.pdf (/var/folders/.../jh-file-xxx/cover-letter.pdf)" for
CLI, JSON `{opened: true, temp_path: ...}` for MCP).

## Implementation sketch

In `src/jobhound/commands/file.py`, after the `delete` command:

```python
@app.command(name="open")
def open_(slug: str, name: str, /) -> None:
    """Open a file in the OS's associated application."""
    from jobhound.application.file_launcher import open_in_default_app

    try:
        store, canonical = _store_and_slug(slug)
        tmp_path = open_in_default_app(store, canonical, name)
    except Exception as exc:
        _handle_error(exc)
        return
    print(f"opened: {name} ({tmp_path})")
```

## MCP tool: `open_file`

In `src/jobhound/mcp/tools/files.py`, alongside the existing 7 file tools:

```python
def open_file(repo: OpportunityRepository, slug: str, name: str) -> str:
    """Materialise a file to a temp dir and launch the user's default app for it."""
    try:
        resolved = _resolve(repo, slug)
        tmp_path = open_in_default_app(_store(repo), resolved, name)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="open_file"))
    return json.dumps({"opened": True, "filename": name, "temp_path": str(tmp_path)})
```

Plus the `register()` entry:

```python
@app.tool(
    name="open_file",
    description="Open a file in the user's default app for that file type. The MCP server runs locally; the file opens on the user's actual desktop.",
)
def _o(slug: str, name: str) -> str:
    return open_file(repo, slug=slug, name=name)
```

MCP count: 37 → 38.

## Tests

`tests/commands/test_file.py` (or wherever the existing file-command tests
live — check `tests/` layout first).

- Mock `subprocess.run` and `os.startfile`. Verify:
  - Temp file exists at the asserted path before launcher is invoked.
  - Temp file content matches what `file_service.read` returned.
  - Original filename is preserved (extension intact for app association).
  - On `darwin`, `open` is called; on `linux`, `xdg-open`; on `win32`,
    `os.startfile`. Patch `sys.platform` for each.
- Error paths:
  - Nonexistent slug → `_handle_error` exits non-zero.
  - Nonexistent filename → `FileNotFoundError` from `file_service.read` →
    friendly message, non-zero exit.
  - Launcher returns non-zero → friendly message, non-zero exit, temp
    file is still on disk (user can retry manually).

No real subprocess calls in tests. No real GUI app launches.

## Out of scope

- **No `--watch` / round-trip.** Watching the temp file for edits and
  syncing changes back into the store via `file_service.write` is a
  separate, larger feature (revision conflicts, base-revision tracking,
  user prompts on conflict). If requested later, file as its own task.
- **No `--app <appname>` override.** macOS `open -a Preview` is tempting
  but cross-platform parity is hard. v1 trusts the OS default.

## Docs to update

- `docs/commands.md` (or wherever the `jh file ...` table is — check
  `docs/` after writing the spec).
- Help text on the `open` command is the only required doc surface.
  README mention is optional.

