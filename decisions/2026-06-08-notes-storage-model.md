# Decision: Move notes from notes.md to notes/ directory

## Decision
Replace the single per-opportunity `notes.md` file with a per-note
file under a `notes/` directory, mirroring the existing
`correspondence/` pattern. Each note becomes its own markdown file
named by an ISO-8601-derived timestamp.

Concrete shape:

- Path: `<opp>/notes/<YYYY-MM-DDTHH-MM-SSZ>.md` (colons replaced
  with dashes in the time portion for filesystem portability).
- Optional `--title <slug>` flag on `jh note add` produces
  `<timestamp>-<title-slug>.md` for human-readable names.
- Body: bare markdown. No frontmatter. Timestamp comes from the
  filename; nothing else is currently load-bearing.
- One note per file. Symmetry with correspondence: one file per
  interaction.

`jh note add SLUG "msg"` writes the file with `"msg"` as the body
and bumps `last_activity` on the opportunity (same semantics as
`ops_service.add_note` today, different storage). Longer notes
via `--from <path>` or `--from -` (stdin), matching
`jh file write`'s shape.

## Context
`notes.md` was an append-only single file. `jh add note` appended
`- <ISO-Z-timestamp> <msg>\n` (`ops_service.py:37`); users and
assistants also wrote freeform markdown (H2 day headers,
multi-paragraph prose) directly into the same file.

The real corpus (6 files total):

- 2 are essentially empty (template stub, archived opp).
- 2 are canonical bullet-style (Menlo files — 38 bullets between
  them).
- 2 are pure prose with H2 day headers and no bullets at all
  (Tailscale, UKHSA).

The mixed shape made CRUD on individual notes awkward: addressing
required either a parser (timestamp prefix? substring? line
index?) or accepting that "notes" were only the bullet lines,
with prose forever unaddressable.

The CRUD coverage work in #101 forced the question: can we make
`note list`, `note show`, `note remove`, `note edit` trivial?

## Alternatives considered

**(a) Keep notes.md, write a parser (lenient grammar — bullet
lines are notes, prose is context).** The original Q1 of #101.
Works but requires a parser, an addressing scheme decision, and
never makes the prose addressable.

**(b) Keep notes.md, enforce strict structure (only bullet lines
allowed).** Hostile to how users and assistants actually use the
file today. Forces a parser anyway.

**(c) One file per note under `notes/` (chosen).** Filesystem is
the parser. Each note has a stable identity (its path). CRUD
operations become file operations. Symmetric with
`correspondence/`. Enables a cheap derived timeline view across
parallel structured streams.

## Reasoning
Option (c) was chosen because:

- **CRUD becomes trivial.** Every note is a file; every operation
  on a note is a file operation. No parser, no addressing scheme
  to design. Update (previously n/a) becomes a meaningful verb —
  edit a file.
- **Git audit trail per note.** Each `note add`, `note edit`,
  `note remove` becomes its own commit (alongside the existing
  `last_activity` bump commit, matching the current
  two-commit-per-note pattern in `ops_service.add_note`).
- **Symmetric with correspondence.** Already-established mental
  model: one file per chronological event. Timeline derivation
  becomes "iterate notes/ + correspondence/ + meta.toml
  transitions" — three structured streams.
- **No speculative structure.** Bare markdown body, no
  frontmatter, no schemas. Add structure only when an attribute
  becomes load-bearing.

## Trade-offs accepted

- **Migration cost.** Existing `notes.md` files need a one-shot
  migration. Mixed structure makes the migration non-trivial;
  algorithm below.
- **More files in the data repo.** Per-opportunity directory
  gains a `notes/` directory with N files instead of one
  `notes.md`. Negligible at this scale.
- **Lost ability to scroll one file for chronological review.**
  Users who previously ran `cat notes.md` get a `ls notes/` +
  per-file read flow. `jh note list` and the deferred
  `jh timeline` cover this; raw filesystem access remains
  available (`cat notes/*.md`).
- **No backwards compatibility.** Per "Replace, don't deprecate"
  — hard cut. The migration script runs once; old `notes.md` is
  gone afterward.

## Migration algorithm

Scan each `notes.md` top to bottom. A line is a **date marker**
if it matches either:

- `^## YYYY-MM-DD( — .*)?$` (H2 day header, optional suffix)
- `^- YYYY-MM-DDTHH:MM:SSZ .*` (timestamped bullet from
  `jh add note`)

Each date marker starts a new note. The note's body is the marker
line itself plus every following line up to (but not including)
the next date marker. The note's timestamp is the date from the
marker — H2 markers synthesize `T00:00:00Z`; bullets keep their
full timestamp. Filename uses the dash-separated time form
(`YYYY-MM-DDTHH-MM-SSZ.md`).

**One note per bullet** (not day-bundled): each `jh add note`
invocation's text was a discrete write; the migration preserves
that discrete identity.

**Edge cases:**

- **Pre-first-marker preamble** (e.g. `# Menlo Security Inc. —
  Running Notes`): discard. All observed preamble is a redundant
  title line.
- **Empty placeholder notes** (body = marker line only, no real
  content following): skip. These are leftover scaffolding
  headers from the legacy format.
- **Filename collisions** (two markers in the same second, or two
  H2 headers with the same date): suffix with a counter
  (`-2.md`, `-3.md`, …).
- **H2 date differing from bullet timestamps under it** (Menlo
  EM file): both still count as markers. The H2 becomes its own
  (likely empty → skipped) note; each bullet becomes its own
  note. The "mismatch" is what we want — each bullet is when the
  actual event happened.
- **Date-like strings in body content**: not markers. Only
  line-anchored `^## …` and `^- <ISO-Z-timestamp> …` count.
- **Empty / template files**: skip entirely. The template stub
  gets a different update (replace `notes.md` with an empty
  `notes/` directory).

**Migration script shape:** mirrors `scripts/migrate_from_yaml.py`
— dry-run-by-default; prints the planned per-file output; applies
on `--apply`; one bulk commit per opportunity in the data repo.

## Supersedes
None directly. Dissolves the original open design question 1 in
#101 ("notes parser grammar + addressing scheme") — the question
no longer applies because the filesystem is the parser.

## Outcome
- This file records the decision.
- New issue files the migration script and call-site updates
  (`ops_service.add_note`, MCP `add_note`, file-store writes,
  template, tests).
- #101's `note` row in the CRUD matrix updates:
  `note add` (write file), `note list` (enumerate dir),
  `note show` (read file), `note remove` (delete file),
  `note edit` (now a real verb — was n/a).
- Open design question 1 in #101 is dissolved.
- Future `jh timeline` (separate decision and issue) iterates
  `notes/` and `correspondence/` as parallel structured streams.
