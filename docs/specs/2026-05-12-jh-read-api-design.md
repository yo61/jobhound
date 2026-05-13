# `jh` Read API — Design Spec (Phase 3a)

Date: 2026-05-12 (revised 2026-05-13)
Status: Draft, awaiting review
Branch: `feat/phase3-read-api-design`

## Goal

Expose `jh`'s opportunity data to in-process consumers through a single
library API, and surface that API on the command line via `jh show` and
`jh export`. The library is shaped so a later phase can wrap it in an HTTP
daemon with a web UI without rework.

This is **Phase 3a** of a larger absorption effort: the dashboard, today,
CV, PDF, and ICS renderers currently in `~/Documents/Projects/Job Hunting
2026-04/internals/scripts/` will move into `jobhound` as DDD application
services in subsequent sub-phases (3b, 3c). After absorption, `Job Hunting
2026-04` becomes archival data only.

## Strategic direction

### Why absorb the Job Hunting 2026-04 renderers into `jobhound`

The original two-repo split (jobhound for code, Job Hunting 2026-04 for
data + scripts) was driven by a *constraint*: data lived in iCloud-synced
`~/Documents`, where `UF_HIDDEN` flags on binary caches broke Python
venvs. With the data root now at `~/.local/share/jh/` (outside iCloud),
that constraint is gone, and so is the reason to keep the bounded context
split across two repos.

The `Opportunity` aggregate in `jobhound` and the `Opportunity` dataclass
in `Job Hunting 2026-04/internals/scripts/opportunities.py` already model
the same concept. The DDD answer is: don't split a bounded context across
repos unless deployment forces you to. Nothing forces this anymore.

### Sub-phase sequencing

Each sub-phase ships independently; you can stop or redirect between them.

| Sub-phase | Deliverable | Adds runtime deps? |
|---|---|---|
| **3a** *(this spec)* | Library: `OpportunityQuery`, snapshots, serialisation. CLI: `jh show`, `jh export`. | No |
| **3b** | `jh dashboard`, `jh today`. Markdown + HTML + ICS feed. | No (stdlib only) |
| **3c** | `jh cv`, `jh pdf`. CV rendering, generic markdown→PDF. Behind `pip install jobhound[reports]` extra. | `reportlab`, `mistune` (optional) |
| **3d** | Verify `Job Hunting 2026-04` has no live writes since migration; archive in place with read-only flags. | — |
| *(later, separate spec)* | HTTP daemon + web UI. Behind `pip install jobhound[web]` extra. | `starlette`, `jinja2`, `uvicorn` (optional) |

### Optional extras strategy

The dashboard's markdown and HTML renderers, plus `today.md` and the ICS
feed, use stdlib only (`html.escape`, `string.Template`, plain string
formatting). They ship by default — `pip install jobhound` gets the CLI
*and* `jh dashboard`.

PDF rendering brings `reportlab` (multi-MB) and a markdown parser. It is
gated behind `pip install jobhound[reports]`. The PDF application services
lazy-import the heavy deps so CLI startup is unaffected for users without
the extra.

The future daemon will be gated behind `pip install jobhound[web]` for the
same reason.

## Scope of this spec (Phase 3a only)

In scope:

- New read-only **query layer** in `jobhound`: `OpportunityQuery`, filter
  dataclass, snapshot dataclasses, JSON serialisation helpers.
- New CLI commands: `jh show <slug>` (human text by default, `--json` for
  machines) and `jh export` (streaming JSON envelope to stdout).
- File-listing and file-reading APIs the future CV/MD-to-PDF application
  services will route through.
- **DDD layer reorganisation**: split today's flat `src/jobhound/` into
  `domain/`, `infrastructure/`, `application/`, `commands/` subpackages.
  Done as a mechanical prologue commit before any new code lands.

Out of scope (deferred to later sub-phases):

- Dashboard / today / CV / PDF / ICS renderers (3b, 3c).
- HTTP daemon / web UI (later, separate spec).
- Write API for external consumers — mutations stay in CLI commands
  routed through `OpportunityRepository`.
- `--to <dir>` / `--archive` bundling on `jh export`. Use cases
  (hand-off, backup, portability, schema escape hatch) are deferred until
  a real consumer exists. `jh export` in Phase 3a is streaming JSON only.

## Why a library, not a daemon (now)

We considered three ways to enforce "no direct DB access from consumers":

1. **`jh` as a Python library.** In-process consumers (now: future
   application services for dashboard/CV/PDF; eventually: HTTP handlers in
   a daemon) import `jobhound.application.query`. They never read
   `meta.toml` directly; `OpportunityQuery` is the public read surface.
   *Chosen.*
2. **Subprocess + JSON.** External consumers `subprocess.run(["jh",
   "export"])` and parse stdout. Honours the principle, language-agnostic,
   ~100–300 ms per call. *Supported as a side-effect of `jh export`.*
3. **HTTP daemon.** Consumers hit `http://localhost:PORT/...`. Adds port
   management, daemon lifecycle, route design, auth model, client
   library — none of which earn their keep yet. *Future.*

The library route satisfies the architectural goal at the lowest cost.
When the daemon ships, its HTTP handlers will inject the same
`OpportunityQuery`; the library is the foundation, not a detour.

## The implicit daemon API (what the library is shaped for)

When a daemon eventually ships, these are the endpoints it will expose.
Listed here so the library's public surface can be checked against the
eventual HTTP contract.

| Method | Path | Library call | Used by |
|---|---|---|---|
| `GET` | `/opportunities?status=&priority=&slug=&active_only=&include_archived=` | `query.list(filters, today=...)` | dashboard, frontend list |
| `GET` | `/opportunities/{slug}` | `query.find(slug, today=...)` | `jh show`, CV service, frontend detail |
| `GET` | `/opportunities/{slug}/files` | `query.files(slug)` | CV service, frontend |
| `GET` | `/opportunities/{slug}/files/{filename}` | `query.read_file(slug, filename)` | CV, md→pdf, frontend file viewer |
| `GET` | `/stats?status=&priority=...` | `query.stats(filters)` | dashboard funnel, frontend summary |

Every response carries envelope metadata (`schema_version`, `timestamp`,
`db_root`), so no separate `/meta` endpoint is needed.

No write endpoints. Writes stay in CLI commands via
`OpportunityRepository`.

## Architecture

### DDD layer split

The existing `src/jobhound/` is flat. As part of Phase 3a we reorganise
into subpackages that mirror the DDD layers:

```
src/jobhound/
  __init__.py
  cli.py                                 # adapter — Cyclopts App; subcommand registration

  domain/                                # pure domain — no I/O, no infrastructure
    __init__.py
    opportunities.py                     # Opportunity aggregate
    status.py priority.py contact.py     # value objects
    slug.py slug_value.py
    transitions.py                       # domain service

  infrastructure/                        # I/O + persistence + config
    __init__.py
    repository.py                        # OpportunityRepository (write side)
    meta_io.py                           # tomllib/tomli_w + ValidationError
    paths.py                             # Paths dataclass + paths_from_config
    config.py                            # XDG-strict config loader
    git.py                               # auto-commit helper

  application/                           # use-case services + read views
    __init__.py
    query.py                             # OpportunityQuery + Filters     (3a)
    snapshots.py                         # OpportunitySnapshot, etc.     (3a)
    serialization.py                     # JSON dict converters          (3a)
    # later:
    # dashboard_service.py today_service.py    (3b)
    # cv_service.py pdf_service.py ics_service.py  (3c)

  commands/                              # adapter — CLI subcommands
    __init__.py
    new.py apply.py log.py ... (existing)
    show.py export.py                    # (3a)
    # later: dashboard.py today.py cv.py pdf.py (3b/3c)

  prompts.py                             # presentation helper (questionary)
```

Notes on the reorganisation:

- `cli.py` and `prompts.py` stay at the package root: `cli.py` is the
  entry point; `prompts.py` is a presentation utility used by command
  modules. Neither belongs in a single DDD layer.
- The reorganisation is the **first commit** of Phase 3a. It is purely
  mechanical: `git mv` source files, rewrite imports, no behaviour
  change. The test suite (142 tests) must pass at the new import paths
  before any new code lands.
- The reorg commit message follows Conventional Commits: `refactor:
  reorganise package into domain/infrastructure/application/commands
  subpackages`.
- `OpportunityRepository` keeps its full surface — it remains the sole
  write path. `OpportunityQuery` is a *sibling* (not a subclass, not a
  wrapper) so reads have no git side effects on construction.

### CQRS-shaped read/write split

The existing `OpportunityRepository` (`src/jobhound/infrastructure/
repository.py` post-reorg) owns **writes**: scaffolding, saving, archive,
delete, and the auto-commit step. Its constructor calls `ensure_repo`, a
write-side concern.

`OpportunityQuery` (new, `src/jobhound/application/query.py`) is the
**read** side: no git side effects on construction, no `Config`
dependency (auto-commit knobs are irrelevant for reads), no methods that
mutate disk. Tests and callers use either independently.

### Library API

#### `application/query.py`

```python
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from jobhound.application.snapshots import (
    FileEntry, OpportunitySnapshot, Stats,
)
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.paths import Paths


@dataclass(frozen=True)
class Filters:
    """Optional read-time filters. Empty/None = no filter on that dimension."""
    statuses: frozenset[Status] = field(default_factory=frozenset)
    priorities: frozenset[Priority] = field(default_factory=frozenset)
    slug_substring: str | None = None
    active_only: bool = False
    include_archived: bool = False


class OpportunityQuery:
    """Read-only view over the data root. The public read surface of `jh`."""

    def __init__(self, paths: Paths) -> None: ...

    def list(
        self, filters: Filters = Filters(), *, today: date,
    ) -> list[OpportunitySnapshot]:
        """Return all snapshots matching filters, sorted by slug."""

    def find(self, slug: str, *, today: date) -> OpportunitySnapshot:
        """Return one snapshot. Raises FileNotFoundError if the slug is unknown."""

    def files(self, slug: str) -> list[FileEntry]:
        """List every file inside the opportunity dir, recursive into correspondence/."""

    def read_file(self, slug: str, filename: str) -> bytes:
        """Read the bytes of a single file inside the opportunity dir."""

    def stats(self, filters: Filters = Filters()) -> Stats:
        """Aggregate counts: funnel per Status, count per source."""
```

Notes:

- `today` is a **required keyword argument** for `list` and `find`. The
  derived flags (`is_stale`, `looks_ghosted`, `days_since_activity`) depend
  on "today's date"; passing it explicitly keeps the layer pure (no
  implicit `date.today()`) and makes tests deterministic. CLI callers
  pass `date.today()`; a future daemon would pass the request time.
- `read_file` returns **bytes**, not `str`. Markdown is text but PDFs and
  other binaries are not. Consumers decode as appropriate.
- Filter semantics: `statuses` and `priorities` are **OR within the
  set**; filters are **AND across dimensions**. `active_only=True` is
  sugar for "any status where `Status.is_active`"; it AND-combines with
  an explicit `statuses` filter (intersection).
- `include_archived=False` (default) reads only `paths.opportunities_dir`.
  `True` reads from both `opportunities_dir` and `archive_dir`; each
  snapshot carries `archived: bool` so consumers can group.
- The class is thread-safe in the read sense (no shared mutable state);
  a daemon can serve concurrent reads without locking.

#### `application/snapshots.py`

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status


@dataclass(frozen=True)
class ComputedFlags:
    is_active: bool
    is_stale: bool
    looks_ghosted: bool
    days_since_activity: int | None


@dataclass(frozen=True)
class OpportunitySnapshot:
    opportunity: Opportunity        # the raw aggregate (unchanged)
    archived: bool                   # was loaded from archive_dir/
    path: Path                       # absolute path to the opp dir
    computed: ComputedFlags          # derived at snapshot time


@dataclass(frozen=True)
class FileEntry:
    name: str                        # relative to opp_dir, e.g. "cv.md"
                                     # or "correspondence/2026-05-01-x.md"
    size: int
    mtime: datetime                  # tz-aware (UTC)


@dataclass(frozen=True)
class Stats:
    funnel: dict[Status, int]        # every Status present; absent → 0
    sources: dict[str, int]          # "(unspecified)" key for None source
```

#### `application/serialization.py`

```python
from datetime import datetime
from pathlib import Path
from typing import Any

from jobhound.application.snapshots import (
    FileEntry, OpportunitySnapshot, Stats,
)

SCHEMA_VERSION: int = 1


def list_envelope(
    snapshots: list[OpportunitySnapshot],
    *,
    timestamp: datetime,
    db_root: Path,
) -> dict[str, Any]:
    """Build the bulk-export envelope."""


def show_envelope(
    snapshot: OpportunitySnapshot,
    *,
    timestamp: datetime,
    db_root: Path,
) -> dict[str, Any]:
    """Build the single-opportunity envelope (jh show --json)."""


def snapshot_to_dict(snap: OpportunitySnapshot) -> dict[str, Any]: ...
def file_entry_to_dict(entry: FileEntry) -> dict[str, Any]: ...
def stats_to_dict(stats: Stats) -> dict[str, Any]: ...
```

These are the only functions that know about JSON shape. The CLI, future
daemon, and any future export format share them. Functions return
JSON-native types only (`str`, `int`, `bool`, `None`, `list`, `dict`);
dates, datetimes, `Path`, and `StrEnum` values are converted explicitly
inside the serialisers, so `json.dumps` does not need a `default` hook.

### JSON shape — list envelope

```json
{
  "schema_version": 1,
  "timestamp": "2026-05-12T14:23:45.121Z",
  "db_root": "/Users/robin/.local/share/jh",
  "opportunities": [
    {
      "slug": "2026-05-acme-em",
      "company": "Acme Corp",
      "role": "Engineering Manager",
      "status": "applied",
      "priority": "high",
      "source": "LinkedIn",
      "location": "Remote, UK",
      "comp_range": "£110k–£130k",
      "first_contact": "2026-05-01",
      "applied_on": "2026-05-03",
      "last_activity": "2026-05-10",
      "next_action": "Follow up with recruiter",
      "next_action_due": "2026-05-17",
      "tags": ["remote", "fintech"],
      "contacts": [
        {"name": "Jane Doe", "role": "Recruiter", "channel": "email"}
      ],
      "links": {"posting": "https://..."},
      "archived": false,
      "path": "/Users/robin/.local/share/jh/opportunities/2026-05-acme-em",
      "computed": {
        "is_active": true,
        "is_stale": false,
        "looks_ghosted": false,
        "days_since_activity": 2
      }
    }
  ]
}
```

Field rules:

- **Dates**: ISO 8601 dates (`YYYY-MM-DD`), strings.
- **Timestamps**: ISO 8601 UTC (`2026-05-12T14:23:45.121Z`).
- **Enums** (`status`, `priority`): lowercase strings matching the
  `StrEnum` values. Already true today since both are `StrEnum`.
- **None values on raw opportunity fields**: omitted entirely (no
  `"source": null`). Matches the TOML serialisation pattern in
  `meta_io.py:_as_serializable`.
- **`computed` block**: every key is always present.
  `days_since_activity` is the one field that can be `null` (when
  `last_activity` is unset); consumers can rely on the other keys
  existing as booleans.
- **Empty collections** (`tags: []`, `contacts: []`, `links: {}`):
  emitted as empty containers, **not omitted**. Consumers can rely on
  the keys existing.
- **`path`**: absolute, since most consumers want to open files
  directly. `db_root` is at the envelope level for any consumer that
  wants relative reconstruction.

### JSON shape — show envelope (`jh show --json`)

Same envelope, singular key:

```json
{
  "schema_version": 1,
  "timestamp": "2026-05-12T14:23:45.121Z",
  "db_root": "/Users/robin/.local/share/jh",
  "opportunity": { /* same shape as one element of opportunities[] */ }
}
```

### JSON shape — file entries (`query.files(slug)` output, serialised)

Not exposed via CLI in Phase 3a (no `jh files` command). Documented here
for the daemon contract:

```json
[
  {"name": "meta.toml", "size": 412, "mtime": "2026-05-10T12:01:33Z"},
  {"name": "notes.md", "size": 1480, "mtime": "2026-05-08T19:44:02Z"},
  {"name": "cv.md", "size": 6210, "mtime": "2026-05-03T08:12:00Z"},
  {"name": "correspondence/2026-05-01-recruiter-intro.md",
   "size": 982, "mtime": "2026-05-01T15:33:10Z"}
]
```

### JSON shape — stats

```json
{
  "schema_version": 1,
  "timestamp": "2026-05-12T14:23:45.121Z",
  "funnel": {
    "prospect": 2, "applied": 3, "screen": 1, "interview": 0, "offer": 0,
    "accepted": 0, "declined": 0, "rejected": 1, "withdrawn": 0, "ghosted": 0
  },
  "sources": {
    "LinkedIn": 4, "Referral": 2, "(unspecified)": 1
  }
}
```

Stats over a filtered subset reflect the same filters passed in.

## CLI commands

### `jh show <slug> [--json]`

```
jh show 2026-05-acme-em
jh show acme                    # uses resolve_slug (prefix match, prompt if ambiguous)
jh show acme --json
```

Behaviour:

- Slug resolution uses the existing `resolve_slug` from
  `jobhound.domain.slug` for consistency with `jh log`, `jh apply`, etc.
- **Default output** (no `--json`): human-readable text. Sections:
  - Header line: `Company — Role  (slug)`
  - Status block: `Status / Priority / Applied / Last activity / Next
    action (due) / Days since activity`
  - Tags (if any), contacts (if any), links (if any), source/location/
    comp (if set).
  - Files block (one line per file from `query.files(slug)`).
  - Path footer: `Path: <abs>`.
  - No ANSI colour by default; respect `NO_COLOR` env if we ever add
    colour.
- **`--json`**: pretty-printed JSON (indent=2) on stdout. The
  `show_envelope` shape above.

Implementation pattern (matches `commands/list_.py`):

```python
def run(slug: str, *, json_out: bool = False) -> None:
    cfg = load_config()
    paths = paths_from_config(cfg)
    q = OpportunityQuery(paths)
    snap = q.find(slug, today=date.today())
    if json_out:
        envelope = show_envelope(snap, timestamp=_now_utc(), db_root=paths.db_root)
        print(json.dumps(envelope, indent=2))
    else:
        _print_human(snap, q.files(slug))
```

The flag in cyclopts: `json_out: Annotated[bool, Parameter(name=["--json"])] = False`.
The parameter is named `json_out` to avoid shadowing the `json` stdlib
module at the call site; the user-facing flag is `--json`.

### `jh export`

```
jh export                                          # all non-archived, default filters
jh export --status applied,screen                   # any of these statuses
jh export --priority high                           # high priority only
jh export --slug acme                               # substring match
jh export --active-only                             # any active status (sugar)
jh export --include-archived                        # add archive/ to the walk
jh export --status applied --status screen --priority high   # repeatable form
```

Filter semantics:

- `--status` / `--priority` accept comma-separated values *or* repeated
  flags (cyclopts list-typed parameter handles both).
- `--slug` is **substring match** against the slug. No regex, no glob.
- `--active-only` is sugar for "any active status"; intersects with
  `--status` if both are given.
- `--include-archived` adds the archive walk; off by default to match
  `jh list`.
- All filters AND across dimensions; values OR within a dimension.

Output: pretty-printed JSON (`indent=2`) on stdout, the `list_envelope`
shape.

Exit codes:

- `0` on success (including empty result).
- `2` on unknown filter values (e.g. `--status foo`). Cyclopts handles
  this automatically via `Status(value)` coercion.
- `1` on unexpected I/O errors.

## Error handling

| Condition | Library raises | CLI exit | CLI stderr |
|---|---|---|---|
| Unknown slug in `show` | `FileNotFoundError` | 2 | `jh: no opportunity matches: <query>` |
| Invalid `--status foo` | `ValueError` (from `Status(...)`) | 2 | `jh: invalid status: foo` |
| Corrupt `meta.toml` | `ValidationError` (existing) | 1 | `jh: <path>: <reason>` |
| File outside opp dir requested | `ValueError` | 2 | `jh: filename must be inside the opportunity directory: <name>` |
| `correspondence/` etc. missing | silently empty list | 0 | — |

`read_file(slug, filename)` MUST reject path traversal: any `filename`
containing `..` or starting with `/` raises `ValueError`. The resolved
path must lie under `opp_dir.resolve()`.

## Testing strategy

Tests live in `tests/`, mirroring the package structure. New test files
(Phase 3a):

- `tests/application/test_query.py` — `OpportunityQuery` happy paths and
  filter cross-products.
- `tests/application/test_snapshots.py` — snapshot construction, derived
  flags vs raw fields.
- `tests/application/test_serialization.py` — JSON shape exactly matches
  the spec (compare against a fixture dict). Stable field order. Empty
  collections preserved.
- `tests/commands/test_cmd_show.py` — human output sections, `--json`
  output, slug resolution.
- `tests/commands/test_cmd_export.py` — filter combinations, envelope
  shape, exit codes.

Existing tests under `tests/` get their imports rewritten as part of the
reorg commit. The 142-test suite must pass post-reorg before any new code
lands.

Conventions (from `quality/criteria.md`):

- Real TOML fixtures on a `tmp_path` data root (no mocks of `meta_io`).
- Every `raise` in `query.py` / `serialization.py` has a triggering test.
- Filter behaviour tests assert against `Status.APPLIED`, not the string
  `"applied"` (typed-field rule).
- Snapshot tests assert against `Priority.HIGH`, not `"high"`.
- Path-traversal rejection has its own test
  (`test_read_file_rejects_traversal`).

Test data root construction: a `query_paths` fixture that builds a
`tmp_path` with a couple of opportunities (one active, one stale, one
archived). Reused across `test_query.py` and `test_cmd_export.py`.

## Phase 3b and 3c — sketch (not in this spec)

For context, so the read API's shape can be sanity-checked against the
eventual consumers. Detailed specs land separately when 3b/3c begin.

### Phase 3b — dashboard + today (stdlib only)

New application services in `src/jobhound/application/`:

- `dashboard_service.build_view(query, filters, today) -> DashboardView`
  — composes `query.list()` + `query.stats()` into a view model:
  active-sorted, stale-flagged, funnel counts, source breakdown.
- `today_service.build_view(query, today) -> TodayView` — overdue / due
  today / due soon buckets.

New commands:

- `jh dashboard [--open]` — writes `dashboard.md` and `dashboard.html` to
  the cache dir; `--open` opens the HTML in the default browser.
  Manual-only; no auto-rebuild on mutations.
- `jh today` — writes `today.md` to the cache dir and prints its
  contents.
- `jh ics [--write <path>]` — writes the ICS feed; default path is
  `<cache>/reminders.ics`.

Cache dir is the existing `paths.cache_dir` (`~/.cache/jh/`, via
`xdg_cache_home`).

### Phase 3c — CV + PDF (optional `[reports]` extra)

New application services:

- `cv_service.resolve_source(query, slug) -> CvSource` — locates the
  opportunity's `cv.md` (via `query.read_file`) and the matching
  `_shared/cv_base/` source.
- `pdf_service.render(markdown_bytes, layout) -> bytes` — generic
  markdown→PDF via `reportlab` + `mistune`. Lazy-imports the heavy deps.

New commands (all gated behind `jobhound[reports]`):

- `jh cv <slug> [--out <path>]` — renders the opp's CV to PDF.
- `jh pdf <markdown_path> [--out <path>]` — generic markdown→PDF.

The reportlab/mistune imports happen inside the application service
modules, behind a small `_ensure_reports_extra_installed()` guard that
raises a clear error if the extra isn't installed.

### Phase 3d — archive Job Hunting 2026-04

1. Verify no commits or file edits in `~/Documents/Projects/Job Hunting
   2026-04/` since the 2026-05-12 migration.
2. Diff `opportunities/` against `~/.local/share/jh/opportunities/` to
   confirm only the YAML→TOML format change differs.
3. Rename to `.Job-Hunting-2026-04.archived` (leading-dot hide).
4. Apply `chflags -R uchg` to lock files read-only.
5. Leave a `README.md` at the renamed path pointing at the `jobhound`
   repo and the `~/.local/share/jh/` data root.

## Open questions for review

None at the time of writing. The Q&A that produced this spec resolved:

- `show` defaults to human text, `--json` for machines.
- Snapshot includes raw fields + namespaced `computed` block.
- Bulk output is an envelope object with `schema_version`, `timestamp`,
  `db_root`.
- Archive off by default, `--include-archived` to opt in; `archived`
  flag on every snapshot.
- All filters in: `--status`, `--priority`, `--slug`, `--active-only`,
  `--include-archived`. Comma-or-repeated for multi-value; substring
  for slug.
- Library route (not daemon, not subprocess-only) — daemon is a future
  phase.
- `OpportunityQuery` is a separate class from `OpportunityRepository`;
  reads have no git side effects.
- Library ships `stats()` (one source of truth for funnel/source rules).
- `jh export` in Phase 3a is streaming JSON only; bundling deferred.
- File listing is recursive (`correspondence/` entries appear as
  `correspondence/<name>`).
- DDD subpackage layout (`domain/`, `infrastructure/`, `application/`,
  `commands/`). Reorg is the first commit of Phase 3a.
- HTML dashboard ships by default (stdlib only); PDF rendering behind
  `[reports]` extra; future web behind `[web]` extra.
- `jh dashboard` is manual-only; rebuild on every invocation.
- Job Hunting 2026-04: archive in place (Phase 3d) after verifying no
  live writes since migration.

## References

- Multi-phase project memory (`project_jh_cli.md`): Phase 3 / consumer
  absorption.
- DDD refactor spec: `docs/specs/2026-05-11-jh-cli-design.md`.
- Existing repository surface: `src/jobhound/repository.py`.
- Existing aggregate: `src/jobhound/opportunities.py`.
- Renderers to be absorbed (read-only references, currently
  inaccessible from sandbox):
  - `~/Documents/Projects/Job Hunting 2026-04/internals/scripts/build_dashboard.py`
  - `~/Documents/Projects/Job Hunting 2026-04/internals/scripts/render.py`
  - `~/Documents/Projects/Job Hunting 2026-04/internals/scripts/render_cv.py`
  - `~/Documents/Projects/Job Hunting 2026-04/internals/scripts/md_to_pdf.py`
