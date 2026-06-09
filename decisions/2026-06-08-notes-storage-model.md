# Decision: Per-item file storage for append-only streams

## Decision

Append-only data streams on an opportunity (today: notes and
correspondence) move to a directory of **per-item files**, with
**Unix-timestamp filenames** (optionally suffixed with a title
slug for filesystem-backend browsability) and **TOML frontmatter**
as the source of truth for per-item metadata.

Concrete shape per item:

- Path on the filesystem backend:
  `<opp>/<stream>/<unix_ts>.md` or
  `<opp>/<stream>/<unix_ts>-<title-slug>.md` (the slug is
  optional, supplied via `--title` at write time).
- File contents start with TOML frontmatter, then bare markdown
  body:

```
+++
created = 2026-06-08T14:23:05Z
title = "Charlotte Eyre background"
+++

Body markdown — bullets, paragraphs, code, whatever.
```

The frontmatter contains at minimum `created` (TOML datetime).
Optional and stream-specific fields (`title`, `channel`,
`direction`, `who`, …) populate as load-bearing needs emerge.

The rule applies to both notes and correspondence. Notes
implementation lands first (#102); correspondence follows in a
separate, deferred migration.

## Context

`notes.md` was an append-only single file. `jh add note` appended
`- <ISO-Z-timestamp> <msg>\n` (`ops_service.py:37`); users and
assistants also wrote freeform markdown (H2 day headers,
multi-paragraph prose) directly into the same file.

Real corpus (6 files total):

- 2 essentially empty (template stub, archived opp).
- 2 canonical bullet-style (Menlo files — 38 bullets between
  them).
- 2 pure prose with H2 day headers and no bullets at all
  (Tailscale, UKHSA).

The mixed shape made CRUD on individual notes awkward and
ultimately drove the move to per-item files.

A subsequent design pass surfaced a constraint not in the
original framing: the data model should not embed
filesystem-specific addressing conventions, because backend
portability (SQLite, HTTP API, KV store) is a possible future
direction. Two implications:

- **Identity must look like a primary key, not a path.** Whatever
  the filesystem uses as filename should slot cleanly into any
  future backend as an integer ID, JSON field, or row key.
- **Data must be self-describing.** A note's creation timestamp
  can't live only in its filename — that's a filesystem
  convention. The truth has to be in the data so any backend can
  carry it without parsing a path.

This reframes the choice of filename and metadata: pure ISO
filenames look like paths and bind to filesystem layout; pure
Unix timestamps look like IDs and survive backend migration.
Bare markdown bodies lose metadata when divorced from filenames;
TOML frontmatter keeps metadata with the data.

## Alternatives considered

**(a) Keep `notes.md`, write a parser (lenient grammar — bullet
lines are notes, prose is context).** The original Q1 of #101.
Works but requires a parser, an addressing scheme decision, and
never makes the prose addressable.

**(b) Keep `notes.md`, enforce strict structure (only bullet
lines allowed).** Hostile to how users and assistants actually
use the file today. Forces a parser anyway.

**(c) Per-item files with ISO-timestamp filenames + bare-markdown
bodies (earlier draft of this decision).** CRUD becomes trivial,
filesystem symmetry with `correspondence/` is preserved. But
binds metadata to filesystem-specific conventions — a future
backend migration would have to re-write all data.

**(d) Per-item files with opaque IDs + self-describing metadata
(chosen).** Filename is just an addressable key; metadata lives
in the data. Backend-portable: works as-is in SQL (integer
primary key), JSON APIs, KV stores, and the current filesystem.

## Reasoning

Option (d) was chosen because:

- **Backend portability is preserved.** Unix-timestamp IDs slot
  into any backend as integers. TOML frontmatter is parseable in
  any environment. Migrating storage in the future is a backend
  swap, not a data re-encoding.
- **CRUD becomes trivial.** Every note is a file (today); every
  operation on a note is a file operation. No parser for the
  body, no addressing scheme. Update (previously n/a in the
  single-file model) becomes a meaningful verb.
- **TOML matches the project's existing convention.** Already
  the format for `meta.toml`. Native datetime support means
  `created = 2026-06-08T14:23:05Z` is a typed value, not a
  string consumers must parse.
- **Git audit trail per item.** Each `note add`, `note edit`,
  `note remove` is its own commit. Cleaner than line-level diffs
  against a single file.
- **No speculative metadata schema.** Frontmatter starts with
  just `created` (mandatory) and `title` (optional). Other
  fields appear only when something needs them.

## Trade-offs accepted

- **Migration cost.** Existing `notes.md` files need a one-shot
  migration. Mixed structure makes the migration non-trivial.
  Algorithm below.
- **Filename readability regresses.** `ls notes/` shows
  Unix-timestamp filenames (e.g. `1812345785.md`) rather than
  ISO dates. The optional `--title` slug suffix offsets this for
  FS-backend DX (`1812345785-charlotte-prep.md`); raw
  ordered-by-time browsing is still available via `ls -t`.
- **Two layers of `created` timestamp.** Both filename and
  frontmatter carry the creation time. Filename is a backend
  affordance; frontmatter is the source of truth. If they ever
  disagree (corruption, hand-editing the filename), prefer
  frontmatter.
- **Filesystem symmetry with `correspondence/` breaks until the
  correspondence migration lands.** Notes adopt the new shape
  immediately; correspondence keeps its semantic filenames
  (`YYYY-MM-DD-channel-direction-who.md`) until its own
  migration. Known asymmetry, intentional sequencing.
- **No backwards compatibility.** Per "Replace, don't deprecate"
  — hard cut. The migration script runs once; old `notes.md` is
  gone afterward.

## Migration algorithm

Scan each `notes.md` top to bottom. A line is a **date marker**
if it matches either:

- `^## YYYY-MM-DD( — .*)?$` (H2 day header, optional suffix)
- `^- YYYY-MM-DDTHH:MM:SSZ .*` (timestamped bullet from
  `jh add note`)

Each date marker starts a new note. The marker's ISO timestamp
becomes the note's `created` (H2 markers synthesize
`T00:00:00Z`). The Unix-timestamp form of that ISO time becomes
the filename: `notes/<unix_ts>.md`.

Body shape after migration:

```
+++
created = <original ISO timestamp>
+++

<body content>
```

Body content:

- **Bullet markers:** strip the `- <ISO-timestamp> ` prefix; the
  body is just the message text.
- **H2 markers:** strip the `## <date>[ — suffix]` header line;
  the body is everything below it up to (but not including) the
  next marker.

**One note per bullet** (not day-bundled).

**Edge cases:**

- **Pre-first-marker preamble** (e.g. `# Menlo Security Inc. —
  Running Notes`): discard. All observed preamble is a redundant
  title line.
- **Empty placeholder notes** (body after stripping = whitespace
  only): skip.
- **Filename collisions** (two markers in the same Unix second):
  integer suffix `-2`, `-3`, … on the filename. Frontmatter
  `created` remains the original ISO timestamp; the suffix is a
  pure filesystem disambiguator.
- **H2 date differing from bullet timestamps under it** (Menlo
  EM file): both still count as markers. The H2 becomes its own
  (likely empty → skipped) note; each bullet becomes its own
  note.
- **Date-like strings in body content**: not markers. Only
  line-anchored `^## …` and `^- <ISO-Z-timestamp> …` count.
- **Empty / template files**: skip entirely. The template stub
  replaces `notes.md` with an empty `notes/` directory.

**Migration script shape:** mirrors `scripts/migrate_from_yaml.py`
— dry-run-by-default; prints the planned per-file output;
applies on `--apply`; one bulk commit per opportunity in the
data repo.

## Correspondence: same rule, deferred

Correspondence currently uses semantic filenames
(`YYYY-MM-DD-channel-direction-who.md`) and a separate file per
interaction with bare-markdown bodies. The same per-item-file
rule applies — `correspondence/<unix_ts>.md` with TOML
frontmatter carrying `created`, `channel`, `direction`, `who`,
and optionally `title`.

Migration is **out of scope for #102** because:

- Correspondence is a smaller, less-active stream than notes.
- Bundling both migrations widens the blast radius of one PR.
- Notes is the immediate gating need (it blocks #101's CRUD
  coverage); correspondence's current shape blocks nothing.

Tracked separately as a follow-up issue.

## Supersedes

None directly. Dissolves the original Q1 of #101 ("notes parser
grammar + addressing scheme") — the question no longer applies
because the filesystem is just one possible backend, and item
identity lives in the data.

## Outcome

- This file records the decision and the rule that covers both
  streams.
- Notes implementation tracked in #102 (filename, frontmatter,
  migration script, call-site updates, CRUD verbs).
- Correspondence migration tracked separately as a deferred
  follow-up issue.
- #101's `note` row in the CRUD matrix reflects the new model:
  `note add` (write file), `note list` (enumerate dir),
  `note show` (read file), `note remove` (delete file),
  `note edit` (now a real verb).
- `jh timeline` (#103) reads `created` from TOML frontmatter
  rather than parsing filenames — robust to future field
  additions and to backend swaps.
- Open design question 1 in #101 is dissolved.

## Revision (2026-06-08)

Filename shape changed from Unix-timestamp (`<unix_ts>.md`) to
**per-opportunity monotonic sequence** (`<seq>.md` or
`<seq>-<title>.md`). The sequence counter lives in `meta.toml` as
`notes_next_seq` and never decrements — deleting the highest-numbered
note leaves a permanent gap, so note IDs are stable for the life of
the opportunity.

Reasoning:

- The decision's intent — "identity must look like a primary key, not
  a path" — is satisfied more directly by a monotonic integer than by
  a Unix timestamp.
- Backend portability is preserved (sequence integer maps cleanly to
  SQL primary keys, JSON IDs, KV row keys).
- User-facing IDs are stable across deletes; `note 3` always refers
  to the same note that was created third.
- Migration assigns seq 1..N to existing notes in chronological order
  by `created`.

Supersedes the "Concrete shape per item" path in the original
decision (`<opp>/<stream>/<unix_ts>.md`). Frontmatter shape unchanged.

Open: correspondence (#105) will reuse the same monotonic-sequence
rule when that migration lands. The shared frontmatter helper
(`application/frontmatter.py`) is built generic enough to support it.
