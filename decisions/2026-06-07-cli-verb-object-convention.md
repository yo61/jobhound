# Decision: CLI verb/object naming convention

## Decision
Top-level `jh` verbs apply to **opportunities** (the implicit subject
of the CLI). All other operations follow `jh <object> <verb>` —
grouping by object and using the object's own verb vocabulary.

Concretely:

- **Stay as bare top-level verbs (on opportunity):** `accept`,
  `apply`, `archive`, `bump`, `clear`, `decline`, `delete`,
  `export`, `ghost`, `list`, `log`, `new`, `show`, `stats`,
  `unarchive`, `withdraw`. The `set` and `clear` groups also stay
  top-level because their subcommands name opportunity **fields**,
  not separate objects (`jh set status`, `jh clear applied-on`).
- **Move to `jh <object> <verb>`:** every operation on a child
  collection of an opportunity. Contacts, notes, tags, and links
  each become a top-level object group with their own verbs.
  Files (`jh file ...`) already conform.

The migration is a hard rename — no deprecation aliases. Tracked
in a follow-up issue.

## Context
Before this decision, the CLI mixed two grouping styles:

- **Verb-first (action → object):** `jh add {contact|note|tag}`,
  `jh remove {contact|link|tag}`, `jh set {field…}`,
  `jh clear {field…}`.
- **Object-first (object → action):** `jh file {append|delete|...}`.

Issue #45 (originally `jh remove note`) and issue #67 (parity for
missing `list_*` verbs) both raised "what's the naming rule?"
because adding new commands required picking a side and the choice
wasn't written down. Without a rule, every new verb invites the
same debate.

The codebase is implicitly a **per-row API**: every command's first
positional is `SLUG_QUERY` (the opportunity). So opportunity is
the implicit subject of essentially everything. The naming rule
just lifts that implicit subject one level out.

A separate observation forced part of the rule: `link` was sitting
under `jh set link` despite being a **named child collection**, not
a scalar field. The convention disambiguates this cleanly — links
move to `jh link {set|remove|list}` alongside the other child
objects.

## Alternatives considered

**(a) Standardize on pure verb-first (`jh add note`, `jh open
file`, etc.).** Forces collisions with bare verbs — `jh list` is
already opportunity-list, but `jh list files` would compete for
the same prefix. Also scatters the file-op vocabulary
(`append/delete/import/open/read/write`) across the top level,
losing the discoverable `jh file <TAB>` namespace.

**(b) Standardize on pure object-first (`jh opportunity accept`,
`jh opportunity apply`, etc.).** Mechanically consistent with the
gh / gcloud / kubectl style, but wrecks the lightweight
ergonomics. `jh accept` is a dominant high-frequency use case;
making it `jh opportunity accept` is worse for users without
buying anything they would notice.

**(c) Hybrid with a stated rule (chosen).** Top-level for the
implicit subject (opportunity), `<object> <verb>` for everything
else. Preserves ergonomics for the common case, gives discoverable
namespaces for child objects.

## Reasoning
Option (c) was chosen because:

- The CLI is **opportunity-centric by construction** — every
  command takes a slug. Putting opportunity verbs at the top level
  reflects that mental model directly.
- Child objects (`contact`, `note`, `tag`, `link`, `file`) each
  have a non-trivial verb vocabulary (at minimum `add`/`list`/`remove`,
  and `file` has seven). Grouping by object means
  `jh contact <TAB>` is self-documenting and scales as new verbs
  appear.
- The current `jh set` / `jh clear` families are genuinely
  top-level opportunity verbs parameterised by field name — they
  don't belong in either object group. The rule explicitly keeps
  them there rather than forcing a fake `jh field set` shape.

## Trade-offs accepted

- **Breaking change.** All `jh add`, `jh remove`, and `jh set link`
  call sites need updating. CLI users with shell aliases or
  scripts will see breakage on the next minor. Per
  "Replace, don't deprecate" — no compatibility aliases.
- **Asymmetry between CLI and MCP surfaces.** MCP tool names
  (`add_contact`, `set_link`, …) are currently verb-first
  snake_case. Whether to mirror the CLI rename on the MCP surface
  is a separate decision, deferred.
- **`set`/`clear` stay as verb-grouped exceptions.** A purist
  reading of the rule would object that field setters look
  inconsistent with child-object groups. The justification is that
  fields are not objects — they're aspects of the opportunity, not
  related entities. `jh set company "Acme"` and
  `jh contact add --name Jane` are different shapes of operation,
  and conflating them costs more than the surface inconsistency.

## Supersedes
None. This codifies a naming rule that previously existed only as
implicit habit, with `jh file` already conforming and the rest of
the surface accumulated verb-first.

## Outcome
- This file documents the rule.
- `docs/commands.md` gains a "Naming convention" section pointing
  back here.
- Issue #45 retitled to use the new shape (`jh note remove`).
- A new tracking issue covers the CLI migration sweep and the
  verb-coverage matrix per object.
- Issue #67 (list-parity) annotated to note the convention is now
  codified; its planned `jh <domain> list <slug>` shape already
  conforms.
- MCP-surface naming alignment is left as a separate, pending
  decision.
