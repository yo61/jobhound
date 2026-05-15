# `jh` shell completion — Design Spec

Date: 2026-05-15
Status: Draft, awaiting review
Branch: `feat/shell-completion` (not yet created; cut off `main`)

Add contextual tab completion for the `jh` CLI across bash, zsh, and fish:

- `jh <tab>` → top-level commands
- `jh file <tab>` → file subcommands (`list`, `show`, `write`, `append`, `delete`, `open`)
- `jh file open <tab>` → opportunity slugs
- `jh file open <slug> <tab>` → filenames in that opportunity

Same pattern extends to `jh show`, `jh apply`, `jh log`, etc. — any positional
that takes a slug or filename should complete.

## Strategic direction

### Why this exists

Today the user has to type slugs and filenames blind. Slugs like
`2026-05-12-acme-corp-staff-engineer` are not memorable. The user knows
the company but not the full slug, so they `jh list | grep acme` to find
it, then copy-paste. That breaks flow.

Shell completion makes the CLI feel like a first-class tool — same UX
contract as `git`, `gh`, `kubectl`. The user types `jh file open ac<tab>`
and the canonical slug fills in.

### Why this is non-trivial

Two classes of completion:

1. **Static** — commands and subcommands. Known at install time. Can be
   baked into a shell-specific completion script. Cheap.
2. **Dynamic** — opportunity slugs and filenames inside an opp. Must be
   computed at completion time from the user's actual data. Cannot be
   baked into a script.

Dynamic completion is the load-bearing piece. The standard pattern
(used by `gh`, `kubectl`, `helm`, `git`) is:

- The shell completion script is a thin shim.
- It invokes the tool itself with a hidden subcommand
  (`jh __complete <shell> <words...>`).
- The tool prints completion candidates to stdout, one per line.
- The shell script reads stdout into its completion buffer.

This puts all completion logic in Python where it has full access to
`opportunities_dir`, `file_service.list_`, and so on.

### Why not use cyclopts native completion

Cyclopts 4.11.2 (the pinned version) does not ship a turnkey completion
generator comparable to `click`'s `@click.shell_completion` or
`typer --install-completion`. **Verify this is still true before
implementing** — cyclopts evolves fast and may have shipped something
between the pin and the picked-up date. If it has, prefer the native
mechanism; the design below is the fallback.

### Why not `shtab`

`shtab` generates completion scripts from argparse/click/argcomplete
introspection. It does not understand cyclopts' `App` structure, and it
has no story for dynamic completion (its closing argument is "use a
function that calls your tool" — same pattern we're rolling).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Shell completion script (bash/zsh/fish)                    │
│  - Registered with the shell's completion system            │
│  - Knows: how to extract <words> from the command line       │
│  - Calls: jh __complete <shell> <words...>                  │
│  - Reads: stdout, feeds it back to the shell                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  jh __complete <shell> <words...>  (hidden subcommand)      │
│  - Parses <words> to determine completion context           │
│  - Dispatches to a completer function for that context      │
│  - Prints candidates, one per line, to stdout               │
└─────────────────────────────────────────────────────────────┘
                          │
       ┌──────────────────┼──────────────────────┐
       ▼                  ▼                      ▼
  ┌─────────┐      ┌──────────┐         ┌──────────────┐
  │ slug    │      │ filename │         │ static       │
  │ enum    │      │ enum     │         │ (commands,   │
  │ (cheap) │      │ (cheap)  │         │ subcommands) │
  └─────────┘      └──────────┘         └──────────────┘
```

## Design decisions

### 1. Hidden command, not flag

`jh __complete ...` not `jh --complete`. Three reasons:

- Subcommands compose with positionals (`__complete zsh jh file open ac`);
  flags don't.
- Hidden subcommands don't appear in `--help` output; flags would
  pollute the global flag namespace.
- Double-underscore prefix is the established convention (`kubectl
  __complete`, `helm __complete`).

In cyclopts, register with a `name` that starts with `__` and either
omit it from help or override the App's help renderer to filter out
double-underscore commands.

### 2. Completion context detection

The `__complete` handler receives the full `<words>` list (everything
typed so far, including the partial last word). Dispatch rules,
evaluated top-down:

| Position pattern                              | Completer       |
| --------------------------------------------- | --------------- |
| `jh`                                          | top-level cmds  |
| `jh file`                                     | file subcmds    |
| `jh file <show\|write\|append\|delete\|open> ` | slug            |
| `jh file <show\|write\|append\|delete\|open> <slug> ` | filename in slug |
| `jh <show\|apply\|log\|...> ` (any cmd taking a slug positional) | slug |
| `jh --<flag> `                                | flag-value completer (per flag) |

For v1, focus on the slug + filename cases. Flag-value completion
(e.g. completing `--status`'s enum values) is a follow-up.

### 3. Slug completer

```python
def _complete_slug(prefix: str) -> Iterable[str]:
    cfg = load_config()
    paths = paths_from_config(cfg)
    if not paths.opportunities_dir.exists():
        return
    for entry in paths.opportunities_dir.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            yield entry.name
```

**Critical:** return *canonical* slug names, unfiltered by `prefix`.
The shell does its own prefix matching against the candidate list. If
this function filters by prefix, fuzzy/menu-style completion (zsh
`menu-select`, fish substring match) breaks.

`resolve_slug` accepts prefix matches at command runtime — that's a
separate concern from completion.

### 4. Filename completer

```python
def _complete_filename(slug: str, prefix: str) -> Iterable[str]:
    cfg = load_config()
    paths = paths_from_config(cfg)
    try:
        canonical = resolve_slug(slug, paths.opportunities_dir)
    except Exception:
        return  # ambiguous/missing slug; no completions
    store = GitLocalFileStore(paths)
    for entry in file_service.list_(store, canonical.name):
        yield entry.name
```

Routes through `file_service` for the same reason `jh file open` does:
the FileStore Protocol must be honoured even by completion code.

### 5. Performance: lazy imports

`jh --help` cold-start imports the world (all command modules,
cyclopts, MCP machinery if the entry point pulls it). For completion
to feel instant (target: <100ms), the `__complete` code path must
avoid imports it doesn't need.

Specifically:

- The `__complete` dispatcher should be reachable **without** loading
  the other command modules. One option: put `__complete` in its own
  module (`src/jobhound/commands/_complete.py`) and have `cli.py`
  branch on `sys.argv[1] == "__complete"` *before* registering the
  rest of the commands.
- Within `_complete.py`, import `file_service` / `GitLocalFileStore`
  only inside `_complete_filename` (the only path that needs them).
  Slug completion needs only `pathlib` + `load_config` + `paths`.

**Action item for implementation:** measure cold-start with
`hyperfine 'jh __complete zsh jh file open '` before and after lazy
imports. If <100ms cold, ship it. If not, profile with `python -X
importtime`.

### 6. Shell coverage

v1: bash, zsh, fish. The three shells the user community actually
uses. PowerShell can come later if requested — it has a different
completion model (parameter-set objects, not text) that's worth its
own design pass.

Per-shell completion script lives in `src/jobhound/_completion/`:

- `_completion/jh.bash`
- `_completion/jh.zsh`
- `_completion/jh.fish`

These are static text files, shipped with the wheel. The install
command reads them and writes them out.

### 7. Install UX

```
jh completion install             # auto-detect $SHELL, install
jh completion install --shell zsh # explicit shell
jh completion bash                # print to stdout
jh completion zsh                 # print to stdout
jh completion fish                # print to stdout
```

`install` paths (auto-detected from `$SHELL`):

| Shell | Path                                          |
| ----- | --------------------------------------------- |
| bash  | `~/.local/share/bash-completion/completions/jh` |
| zsh   | `~/.zfunc/_jh` (and remind user to `fpath+=~/.zfunc; autoload -U compinit; compinit`) |
| fish  | `~/.config/fish/completions/jh.fish`          |

The print-to-stdout variants are for users with non-standard setups
(homebrew zsh, custom completion dirs, etc.). They eval/save it
themselves.

### 8. What the shell scripts actually do

Sketch for bash:

```bash
_jh_complete() {
    local IFS=$'\n'
    local response
    response=$(jh __complete bash "${COMP_WORDS[@]:0:$COMP_CWORD}" "${COMP_WORDS[$COMP_CWORD]}" 2>/dev/null)
    COMPREPLY=($(compgen -W "$response" -- "${COMP_WORDS[$COMP_CWORD]}"))
}
complete -F _jh_complete jh
```

Sketch for zsh:

```zsh
#compdef jh
_jh() {
    local -a candidates
    candidates=("${(@f)$(jh __complete zsh ${words[1,$CURRENT-1]} ${words[$CURRENT]} 2>/dev/null)}")
    compadd -a candidates
}
_jh "$@"
```

Sketch for fish:

```fish
function __jh_complete
    set -l tokens (commandline -opc) (commandline -ct)
    jh __complete fish $tokens 2>/dev/null
end
complete -c jh -f -a "(__jh_complete)"
```

These are sketches — verify quoting (filenames with spaces in
correspondence/) before shipping.

## Tests

`tests/commands/test_complete.py`:

- **Static completion** — `jh __complete <shell> jh ""` returns the
  top-level command list. Same for `jh file ""` → file subcommands.
- **Dynamic slug completion** — create temp `opportunities_dir` with
  three slug directories; assert all three appear in output. Hidden
  dirs (`.cache`, `.git`) excluded.
- **Dynamic filename completion** — populate one opp with three files
  via `file_service.write`; assert all three appear.
- **Unresolvable slug** — `jh __complete <shell> jh file open
  not-a-real-slug ""` returns empty (does not error).
- **No-config / no-opps-dir** — `jh __complete` runs without
  `~/.jobhound/config.toml` returning candidates that make sense
  (empty for slug completer, full static lists for command completers).
- **Performance** — micro-benchmark in a perf test (skip by default,
  run on demand): `__complete` for slugs must return in <100ms on the
  test author's machine. Not a CI gate; a regression canary.

Install command tests:

- `jh completion bash` prints the bash script content (asserted to
  contain `complete -F _jh_complete jh`).
- `jh completion install --shell zsh --dest <tmpdir>` writes the
  script to `<tmpdir>/_jh` and prints next-steps. (Add a `--dest`
  override for testability if needed; otherwise use a fixture that
  redirects `$HOME`.)

## Out of scope

- **Rich completion descriptions.** zsh can show
  `acme-staff-eng   Acme Corp · Staff Engineer · applied`
  next to each candidate. Lovely UX. Requires a separate output
  format from `__complete` and extra metadata per slug. File as a
  follow-up.
- **Flag value completion.** `--status <tab>` listing the enum
  values, `--tag <tab>` listing existing tags. Same machinery, just
  more dispatch rules. Add incrementally.
- **PowerShell.** Different completion model, worth its own design.
- **`jh mcp` completions.** The MCP server entry point doesn't need
  arg completion — it's typically launched by an MCP client, not
  typed at a prompt.
- **Caching slug/filename enumeration.** Premature. Measure first;
  the filesystem listings are tiny.

## Docs to update

- `docs/commands.md` (the table of `jh ...` commands) — add
  `jh completion`. Don't document `jh __complete` (it's internal).
- README "Installation" section — append a line about
  `jh completion install` for tab-completion.

## Risks / open questions

- **Cyclopts hidden-command support.** Verify cyclopts 4.11 lets us
  register a command name with a leading underscore and exclude it
  from `--help`. If not, the workaround is the
  `sys.argv[1] == "__complete"` early-branch in `cli.py` — that
  bypasses cyclopts entirely for the completion path, which is also
  better for startup performance.
- **Slug canonical form vs prefix match.** The shell's prefix
  matcher uses the candidates returned, not raw slugs. If we ever
  want fuzzy/substring matching (e.g. typing `eng` matching
  `acme-staff-engineer`), that requires returning all slugs and
  letting the shell do substring matching — zsh and fish support
  this; bash doesn't natively.
- **Filename quoting.** Correspondence filenames can contain
  hyphens and dots but should not contain spaces under current
  conventions. Confirm before shipping; if they can, the shell
  scripts need quoting passes.
