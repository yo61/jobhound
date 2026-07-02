# jobhound

Action-based CLI for tracking a personal job hunt. Status changes are a
consequence of recorded events (`apply`, `log`, `withdraw`, …), not direct
field edits.

## Install

```bash
uv tool install jobhound   # or: pipx install jobhound
```

Exposes the `jh` command.

For tab-completion, run:

```bash
jh completion install
```

See `jh completion --help` for per-shell options.

## Usage

```bash
jh new --company Acme --role "Senior Engineer"
jh apply acme
jh log acme --channel email --direction to --who recruiter \
            --body draft.md --next-status screen
jh note add acme "Recruiter mentioned a hybrid setup"
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

### Adding a job from a URL

Create an opportunity by scraping a job posting instead of typing the
details:

```bash
jh new --url https://www.linkedin.com/jobs/view/4383908452
```

jobhound extracts the company, role, location, and description, stores the
posting as a `posting` link, and saves the full text as
`job-description.md`. Extraction runs locally with no LLM: LinkedIn is read
from its page metadata, and other job sites are read from the schema.org
`JobPosting` data most publish for Google Jobs. Tracking parameters in the
URL are ignored — deduplication keys on the posting's canonical URL, so the
same job added twice is rejected.

Most postings are fetched without logging in. For a posting behind a login,
let jobhound reuse the session from your browser — grant permission once:

```bash
jh config set allow-browser-cookie-access true
```

jobhound then reads the cookies for that site from your default browser
(configurable with `jh config set cookie-browser <name>` and
`cookie-browser-profile`) and replays them to fetch the posting. Cookies are
read only for the target site, used for that fetch, and never stored.

### Managing opportunity files

`jh file` provides uniform access to files inside an opportunity (CVs,
research notes, correspondence, etc.). Available subcommands:

- `jh file list <slug>` — list files
- `jh file show <slug> <name>` — print to stdout; use `--out <path>` to export
- `jh file write <slug> <name> --content <str>` (or `--from <path>`)
- `jh file append <slug> <name> --content <str>` (or `--from <path>`)
- `jh file delete <slug> <name> --yes`

Pass `--base-revision <r>` (the revision string from a prior `jh file show`
or `jh file write`) to enable optimistic-concurrency conflict detection.
For text files, a 3-way merge is attempted automatically; binary conflicts
surface the current file's metadata and suggest an alternate name.

## Storage

Per-opportunity data is stored under `$XDG_DATA_HOME/jh/` (defaults to
`~/.local/share/jh/`) as a TOML file plus markdown notes and
correspondence. The data root is a git repo with auto-commits on every
state change — your history is auditable and you can push it anywhere.

## AI integration (MCP)

`jh` ships a Model Context Protocol server so AI clients (Claude
Desktop, Claude Code, Continue, Zed, …) can read and modify your job
hunt directly. The MCP tools cover read operations (list, show, stats,
files, file content), creating an opportunity from a job-posting URL
(`create_from_url`, plus `browser_status` for authenticated scraping),
state transitions (apply, log, withdraw, ghost, accept, decline), field
setters, relation operations (tags, contacts, links), opportunity ops
(notes, archive, delete), and a uniform file API (read, write, import,
export, append, delete) with optimistic-concurrency conflict detection
and 3-way merge for text files.

Install the optional extra:

```bash
uv tool install 'jobhound[mcp]'
```

Then point your MCP client at the server. For Claude Desktop, add to
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jobhound": {
      "command": "jh",
      "args": ["mcp"]
    }
  }
}
```

For zero-install discovery (no `uv tool install` needed):

```json
{
  "mcpServers": {
    "jobhound": {
      "command": "uvx",
      "args": ["--from", "jobhound[mcp]", "jh-mcp"]
    }
  }
}
```

The same pattern works for Claude Code (`.mcp.json`), Continue, Zed,
and any other MCP-spec-compliant client.

By default the AI gets full CLI parity — including writes. Most MCP
clients show each tool call to the user before executing it; that's
the consent layer. The one tool that requires explicit
double-confirmation is `delete_opportunity`, which needs `confirm=true`
in the call args (otherwise it returns a preview only, no side
effects).

## Status

Pre-1.0. The CLI surface is stable; semantic-versioned releases via
Conventional Commits.
