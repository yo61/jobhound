# UTC Timestamps Migration — Design Spec

Date: 2026-05-15
Status: Shipped in v0.7.0 (PR #24, PR #26)
Branch: `feat/utc-timestamps-design`
Task: #35

**Revision 2026-05-16:** Decisions 5 and 8 amended after live migration testing —
bare dates now convert as **noon-local** (not midnight-local) to keep the
calendar date visually intact in the stored UTC string and to stay clear of
DST transition windows. See "Bare date case" under decision 5 and decision 8
for details.

## Goal

Replace every `date`-typed value in the persisted model and surrounding API
with a tz-aware `datetime` stored as UTC, while continuing to display whole
seconds in the user's local timezone at every human-facing edge. After this
lands:

- `meta.toml` stores `applied_on`, `first_contact`, `last_activity`, and
  `next_action_due` as ISO 8601 offset date-times in UTC with microsecond
  precision.
- The domain `Opportunity` aggregate carries `datetime | None` on those four
  fields, never `date | None`.
- Every service method, MCP tool, and CLI flag that previously took
  `today: date` takes `now: datetime` instead — the name change is
  deliberate so the type change is unmissable at every call site.
- Bare dates accepted on the CLI are interpreted as noon in the user's
  local TZ, then normalised to UTC; full ISO 8601 timestamps with offsets
  are accepted verbatim. (Noon, not midnight, so the stored UTC value
  retains the user's calendar date in raw form and stays clear of DST
  transition windows.)
- `is_stale` / `looks_ghosted` thresholds compare *calendar days in the
  user's local TZ*, not raw UTC subtraction — so "14 days stale" matches a
  human's intuition regardless of when in the day the last activity was
  recorded.

Phase 4 (MCP) clients already speak ISO 8601 with Z-suffix offsets for
`FileEntry.mtime`; that contract gets extended to the lifecycle fields too.

## Strategic direction

### Why this exists

The current model loses information at every write.

- `last_activity = 2026-05-14` says *something happened on that calendar
  day in some timezone*. Two interactions on the same day collapse into one
  bare date. The "ghosted in 21 days" rule depends on which timezone "the
  calendar day" was computed in — undefined and incidental today.
- `applied_on = 2026-05-14` for someone who applied at 23:55 local on
  2026-05-13 (UTC: 2026-05-14T05:55Z) records the wrong day relative to a
  later "I haven't heard back in N days" computation.
- `notes.md` already records interactions but with no timestamp at all —
  the chronological ordering is implicit from line order. There is no way
  to ask "how long between my recruiter reply and my next message?".

The user's preference, captured in their memory `feedback_timestamps_utc_local`,
is unambiguous: store tz-aware UTC, convert to local at the display edge.
This spec implements that preference end-to-end and adds the small amount
of machinery needed to display and compare correctly.

This is a foundational change for any future feature that benefits from
precise time semantics: SLAs, time-since-interaction analytics, calendar
integrations, ghost detection that crosses DST boundaries, and the
deferred ICS export from Phase 3b.

### Why now

Three reasons converge:

1. Task #43 (`no_commit` removal) shipped on 2026-05-15. Every state-changing
   API call now commits — meaning each commit timestamp is the implicit
   "what time did this transition happen at" record. That implicit timestamp
   should match what we explicitly store. Moving to tz-aware UTC now keeps
   the explicit and implicit records in lockstep.
2. The MCP surface (Phase 4) shipped a Z-suffix datetime convention for
   `FileEntry.mtime` and envelope timestamps. Continuing to mix bare dates
   into the JSON envelope alongside ISO datetimes is inconsistent and
   confuses agent-side type inference.
3. The data set is still small — seven opportunities, ~150 meta.toml
   writes total in git history. Migrating now is a one-shot script;
   migrating later is the same script plus user retraining.

### Scope

**In scope:**

- Type change `date | None` → `datetime | None` on the four lifecycle
  fields in `domain/opportunities.py`.
- Renaming the `today: date` keyword parameter to `now: datetime`
  everywhere it appears — domain methods, application services, the
  read-side query, MCP tools, and CLI flags. This is exhaustive; PICKUP's
  surface inventory lists ~30 call sites and they all change.
- A new `domain/timekeeping.py` module that owns:
  - `to_utc(value)` — naive datetime → local TZ → UTC; aware datetime →
    `.astimezone(UTC)`; passthrough for already-UTC values.
  - `calendar_days_between(then_utc, now_utc)` — counts local-TZ midnight
    boundaries crossed; the new arithmetic primitive for stale/ghosted.
  - `display_local(value, *, precision="seconds")` — UTC → local TZ,
    truncated to whole seconds.
- Migration script `scripts/migrate_dates_to_datetimes.py` that walks every
  `meta.toml` in the data root, converts bare-date fields to
  noon-local-TZ→UTC, writes back, and commits with a single
  `chore(migration): UTC datetime conversion` commit.
- A new dependency: `tzlocal >= 5.0` (pure Python, ~10 KB).
- Schema bump: `serialization.py:SCHEMA_VERSION` 1 → 2. The JSON envelope
  shape doesn't change in topology, only in the values of the four
  lifecycle fields (now Z-suffix datetimes instead of bare YYYY-MM-DD).
- Test fixture migration: every `today=date(2026, 5, 14)` in the test
  suite becomes a `now=datetime(2026, 5, 14, 13, 0, tzinfo=UTC)` (or
  similar pinned UTC instant). Expect ~30–50 test functions touched.

**Out of scope:**

- Renaming `Slug.build`'s prefix away from `YYYY-MM-DD`. Slugs are
  human-readable filesystem identifiers; a microsecond timestamp in a slug
  is hostile. `Slug.build` accepts `now: datetime` but internally derives
  the date prefix via `now.astimezone(local_tz).date()`. The slug string
  format stays date-only.
- Correspondence filenames (`<YYYY-MM-DD>-<channel>-<direction>-<who>.md`).
  Same reasoning as slugs — filesystems and humans prefer date-stamped
  filenames. Precise time for each interaction lives in the corresponding
  `last_activity` write in `meta.toml`.
- Rewriting historical `notes.md` lines. The format changes going forward
  only — new lines get `- YYYY-MM-DDTHH:MM:SSZ msg`; existing lines stay
  as written.
- Per-field timezone storage. Every stored datetime is UTC. The local TZ
  is determined at the read/write edge from `tzlocal.get_localzone()`.
- `OpportunityRepository`-as-port refactor. Same Protocol pattern as
  `FileStore` would let us add a non-FS storage backend; orthogonal to
  this work.
- DST-aware migration of past `applied_on = 2025-03-08` (i.e. dates that
  cross historical DST boundaries). Migration uses the *current* local
  zone offset for every conversion — accepting that one-time noise of a
  few hours either way for pre-DST-transition entries. Acceptable for
  the seven-opportunities-as-of-2026-05-15 data set; documented as a
  known limitation in `CHANGELOG.md`.

## Design decisions

Each subsection consolidates one of the eight decisions locked during the
brainstorm. The decisions are not open for re-litigation in this spec —
that conversation already happened. This section captures *what was
decided and why*, in a form the implementer can cite during PR review.

### 1. Storage format: tz-aware UTC datetime with microsecond precision

Stored representation in `meta.toml`:

```toml
applied_on = 2026-05-14T13:42:11.123456+00:00
last_activity = 2026-05-14T15:08:00.000000+00:00
```

TOML 1.0's "offset date-time" type covers this exactly. `tomllib.load`
parses it into a tz-aware `datetime` automatically; `tomli_w.dump` round-trips
it back. No custom serialiser in
`infrastructure/meta_io.py:_as_serializable` — the field just becomes a
`datetime` and `tomli_w` handles it.

Microsecond precision is stored because the cost is two columns of TOML
text and the upside is unambiguous ordering for two writes within the
same second (which `no_commit` removal made plausible: a `jh log` followed
by a `jh set-priority` two seconds apart now produces two commits with
two distinct `last_activity` writes).

**Why not seconds:** dropping to second precision is a one-line truncation
on read; recovering microseconds we never stored is impossible. Optionality
flows in one direction.

### 2. `notes.md` format: full UTC, Z-suffix, whole seconds

New format for every line written from this PR forward:

```
- 2026-05-14T13:42:00Z follow up with recruiter
```

- Whole seconds, never microseconds (notes are human reading material).
- `Z` suffix, never `+00:00` (visually compact, unambiguously UTC).
- Existing lines (no timestamp prefix) are not rewritten. The parser
  treats them as ordered-but-undated.

Implementation lives in `application/ops_service.add_note`:

```python
def add_note(repo, *, slug, msg, now: datetime, no_commit=False):
    line = f"- {_format_z_seconds(now)} {msg}\n"
    file_service.append(repo, slug=slug, filename="notes.md", data=line.encode())
    ...
```

`_format_z_seconds` lives in `domain/timekeeping.py` and uses
`display_local(value, precision="seconds")` followed by re-converting to
UTC's wall time — or more simply, `value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")`.

### 3. Correspondence filename: unchanged

Files in `correspondence/` keep the date-only prefix:

```
correspondence/2026-05-14-email-out-alice.md
```

Multiple interactions on the same date with the same person/channel/
direction get a numeric suffix on subsequent files (`-2.md`, `-3.md`) — this
is the existing behaviour in `commands/log.py` and stays. The precise time
of each interaction is recorded in the corresponding `last_activity` write
on `meta.toml`; the filename is a filesystem-friendly index, not the
canonical timestamp.

### 4. `is_stale` / `looks_ghosted`: calendar days in local TZ

The threshold semantics shift from "≥14 days" of `date` subtraction to
"≥14 *local-TZ calendar days* have passed between two UTC instants".

Concretely:

```python
# domain/timekeeping.py
def calendar_days_between(then_utc: datetime, now_utc: datetime) -> int:
    """Whole local-TZ calendar days from `then_utc` to `now_utc` (≥ 0).

    Both inputs must be tz-aware. Conversion to local TZ happens here.
    Days are counted as midnight boundaries crossed in the local zone.
    """
    tz = get_localzone()
    then_local = then_utc.astimezone(tz).date()
    now_local = now_utc.astimezone(tz).date()
    delta = (now_local - then_local).days
    return max(delta, 0)
```

Then `Opportunity.is_stale` / `looks_ghosted` use it:

```python
def days_since_activity(self, now: datetime) -> int | None:
    if self.last_activity is None:
        return None
    return calendar_days_between(self.last_activity, now)

def is_stale(self, now: datetime) -> bool:
    days = self.days_since_activity(now)
    return self.is_active and days is not None and days >= STALE_DAYS
```

The threshold constants `STALE_DAYS = 14` and `GHOSTED_DAYS = 21` keep
their values and meaning.

**Edge case:** DST transitions. A 24h calendar day in March (spring
forward) is 23h of wall clock; in November, 25h. `calendar_days_between`
counts boundaries crossed in the local zone, so it stays correct
regardless. UTC arithmetic that compared 14 * 86400 seconds would silently
slip by an hour twice a year.

### 5. CLI input parsing: cyclopts native, 6 ISO formats, naive → local → UTC

CLI flags currently typed `Annotated[str | None, Parameter(...)]` become
`Annotated[datetime | None, Parameter(...)]`. cyclopts uses
`datetime.fromisoformat` natively. Python 3.11+'s `fromisoformat` accepts:

```
%Y-%m-%d
%Y-%m-%dT%H:%M:%S
%Y-%m-%d %H:%M:%S
%Y-%m-%dT%H:%M:%S%z
%Y-%m-%dT%H:%M:%S.%f
%Y-%m-%dT%H:%M:%S.%f%z
```

Cyclopts surfaces parse errors as the standard "invalid value for option"
typer-style message. No custom parser needed.

After cyclopts hands the application a `datetime`, the service layer
normalises it through a single helper:

```python
# domain/timekeeping.py
def to_utc(value: datetime) -> datetime:
    """Attach local TZ to a naive datetime, then convert to UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=get_localzone())
    return value.astimezone(UTC)
```

Every service entry point that accepts a `datetime` from an adapter
calls `to_utc` on the way in. The domain layer never sees naive values.

**Pattern source:** `syntool`'s `ensure_timezone` helper in
`src/syn/lib/grafana/endpoints/silences.py`. Same shape, same contract.

**Bare date case:** `--applied-on 2026-05-14` parses as
`datetime(2026, 5, 14, 0, 0)` (naive midnight). `to_utc` recognises naive
midnight as a *bare-date hint* and bumps the time to noon-local before
applying the zone, then converts to UTC. End result: a tz-aware UTC datetime
at noon-local on the given calendar day.

The noon-local choice (rather than midnight-local) keeps the user's calendar
date visually intact in the stored UTC string — `2026-04-29` in BST stores
as `2026-04-29 11:00:00+00:00` rather than `2026-04-28 23:00:00+00:00`. It
also sits safely outside DST transition windows (which happen 01:00–03:00
local). For `is_stale` and `looks_ghosted` (which use
`calendar_days_between` on local-zone dates), midnight vs. noon produces
identical results; the difference is purely visual in the raw TOML.

### 6. Parameter rename: `today: date` → `now: datetime`

Every keyword named `today` becomes `now`. This is exhaustive across:

- Domain methods on `Opportunity` (8 methods).
- `Slug.build`.
- Application services (`lifecycle_service`, `field_service`, `ops_service`,
  `query.OpportunityQuery`).
- MCP tool wrappers in `mcp/tools/*.py`.
- CLI command modules in `commands/*.py`.

**Why a rename, not just a type change:** the type signature `now: datetime`
versus `today: date` makes the change visible to humans skimming the diff
in code review *and* to anyone reading a stack trace or repl session that
includes argument names. A pure type change (`today: datetime`) would
leave latent bugs at any call site we missed during the conversion —
"the test passed `today=date.today()` and didn't crash" silently is the
exact failure mode the rename prevents.

The rename forces every call site to be touched at least once during
this PR, which is the only sufficient correctness check for a
search-and-replace migration.

### 7. Display precision: whole seconds local, full UTC in JSON

Two distinct audiences, two distinct precisions:

| Surface | Format | Precision | TZ |
|---|---|---|---|
| `meta.toml` storage | `2026-05-14T13:42:11.123456+00:00` | microseconds | UTC |
| `notes.md` line prefix | `2026-05-14T13:42:00Z` | seconds | UTC |
| MCP JSON envelope | `2026-05-14T13:42:11.123456Z` | microseconds | UTC |
| `jh show` (human text) | `2026-05-14 14:42:11 BST` | seconds | local |
| `jh list` (human text) | `2026-05-14 14:42` | minutes | local |

The asymmetry is deliberate. Machine consumers (MCP, future daemon) get
full fidelity; humans get readable values. The library always returns
full-precision UTC datetimes — display truncation lives in the adapter
(`commands/show.py`, `commands/list_.py`) via `display_local`.

### 8. Migration: existing bare dates → noon local TZ → UTC

A one-shot script lives at `scripts/migrate_dates_to_datetimes.py`. It:

1. Walks `<data_root>/opportunities/*/meta.toml` and
   `<data_root>/archive/*/meta.toml`.
2. For each file, parses with `tomllib`. If any of the four lifecycle
   fields parsed as `datetime.date` (not `datetime.datetime`), it
   converts:

   ```python
   tz = get_localzone()
   local_noon = datetime.combine(value, time(12, 0), tzinfo=tz)
   value_utc = local_noon.astimezone(UTC)
   ```

   Noon-local rather than midnight-local — same reasoning as decision 5's
   bare-date CLI handling. Keeps the calendar date intact in the raw UTC
   string, avoids DST transition edge cases.

3. Writes the file back via `tomli_w.dump` — same `_FIELD_ORDER`, same
   shape, only the four field types changed.
4. Commits each opportunity directory individually with message
   `chore(migration): UTC datetime conversion for <slug>` so the audit
   trail per opportunity is visible in `git log` later.

The script is idempotent: a re-run on already-migrated files reads
`datetime` values, sees they're already UTC, leaves them alone. No
commit produced if nothing changed.

**Known limitation:** dates predating a past DST transition convert
using the *current* zone offset. For Robin's data set (seven
opportunities, all from 2026), no DST boundary is crossed — the noise
is zero. For future imports of older data, the migration script logs a
warning naming each affected opportunity and the magnitude of the
offset (±1h).

The migration is a CLI command too: `jh migrate utc-timestamps` —
discoverable, idempotent, easy to invoke for any future user picking up
a pre-v0.7 data root.

## Surface diff

The diff is large but mechanical. Listed below per layer.

### `src/jobhound/domain/`

**`opportunities.py`:**
- `from datetime import date` → `from datetime import UTC, datetime`
- `first_contact: date | None` → `first_contact: datetime | None` (4×)
- `days_since_activity(self, today: date) -> int | None` → `(self, now: datetime)`. Body uses `calendar_days_between`.
- `is_stale(self, today: date)`, `looks_ghosted(self, today: date)` — same rename.
- `apply(self, *, applied_on: date, today: date, next_action: str, next_action_due: date)` → `(self, *, applied_on: datetime, now: datetime, next_action: str, next_action_due: datetime)`.
- `log_interaction`, `withdraw`, `ghost`, `accept`, `decline`, `touch` — `today: date` → `now: datetime`.
- `opportunity_from_dict` (l. 147–171) — no change: TOML parser already
  produces `datetime` objects when the value has time + offset; the
  migration pass guarantees every persisted file conforms.

**`slug_value.py`:**
- `Slug.build(cls, today: date, company: str, role: str)` → `(cls, now: datetime, company: str, role: str)`.
- Internal date extraction: `prefix = now.astimezone(get_localzone()).date().isoformat()`.

**`timekeeping.py` (new):**
- `to_utc(value: datetime) -> datetime`
- `calendar_days_between(then_utc: datetime, now_utc: datetime) -> int`
- `display_local(value: datetime, *, precision: Literal["seconds", "minutes"] = "seconds") -> str`
- `now_utc() -> datetime` — single-line wrapper around `datetime.now(UTC)`
  so adapters that need the current instant import one symbol; trivial,
  but it documents the convention.
- `_format_z_seconds(value: datetime) -> str` (internal, used by `notes.md`).

### `src/jobhound/application/`

**`lifecycle_service.py`** (six functions, all touched):
- `create(repo, *, company, role, source, today: date, ...)` → `..., now: datetime, ...`.
- `apply_to(repo, *, slug, applied_on: date, next_action, next_action_due: date, today: date, ...)` → datetimes throughout, `today` → `now`.
- `log_interaction`, `withdraw_from`, `mark_ghosted`, `accept_offer`, `decline_offer` — same.

**`field_service.py`** (l. 137 and surrounds):
- `touch(repo, *, slug, today: date, ...)` → `now: datetime`.
- `set_first_contact`, `set_applied_on`, `set_last_activity`,
  `set_next_action` — each `date | None` argument becomes `datetime | None`.

**`ops_service.py`** (l. 22):
- `add_note(repo, *, slug, msg, today: date, ...)` → `now: datetime`.
- Internal formatting: prepend `_format_z_seconds(now)` to the message.

**`query.py`** (l. 67, 82, 105, 115, 157):
- `OpportunityQuery.list(self, filters, *, today: date)` → `now: datetime`.
- `_walk_root(..., archived: bool, today: date)` → `now: datetime`.
- `find(self, slug, *, today: date)` → `now: datetime`.
- `stats(self, ...)` — currently takes no date; no change.
- l. 157: internal `snaps = self.list(filters, today=date.today())` becomes
  `snaps = self.list(filters, now=now_utc())`.

**`serialization.py`:**
- New helper alongside `_date_or_none`:
  ```python
  def _datetime_or_none(value: datetime | None) -> str | None:
      return _datetime_to_z(value) if value is not None else None
  ```
- The four lifecycle field lines (l. 47–51) switch from `_date_or_none` to
  `_datetime_or_none`.
- `SCHEMA_VERSION: int = 1` → `SCHEMA_VERSION: int = 2`.

**`snapshots.py`:**
- `OpportunitySnapshot` carries an `Opportunity`; no direct change here.
  The `Opportunity`'s field types changing propagates through transparently.
- `ComputedFlags.days_since_activity: int | None` — unchanged. The number
  is a calendar-day count, which is the same type before and after.

### `src/jobhound/infrastructure/`

**`meta_io.py`:**
- No code change to `_as_serializable` or `_FIELD_ORDER`. The migration
  pass guarantees that by the time `_as_serializable` runs, the four
  lifecycle fields are `datetime`; `tomli_w` handles them.
- Add a `_validate_tz_aware(opp: Opportunity) -> None` helper called from
  `validate()` that asserts no lifecycle field is naive. Raises
  `ValidationError("first_contact is timezone-naive in <path>")` if any
  bare-date value reached us — defence in depth against a partial
  migration. Migration script and write paths can never produce a naive
  value, but a hand-edited `meta.toml` could.

**`repository.py`:**
- No direct change. `repository.create` already takes the Opportunity
  fully built; the value object change cascades.

### `src/jobhound/mcp/`

**`tools/lifecycle.py`** (l. 28, 37):
- `today: date` → `now: datetime`.
- `_derive_slug(company, today: date)` → `_derive_slug(company, now: datetime)`.
- Every helper that produces `date.today()` for a default now produces
  `now_utc()`.

**`tools/fields.py`** (l. 21):
- `_wrap(tool_name, fn, today: date)` → `now: datetime`.

**`tools/ops.py`** (l. 48):
- `today=date.today()` → `now=now_utc()`.

**`tools/reads.py`** (l. 76, 90):
- Same `today=date.today()` → `now=now_utc()` substitution.

**`tools/relations.py`** (l. 24):
- Same.

**`converters.py`** (l. 5, 72):
- Import `datetime`. `today: date` → `now: datetime`.
- Date input parsing: tool-level `str` arguments parse via
  `datetime.fromisoformat`, then through `to_utc`. The MCP API contract
  documents the accepted formats (same six as CLI).

### `src/jobhound/commands/`

Every command module that currently imports `date` for typing or calls
`date.today()` is touched.

**`apply.py`** (l. 24, 25):
```python
# before
applied_on: str,            # parsed downstream
next_action_due: str,
today: Annotated[str | None, Parameter(show=False)] = None,

# after
applied_on: datetime,
next_action_due: datetime,
now: Annotated[datetime | None, Parameter(show=False)] = None,
```

**`new.py`** (l. 27, 28), **`log.py`** (l. 41, 43): same shape.

**`show.py`** (l. 7, 31), **`export.py`** (l. 7, 46), **`note.py`**,
**`_terminal.py`**: replace `today=date.today()` with `now=now_utc()`.

**`prompts.py`** (l. 13, 60):
- `parse_date_input(value: str, *, today: date) -> date` is used in
  interactive prompts (relative inputs like "tomorrow"). Keep it, but
  rename to `parse_datetime_input` and have it return a tz-aware UTC
  datetime. Internal expansion of "tomorrow" computes against
  `now.astimezone(get_localzone()).date() + timedelta(days=1)`, then
  noon local → UTC (matching the bare-date convention from decision 5).

### Tests

The biggest mechanical change. Two patterns repeat across the suite:

```python
# before
today = date(2026, 5, 14)
opp.apply(applied_on=today, today=today, next_action="x", next_action_due=today)

# after
now = datetime(2026, 5, 14, 13, 0, tzinfo=UTC)
opp.apply(applied_on=now, now=now, next_action="x", next_action_due=now)
```

Where tests need a stable "today" for stale/ghost arithmetic, fix the
hour/minute/second so DST has no influence on local-zone reasoning:

```python
# stable test instant — same wall-clock in any local zone
NOON_UTC = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
```

New tests required:
- `tests/domain/test_timekeeping.py` — `to_utc`, `calendar_days_between`,
  `display_local`, `now_utc`. Cover: naive input, aware-non-UTC input,
  DST boundary, midnight-edge calendar days.
- `tests/application/test_migration.py` — migration script idempotency,
  pre-DST warning emission, no-op on already-migrated files.
- `tests/infrastructure/test_meta_io_validation.py` — naive datetime in
  meta.toml raises `ValidationError`.
- `tests/integration/test_z_suffix_envelope.py` — `jh show --json` and
  `jh export` JSON output has Z-suffix datetimes on all four lifecycle
  fields.

Expected delta: ~50 test functions modified, ~12 new test functions.
Suite grows from 399 to roughly 430.

### Dependencies

**Added:** `tzlocal >= 5.0` to `[project.dependencies]` in `pyproject.toml`.
Pure Python, no native code, ~10 KB installed. Source:
github.com/regebro/tzlocal.

**Tested against:** the same Python matrix already in CI (3.11, 3.12,
3.13, 3.14). `tzlocal` 5.x supports 3.9+; no floor change.

## The local-TZ calendar-day helper, in detail

The single subtle piece of new logic. Three behaviours to get right:

### B1: Midnight-boundary edge case

```
last_activity = 2026-05-14T23:55:00 BST  (UTC: 22:55Z)
now           = 2026-05-15T00:05:00 BST  (UTC: 23:05Z)
```

10 minutes of wall-clock time. UTC subtraction says 600 seconds = 0 days.
Local-TZ calendar-day count: `2026-05-15 - 2026-05-14 = 1`. The user
recorded an interaction *yesterday* — this is what matters for "how stale
is this?", not the UTC count.

### B2: DST spring-forward

```
last_activity = 2026-03-29T00:30:00 BST   (just after BST starts)
now           = 2026-04-12T12:00:00 BST   (14 days + 11.5h later)
```

Local-TZ calendar-day count: 14. `(now - last_activity).days` in UTC:
also 14 (the UTC delta is 14 days minus one hour, which still floors to
14). Same answer here — but the next bullet shows where they diverge.

### B3: Activity recorded *during* DST transition

```
last_activity = 2026-03-29T01:30:00 BST   (UTC: 2026-03-29T00:30Z)
                                          (last instant before clocks jump)
now           = 2026-04-11T03:00:00 BST   (UTC: 2026-04-11T02:00Z)
```

UTC delta: `13 days, 1h30m`. UTC `.days` floor: 13.
Local calendar days: `2026-04-11 - 2026-03-29 = 13`. Same here.

The cases where they *differ* are the ones in B1 — close-to-midnight
crossings — which is exactly the failure mode users complain about
("I logged a reply *yesterday*, why does it say zero days?"). Local-TZ
calendar arithmetic is the answer.

### Implementation

```python
def calendar_days_between(then_utc: datetime, now_utc: datetime) -> int:
    if then_utc.tzinfo is None or now_utc.tzinfo is None:
        raise ValueError("calendar_days_between requires tz-aware datetimes")
    tz = get_localzone()
    return max((now_utc.astimezone(tz).date() - then_utc.astimezone(tz).date()).days, 0)
```

Properties (testable):
- `then == now` → 0.
- `now < then` → 0 (clamped; "negative staleness" is meaningless).
- `then 23:59:59 local`, `now 00:00:00 next-day local` → 1 (one boundary
  crossed).
- `then 00:00:00 day-N local`, `now 23:59:59 day-N local` → 0 (same calendar day).

## Migration plan

One-shot. Run by the user on the existing data root before installing
the v0.7 build that *requires* `datetime` in meta.toml.

```bash
uv tool install --upgrade 'jobhound[mcp]'      # picks up v0.7.0
jh migrate utc-timestamps                      # one shot, idempotent
```

Internally:

1. Walks `<data_root>/opportunities/*/meta.toml` and
   `<data_root>/archive/*/meta.toml`.
2. For each opportunity:
   - Reads meta.toml via `tomllib`.
   - For each of `{first_contact, applied_on, last_activity,
     next_action_due}`: if value is `date` (not `datetime`), converts to
     noon local TZ → UTC. If value is already `datetime` and tz-aware,
     leaves alone. If value is `None`, leaves alone. If value is naive
     datetime (impossible from a non-migrated read, but defensive),
     interprets as local → UTC and logs a warning.
   - Writes back via `tomli_w.dump`.
3. After all files are written, runs `git add -A && git commit -m
   "chore(migration): UTC datetime conversion"` *in a single batch* —
   one commit, reviewable as one diff.

**Rollback:** the commit is reversible with `git revert HEAD`. The diff
is bounded (only the four lifecycle field values change) and easy to
audit.

**Idempotency test:** running `jh migrate utc-timestamps` twice in a row
produces no second commit. The script reports
`No bare-date fields found; nothing to do.`

### Testing the migration in CI

`tests/application/test_migration.py` builds a temp data root with
hand-written bare-date meta.toml files, runs the migration in-process,
asserts the resulting datetimes are tz-aware UTC at noon local, and
re-runs to assert idempotency.

## Risks and edge cases

### R1: Test suite churn obscures real bugs

The mechanical part of the change is large enough that real regressions
can hide behind expected diff. Mitigation:

- Land the migration in two PRs:
  - **PR A:** add `timekeeping.py`, change the `Opportunity` domain
    layer, change services + query, write a migration script, run it
    against a checked-in `tests/fixtures/data_root_pre_migration/`
    fixture, assert the post-migration state matches a
    `tests/fixtures/data_root_post_migration/` fixture. The full suite
    must still pass — all 399 existing tests are updated.
  - **PR B:** swap CLI and MCP adapters to the new `now: datetime`
    signatures. Pure adapter change with the domain already in the
    final shape.
- Use `git log --follow` on `tests/test_cmd_apply.py` (etc.) during PR
  review to spot anything that disappeared without an obvious reason.

### R2: A naive datetime sneaks past `to_utc`

If a service forgets the `to_utc()` call, a naive datetime can reach the
domain. `_validate_tz_aware` in `meta_io.py` catches the read side;
serialisation `_datetime_to_z` raises if its input is naive (already does
— `.isoformat()` on a naive datetime produces no `+00:00`, the `.replace`
no-ops, the string lacks `Z`, which would be caught by a wire-format
contract test).

Add to `tests/domain/test_timekeeping.py`:

```python
def test_format_z_seconds_rejects_naive():
    with pytest.raises(ValueError, match="tz-aware"):
        _format_z_seconds(datetime(2026, 5, 14, 13, 0))
```

### R3: User's `TZ` environment variable disagrees with system zone

`tzlocal.get_localzone()` consults system config and the `TZ` env var.
A user who exports `TZ=UTC` in their shell but lives in BST will get
"midnight UTC" for `2026-05-14`, not "midnight BST". This is the
behaviour `tzlocal` documents and what every well-behaved Unix tool
does. The spec accepts this — `TZ` exists exactly to override
`/etc/localtime`.

### R4: Pre-DST historical migration noise

Documented in scope. The migration script emits a warning for each
field whose value would convert differently under the historical
offset vs. the current offset. For the 2026-only data set, no warnings
fire.

### R5: TOML `local-date` parses to `datetime.date`, not `datetime.datetime`

This is the precondition the migration relies on: `tomllib` does
distinguish `2026-05-14` from `2026-05-14T00:00:00+00:00`. The migration
walks meta.toml files and produces only the latter form. After
migration, every read produces `datetime`. Tests assert this on the
pre/post fixtures.

### R6: Mid-migration crash

If the migration script crashes between writing meta.toml files and
running `git commit`, the data root has uncommitted changes. Re-running
the script is idempotent (it sees datetimes, leaves them alone), but
the user is left with `git status` showing modified files. Mitigation:
the script commits *only at the very end* and fails loudly on any
write error, so a crash leaves the working tree as either
all-old-format or all-old-format-plus-uncommitted-new-format. Never
mid-state per file. `git stash && git checkout HEAD -- .` reverts.

## PR plan

Two PRs, in order:

1. **PR A — Domain + services + migration** (`feat/utc-timestamps-design`,
   this branch):
   - `domain/timekeeping.py` (new)
   - `domain/opportunities.py` field types + parameter renames
   - `domain/slug_value.py` parameter rename
   - `application/*_service.py` parameter renames
   - `application/query.py` parameter rename
   - `application/serialization.py` Z-suffix on lifecycle fields,
     `SCHEMA_VERSION` bump
   - `infrastructure/meta_io.py` validation guard
   - `scripts/migrate_dates_to_datetimes.py` (new) + `jh migrate
     utc-timestamps` CLI command (new) under `commands/migrate.py`
   - Test suite updates (~50 functions, ~12 new)
   - `pyproject.toml` adds `tzlocal`
   - `CHANGELOG.md` entry under `feat!:` — breaking change
   - **Breaking flag:** in pre-1.0 semver mode, `feat!:` bumps MINOR
     (per release-please config), so this ships as v0.7.0 not v1.0.0.

2. **PR B — Adapters** (`feat/utc-timestamps-adapters`, branched off A
   once merged):
   - `mcp/tools/*.py` parameter renames + `now_utc()` substitutions
   - `mcp/converters.py` updates
   - `commands/*.py` flag-type changes (`str` → `datetime`)
   - `commands/prompts.py` rename + return-type change
   - Integration tests on CLI flag parsing, including the six accepted
     formats and the "naive interpreted as local" rule
   - `README.md` documentation update for the new datetime flags
   - Migration guidance section in `README.md`

Splitting at the application/adapter boundary keeps each PR
reviewable. PR A is the load-bearing change; PR B is mechanical.

## Deferred follow-ups

Captured here so they don't get lost during implementation:

- **F1:** `application/sync_data` consideration. The `sync_data` MCP tool
  currently silently no-ops on invalid `direction` (noted in earlier
  Phase 4 follow-up polish list). With timestamp semantics now precise,
  reconsider whether `sync` should record a `last_synced_at: datetime`
  on each opportunity. Probably yes, but a separate spec.
- **F2:** Calendar integration. With every interaction now precisely
  timestamped, `jh ics` (Phase 3b deferred) can produce a richer
  feed — meeting blocks instead of all-day events.
- **F3:** "Activity rate" stats. `stats.funnel` could grow a "median
  days between interactions" or "p95 time-to-first-reply" with the new
  precision. Out of scope for this PR.

## Acceptance criteria

Done when:

- `rg "today:\s*date\b" src/` returns no results.
- `rg "from datetime import date\b" src/` returns at most one result
  (`domain/slug_value.py` may still import `date` for its internal
  `date.isoformat()` call, depending on the final shape).
- `meta.toml` files in the repo's fixture data set contain ISO 8601
  offset date-time values for the four lifecycle fields.
- `jh show <slug>` displays whole-second local-TZ values for the four
  fields.
- `jh show <slug> --json` envelope includes Z-suffix microsecond-
  precision UTC datetimes.
- `jh migrate utc-timestamps` is idempotent: a second invocation
  produces no commit.
- Full test suite passes — target ~430 tests on green CI for both PRs.
- `CHANGELOG.md` entry documents the breaking change and the migration
  command.

## Cleanup

When this spec lands as a commit, delete `PICKUP.md` per its own
cleanup instruction:

```bash
git rm PICKUP.md && git commit -m "chore: drop UTC timestamps pickup notes"
```
