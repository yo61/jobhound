# UTC Timestamps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `jobhound` from bare `date` storage to tz-aware UTC `datetime` end-to-end, with local-TZ display at every human-facing surface, and a one-shot idempotent migration script for existing data.

**Architecture:** New `domain/timekeeping.py` module owns all timezone conversion (`to_utc`, `calendar_days_between`, `display_local`, `now_utc`, `_format_z_seconds`). The 4 lifecycle fields on `Opportunity` flip from `date | None` to `datetime | None`. Every keyword parameter named `today: date` is renamed `now: datetime` — the rename is exhaustive and deliberate (so the type change is unmissable at every call site during code review and in stack traces). `is_stale` / `looks_ghosted` shift from UTC subtraction to local-TZ calendar-day arithmetic. Bare dates accepted on the CLI parse as midnight-local-TZ then convert to UTC. JSON envelope datetimes get Z-suffix microsecond precision; human display gets whole seconds local TZ.

**Tech Stack:** Python 3.11+ stdlib (`datetime`, `tomllib`), `tomli_w` (already in deps), new dep `tzlocal>=5.0`, `pytest` (existing), `uv` (deps + venv).

---

## Reference

- **Spec:** `docs/specs/2026-05-15-utc-timestamps-design.md`
- **Task tracker:** Task #35 (was `feat/utc-timestamps-design`, now merged as commit `03795e5`)
- **Pre-existing context:** Phase 4 MCP server already uses `_datetime_to_z` in `application/serialization.py:30-32` for `FileEntry.mtime` and envelope timestamps — the Z-suffix wire format is established; this plan extends it to the four lifecycle fields.

## Spec refinement (locked in before drafting tasks)

The spec proposed a two-PR split where PR A landed services without adapters. That partition is broken — when a service signature changes from `today` to `now`, every call site must change atomically or the build breaks.

**Revised partition** (this plan implements):

- **PR A** — Internal foundation. All renames *and* all adapter call-site updates so the test suite passes end-to-end. CLI flag *types* (`str` vs `datetime`) stay as today (`str`), preserving today's UX. After PR A: working software at every commit, ships as **v0.7.0** (breaking change due to TOML schema bump).
- **PR B** — Optional CLI flag UX upgrade. Switch `commands/*.py` flag types from `Annotated[str | None, ...]` to `Annotated[datetime | None, ...]`, letting cyclopts natively parse the six ISO 8601 formats. Rename `prompts.parse_date_input` → `parse_datetime_input`. Pure adapter-layer polish.

## TDD sequencing (fixtures-first)

Task ordering is **strictly TDD**: A2 and A3 introduce new behaviour (timekeeping module, validation guard) via red→green per function. **A4 is the failing-test baseline** — it updates every existing test fixture and assertion to express the new API contract. The suite goes red at A4. Subsequent tasks (A5–A13) each turn a slice of the suite green by implementing the contract one layer at a time. A14 and A16 are TDD for new tooling (migration script, integration test).

**Build state expectation per commit:**

| Commit | Build state |
|---|---|
| A1 (deps) | green |
| A2 (timekeeping) | green |
| A3 (validation guard) | green (one test from A3 stays red until A5) |
| **A4 (fixtures + contracts)** | **red, cascading failures** |
| A5 (domain) | less red — domain & A3's deferred test green |
| A6 (Slug.build) | less red |
| A7 (serialization) | less red |
| A8–A13 (services + adapters) | less red per commit |
| A14 (migration script) | full green |
| A15–A18 (command, integration, changelog, PR) | full green |

A reviewer reading the branch's commits chronologically sees the contract land first, then watches the implementation satisfy it layer by layer.

## File Structure

### Created in PR A

| File | Responsibility |
|---|---|
| `src/jobhound/domain/timekeeping.py` | All timezone conversion + display helpers. The only place `tzlocal.get_localzone()` is called. |
| `tests/domain/test_timekeeping.py` | Unit tests for `to_utc`, `calendar_days_between`, `display_local`, `now_utc`, `_format_z_seconds`. |
| `scripts/migrate_dates_to_datetimes.py` | Idempotent migration: walks `<data_root>/{opportunities,archive}/*/meta.toml`, converts bare-date lifecycle fields to midnight-local-TZ→UTC datetimes, writes back, single git commit. |
| `src/jobhound/commands/migrate.py` | `jh migrate utc-timestamps` Typer command that invokes the script with the configured data root. |
| `tests/application/test_migrate.py` | Migration idempotency + pre-DST warning emission. |
| `tests/integration/test_z_suffix_envelope.py` | `jh show --json` and `jh export` produce Z-suffix datetimes on the four lifecycle fields. |
| `tests/infrastructure/test_meta_io_validation.py` | Naive datetime in meta.toml raises `ValidationError`. |

### Modified in PR A

| File | Change |
|---|---|
| `pyproject.toml` | Add `tzlocal>=5.0` to `[project.dependencies]`. |
| `src/jobhound/domain/opportunities.py` | 4 fields `date | None` → `datetime | None`. Methods rename `today: date` → `now: datetime`. `days_since_activity` uses `calendar_days_between`. |
| `src/jobhound/domain/slug_value.py` | `Slug.build` parameter rename; derives date prefix via `now.astimezone(get_localzone()).date()`. |
| `src/jobhound/infrastructure/meta_io.py` | Add `_validate_tz_aware` called from `validate()`. |
| `src/jobhound/application/lifecycle_service.py` | 6 functions: type changes + parameter rename. |
| `src/jobhound/application/field_service.py` | 4 date setters: `date | None` → `datetime | None`. `touch`: rename. |
| `src/jobhound/application/ops_service.py` | `add_note`: rename; prepend `_format_z_seconds(now)` to message body. |
| `src/jobhound/application/query.py` | `list`, `find`, `_walk_root`: parameter rename. Internal `date.today()` → `now_utc()`. |
| `src/jobhound/application/serialization.py` | Add `_datetime_or_none`; swap 4 lifecycle field calls; bump `SCHEMA_VERSION` 1→2. |
| `src/jobhound/mcp/converters.py` | `today: date` → `now: datetime` (line 72 + import). |
| `src/jobhound/mcp/tools/lifecycle.py` | Parameter rename + internal `date.today()` → `now_utc()`. |
| `src/jobhound/mcp/tools/fields.py` | `_wrap` parameter rename. |
| `src/jobhound/mcp/tools/ops.py` | Internal `today=date.today()` → `now=now_utc()`. |
| `src/jobhound/mcp/tools/reads.py` | Two `today=date.today()` call sites → `now=now_utc()`. |
| `src/jobhound/mcp/tools/relations.py` | One `today=date.today()` call site → `now=now_utc()`. |
| `src/jobhound/commands/apply.py` | Internal `today` → `now`; CLI flag stays `str`. Add `to_utc` parse pipeline. |
| `src/jobhound/commands/new.py` | Same pattern. |
| `src/jobhound/commands/log.py` | Same pattern. |
| `src/jobhound/commands/note.py` | Same pattern. |
| `src/jobhound/commands/show.py` | Internal `today=date.today()` → `now=now_utc()`. Use `display_local` for human output of lifecycle fields. |
| `src/jobhound/commands/export.py` | Same internal rename. |
| `src/jobhound/commands/_terminal.py` | Same. |
| `src/jobhound/cli.py` | Register the new `jh migrate` command group. |
| `tests/**/*.py` | ~50 test functions updated in A4: `today=date(...)` → `now=datetime(..., tzinfo=UTC)`. Serialization tests assert Z-suffix output + `schema_version=2`. Ops tests assert Z-prefix notes lines. |
| `CHANGELOG.md` | `feat!:` entry documenting the breaking change + the migration command. |

### Modified in PR B (separate plan section)

`src/jobhound/commands/apply.py`, `new.py`, `log.py`, `note.py`, `_terminal.py`: switch flag types `str` → `datetime`. `src/jobhound/prompts.py`: rename `parse_date_input` → `parse_datetime_input` with datetime return type.

### Test fixture conventions (used throughout PR A)

- **Default instant pinning:** Every test fixture uses **noon UTC** unless the test exercises a midnight or DST boundary:
  ```python
  NOON_UTC = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
  ```
  Pinning at noon UTC means most local zones see the same calendar date as UTC, keeping `is_stale` / `looks_ghosted` assertions zone-stable in CI (which typically runs in UTC) and on developer machines (which may be in any zone).
- **Boundary tests:** Use `monkeypatch.setattr("jobhound.domain.timekeeping.get_localzone", lambda: ZoneInfo("Europe/London"))` to pin the zone explicitly. Pattern already established in `tests/domain/test_timekeeping.py` from Task A2.

---

## Branch & PR sequence

- **PR A:** branch `feat/utc-timestamps-impl-a` off current `main`
- **PR B:** branch `feat/utc-timestamps-impl-b` off `main` (after PR A merges)

---

## Part 1 — PR A: Internal foundation

### Task A1: Create branch + add `tzlocal` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Cut the implementation branch off current `main`**

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/utc-timestamps-impl-a
```

Expected: branch `feat/utc-timestamps-impl-a` tracks no upstream yet.

- [ ] **Step 2: Add `tzlocal` to project dependencies**

In `pyproject.toml`, locate `[project] dependencies = [...]` and add the new entry (alphabetical placement):

```toml
dependencies = [
    "cyclopts>=3.0",
    "tomli-w>=1.0",
    "tzlocal>=5.0",
]
```

(Adjust to match the actual current list; the only change is adding `"tzlocal>=5.0"`.)

- [ ] **Step 3: Sync lockfile**

Run: `uv sync`
Expected: `uv.lock` updated with `tzlocal` and its single transitive dep on macOS (none) / Linux (none) / Windows (`tzdata`).

- [ ] **Step 4: Verify import works**

Run: `uv run python -c "from tzlocal import get_localzone; print(get_localzone())"`
Expected: prints the local zone name (e.g., `Europe/London`).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(deps): add tzlocal for local-zone awareness"
```

---

### Task A2: Build `domain/timekeeping.py` with TDD

**Files:**
- Create: `src/jobhound/domain/timekeeping.py`
- Create: `tests/domain/test_timekeeping.py`

This is the only module that calls `tzlocal.get_localzone()`. All other code reaches local-zone awareness through this module.

- [ ] **Step 1: Write failing tests for `to_utc`**

Create `tests/domain/test_timekeeping.py`:

```python
"""Unit tests for domain/timekeeping.py."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from jobhound.domain.timekeeping import (
    calendar_days_between,
    display_local,
    now_utc,
    to_utc,
    _format_z_seconds,
)


class TestToUtc:
    def test_naive_input_treated_as_local(self, monkeypatch):
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        naive = datetime(2026, 5, 14, 13, 0)
        result = to_utc(naive)
        assert result.tzinfo == UTC
        # 13:00 BST (UTC+1) → 12:00 UTC
        assert result.hour == 12

    def test_aware_utc_passthrough(self):
        aware = datetime(2026, 5, 14, 13, 0, tzinfo=UTC)
        assert to_utc(aware) == aware

    def test_aware_non_utc_converted(self):
        aware = datetime(2026, 5, 14, 13, 0, tzinfo=ZoneInfo("America/New_York"))
        result = to_utc(aware)
        assert result.tzinfo == UTC
        # 13:00 EDT (UTC-4) → 17:00 UTC
        assert result.hour == 17
```

- [ ] **Step 2: Run tests — expect failure (module doesn't exist)**

Run: `uv run pytest tests/domain/test_timekeeping.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'jobhound.domain.timekeeping'`.

- [ ] **Step 3: Create the module with `to_utc`**

Create `src/jobhound/domain/timekeeping.py`:

```python
"""Timezone-aware datetime helpers. The only module that calls tzlocal.

`to_utc` is the boundary helper — every datetime coming in from an adapter
(CLI flag, MCP arg, file input) passes through this on the way in.
`display_local` is the boundary helper on the way out, for human output.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from tzlocal import get_localzone


def to_utc(value: datetime) -> datetime:
    """Normalise a datetime to tz-aware UTC.

    A naive datetime is interpreted as the user's local zone, then converted.
    An aware datetime (any zone) is converted to UTC by `.astimezone()`.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=get_localzone())
    return value.astimezone(UTC)
```

- [ ] **Step 4: Run `to_utc` tests — expect pass**

Run: `uv run pytest tests/domain/test_timekeeping.py::TestToUtc -v`
Expected: 3 passed.

- [ ] **Step 5: Write failing tests for `calendar_days_between`**

Append to `tests/domain/test_timekeeping.py`:

```python
class TestCalendarDaysBetween:
    def test_same_instant_is_zero(self):
        t = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
        assert calendar_days_between(t, t) == 0

    def test_negative_clamped_to_zero(self):
        earlier = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
        later = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
        assert calendar_days_between(later, earlier) == 0

    def test_midnight_boundary_crossing(self, monkeypatch):
        """10 minutes of wall-clock, but a calendar boundary crossed."""
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        # 23:55 BST = 22:55 UTC. 00:05 next-day BST = 23:05 UTC.
        then = datetime(2026, 5, 14, 22, 55, tzinfo=UTC)
        now = datetime(2026, 5, 14, 23, 5, tzinfo=UTC)
        assert calendar_days_between(then, now) == 1

    def test_same_local_day_returns_zero(self, monkeypatch):
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        then = datetime(2026, 5, 14, 9, 0, tzinfo=UTC)  # 10:00 BST
        now = datetime(2026, 5, 14, 21, 0, tzinfo=UTC)  # 22:00 BST
        assert calendar_days_between(then, now) == 0

    def test_naive_input_rejected(self):
        naive = datetime(2026, 5, 14, 12, 0)
        aware = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="tz-aware"):
            calendar_days_between(naive, aware)
        with pytest.raises(ValueError, match="tz-aware"):
            calendar_days_between(aware, naive)
```

- [ ] **Step 6: Run — expect failure (function not defined)**

Run: `uv run pytest tests/domain/test_timekeeping.py::TestCalendarDaysBetween -v`
Expected: `ImportError` or `AttributeError: module 'jobhound.domain.timekeeping' has no attribute 'calendar_days_between'`.

- [ ] **Step 7: Implement `calendar_days_between`**

Append to `src/jobhound/domain/timekeeping.py`:

```python
def calendar_days_between(then_utc: datetime, now_utc: datetime) -> int:
    """Whole local-TZ calendar days between two UTC instants (≥ 0).

    Both inputs must be tz-aware. The arithmetic counts midnight
    boundaries crossed in the local zone, *not* raw UTC seconds. This
    is the correct semantic for "is this opportunity stale" — humans
    think in calendar days, not 86400-second blocks.
    """
    if then_utc.tzinfo is None or now_utc.tzinfo is None:
        raise ValueError("calendar_days_between requires tz-aware datetimes")
    tz = get_localzone()
    then_local = then_utc.astimezone(tz).date()
    now_local = now_utc.astimezone(tz).date()
    return max((now_local - then_local).days, 0)
```

- [ ] **Step 8: Run — expect pass**

Run: `uv run pytest tests/domain/test_timekeeping.py::TestCalendarDaysBetween -v`
Expected: 5 passed.

- [ ] **Step 9: Write failing tests for `display_local`, `now_utc`, `_format_z_seconds`**

Append to `tests/domain/test_timekeeping.py`:

```python
class TestDisplayLocal:
    def test_seconds_precision(self, monkeypatch):
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        value = datetime(2026, 5, 14, 12, 0, 30, 123456, tzinfo=UTC)
        # 12:00:30 UTC → 13:00:30 BST
        assert display_local(value, precision="seconds") == "2026-05-14 13:00:30 BST"

    def test_minutes_precision(self, monkeypatch):
        monkeypatch.setattr(
            "jobhound.domain.timekeeping.get_localzone",
            lambda: ZoneInfo("Europe/London"),
        )
        value = datetime(2026, 5, 14, 12, 0, 30, 123456, tzinfo=UTC)
        assert display_local(value, precision="minutes") == "2026-05-14 13:00 BST"


class TestNowUtc:
    def test_returns_utc_aware(self):
        result = now_utc()
        assert result.tzinfo == UTC


class TestFormatZSeconds:
    def test_z_suffix_whole_seconds(self):
        value = datetime(2026, 5, 14, 12, 0, 30, 123456, tzinfo=UTC)
        assert _format_z_seconds(value) == "2026-05-14T12:00:30Z"

    def test_naive_rejected(self):
        naive = datetime(2026, 5, 14, 12, 0)
        with pytest.raises(ValueError, match="tz-aware"):
            _format_z_seconds(naive)
```

- [ ] **Step 10: Run — expect failure**

Run: `uv run pytest tests/domain/test_timekeeping.py -v`
Expected: `TestDisplayLocal`, `TestNowUtc`, `TestFormatZSeconds` fail with attribute/import errors.

- [ ] **Step 11: Implement remaining helpers**

Append to `src/jobhound/domain/timekeeping.py`:

```python
def display_local(value: datetime, *, precision: Literal["seconds", "minutes"] = "seconds") -> str:
    """Format a UTC datetime for human display in the user's local zone.

    `precision="seconds"` → `2026-05-14 13:00:30 BST`
    `precision="minutes"` → `2026-05-14 13:00 BST`
    """
    if value.tzinfo is None:
        raise ValueError("display_local requires a tz-aware datetime")
    local = value.astimezone(get_localzone())
    if precision == "seconds":
        return local.strftime("%Y-%m-%d %H:%M:%S %Z")
    return local.strftime("%Y-%m-%d %H:%M %Z")


def now_utc() -> datetime:
    """Current instant as a tz-aware UTC datetime. Use everywhere instead of `date.today()`."""
    return datetime.now(UTC)


def _format_z_seconds(value: datetime) -> str:
    """Format a tz-aware UTC datetime as ISO 8601 with Z suffix and whole seconds.

    Used for notes.md line prefixes. Rejects naive inputs.
    """
    if value.tzinfo is None:
        raise ValueError("_format_z_seconds requires a tz-aware datetime")
    value = value.astimezone(UTC).replace(microsecond=0)
    return value.isoformat().replace("+00:00", "Z")
```

- [ ] **Step 12: Run full timekeeping test file — expect all pass**

Run: `uv run pytest tests/domain/test_timekeeping.py -v`
Expected: 12 passed.

- [ ] **Step 13: Commit**

```bash
git add src/jobhound/domain/timekeeping.py tests/domain/test_timekeeping.py
git commit -m "feat(domain): add timekeeping module for UTC/local conversion"
```

---

### Task A3: Add `meta_io` validation guard

**Files:**
- Modify: `src/jobhound/infrastructure/meta_io.py` (add helper, call from `validate`)
- Create: `tests/infrastructure/test_meta_io_validation.py`

This guard catches naive datetimes (impossible from migration-produced files, possible from hand-edited meta.toml). One test passes at this commit; the other stays red until A5 (which is intentional — it asserts the post-rename type, which doesn't exist yet).

- [ ] **Step 1: Write failing tests**

Create `tests/infrastructure/test_meta_io_validation.py`:

```python
"""Validate `meta_io` rejects naive datetimes in lifecycle fields."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.infrastructure.meta_io import ValidationError, validate


def _base_data() -> dict:
    return {
        "slug": "2026-05-14-acme-eng",
        "company": "Acme",
        "role": "Engineer",
        "status": "applied",
        "priority": "medium",
    }


def test_naive_applied_on_rejected():
    data = _base_data()
    data["applied_on"] = datetime(2026, 5, 14, 12, 0)  # naive
    with pytest.raises(ValidationError, match="timezone-naive"):
        validate(data, Path("/tmp/fake.toml"))


def test_aware_utc_applied_on_accepted():
    data = _base_data()
    data["applied_on"] = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    opp = validate(data, Path("/tmp/fake.toml"))
    assert opp.applied_on == datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
```

- [ ] **Step 2: Run — expect failure (first test fails: no naive check yet; second test fails: Opportunity.applied_on is still typed `date | None`)**

Run: `uv run pytest tests/infrastructure/test_meta_io_validation.py -v`
Expected: both tests fail.

- [ ] **Step 3: Add the helper**

In `src/jobhound/infrastructure/meta_io.py`, after the imports:

```python
from datetime import datetime

_LIFECYCLE_DATETIME_FIELDS = (
    "first_contact",
    "applied_on",
    "last_activity",
    "next_action_due",
)


def _validate_tz_aware(data: dict, path: Path | None) -> None:
    """Reject naive datetimes in lifecycle fields."""
    for name in _LIFECYCLE_DATETIME_FIELDS:
        value = data.get(name)
        if isinstance(value, datetime) and value.tzinfo is None:
            raise ValidationError(
                f"{name} is timezone-naive in {path}: every lifecycle field must be tz-aware UTC"
            )
```

Wire it into `validate`:

```python
def validate(data: dict[str, Any], path: Path | None) -> Opportunity:
    """Parse a meta.toml dict and return the Opportunity (or raise ValidationError)."""
    if not isinstance(data, dict):
        raise ValidationError("meta.toml must be a table at the top level")
    _validate_tz_aware(data, path)  # ← new
    try:
        opp = opportunity_from_dict(data, path)
    ...
```

- [ ] **Step 4: Run — first test passes, second still fails (deferred to A5)**

Run: `uv run pytest tests/infrastructure/test_meta_io_validation.py::test_naive_applied_on_rejected -v`
Expected: pass.

Run: `uv run pytest tests/infrastructure/test_meta_io_validation.py::test_aware_utc_applied_on_accepted -v`
Expected: fail. This test stays red until A5 lands the type change on `Opportunity`.

- [ ] **Step 5: Commit (with the deferred test documented)**

```bash
git add src/jobhound/infrastructure/meta_io.py tests/infrastructure/test_meta_io_validation.py
git commit -m "feat(infrastructure): reject naive datetimes in meta.toml lifecycle fields

test_aware_utc_applied_on_accepted stays red until A5 lands the
datetime type change on Opportunity."
```

---

### Task A4: Test contract migration (failing-test baseline)

**Files:**
- Modify: every test file that calls a service or domain method with `today=date(...)` or constructs an `Opportunity` with `date`-typed lifecycle fields. Expect ~30–50 test files touched.

**Purpose:** Express the new API contract in test form, all in one commit. After this commit the test suite is red across the board. Tasks A5–A13 each turn a slice green by satisfying the contract one layer at a time.

**Convention reminder:** every fixture instant pins to **noon UTC** unless the test explicitly exercises a midnight or DST boundary. Pattern:

```python
from datetime import UTC, datetime

NOON_UTC = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
```

- [ ] **Step 1: Find all `Opportunity(...)` constructions in tests**

Run: `rg -n "Opportunity\(" tests/ | head -80`

For each match, update lifecycle-field arguments from `date(...)` to `datetime(..., 12, 0, tzinfo=UTC)`:

```python
# before
Opportunity(
    ...,
    first_contact=date(2026, 5, 10),
    applied_on=date(2026, 5, 14),
    last_activity=date(2026, 5, 14),
    next_action_due=date(2026, 5, 21),
    ...
)

# after
Opportunity(
    ...,
    first_contact=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
    applied_on=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    last_activity=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    next_action_due=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
    ...
)
```

Add `from datetime import UTC, datetime` to the imports of each affected test file (delete `from datetime import date` if no other usage remains).

- [ ] **Step 2: Find all `today=date(...)` keyword calls**

Run: `rg -n "today=date\(" tests/ | head -80`

Convert each to `now=datetime(..., 12, 0, tzinfo=UTC)`:

```python
# before
service.apply_to(repo, slug, applied_on=date(2026, 5, 14), today=date(2026, 5, 14), ...)

# after
service.apply_to(repo, slug, applied_on=NOON_UTC, now=NOON_UTC, ...)
```

(Using a module-level `NOON_UTC` constant cuts repetition. Define it at the top of each test file.)

- [ ] **Step 3: Find `value=date(...)` calls on field setters**

Run: `rg -n "value=date\(" tests/ | head -40`

For `field_service.set_first_contact(..., value=date(...))` etc., convert `value` to `datetime(..., 12, 0, tzinfo=UTC)`.

- [ ] **Step 4: Update fixture meta.toml files (if any)**

Run: `rg -l "^(first_contact|applied_on|last_activity|next_action_due) = \d{4}-\d{2}-\d{2}$" tests/`

For each fixture file found, hand-edit the field to ISO 8601 offset date-time form:

```toml
# before
applied_on = 2026-05-14

# after
applied_on = 2026-05-14T12:00:00+00:00
```

- [ ] **Step 5: Update serialization-test assertions to expect Z-suffix output + schema_version=2**

Run: `rg -n "schema_version|applied_on.*iso|2026-05-..\"" tests/application/ tests/integration/ 2>/dev/null`

For each serialization test asserting on the JSON envelope output:

```python
# before
assert envelope["schema_version"] == 1
assert envelope["opportunity"]["applied_on"] == "2026-05-14"

# after
assert envelope["schema_version"] == 2
# Z-suffix datetime; allow microseconds: `2026-05-14T12:00:00Z` or `...00.000000Z`
assert envelope["opportunity"]["applied_on"].startswith("2026-05-14T12:00:00")
assert envelope["opportunity"]["applied_on"].endswith("Z")
```

- [ ] **Step 6: Update ops-test assertions for the new Z-prefix notes line**

Run: `rg -n "notes\.md|add_note" tests/application/`

For tests of `ops_service.add_note`, assert the new line format includes the timestamp prefix:

```python
# before
assert note_line == "- follow up with recruiter\n"

# after
assert note_line == "- 2026-05-14T12:00:00Z follow up with recruiter\n"
```

- [ ] **Step 7: Update CLI tests using the hidden `--today` flag**

Run: `rg -n "\"--today\"|--today=" tests/`

Rename to `--now` and update the value to an ISO datetime string:

```python
# before
result = runner.invoke(app, ["apply", slug, "--applied-on", "2026-05-14", "--today", "2026-05-14"])

# after
result = runner.invoke(app, ["apply", slug, "--applied-on", "2026-05-14", "--now", "2026-05-14T12:00:00Z"])
```

(The user-visible flags `--applied-on`, `--next-action-due` keep accepting bare dates; their value strings don't change in PR A. The internal hidden flag is what gets renamed.)

- [ ] **Step 8: Update display-format assertions (if any exist)**

Run: `rg -n "applied:|first_contact:|last_activity:" tests/`

Any test that asserts the human-display string of a lifecycle field needs updating to the new `display_local` output (e.g., `2026-05-14 13:00:00 BST` instead of `2026-05-14`). For zone stability, monkeypatch the local zone in such tests.

If no such tests exist today, skip this step.

- [ ] **Step 9: Run full suite — expect cascading failures**

Run: `uv run pytest -q 2>&1 | tail -30`

Expected shape of failures:
- `TypeError: ... got an unexpected keyword argument 'now'` (domain/service/MCP/CLI hasn't been renamed yet)
- `TypeError: ... expected date, got datetime` (Opportunity field types not yet changed)
- Assertion failures on `schema_version`, Z-suffix datetime strings, notes Z-prefix lines

This is the **failing-test baseline** the rest of the PR turns green. Note the failure count for the commit message:

```bash
uv run pytest -q 2>&1 | tail -3
# Take note of the "N failed, M passed" line.
```

- [ ] **Step 10: Commit**

```bash
git add tests/
git commit -m "test: migrate fixtures + assertions to new API contract (red baseline)

Expresses the post-migration API contract in test form. The suite is
intentionally red after this commit. Tasks A5-A13 turn it green one
layer at a time.

Baseline: <N failed, M passed from step 9>"
```

---

### Task A5: Flip `Opportunity` domain field types and rename `today`→`now`

**Files:**
- Modify: `src/jobhound/domain/opportunities.py`

This is the load-bearing type change. After this commit:
- Domain-layer tests (`tests/domain/test_opportunities.py` and similar) go from red to green.
- A3's deferred test `test_aware_utc_applied_on_accepted` goes from red to green.
- Service-layer and adapter-layer tests stay red (call sites still use old API; that's A8–A13).

- [ ] **Step 1: Update imports and `STALE_DAYS` block**

In `src/jobhound/domain/opportunities.py:6`, change:

```python
from datetime import date
```

to:

```python
from datetime import datetime

from jobhound.domain.timekeeping import calendar_days_between
```

- [ ] **Step 2: Update the 4 field types**

In `src/jobhound/domain/opportunities.py:31-35`:

```python
first_contact: datetime | None
applied_on: datetime | None
last_activity: datetime | None
next_action: str | None
next_action_due: datetime | None
```

- [ ] **Step 3: Update `days_since_activity`, `is_stale`, `looks_ghosted`**

Replace `src/jobhound/domain/opportunities.py:44-55`:

```python
def days_since_activity(self, now: datetime) -> int | None:
    if self.last_activity is None:
        return None
    return calendar_days_between(self.last_activity, now)

def is_stale(self, now: datetime) -> bool:
    days = self.days_since_activity(now)
    return self.is_active and days is not None and days >= STALE_DAYS

def looks_ghosted(self, now: datetime) -> bool:
    days = self.days_since_activity(now)
    return self.is_active and days is not None and days >= GHOSTED_DAYS
```

- [ ] **Step 4: Update `apply`, `log_interaction`, `withdraw`, `ghost`, `accept`, `decline`, `touch`**

Replace `src/jobhound/domain/opportunities.py:59-125`. Every keyword named `today` becomes `now`, every `date` annotation becomes `datetime`, every body line `last_activity=today` becomes `last_activity=now`:

```python
def apply(
    self,
    *,
    applied_on: datetime,
    now: datetime,
    next_action: str,
    next_action_due: datetime,
) -> Opportunity:
    """Submit the application. Requires status `prospect`."""
    require_transition(self.status, Status.APPLIED, verb="apply")
    return replace(
        self,
        status=Status.APPLIED,
        applied_on=applied_on,
        last_activity=now,
        next_action=next_action,
        next_action_due=next_action_due,
    )

def log_interaction(
    self,
    *,
    now: datetime,
    next_status: str,
    next_action: str | None,
    next_action_due: datetime | None,
    force: bool,
) -> Opportunity:
    if not force:
        require_transition(self.status, next_status, verb="log")
    new_status = self.status if next_status == "stay" else Status(next_status)
    return replace(
        self,
        status=new_status,
        last_activity=now,
        next_action=next_action if next_action is not None else self.next_action,
        next_action_due=(
            next_action_due if next_action_due is not None else self.next_action_due
        ),
    )

def withdraw(self, *, now: datetime) -> Opportunity:
    require_transition(self.status, Status.WITHDRAWN, verb="withdraw")
    return replace(self, status=Status.WITHDRAWN, last_activity=now)

def ghost(self, *, now: datetime) -> Opportunity:
    require_transition(self.status, Status.GHOSTED, verb="ghost")
    return replace(self, status=Status.GHOSTED, last_activity=now)

def accept(self, *, now: datetime) -> Opportunity:
    require_transition(self.status, Status.ACCEPTED, verb="accept")
    return replace(self, status=Status.ACCEPTED, last_activity=now)

def decline(self, *, now: datetime) -> Opportunity:
    require_transition(self.status, Status.DECLINED, verb="decline")
    return replace(self, status=Status.DECLINED, last_activity=now)

def touch(self, *, now: datetime) -> Opportunity:
    """Bump `last_activity` without changing status."""
    return replace(self, last_activity=now)
```

- [ ] **Step 5: Run tests — domain-layer tests + A3's deferred test go green**

Run: `uv run pytest tests/domain/ tests/infrastructure/test_meta_io_validation.py -v`
Expected: domain tests pass; both `test_meta_io_validation` tests pass. Service-layer and adapter-layer tests in other directories still fail — that's expected.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/domain/opportunities.py
git commit -m "feat(domain)!: Opportunity uses tz-aware datetime for lifecycle fields

BREAKING CHANGE: first_contact, applied_on, last_activity, and
next_action_due are now datetime | None (tz-aware UTC). Domain method
parameter today: date renamed to now: datetime."
```

---

### Task A6: Update `Slug.build`

**Files:**
- Modify: `src/jobhound/domain/slug_value.py:39`

- [ ] **Step 1: Update imports**

In `src/jobhound/domain/slug_value.py:7`:

```python
from datetime import datetime

from jobhound.domain.timekeeping import to_utc
from tzlocal import get_localzone
```

- [ ] **Step 2: Update `Slug.build`**

At `src/jobhound/domain/slug_value.py:39`:

```python
@classmethod
def build(cls, now: datetime, company: str, role: str) -> Slug:
    """Build a slug from current instant, company, and role.

    The date prefix uses the user's local-zone calendar date (slugs are
    human-readable filesystem identifiers, not UTC instants).
    """
    now_utc_value = to_utc(now)
    local_date = now_utc_value.astimezone(get_localzone()).date()
    prefix = local_date.isoformat()
    # ...rest of the existing body unchanged, but using `prefix` instead of
    # `today.isoformat()`.
```

(Adapt the inner body to keep the existing slug-construction logic; only the source of `prefix` changes.)

- [ ] **Step 3: Run slug tests**

Run: `uv run pytest tests/domain/test_slug_value.py -v` (or the actual test path)
Expected: pass — A4 already updated tests to use `now=datetime(...)`.

- [ ] **Step 4: Commit**

```bash
git add src/jobhound/domain/slug_value.py
git commit -m "refactor(domain): Slug.build accepts now: datetime, derives local-TZ prefix"
```

---

### Task A7: Update `application/serialization.py` — Z-suffix datetimes + schema bump

**Files:**
- Modify: `src/jobhound/application/serialization.py`

- [ ] **Step 1: Add `_datetime_or_none` helper**

In `src/jobhound/application/serialization.py`, just after `_date_or_none` at line 26-27:

```python
def _datetime_or_none(value: datetime | None) -> str | None:
    return _datetime_to_z(value) if value is not None else None
```

- [ ] **Step 2: Update the 4 lifecycle field serialization calls**

In `src/jobhound/application/serialization.py:47-51`, replace:

```python
"first_contact": _date_or_none(opp.first_contact),
"applied_on": _date_or_none(opp.applied_on),
"last_activity": _date_or_none(opp.last_activity),
"next_action": opp.next_action,
"next_action_due": _date_or_none(opp.next_action_due),
```

with:

```python
"first_contact": _datetime_or_none(opp.first_contact),
"applied_on": _datetime_or_none(opp.applied_on),
"last_activity": _datetime_or_none(opp.last_activity),
"next_action": opp.next_action,
"next_action_due": _datetime_or_none(opp.next_action_due),
```

- [ ] **Step 3: Bump `SCHEMA_VERSION`**

In `src/jobhound/application/serialization.py:23`:

```python
SCHEMA_VERSION: int = 2
```

- [ ] **Step 4: Run serialization tests**

Run: `uv run pytest tests/application/test_serialization.py -v` (path may differ)
Expected: pass — A4 already updated assertions to expect Z-suffix output and `schema_version=2`.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/application/serialization.py
git commit -m "feat(application)!: serialize lifecycle fields as Z-suffix datetimes (schema v2)"
```

---

### Task A8: Update `application/lifecycle_service.py`

**Files:**
- Modify: `src/jobhound/application/lifecycle_service.py`

Six functions touched. Pattern: `today: date` → `now: datetime`, `date` → `datetime` for `applied_on` and `next_action_due`.

- [ ] **Step 1: Update imports**

In `src/jobhound/application/lifecycle_service.py:12`:

```python
from datetime import datetime
```

- [ ] **Step 2: Update `apply_to`**

Replace lines 28-46:

```python
def apply_to(
    repo: OpportunityRepository,
    slug: str,
    *,
    applied_on: datetime,
    now: datetime,
    next_action: str,
    next_action_due: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.apply(
        applied_on=applied_on,
        now=now,
        next_action=next_action,
        next_action_due=next_action_due,
    )
    repo.save(after, opp_dir, message=f"apply: {after.slug}")
    return before, after, opp_dir
```

- [ ] **Step 3: Update `log_interaction`**

Lines 49-74. Rename `today` → `now`, type `next_action_due: date | None` → `datetime | None`, body call `before.log_interaction(today=today, ...)` → `before.log_interaction(now=now, ...)`.

- [ ] **Step 4: Update `withdraw_from`, `mark_ghosted`, `accept_offer`, `decline_offer`**

Lines 77-126. Each takes only `today: date` → `now: datetime`; body call uses `now=now`.

- [ ] **Step 5: Run lifecycle service tests**

Run: `uv run pytest tests/application/test_lifecycle_service.py -v` (path may differ)
Expected: pass — A4 already updated fixtures.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/application/lifecycle_service.py
git commit -m "refactor(application): lifecycle_service uses now: datetime"
```

---

### Task A9: Update `application/field_service.py`

**Files:**
- Modify: `src/jobhound/application/field_service.py`

Five lines to change: 4 `set_*` functions accepting `date | None` and 1 `touch` accepting `today: date`.

- [ ] **Step 1: Update import**

In `src/jobhound/application/field_service.py:10`:

```python
from datetime import datetime
```

- [ ] **Step 2: Update the 4 lifecycle-field setters**

Lines 95-116. Each:

```python
def set_first_contact(
    repo: OpportunityRepository,
    slug: str,
    value: datetime | None,
) -> tuple[Opportunity, Opportunity, Path]:
    return _set_field(repo, slug, "first_contact", value, "first_contact")
```

Apply the same `datetime | None` to `set_applied_on`, `set_last_activity`. For `set_next_action` (line 119), change `due: date | None` → `due: datetime | None`.

- [ ] **Step 3: Update `touch`**

Lines 133-143:

```python
def touch(
    repo: OpportunityRepository,
    slug: str,
    *,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    """Bump last_activity to `now` without changing anything else."""
    before, opp_dir = repo.find(slug)
    after = before.touch(now=now)
    repo.save(after, opp_dir, message=f"touch: {after.slug}")
    return before, after, opp_dir
```

- [ ] **Step 4: Run field service tests**

Run: `uv run pytest tests/application/test_field_service.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/application/field_service.py
git commit -m "refactor(application): field_service uses datetime for lifecycle fields"
```

---

### Task A10: Update `application/ops_service.py` — `add_note` + Z-suffix line prefix

**Files:**
- Modify: `src/jobhound/application/ops_service.py:22` (function signature) and body (prepend timestamp to message)

- [ ] **Step 1: Update import**

In `src/jobhound/application/ops_service.py:7`:

```python
from datetime import datetime

from jobhound.domain.timekeeping import _format_z_seconds
```

- [ ] **Step 2: Update `add_note` to rename `today`→`now` and prepend timestamp to the note line**

Locate the existing message-construction line in `add_note`. The user-facing change: every new note line in `notes.md` starts with `- YYYY-MM-DDTHH:MM:SSZ msg\n`.

```python
def add_note(
    repo: OpportunityRepository,
    slug: str,
    *,
    msg: str,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Path]:
    timestamp = _format_z_seconds(now)
    line = f"- {timestamp} {msg}\n"
    # ...continue using file_service.append for the line; the rest of the
    # function body (load opp, append to notes.md, possibly touch last_activity)
    # stays as today, modulo the today→now rename.
```

- [ ] **Step 3: Run ops service tests**

Run: `uv run pytest tests/application/test_ops_service.py -v`
Expected: pass — A4 already updated assertions to expect Z-prefix lines.

- [ ] **Step 4: Commit**

```bash
git add src/jobhound/application/ops_service.py
git commit -m "feat(application)!: notes.md lines get Z-suffix UTC timestamp prefix"
```

---

### Task A11: Update `application/query.py`

**Files:**
- Modify: `src/jobhound/application/query.py:67,82,105,115,157`

- [ ] **Step 1: Update import**

In `src/jobhound/application/query.py:11`:

```python
from datetime import UTC, datetime

from jobhound.domain.timekeeping import now_utc
```

- [ ] **Step 2: Update `list`, `find`, `_walk_root`, `stats`**

Replace every `today: date` keyword with `now: datetime`. Body calls to `opp.is_stale(today=today)` → `opp.is_stale(now=now)` (similarly for `looks_ghosted`, `days_since_activity`).

At line 157:

```python
snaps = self.list(filters, now=now_utc())
```

- [ ] **Step 3: Run query tests**

Run: `uv run pytest tests/application/test_query.py -v`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/jobhound/application/query.py
git commit -m "refactor(application): OpportunityQuery uses now: datetime"
```

---

### Task A12: Update `mcp/converters.py` and all `mcp/tools/*.py` call sites

**Files:**
- Modify: `src/jobhound/mcp/converters.py:5,72`
- Modify: `src/jobhound/mcp/tools/lifecycle.py:28,37`
- Modify: `src/jobhound/mcp/tools/fields.py:21`
- Modify: `src/jobhound/mcp/tools/ops.py:48`
- Modify: `src/jobhound/mcp/tools/reads.py:76,90`
- Modify: `src/jobhound/mcp/tools/relations.py:24`

All mechanical: `today: date` → `now: datetime`, `today=date.today()` → `now=now_utc()`.

- [ ] **Step 1: Update `mcp/converters.py`**

Change import from `from datetime import date` to `from datetime import datetime`. At line 72, rename parameter.

- [ ] **Step 2: Update `mcp/tools/lifecycle.py`**

Change import to `datetime`. Rename parameter at line 28. Rename `_derive_slug` at line 37 (`today: date` → `now: datetime`); internal call becomes `Slug.build(now=now, ...)`.

Replace any `today=date.today()` defaults with `now=now_utc()` (importing `from jobhound.domain.timekeeping import now_utc`).

- [ ] **Step 3: Update `mcp/tools/fields.py`**

Rename `_wrap(tool_name, fn, today: date)` → `_wrap(tool_name, fn, now: datetime)` at line 21. Update internal usage accordingly.

- [ ] **Step 4: Update `mcp/tools/ops.py`**

At line 48, change `today=date.today()` to `now=now_utc()`. Update imports.

- [ ] **Step 5: Update `mcp/tools/reads.py`**

Two call sites (line 76, 90): `today=date.today()` → `now=now_utc()`.

- [ ] **Step 6: Update `mcp/tools/relations.py`**

One call site (line 24): same substitution.

- [ ] **Step 7: Run MCP tool tests**

Run: `uv run pytest tests/mcp/ -v`
Expected: pass — A4 already updated MCP test fixtures.

- [ ] **Step 8: Commit**

```bash
git add src/jobhound/mcp/
git commit -m "refactor(mcp): MCP tools use now: datetime / now_utc()"
```

---

### Task A13: Update `commands/*.py` call sites + display formatting

**Files:**
- Modify: `src/jobhound/commands/apply.py`
- Modify: `src/jobhound/commands/new.py`
- Modify: `src/jobhound/commands/log.py`
- Modify: `src/jobhound/commands/note.py`
- Modify: `src/jobhound/commands/show.py`
- Modify: `src/jobhound/commands/export.py`
- Modify: `src/jobhound/commands/_terminal.py`

CLI flag *types* stay `Annotated[str | None, Parameter(show=False)]` in PR A. The internal hidden flag renames `today` → `now`, and each command parses string flags through `datetime.fromisoformat` + `to_utc` before calling services. Display formatting routes through `display_local`.

- [ ] **Step 1: Update each command file (rename + parse pipeline)**

For each command file, the rename pattern is:

```python
# before
from datetime import date
...
today: Annotated[str | None, Parameter(show=False)] = None,
...
today_obj = date.fromisoformat(today) if today else date.today()
lifecycle_service.apply_to(repo, slug, today=today_obj, ...)

# after
from datetime import datetime
from jobhound.domain.timekeeping import now_utc, to_utc
...
now: Annotated[str | None, Parameter(show=False)] = None,
...
now_obj = to_utc(datetime.fromisoformat(now)) if now else now_utc()
lifecycle_service.apply_to(repo, slug, now=now_obj, ...)
```

For date inputs that aren't hidden test-flags (e.g., `--applied-on`):

```python
# before
applied_on: str,
applied_on_obj = date.fromisoformat(applied_on)

# after
applied_on: str,
applied_on_obj = to_utc(datetime.fromisoformat(applied_on))
```

Files in priority order:

1. `commands/show.py` — only `today=date.today()` to migrate.
2. `commands/export.py` — same.
3. `commands/_terminal.py` — same.
4. `commands/note.py` — `today` hidden flag + possible due-date input.
5. `commands/apply.py` — `applied_on`, `next_action_due`, `today`.
6. `commands/new.py` — `next_action_due`, `today`.
7. `commands/log.py` — `next_action_due`, `today`.

- [ ] **Step 2: Update human-display formatting**

Find display sites:

```bash
rg -n "applied_on|first_contact|last_activity|next_action_due" src/jobhound/commands/show.py src/jobhound/commands/list_.py src/jobhound/commands/_terminal.py
```

For each line that prints a lifecycle field, route through `display_local`:

```python
# before — would produce "2026-05-14 12:00:30+00:00" (raw UTC ISO)
print(f"applied: {opp.applied_on}")

# after — produces "2026-05-14 13:00:30 BST" (local TZ, whole seconds)
from jobhound.domain.timekeeping import display_local
print(f"applied: {display_local(opp.applied_on) if opp.applied_on else '—'}")
```

`jh list` (typically minute-precision for compactness) uses `display_local(value, precision="minutes")`.

The `--json` envelope output is untouched — already handled by `serialization.py` from A7.

- [ ] **Step 3: Run CLI tests**

Run: `uv run pytest tests/ -k "cmd_" -v`
Expected: pass — A4 already updated `--today`→`--now` flag values and any display assertions.

- [ ] **Step 4: Run full suite — expect full green**

Run: `uv run pytest -q`
Expected: full pass. Test count should be roughly the same as pre-migration; new tests come in A14 and A16.

If any tests are still red, they're residual call sites missed in earlier tasks. Fix each in place and re-run.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/commands/
git commit -m "refactor(cli): commands convert string flags to UTC datetime; human output uses display_local"
```

---

### Task A14: Write the migration script

**Files:**
- Create: `scripts/migrate_dates_to_datetimes.py`
- Create: `tests/scripts/test_migrate.py`

The script is library-shaped so the tests can call it in-process. A15 wires up the CLI command.

- [ ] **Step 1: Write failing tests**

Create `tests/scripts/test_migrate.py`:

```python
"""Migration script: bare-date meta.toml → tz-aware UTC datetime."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from scripts.migrate_dates_to_datetimes import migrate_data_root


def _write_meta(path: Path, applied_on: object) -> None:
    """Write a minimal meta.toml with a single date field."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'company = "Acme"\nrole = "Engineer"\nstatus = "applied"\n'
        f'slug = "2026-05-14-acme-eng"\npriority = "medium"\n'
        f'applied_on = {applied_on.isoformat()}\n'
    )


def test_migration_converts_bare_date(tmp_path, monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    meta = tmp_path / "opportunities" / "2026-05-14-acme-eng" / "meta.toml"
    _write_meta(meta, date(2026, 5, 14))

    changes = migrate_data_root(tmp_path)
    assert changes == 1

    import tomllib
    with meta.open("rb") as fh:
        data = tomllib.load(fh)
    assert isinstance(data["applied_on"], datetime)
    assert data["applied_on"].tzinfo is not None
    # TZ=UTC, so midnight local == midnight UTC
    assert data["applied_on"] == datetime(2026, 5, 14, 0, 0, tzinfo=UTC)


def test_migration_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    meta = tmp_path / "opportunities" / "2026-05-14-acme-eng" / "meta.toml"
    _write_meta(meta, datetime(2026, 5, 14, 0, 0, tzinfo=UTC))

    changes = migrate_data_root(tmp_path)
    assert changes == 0
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/scripts/test_migrate.py -v`
Expected: `ModuleNotFoundError: No module named 'scripts.migrate_dates_to_datetimes'`.

- [ ] **Step 3: Write the migration script**

Create `scripts/migrate_dates_to_datetimes.py`:

```python
"""One-shot migration: bare-date lifecycle fields → tz-aware UTC datetimes.

Idempotent. Safe to re-run. Operates on raw TOML so it doesn't depend on
the post-migration Opportunity type assertions.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, date, datetime, time
from pathlib import Path

import tomli_w
from tzlocal import get_localzone

LIFECYCLE_FIELDS = (
    "first_contact",
    "applied_on",
    "last_activity",
    "next_action_due",
)


def _maybe_convert(value: object, tz: object) -> datetime | None:
    """Convert a bare date to midnight-local→UTC; passthrough for None / datetime.

    Returns None when no conversion is needed (already a datetime or None).
    Returns a datetime when conversion happened.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return None  # already migrated
    if isinstance(value, date):
        local_midnight = datetime.combine(value, time(0, 0), tzinfo=tz)
        return local_midnight.astimezone(UTC)
    return None


def _migrate_one(path: Path, tz: object) -> bool:
    """Migrate a single meta.toml. Returns True if anything changed."""
    with path.open("rb") as fh:
        data = tomllib.load(fh)

    changed = False
    for name in LIFECYCLE_FIELDS:
        converted = _maybe_convert(data.get(name), tz)
        if converted is not None:
            data[name] = converted
            changed = True

    if changed:
        with path.open("wb") as fh:
            tomli_w.dump(data, fh)
    return changed


def migrate_data_root(root: Path) -> int:
    """Walk a data root, migrate every meta.toml. Returns count of files changed."""
    tz = get_localzone()
    count = 0
    for subdir in ("opportunities", "archive"):
        base = root / subdir
        if not base.is_dir():
            continue
        for meta in base.glob("*/meta.toml"):
            if _migrate_one(meta, tz):
                count += 1
    return count
```

- [ ] **Step 4: Run — expect pass**

Run: `uv run pytest tests/scripts/test_migrate.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_dates_to_datetimes.py tests/scripts/test_migrate.py
git commit -m "feat(scripts): add UTC datetime migration for existing meta.toml files"
```

---

### Task A15: Wire `jh migrate utc-timestamps` CLI command

**Files:**
- Create: `src/jobhound/commands/migrate.py`
- Modify: `src/jobhound/cli.py` (register the new command group)

- [ ] **Step 1: Create the command module**

`src/jobhound/commands/migrate.py`:

```python
"""`jh migrate` subcommand group. Currently exposes `utc-timestamps`."""

from __future__ import annotations

from pathlib import Path

import cyclopts

from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.git import git_commit_all
from scripts.migrate_dates_to_datetimes import migrate_data_root

app = cyclopts.App(name="migrate", help="One-shot data migrations.")


@app.command(name="utc-timestamps")
def utc_timestamps() -> None:
    """Migrate bare-date lifecycle fields to tz-aware UTC datetimes.

    Idempotent. Safe to re-run. Writes a single git commit if anything changed.
    """
    cfg = load_config()
    root = Path(cfg.data_root)
    count = migrate_data_root(root)
    if count == 0:
        print("No bare-date fields found; nothing to do.")
        return
    git_commit_all(root, message="chore(migration): UTC datetime conversion")
    print(f"Migrated {count} meta.toml file(s) and committed.")
```

(The exact `git_commit_all` helper name depends on what's in `infrastructure/git.py`; use whatever existing helper commits all changes in the data root, or wire it directly via `subprocess.run`.)

- [ ] **Step 2: Register the command group in `cli.py`**

In `src/jobhound/cli.py`, after the other `app.command(...)` registrations:

```python
from jobhound.commands import migrate as cmd_migrate

app.command(cmd_migrate.app)
```

- [ ] **Step 3: Smoke-test the wiring**

Run: `uv run jh migrate --help`
Expected: output describing `utc-timestamps` subcommand.

Run: `uv run jh migrate utc-timestamps`
Expected (against your actual `~/.local/share/jh/`, post-test-data migration): either `No bare-date fields found; nothing to do.` or `Migrated N meta.toml file(s) and committed.`. **Do not run against production data yet; use a copy.**

- [ ] **Step 4: Commit**

```bash
git add src/jobhound/commands/migrate.py src/jobhound/cli.py
git commit -m "feat(cli): add 'jh migrate utc-timestamps' command"
```

---

### Task A16: Integration test — Z-suffix in JSON envelope

**Files:**
- Create: `tests/integration/test_z_suffix_envelope.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end: `jh show --json` and `jh export` emit Z-suffix datetimes."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from cyclopts.testing import CliRunner  # or whatever the project's CLI test harness is

from jobhound.cli import app


Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def test_jh_show_json_has_z_suffix_datetimes(tmp_data_root):
    """tmp_data_root is an existing fixture that seeds a known opportunity."""
    runner = CliRunner()
    result = runner.invoke(app, ["show", "<known-slug>", "--json"])
    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["schema_version"] == 2
    opp = envelope["opportunity"]
    for field in ("first_contact", "applied_on", "last_activity", "next_action_due"):
        if field in opp and opp[field] is not None:
            assert Z_RE.match(opp[field]), f"{field} = {opp[field]!r} is not Z-suffix"
```

(Replace placeholders with the actual fixture / CLI test pattern in this repo.)

- [ ] **Step 2: Run — expect pass**

Run: `uv run pytest tests/integration/test_z_suffix_envelope.py -v`
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_z_suffix_envelope.py
git commit -m "test(integration): assert Z-suffix datetimes in jh show --json"
```

---

### Task A17: Update `CHANGELOG.md`

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add the v0.7.0 entry**

At the top of `CHANGELOG.md` (above the previous entry), prepend:

```markdown
## v0.7.0 (unreleased)

### BREAKING CHANGES

- **meta.toml schema bumped 1→2.** The four lifecycle fields
  (`first_contact`, `applied_on`, `last_activity`, `next_action_due`)
  are now tz-aware UTC datetimes (ISO 8601 offset date-time) instead of
  bare dates. Run `jh migrate utc-timestamps` against your data root
  before installing v0.7.0; the migration is idempotent and produces a
  single git commit.
- All keyword parameters named `today: date` are now `now: datetime`
  (tz-aware UTC). Internal call-site rename across domain, services,
  MCP tools, and CLI commands.

### Features

- `jh migrate utc-timestamps` — one-shot, idempotent migration command
  for converting existing data root meta.toml files to the new schema.
- `notes.md` lines written after this release carry an ISO 8601
  Z-suffix UTC timestamp prefix (e.g.,
  `- 2026-05-14T13:42:00Z follow up with recruiter`). Historical lines
  are left as written.
- `is_stale` and `looks_ghosted` now use *local-TZ calendar-day*
  arithmetic. The "14 days stale" threshold matches a human's
  intuition regardless of UTC offset.

### Dependencies

- Added: `tzlocal >= 5.0`.

### Known limitations

- Migration of pre-DST historical dates uses the *current* local-zone
  offset, which may shift those values by ±1h. For data sets created
  in 2026 only (no DST boundary crossings), this is zero noise.
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): document v0.7.0 UTC datetime migration"
```

---

### Task A18: Open and merge PR A

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/utc-timestamps-impl-a
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --title "feat!: UTC datetime storage end-to-end (Task #35 PR A)" --body "$(cat <<'EOF'
## Summary

PR A of two for Task #35 — replaces every `date` in the persisted model with tz-aware `datetime` (UTC stored). Spec: `docs/specs/2026-05-15-utc-timestamps-design.md`. Plan: `docs/plans/2026-05-15-utc-timestamps.md`.

Internal type and rename migration end-to-end. CLI flag types stay `str`; PR B will switch them to native `datetime` parsing.

Includes `jh migrate utc-timestamps` for converting existing data roots. Idempotent.

Breaking change: meta.toml schema v1→v2 (pre-1.0 semver: bumps to v0.7.0, not v1.0.0, per release-please config).

## Test plan

- [ ] Full test suite passes.
- [ ] `jh migrate utc-timestamps` against a copy of the user's data root produces a clean commit; second run reports "nothing to do".
- [ ] `jh show <slug> --json` envelope has Z-suffix datetimes on the four lifecycle fields and `schema_version: 2`.
EOF
)"
```

- [ ] **Step 3: Wait for CI**

```bash
until gh pr view <PR#> --json statusCheckRollup -q '[.statusCheckRollup[]?|.conclusion] | all(. != "")' 2>/dev/null | grep -q true; do sleep 10; done
gh pr view <PR#> --json mergeStateStatus,statusCheckRollup
```

Expected: all checks SUCCESS, mergeState CLEAN.

- [ ] **Step 4: Merge**

```bash
gh pr merge <PR#> --rebase --delete-branch
```

- [ ] **Step 5: Sync local main**

```bash
git checkout main
git pull --ff-only origin main
```

---

## Part 2 — PR B: CLI flag UX upgrade (optional follow-up)

After PR A merges, these tasks switch CLI flags from `str` to native `datetime` parsing. Pure adapter work.

### Task B1: Cut branch off updated `main`

- [ ] **Step 1: Branch**

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/utc-timestamps-impl-b
```

---

### Task B2: Switch CLI flag types to `datetime`

**Files:**
- Modify: `src/jobhound/commands/apply.py`
- Modify: `src/jobhound/commands/new.py`
- Modify: `src/jobhound/commands/log.py`
- Modify: `src/jobhound/commands/note.py`
- Modify: `src/jobhound/commands/_terminal.py`

- [ ] **Step 1: For each command file, change flag types**

Pattern per command:

```python
# before (PR A's state)
applied_on: str,
next_action_due: str,
now: Annotated[str | None, Parameter(show=False)] = None,
...
applied_on_obj = to_utc(datetime.fromisoformat(applied_on))
next_action_due_obj = to_utc(datetime.fromisoformat(next_action_due))
now_obj = to_utc(datetime.fromisoformat(now)) if now else now_utc()

# after (PR B)
applied_on: datetime,
next_action_due: datetime,
now: Annotated[datetime | None, Parameter(show=False)] = None,
...
applied_on_obj = to_utc(applied_on)
next_action_due_obj = to_utc(next_action_due)
now_obj = to_utc(now) if now else now_utc()
```

Cyclopts now does the `fromisoformat` parse and surfaces format errors with its native "invalid value for option" message.

- [ ] **Step 2: Update CLI tests if needed**

Existing tests passing `--applied-on 2026-05-14` continue to work — cyclopts parses `2026-05-14` via `datetime.fromisoformat` (which accepts bare dates as midnight). No test changes required for the happy path.

Add new tests for:
- The six accepted ISO 8601 formats from the spec.
- A malformed input (e.g., `--applied-on garbage`) producing a clean error.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_cmd_*.py -v`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/jobhound/commands/ tests/
git commit -m "feat(cli): commands accept datetime flags via cyclopts native parsing"
```

---

### Task B3: Rename `prompts.parse_date_input` → `parse_datetime_input`

**Files:**
- Modify: `src/jobhound/prompts.py`
- Modify: any tests of `prompts`

- [ ] **Step 1: Rename and re-type**

In `src/jobhound/prompts.py:13`:

```python
def parse_datetime_input(value: str, *, now: datetime) -> datetime:
    """Parse user-typed datetime/date input.

    Accepts ISO 8601 (any of the six fromisoformat-supported variants) plus
    relative forms ("today", "tomorrow", "in 3 days"). Returns tz-aware UTC.
    """
    # ...existing relative-date logic adapted to operate on `now.astimezone(local).date()`...
    # ...for ISO inputs: to_utc(datetime.fromisoformat(value))
```

Update the line 60 call site to use the new name and parameter signature.

- [ ] **Step 2: Update callers**

Run: `rg -n "parse_date_input" src/ tests/`
For each match, replace `parse_date_input(raw, today=date.today())` with `parse_datetime_input(raw, now=now_utc())`.

- [ ] **Step 3: Run tests**

Run: `uv run pytest -q`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/jobhound/prompts.py tests/
git commit -m "refactor(prompts): parse_date_input renamed to parse_datetime_input"
```

---

### Task B4: Open and merge PR B

- [ ] **Step 1: Push**

```bash
git push -u origin feat/utc-timestamps-impl-b
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --title "feat(cli): native datetime flag parsing (Task #35 PR B)" --body "$(cat <<'EOF'
## Summary

PR B of two for Task #35 — switches CLI flag types from `str` to `datetime` so cyclopts parses ISO 8601 inputs natively. Pure UX upgrade; no functional change from PR A.

Also renames `prompts.parse_date_input` → `parse_datetime_input` for type consistency.

## Test plan

- [ ] Full test suite passes.
- [ ] `jh apply <slug> --applied-on 2026-05-14T13:42:00+01:00 ...` accepted and stored as the equivalent UTC instant.
- [ ] `jh apply <slug> --applied-on garbage` produces a clean cyclopts error.
EOF
)"
```

- [ ] **Step 3: Wait for CI and merge**

```bash
until gh pr view <PR#> --json statusCheckRollup -q '[.statusCheckRollup[]?|.conclusion] | all(. != "")' 2>/dev/null | grep -q true; do sleep 10; done
gh pr merge <PR#> --rebase --delete-branch
git checkout main
git pull --ff-only origin main
```

---

## Verification at the end

After both PRs are merged:

```bash
# 1. The rename is total — no surviving `today: date` keyword parameters
rg "today:\s*date\b" src/
# Expected: no output

# 2. No bare `date` imports in source (one allowed exception in slug_value.py
# for its internal `.date()` call)
rg "from datetime import date\b" src/
# Expected: at most one match

# 3. Run the migration against your actual data root copy
cp -r ~/.local/share/jh ~/Desktop/jh-backup-pre-migration
uv tool install --upgrade 'jobhound[mcp]'
jh migrate utc-timestamps
# Expected: "Migrated N meta.toml file(s) and committed."

# 4. Idempotency check
jh migrate utc-timestamps
# Expected: "No bare-date fields found; nothing to do."

# 5. Visual spot check
head -20 ~/.local/share/jh/opportunities/*/meta.toml | grep applied_on
# Expected: ISO 8601 offset date-time values

# 6. JSON envelope sanity check
jh show <some-slug> --json | jq '.opportunity | {first_contact, applied_on, last_activity, next_action_due}'
# Expected: Z-suffix datetimes
```

---

## Self-review notes

- **Spec coverage:** All 8 locked design decisions from the spec map to tasks (storage format → A7; notes.md → A10; correspondence filename unchanged → no task needed; is_stale → A5; CLI input parsing → A13+B2; rename → A5–A13; precision → A7+A13; migration → A14+A15).
- **Two-PR partition:** Refined from spec (services and adapters must change atomically because the keyword parameter renamed). PR A is end-to-end working at the final commit; PR B is pure UX.
- **TDD discipline:** Applied strictly — A4 establishes the failing-test baseline; A5–A13 each turn a slice green. New code (A2, A3, A14, A16) follows red→green per function. The build is intentionally red between A4 and A13; A13's final step asserts full green before commit.
- **Reviewability:** A4's single fixture commit (one large but uniform diff) is the contract statement; each impl commit afterward turns a measurable slice of tests green. Reviewer reads the contract first, then watches the implementation satisfy it.
