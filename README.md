# jobhound

Action-based CLI for tracking a personal job hunt. Status changes are a
consequence of recorded events (`apply`, `log`, `withdraw`, …), not direct
field edits.

## Install

```bash
uv tool install jobhound   # or: pipx install jobhound
```

Exposes the `jh` command.

## Usage

```bash
jh new --company Acme --role "Senior Engineer"
jh apply acme
jh log acme --channel email --direction to --who recruiter \
            --body draft.md --next-status screen
jh note acme --msg "Recruiter mentioned a hybrid setup"
jh withdraw acme
jh list
jh show acme                # human-readable detail; --json for the envelope
jh export --active-only     # bulk JSON envelope to stdout
```

Each command is a verb on a single opportunity. Run `jh --help` for the
full set: `new`, `apply`, `log`, `withdraw`, `ghost`, `accept`, `decline`,
`note`, `priority`, `tag`, `link`, `contact`, `list`, `edit`, `archive`,
`delete`, `sync`, `show`, `export`.

`jh export` filters: `--status` and `--priority` (comma-separated or
repeatable), `--slug` (substring), `--active-only`, `--include-archived`.

## Storage

Per-opportunity data is stored under `$XDG_DATA_HOME/jh/` (defaults to
`~/.local/share/jh/`) as a TOML file plus markdown notes and
correspondence. The data root is a git repo with auto-commits on every
state change — your history is auditable and you can push it anywhere.

## Status

Pre-1.0. The CLI surface is stable; semantic-versioned releases via
Conventional Commits.
