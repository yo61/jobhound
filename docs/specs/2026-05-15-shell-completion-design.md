# `jh` shell completion — Design Spec

Date: 2026-05-15
Last refreshed: 2026-05-17
Status: Approved 2026-05-17
Branch: `feat/shell-completion`

Tracking issue: [#44](https://github.com/yo61/jobhound/issues/44).

Add contextual tab completion for the `jh` CLI across bash, zsh, and fish:

- `jh <tab>` → top-level commands
- `jh file <tab>` → file subcommands (`list`, `read`, `write`, `append`, `delete`, `open`, `import`)
- `jh file open <tab>` → opportunity slugs
- `jh file open <slug> <tab>` → filenames in that opportunity (including
  filenames with spaces such as `Job Description.md`)
- `jh set <tab>` → settable field names; `jh set status <slug> <tab>`
  → `Status` enum values (positional); `jh set priority --to <tab>`
  → `Priority` enum values (flag value — `priority` is the only
  setter that uses a `--to` flag for its value)
- `jh clear <tab>`, `jh add <tab>`, `jh remove <tab>` → respective
  sub-verb lists, then slug, then per-sub-verb arguments

Same pattern extends to any positional taking a slug: accept, apply,
bump, decline, delete, ghost, log, show, withdraw.

## Strategic direction

### Why this exists

Today the user types slugs and filenames blind. Slugs like
`2026-05-12-acme-corp-staff-engineer` are not memorable. The user
knows the company but not the full slug, so they `jh list | grep acme`
to find it, then copy-paste. That breaks flow.

Shell completion makes the CLI feel like a first-class tool — same UX
contract as `git`, `gh`, `kubectl`. The user types `jh file open
ac<tab>` and the canonical slug fills in.

### Why this is non-trivial

Two classes of completion:

1. **Static** — commands, subcommands, enum values. Known at install
   time but easier to compute at completion time via cyclopts
   introspection than to hardcode into the shell script.
2. **Dynamic** — opportunity slugs and filenames inside an opp. Must
   be computed at completion time from the user's actual data.

The standard pattern (used by `gh`, `kubectl`, `helm`, `git`):

- The shell completion script is a thin shim.
- It invokes the tool itself with a hidden subcommand
  (`jh __complete <shell> <words...>`).
- The tool prints completion candidates to stdout, one per line.
- The shell script reads stdout into its completion buffer.

This keeps completion logic in Python, where it has full access to
`opportunities_dir`, `file_service.list_`, and the cyclopts command
tree.

### Why not cyclopts native completion

Cyclopts 4.11.2 (pinned in `pyproject.toml`, released 2026-05-04)
does not ship a turnkey completion generator comparable to `click`'s
`@click.shell_completion` or `typer --install-completion`. Cyclopts
evolves fast; before implementation, re-check the cyclopts release
notes — if a native generator has shipped, prefer it. The design
below is the fallback.

### Why not `shtab`

`shtab` generates completion scripts from argparse/click/argcomplete
introspection. It does not understand cyclopts' `App` structure, and
it has no story for dynamic completion (its closing argument is "use
a function that calls your tool" — the same pattern we're rolling).

## Closed open questions

The original draft of this spec listed three open questions. They are
resolved here so the implementation plan does not have to revisit them:

1. **Cyclopts hidden-command support** — `App.__init__` exposes
   `show: bool = True`, and the same kwarg is accepted by
   `app.command(...)` via `**kwargs`. Registering with `show=False`
   omits a command from `--help` and from cyclopts' command-not-found
   suggestions. No `sys.argv` early-branch fallback is required.
2. **Filename character set** — verified against the live data root
   at `$XDG_DATA_HOME/jh/opportunities`. Filenames with spaces exist
   today (`Job Description.md`, `About the Job.md`). The shell
   scripts must quote candidates correctly; this is no longer a
   speculative risk.
3. **Slug canonical form vs. fuzzy match** — keep canonical-only for
   v1. The `__complete` handler returns full canonical slugs and lets
   the shell perform its native prefix matching. Fuzzy/substring
   matching (zsh `menu-select`, fish substring) is a follow-up; it
   requires zero changes to `__complete` (return all slugs, the
   shell does the rest) but does need per-shell completer tuning.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Shell completion script (bash/zsh/fish)                    │
│  - Registered with the shell's completion system            │
│  - Knows: how to extract <words> from the command line      │
│  - Calls: jh __complete <shell> <words...>                  │
│  - Reads: stdout, feeds it back to the shell (quoting       │
│    candidates that contain spaces)                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  jh __complete <shell> <words...>  (hidden subcommand)      │
│  - Parses <words> against the cyclopts App tree to          │
│    determine completion context                             │
│  - Dispatches to a completer function for that context      │
│  - Prints candidates, one per line, to stdout               │
└─────────────────────────────────────────────────────────────┘
                          │
       ┌──────────────────┼──────────────────────┬──────────────┐
       ▼                  ▼                      ▼              ▼
  ┌─────────┐      ┌──────────┐         ┌──────────────┐  ┌──────────┐
  │ slug    │      │ filename │         │ static       │  │ enum     │
  │ enum    │      │ enum     │         │ (commands +  │  │ value    │
  │ (cheap) │      │ (cheap)  │         │  subcommands │  │ enum     │
  │         │      │          │         │  via         │  │ (cheap)  │
  │         │      │          │         │  cyclopts)   │  │          │
  └─────────┘      └──────────┘         └──────────────┘  └──────────┘
```

## Design decisions

### 1. Hidden command, not flag

`jh __complete ...`, not `jh --complete`. Three reasons:

- Subcommands compose with positionals (`__complete zsh jh file open ac`);
  flags don't.
- Hidden subcommands don't appear in `--help` output; flags would
  pollute the global flag namespace.
- Double-underscore prefix is the established convention (`kubectl
  __complete`, `helm __complete`).

Register as `app.command(_complete, name="__complete", show=False)`
in `src/jobhound/cli.py`.

### 2. Completion context detection

The `__complete` handler receives the full `<words>` list (everything
typed so far, including the partial last word). It dispatches by
walking the cyclopts App tree rather than parsing positions by
string. Pseudocode:

```python
def dispatch(words: list[str]) -> Iterable[str]:
    node: App = top_app
    for w in words[1:-1]:  # skip "jh" and the partial last word
        sub = node._commands.get(w)
        if sub is None:
            break  # we've left the static command tree → dynamic completer
        node = sub
    # node is now the deepest matched App; words[-1] is the partial
    if still_in_static_tree(node):
        yield from static_completer(node)
    else:
        yield from dynamic_completer(node, words)
```

| Position pattern | Completer |
| --- | --- |
| `jh ` | top-level commands (from `top_app._commands`, filtered by `show=True`) |
| `jh <sub-app> ` | subcommands of that App |
| `jh <verb> ` where verb takes a slug positional | slugs |
| `jh file <verb> <slug> ` | filenames in that opp |
| `jh set status <slug> ` | `Status` enum values (positional) |
| `jh set priority --to ` | `Priority` enum values (flag value) |

**Commands that take a slug positional** (verified against
`src/jobhound/commands/`): accept, add (after sub-verb), apply, bump,
clear (after sub-verb), decline, delete, file (after sub-verb), ghost,
log, remove (after sub-verb), set (after sub-verb), show, withdraw.

**Commands that do not take a slug**: archive (optional), export,
list, mcp, migrate, new, stats.

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

Return *canonical* slug names, unfiltered by `prefix`. The shell does
its own prefix matching. Filtering here would break fuzzy/menu-style
completion (zsh `menu-select`, fish substring match).

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
Filenames may contain spaces — quoting is the shell script's job
(see §6).

### 5. Enum registry

A small static table maps `(command_path) → enum class` for positional
arguments, and `((command_path), flag_name) → enum class` for flag
values. Today there is exactly one of each:

```python
from jobhound.domain.status import Status
from jobhound.domain.priority import Priority

# (command_path_after_slug) → enum class
_POSITIONAL_ENUMS: dict[tuple[str, ...], type[StrEnum]] = {
    ("set", "status"): Status,  # jh set status <slug> <value>
}

# (command_path, flag_name) → enum class
_FLAG_ENUMS: dict[tuple[tuple[str, ...], str], type[StrEnum]] = {
    (("set", "priority"), "--to"): Priority,  # jh set priority --to <value> <slug>
}
```

Free-text fields (`source`, `location`, `company`, `role`) deliberately
return no completions — typing freely is the intended UX.

Adding a third enum later (e.g. `Source` if it becomes typed) is a
two-line change: add the import and the appropriate entry in one of
the two tables.

### 6. Filename quoting per shell

Filenames with spaces require care in each shell. The original spec's
bash sketch is incorrect for the spaces case and is replaced.

**bash:**

```bash
_jh_complete() {
    local IFS=$'\n'
    local response
    mapfile -t response < <(jh __complete bash "${COMP_WORDS[@]:0:$COMP_CWORD}" "${COMP_WORDS[$COMP_CWORD]}" 2>/dev/null)
    COMPREPLY=()
    for cand in "${response[@]}"; do
        COMPREPLY+=("$(printf '%q' "$cand")")
    done
    compopt -o nospace 2>/dev/null
}
complete -F _jh_complete jh
```

`mapfile -t` reads stdout into an array, preserving spaces. `printf
'%q'` escapes the candidate so bash treats it as a single token when
inserted. `compopt -o nospace` prevents bash from appending a trailing
space mid-token (we control trailing spaces in the completer output if
needed).

**zsh:**

```zsh
#compdef jh
_jh() {
    local -a candidates
    candidates=("${(@f)$(jh __complete zsh ${words[1,$CURRENT-1]} ${words[$CURRENT]} 2>/dev/null)}")
    compadd -a candidates
}
_jh "$@"
```

`${(@f)…}` splits on newlines only (not whitespace), so spaces inside
a candidate stay intact. `compadd -a` adds the array verbatim.

**fish:**

```fish
function __jh_complete
    set -l tokens (commandline -opc) (commandline -ct)
    jh __complete fish $tokens 2>/dev/null
end
complete -c jh -f -a "(__jh_complete)"
```

Fish's `complete -a` reads `\n`-separated stdout and handles quoting
itself; `-f` disables file-name completion fallback.

Each script must be tested against at least one candidate that
contains a space (e.g. `jh file open <slug> Job<tab>` should complete
to `Job Description.md`).

### 7. Performance: lazy imports

`jh --help` cold-start imports all command modules. For completion to
feel instant (target: <100ms wall-clock), the `__complete` path must
avoid imports it doesn't need.

Strategy:

- Put `__complete` in its own module (`src/jobhound/commands/_complete.py`).
- Top-level imports in that module: stdlib + `cyclopts.App` only.
- `load_config` / `paths_from_config` imported lazily inside slug and
  filename completer functions.
- `file_service` and `GitLocalFileStore` imported lazily inside the
  filename completer (the only path that needs them).
- Enum classes imported lazily inside the enum completer.

Walk the cyclopts App tree using attribute introspection (no
re-importing of command modules — the cyclopts App already has them
all in `_commands` after `cli.py` runs).

**Action item for implementation:** measure cold-start with
`hyperfine 'jh __complete zsh jh file open '` before and after lazy
imports. If <100ms cold, ship it. If not, profile with
`python -X importtime jh __complete zsh jh file open`.

### 8. Shell coverage

v1: bash, zsh, fish. The three shells the user community actually
uses. PowerShell is out of scope; it has a different completion model
(parameter-set objects, not text) that's worth its own design pass.

Per-shell completion scripts ship as static text files inside the
wheel:

- `src/jobhound/_completion/jh.bash`
- `src/jobhound/_completion/jh.zsh`
- `src/jobhound/_completion/jh.fish`

The install command reads them and writes them out.

### 9. Install UX

```
jh completion install              # auto-detect $SHELL, install
jh completion install --shell zsh  # explicit shell
jh completion bash                 # print to stdout
jh completion zsh                  # print to stdout
jh completion fish                 # print to stdout
```

Install paths (auto-detected from `$SHELL`):

| Shell | Path |
| --- | --- |
| bash | `~/.local/share/bash-completion/completions/jh` |
| zsh  | `~/.zfunc/_jh` (and remind user to `fpath+=~/.zfunc; autoload -U compinit; compinit`) |
| fish | `~/.config/fish/completions/jh.fish` |

The print-to-stdout variants are for users with non-standard setups
(homebrew zsh, custom completion dirs). They eval/save it themselves.

`install` is idempotent: if the destination file already exists with
the current content, it's a no-op; if it differs, the existing file is
moved to `<path>.bak` before overwrite.

## Tests

`tests/commands/test_complete.py`:

- **Static — top-level**: `__complete zsh jh ""` returns every
  top-level command from `app._commands` (filtered to `show=True`).
- **Static — sub-App**: `__complete zsh jh file ""` returns the seven
  `file` subcommands.
- **Dynamic slug**: create a temp `opportunities_dir` with three slug
  directories; assert all three appear. Hidden dirs (`.cache`, `.git`)
  excluded.
- **Dynamic filename**: populate one opp with three files via
  `file_service.write`; assert all three appear. Include one filename
  with a space (`Job Description.md`); assert it appears verbatim
  (the shell script does the quoting).
- **Enum positional**: `__complete zsh jh set status <slug> ""`
  returns the 10 `Status` values.
- **Enum flag value**: `__complete zsh jh set priority --to ""`
  returns the 3 `Priority` values.
- **Unresolvable slug**: `__complete zsh jh file open not-a-real-slug ""`
  returns empty; does not error.
- **No config / no opps dir**: `__complete` runs without
  `~/.jobhound/config.toml` returning sensible candidates (empty for
  slug/filename completers, full lists for static and enum completers).
- **Performance regression canary** (`pytest -m perf`, opt-in):
  `__complete zsh jh file open ""` returns in <100ms on the test
  author's machine. Not a CI gate; a regression signal.

Install command tests:

- `jh completion bash` prints the bash script content (asserted to
  contain `complete -F _jh_complete jh`).
- `jh completion install --shell zsh --dest <tmpdir>` writes the
  script to `<tmpdir>/_jh` and prints next-steps. Add a `--dest`
  override for testability; otherwise use a fixture that redirects
  `$HOME`.
- `jh completion install` twice in a row leaves the destination
  unchanged on the second run (idempotency).
- `jh completion install` against an existing different file moves it
  to `<path>.bak` before overwrite.

## Quoting test matrix

The "filename with space" case must pass in all three shells. CI is
not going to run interactive shells, so this is a manual smoke test
captured in `docs/commands.md`:

| Shell | Test | Expected |
| --- | --- | --- |
| bash | `jh file open <slug> Job<tab>` | completes to `Job\ Description.md` |
| zsh  | `jh file open <slug> Job<tab>` | completes to `Job\ Description.md` (or quoted, depending on user's `zstyle`) |
| fish | `jh file open <slug> Job<tab>` | completes to `'Job Description.md'` |

## Out of scope

- **Rich completion descriptions.** zsh can show
  `acme-staff-eng   Acme Corp · Staff Engineer · applied` next to
  each candidate. Lovely UX, separate output format. File as
  follow-up.
- **PowerShell.** Different completion model, worth its own design.
- **`jh mcp` argument completion.** The MCP server entry point is
  launched by an MCP client, not typed at a prompt.
- **Caching slug/filename enumeration.** Premature. Measure first;
  filesystem listings on a < 200-opp data root are cheap.
- **Fuzzy / substring slug matching.** Default to canonical-only for
  v1; revisit if users ask.
- **Completion of file-content-derived values** (e.g. tags currently
  applied to an opp). Useful but separate scope.

## Docs to update

- `docs/commands.md` (table of `jh ...` commands) — add
  `jh completion`. Do not document `jh __complete` (internal).
- `README.md` "Installation" section — append a line about
  `jh completion install` for tab-completion.

## Implementation order (input to writing-plans)

1. `_complete.py` module + cyclopts registration with `show=False`.
2. Static completer (walk cyclopts tree).
3. Slug completer.
4. Filename completer.
5. Enum registry + positional and flag completers.
6. bash / zsh / fish shell scripts, each tested against a space-containing filename.
7. `jh completion install` / `jh completion <shell>` commands.
8. Lazy-imports refactor + `hyperfine` measurement; profile if >100ms.
9. Docs updates (`commands.md`, `README.md`).
10. CHANGELOG entry via Conventional Commits `feat:` so release-please
    bumps the minor version.
