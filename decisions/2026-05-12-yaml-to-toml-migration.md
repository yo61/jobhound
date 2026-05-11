# Decision: Bulk-import YAML store as a single TOML root commit

## Decision
Migrate the legacy YAML job-hunt store at
`~/Documents/Projects/Job Hunting 2026-04/` into a fresh TOML data root at
`~/.local/share/jh/` via a one-shot script (`scripts/migrate_from_yaml.py`)
that produces a single bulk import commit. The script is kept in the repo
for reference rather than deleted post-run. The old YAML repo is preserved
unmodified as read-only history.

## Context
The original workflow stored each opportunity as a `meta.yaml` plus
adjacent markdown files inside a Taskfile-driven directory tree under
iCloud-synced Documents. The new `jh` CLI (Original CLI plan complete +
DDD refactor) reads/writes TOML at the XDG data home. Both stores cannot
coexist as the source of truth — the migration cuts over to TOML.

The source repo contained 7 active opportunities and a `_shared/` tree
with 4 subdirectories (`cv_base`, `linkedin`, `networking`, `templates`).
The YAML repo's git history is granular (one commit per day-of-field-edit)
but not load-bearing for the user's workflow — it's effectively an
append-only audit trail of past edits, not a record we need to query.

## Alternatives considered

**(a) Replay each YAML commit as a TOML commit.** Preserves the audit
trail. Requires either a `git filter-repo` script that rewrites each
commit's `meta.yaml` to `meta.toml`, or a synthetic replay that walks
the YAML history and applies each change through the `jh` CLI. Either
approach is days of work for an audit trail nobody is querying.

**(b) Per-opportunity migration commits.** Run the migration script in a
loop, committing each opportunity separately. Cleaner per-opportunity
audit on the new repo's `git log`, but the commits are all the same
mechanical "imported from yaml" — no information gain.

**(c) Single bulk import commit (chosen).** One commit:
`import: bulk migration from yaml store`. Clean starting point. The
TOML repo's history begins fresh, with subsequent commits genuinely
representing the new workflow.

## Reasoning
Option (c) was chosen because:
- The YAML repo's commit-level granularity isn't being queried by
  anything (no audit, no compliance, no reporting).
- A fresh single-root history is the right starting point for a tool
  that will commit per-action going forward — the boundary between
  "imported state" and "actions taken in `jh`" stays clean and
  legible in `git log`.
- The YAML repo is preserved verbatim as a fallback if the migration
  ever needs to be re-run with different logic.

## Trade-offs accepted

- **Lost granularity:** the YAML repo's per-field commit history is no
  longer reachable from the TOML repo's `git log`. The original repo
  remains on disk as the only source of historical detail.
- **No migration tests.** The original CLI plan's Task 24 specified
  `tests/test_migrate.py`. The choice was to skip and rely on one-time
  human verification: run the script in dry-run mode, inspect the
  proposed copy plan, run `--apply`, then `jh list` and spot-check
  meta.toml content. Acceptable for a one-shot; if the script ever
  needs to run again on a different input, tests should be added then.
- **Script retention** despite being one-shot. Costs ~170 lines in the
  repo; pays for itself only if the migration ever needs to be re-run
  or referenced. Bias toward keeping documented one-shots over deleting
  them.
- **Defaults route to `~/.local/share/jh/`.** Locks in the XDG data
  home as the canonical data root. Custom locations remain possible via
  `~/.config/jh/config.toml`'s `db_path` setting, but the migration
  script hard-codes the default destination via `load_config()`.

## Skip rules embedded in the script
- `meta.yaml` (replaced by generated `meta.toml`)
- `.DS_Store`, `.gitkeep` (filesystem noise)
- `.claude/` directories (assistant working state, not data)

These are deliberate; new file types should be re-examined if they
appear in a future re-run.

## Supersedes
Nothing. The original CLI plan referenced this work as "Task 24" but
did not enumerate the strategic choices; this entry fills that gap
post-hoc.

## Outcome
- Single commit `b8c48c0 import: bulk migration from yaml store` in
  `~/.local/share/jh/`.
- 7 opportunities + 4 `_shared/` subdirectories successfully imported.
- Old repo at `~/Documents/Projects/Job Hunting 2026-04/` preserved
  unmodified; do not edit.
- Migration script retained at `scripts/migrate_from_yaml.py` with a
  dry-run default. To re-run safely: read the file's docstring; run
  without `--apply` first to inspect the plan.
