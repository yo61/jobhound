# Design: notes.md → per-note files migration (#102)

**Status:** Design approved 2026-06-08. Implementation pending.
**Related decision:** `decisions/2026-06-08-notes-storage-model.md` (amended in this PR — see Section 8).
**Tracking issue:** #102.

## Summary

Replace per-opportunity `notes.md` with per-note files under `<opp>/notes/`.
Each note is a separate Markdown file with TOML frontmatter (`created`
mandatory; `title` optional) and a per-opportunity monotonic sequence
number as the addressable ID.

The filename shape is `<seq>.md` (e.g. `5.md`) or `<seq>-<slug>.md`
(e.g. `5-charlotte-prep.md`) where `seq` is assigned at write time from
a counter held in `meta.toml` (`notes_next_seq`) and never decrements.
Deleting a note leaves a permanent gap in the sequence — `note 3` always
refers to the same content for the life of the opportunity.

A one-shot migration script ports existing `notes.md` files to the new
shape, assigning sequence numbers 1..N to parsed notes in chronological
order by `created`.

## Goals

- Each note is independently addressable, readable, editable, and
  deletable.
- Note IDs are stable: a user or agent who saw `note 3` an hour ago can
  still address `note 3` after any sequence of mutations.
- Storage shape is backend-portable. Sequence integers map cleanly to
  SQL primary keys, JSON IDs, or KV row keys. TOML frontmatter is
  parseable in any environment.
- `jh timeline` (#103) can read `created` from frontmatter without
  parsing filenames.
- Correspondence (#105) can adopt the same model later, reusing the
  frontmatter helper introduced here.

## Non-goals

- Backwards compatibility with the old `notes.md` layout. Per the
  project rule "Replace, don't deprecate," there is no dual-format
  read path. The migration script is the one-way upgrade.
- Cross-opportunity note operations (e.g. `note list` without a slug).
  Per-opp only, matching the rest of the CLI.
- Editing the `created` timestamp or `title` field via `note edit`.
  Frontmatter is preserved through edits; only the body changes.
- Status-transition history or git-replay-based timeline (out of scope
  for #102; tracked in #103).

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLI (commands/note.py)            MCP (mcp/tools/ops.py)           │
│   add  list  show  edit  remove     add_note  list_notes  read_note │
│                                     edit_note  remove_note          │
└─────────────────────┬───────────────────────────┬───────────────────┘
                      │                           │
                      ▼                           ▼
            ┌─────────────────────────────────────────────┐
            │  application/notes_service.py  (use cases)  │
            │   add_note · list_notes · read_note         │
            │   edit_note · remove_note                   │
            └────────┬───────────────────────────┬────────┘
                     │                           │
                     ▼                           ▼
         ┌──────────────────────┐   ┌────────────────────────────┐
         │ application/         │   │ application/file_service   │
         │ frontmatter.py       │   │ (existing — unchanged)     │
         │  parse · serialize   │   │ write / read / list / del  │
         │  Document dataclass  │   │                            │
         └──────────────────────┘   └──────────────┬─────────────┘
                                                   ▼
                                       ┌──────────────────────┐
                                       │ infrastructure/      │
                                       │ storage (FileStore)  │
                                       │  GitLocalFileStore   │
                                       └──────────────────────┘
```

**Boundary rules** (preserved from existing architecture):

- CLI and MCP adapters are thin — only call `notes_service`, never
  reach into `file_service` or storage directly.
- `notes_service` owns all filename, sequence, and frontmatter logic.
- `frontmatter.py` is pure — no FS, no store, no git. Bytes in,
  dataclass out (and vice versa).

## Components

### `application/frontmatter.py` (new — shared with correspondence)

Pure helper module. Two dataclasses, three functions.

```python
@dataclass(frozen=True)
class Frontmatter:
    created: datetime                       # tz-aware UTC; rejects naive
    title: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Document:
    frontmatter: Frontmatter
    body: str                               # bare markdown

class FrontmatterError(Exception):
    """Parse/validation failure with line context."""

def parse(content: bytes) -> Document: ...
def serialize(doc: Document) -> bytes: ...
def parse_or_synthesize(content: bytes, fallback_created: datetime) -> Document: ...
```

**File shape produced by `serialize`:**

```
+++
created = 2026-06-08T14:23:05Z
title = "Charlotte Eyre background"
+++

Body markdown — bullets, paragraphs, code, whatever.
```

- Delimiter `+++` on its own line (Hugo/Zola convention — unambiguous
  vs. markdown `---` horizontal rules and YAML frontmatter).
- Single blank line between frontmatter close and body.
- `title` omitted from output when `None` (no empty key).
- Body trailing newline added on write, stripped on parse (idempotent
  round-trip).
- `extras` mapping holds stream-specific frontmatter fields (e.g.
  `channel`, `direction`, `who` for correspondence in #105). This
  module never gains a per-consumer schema — typed views are layered on
  top by the consuming service.

**`parse` rules:**

- Empty content → `FrontmatterError("empty document")`.
- Doesn't start with `+++\n` → `parse` raises; `parse_or_synthesize`
  treats as bare markdown with the supplied `fallback_created`.
- Opening `+++` but no closing `+++` → `FrontmatterError("unclosed
  frontmatter")` with line number.
- TOML parse failure → `FrontmatterError` wrapping the
  `TOMLDecodeError`.
- `created` missing → `FrontmatterError("missing required field:
  created")`.
- `created` naive datetime → `FrontmatterError("created must be
  tz-aware UTC")` (matches `meta_io._validate_tz_aware` policy).
- Extras keys pass through into `extras` unchanged.

**TOML library:** stdlib `tomllib` for read, `tomli_w` for write — both
already in use via `meta_io.py`.

### `application/notes_service.py` (new)

Five use-case functions + typed result/error classes. Mirrors the
existing focused-service pattern (`lifecycle_service`, `field_service`,
`relation_service`). All five take `(repo, store, slug, ...)` for
caller symmetry — even the read-only ones, where the extra `repo.find()`
cost is trivial.

```python
@dataclass(frozen=True)
class NoteSummary:
    """Metadata only — what `list_notes` returns. No body fetched."""
    seq: int
    filename: str                           # "5.md" or "5-charlotte-prep.md"
    created: datetime
    title: str | None

@dataclass(frozen=True)
class Note:
    """Full note — what `read_note` and `edit_note` return."""
    seq: int
    filename: str
    created: datetime
    title: str | None
    body: str
    revision: Revision                      # for conflict-safe follow-up edits

@dataclass(frozen=True)
class AddNoteResult:
    before: Opportunity
    after: Opportunity
    opp_dir: Path
    seq: int
    filename: str


def add_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    *,
    body: str,
    title: str | None = None,
    now: datetime,
) -> AddNoteResult: ...

def list_notes(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
) -> list[NoteSummary]: ...                 # sorted by seq ascending

def read_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    seq: int,
) -> Note: ...                              # raises NoteNotFoundError

def edit_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    seq: int,
    *,
    body: str,
    base_revision: Revision | None = None,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Note]: ...

def remove_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    seq: int,
    *,
    now: datetime,
) -> tuple[Opportunity, Opportunity, int]: ...   # returns the removed seq
```

**Why `NoteSummary` vs `Note`.** `list_notes` enumerates `notes/*.md`
and reads only the frontmatter prefix of each file — it never has to
fetch full bodies. Returning a body-less type makes this contract
explicit at the type level and prevents an agent (or future caller)
from accidentally relying on `list_notes()[i].body`. `read_note` does
the body fetch and returns the full `Note` including the `revision`
that callers echo back as `base_revision` on a follow-up edit.

**Sequence assignment.** `add_note` reads `opp.notes_next_seq` from
`meta.toml`, uses that as the new note's seq, writes `+1` back as part
of the same `repo.save` that bumps `last_activity`. No filesystem scan;
the counter is authoritative.

**Filename construction** (used by `add_note`):

```python
def _filename(seq: int, title: str | None) -> str:
    if title is None:
        return f"{seq}.md"
    slug = slugify(title)
    if not slug:
        raise TitleSlugError(title, "slugifies to empty")
    return f"{seq}-{slug}.md"
```

Title slugification uses a new `domain/slug.slugify` helper (extracted
from the existing `commands/log.py::_name_slug` — same rule, reused by
notes, correspondence migration, and the existing log path).

**Filename parsing** (used by `list_notes` and `read_note` to find an
existing file from a `seq`):

```python
_NOTE_FILENAME = re.compile(r"^(\d+)(?:-[a-z0-9-]+)?\.md$")

def _parse_filename(name: str) -> int | None:
    """Return the seq from a valid note filename, or None."""
    m = _NOTE_FILENAME.match(name)
    return int(m.group(1)) if m else None
```

`list_notes` iterates `<opp>/notes/*.md`, applies `_parse_filename`,
discards `None` results (skipping hidden files / non-matching entries
without raising), and `_parse_filename` on a name that *looks* like a
note but isn't valid (e.g. `2-Foo_Bar.md` with uppercase or
underscore) returns `None` — those entries surface via a separate
strict scan that raises `NoteFilenameError`, so corruption isn't
silently hidden. `read_note(slug, seq)` resolves to the unique file
whose `_parse_filename` returns `seq`; if zero match, raises
`NoteNotFoundError`; if more than one matches (shouldn't happen,
defensive), raises `NoteFilenameError`.

**`add_note` flow:**

```python
def add_note(repo, store, slug, *, body, title=None, now) -> AddNoteResult:
    if not body.strip():
        raise EmptyBodyError()
    before, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    seq = before.notes_next_seq
    filename = _filename(seq, title)
    doc = Document(
        frontmatter=Frontmatter(created=now, title=title),
        body=body.strip(),
    )
    file_service.write(
        store, canonical, f"notes/{filename}", frontmatter.serialize(doc)
    )
    after = before.bump(now=now).with_notes_next_seq(seq + 1)
    repo.save(after, opp_dir, message=f"note: {after.slug} #{seq}")
    return AddNoteResult(before, after, opp_dir, seq, filename)
```

Two commits per add: one from `file_service.write` (the new note file),
one from `repo.save` (the meta.toml update). Same two-commit pattern as
the existing `ops_service.add_note`.

**`edit_note` flow.** Reads the existing file, preserves `created` and
`title`, rewrites the body. Passes `base_revision` through to
`file_service.write` so the existing six-case state machine handles
3-way merge on concurrent text edits — same conflict protection as
`jh file write`.

**`remove_note` flow.** Deletes the file via `file_service.delete`.
Does not decrement `notes_next_seq` — gaps are permanent (this is the
property that makes IDs stable).

**Exceptions:**

- `NoteNotFoundError(slug, seq)` — seq doesn't exist.
- `NoteFilenameError(filename, reason)` — file in `notes/` doesn't
  match the seq pattern (hand-corrupted or external write).
- `EmptyBodyError()` — body whitespace-only on add or edit.
- `TitleSlugError(title, reason)` — `--title` slugifies to empty.

**The existing `ops_service.add_note` is removed.** Per "Replace, don't
deprecate" — no shim. Callers (CLI command, MCP tool) move to
`notes_service.add_note`.

### `commands/note.py` (rewrite)

Replaces the current single-verb (`jh note add --msg`) module with the
full five-verb group. Breaking change.

```
jh note add SLUG BODY [--title SLUG] [--from PATH|-]
jh note list SLUG [--reverse]
jh note show SLUG SEQ [--with-frontmatter]
jh note edit SLUG SEQ [--from PATH|-]
jh note remove SLUG SEQ
```

**`note add`** — `BODY` is positional; `--from PATH|-` is mutually
exclusive with positional body. `--title` is optional, slugified by the
service. Empty body → exit 1.

**`note list`** — Rich-formatted by default, plain on non-TTY. Columns:
`#`, `CREATED`, `TITLE`. Gaps in seq are visible. `--reverse` shows
newest-first; default is seq ascending (= chronological creation
order). Empty `notes/` prints `(no notes)` to stderr; exit 0.

**`note show`** — Body to stdout by default (pipe-friendly).
`--with-frontmatter` prints the raw stored shape including `+++`.

**`note edit`** — `--from PATH|-` writes the new body directly. No
`--from` opens `$EDITOR` (fallback: `$VISUAL`, then `vi`) on a temp
file prefilled with the current body. Exit without changes → no
write, exit 1. Concurrency: service uses the revision from its own
read as `base_revision`; CLI doesn't thread it.

**`note remove`** — No interactive confirmation. Git-tracked data
makes deletes recoverable via `git revert`; an extra `--yes` for a
single-file operation is process noise. (Distinct from `jh delete
<opp>` which destroys the whole directory and keeps its `--confirm`
gate.)

**Error handling.** Service exceptions translate to stderr messages
and `exit 1`. `TextConflictError` / `BinaryConflictError` on `edit`
format the conflict markers — same pattern as `jh file write`.

### `mcp/tools/ops.py` (extend)

Tool names stay verb-first `snake_case` per the still-pending
MCP-naming question. `add_note` rewritten in place; four new tools
added.

```
add_note(slug, body, title=None, today=None)
list_notes(slug)
read_note(slug, seq, with_frontmatter=False)
edit_note(slug, seq, body, base_revision=None, today=None)
remove_note(slug, seq, today=None)
```

**`add_note` response:**

```json
{
  "opportunity": { /* mutation_response shape */ },
  "note": {
    "seq": 5,
    "filename": "5-charlotte-prep.md",
    "created": "2026-06-08T14:23:05Z",
    "title": "Charlotte prep"
  }
}
```

**`list_notes` response:**

```json
{
  "slug": "acme",
  "notes": [
    { "seq": 1, "filename": "1.md",                "created": "...", "title": null },
    { "seq": 2, "filename": "2-kickoff.md",        "created": "...", "title": "kickoff" },
    { "seq": 5, "filename": "5-charlotte-prep.md", "created": "...", "title": "Charlotte prep" }
  ]
}
```

Body excluded by design — `list_notes` is cheap directory enumeration;
`read_note` is the body fetch. Keeps token cost predictable for agents
iterating across many opps.

**`read_note` response:**

```json
{
  "slug": "acme",
  "note": {
    "seq": 5,
    "filename": "5-charlotte-prep.md",
    "created": "2026-06-08T14:23:05Z",
    "title": "Charlotte prep",
    "body": "Charlotte mentioned a 4-stage loop...",
    "revision": "a1b2c3d4..."
  }
}
```

`revision` is included so agents can echo it back as `base_revision`
on a follow-up `edit_note` — same `read_file` → `write_file` pattern
already used in `mcp/tools/files.py`. With `with_frontmatter=True`,
the `body` field includes the raw `+++` block.

**`edit_note` response:** same shape as `add_note` (mutation_response +
`note` block). Conflict errors translate via the existing handlers in
`mcp.errors`.

**`remove_note` response:**

```json
{
  "opportunity": { /* mutation_response shape */ },
  "removed_seq": 5
}
```

**New error translations** in `mcp.errors`:

- `NoteNotFoundError` → `{"error": "note_not_found", "slug", "seq"}`
- `EmptyBodyError` → `{"error": "empty_body"}`
- `NoteFilenameError` → `{"error": "note_filename_invalid",
  "filename", "reason"}`
- `TitleSlugError` → `{"error": "title_slug_invalid", "title",
  "reason"}`

### `infrastructure/repository.py::create` (edit)

```diff
 opp_dir.mkdir(parents=True)
-(opp_dir / "notes.md").write_text("")
+(opp_dir / "notes").mkdir()
 (opp_dir / "research.md").write_text(...)
 (opp_dir / "correspondence").mkdir()
```

Eager-create the `notes/` directory (matches existing
`correspondence/` treatment) so users browsing the data repo see where
notes will land. The empty directory is implicit via `notes_next_seq =
1` in `meta.toml`; Git's inability to track empty directories is not a
concern because `repository.create` is the only path that scaffolds an
opp.

### `Opportunity` domain model (edit)

```diff
 @dataclass(frozen=True)
 class Opportunity:
     company: str
     role: str
     slug: str
     ...
+    notes_next_seq: int = 1
```

- Default `1` keeps every existing constructor call working.
- New helper `with_notes_next_seq(n: int) -> Opportunity` for the
  immutable-update pattern (parallels `bump()`).
- Validation rejects `notes_next_seq < 1` in `meta_io.validate`.

### `meta_io.py` (edit)

Three changes:

1. Add `"notes_next_seq"` to `_FIELD_ORDER` — **last position** (after
   `next_action_due`), since it's machine-managed and not
   user-meaningful.
2. Add to `opportunity_from_dict` parsing.
3. `tomli_w.dump` writes it in canonical position.

No backwards-compat path. A pre-migration `meta.toml` (no
`notes_next_seq` field) raises at validate. The CHANGELOG breaking
note directs users to the migration script.

## Migration script — `scripts/migrate_notes_to_directory.py`

Mirrors `scripts/migrate_from_yaml.py` in shape. Dry-run by default,
`--apply` to write.

### CLI

```
uv run scripts/migrate_notes_to_directory.py            # dry-run
uv run scripts/migrate_notes_to_directory.py --apply
uv run scripts/migrate_notes_to_directory.py --only acme,menlo
```

### Per-opportunity algorithm

```
1. Locate <data_root>/opportunities/*/notes.md AND
                    <data_root>/archive/*/notes.md.
2. For each notes.md:
   a. Parse into a list of MarkerNote records (grammar below).
   b. Drop notes with whitespace-only body.
   c. Sort surviving markers by created ascending.
   d. Assign seq 1..N in that order.
   e. For each MarkerNote with assigned seq:
        write <opp>/notes/<seq>.md with:
          +++
          created = <original ISO timestamp>
          +++

          <body>
   f. Delete the original notes.md.
   g. Update meta.toml: notes_next_seq = N + 1.
   h. Commit as one commit:
        "migrate: notes.md → notes/ for <slug>"
3. Summary: opps migrated, notes ported, opps skipped.
```

### Grammar

```python
DATE_MARKER_H2  = re.compile(r"^## (\d{4}-\d{2}-\d{2})(?: — .*)?$")
DATE_MARKER_BUL = re.compile(r"^- (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) (.*)$")
```

- `DATE_MARKER_H2` matches start a new MarkerNote at the date with
  `T00:00:00Z` appended for `created`. Body is everything below up to
  the next marker, with the `## …` line stripped.
- `DATE_MARKER_BUL` starts a new MarkerNote with the full ISO
  timestamp as `created`. Body is `m.group(2)` plus any indented
  continuation lines beneath it.
- Pre-first-marker content is discarded (decision doc: "redundant
  title line").
- Date strings inside body text are not markers — only line-anchored
  `^## …` or `^- <ISO-Z-timestamp> …` count.

### Edge cases

| Case | Handling |
|---|---|
| H2 date differs from bullet timestamps under it | Both are markers. H2 becomes its own note (likely empty → skipped); each bullet is its own note. |
| Pre-first-marker preamble | Discarded silently. |
| Whitespace-only body after stripping | Skipped — not migrated. |
| Empty / template `notes.md` | Skipped; `notes/` dir created empty; `notes_next_seq = 1`. |
| Identical timestamps in same file | Both become distinct notes; chronological-sort tie-breaks by source-file order. No filename collision because seqs are sequential. |
| `notes.md` already missing | Logs `(already migrated)` and continues. Idempotent. |
| `notes/` directory already exists | Aborts that opp with a clear error — refuse to merge into a directory we didn't create. |
| Archive opps (`archive/*/notes.md`) | Migrated identically — corpus is uniform after one pass. |

### Dry-run output

Mirrors the YAML-migration script — one block per opp, with planned
per-file output and per-opp summary. The final summary block reports
total opps scanned / migrated / skipped and total notes ported.

### `--apply` mode

1. For each opp to migrate, perform all FS operations (write new
   files, update meta.toml, delete `notes.md`).
2. After per-opp FS work succeeds: `git add . && git commit -m
   "migrate: notes.md → notes/ for <slug>"` in the data repo. One
   commit per opp.
3. Mid-opp error → stop the script. Don't commit partial work.
   Already-committed earlier opps stay. User re-runs after fixing —
   the script is idempotent.

### Live-corpus dry-run review (workflow, not code)

Before `--apply`:

1. Run dry-run against the user's actual data repo.
2. Inspect output for the 6 known files (Menlo × 2, Tailscale, UKHSA,
   2 empty).
3. Spot-check 2-3 generated note bodies — bullet stripping,
   H2 stripping, discards.
4. Then `--apply`.

## Testing strategy

| Layer | File | What it covers |
|---|---|---|
| Frontmatter | `tests/application/test_frontmatter.py` (new) | parse/serialize round-trip, validation errors, `parse_or_synthesize` |
| notes_service | `tests/application/test_notes_service.py` (new) | add/list/read/edit/remove, sequence via `notes_next_seq`, exceptions |
| Domain | `tests/domain/test_opportunities.py` (extend) | `notes_next_seq` default, `with_notes_next_seq`, validation |
| meta_io | `tests/test_meta_io.py` (extend) | round-trip, reject invalid values |
| Repository | `tests/infrastructure/test_repository.py` (extend) | `create` makes `notes/` directory, no `notes.md` |
| CLI | `tests/commands/test_cmd_note.py` (new) | all five verbs end-to-end |
| MCP | `tests/mcp/test_tools_ops.py` (extend) | five tools end-to-end |
| Migration | `tests/scripts/test_migrate_notes.py` (new) | grammar, edge cases, idempotency, commit shape |
| Integration | `tests/integration/` | one cross-layer round-trip |

**Discipline:**

- Behavior, not implementation. Tests assert what verbs produce, not
  internal helpers.
- Edges and errors: empty body, missing seq, conflict on edit, both
  `BODY` and `--from`, non-existent opp, corrupt filename — covered.
- Mock only boundaries. Use `InMemoryFileStore` for fast
  service-layer tests; `GitLocalFileStore` against a temp data repo
  for integration. Don't mock `OpportunityRepository`, `notes_service`,
  or `frontmatter`.

**Property test** — one, on the frontmatter parser:

```python
@given(
    created=datetimes(timezones=just(UTC)),
    title=one_of(none(), text(min_size=1, max_size=80)),
    body=text(min_size=1, max_size=2000),
)
def test_roundtrip(created, title, body):
    doc = Document(Frontmatter(created=created, title=title), body=body)
    assert parse(serialize(doc)) == doc
```

Catches TOML datetime/quoting and body-boundary edge cases the
example tests would miss.

## Documentation

- `docs/commands.md` — replace the existing `jh add note` section with
  the new `jh note <verb>` group. One block per verb with shape,
  flags, example. Note that seq gaps are permanent.
- `README.md` — replace any `jh add note <slug> --msg ...` examples
  with `jh note add <slug> "..."`. Update any quick-start that
  references `notes.md`.

## CHANGELOG entry (breaking change)

```
### ⚠ BREAKING CHANGES

* `notes.md` replaced by per-note files under `<opp>/notes/`. Each
  note is a separate file (`<seq>.md` or `<seq>-<title>.md`) with TOML
  frontmatter holding `created` and optional `title`.
* `jh add note <slug> --msg "..."` is removed. Use
  `jh note add <slug> "..."` (positional body, optional `--title`,
  optional `--from PATH|-`).
* New CLI verbs: `jh note list`, `jh note show`, `jh note edit`,
  `jh note remove`.
* New MCP tools: `list_notes`, `read_note`, `edit_note`, `remove_note`.
* `meta.toml` gains a machine-managed `notes_next_seq` integer field
  (monotonic counter, never decrements on delete).
* Existing data repos require migration. Run
  `uv run scripts/migrate_notes_to_directory.py --apply` after
  pulling. Run without `--apply` first to review the dry-run output.
```

## Decision-doc amendment

First commit in the PR. `decisions/2026-06-08-notes-storage-model.md`
gets a `## Revision (2026-06-08)` section appended:

- Filename shape changed from Unix-timestamp to per-opportunity
  monotonic sequence (`<seq>.md` or `<seq>-<title>.md`).
- Counter `notes_next_seq` lives in `meta.toml` and never decrements.
- Reasoning: the decision's intent ("identity must look like a
  primary key, not a path") is satisfied more directly by a monotonic
  integer than by a Unix timestamp. Backend portability is preserved.
  User-facing IDs are stable across deletes.
- Migration assigns seq 1..N in chronological order by `created`.
- Original sections of the doc stay intact — design evolution is
  auditable in time order.

## PR sequencing (single PR, ordered commits)

1. `docs:` amend `decisions/2026-06-08-notes-storage-model.md` with
   Revision section.
2. `feat:` `application/frontmatter.py` + tests.
3. `feat:` `application/notes_service.py` + tests; remove old
   `ops_service.add_note`.
4. `feat:` `Opportunity.notes_next_seq` + `meta_io` field + tests.
5. `feat:` `repository.create` — `notes/` dir instead of `notes.md`.
6. `feat!:` `commands/note.py` — five-verb group; update any callers
   in `commands/__init__.py` registration.
7. `feat:` `mcp/tools/ops.py` — rewrite `add_note`, add four new
   tools; new error translations in `mcp.errors`.
8. `feat:` `scripts/migrate_notes_to_directory.py` + tests.
9. `docs:` `docs/commands.md` + `README.md` updates.
10. `chore:` CHANGELOG entry for the breaking change.

Reviewer reads commits top-to-bottom and follows the design.

## Open questions resolved during brainstorming

- **Service module:** new `notes_service.py` (not extension of
  `ops_service`).
- **Addressing:** per-opp monotonic sequence; user references by
  integer seq (`jh note show acme 5`).
- **Stability:** counter held in `meta.toml`, never decrements;
  deletes leave permanent gaps.
- **List display:** show the N from the filename, gaps visible.
- **Decision doc:** amend existing in place with a Revision section.
- **PR sequencing:** single PR with ordered commits.
