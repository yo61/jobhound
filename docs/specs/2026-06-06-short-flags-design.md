# Short-flag Aliases — Design

Date: 2026-06-06
Status: Drafted, light process
Branch: `feat/short-flags`

Add short-flag aliases (e.g. `-a` for `--all`) to existing `Parameter(name=[...])` declarations across `src/jobhound/commands/*.py`. Mechanical, additive change. No semantics change; long forms continue to work.

## Why

`jh` has no short flags today. Standard CLI tools (`ls`, `grep`, `git`) have them; the project owner asked for the same ergonomics.

## Scope

Only flags that **already** have explicit `Parameter(name=[...])` declarations get a short alias. Adding `Parameter` annotations to auto-named lifecycle command flags (e.g. `--company`, `--role`, `--now`, `--on`) is out of scope for this PR — those can be a separate sweep later.

## The mapping

| Long flag | Short | Commands |
|---|---|---|
| `--all` | `-a` | `list`, `stats` |
| `--archived` | `-A` (capital) | `list`, `stats` |
| `--status` | `-s` | `list`, `stats`, `export` |
| `--json` | `-j` | `show`, `stats` |
| `--priority` | `-p` | `export` |
| `--out` | `-o` | `file read` |
| `--name` | `-n` | `file write` |
| `--content` | `-c` | `file write`, `file append` |
| `--from` | `-f` | `file write`, `file append` |
| `--yes` | `-y` | `file delete` |
| `--dest` | `-d` | `completion install` |

### Deliberately long-only

- `--archived` uses capital `-A` to disambiguate from `-a` (`--all`) on the same command (`list`, `stats`). Both can be typed alongside each other; capital A avoids ambiguity.
- `--shell`, `--slug`, `--active-only`, `--include-archived`, `--overwrite`, `--base-revision`: no natural one-letter shortcut. Better long-only than invented.
- `--name`, `--content`, `--from`, `--yes`, etc. on auto-named lifecycle command params (e.g. `delete.py`'s `--yes`, which is auto-named, not declared via `Parameter`): out of scope. Existing `file delete` has explicit `Parameter(name=["--yes"], negative=())` so it gets `-y`; auto-named `delete` does not.

## Per-command summary

- `commands/show.py` (1 flag): `--json` → `-j`
- `commands/list_.py` (3 flags): `--all` → `-a`, `--archived` → `-A`, `--status` → `-s`
- `commands/stats.py` (4 flags): `--all` → `-a`, `--archived` → `-A`, `--status` → `-s`, `--json` → `-j`
- `commands/export.py` (2 flags): `--status` → `-s`, `--priority` → `-p`
- `commands/file.py` (5 flags across 4 subcommands): `--out` → `-o`, `--name` → `-n`, `--content` → `-c`, `--from` → `-f`, `--yes` → `-y`
- `commands/completion.py` (1 flag): `--dest` → `-d`

Six files. Each edit is mechanical: extend the existing `Parameter(name=[...])` list.

## Testing

For each command file edited, the existing test suite is unchanged (long forms must still work). Add one new test per command that invokes a representative short flag and asserts the same behavior as the long form. Cyclopts validates flag registration at app build time, so if a short alias conflicts within a command's namespace, the app would fail to build — the existing tests catch that.

## Non-goals

- No changes to MCP tool signatures (they use named params, not flags).
- No changes to auto-named flags in lifecycle commands.
- No documentation updates (cyclopts auto-generates `--help` from the `Parameter` declarations; short flags will appear there automatically).
- No changes to bash/zsh/fish completion scripts (short flags don't need completion candidates of their own).

## Rollback

If a short alias collides with something I missed, the app will fail to build at startup. Fix is to remove the offending short alias from that command's `Parameter(name=[...])` list.
