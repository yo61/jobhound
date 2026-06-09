# jh Commands Reference

Complete reference of all `jh` CLI commands. For quick help, run `jh --help` or `jh <command> --help`.

## Naming convention

- **Top-level verbs apply to opportunities.** `jh apply`, `jh accept`,
  `jh archive`, `jh new`, `jh list`, `jh show`, etc. all act on the
  opportunity identified by `SLUG_QUERY`. The `set` and `clear`
  groups also stay at the top level because their subcommands name
  opportunity *fields* (`jh set status`, `jh clear applied-on`), not
  separate objects.
- **Everything else is `jh <object> <verb>`.** Operations on child
  collections of an opportunity (files, contacts, notes, tags, links)
  group under the object: `jh file open`, `jh contact add`,
  `jh note remove`, `jh tag list`, `jh link set`.

The rationale and trade-offs are recorded in
[decisions/2026-06-07-cli-verb-object-convention.md](../decisions/2026-06-07-cli-verb-object-convention.md).

## Main Commands

| Command | Description |
| --- | --- |
| `jh accept` | Accept the offer. |
| `jh apply` | Apply to an opportunity. |
| `jh archive` | Archive an opportunity. |
| `jh bump` | Bump last-activity to now. |
| `jh clear` | Clear a nullable field on an opportunity. |
| `jh completion` | Print or install jh shell completion scripts. |
| `jh contact` | Manage contacts on an opportunity. |
| `jh decline` | Decline the offer. |
| `jh delete` | Delete an opportunity permanently. |
| `jh export` | Export all opportunities as JSON. |
| `jh file` | Manage files inside an opportunity. |
| `jh ghost` | Mark an opportunity as ghosted. |
| `jh link` | Manage named links on an opportunity. |
| `jh list` | List opportunities. |
| `jh log` | Log an interaction with an opportunity. |
| `jh mcp` | Run the MCP server over stdio. |
| `jh migrate` | Run one-shot data migrations. |
| `jh new` | Create a new opportunity. |
| `jh note` | Manage notes on an opportunity. |
| `jh set` | Set a single field on an opportunity. |
| `jh show` | Show an opportunity. |
| `jh stats` | Show pipeline stats. |
| `jh tag` | Manage tags on an opportunity. |
| `jh withdraw` | Withdraw from an opportunity. |

## File Sub-Commands

Use `jh file <command> <slug> [args]` to manage opportunity files.

| Command | Description |
| --- | --- |
| `jh file append` | Append content to a file. |
| `jh file delete` | Delete a file. |
| `jh file import` | Import a file from the local filesystem. |
| `jh file list` | List files in an opportunity. |
| `jh file open` | Open a file in your default app. |
| `jh file read` | Print file content to stdout. |
| `jh file write` | Write or replace a file. |

## Contact Sub-Commands

Use `jh contact <command> <slug> [args]` to manage contacts on an opportunity.

| Command | Description |
| --- | --- |
| `jh contact add` | Add a contact to an opportunity. |
| `jh contact list` | List contacts on an opportunity. `--json` emits machine-readable output. |
| `jh contact show` | Show one contact's details. Address by name; disambiguate with `--match-role` / `--match-channel`. |
| `jh contact edit` | Update fields on a contact. Renames via `--new-name` — the contact must be addressed by its new name afterward. |
| `jh contact remove` | Remove a contact from an opportunity. |

## Note Sub-Commands

Use `jh note <command> <slug> [args]` to manage notes on an opportunity.
Each note is a file under `<opp>/notes/<seq>[-<title-slug>].md` with TOML
frontmatter. The sequence number is the stable identifier and never
decrements — deleting a note leaves a permanent gap.

| Command | Description |
| --- | --- |
| `jh note add` | Write a new note. `BODY` is positional; alternatively `--from PATH\|-`. Optional `--title` slugifies into the filename. Returns the assigned seq. |
| `jh note list` | List notes for an opportunity (metadata only). `--reverse` shows newest-first. |
| `jh note show` | Print one note's body. `--with-frontmatter` prints the full file. |
| `jh note edit` | Rewrite a note's body. Uses `--from PATH\|-` or opens `$EDITOR`. `created` and `title` are preserved. |
| `jh note remove` | Delete a note. Permanent — the seq number stays gone. |

## Tag Sub-Commands

Use `jh tag <command> <slug> <name>` to manage tags on an opportunity.

| Command | Description |
| --- | --- |
| `jh tag add` | Add a tag to an opportunity. |
| `jh tag remove` | Remove a tag from an opportunity. |

## Link Sub-Commands

Use `jh link <command> <slug> [args]` to manage named links on an opportunity.

| Command | Description |
| --- | --- |
| `jh link set` | Add or update a named link. |
| `jh link remove` | Remove a named link from an opportunity. |

## Set Sub-Commands

Each `jh set <field>` subcommand has its own signature. See `jh set <field> --help` for details.

| Command | Description |
| --- | --- |
| `jh set applied-on` | Set the application date. |
| `jh set comp-range` | Set compensation range. |
| `jh set company` | Set company name. |
| `jh set first-contact` | Set first contact date. |
| `jh set last-activity` | Set last activity timestamp. |
| `jh set location` | Set job location. |
| `jh set next-action` | Set next action and due date. |
| `jh set priority` | Set priority level (high, medium, low). |
| `jh set role` | Set job role/title. |
| `jh set source` | Set opportunity source. |
| `jh set status` | Set opportunity status. |

## Clear Sub-Commands

Use `jh clear <command> <slug>` to clear nullable fields.

| Command | Description |
| --- | --- |
| `jh clear applied-on` | Clear the application date. |
| `jh clear comp-range` | Clear compensation range. |
| `jh clear first-contact` | Clear first contact date. |
| `jh clear last-activity` | Clear last activity timestamp. |
| `jh clear location` | Clear job location. |
| `jh clear next-action` | Clear next action. |
| `jh clear source` | Clear opportunity source. |

## Completion Sub-Commands

Use `jh completion <command>` to print or install shell completion scripts.

| Command | Description |
| --- | --- |
| `jh completion bash` | Print the bash completion script to stdout. |
| `jh completion fish` | Print the fish completion script to stdout. |
| `jh completion install` | Install the jh completion script for the current shell. |
| `jh completion zsh` | Print the zsh completion script to stdout. |

## Notes Storage Migration (v0.12 upgrade)

Opportunities created before v0.12 had a single `<opp>/notes.md` file.
Starting in v0.12, notes live as per-note files under `<opp>/notes/`
with TOML frontmatter. The first time you run any `jh` command after
upgrading, the CLI auto-migrates any remaining legacy `notes.md` files
(one commit per opportunity in the data repo).

Manual migration (e.g. for dry-run inspection):

```
uv run scripts/migrate_notes_to_directory.py            # dry-run
uv run scripts/migrate_notes_to_directory.py --apply
```

If an opportunity is in an ambiguous half-migrated state (legacy
`notes.md` exists alongside a populated `notes/` directory), the
auto-migration prints a warning and skips that opportunity. Resolve
manually by either restoring the legacy file or merging its content
into the new directory shape.

To restore a legacy `notes.md` after migration:

```
uv run scripts/restore_legacy_notes_md.py SLUG
```

This finds the per-opp `migrate:` commit, looks up its parent, and
writes the pre-migration `notes.md` back. The new `notes/` directory
and `notes_next_seq` counter are NOT undone.

## Global Flags

| Flag | Description |
| --- | --- |
| `-h`, `--help` | Display help message and exit. |
| `--version` | Display application version. |

## Examples

### Create and track an opportunity

```bash
jh new --company Acme --role "Senior Engineer"
jh apply acme
jh log acme --channel email --direction outbound --who "Jane Smith" --body notes.txt
jh show acme
```

### Manage opportunity files

```bash
jh file list acme
jh file write acme research.md --from /path/to/notes.md
jh file open acme research.md
jh file delete acme research.md --yes
```

### Update opportunity fields

```bash
jh set status acme interview
jh set priority acme --to high
jh set next-action acme "Follow up" 2026-05-25
jh tag add acme fintech
jh contact add acme --name "Jane Smith" --role-title recruiter
```

### Export and filter

```bash
jh list                                    # All opportunities
jh export --active-only                   # Active only
jh export --status applied,screen         # Filter by status
jh export --priority high,medium          # Filter by priority
```

### Tab-completion

For shell-specific setup and options, see:

```bash
jh completion --help
jh completion install                      # Auto-detect shell and install
jh completion bash                         # Print bash script
jh completion zsh                          # Print zsh script
jh completion fish                         # Print fish script
```
