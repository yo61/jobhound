# Unarchive + List Filters — Design

Date: 2026-06-05
Status: Drafted, awaiting review
Branch: not yet cut (suggest `feat/unarchive-and-list-filters` when work begins)

Add an `unarchive` verb (CLI + MCP) and filter flags (`--all`, `--archived`,
`--status`) to `jh list` and `jh stats`. Today `jh list` is hard-wired to
"active opportunities only" via `OpportunityRepository.all()`, and there is
no public way to take an opportunity out of the archived state. This design
closes both gaps without changing the default `jh list` output.

## Why now

User report (2026-06-05):

> I need to be able to un-archive opportunities, and list archived
> opportunities, ie. an "--all" filter and/or a --status foo filter.

The read-side capability is already present in
`application/query.py:OpportunityQuery.list()` via the `Filters` dataclass
(`statuses`, `include_archived`). MCP already exposes those filters in
`list_opportunities`. The CLI is the only surface that hasn't caught up,
and the write-side inverse of `archive` has never existed at any surface.

## Decisions

The design space was settled in a brainstorming pass on 2026-06-05. The
locked decisions are:

1. **Verb name:** `unarchive` — direct inverse of the existing public verb
   `archive`. Applies to both CLI (`jh unarchive`) and MCP
   (`unarchive_opportunity`).
2. **`jh list` filters:** `--all` and `--archived`. Mutually exclusive.
   - Default (no flag): active opportunities only — today's behavior, unchanged.
   - `--archived`: archived opportunities only.
   - `--all`: active + archived.
3. **`--status` filter:** accepts both repeated flags and comma-separated
   values. Available on `list` and `stats`. Combines as `OR` (frozenset).
   `jh list --status applied --status screen`,
   `jh list --status applied,screen`, and
   `jh list --status applied,screen --status interview` are all equivalent.
4. **Archived row marker:** trailing `*` at end of each archived row in
   `jh list`. Omitted on active rows.
5. **`jh stats` parity:** same `--all` / `--archived` / `--status` flags,
   same defaults.
6. **MCP:** add `unarchive_opportunity(slug)`, mirroring `archive_opportunity`.
7. **Slug resolution for `jh unarchive`:** look in archived rows first;
   if not found, also check active rows and produce a smarter error.

## Non-goals

- Adding `--priority` or `--slug-substring` to the CLI. The query layer
  supports them, but the user did not ask for them and YAGNI applies.
- Multi-select for `--archived` (i.e. no archived-only `--status` semantics
  that differ from active). The `--archived` and `--status` filters compose
  orthogonally: `jh list --archived --status rejected` = archived rows
  whose status is `rejected`.
- A "soft archive" status or an `archived: bool` field on `Opportunity`.
  Archived is a storage-location concept, not a domain state; the public
  surface uses "archived" as a state concept, but the domain model is
  untouched.
- Migrating the existing `jh list` output format. Three columns plus the
  trailing-`*` marker on archived rows. No JSON output for `list` is added.

## Public surface

### CLI

```
$ jh unarchive <slug>
  unarchived: 2026-03-gamma-staff

$ jh list                              # default = active only (unchanged)
$ jh list --archived                   # archived only
$ jh list --all                        # active + archived (archived rows end in `*`)
$ jh list --status applied             # active, status=applied
$ jh list --status applied,screen      # active, status in {applied, screen}
$ jh list --all --status rejected      # both sets, status=rejected
$ jh list --all --archived             # error: --all and --archived are mutually exclusive

$ jh stats                             # default = active only (unchanged)
$ jh stats --all
$ jh stats --archived
$ jh stats --status applied,screen
```

Example mixed output:

```
$ jh list --all
2026-05-acme-em                                         applied      high
2026-04-beta-eng                                        screen       medium
2026-03-gamma-staff                                     rejected     low    *
```

Slug-resolution error from `jh unarchive`:

```
$ jh unarchive gamma                   # gamma is archived → success
  unarchived: 2026-03-gamma-staff

$ jh unarchive acme                    # acme is active, not archived
  jh: 'acme' matches an active opportunity (2026-05-acme-em); nothing to unarchive

$ jh unarchive nonesuch                # not present anywhere
  jh: no archived opportunity matches 'nonesuch'
```

### MCP

New tool, registered alongside `archive_opportunity` in
`src/jobhound/mcp/tools/ops.py`:

```python
@app.tool(
    name="unarchive_opportunity",
    description="Restore an archived opportunity.",
)
def _u(slug: str) -> str:
    return unarchive_opportunity(repo, slug=slug)
```

Response shape mirrors `archive_opportunity`: a mutation envelope with
`archived=False` on the resulting snapshot.

No changes to `list_opportunities` or `show_stats` — they already accept
`include_archived` and `statuses`. The CLI work just exposes what MCP
already has.

## Architecture

Three layers touched. Each change is additive and symmetric with an
existing pattern.

### Domain layer

No changes. `Status` already has the values the user filters on; archived
remains a storage concept, not a `Status` enum member.

### Application layer

- `application/ops_service.py` — add `unarchive_opportunity(repo, slug)`
  mirroring `archive_opportunity`. Returns `(opp, opp, new_dir)`, where
  `new_dir` is the path inside `opportunities_dir`.
- `application/query.py` — no changes. `Filters` and `OpportunityQuery.list()`
  already do what we need.

### Infrastructure layer

- `infrastructure/repository.py` — add `OpportunityRepository.unarchive(opp_dir)`.
  Mirrors `archive`: refuses if the destination already exists, then
  `shutil.move` from `archive_dir` to `opportunities_dir`, then `_commit`
  with message `f"unarchive: {opp_dir.name}"`.
- A new resolution helper for the unarchive slug-lookup. Two options
  considered; chose the second:
  - (Rejected) Add a method to `OpportunityRepository` that resolves against
    archive only. Simple but duplicates the active-fallback logic for the
    helpful error.
  - (Chosen) Implement the lookup inside `commands/unarchive.py` using
    `resolve_slug(query, paths.archive_dir)` first, then on
    `SlugNotFoundError` try `resolve_slug(query, paths.opportunities_dir)`
    to build the smarter error message. Keeps the helpful-error policy at
    the CLI boundary; the repository stays a thin persistence layer.

### CLI layer

- `commands/unarchive.py` — new module, mirrors `commands/archive.py`.
- `commands/list_.py` — rewrite `run()` to accept `--all`, `--archived`,
  `--status` and route through `OpportunityQuery.list(Filters(...))`
  instead of `OpportunityRepository.all()`.
- `commands/stats.py` — add the same three flags; build the same `Filters`;
  pass to `OpportunityQuery.stats(Filters(...))`.
- `cli.py` — register `unarchive` between `archive` and `delete`.
- `commands/_complete.py` — add `unarchive` to `_SLUG_AT_POSITION` and
  `_TOP_LEVEL_COMMANDS`. The `_complete_slug` helper currently yields from
  `paths.opportunities_dir` only; for `unarchive` it should yield from
  `paths.archive_dir`. Add a per-command slug-source map keyed by
  `cmd_path`.

### MCP layer

- `mcp/tools/ops.py` — add `unarchive_opportunity(repo, *, slug)` that
  routes to `ops_service.unarchive_opportunity` and returns the mutation
  envelope (`archived=False`). Register on the FastMCP app.

## Filter parsing

`--status` accepts both comma-separated and repeated forms. Implementation
sketch using cyclopts:

```python
def run(
    *,
    all_: Annotated[bool, Parameter(name=["--all"])] = False,
    archived: Annotated[bool, Parameter(name=["--archived"])] = False,
    status: Annotated[list[str] | None, Parameter(name=["--status"])] = None,
) -> None:
    if all_ and archived:
        raise SystemExit("jh: --all and --archived are mutually exclusive")
    raw = list(status or [])
    tokens = [t.strip() for chunk in raw for t in chunk.split(",") if t.strip()]
    try:
        statuses = frozenset(Status(t) for t in tokens)
    except ValueError as exc:
        raise SystemExit(f"jh: unknown status: {exc}") from exc
    filters = Filters(
        statuses=statuses,
        include_archived=all_,
        # `--archived` is realized below by switching roots, not by Filters.
    )
    ...
```

The active/archived dimension does **not** map cleanly onto
`Filters.include_archived` alone, because `Filters` has no
`archived_only` mode. Two implementation choices:

- **(Chosen)** Keep `Filters` as-is. The CLI command resolves `--archived`
  by calling `OpportunityQuery.list(filters_with_include_archived=True)`
  and post-filtering to `snap.archived` rows. Avoids changing the read
  API for a CLI-only concern.
- (Rejected) Extend `Filters` with `archived_only: bool`. Slightly more
  uniform but ripples through MCP, breaks no-op semantics, and the new
  field would have no MCP user today.

## Display marker

`commands/list_.py` produces three columns today:

```python
print(f"{opp.slug:<55} {opp.status:<12} {opp.priority}")
```

The marker becomes:

```python
mark = " *" if snap.archived else ""
print(f"{opp.slug:<55} {opp.status:<12} {opp.priority:<8}{mark}")
```

The priority column gets a fixed width so the asterisk lands in a stable
column. The width is chosen to fit the longest `Priority` value plus a
gap.

## Docstring cleanup

Cyclopts uses each command function's docstring as the `--help` text.
That is the user-visible surface for backend leakage. Today's function
docstrings (`commands/archive.py:run` says `"Archive an opportunity."`)
are already clean, so the immediate `--help` surface has no leaks to
fix. New code follows the same convention:

- `commands/unarchive.py:run` — docstring describes the state change
  (e.g. `"Unarchive an opportunity."`), never the storage move.
- MCP tool `description=` fields for `archive_opportunity` and
  `unarchive_opportunity` describe the state change, not the storage move.

Module-level docstrings (e.g. `commands/archive.py` line 1) currently
name `opportunities/` and `archive/`. These are source-only — not in
the public interface — but get cleaned up as hygiene in passing while
the surrounding files are edited. Internal docstrings on
`OpportunityRepository.archive` / `.unarchive` continue to name the
directories — that is the repository's domain and not part of the
public interface.

## Testing

Each layer gets focused tests. Tests are behavior-level — invoking the
CLI / MCP tool / service and asserting on outputs, not on intermediate
state.

### Repository

- `test_repository.py`: add a test that `unarchive(archived_opp_dir)`
  moves the directory back and records a `unarchive: <slug>` commit.
- Add a test that `unarchive` refuses when the target already exists in
  `opportunities/` (mirror the existing `archive` collision test).

### Application

- `test_ops_service.py`: add a test for `unarchive_opportunity` that
  verifies the returned `new_dir` is under `paths.opportunities_dir`.

### CLI

- `test_cmd_lifecycle.py`: add `test_unarchive_moves_folder` mirroring
  `test_archive_moves_folder`.
- Add `test_unarchive_error_on_active_slug` covering the smarter error.
- Add `test_unarchive_error_on_missing_slug` covering the not-found error.
- `test_cmd_list.py`: cover `--all` (mixed rows, asterisk on archived),
  `--archived` (archived only), `--status applied`,
  `--status applied,screen`, `--status applied --status screen`,
  `--all --archived` (error), and unknown status (error).
- `test_cmd_stats.py`: cover the same flags at the stats surface.

### MCP

- `tests/mcp/test_tools_ops.py`: add a test for `unarchive_opportunity`
  that round-trips an `archive` then verifies the snapshot's `archived`
  flag flips back to `False`.

### Completion

- `tests/commands/test_cmd_complete.py`: add a test that
  `__complete <shell> jh unarchive ` yields archived slugs and not active
  ones.

## Rollout

One PR, all layers. No feature flag, no migration. The default behaviors
of `jh list` and `jh stats` are unchanged, and `jh unarchive` is purely
additive, so the change is non-breaking for existing scripts and muscle
memory.

## Out of scope (for explicitness)

- Bulk unarchive (`jh unarchive --all`, glob patterns) — defer until asked.
- A history of archived/unarchived transitions on `Opportunity`. Git log
  already provides this.
- Distinguishing "archived because terminal" from "archived manually."
  No data model for it today; not requested.
