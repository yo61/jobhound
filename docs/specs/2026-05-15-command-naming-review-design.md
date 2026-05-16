# CLI + MCP Command Naming Review — Design Charter

Date: 2026-05-15
Status: Resolved 2026-05-16. Locked decisions captured in
[`2026-05-16-command-rename-plan.md`](2026-05-16-command-rename-plan.md).
This charter is retained as the historical record of the 18-row
inconsistency catalogue and the principles applied.
Branch: not yet cut (suggest `chore/command-naming-review` when work begins)

Audit the CLI and MCP command surfaces for naming consistency and
domain-fit, then propose a normalized scheme. This is a **review charter**:
it frames the work, scopes the inputs, and lists the principles to apply.
The actual renames are a downstream task gated on the review's output.

## Why now

`jh` v0.6.1 is on PyPI and Phase 4 (MCP) + Phase 6 (file API) are shipped,
which means the CLI and MCP surfaces have grown in parallel without a unified
naming pass. Trigger observation (user, 2026-05-15):

> I wanted to add a file and there's no `add` or `upload` command. `write`
> appears to be the one?

That ambiguity isn't a one-off — it's a symptom. A review now, before more
verbs accrete, is cheaper than after.

## Surface to review

### CLI top-level (from `src/jobhound/cli.py`)

| Category | Commands |
|----------|----------|
| Create / lifecycle | `new`, `apply`, `withdraw`, `ghost`, `accept`, `decline`, `archive`, `delete` |
| Mutate fields | `edit`, `note`, `priority`, `tag`, `link`, `contact`, `log` |
| Read | `list`, `show`, `export` |
| Sync / infra | `sync`, `mcp` |
| Subcommand group | `file` → `list`, `show`, `write`, `append`, `delete` |

### MCP tools (37 total, from current server registration)

Grouped by apparent intent:

- **Lifecycle:** `new_opportunity`, `apply_to`, `withdraw_from`, `mark_ghosted`,
  `accept_offer`, `decline_offer`, `archive_opportunity`, `delete_opportunity`
- **Setters (single field):** `set_priority`, `set_status`, `set_role`,
  `set_company`, `set_location`, `set_link`, `set_source`, `set_comp_range`,
  `set_first_contact`, `set_last_activity`, `set_applied_on`, `set_next_action`
- **Collection mutators:** `add_tag`, `remove_tag`, `add_contact`, `add_note`,
  `log_interaction`
- **Read:** `get_opportunity`, `list_opportunities`, `get_stats`
- **Files:** `list_files`, `read_file`, `write_file`, `append_file`,
  `delete_file`, `import_file`, `export_file`
- **Infra / misc:** `sync_data`, `touch`

## Inconsistencies the review must resolve

Each row is a concrete divergence with citations, not opinion. The review
output should say, for each row, "keep both", "normalize to X", or "needs
more discussion".

| # | CLI | MCP | What's wrong |
|---|-----|-----|--------------|
| 1 | `apply` | `apply_to` | Same op, different verb form. MCP includes preposition; CLI drops it. |
| 2 | `withdraw` | `withdraw_from` | Same as above. |
| 3 | `ghost` | `mark_ghosted` | Diverges in *both* verb shape and tense (active vs. past participle marker). |
| 4 | `show` | `get_opportunity` | Read-one. CLI uses display verb (`show`), MCP uses accessor (`get`). |
| 5 | `new` | `new_opportunity` | MCP is namespaced with the noun; CLI is bare. |
| 6 | `sync` | `sync_data` | MCP's `_data` suffix is non-informative — what else would `sync` sync? |
| 7 | (none) | `get_stats` | MCP-only coverage. Should `jh stats` exist? |
| 8 | (none) | `touch` | MCP-only. What does it touch? If `last_activity = now()`, name it. |
| 9 | `priority X 5` | `set_priority` | CLI uses bare noun as verb; MCP uses `set_` prefix. CLI form reads ambiguously (set vs. filter vs. show). |
| 10 | `tag X foo` | `add_tag` / `remove_tag` | CLI conflates add+remove behind a single `tag` verb (presumably toggling or via flags). MCP splits them. Verify which is right. |
| 11 | `contact X ...` | `add_contact` | CLI verb shape; MCP `add_` prefix. Is `jh contact` add-only, or does it also edit/remove? |
| 12 | `note X ...` | `add_note` | Same pattern as contact. |
| 13 | `log X ...` | `log_interaction` | MCP suffix says *what* is logged; CLI assumes context. |
| 14 | `file write` | `write_file` | The flagged complaint. `write` is unintuitive for "add a new file". |
| 15 | `file write` | `write_file` + `import_file` | MCP has two write paths; CLI exposes only one. What's the user-facing difference? Is one redundant? |
| 16 | `file show` | `read_file` | Same op, `show` vs. `read`. Pick one across both surfaces. |
| 17 | `file delete`, `delete` | `delete_file`, `delete_opportunity` | CLI relies on group nesting to disambiguate; MCP suffixes. Both are valid — pick one and apply uniformly. |
| 18 | Top-level lifecycle verbs (`apply`, `ghost`, `archive`, …) | Flat `*_opportunity` suffix | CLI assumes "everything operates on an opportunity by default". MCP names the noun explicitly. Should CLI grow an `opp` subgroup, or should MCP drop the suffix? |

## Principles the review should commit to

Proposed — to be ratified or revised during the review itself.

1. **One verb per concept across surfaces.** If the CLI says `show`, MCP
   should say `show` (or be a thin alias). Drift is the bug.
2. **Verb intuitiveness beats verb correctness.** `write` is technically right
   for "create or overwrite bytes", but `add` / `upload` match user mental
   models for "I have a new file". When they diverge, pick the intuitive one
   and document the technical nuance, not the other way round.
3. **Surface coverage should match.** If MCP has `get_stats` and `touch`, the
   CLI should have them too — or the MCP versions should justify their
   absence elsewhere. Asymmetry hides features from one of the two audiences.
4. **Prefer explicit prefixes for mutators on flat surfaces.** `set_priority`
   beats `priority` because the latter could plausibly mean "show",
   "filter", or "set". On grouped surfaces (CLI under `jh opp …`) the noun
   alone is fine because the group already implies the verb context.
5. **Group bare nouns; suffix flat surfaces.** Two valid disambiguation
   strategies. Pick one per surface, not both. CLI naturally favors groups
   (`jh file delete`); MCP naturally favors suffixes (`delete_file`). That's
   fine — the rule is "be consistent within a surface", not "be identical
   across surfaces".
6. **One operation, one name.** If `write_file` and `import_file` are both
   "put bytes into the store", merge them. If they're genuinely different,
   the names must say how (e.g. `upload_file` from local path vs.
   `write_file` from inline bytes).

## Out of scope

- The MCP `mcp__jobhound__*` prefix — that's enforced by the MCP protocol, not
  a naming choice we control.
- Internal module names (`commands/list_.py`'s trailing underscore, etc.) —
  user-invisible.
- Help text wording, error messages, log format — separate review.

## Method

1. **Enumerate.** Build a single table of every CLI command, every CLI
   subcommand, every MCP tool. Source of truth is the registration sites
   in `src/jobhound/cli.py`, `src/jobhound/commands/*.py`, and the MCP server
   registration module.
2. **Categorize.** Tag each entry with: surface (CLI / MCP / both), domain
   (opportunity / file / infra / misc), action class (create / read / update
   / delete / lifecycle-transition / collection-mutate).
3. **Diff.** For every operation that exists on both surfaces, flag any
   verb-form divergence. For every operation that exists on only one surface,
   flag it as a coverage gap unless there's a documented reason (e.g.
   `file open` is CLI-only because launching a GUI from an agent session is
   meaningless — already justified in `docs/specs/2026-05-15-file-open-design.md`).
4. **Propose.** Produce a rename table: `current_name → proposed_name` with
   a one-line rationale per row. Group by "uncontroversial" vs. "needs
   discussion".
5. **Migration story.** v0.6.1 is on PyPI and there are MCP clients in the
   wild. Renames are breaking. Decide: hard cut at v0.7 (with a clear
   `CHANGELOG.md` migration section), deprecation aliases for one minor, or
   per-command judgment. Don't ship renames without answering this.

## Deliverable

A follow-up design doc (`docs/specs/YYYY-MM-DD-command-rename-plan.md`) with:
- the rename table from step 4,
- the migration decision from step 5,
- explicit "no change" entries for surface diffs the review decided to keep.

The implementation is then a mechanical change against that table — Typer
command names, MCP tool registrations, tests, README, completions, and any
spec docs that reference the old names (the `2026-05-15-*-design.md` set in
particular).

## Estimated effort

- Review + proposal doc: ~half day of focused work.
- Implementation (assuming a hard cut, no aliases): ~half day; mostly
  rename mechanics + test/doc updates. Aliases roughly double the
  implementation cost and complicate the help output, so the migration
  decision is the main cost lever.
