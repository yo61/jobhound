# Pickup notes — Task #35 (UTC timestamps)

Temporary checkpoint. Delete this file once the #35 spec lands.

## Where we left off (2026-05-15)

- **Branch:** `feat/utc-timestamps-design` (off `main` at `e7a1e45`).
- **Last commit on main:** `e7a1e45 refactor: remove no_commit kwarg from CLI, services, and repository`.
- **State:** branch is empty (just created). Next step is writing the spec.

Task #43 (`no_commit` removal) shipped as PR #19; no release PR opened
because `refactor:` doesn't trigger release-please bumps in this config.
Test suite at 399.

## Steps to resume

### 1. Sanity-check git state

```bash
cd ~/code/github/yo61/jobhound
git branch --show-current        # should show feat/utc-timestamps-design
git status                       # should be clean (only this PICKUP.md)
git log --oneline -3             # tip is the empty branch off e7a1e45
```

### 2. Write the spec

The brainstorm is fully done. All design questions are answered (see
"Design decisions" below). Next action: invoke `superpowers:brainstorming`
formally (or skip to writing the spec since brainstorm content is locked),
then write the spec to:

`docs/specs/2026-05-15-utc-timestamps-design.md`

### 3. Open spec PR, then move to implementation plan

After the spec is committed and reviewed, invoke `superpowers:writing-plans`
to produce the implementation plan. This is a large refactor (the spec
analysis suggests ~15-20 tasks across 2 PRs).

## Design decisions (all locked in)

The user answered every brainstorming question. Capture these in the spec:

1. **Schema migration for existing data (answer 1b):** Existing bare-date
   entries in `meta.toml` (e.g., `applied_on = 2026-05-10`) convert to
   "midnight in user's local TZ on that date, then UTC-normalized." Edge
   case: dates crossing a past DST shift use the CURRENT local-zone offset.
   Acceptable noise; flag it in the spec.

2. **notes.md format:** Use full UTC timestamps with `Z` suffix and **whole
   seconds**. Example: `- 2026-05-14T13:42:00Z follow up with recruiter`.
   Existing entries are left alone (no rewrite of historical lines).

3. **Correspondence filename:** Stays date-only:
   `<YYYY-MM-DD>-<channel>-<direction>-<who>.md`. Precise time lives in
   `meta.toml`'s `last_activity` for that interaction. No filename
   migration needed.

4. **is_stale / looks_ghosted semantics:** Calendar-day arithmetic in
   the user's local TZ. "≥14 calendar days" means: the local-TZ calendar
   day of `now` is at least 14 days after the local-TZ calendar day of
   `last_activity`.

5. **CLI flag input contract:** Cyclopts native `datetime | None` parsing
   via `datetime.fromisoformat`. Accept all six formats syntool accepts
   (these are exactly what 3.11+ `fromisoformat` handles):
   - `%Y-%m-%d`
   - `%Y-%m-%dT%H:%M:%S`
   - `%Y-%m-%d %H:%M:%S`
   - `%Y-%m-%dT%H:%M:%S%z`
   - `%Y-%m-%dT%H:%M:%S.%f`
   - `%Y-%m-%dT%H:%M:%S.%f%z`

   Naive input attached to user's local TZ via `tzlocal.get_localzone()`,
   then `.astimezone(UTC)` for storage. Pattern matches
   `/Users/robin.syn/code/synadia/synadia-labs/syntool` (specifically
   `src/syn/lib/grafana/endpoints/silences.py:ensure_timezone`).

6. **Parameter rename:** `today: date` becomes `now: datetime` (UTC)
   everywhere — services, MCP tools, CLI flags. The new name visibly
   signals the type change.

7. **Precision (Q1):** **Store microseconds, display whole seconds.**
   - TOML storage: `applied_on = 2026-05-10T13:42:11.123456+00:00`
   - notes.md: `- 2026-05-14T13:42:00Z msg` (whole seconds)
   - CLI display (`jh show`/`jh list`): whole seconds, local TZ
   - MCP JSON envelope: full precision in UTC (machine consumption)

8. **Sequencing (Q2):** `#43 first, then #35` — done. We're now on
   step 2.

## Affected surface (rough inventory for the plan)

**Domain (`src/jobhound/domain/`):**
- `Opportunity` dataclass fields: `first_contact`, `applied_on`,
  `last_activity`, `next_action_due` — change from `date | None` to
  `datetime | None` (tz-aware UTC).
- Methods: `is_active`, `is_stale(now: datetime)`,
  `looks_ghosted(now: datetime)`, `days_since_activity(now: datetime)`.
- Stale thresholds (`STALE_DAYS = 14`, `GHOSTED_DAYS = 21`) — semantics
  shift from "≥14 days" of date subtraction to "≥14 calendar days in
  local TZ". Need a helper like
  `calendar_days_between(then_utc, now_utc, tz)` so the arithmetic is
  localized.
- State-transition methods (`apply`, `log_interaction`, `withdraw`,
  `ghost`, `accept`, `decline`, `touch`) — change `today: date` →
  `now: datetime`.

**Application services (`src/jobhound/application/`):**
- `lifecycle_service.{create, apply_to, log_interaction, withdraw_from,
   mark_ghosted, accept_offer, decline_offer}` — `today` param rename
   and type change.
- `field_service.{set_first_contact, set_applied_on, set_last_activity,
   set_next_action, touch}` — date parameters become datetime.
- `ops_service.add_note(*, msg, now: datetime)` — drop `today`.
- `query.py`: `OpportunityQuery.list(filters, *, now: datetime)`,
  `.find(slug, *, now: datetime)`, `.stats()` — `today` rename + type.
- `serialization.py`: `_date_or_none` → handle both `date` and
  `datetime`; new `_datetime_or_none` helper for the timestamp fields.
  Maintain Z-suffix output for envelope.

**Infrastructure:**
- `meta_io.py`: `_FIELD_ORDER` and `_as_serializable` — date fields are
  serialized as `tomli_w` already supports `datetime`; just verify the
  tz-aware datetime round-trips.
- Migration helper module (new): `migrate_dates_to_datetimes.py` or
  similar — reads existing `meta.toml` files, converts bare dates to
  midnight-local-TZ→UTC, writes back. One commit per migration.

**MCP / CLI adapters:**
- `mcp/tools/*.py`: CLI flag types `str | None` for date input → still
  parse via `datetime.fromisoformat`, naive → local → UTC.
- `commands/*.py`: replace `Annotated[str | None, Parameter(...)]` for
  date flags with `Annotated[datetime | None, Parameter(...)]` (cyclopts
  parses natively).

**Test scaffolding:**
- All existing tests pass `today=date(2026, 5, 14)` to services. Replace
  with `now=datetime(2026, 5, 14, 13, 0, tzinfo=UTC)` (or similar fixed
  values). Many tests will need updates — likely 30-50 test functions.

**Dependencies:**
- Add `tzlocal>=5.0` to `[project.dependencies]`. ~10 KB, pure Python.

## Open questions for review (none)

The user has answered every clarifying question. The spec writer should
not introduce new design decisions — just consolidate the above into
spec form and write it.

## Cleanup

When the #35 spec lands as a commit, delete this file:

```bash
git rm PICKUP.md && git commit -m "chore: drop UTC timestamps pickup notes"
```
