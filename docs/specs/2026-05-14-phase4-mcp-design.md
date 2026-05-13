# Phase 4 — MCP Server Design Spec

Date: 2026-05-14
Status: Draft, awaiting review
Branch: `feat/phase4-mcp-design`

## Goal

Expose the full `jh` command surface — reads and writes — to Model Context
Protocol (MCP) clients (Claude Desktop, Claude Code, Continue, Zed, and any
other spec-compliant client). The MCP server is the AI-integration adapter:
it wraps `OpportunityQuery` and `OpportunityRepository` (both established in
Phase 3a) as MCP tools that AI assistants can call directly.

This is **Phase 4** of the absorption effort. Phase 3a shipped the
foundation (read API + DDD reorg). Phase 3b/c (dashboard/today/ICS/CV/PDF)
remain queued. The MCP server can ship independently of those — it depends
only on the Phase 3a public surface.

## Strategic direction

### Why MCP, not the HTTP daemon documented in Phase 3a

The Phase 3a spec listed a future HTTP daemon as "later, separate spec"
(`docs/specs/2026-05-12-jh-read-api-design.md` §"Why a library, not a
daemon"). The argument was that daemon costs (port management, lifecycle,
auth, routing, client library) didn't earn their keep without a concrete
consumer.

There is now a concrete consumer: Robin wants to use AI tools to review
and act on his job hunt. MCP is the right protocol for that use case:

- Runs over stdio — no port, no daemon lifecycle, no auth model
- Universally supported by AI clients (Anthropic, Continue, Zed, and the
  growing MCP ecosystem)
- Subprocess-per-session matches the security model (each client decides
  when to spawn; nothing is "always on")
- Sidesteps every reason the HTTP daemon was deferred

The HTTP daemon stays deferred. It earns its keep when a *browser UI* needs
it, or when non-MCP concurrent consumers appear — not before.

### Target client universe

All MCP-spec-compliant clients (Claude Desktop, Claude Code, Continue,
Zed, and future entrants). The server must use only universal MCP
primitives: tools. Resources and prompts have variable client support and
are deferred to a possible v2.

### Write surface decision

The server exposes the *full* CLI command surface — reads and writes. The
user has chosen "all-in on AI" and accepts the CQRS trust boundary moves
from the CLI/AI split to the AI-client-approval UI. Every MCP write goes
through `OpportunityRepository`, preserving auto-commit semantics
established in Phase 3a.

The one exception is `delete_opportunity`, which requires an explicit
`confirm: bool = True` argument. Every other write is recoverable from
git history; delete is the only permanent op.

## Architecture

### DDD layering

Phase 3a established four DDD layers in `src/jobhound/`:

- `domain/` — entities (`Opportunity`), value objects, domain services.
  No I/O.
- `infrastructure/` — persistence (`OpportunityRepository`, `meta_io`),
  paths, config, git. The only layer that touches disk or git.
- `application/` — use-case services + read DTOs. Phase 3a populated the
  *read* side here (`OpportunityQuery`, snapshots, serialization).
- `commands/` — CLI adapter. Cyclopts subcommands; argument parsing;
  human-text output.

Phase 4 adds a fifth-layer-equivalent adapter:

- `mcp/` — MCP adapter. Tool registration; argument parsing; JSON-shaped
  output. **Sibling to `commands/`, not nested under it.** Same depth in
  the dependency graph, same role at the system boundary, but a
  different protocol.

The dependency rule is unchanged: adapters depend on application, which
depends on domain (with infrastructure plugged into application through
`Paths` + `Repository`). Adapters MAY NOT contain domain logic — only
protocol translation.

### Phase 3a had read services. Phase 4 adds write services.

Phase 3a populated `application/` with read use-cases
(`OpportunityQuery`) and read DTOs (snapshots, serialization), but
**left write orchestration inlined in CLI commands**. Each command in
`commands/` currently does its own load-mutate-save dance:

```python
# commands/apply.py — current pattern
cfg = load_config()
repo = OpportunityRepository(paths_from_config(cfg), cfg)
opp, opp_dir = repo.find(slug)
opp = opp.apply(applied_on=..., today=..., next_action=..., next_action_due=...)
repo.save(opp, opp_dir, message=f"apply: {opp.slug}")
```

Phase 4 cannot duplicate that orchestration into the MCP adapter — that
would put load-mutate-save logic in TWO adapters, violating the rule that
adapters are translation-only. So Phase 4 **extracts write orchestration
into application services** that *both* adapters can call.

The write side of `application/` becomes:

```
application/
  query.py                            # Phase 3a (read use-cases)
  snapshots.py                        # Phase 3a (read DTOs)
  serialization.py                    # Phase 3a (read converters)
  lifecycle_service.py                # NEW Phase 4 — state transitions
  field_service.py                    # NEW Phase 4 — single-field setters
  relation_service.py                 # NEW Phase 4 — tags/contacts/links
  ops_service.py                      # NEW Phase 4 — note/archive/delete/sync
```

Each service function has the shape:

```python
def set_priority(
    repo: OpportunityRepository,
    slug: str,
    level: Priority,
) -> tuple[Opportunity, Opportunity, Path]:
    """Load, mutate, save. Returns (before, after, opp_dir).

    Used by both CLI and MCP adapters. No format concerns.
    """
    opp_pre, opp_dir = repo.find(slug)
    opp_post = opp_pre.with_priority(level)
    repo.save(opp_post, opp_dir, message=f"priority: {opp_post.slug} {level.value}")
    return opp_pre, opp_post, opp_dir
```

This is small — usually 3–5 lines per service function. But it is the
**only** place orchestration lives. Adapters become thin translators.

### CLI commands are NOT refactored in Phase 4

The CLI commands in `commands/` continue to do their own inlined
orchestration *temporarily*. Phase 4 introduces the application services
and routes the MCP adapter through them, but does not touch the CLI
adapter. Rationale:

- The CLI commands are tested (Phase 3a 142 tests cover them).
- The MCP adapter is the new code that needs the services anyway.
- Once Phase 4 validates the service shapes against real adapter use,
  the CLI refactor is a clear follow-on with no design risk.

That follow-on is **Phase 4 cleanup** (out of scope for the Phase 4 spec
but flagged in the implementation plan):

> After Phase 4 ships, refactor each `commands/*.py` to call its matching
> `application/*_service.py` function instead of inlining the
> load-mutate-save pattern. CLI tests should remain green throughout.

### Package layout

```
src/jobhound/
  __init__.py                         # unchanged
  cli.py                              # registers `mcp` subcommand
  prompts.py                          # unchanged

  domain/                             # unchanged (Phase 3a)
  infrastructure/                     # unchanged (Phase 3a)

  application/
    query.py                          # Phase 3a (unchanged)
    snapshots.py                      # Phase 3a (unchanged)
    serialization.py                  # Phase 3a (unchanged)
    lifecycle_service.py              # NEW Phase 4
    field_service.py                  # NEW Phase 4
    relation_service.py               # NEW Phase 4
    ops_service.py                    # NEW Phase 4

  commands/                           # unchanged in Phase 4
                                      # (refactor to use services in cleanup phase)

  mcp/                                # NEW adapter subpackage
    __init__.py                       # exports build_server, main
    server.py                         # FastMCP app + tool registration
    converters.py                     # compute_diff + response builders
    errors.py                         # exception → MCP error mapping
    tools/                            # one module per logical group;
                                      # each calls into application/*_service
      __init__.py
      reads.py                        # 5 tools  → application/query.py
      lifecycle.py                    # 7 tools  → application/lifecycle_service.py
      fields.py                       # 12 tools → application/field_service.py
      relations.py                    # 4 tools  → application/relation_service.py
      ops.py                          # 4 tools  → application/ops_service.py
```

### Runtime model

- Spawned as a subprocess by the MCP client over stdio
- Long-lived for the session; one server process per client session
- **Stateless reads:** every tool call constructs a fresh
  `OpportunityQuery(paths)` and re-reads `meta.toml`. Cheap (~KBs per opp);
  avoids stale-cache bugs across concurrent CLI mutations.
- **One `OpportunityRepository` cached at startup** for writes; preserves
  the per-mutation auto-commit semantics.
- Single-process asyncio; tool calls serialise naturally. No locking at the
  MCP layer. Git operations across processes carry the same caveats they do
  today (concurrent `jh` invocations can still trip git lock).

### MCP primitives used

**Tools only** for v1. ~32 tools across the five modules. No Resources, no
Prompts — both have variable client support; tools are universal across
the entire MCP ecosystem. Add later if a specific client UX demands it.

### Dependencies

- New optional extra `jobhound[mcp]` pulling in the official `mcp` Python
  SDK (Anthropic's `modelcontextprotocol` package).
- Lazy-imported inside `mcp/server.py` so users without the extra pay no
  startup cost on every `jh` invocation.
- The `jh mcp` subcommand checks the extra is installed and prints a clear
  `pip install jobhound[mcp]` message if not.

### Two entry points

Both spawn the same server code. The duplication is intentional — gives
users one path they'll already know (`jh mcp`) and one zero-install path
(`uvx`) to recommend in the README.

1. **`jh mcp`** — Cyclopts subcommand on the existing CLI. Registration
   in `cli.py` next to `show` and `export`. Client config:
   ```json
   "jobhound": { "command": "jh", "args": ["mcp"] }
   ```
   Requires `uv tool install jobhound`.

2. **`jh-mcp`** — separate `[project.scripts]` entry point pointing at
   `jobhound.mcp.server:main`. Bypasses the `jh` parser, so works with
   `uvx`:
   ```json
   "jobhound": { "command": "uvx", "args": ["--from", "jobhound", "jh-mcp"] }
   ```
   Zero global install required.

## Tool inventory

32 tools across 5 modules. Every read tool returns the existing JSON
envelope shape from `jobhound.application.serialization` (Phase 3a). Every
mutation tool returns the standard mutation response:

```json
{"opportunity": <full_post_snapshot_dict>,
 "changed":     {<field>: [<before>, <after>], ...}}
```

For `new_opportunity` the `changed` field is `null` (no "before" state).
For `delete_opportunity` the response shape is
`{"deleted_opportunity": <last_snapshot>, "changed": null}`. Idempotent
ops (setting a field to its current value) return `changed: {}`.

### `mcp/tools/reads.py` — 5 tools

| Tool | Args | Returns |
|---|---|---|
| `list_opportunities` | `statuses?`, `priorities?`, `slug_substring?`, `active_only=False`, `include_archived=False` | `list_envelope` shape |
| `get_opportunity` | `slug` | `show_envelope` shape |
| `get_stats` | (same filters as list) | `stats_to_dict` shape |
| `list_files` | `slug` | `[FileEntry, …]` (recursive, hidden excluded) |
| `read_file` | `slug, filename` | `{filename, content: str, size}`. Content is utf-8 if decodable, base64-encoded otherwise. |

### `mcp/tools/lifecycle.py` — 7 tools (state transitions)

Each maps directly to a state-transition method on the `Opportunity`
aggregate. Enforces the legal-transition rules in
`jobhound.domain.transitions`.

| Tool | Args | Maps to |
|---|---|---|
| `new_opportunity` | `company, role, slug?, source?, priority="medium", location?, comp_range?, first_contact?=today, tags?, next_action?, next_action_due?` | `Repository.create()` |
| `apply_to` | `slug, applied_on?=today, next_action, next_action_due` | `Opportunity.apply()` |
| `log_interaction` | `slug, next_status, next_action?, next_action_due?, today?=today, force=False` | `Opportunity.log_interaction()` |
| `withdraw_from` | `slug, today?=today` | `Opportunity.withdraw()` |
| `mark_ghosted` | `slug, today?=today` | `Opportunity.ghost()` |
| `accept_offer` | `slug, today?=today` | `Opportunity.accept()` |
| `decline_offer` | `slug, today?=today` | `Opportunity.decline()` |

### `mcp/tools/fields.py` — 12 tools (replaces `jh edit`)

Field-specific setters. Each takes `slug` plus the new value (nullable
where the underlying field is). Returns the standard mutation response.

`set_company`, `set_role`, `set_priority`, `set_status` (bypasses
transitions; equivalent to `jh log --force`), `set_source`, `set_location`,
`set_comp_range`, `set_first_contact`, `set_applied_on`, `set_last_activity`,
`set_next_action` (text + due combined since they always travel together),
`touch` (bump `last_activity` to today without other change).

### `mcp/tools/relations.py` — 4 tools

| Tool | Args | Notes |
|---|---|---|
| `add_tag` | `slug, tag` | Appended, deduped, sorted (matches `jh tag --add`) |
| `remove_tag` | `slug, tag` | Matches `jh tag --remove` |
| `add_contact` | `slug, name, role?, channel?` | Appends |
| `set_link` | `slug, name, url` | Set or overwrite (matches `jh link` semantics) |

### `mcp/tools/ops.py` — 4 tools

| Tool | Args | Notes |
|---|---|---|
| `add_note` | `slug, msg` | Appends timestamped entry to `notes.md` |
| `archive_opportunity` | `slug` | Moves to `archive/`. Reversible (files moved, no data loss) |
| `delete_opportunity` | `slug, confirm: bool = False` | Permanent. Requires `confirm=True`; without it, returns a preview of what would be deleted (snapshot + file list) with no side effects |
| `sync_data` | `direction: "pull"\|"push"\|"both" = "pull"` | Git push/pull on the data root |

### CLI parity choices

- **Not exposed:** `set_slug` (rename — rare, leave to CLI), `remove_link`
  (doesn't exist on the CLI today; MCP does not add new functionality).
- **`jh edit` replaced** by the 12 `fields.py` tools rather than mirrored as
  a single opaque tool — the AI's discovery is better with named verbs
  than with a free-form patch dict.
- **`log_interaction` enforces transitions; `set_status` bypasses them.**
  Mirrors the CLI's `jh log` (enforces) vs `jh log --force` (bypasses)
  split.

## Data flow & semantics

### Read flow

```
client → reads.list_opportunities(args)
       → OpportunityQuery(paths).list(Filters(**args), today=date.today())
       → list_envelope(snaps, timestamp=now_utc, db_root=paths.db_root)
       → json.dumps → MCP TextContent
```

Fresh `OpportunityQuery` per call. No caching.

### Mutation flow

The MCP tool is a thin translator. The orchestration sits in the
application service. The tool only handles MCP-shaped concerns: argument
parsing, JSON-envelope formatting, error-response shaping.

```
client → mcp.tools.fields.set_priority(slug="acme", level="high")    [adapter]
       → application.field_service.set_priority(repo, "acme", Priority.HIGH)
           → opp_pre, opp_dir = repo.find("acme")                    [calls infra]
           → opp_post         = opp_pre.with_priority(Priority.HIGH) [calls domain]
           → repo.save(opp_post, opp_dir,
                       message="priority: 2026-05-acme-em high")     [calls infra]
           → return (opp_pre, opp_post, opp_dir)
       → snap_post = build_snapshot(opp_post, opp_dir, archived=False,
                                     today=date.today())             [adapter]
       → changed   = compute_diff(opp_pre, opp_post)                 [adapter]
       → return {opportunity: snapshot_to_dict(snap_post), changed}  [adapter]
```

The labels show the layer boundaries: the `[adapter]` lines live in
`mcp/`, the `[calls infra]` and `[calls domain]` lines are inside the
application service body, and the service itself lives in
`application/field_service.py`. The adapter never touches `Opportunity`
methods or `Repository` methods directly — it goes through the service.

### Diff computation

`mcp/converters.py` exposes a single pure function:

```python
def compute_diff(before: Opportunity, after: Opportunity) -> dict[str, list]:
    """Return {field_name: [before_value, after_value]} for every changed field.

    Uses the same JSON-native conversion as snapshot_to_dict — dates become
    ISO strings, enums become their .value, contacts become dicts. The diff
    is json.dumps-able without a default hook.

    Empty diff ({}) means an idempotent no-op write.
    """
```

The diff operates on aggregate fields directly (frozen `Opportunity`
objects from the domain layer). JSON-native conversion is done at the
edge in the same module, sharing helpers with
`application/serialization.py` so the wire shape stays consistent.

### Slug resolution

All tools that take `slug` accept **fuzzy match** via the existing
`resolve_slug` from `jobhound.domain.slug`:

- Exact folder name → that opp
- Unique substring → that opp
- Ambiguous → `AmbiguousSlugError` mapped to an MCP error response listing
  every candidate
- Not found → `SlugNotFoundError` mapped to an MCP error response

The AI can call `list_opportunities` first if it wants the canonical slug,
but doesn't have to. "Apply to Acme" works.

### Date semantics

- Every date argument is **optional, server-defaulting to `date.today()`**
  in tools where the CLI default is also today. Required-in-CLI dates
  (e.g., `apply_to`'s `next_action_due`) stay required-in-MCP.
- The AI can pass any ISO 8601 date string (`YYYY-MM-DD`) to override.
- The server parses + validates; bad date strings produce an
  `invalid_value` error.
- Mutation responses **echo the resolved date** inside the snapshot, so the
  AI can confirm what got written without a follow-up read.

### Auto-commit semantics

- **One git commit per mutation tool call.** Mirrors the CLI's "action =
  commit" pattern.
- Commit messages are auto-generated from the tool name + slug + (where
  short) the new value: `"set_priority: 2026-05-acme-em high"`,
  `"apply_to: 2026-05-acme-em"`, `"add_note: 2026-05-acme-em"`, etc.
- **Idempotent writes produce no commit.** If `set_priority("acme",
  "high")` is called when priority is already `high`, the file is
  rewritten with identical bytes, `git add` sees no change, no commit
  results. The MCP response still includes
  `{opportunity: <unchanged>, changed: {}}` so the AI sees the no-op.
- Reads never commit anything (no git side effects on
  `OpportunityQuery.__init__`, established in Phase 3a).

### Concurrency

Stdio MCP server is single-process. Tool calls serialise inside asyncio.
No locking required at the MCP layer. Git operations across the same data
root from multiple processes (e.g., a `jh` CLI run during an MCP session)
carry the same caveats they do today — `OpportunityRepository._commit`
doesn't take a cross-process lock, and the user is responsible for not
running two writers concurrently.

## Error handling

### Error response shape

Every tool catches domain exceptions and returns an MCP error response
with a structured payload:

```json
{
  "error": {
    "code": "<machine-readable-code>",
    "message": "<human-readable>",
    "details": { /* optional structured info the AI can act on */ }
  }
}
```

Implementation: `mcp/errors.py` defines a single
`tool_error_response(code, message, **details)` helper. Each tool wraps
its body in a try/except that maps domain exceptions to this helper.
FastMCP surfaces these as MCP tool errors with `isError: true`.

### Exception → code mapping

| Domain exception | Code | Details |
|---|---|---|
| `SlugNotFoundError` | `slug_not_found` | `{query}` |
| `AmbiguousSlugError` | `ambiguous_slug` | `{query, candidates: [<slug>, …]}` |
| `InvalidTransitionError` | `invalid_transition` | `{verb, current_status, legal_targets: [<status>, …]}` |
| `ValidationError` | `validation_error` | `{path: <opp-dir>, reason}` |
| `FileExistsError` | `slug_already_exists` | `{slug}` |
| `ValueError` (bad enum value) | `invalid_value` | `{param, value, allowed: [<choice>, …]}` |
| `ValueError` (path traversal) | `path_outside_opp_dir` | `{slug, filename}` |
| `subprocess.CalledProcessError` (sync) | `git_error` | `{direction, returncode, stderr}` |
| Anything uncaught | `internal_error` | `{tool, message: <exc.__class__.__name__>}` |

### AI recovery hints

The key fields are the ones that tell the AI what to try next:

- **`legal_targets`** on `invalid_transition` — the legal moves from the
  current state. AI can self-correct by calling `log_interaction` with one
  of the legal next-status values.
- **`candidates`** on `ambiguous_slug` — every matching slug. AI picks the
  right one and retries.
- **`allowed`** on `invalid_value` — every valid enum value. AI corrects
  and retries.

### What doesn't go to the AI

- **Stack traces.** Unexpected exceptions log to stderr (visible to the
  user via the MCP client's debug pane) but return only
  `code: "internal_error"` with the exception class name. No PII or
  filesystem paths leaked.
- **Re-raises.** Tools never re-raise. A bare `raise` inside a tool body
  is a bug.

### Logging

Errors and writes log to stderr via Python `logging`. INFO for normal
ops, ERROR for `internal_error`. MCP clients route the server's stderr to
a debug log the user can inspect. No file logging — the server is
stateless on disk beyond the data root it serves.

## Testing strategy

### What to test (and what not to)

| Layer | Approach |
|---|---|
| Domain (`Opportunity.apply()`, `Status` rules, …) | **Already tested in Phase 3a (201 tests). Not re-tested.** |
| Infrastructure (`OpportunityRepository`, `meta_io`, …) | **Already tested in Phase 3a.** Not re-tested. |
| Application read services (`OpportunityQuery`) | **Already tested in Phase 3a.** Not re-tested. |
| Application write services (NEW: `lifecycle_service`, `field_service`, `relation_service`, `ops_service`) | One test per service function over the existing `tmp_jh` fixture. Verifies load-mutate-save returns `(before, after, opp_dir)` correctly and that the right commit message is set. ~25–30 tests. |
| Pure helpers (`compute_diff`, `tool_error_response`) | Unit tests on the pure functions. No fixtures. |
| Each MCP tool function | Direct function call via `call_tool` fixture. Verifies argument parsing, service dispatch, response shape. The service is already tested separately, so tool tests only need to confirm "the tool routes to the right service with the right args and packages the result correctly." |
| Error mapping | One test per domain exception → MCP error code. |
| Full MCP round-trip | A small handful of integration tests over actual stdio. Tool registration + JSON envelope shape end-to-end smoke. |
| MCP SDK behaviour | **Trust upstream.** Not tested. |

### Test layout

```
tests/application/
  test_lifecycle_service.py   # NEW Phase 4 — apply/log/withdraw/ghost/accept/decline
  test_field_service.py       # NEW Phase 4 — 12 setters + touch
  test_relation_service.py    # NEW Phase 4 — add_tag/remove_tag/add_contact/set_link
  test_ops_service.py         # NEW Phase 4 — add_note/archive/delete/sync

tests/mcp/
  __init__.py
  conftest.py                 # mcp_paths (git-init'd query_paths), call_tool helper
  test_converters.py          # compute_diff for every field type
  test_errors.py              # error response shape + exception mapping
  test_tools_reads.py         # list/get/stats/files/read_file
  test_tools_lifecycle.py     # routes to lifecycle_service; response shape
  test_tools_fields.py        # routes to field_service; response shape
  test_tools_relations.py     # routes to relation_service; response shape
  test_tools_ops.py           # routes to ops_service; response shape
  test_server_integration.py  # stdio round-trip smoke (~3 tests)
```

### Fixtures

Two new fixtures in `tests/mcp/conftest.py`, both built on Phase 3a
infrastructure:

- **`mcp_paths`** — extends `query_paths` (from
  `tests/application/conftest.py`) with `subprocess.run(["git", "init", …])`
  on the data root so `Repository` operations don't fail on `ensure_repo`.
  Seeds the same three opps (acme/beta/gamma).
- **`call_tool(name, **kwargs)`** — invokes a registered tool handler by
  name and returns the parsed response dict. Doesn't go through stdio
  (that's `test_server_integration.py`); calls the FastMCP-registered
  handler directly. Used by every test file except the integration one.

### Estimated count

Roughly **70–85 new tests** total: ~25–30 for the new application write
services (they're the load-mutate-save logic, so they need genuine
coverage of each verb/field), and ~45–55 for the MCP adapter layer.

The application service tests use the existing `tmp_jh` fixture with a
real git-init'd data root, so they cover commit-message correctness and
idempotency end-to-end. The MCP tool tests then only need to verify the
adapter wiring (right args → right service call → right response shape)
since the service is already proven.

Aim is *coverage of each contract at its own layer*, not exhaustive
enumeration of inputs — the domain layer already does the latter.

## Out of scope (deferred)

- **CLI command refactor.** The CLI commands in `commands/` continue to
  inline their load-mutate-save orchestration during Phase 4. Once the
  application services land and prove themselves under MCP use, a
  follow-on cleanup phase refactors each `commands/*.py` to call its
  matching `application/*_service.py` function. Phase 4 itself does not
  modify the CLI adapter — the existing 142 CLI/integration tests remain
  green throughout without changes.
- **Resources and Prompts (other MCP primitives).** Tools-only for v1.
  Resources could later expose `opportunity://<slug>` URIs for clients
  that render them well; Prompts could later expose curated templates
  like "weekly review". Both have variable client support; revisit when a
  specific client UX demands them.
- **Subscriptions / notifications** for live data updates. The MCP spec
  supports notifications, but no consumer needs them yet.
- **A separate `[mcp-write]` extra** gating writes. The user has chosen
  full-CLI parity; gating writes would be re-litigating that decision.
- **Multi-user / multi-tenant.** Single-user tool by design.
- **`set_slug` and `remove_link`.** Not part of CLI surface today;
  introducing them via MCP would expand domain functionality, which is
  out of scope for an adapter.

## Open questions for review

None at the time of writing. The Q&A that produced this spec resolved:

- Target clients: all MCP-compliant clients (universal protocol only).
- Write surface: full CLI parity, including destructive ops, with
  `confirm: bool` only on `delete_opportunity`.
- `jh new` and `jh edit`: replaced by `new_opportunity` (full args) and 12
  field-specific setters respectively.
- Installation: both `jh mcp` (for installed users) and `uvx jh-mcp` (for
  zero-install discovery).
- Return shape for mutations: `{opportunity, changed}` combining the full
  post-snapshot with a structured diff.
- Slug resolution: fuzzy match at the MCP boundary (same as CLI).
- Dates: server defaults to `date.today()` where CLI does; AI can
  override with ISO strings.
- Auto-commit: one commit per mutation; idempotent writes produce no
  commit.
- MCP primitives: tools only for v1; resources and prompts deferred.
- Errors: structured payloads with machine-readable codes and AI-recovery
  hints (`legal_targets`, `candidates`, `allowed`).

## References

- Phase 3a spec: `docs/specs/2026-05-12-jh-read-api-design.md` — the
  "implicit daemon API" table there is now this MCP contract.
- Phase 3a plan: `docs/plans/2026-05-13-phase3a-read-api.md` — the
  testing patterns (TDD per tool, `call_tool` analogue to `invoke`) are
  the model for Phase 4.
- Project memory: `project_jh_ai_integration.md` — the strategic context
  for choosing MCP over the HTTP daemon.
- MCP spec: <https://spec.modelcontextprotocol.io>
- MCP Python SDK: <https://github.com/modelcontextprotocol/python-sdk>
