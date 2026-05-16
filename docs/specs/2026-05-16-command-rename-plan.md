# Command Rename Plan — Locked Decisions

Date: 2026-05-16
Status: Locked (user-approved 2026-05-16)
Branch: `chore/command-rename-plan` (this spec), `chore/command-renames` (implementation, to follow)
Supersedes: row-by-row analysis in `docs/specs/2026-05-15-command-naming-review-design.md`

Output of the naming-review charter. The charter enumerated 18 inconsistencies
across the CLI and MCP surfaces; this document records the locked decisions
plus the resulting rename table.

## Resolved during the review

- **Row 6 (`sync` / `sync_data`)**: already resolved — removed entirely (PR #29). No CLI counterpart; the MCP tool exposed privileged `git pull/push` to an AI for ~zero realised value.

## Patterns and decisions

### Pattern A — Lifecycle verb shape

MCP today mixes prepositions, markers, and noun-suffixes (`apply_to`,
`withdraw_from`, `mark_ghosted`, `accept_offer`, `decline_offer`,
`archive_opportunity`, `delete_opportunity`, `new_opportunity`).

**Decision: regularise MCP to the `verb_opportunity` pattern.** CLI keeps top-level bare verbs.

| Current CLI | Current MCP | New MCP |
|---|---|---|
| `jh new` | `new_opportunity` | `create_opportunity` |
| `jh apply` | `apply_to` | `apply_to_opportunity` |
| `jh withdraw` | `withdraw_from` | `withdraw_from_opportunity` |
| `jh ghost` | `mark_ghosted` | `ghost_opportunity` |
| `jh accept` | `accept_offer` | `accept_opportunity` |
| `jh decline` | `decline_offer` | `decline_opportunity` |
| `jh archive` | `archive_opportunity` | (unchanged) |
| `jh delete` | `delete_opportunity` | (unchanged) |

Rationale: a flat MCP namespace benefits from one consistent `verb_opportunity`
shape — the AI picks the right tool by matching verbs against opportunity
context, instead of memorising irregular prepositions and markers. CLI's
top-level structure implies "opportunity" by default; the asymmetry is
documented in principle 5 of the charter.

### Pattern B — Read verbs

`show` is for things with rich rendered display (opportunities); `read` is for
things returning content bytes (files). Today both surfaces are misaligned on
this distinction.

| Current CLI | Current MCP | New CLI | New MCP |
|---|---|---|---|
| `jh show <slug>` | `get_opportunity` | (unchanged) | `show_opportunity` |
| `jh file show` | `read_file` | `jh file read` | (unchanged) |
| `jh export` | (no direct MCP counterpart; `list_opportunities` covers bulk read) | (unchanged) | (unchanged) |

### Pattern C — Single-field mutators and collection additions

CLI top-level bare-noun verbs (`jh priority`, `jh contact`, `jh note`, etc.) are
ambiguous (set vs filter vs show). Move them under explicit `set` and `add`
subgroups. MCP keeps its `set_*` / `add_*` flat-namespace prefixes.

| Current CLI | New CLI | Current MCP (unchanged) |
|---|---|---|
| `jh priority <slug> <level>` | `jh set priority <slug> <level>` | `set_priority` |
| (none — uses generic `jh edit`) | `jh set company <slug> <value>` | `set_company` |
| (none) | `jh set role <slug> <value>` | `set_role` |
| (none) | `jh set status <slug> <value>` | `set_status` |
| (none) | `jh set source <slug> <value>` | `set_source` |
| (none) | `jh set location <slug> <value>` | `set_location` |
| (none) | `jh set comp-range <slug> <value>` | `set_comp_range` |
| (none) | `jh set link <slug> <name> <url>` | `set_link` |
| (none) | `jh set first-contact <slug> <when>` | `set_first_contact` |
| (none) | `jh set applied-on <slug> <when>` | `set_applied_on` |
| (none) | `jh set last-activity <slug> <when>` | `set_last_activity` |
| (none) | `jh set next-action <slug> ...` | `set_next_action` |
| `jh contact <slug> ...` | `jh add contact <slug> ...` | `add_contact` |
| `jh note <slug> <msg>` | `jh add note <slug> <msg>` | `add_note` |
| `jh tag <slug> <name>` | `jh add tag <slug> <name>` (see Pattern D for removal) | `add_tag` |
| `jh log <slug> ...` | `jh log <slug> ...` (kept — it's an interaction verb, not a field setter) | `log_interaction` (unchanged) |

`jh edit` (interactive `$EDITOR` editor of `meta.toml`) is **kept** as-is —
it's a different UX from the per-field setters.

### Pattern D — `tag` add/remove split

| Current CLI | New CLI | Current MCP (unchanged) |
|---|---|---|
| `jh tag <slug> <name>` (toggle/flag-based) | `jh add tag <slug> <name>` and `jh remove tag <slug> <name>` | `add_tag` / `remove_tag` |

Note: this introduces a new `jh remove` subgroup. For symmetry it would also
cover `jh remove contact` if a `remove_contact` MCP tool is added later — none
exists today, so v1 of the rename only includes `jh remove tag`.

### Pattern E — Coverage gaps + `touch` → `bump`

MCP-only tools without CLI parity, plus a rename of `touch` to `bump` with
backwards-compat alias.

| Current CLI | Current MCP | New CLI | New MCP |
|---|---|---|---|
| (none) | `get_stats` | `jh stats` | `show_stats` |
| (none) | `touch` | `jh bump <slug>` | `bump` (primary) + `touch` alias |

`bump` is more descriptive than `touch` for "set `last_activity` to now without
changing status". The Unix-idiomatic `touch` is retained as an MCP alias because
its existing usage pattern (the AI calling `touch` from natural-language prompts
like "bump activity on Acme") would otherwise break with no muscle-memory cost
benefit. The alias is the only one in this rename — every other change is hard cut.

### Pattern F — File commands: add `file import` alongside `file write`

The original complaint that started this review: *"I wanted to add a file and
there's no 'add' or 'upload' command. 'write' appears to be the one?"*

| Current CLI | New CLI | Current MCP (unchanged) |
|---|---|---|
| `jh file write <slug> <name>` (bytes/stdin) | (unchanged) | `write_file` |
| (none) | `jh file import <slug> <local-path>` | `import_file` |
| `jh file export <slug> <name> <local-dest>` | (already exists; verify naming) | `export_file` |
| `jh file open <slug> <name>` | (unchanged — shipped in PR #30) | `open_file` (also shipped in PR #30) |

CLI gains `jh file import` so the common "add a file from disk" workflow has a
matching CLI verb. `jh file write` stays for stdin / inline bytes.

### Pattern G — CLI top-level structure

**Decision: keep CLI top-level for opportunity verbs.** No `jh opp ...`
subgroup. The "everything operates on an opportunity by default" mental model
is short, ergonomic, and matches existing muscle memory. Subgroups only for
namespaces that need them: `jh file ...`, new `jh set ...`, new `jh add ...`,
new `jh remove ...`.

After the rename, the CLI top-level surface is:

```
Lifecycle:    new, apply, withdraw, ghost, accept, decline, archive, delete
Mutation:     edit, log, bump
Read:         list, show, export, stats
Subgroups:    file, set, add, remove
Infra:        sync (now gone), mcp, migrate
```

Note `set`, `add`, `remove` are new subgroups; `bump` and `stats` are new
top-level commands.

## Migration

**Hard cut at v0.8.0**, with one exception:

- All renames ship breaking in v0.8.0 (release-please will bump per the `feat!:`
  marker in the implementation PR's commits).
- **Exception:** MCP `touch` is retained as an alias for `bump` indefinitely. It
  appears in both the MCP server's tool list (`touch` with description
  "Alias for `bump` — kept for backwards compatibility.") and dispatches to the
  same handler. No CLI alias — `jh touch` is not added because there was no
  prior CLI muscle memory to preserve.

CHANGELOG entries are auto-generated by release-please from the implementation
PR's commit messages. The migration command (`jh migrate utc-timestamps`)
is unaffected; this rename touches only verbs, not data on disk.

## Implementation scope

A single PR (`chore/command-renames`) makes all rename changes atomically:

### `src/jobhound/cli.py`
- Re-register lifecycle commands as-is (no CLI rename on top-level lifecycle).
- Remove top-level `priority`, `contact`, `note`, `tag` registrations.
- Add new subgroup apps: `set_app`, `add_app`, `remove_app`.
- Add new top-level commands: `bump`, `stats`.

### `src/jobhound/commands/`
- New `set.py` — cyclopts subgroup containing 12 setter commands.
- New `add.py` — cyclopts subgroup containing `tag`, `contact`, `note`.
- New `remove.py` — cyclopts subgroup containing `tag`.
- New `bump.py` — single command.
- New `stats.py` — single command.
- New `file.py:read` (renamed from `show`); existing `file.py:show` removed.
- New `file.py:import_` (added).
- Remove `priority.py`, `contact.py`, `note.py`, `tag.py` (or rewrite their
  contents to live inside the new subgroup modules).

### `src/jobhound/mcp/tools/`
- `lifecycle.py`: rename 6 tools per Pattern A table.
- `reads.py`: rename `get_opportunity` → `show_opportunity`; rename `get_stats` → `show_stats`.
- `ops.py`: rename `touch` → `bump`; register `touch` as alias (same handler).

### Tests
- All test files referring to old CLI commands (`tests/test_cmd_priority.py` etc.)
  rename to the new structure. Per-file renames + fixture updates.
- MCP test files (`tests/mcp/test_tools_*.py`) update tool names.
- Integration tests that invoke commands via `runner.invoke(app, [...])`
  update the arg lists.

### Docs
- `README.md`: update the command surface table.
- `docs/specs/2026-05-15-command-naming-review-design.md`: mark Status = resolved.
- This document (`docs/specs/2026-05-16-command-rename-plan.md`): retained as
  a historical record of the decision.

### CHANGELOG

Auto-generated by release-please from the `feat!:` markers on the rename
commit(s). The release PR's body will document each rename.

## Acceptance criteria

Done when:

- `rg "today:\s*date\b" src/` returns no results (already true from v0.7.0).
- `rg "set_priority\b" src/` returns hits only inside test code and the MCP
  registration (not in CLI command modules — those now live under `commands/set.py`).
- `jh --help` shows the new subgroup structure: `file`, `set`, `add`, `remove`,
  `bump`, `stats`, plus the unchanged lifecycle verbs.
- The MCP `tools/list` response contains the new names; `touch` appears
  alongside `bump` with an "alias" note in the description.
- Full test suite passes — target ~470 tests (443 + new tests for the new
  subgroup structure + small additions for `stats`, `bump`).
- `CHANGELOG.md` v0.8.0 entry generated by release-please documents the breaking
  changes.

## Estimated effort

- **Implementation PR:** ~4-6 hours of focused work. Bulk is mechanical
  rename + test-fixture updates. Highest-risk piece is the CLI subgroup
  restructure (Pattern C/D) because it touches command-registration plumbing.
- **Review:** the diff will be large but uniform; rename mechanics are
  greppable. A reviewer should focus on:
  - Correct subgroup nesting in `cli.py`.
  - MCP `register()` blocks pointing at the renamed handlers.
  - The `touch`-alias path in `mcp/tools/ops.py` registering both names to the
    same function.
  - Test fixtures updated for the new arg shape (`["set", "priority", slug, value]`
    instead of `["priority", slug, value]`).
