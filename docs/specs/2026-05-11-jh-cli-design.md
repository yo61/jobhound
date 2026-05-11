# `jh` CLI — Design Spec

Date: 2026-05-11
Status: Draft, awaiting review

## Goal

Replace the current Taskfile-driven job-hunt workflow (which requires
hand-editing `meta.yaml`) with an **action-based Python CLI** named `jh`.
Operations are verbs (`apply`, `log`, `withdraw`, …); status changes are
side-effects of actions, not direct field edits.

## Scope

In scope:

- New Python package `jobhound` in a new sibling repo at
  `~/Documents/Projects/jobhound/`, exposing a `jh` CLI entry point.
- Full migration of operations away from the existing
  `Job Hunting 2026-04/` repo (Taskfile + Python scripts). The old repo
  becomes the **data source** for a one-shot import; once migrated, the
  user-facing surface is `jh` only.
- Switch storage from per-opportunity `meta.yaml` to `meta.toml`.
- Move data out of the project tree into XDG-strict directories under `$HOME`.
- Make the `jh` repo's data root a git repo, with auto-commits per action.

Out of scope (explicitly deferred):

- Rewriting `build_dashboard.py`'s output design (the dashboards stay
  functionally as-is; only the input format and location change).
- Auto-push to a remote (manual `jh sync` runs `git push`).
- Web/UI front-end.
- Cross-machine sync beyond `git push`.

## Architecture

### Package layout

```
~/Documents/Projects/jobhound/
  pyproject.toml
  uv.lock
  Taskfile.yml             # dev:* tasks only (lint, fmt, test, typecheck, hooks)
  README.md
  USAGE.md
  src/jobhound/
    __init__.py
    cli.py                 # typer app, subcommand registration
    config.py              # XDG path resolution, config.toml load
    paths.py               # Paths dataclass: db_root, opportunities, shared, archive, cache, logs
    meta_io.py             # tomllib read, tomli-w write, validation
    opportunities.py       # Opportunity dataclass + queries (native TOML dates)
    prompts.py             # questionary helpers (slug picker, status menu, date)
    git.py                 # auto-commit helper
    render/
      dashboard.py
      today.py
      ics.py
      cv.py
      md_pdf.py
    commands/
      __init__.py
      apply.py log.py note.py link.py contact.py tag.py priority.py
      withdraw.py ghost.py accept.py decline.py
      new.py edit.py archive.py delete.py
      build.py today.py dashboard.py list.py sync.py
      cv.py pdf.py
  scripts/
    migrate_from_yaml.py   # one-shot migration; not part of jh
  tests/
    conftest.py            # tmp db_path fixture, sample opportunities
    test_*.py
  docs/
    specs/
      2026-05-11-jh-cli-design.md
    schema.md              # meta.toml field reference (dev-facing only)
```

### Entry point

`pyproject.toml`:

```toml
[project.scripts]
jh = "jobhound.cli:app"
```

After `uv sync`, `jh` is available inside the venv.

### CLI framework

- **`typer`** for the CLI (Click underneath, type-annotation ergonomics,
  auto-generated `--help`).
- **`questionary`** for interactive menus (status pick, channel pick,
  direction pick) and confirmations.
- **`typer.prompt`** for simple text/date input.

### File format

**TOML** everywhere. `meta.toml` per opportunity. Schema is documented in
`docs/schema.md` (dev-facing only). The file is **not** intended to be
hand-edited in normal operation — `jh edit` remains as an escape hatch,
but the runtime CLI does not surface field documentation.

### Storage location (XDG-strict)

| Purpose          | Path (default)                       |
| ---------------- | ------------------------------------ |
| Config           | `~/.config/jh/config.toml`           |
| Data root        | `~/.local/share/jh/`                 |
| Cache (derived)  | `~/.cache/jh/`                       |
| Logs             | `~/.local/state/jh/`                 |

`$XDG_*` environment variables are honoured if set.

Inside the data root:

```
~/.local/share/jh/
  .git/                              # data is git-tracked
  opportunities/<slug>/
    meta.toml
    notes.md
    correspondence/
    cv.md  cv.pdf
    job-description.{md,pdf,mhtml}
    interview-prep.md
    research.md
  _shared/
    cv_base/  linkedin/  networking/
  archive/<slug>/                    # closed opportunities, same shape
```

Derived outputs (regeneratable) live under the cache root:

```
~/.cache/jh/
  dashboard.md  dashboard.html  today.md  reminders.ics
```

### Config file

`~/.config/jh/config.toml` — created lazily if absent. Day-one schema:

```toml
db_path = "~/.local/share/jh"   # data root (XDG default)
auto_commit = true              # commit to data-root git on every mutation
editor = ""                     # override $EDITOR; empty = use $EDITOR or vi
```

Missing fields fall back to defaults. The file is the only configuration
surface; environment variables are not honoured (except XDG).

### Backend: git-tracked TOML files with auto-commit

The data root is a git repo. Every mutating subcommand performs:

```
write meta.toml (and any sibling artefacts)
git -C <db_path> add -A
git -C <db_path> commit -m "<verb>: <slug>[ <extra-context>]"
```

Commit message conventions (greppable):

| Verb        | Message                                                          |
| ----------- | ---------------------------------------------------------------- |
| `new`       | `new: 2026-05-foo-corp-engineering-manager`                      |
| `apply`     | `apply: 2026-05-foo-corp-engineering-manager`                    |
| `log`       | `log: <slug> <old_status> → <new_status>` (or `(no status change)`) |
| `withdraw`  | `withdraw: <slug>`                                               |
| `ghost`     | `ghost: <slug>`                                                  |
| `accept`    | `accept: <slug>`                                                 |
| `decline`   | `decline: <slug>`                                                |
| `note`      | `note: <slug>`                                                   |
| `link`      | `link: <slug> <name>`                                            |
| `contact`   | `contact: <slug> <name>`                                         |
| `tag`       | `tag: <slug> +foo -bar`                                          |
| `priority`  | `priority: <slug> <new>`                                         |
| `archive`   | `archive: <slug>`                                                |
| `delete`    | `delete: <slug>`                                                 |
| `edit`      | `edit: <slug>`                                                   |

Disable per-action with `--no-commit` (power user, e.g. mid-rebase) or
globally with `auto_commit = false` in config. **Never** auto-push.
`jh sync` runs `git push` (and only if the user has set up a remote).

If validation fails, the file is rewritten with the `# ERROR:` block (per
the existing `edit_opportunity` pattern) and the commit is **not** made.

## Subcommand catalog

### Action verbs (status-affecting)

| Verb        | Action                                  | Status effect                                                          |
| ----------- | --------------------------------------- | ---------------------------------------------------------------------- |
| `jh new`    | Create entry                            | → `prospect`                                                           |
| `jh apply`  | Submitted application                   | → `applied`, sets `applied_on`                                         |
| `jh log`    | Record interaction                      | Prompts for next status; default = advance one stage. Can pick `rejected` from this menu. |
| `jh withdraw` | I pulled out                          | → `withdrawn`                                                          |
| `jh ghost`  | Giving up; no response                  | → `ghosted`                                                            |
| `jh accept` | Accepted offer                          | → `accepted` (only valid from `offer`)                                 |
| `jh decline`| Declined offer                          | → `declined` (only valid from `offer`)                                 |

All bump `last_activity` to today. All prompt for next `next_action` +
`next_action_due` (except `ghost`, which is terminal).

### Non-status verbs

| Verb           | Action                                                  |
| -------------- | ------------------------------------------------------- |
| `jh note`      | Append timestamped one-liner to `notes.md`              |
| `jh link`      | Add/update an entry in `links`                          |
| `jh contact`   | Add a contact entry                                     |
| `jh tag`       | Add/remove tags                                         |
| `jh priority`  | Set `high`/`medium`/`low`                               |

`jh note` bumps `last_activity` (a note implies you thought about it).
The other four do not.

### Infrastructure verbs (migrated from Taskfile)

| Verb            | Action                                                  |
| --------------- | ------------------------------------------------------- |
| `jh edit`       | Escape hatch — open `meta.toml` in `$EDITOR` with validation loop (port of current `edit_opportunity`) |
| `jh build`      | Regenerate dashboards / today.md / reminders.ics into `~/.cache/jh/` |
| `jh today`      | `jh build`, then print `today.md`                       |
| `jh dashboard`  | `jh build`, then `open` `dashboard.html`                |
| `jh list`       | One-line summary of every opportunity                   |
| `jh archive`    | Move `<slug>` from `opportunities/` to `archive/`       |
| `jh delete`     | `git rm` (tracked) + `trash` (untracked)                |
| `jh cv`         | Render `<slug>/cv.md` → `<slug>/cv.pdf`                 |
| `jh pdf`        | Render any markdown file to PDF                         |
| `jh sync`       | `git push` (on-demand, no auto-push)                    |

### Help discovery

`jh --help` lists all subcommands. `jh <verb> --help` shows that verb's
flags and prompts. No `jh schema` / `jh fields` runtime command — schema
lives in `docs/schema.md`.

## Interaction model

### Hybrid prompting

- Verbs with ≤2 inputs are pure flag-driven (e.g. `jh note SLUG --msg "..."`,
  `jh priority SLUG --to high`).
- High-input verbs (`jh log`, `jh apply`, `jh contact`, `jh new`) walk the
  user through prompts for missing fields. Any field supplied via flag
  skips its prompt. Power users can fully script by providing all flags.

### Slug resolution

Positional argument. Resolution:

1. Exact match against `opportunities/*/` → use it.
2. Otherwise: prefix or substring match across all slugs.
3. If exactly one slug matches → use it.
4. If multiple match → print the matches and exit non-zero.
5. If none → error.

The same resolver is also used over `archive/*/` for `jh edit` so an
archived opportunity can still be inspected.

### Dates

- Input: ISO `YYYY-MM-DD`. Convenience: `today`, `tomorrow`, `+7d` accepted.
- Storage: native TOML date type (no string coercion).
- Default for any date field with a prompt: today.

### `jh log` deep-dive (the workhorse)

**Interactive flow** (all prompts skipped if the corresponding flag is set):

```
$ jh log elliptic
Channel: ● email ○ linkedin ○ call ○ meeting ○ other
Direction: ● from ○ to
Who: Joey Capper
Open editor for body content? [Y/n] Y         → $EDITOR opens a temp file
Next status (currently: applied):
  ● screen     (advance to next stage)        [default]
  ○ interview
  ○ offer
  ○ rejected
  ○ stay at applied
Next action: Confirm screening date
Next action due [2026-05-18]: <Enter>
```

**Effects on disk**:

- New file `correspondence/2026-05-11-email-from-joey-capper.md` containing
  the body text.
- `meta.toml` updates: `status=screen`, `last_activity=2026-05-11`,
  `next_action=...`, `next_action_due=2026-05-18`.
- Git commit: `log: 2026-04-elliptic-engineering-manager applied → screen`.

**Fully-flagged invocation** (for scripting):

```
jh log elliptic \
  --channel email --direction from --who "Joey Capper" \
  --body draft.md \
  --next-status screen \
  --next-action "Confirm screening date" \
  --next-action-due 2026-05-18
```

**Validation rules** (enforced before any write):

- `--next-status` must be a legal transition from the current status.
- Legal forward transitions via `jh log`: `applied→screen`,
  `screen→interview`, `interview→offer`. `prospect→applied` is **not**
  legal via `jh log` (use `jh apply`, which also sets `applied_on`).
  Similarly `offer→accepted`/`offer→declined` are **not** legal via
  `jh log` (use `jh accept`/`jh decline`).
- `rejected` is a legal target from any active status.
- "Stay" is always a legal target (status unchanged).
- Cross-stage jumps (e.g. `applied→interview`) require `--force`. The
  interactive menu does **not** offer cross-stage jumps; only legal
  transitions plus "stay" plus "rejected" appear.
- Default in the interactive menu:
  - `prospect`: stay (no forward target without `jh apply`).
  - `applied`: screen.
  - `screen`: interview.
  - `interview`: offer.
  - `offer`: stay (forward requires `jh accept`/`jh decline`).

## Shared mechanics

### Config loading (`jobhound.config`)

- `load_config() -> Config` reads `~/.config/jh/config.toml` if present,
  else returns defaults.
- `Config` is a frozen dataclass: `db_path: Path`, `auto_commit: bool`,
  `editor: str`.
- `$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`, `$XDG_CACHE_HOME`, `$XDG_STATE_HOME`
  are honoured if set.
- `~` expansion happens at load time.

### Paths (`jobhound.paths`)

A `Paths` dataclass derived from `Config`. All commands receive a
`Paths` instance via typer's dependency-injection-ish pattern (a callback
on the root app).

### Meta IO (`jobhound.meta_io`)

- `read(path: Path) -> Opportunity` — `tomllib.load`, then build via
  `opportunity_from_dict`.
- `write(opp: Opportunity, path: Path) -> None` — `tomli_w.dumps` with
  field ordering preserved.
- `validate(data: dict, path: Path) -> Opportunity` — ports the current
  validation in `edit_opportunity._validate`, including slug-safety checks.

### Auto-commit (`jobhound.git`)

- `commit_change(db_path: Path, message: str, *, enabled: bool) -> None`
  runs `git add -A && git commit -m <message>`. No-op when `enabled` is
  False or the working tree is clean.
- Failed validation → no commit (caller doesn't call it).
- The decorator `@committing("<verb>")` on a typer subcommand handles the
  wrap automatically: it reads the slug from the args, reads `auto_commit`
  from config, and commits after the function returns success.

### Validation reuse

The validation loop from `edit_opportunity.py` (parse → validate → reopen
editor with `# ERROR:` block) is preserved in `jh edit`, ported to read
TOML via tomllib.

## Migration

A one-shot script at `scripts/migrate_from_yaml.py` (not part of `jh`).
Run once:

```
uv run python scripts/migrate_from_yaml.py \
  --from "~/Documents/Projects/Job Hunting 2026-04" \
  --to "~/.local/share/jh"
```

Steps:

1. Create `<to>/opportunities/`, `<to>/_shared/`, `<to>/archive/`.
2. For each `<from>/opportunities/<slug>/`:
   - Convert `meta.yaml` → `meta.toml` (dates → native TOML dates).
   - Copy `notes.md`, `correspondence/`, `cv.*`, `job-description.*`,
     `interview-prep.md`, `research.md` as-is.
3. Same for `<from>/archive/`.
4. Copy `<from>/_shared/` as-is.
5. `git init <to> && git add -A && git commit -m "Initial import"`.
6. Print a summary and a reminder: "Old repo is untouched. Delete it once
   you've verified `~/.local/share/jh` is correct."

The migration script is intentionally **not** a `jh` subcommand — it's a
one-time operation and shouldn't appear in `jh --help`.

## Tests

- pytest, top-level `tests/` mirroring `src/jobhound/`.
- `conftest.py` provides:
  - `tmp_db` fixture: a tmpdir set up as a valid `db_path` (with `.git`
    initialised), populated with a small set of sample opportunities at
    known statuses.
  - `cli_runner` fixture: typer's `CliRunner` configured to point at the
    `tmp_db`.
- Every subcommand has at least:
  - One happy-path test that exercises the flag-driven mode.
  - One test that asserts the correct git commit was created.
  - One test for the failure mode the verb is most likely to hit (e.g.
    `jh accept` from non-`offer` status).
- Status-transition rules tested exhaustively in `test_transitions.py`.
- Slug resolution tested in `test_prompts.py`.
- No tests for the interactive prompts themselves (out of scope; covered
  manually).

## Docs

| File                                     | Purpose                                                              |
| ---------------------------------------- | -------------------------------------------------------------------- |
| `README.md`                              | Install, first-run, config, paths overview                           |
| `USAGE.md`                               | Day-to-day handbook — rewrite of the existing one in `jh` terms      |
| `docs/schema.md`                         | `meta.toml` field reference (dev-facing only, not surfaced at runtime) |
| `docs/specs/2026-05-11-jh-cli-design.md` | This file                                                            |

## Open questions / deferred work

- **Reminders**: the existing macOS LaunchAgent calls `task build`. After
  migration it should call `jh build`. The LaunchAgent install scripts
  themselves can move into the new repo (`scripts/install_reminders.sh`)
  or stay where they are; deferred — fix in the implementation phase.
- **Auto-push on `jh sync`**: out of scope for v1. Could be a config flag
  later (`push_on = ["sync", "interactive-exit"]`).
- **`jh log --body -`**: read body from stdin. Useful for piping. Trivial
  to add; deferred unless needed.
- **`jh fsck`** (validate the whole data root, find orphaned files): nice
  to have, deferred.
- **Cross-machine sync**: implied by git but not designed. The user owns
  the remote; the CLI does not.
