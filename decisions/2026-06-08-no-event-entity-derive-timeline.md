# Decision: Defer first-class Event entity; derive jh timeline view

## Decision
Don't introduce an `Event` domain entity. Instead, ship a derived
`jh timeline <slug>` (and matching MCP tool) that computes a
chronological view at read time from the three existing data
streams:

- `notes/*.md` (per-note files after the notes-storage-model
  migration — see
  [2026-06-08-notes-storage-model.md](2026-06-08-notes-storage-model.md))
- `correspondence/*.md` (per-interaction files written by
  `jh log`)
- meta.toml field changes (current scalar timestamp fields
  directly; git history replay for full transition history if
  later needed)

Each stream's entries get tagged with their type (`note`,
`correspondence`, `status_change`, `field_change`) and merged on
timestamp.

## Context
Issue #67 raised that "things that happened on an opportunity"
lived in three disconnected places (notes, correspondence files,
scalar timestamp fields on Opportunity). A user-facing want
emerged: "see what happened on this opportunity, in order."

Two structural options:

- Add `Event` as a first-class entity (new persistence, new
  domain methods, new MCP tools, new tests, new migration).
- Treat "events" as a *view* derived from data that already
  exists in durable form.

The notes-storage-model decision (sibling decision filed the same
day) turned the notes stream into a structured directory of
per-note files — the same shape `correspondence/` already has.
That makes deriving the view materially cheaper than it was when
notes were a freeform markdown blob.

## Alternatives considered

**(a) Add `Event` as a first-class entity.** Append-only event
log per opportunity (TOML, JSONL, or SQLite). Every state
transition, field change, note, correspondence, etc. writes an
event. Pros: structured queries, attributes attached to events
(categorization, sentiment, follow-ups). Cons: new domain layer,
new persistence, new migration, sync problem (what if someone
edits a note file by hand?).

**(b) Derive the timeline view at read time (chosen).** Iterate
the three existing streams, merge on timestamp, render. No new
storage, no sync problem, no migration.

## Reasoning
Option (b) was chosen because:

- The user-facing want is a **view**, not a new storage shape.
  Views are cheap; entities are expensive.
- The data already exists in three durable, structured streams
  (after the sibling notes-storage decision). Adding a fourth
  derived-from-these stream creates a sync problem.
- The codebase is small; the audience is one person doing a
  personal job hunt. Recomputing on every call costs microseconds
  on tens of opportunities × tens to hundreds of events each.
- "Don't add features users don't actively need." The user
  hasn't asked for status-change journaling, follow-up reminders
  attached to past events, or sentiment categorization — just
  "see what happened in order." That's a render.

## Trade-offs accepted

- **Recomputed on every call.** No pre-indexed event store.
  Becomes a problem only at a scale this app won't see (thousands
  of opps × thousands of events).
- **No event-level attributes beyond what the source streams
  carry.** If a future requirement needs categorization, manual
  follow-up reminders attached to past events, or other
  attributes that can't be derived from notes / correspondence /
  meta, `Event` may need to become a real entity then.
- **meta.toml field-change derivation requires git history
  replay.** For the initial `jh timeline` view, defer this:
  surface just notes + correspondence + current scalar field
  timestamps (`first_contact`, `applied_on`, `last_activity`,
  `next_action_due`). Full transition history can be added later
  if useful by walking the data repo's git log.

## Supersedes
None directly. Resolves the "Event entity" question parked in
#67 (closed) and explicitly out-of-scope of #101.

## Outcome
- This file records the decision.
- New issue files the `jh timeline` view (depends on the
  notes-storage-model migration landing first, so the notes
  stream is enumerable as files).
- #101's Out-of-scope section updated to point at this decision
  rather than leaving the Event question parked indefinitely.
