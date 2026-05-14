# File Management API — Design Spec

Date: 2026-05-14
Status: Draft, awaiting review
Branch: `feat/file-management-design`

## Goal

Make the file management surface inside an opportunity directory uniform
and discipline-enforced: **every read and write of any non-`meta.toml`
file inside an opp dir goes through a single `file_service.py` backed by
a swappable `FileStore` port.** After this lands, no application or
adapter code touches `Path.write_text` / `read_bytes` / `unlink` for
files inside an opp dir.

For AI integration, this exposes seven well-behaved MCP tools
(`list_files`, `read_file`, `write_file`, `import_file`, `export_file`,
`append_file`, `delete_file`) with optimistic-concurrency conflict
detection, 3-way merge for text files, and structured errors that the AI
can recover from without bothering the user.

## Strategic direction

### Why this exists

Phase 3a's read API gave us `OpportunityQuery.list_files` and
`read_file` — clean, single-entry-point access to file content. But the
write side is fragmented:

- `src/jobhound/commands/log.py` writes correspondence files directly
  (`corr_path.write_text(body.read_text())`).
- `src/jobhound/application/ops_service.py:add_note` writes `notes.md`
  directly.
- `src/jobhound/infrastructure/repository.py:create` scaffolds
  `notes.md`, `research.md`, and `correspondence/` directly.

The MCP server has read tools but no write/delete file tools. The AI
cannot save a CV draft, store a generated research summary, or attach a
PDF without going through verbal-only "tell the user to do it manually"
workarounds.

This spec closes the write side, with an architecture deliberately
shaped for backend portability (the same API will work over a future
cloud-backed adapter without touching the application or adapter
layers).

### Scope

In scope:

- A new `application/file_service.py` exposing CRUD primitives over an
  abstract `FileStore` port.
- A new `infrastructure/storage/` subpackage with the `FileStore`
  Protocol and the first concrete adapter (`GitLocalFileStore`).
- Five new MCP tools (`write_file`, `import_file`, `export_file`,
  `append_file`, `delete_file`), plus moving the existing `list_files`
  and `read_file` from `mcp/tools/reads.py` to `mcp/tools/files.py`.
- A matching CLI subcommand group `jh file {list, show, write, append,
  delete}` so users get the same capability without ever needing to
  reach into the underlying storage directly. **This is essential for
  backend portability** — with a non-FS adapter (S3, sqlite, remote
  git), there is no local path the user could `cp` or `cat`; the CLI
  must mediate.
- Migration of `ops_service.add_note` and `commands/log.py`'s
  correspondence-write to use the new service.
- Optimistic-concurrency conflict detection on every write, with 3-way
  merge for text files via `git merge-file`.
- New `Revision` NewType hiding the content-identity scheme (currently
  git blob SHA; swappable per port adapter).

Out of scope (deferred):

- `OpportunityRepository`-as-port refactor — same Protocol pattern
  applied to `meta.toml` reads/writes, archive, and delete. Bigger;
  separate spec.
- Subdirectory listing API (`list_dir(subpath)`). Existing `list_files`
  is already recursive.
- Quota / size limits.
- Renaming files in place (`rename_file`). Three-step
  read-write-delete works.
- Concurrent multi-process safety on a shared data root. Pre-existing
  caveat; not made worse by this design.
- Append on binary files (allowed but undefined-behaviour for the file
  format).
- `no_commit` removal across the rest of the codebase — captured as
  task #43.
- Timestamp migration (`date` → `datetime` UTC) — captured as task #35.

## Architecture

### DDD layering

The file API uses the same DDD layout established in Phase 4: a port
declared in `infrastructure/`, an adapter in `infrastructure/storage/`,
and orchestration in `application/`.

```
src/jobhound/
  application/
    file_service.py             # NEW — orchestration; depends on FileStore protocol
    revisions.py                # NEW — Revision NewType (opaque str)
    snapshots.py                # existing — FileEntry stays here
    query.py                    # existing — list_files / read_file delegate to file_service
    ops_service.py              # MIGRATED — add_note delegates to file_service
    ...

  infrastructure/
    storage/                    # NEW SUBPACKAGE
      __init__.py
      protocols.py              # FileStore Protocol (the port)
      git_local.py              # GitLocalFileStore (today's only adapter)
      # future: s3.py, sqlite.py, git_remote.py, in_memory.py (tests)
    repository.py               # MOSTLY UNCHANGED — create still scaffolds initial
                                # files directly (documented exception)

  mcp/tools/
    files.py                    # NEW — owns all 7 file tools (list_files +
                                #       read_file MOVED here from reads.py;
                                #       write_file/import_file/export_file/
                                #       append_file/delete_file are new)
    reads.py                    # SHRINKS — list_files + read_file removed
    ...

  commands/
    file.py                     # NEW — `jh file` subcommand group:
                                #   jh file list   <slug>
                                #   jh file show   <slug> <name> [--out <path>]
                                #   jh file write  <slug> <name> {--content <s> | --from <p>}
                                #                                [--overwrite] [--base-revision <r>]
                                #   jh file append <slug> <name> {--content <s> | --from <p>}
                                #   jh file delete <slug> <name> [--base-revision <r>]
    log.py                      # MIGRATED — correspondence write delegates
                                # to file_service.write
```

### The FileStore port

```python
# infrastructure/storage/protocols.py
from typing import Protocol

class FileStore(Protocol):
    """Backend-agnostic interface for files inside an opportunity directory.

    Implementations may use a local git-managed dir, S3, sqlite, a remote
    git repo, an in-memory dict (tests), etc. file_service.py depends
    ONLY on this protocol, never on a concrete adapter.

    Every mutating method must be atomic and durable on return (for
    git-backed: each call commits). Callers do not call a separate
    `commit` — there is no transaction primitive in this protocol.
    """

    def list(self, opp_slug: str) -> list[FileEntry]: ...
    def exists(self, opp_slug: str, filename: str) -> bool: ...
    def read(self, opp_slug: str, filename: str) -> bytes: ...
    def write(
        self, opp_slug: str, filename: str, content: bytes,
        *, commit_message: str,
    ) -> None: ...
    def append(
        self, opp_slug: str, filename: str, content: bytes,
        *, commit_message: str,
    ) -> None: ...
    def delete(
        self, opp_slug: str, filename: str,
        *, commit_message: str,
    ) -> None: ...
    def compute_revision(self, opp_slug: str, filename: str) -> Revision: ...
```

Notes:

- **Atomicity is the adapter's responsibility.** Git-backed: `git add`
  + `git commit` in one call. S3-backed: a single PUT. Sqlite-backed: a
  transaction.
- **`commit_message` on every mutating call.** Looks git-flavoured but
  generalises: S3 backends ignore it, sqlite backends log it to an
  audit table, in-memory backends drop it.
- **`compute_revision` lives on the protocol** so each backend names its
  content natively (git blob SHA, S3 ETag, sqlite row-version,
  in-memory monotonic int). `application/revisions.py` is just the
  `NewType` wrapper — no implementation choice baked into the
  application layer.

### The first (today's only) adapter

```python
# infrastructure/storage/git_local.py
class GitLocalFileStore:
    """Files live under <paths.opportunities_dir>/<slug>/ inside a
    git-tracked data root. Every mutation = one git commit. Revision =
    git blob SHA via `git hash-object`.
    """

    def __init__(self, paths: Paths) -> None:
        self._paths = paths

    def write(self, opp_slug, filename, content, *, commit_message):
        path = self._resolve(opp_slug, filename)   # path-traversal check
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        subprocess.run(
            ["git", "-C", str(self._paths.db_root), "add", str(path)], check=True,
        )
        subprocess.run(
            ["git", "-C", str(self._paths.db_root), "commit", "-m", commit_message],
            check=True,
        )

    def compute_revision(self, opp_slug, filename):
        path = self._resolve(opp_slug, filename)
        result = subprocess.run(
            ["git", "hash-object", str(path)],
            capture_output=True, text=True, check=True,
        )
        return Revision(result.stdout.strip())

    # ... read, append, delete, list, exists analogous
```

### The application service uses the port

```python
# application/file_service.py
def write(
    store: FileStore,
    slug: str,
    name: str,
    content: bytes,
    *,
    base_revision: Revision | None = None,
    overwrite: bool = False,
) -> WriteResult:
    """Implements the conflict-detection state machine (see §"Conflict
    Detection State Machine"). Calls store.write under the hood. Returns
    a WriteResult with the new revision and a `merged: bool` flag.
    """
    ...
```

### `repository.create` scaffolding exception

`OpportunityRepository.create` scaffolds the initial `notes.md`,
`research.md`, and `correspondence/` at opp-creation time, *before* the
opp directory fully exists from `meta_io`'s point of view. Routing this
through `file_service` (which itself depends on git operations on a
data root that may not exist yet) creates a chicken-and-egg problem.

**Decision:** `repository.create` keeps its direct FS scaffolding as a
documented exception. A comment in the code points at this spec.
Auditing pass (Step 6 of §Sequencing) treats this as a known
exclusion.

### CLI subcommand surface

The CLI is a peer adapter to the MCP server: both call `file_service`,
neither talks directly to the storage backend. **This is what makes the
`FileStore` Protocol genuinely portable** — when an S3 or sqlite
adapter ships, `jh file show acme cv.md` still works, with no user
intervention beyond installing the right backend config.

| Command | Args / flags | Maps to |
|---|---|---|
| `jh file list <slug>` | (none) | `file_service.list` |
| `jh file show <slug> <name>` | `--out <path>` (when set, exports rather than printing); `--rev <r>` to retrieve a specific revision (future, not v1) | `file_service.read` or `.export` |
| `jh file write <slug> <name>` | `--content <str>` xor `--from <path>`; `--overwrite` opt-in; `--base-revision <r>` for scripted-edit flows | `file_service.write` or `.import_` |
| `jh file append <slug> <name>` | `--content <str>` xor `--from <path>` | `file_service.append` |
| `jh file delete <slug> <name>` | `--base-revision <r>` opt; `--yes` to skip confirmation prompt | `file_service.delete` |

Conflict-detection behaviour from the user's terminal:

- **`conflict_text` from `jh file write`**: prints conflict-marker output
  to stderr, exits non-zero. User can manually merge and retry, or
  re-read with `jh file show ... --out /tmp/x` and edit.
- **`conflict_binary`**: prints `conflict_binary: current revision <X>,
  size <Y>, last modified <Z>. Suggested alt: <name>. Re-run with
  --overwrite to clobber, or use --from <path>` to stderr. Exits
  non-zero.
- **`file_exists` (write without `--base-revision`, no `--overwrite`)**:
  prints helpful error pointing at `--overwrite`.
- **`meta_toml_protected`**: prints `jh: meta.toml is protected; use one
  of: jh apply, jh log, jh priority, ...` and exits non-zero.

The CLI does NOT track `base_revision` automatically — users who want
optimistic concurrency from the shell are scripting, and scripts can
capture revisions from `jh file show` output (revision is printed to
stderr or as part of a structured output mode). For interactive use,
`--overwrite` is the escape hatch and the user takes the risk.

### MCP tool surface

After this lands, MCP tool count goes from 32 to 37 (+5 net new). The
existing `list_files` and `read_file` move modules but stay registered
at the same names; their MCP-level signatures gain a `revision` in the
response.

| Tool | Args | Returns |
|---|---|---|
| `list_files` | `slug` | `[{name, size, mtime}]` (existing shape; no revision in list response) |
| `read_file` | `slug, name` | `{content, encoding, revision, size}` (revision added) |
| `write_file` | `slug, name, content: str, base_revision?, overwrite=False` | `{revision, merged}` |
| `import_file` | `slug, name, src_path, base_revision?, overwrite=False` | `{revision, merged}` |
| `export_file` | `slug, name, dst_path, overwrite=False` | `{revision}` |
| `append_file` | `slug, name, content: str` | `{revision}` |
| `delete_file` | `slug, name, base_revision?` | `{revision_before_delete}` |

All write tools reject `meta.toml` with `meta_toml_protected` error.
All write tools reject hidden filenames (starting with `.`) with
`invalid_filename` error. All write tools reject paths escaping the opp
dir with `path_outside_opp_dir` error.

## Conflict-detection state machine

Every write tool (`write_file`, `import_file`, `delete_file`) runs the
same six-case decision matrix. `append_file` is conflict-free by
construction and bypasses this entirely.

### Decision matrix

| # | `base_revision`? | File on disk | Disk matches `base_revision`? | Outcome |
|---|---|---|---|---|
| 1 | No | doesn't exist | — | **Clean create.** Write content, commit, return new revision. |
| 2 | No | exists, `overwrite=False` | — | **Error:** `file_exists`. AI must opt in. |
| 3 | No | exists, `overwrite=True` | — | **Blind overwrite.** Write, commit, return new revision. |
| 4 | Yes | doesn't exist | — | **Error:** `file_disappeared`. AI's file is gone; consult user. |
| 5 | Yes | exists | matches | **Clean write.** No conflict; write, commit, return new revision. |
| 6 | Yes | exists | doesn't match | **Conflict** — branch on file type (see below). |

### Case 6 — conflict resolution

Classify the *current disk content* by attempting utf-8 decode:

**Text path (utf-8-decodable):**

1. Reconstruct three sides:
   - **base**: content at `base_revision` (retrievable via `git cat-file
     -p <blob_sha>` for git-backed adapters; in-memory adapter caches
     content by revision).
   - **theirs**: current disk content.
   - **ours**: AI's proposed new content.
2. Run `git merge-file --stdout base.tmp ours.tmp theirs.tmp`.
3. **Merge succeeded (exit 0):** write the merged content with commit
   message `f"file: write {slug}/{name} (merged base=<short_base>
   theirs=<short_theirs>)"`. Return `WriteResult(revision=new,
   merged=True)`. The AI infers from `merged=True` that the on-disk
   content includes changes it didn't author.
4. **Merge conflicted (non-zero exit):** return error `conflict_text`
   with conflict-marker-annotated output and the three short SHAs.

**Binary path (current disk content not utf-8-decodable):**

No merge attempt. Return error `conflict_binary` with `{filename,
base_revision, current_revision, current_size, current_mtime,
suggested_alt_name}`. AI's options: overwrite anyway, save under
alternative name, or abandon.

### Append, Delete special cases

- **`append_file`** ignores `base_revision`. Concatenation is
  associative. File doesn't exist → create. File exists → append.
  Returns new revision.

- **`delete_file`** with `base_revision`:
  - File missing → `file_not_found`.
  - `base_revision` matches → delete; return last revision before
    delete.
  - `base_revision` doesn't match → `delete_stale_base`. AI's view is
    out of date; re-read and re-decide.
- **`delete_file`** without `base_revision`:
  - File exists → delete unconditionally (matches "this exists; remove
    it" intent).
  - File missing → `file_not_found`.

## Error response shapes

All errors follow the Phase 4 envelope: `{error: {code, message,
details}}`.

| Code | Trigger | `details` payload |
|---|---|---|
| `meta_toml_protected` | Any write tool on `meta.toml` | `{filename, use_instead: [<tool_name>, …]}` |
| `invalid_filename` | Hidden file write attempt or other rejected name | `{filename, reason}` |
| `path_outside_opp_dir` | Filename escapes opp dir after resolve | `{slug, filename}` (existing code; reused) |
| `file_exists` | Decision-matrix Case 2 | `{filename, current_revision}` |
| `file_not_found` | Read/export/delete on missing file | `{filename}` |
| `file_disappeared` | Decision-matrix Case 4 | `{filename, base_revision}` |
| `conflict_text` | Case 6 text path, merge failed | `{filename, base_revision, theirs_revision, conflict_markers_output}` |
| `conflict_binary` | Case 6 binary path | `{filename, base_revision, current_revision, current_size, current_mtime, suggested_alt_name}` |
| `delete_stale_base` | Delete with mismatched `base_revision` | `{filename, base_revision, current_revision}` |

### AI recovery hints (the key fields)

- `current_revision` on `file_exists`, `conflict_binary`,
  `delete_stale_base` — lets the AI re-read with confidence.
- `use_instead` on `meta_toml_protected` — lists the structured tools
  the AI should call (`set_status`, `set_priority`, `add_note`, …).
- `suggested_alt_name` on `conflict_binary` — pre-computed safe name
  (e.g., `cv-ai-draft.pdf` if the original was `cv.pdf`).
- `conflict_markers_output` on `conflict_text` — full text with `<<<<<<<`
  / `=======` / `>>>>>>>` markers; the AI can either show this to the
  user or attempt a programmatic re-resolution.

## Workflows

### AI creates a new file

```
AI → write_file(slug="acme-em", name="cover-letter.md", content="...")
file_service.write
  → store.exists → False → Case 1 (clean create)
  → store.write(..., commit_message="file: write acme-em/cover-letter.md")
  → MCP response: {revision: "<sha>", merged: false}
```

### AI edits a file (clean update)

```
AI → read_file(slug="acme-em", name="cover-letter.md")
  → response: {content: "...", revision: "abc123"}

(AI revises inline)

AI → write_file(slug="acme-em", name="cover-letter.md",
                content="...(revised)...", base_revision="abc123")
  → Case 5: matches → clean write → response: {revision: "def456", merged: false}
```

For very large files (a multi-page PDF), the AI uses `export_file` →
modifies the temp path with its own filesystem tools → calls
`import_file` with the temp path. Same conflict-detection; no bytes in
MCP messages.

### Text conflict, merge clean

```
AI → read_file(slug="acme-em", name="notes.md")
  → response: {content: "<old>", revision: "v1"}

(user runs `jh note acme-em --msg "..."` — notes.md → v2)

AI → write_file(slug="acme-em", name="notes.md",
                content="<old>\n## AI summary\n...", base_revision="v1")
  → Case 6, text path
  → 3-way merge clean
  → response: {revision: "v3", merged: true}
```

AI surfaces to user: "I merged my changes with an update that landed
since I read the file."

### Binary conflict, AI asks user

```
AI → read_file(slug="acme-em", name="cv.pdf")  # earlier; revision "pdf-v1"

(time passes; user updates cv.pdf externally; new revision "pdf-v2")

AI → import_file(slug="acme-em", name="cv.pdf",
                 src_path="/tmp/jh-cv-draft.pdf", base_revision="pdf-v1")
  → Case 6, binary path
  → error: code=conflict_binary
       details={current_revision: "pdf-v2", suggested_alt_name: "cv-ai-draft.pdf", ...}
```

AI's response to the user:

> "I tried to save my updated cv.pdf, but the file on disk has changed
> since I read it (now ~124 KB, last modified at 14:32). Options:
> 1. Overwrite anyway (set `overwrite=True`)
> 2. Save my version as `cv-ai-draft.pdf` instead
> 3. Abandon my version
>
> Which do you want?"

### `ops_service.add_note` post-migration

```python
def add_note(repo, store, slug, *, msg, today):
    line = f"- {today.isoformat()} {msg}\n".encode("utf-8")
    file_service.append(store, slug, "notes.md", line)
    before, opp_dir = repo.find(slug)
    after = before.touch(today=today)
    repo.save(after, opp_dir, message=f"note: {after.slug}")
    return before, after, opp_dir
```

This produces **two commits** per `jh note` (one from `file_service.append`
for `notes.md`, one from `repo.save` for the `last_activity` bump in
`meta.toml`). That's the deliberate trade-off from the no-`no_commit`
discipline.

### `commands/log.py` post-migration

```python
# inside log.py's run():
corr_name = f"correspondence/{_correspondence_filename(today_date, channel, direction, who)}"
file_service.write(
    store, slug_query, corr_name, body.read_bytes(),
    base_revision=None, overwrite=False,
)
before, after, _ = lifecycle_service.log_interaction(repo, slug_query, ...)
```

Also two commits (correspondence file + meta change).

## Testing strategy

Tests split along the port/adapter line.

### Layer coverage

| Layer | Approach | Fixture |
|---|---|---|
| `file_service.py` (orchestration + state machine + merge) | Against `InMemoryFileStore` — no subprocess, no git, no FS | `in_memory_store` |
| `GitLocalFileStore` (adapter — translates protocol to FS + git) | Against `tmp_path` git-init'd data root | `git_local_store` |
| `revisions.py` (NewType wrapper) | Pure unit tests | none |
| MCP `mcp/tools/files.py` | `call_tool` pattern (existing) with `InMemoryFileStore` | `mcp_paths` + `in_memory_store` |
| CLI `commands/file.py` | `invoke` fixture (existing) with `tmp_jh` — exercises the git-local adapter end-to-end since the CLI is the user-facing peer | `tmp_jh` + `invoke` |
| Stdio integration smoke | One stdio round-trip for a file API call | existing `stdio` fixture |
| Existing service tests (`add_note`, `log_interaction`) | Continue passing through the migration | both fixtures |

### Why `InMemoryFileStore`

A test-only adapter that proves the port abstraction is real:

```python
class InMemoryFileStore:
    def __init__(self) -> None:
        self._files: dict[tuple[str, str], bytes] = {}
        self._revisions_by_content: dict[bytes, str] = {}  # for base_revision recovery

    def write(self, slug, name, content, *, commit_message):
        self._files[(slug, name)] = content
    def read(self, slug, name):
        return self._files[(slug, name)]
    def compute_revision(self, slug, name):
        h = hashlib.sha1(self._files[(slug, name)]).hexdigest()
        return Revision(h)
    # ...
```

Three reasons it's load-bearing:

1. **Speed.** A 3-way-merge test against the git adapter has to: create
   tmp data root, git-init, scaffold opp, commit, modify, commit again,
   run `git merge-file` subprocess. Hundreds of ms per test. In-memory
   is microseconds.
2. **Determinism.** Tests assert on revision *equality*, never on the
   literal hash value, so the in-memory scheme's `sha1(content)` and
   the git adapter's `git hash-object` are interchangeable from the
   test's point of view.
3. **Proof the abstraction is real.** If application code leaks any
   git-specific assumption, the in-memory test fails — exactly the
   signal we want.

### Test layout

```
tests/
  application/
    test_file_service.py             # 6-case matrix × write/import/append/delete
                                     # 3-way merge clean + conflict
                                     # meta.toml protection + path traversal
                                     # ~25-30 tests
    test_revisions.py                # ~3 tests

  infrastructure/
    storage/
      __init__.py
      test_git_local_store.py        # ~8 tests: each mutation → one commit,
                                     # revision == git hash-object, etc.

  storage/
    __init__.py
    in_memory.py                     # InMemoryFileStore

  mcp/
    test_tools_files.py              # ~15 tests: one happy + one error per tool
    conftest.py                      # adds in_memory_store fixture

  test_cmd_file.py                   # ~10 tests: jh file list/show/write/
                                     # append/delete, plus conflict-error
                                     # surfacing
```

### Estimated count

~62–67 new tests (the file_service tests + adapter tests + MCP tool tests + ~10 new CLI command tests). Current suite is 307; after this spec lands, ~370.

### What we don't test heavily

- `git merge-file` internals — trust upstream.
- `InMemoryFileStore`'s sha1 — tests use equality only.
- `subprocess.run` mechanics beyond invoking `git hash-object` /
  `git merge-file` with sane args.

## Implementation sequencing

The dependency chain dictates the order. Each step ships green tests;
nothing leaves the codebase half-migrated.

**Step 1 — Port + adapter foundations.**

- `application/revisions.py`
- `infrastructure/storage/protocols.py` (the `FileStore` Protocol)
- `infrastructure/storage/git_local.py` (`GitLocalFileStore`)
- `tests/storage/in_memory.py` (`InMemoryFileStore`)
- `tests/infrastructure/storage/test_git_local_store.py`

Nothing else changes. The adapter just exists.

**Step 2 — `file_service.py` with all six cases + 3-way merge.**

Application-layer logic. Depends on the protocol from Step 1.
Includes:

- `read`, `write`, `import_`, `export`, `append`, `delete`, `list`
- The state machine + merge implementation
- All seven new error codes in `mcp/errors.py`
- `tests/application/test_file_service.py` against `InMemoryFileStore`

Still no integration with existing services or MCP. The service stands
alone, fully tested.

**Step 3 — MCP file tools.**

- Add `mcp/tools/files.py` with the 5 new tools.
- MOVE the existing `list_files` and `read_file` from
  `mcp/tools/reads.py` to `mcp/tools/files.py`.
- Update `mcp/server.py` to register the new module; drop the moves
  from `reads.py`.

After this step, the AI has the full file API. MCP tool count: 32 → 37.

**Step 4 — CLI file subcommand group.**

- Add `commands/file.py` with the 5 subcommands
  (`list`/`show`/`write`/`append`/`delete`).
- Register the subcommand group in `cli.py` (cyclopts supports nested
  app construction).
- Each subcommand calls `file_service.<op>` with a `GitLocalFileStore`
  built from `paths_from_config`.

After this step, the CLI is a peer adapter to MCP. Backend portability
is real.

**Step 5 — Migrate `ops_service.add_note` to use `file_service.append`.**

First existing service to drop direct FS access. `test_ops_service.py`
must stay green (with the two-commits-per-call adjustment if any test
asserted on commit count).

**Step 6 — Migrate `commands/log.py` correspondence-write to use
`file_service.write`.**

Same shape as Step 5.

**Step 7 — Audit + flag remaining direct-FS access.**

Grep `src/jobhound/` for direct file ops. Any remaining inside
`commands/` or `application/` (excluding `repository.create`
scaffolding) is a bug.

**Step 8 — Docs.**

Update `README.md` with both the new MCP file tools AND the `jh file`
subcommand group.

### PR shape

Recommended: **two PRs**.

- **PR A:** Steps 1–4 (foundations + MCP tools + CLI subcommands).
  Lands the full peer-adapter surface — both AI and CLI use the new
  service. No existing-code changes yet.
- **PR B:** Steps 5–8 (the migrations + audit + docs). Converts legacy
  callers; cleans up the last direct-FS access.

This sequencing lets both adapters (MCP and CLI) use the API the
moment PR A lands, without time pressure on the migration work.

## Open questions for review

None at the time of writing. The Q&A that produced this spec resolved:

- **Scope:** everything except `meta.toml` and hidden tool noise is
  user-stored content; the file API is the one and only way to access
  it.
- **Write workflow:** dual shape — `write_file` (content inline) for
  small/text, `import_file` (server moves from AI's temp path) for
  large/binary. AI picks per-call.
- **Read symmetry:** `export_file` (server copies to AI's temp path)
  added alongside the existing `read_file` (bytes inline).
- **Conflict detection:** optimistic concurrency via `base_revision`;
  3-way merge for text files via `git merge-file`; binary conflicts
  surface to the AI to ask the user.
- **Identity:** `Revision` NewType; `compute_revision()` on each
  adapter; today's git-local adapter uses git blob SHA via
  `git hash-object`.
- **Auto-commit:** always. No `no_commit` parameter. Two commits per
  composite action (e.g., `jh note` writes notes.md AND bumps
  last_activity) is the accepted trade-off.
- **Backend portability:** `FileStore` Protocol in
  `infrastructure/storage/protocols.py`; `GitLocalFileStore` is the
  first adapter; future adapters (S3, sqlite, in-memory) drop in
  without touching application or MCP layers.
- **`repository.create` scaffolding** stays direct as a documented
  exception (chicken-and-egg with the data root not yet existing).
- **CLI file commands** added as a peer adapter (`jh file
  list/show/write/append/delete`) — essential for backend portability
  (with non-FS adapters, the user can't reach the store directly via
  shell).
- **No `no_commit`** in this spec; broader removal is task #43.
- **Timestamp migration** (task #35) is independent.

## References

- Phase 4 spec: `docs/specs/2026-05-14-phase4-mcp-design.md` — the MCP
  adapter pattern this spec extends.
- Phase 4 cleanup plan: `docs/plans/2026-05-14-phase4-cleanup-cli-services.md`
  — established the application-service layer.
- `project_jh_ai_integration.md` (memory) — AI-driven workflow
  expectations.
- `feedback_timestamps_utc_local.md` (memory) — independent design
  pressure on dates; explicitly out of scope here.
- Task #43 — broader `no_commit` removal.
- Task #35 — timestamp migration.
