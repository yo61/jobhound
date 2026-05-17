# jh Commands Reference

Complete reference of all `jh` CLI commands. For quick help, run `jh --help` or `jh <command> --help`.

## Main Commands

| Command | Description |
| --- | --- |
| `jh accept` | Accept the offer. |
| `jh add` | Add a tag, contact, or note to an opportunity. |
| `jh apply` | Apply to an opportunity. |
| `jh archive` | Archive an opportunity. |
| `jh bump` | Bump last-activity to now. |
| `jh clear` | Clear a nullable field on an opportunity. |
| `jh completion` | Print or install jh shell completion scripts. |
| `jh decline` | Decline the offer. |
| `jh delete` | Delete an opportunity permanently. |
| `jh export` | Export all opportunities as JSON. |
| `jh file` | Manage files inside an opportunity. |
| `jh ghost` | Mark an opportunity as ghosted. |
| `jh list` | List opportunities. |
| `jh log` | Log an interaction with an opportunity. |
| `jh mcp` | Run the MCP server over stdio. |
| `jh migrate` | Run one-shot data migrations. |
| `jh new` | Create a new opportunity. |
| `jh remove` | Remove a tag, contact, or link from an opportunity. |
| `jh set` | Set a single field on an opportunity. |
| `jh show` | Show an opportunity. |
| `jh stats` | Show pipeline stats. |
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

## Add Sub-Commands

Use `jh add <command> <slug> [args]` to add contacts, tags, or notes.

| Command | Description |
| --- | --- |
| `jh add contact` | Add a contact to an opportunity. |
| `jh add note` | Add a timestamped note to an opportunity. |
| `jh add tag` | Add a tag to an opportunity. |

## Set Sub-Commands

Each `jh set <field>` subcommand has its own signature. See `jh set <field> --help` for details.

| Command | Description |
| --- | --- |
| `jh set applied-on` | Set the application date. |
| `jh set comp-range` | Set compensation range. |
| `jh set company` | Set company name. |
| `jh set first-contact` | Set first contact date. |
| `jh set last-activity` | Set last activity timestamp. |
| `jh set link` | Add or update a named link. |
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

## Remove Sub-Commands

Use `jh remove <command> <slug> [args]` to remove contacts, links, or tags.

| Command | Description |
| --- | --- |
| `jh remove contact` | Remove a contact from an opportunity. |
| `jh remove link` | Remove a named link from an opportunity. |
| `jh remove tag` | Remove a tag from an opportunity. |

## Completion Sub-Commands

Use `jh completion <command>` to print or install shell completion scripts.

| Command | Description |
| --- | --- |
| `jh completion bash` | Print the bash completion script to stdout. |
| `jh completion fish` | Print the fish completion script to stdout. |
| `jh completion install` | Install the jh completion script for the current shell. |
| `jh completion zsh` | Print the zsh completion script to stdout. |

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
jh add tag acme fintech
jh add contact acme --name "Jane Smith" --role-title recruiter
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
