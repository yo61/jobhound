# Phase 3a — Read API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `jh` read API — `OpportunityQuery`, snapshot dataclasses, JSON serialisation, and the `jh show` / `jh export` CLI commands — on top of a DDD-layered package reorganisation, all without adding runtime dependencies.

**Architecture:** Mechanical DDD reorg first (`src/jobhound/` flat → `domain/` + `infrastructure/` + `application/` + `commands/` subpackages) so subsequent code lands in the right layer. Then a CQRS-shaped read side: `OpportunityQuery` is a *sibling* of `OpportunityRepository` (not a wrapper) and has no git side-effects on construction. Snapshots materialise the existing `Opportunity` aggregate's derived methods (`is_stale`, `looks_ghosted`, …) at a fixed `today` so JSON output is frozen-in-time. Serialisation lives in its own module so the CLI, a future HTTP daemon, and any future export format share one source of truth for the wire shape.

**Tech Stack:** Python 3.11+, stdlib only for Phase 3a (no new deps). Cyclopts for CLI parameters (existing). `tomllib` for TOML reads (existing). pytest for tests.

**Spec:** `docs/specs/2026-05-12-jh-read-api-design.md` is the contract; this plan is the execution.

---

## File Structure

### Files moved by Task 1 (mechanical reorg)

```
src/jobhound/
  __init__.py                             # unchanged
  cli.py                                  # imports rewritten (no move)
  prompts.py                              # unchanged (stays at package root)

  domain/                                 # NEW subpackage
    __init__.py                           # empty
    opportunities.py                      # moved from src/jobhound/opportunities.py
    status.py                             # moved
    priority.py                           # moved
    contact.py                            # moved
    slug.py                               # moved
    slug_value.py                         # moved
    transitions.py                        # moved

  infrastructure/                         # NEW subpackage
    __init__.py                           # empty
    repository.py                         # moved
    meta_io.py                            # moved
    paths.py                              # moved
    config.py                             # moved
    git.py                                # moved

  application/                            # NEW subpackage (empty until Task 2)
    __init__.py                           # empty

  commands/                               # unchanged location; imports rewritten
    __init__.py                           # unchanged
    accept.py apply.py archive.py ...     # imports rewritten
    _terminal.py
```

Tests stay flat in `tests/` for the reorg (only imports get rewritten). New Phase 3a tests are introduced in subdirectories:

- `tests/application/test_snapshots.py` (Task 2)
- `tests/application/test_query.py` (Tasks 3, 4, 5)
- `tests/application/test_serialization.py` (Tasks 6, 7)
- `tests/commands/test_cmd_show.py` (Task 8)
- `tests/commands/test_cmd_export.py` (Task 9)
- `tests/application/conftest.py` (Task 3, `query_paths` fixture)

### Files created by later tasks

- `src/jobhound/application/snapshots.py` — Task 2
- `src/jobhound/application/query.py` — Tasks 3, 4, 5
- `src/jobhound/application/serialization.py` — Tasks 6, 7
- `src/jobhound/commands/show.py` — Task 8
- `src/jobhound/commands/export.py` — Task 9

---

## Task 1: Mechanical DDD reorganisation

**Goal:** Split `src/jobhound/` flat layout into `domain/` / `infrastructure/` / `application/` / `commands/` subpackages. Pure rename + import rewrite. Behaviour MUST be unchanged. 142-test suite green before any new code lands.

**Files:**
- Create: `src/jobhound/domain/__init__.py`
- Create: `src/jobhound/infrastructure/__init__.py`
- Create: `src/jobhound/application/__init__.py`
- Move (`git mv`): 7 domain modules into `domain/`, 5 infrastructure modules into `infrastructure/`
- Modify: `src/jobhound/cli.py`, all `src/jobhound/commands/*.py` (imports)
- Modify: every test file under `tests/` that imports `jobhound.<flat>` (imports)

- [ ] **Step 1: Create the subpackage skeletons**

```bash
mkdir -p src/jobhound/domain src/jobhound/infrastructure src/jobhound/application
: > src/jobhound/domain/__init__.py
: > src/jobhound/infrastructure/__init__.py
: > src/jobhound/application/__init__.py
git add src/jobhound/domain/__init__.py src/jobhound/infrastructure/__init__.py src/jobhound/application/__init__.py
```

- [ ] **Step 2: `git mv` the domain modules**

```bash
git mv src/jobhound/opportunities.py src/jobhound/domain/opportunities.py
git mv src/jobhound/status.py        src/jobhound/domain/status.py
git mv src/jobhound/priority.py      src/jobhound/domain/priority.py
git mv src/jobhound/contact.py       src/jobhound/domain/contact.py
git mv src/jobhound/slug.py          src/jobhound/domain/slug.py
git mv src/jobhound/slug_value.py    src/jobhound/domain/slug_value.py
git mv src/jobhound/transitions.py   src/jobhound/domain/transitions.py
```

- [ ] **Step 3: `git mv` the infrastructure modules**

```bash
git mv src/jobhound/repository.py src/jobhound/infrastructure/repository.py
git mv src/jobhound/meta_io.py    src/jobhound/infrastructure/meta_io.py
git mv src/jobhound/paths.py      src/jobhound/infrastructure/paths.py
git mv src/jobhound/config.py     src/jobhound/infrastructure/config.py
git mv src/jobhound/git.py        src/jobhound/infrastructure/git.py
```

- [ ] **Step 4: Confirm the working tree shape**

Run:

```bash
ls src/jobhound/ src/jobhound/domain/ src/jobhound/infrastructure/ src/jobhound/application/
```

Expected: package root contains only `__init__.py`, `cli.py`, `prompts.py`, `__pycache__`, and the four subpackage dirs. Each subpackage contains its `__init__.py` and the moved files.

- [ ] **Step 5: Rewrite imports across `src/` and `tests/`**

The import map is exactly:

| Old import prefix | New import prefix |
|---|---|
| `jobhound.opportunities` | `jobhound.domain.opportunities` |
| `jobhound.status` | `jobhound.domain.status` |
| `jobhound.priority` | `jobhound.domain.priority` |
| `jobhound.contact` | `jobhound.domain.contact` |
| `jobhound.slug` | `jobhound.domain.slug` |
| `jobhound.slug_value` | `jobhound.domain.slug_value` |
| `jobhound.transitions` | `jobhound.domain.transitions` |
| `jobhound.repository` | `jobhound.infrastructure.repository` |
| `jobhound.meta_io` | `jobhound.infrastructure.meta_io` |
| `jobhound.paths` | `jobhound.infrastructure.paths` |
| `jobhound.config` | `jobhound.infrastructure.config` |
| `jobhound.git` | `jobhound.infrastructure.git` |

Use this one-liner from the repo root. It targets `from jobhound.X` and `import jobhound.X` forms across `src/` and `tests/`:

```bash
python - <<'PY'
import pathlib, re

PAIRS = [
    ("opportunities",  "domain.opportunities"),
    ("status",         "domain.status"),
    ("priority",       "domain.priority"),
    ("contact",        "domain.contact"),
    ("slug_value",     "domain.slug_value"),    # MUST come before "slug"
    ("slug",           "domain.slug"),
    ("transitions",    "domain.transitions"),
    ("repository",     "infrastructure.repository"),
    ("meta_io",        "infrastructure.meta_io"),
    ("paths",          "infrastructure.paths"),
    ("config",         "infrastructure.config"),
    ("git",            "infrastructure.git"),
]

roots = [pathlib.Path("src"), pathlib.Path("tests")]
for root in roots:
    for path in root.rglob("*.py"):
        text = path.read_text()
        new = text
        for old, new_suffix in PAIRS:
            new = re.sub(
                rf"\bjobhound\.{old}\b",
                f"jobhound.{new_suffix}",
                new,
            )
        if new != text:
            path.write_text(new)
            print(f"rewrote {path}")
PY
```

Notes:
- `slug_value` is rewritten before `slug` because `slug` is a prefix of `slug_value`; the order matters even with `\b` since the substitution is left-to-right.
- The script only rewrites text. It does not move files.

- [ ] **Step 6: Spot-check the rewrite**

Run:

```bash
rg -n "from jobhound\.(opportunities|status|priority|contact|slug|slug_value|transitions|repository|meta_io|paths|config|git)\b" src tests
```

Expected: NO results. If anything remains, fix it manually and re-run.

Also confirm new imports exist:

```bash
rg -c "from jobhound\.(domain|infrastructure)\." src tests | head -20
```

Expected: positive counts.

- [ ] **Step 7: Run the full test suite at the new import paths**

Run:

```bash
uv run pytest -q
```

Expected: `142 passed` (exact count). No collection errors, no import errors.

If anything fails:
- If `ModuleNotFoundError`, an import was missed. Re-run Step 5's `rg` check.
- If a test fails on behaviour, you've accidentally edited content rather than imports — diff `git status` to find what.

- [ ] **Step 8: Run lint + typecheck**

Run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

Expected: zero warnings, zero errors.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor: reorganise package into domain/infrastructure/application/commands subpackages"
```

The commit should show as renames (`R100`) in `git show --stat` for the moved files plus content diffs only for the import rewrites in `cli.py`, `commands/*.py`, and `tests/*.py`.

---

## Task 2: `application/snapshots.py` — read-side dataclasses

**Goal:** Define the four frozen dataclasses every read API consumer will touch: `ComputedFlags`, `OpportunitySnapshot`, `FileEntry`, `Stats`. Pure data, no I/O.

**Files:**
- Create: `src/jobhound/application/snapshots.py`
- Create: `tests/application/__init__.py` (empty, so pytest can discover the subdir)
- Create: `tests/application/test_snapshots.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/application/__init__.py` (empty file) and `tests/application/test_snapshots.py`:

```python
"""Tests for application/snapshots.py — frozen read-side dataclasses."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from jobhound.application.snapshots import (
    ComputedFlags,
    FileEntry,
    OpportunitySnapshot,
    Stats,
)
from jobhound.domain.contact import Contact
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status


def _opp(**overrides: object) -> Opportunity:
    base = dict(
        slug="2026-05-acme-em",
        company="Acme",
        role="EM",
        status=Status.APPLIED,
        priority=Priority.HIGH,
        source="LinkedIn",
        location=None,
        comp_range=None,
        first_contact=None,
        applied_on=date(2026, 5, 3),
        last_activity=date(2026, 5, 10),
        next_action=None,
        next_action_due=None,
    )
    base.update(overrides)
    return Opportunity(**base)  # type: ignore[arg-type]


def test_computed_flags_is_frozen() -> None:
    flags = ComputedFlags(is_active=True, is_stale=False, looks_ghosted=False, days_since_activity=2)
    with pytest.raises((AttributeError, TypeError)):
        flags.is_active = False  # type: ignore[misc]


def test_snapshot_carries_opportunity_path_and_flags(tmp_path: Path) -> None:
    opp = _opp()
    snap = OpportunitySnapshot(
        opportunity=opp,
        archived=False,
        path=tmp_path,
        computed=ComputedFlags(
            is_active=True, is_stale=False, looks_ghosted=False, days_since_activity=2
        ),
    )
    assert snap.opportunity is opp
    assert snap.archived is False
    assert snap.path == tmp_path
    assert snap.computed.is_active is True


def test_snapshot_is_frozen(tmp_path: Path) -> None:
    snap = OpportunitySnapshot(
        opportunity=_opp(),
        archived=False,
        path=tmp_path,
        computed=ComputedFlags(True, False, False, 0),
    )
    with pytest.raises((AttributeError, TypeError)):
        snap.archived = True  # type: ignore[misc]


def test_file_entry_fields() -> None:
    mtime = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
    entry = FileEntry(name="meta.toml", size=412, mtime=mtime)
    assert entry.name == "meta.toml"
    assert entry.size == 412
    assert entry.mtime == mtime
    assert entry.mtime.tzinfo is timezone.utc


def test_stats_fields() -> None:
    stats = Stats(
        funnel={Status.APPLIED: 3, Status.SCREEN: 1},
        sources={"LinkedIn": 2, "(unspecified)": 1},
    )
    assert stats.funnel[Status.APPLIED] == 3
    assert stats.sources["LinkedIn"] == 2
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run:

```bash
uv run pytest tests/application/test_snapshots.py -v
```

Expected: collection fails or all tests error with `ModuleNotFoundError: No module named 'jobhound.application.snapshots'`.

- [ ] **Step 3: Implement `application/snapshots.py`**

Create `src/jobhound/application/snapshots.py`:

```python
"""Frozen read-side dataclasses returned by OpportunityQuery.

These are pure data: no I/O, no methods that touch disk or git. Construction
is the only place where derived fields (ComputedFlags) get materialised — once
built, a snapshot is immutable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jobhound.domain.opportunities import Opportunity
from jobhound.domain.status import Status


@dataclass(frozen=True)
class ComputedFlags:
    """Derived flags evaluated at a fixed `today` so JSON output is frozen-in-time."""

    is_active: bool
    is_stale: bool
    looks_ghosted: bool
    days_since_activity: int | None


@dataclass(frozen=True)
class OpportunitySnapshot:
    """A single opportunity plus its archive flag, absolute path, and computed flags."""

    opportunity: Opportunity
    archived: bool
    path: Path
    computed: ComputedFlags


@dataclass(frozen=True)
class FileEntry:
    """One file inside an opportunity directory. `name` is relative to the opp dir."""

    name: str
    size: int
    mtime: datetime  # tz-aware (UTC)


@dataclass(frozen=True)
class Stats:
    """Aggregate counts. `funnel` covers every Status; `sources` uses `(unspecified)` for None."""

    funnel: dict[Status, int]
    sources: dict[str, int]
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run:

```bash
uv run pytest tests/application/test_snapshots.py -v
```

Expected: 5 tests pass.

Also run the full suite to confirm no regressions:

```bash
uv run pytest -q
```

Expected: `147 passed` (142 existing + 5 new).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/snapshots.py tests/application/__init__.py tests/application/test_snapshots.py
git commit -m "feat(application): add read-side snapshot dataclasses"
```

---

## Task 3: `application/query.py` — `Filters`, `OpportunityQuery.find()`, `.list()`

**Goal:** The read-side entrypoint. `OpportunityQuery(paths)` constructs without git side-effects; `find(slug, today=...)` returns one snapshot; `list(filters, today=...)` returns all matching snapshots sorted by slug. Archive scanning is opt-in.

**Files:**
- Create: `src/jobhound/application/query.py`
- Create: `tests/application/conftest.py` (the `query_paths` fixture, reused in Tasks 4 + 5)
- Create: `tests/application/test_query.py`

- [ ] **Step 1: Write the `query_paths` fixture**

Create `tests/application/conftest.py`:

```python
"""Shared fixtures for application-layer tests.

`query_paths` builds a `tmp_path` data root with three opportunities:
- one active and recent ("acme")
- one active and stale ("beta", last activity 30 days before `TODAY`)
- one archived ("gamma", in archive/)

Each opp also has a small set of files for read_file / files() tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from jobhound.infrastructure.paths import Paths


TODAY = date(2026, 5, 13)


def _write_meta(opp_dir: Path, **fields: object) -> None:
    """Write a minimal meta.toml. fields override defaults."""
    opp_dir.mkdir(parents=True, exist_ok=True)
    (opp_dir / "correspondence").mkdir(exist_ok=True)
    defaults: dict[str, object] = {
        "company": "Acme",
        "role": "Engineer",
        "slug": opp_dir.name,
        "status": "applied",
        "priority": "medium",
    }
    defaults.update(fields)
    lines = []
    for key, value in defaults.items():
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, list):
            inner = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key} = [{inner}]")
        elif isinstance(value, date):
            lines.append(f"{key} = {value.isoformat()}")
        else:
            lines.append(f"{key} = {value!r}")
    (opp_dir / "meta.toml").write_text("\n".join(lines) + "\n")


@pytest.fixture
def query_paths(tmp_path: Path) -> Paths:
    db_root = tmp_path / "db"
    opps_dir = db_root / "opportunities"
    arch_dir = db_root / "archive"
    shared_dir = db_root / "_shared"
    for d in (opps_dir, arch_dir, shared_dir):
        d.mkdir(parents=True)

    _write_meta(
        opps_dir / "2026-05-acme-em",
        company="Acme",
        role="EM",
        status="applied",
        priority="high",
        source="LinkedIn",
        applied_on=date(2026, 5, 1),
        last_activity=date(2026, 5, 11),  # 2 days before TODAY
        tags=["remote"],
    )
    (opps_dir / "2026-05-acme-em" / "notes.md").write_text("notes\n")
    (opps_dir / "2026-05-acme-em" / "cv.md").write_text("# CV\n")
    (opps_dir / "2026-05-acme-em" / "correspondence" / "intro.md").write_text("hi\n")

    _write_meta(
        opps_dir / "2026-04-beta-eng",
        company="Beta",
        role="Engineer",
        status="screen",
        priority="medium",
        source="Referral",
        applied_on=date(2026, 4, 1),
        last_activity=date(2026, 4, 10),  # 33 days before TODAY -> stale
    )

    _write_meta(
        arch_dir / "2026-03-gamma-staff",
        company="Gamma",
        role="Staff Engineer",
        status="rejected",
        priority="low",
        source="LinkedIn",
        applied_on=date(2026, 3, 1),
        last_activity=date(2026, 3, 20),
    )

    return Paths(
        db_root=db_root,
        opportunities_dir=opps_dir,
        archive_dir=arch_dir,
        shared_dir=shared_dir,
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )
```

- [ ] **Step 2: Write the failing tests for `find` and `list`**

Create `tests/application/test_query.py`:

```python
"""Tests for OpportunityQuery.find and .list (Tasks 3)."""

from __future__ import annotations

from datetime import date

import pytest

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.application.snapshots import OpportunitySnapshot
from jobhound.domain.priority import Priority
from jobhound.domain.slug import SlugNotFoundError
from jobhound.domain.status import Status

from tests.application.conftest import TODAY


def test_find_returns_snapshot(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("acme", today=TODAY)
    assert isinstance(snap, OpportunitySnapshot)
    assert snap.opportunity.slug == "2026-05-acme-em"
    assert snap.archived is False
    assert snap.path == query_paths.opportunities_dir / "2026-05-acme-em"
    assert snap.computed.is_active is True
    assert snap.computed.is_stale is False
    assert snap.computed.days_since_activity == 2


def test_find_marks_stale(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("beta", today=TODAY)
    assert snap.computed.is_stale is True
    assert snap.computed.days_since_activity == 33


def test_find_resolves_archived_opportunity(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snap = q.find("gamma", today=TODAY)
    assert snap.archived is True
    assert snap.path == query_paths.archive_dir / "2026-03-gamma-staff"


def test_find_raises_on_unknown_slug(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    with pytest.raises(SlugNotFoundError):
        q.find("nonexistent", today=TODAY)


def test_list_returns_all_non_archived_by_default(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(today=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert slugs == ["2026-04-beta-eng", "2026-05-acme-em"]
    assert all(s.archived is False for s in snaps)


def test_list_include_archived(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(include_archived=True), today=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert slugs == ["2026-03-gamma-staff", "2026-04-beta-eng", "2026-05-acme-em"]
    archived = {s.opportunity.slug: s.archived for s in snaps}
    assert archived == {
        "2026-03-gamma-staff": True,
        "2026-04-beta-eng": False,
        "2026-05-acme-em": False,
    }


def test_list_filter_by_status(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(statuses=frozenset({Status.APPLIED})), today=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_filter_by_priority(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(priorities=frozenset({Priority.HIGH})), today=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_filter_by_slug_substring(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(slug_substring="acme"), today=TODAY)
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]


def test_list_active_only_excludes_terminal(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(Filters(active_only=True, include_archived=True), today=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert "2026-03-gamma-staff" not in slugs  # rejected is terminal


def test_list_active_only_intersects_with_statuses(query_paths) -> None:
    """active_only AND explicit statuses = intersection (per spec)."""
    q = OpportunityQuery(query_paths)
    # APPLIED is active; SCREEN is active. Both present.
    snaps = q.list(
        Filters(active_only=True, statuses=frozenset({Status.APPLIED})),
        today=TODAY,
    )
    assert [s.opportunity.slug for s in snaps] == ["2026-05-acme-em"]
    # REJECTED is terminal; active_only suppresses it even if requested.
    snaps = q.list(
        Filters(active_only=True, statuses=frozenset({Status.REJECTED}), include_archived=True),
        today=TODAY,
    )
    assert snaps == []


def test_list_returns_sorted_by_slug(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    snaps = q.list(today=TODAY)
    slugs = [s.opportunity.slug for s in snaps]
    assert slugs == sorted(slugs)
```

- [ ] **Step 3: Run the tests to confirm they fail**

Run:

```bash
uv run pytest tests/application/test_query.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'jobhound.application.query'`.

- [ ] **Step 4: Implement `application/query.py` (skeleton + `find` + `list`)**

Create `src/jobhound/application/query.py`:

```python
"""The read-only public surface over the jh data root.

OpportunityQuery is a CQRS sibling of OpportunityRepository: same data, no
writes, no git side-effects on construction. A future HTTP daemon's read
endpoints will inject the same class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from jobhound.application.snapshots import (
    ComputedFlags,
    OpportunitySnapshot,
)
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.slug import SlugNotFoundError, resolve_slug
from jobhound.domain.status import Status
from jobhound.infrastructure.meta_io import read_meta
from jobhound.infrastructure.paths import Paths


@dataclass(frozen=True)
class Filters:
    """Optional read-time filters. Empty/None = no filter on that dimension."""

    statuses: frozenset[Status] = field(default_factory=frozenset)
    priorities: frozenset[Priority] = field(default_factory=frozenset)
    slug_substring: str | None = None
    active_only: bool = False
    include_archived: bool = False


class OpportunityQuery:
    """Read-only view over the data root. The public read surface of `jh`."""

    def __init__(self, paths: Paths) -> None:
        self._paths = paths

    # ---- helpers --------------------------------------------------------

    def _resolve_opp_dir(self, slug: str) -> tuple[Path, bool]:
        """Find `slug` in opportunities/ first, then archive/. Returns (dir, archived)."""
        opps_dir = self._paths.opportunities_dir
        if opps_dir.exists():
            try:
                return resolve_slug(slug, opps_dir), False
            except SlugNotFoundError:
                pass
        arch_dir = self._paths.archive_dir
        if arch_dir.exists():
            return resolve_slug(slug, arch_dir), True
        raise SlugNotFoundError(f"no opportunity matches {slug!r}")

    def _snapshot(self, opp: Opportunity, opp_dir: Path, archived: bool, today: date) -> OpportunitySnapshot:
        days = opp.days_since_activity(today)
        flags = ComputedFlags(
            is_active=opp.is_active,
            is_stale=opp.is_stale(today),
            looks_ghosted=opp.looks_ghosted(today),
            days_since_activity=days,
        )
        return OpportunitySnapshot(
            opportunity=opp, archived=archived, path=opp_dir, computed=flags,
        )

    def _walk_root(self, root: Path, *, archived: bool, today: date) -> list[OpportunitySnapshot]:
        if not root.exists():
            return []
        snaps: list[OpportunitySnapshot] = []
        for sub in sorted(root.iterdir()):
            if not sub.is_dir():
                continue
            meta = sub / "meta.toml"
            if not meta.exists():
                continue
            opp = read_meta(meta)
            snaps.append(self._snapshot(opp, sub, archived, today))
        return snaps

    def _matches(self, snap: OpportunitySnapshot, filters: Filters) -> bool:
        opp = snap.opportunity
        if filters.statuses and opp.status not in filters.statuses:
            return False
        if filters.priorities and opp.priority not in filters.priorities:
            return False
        if filters.active_only and not opp.is_active:
            return False
        if filters.slug_substring is not None and filters.slug_substring not in opp.slug:
            return False
        return True

    # ---- public API -----------------------------------------------------

    def find(self, slug: str, *, today: date) -> OpportunitySnapshot:
        """Resolve `slug` (supports prefix/substring) and return its snapshot."""
        opp_dir, archived = self._resolve_opp_dir(slug)
        opp = read_meta(opp_dir / "meta.toml")
        return self._snapshot(opp, opp_dir, archived, today)

    def list(
        self,
        filters: Filters = Filters(),
        *,
        today: date,
    ) -> list[OpportunitySnapshot]:
        """Return all snapshots matching `filters`, sorted by slug."""
        snaps = self._walk_root(self._paths.opportunities_dir, archived=False, today=today)
        if filters.include_archived:
            snaps += self._walk_root(self._paths.archive_dir, archived=True, today=today)
        snaps = [s for s in snaps if self._matches(s, filters)]
        snaps.sort(key=lambda s: s.opportunity.slug)
        return snaps
```

Notes for the engineer:
- `OpportunityRepository.__init__` calls `ensure_repo`; `OpportunityQuery.__init__` MUST NOT. Reads have no git side-effects (spec line 186, 197).
- `find()` looks in `opportunities/` first, then falls back to `archive/`. This keeps `jh show acme` working for archived opps without needing a separate flag.
- Spec line 543 says `find` should raise `FileNotFoundError` for unknown slugs. We propagate `SlugNotFoundError` instead, which is more specific and what `OpportunityRepository.find` already raises. The CLI in Task 8 catches `SlugNotFoundError` and maps it to exit code 2 with the spec's error message. This is a deliberate library-layer choice; the spec wire contract (CLI exit code + stderr) is preserved.

- [ ] **Step 5: Run the tests to confirm they pass**

Run:

```bash
uv run pytest tests/application/test_query.py -v
```

Expected: all 12 tests pass.

Full suite:

```bash
uv run pytest -q
```

Expected: `159 passed` (147 + 12).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/query.py tests/application/conftest.py tests/application/test_query.py
git commit -m "feat(application): add OpportunityQuery.find and .list with filters"
```

---

## Task 4: `OpportunityQuery.files()` and `.read_file()`

**Goal:** File listing (recursive, names relative to opp dir) and safe file reading (rejects path traversal via `..`, absolute paths, or symlink escape).

**Files:**
- Modify: `src/jobhound/application/query.py` (add two methods)
- Modify: `tests/application/test_query.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/application/test_query.py`:

```python
from datetime import datetime, timezone


def test_files_lists_top_level_and_correspondence(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    entries = q.files("acme")
    names = sorted(e.name for e in entries)
    assert names == ["correspondence/intro.md", "cv.md", "meta.toml", "notes.md"]
    for e in entries:
        assert e.size > 0
        assert e.mtime.tzinfo is not None
        assert e.mtime.tzinfo.utcoffset(e.mtime) == timezone.utc.utcoffset(
            datetime.now(timezone.utc)
        )


def test_files_empty_correspondence_returns_no_correspondence_entries(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    entries = q.files("beta")  # beta has only meta.toml (no notes, no correspondence files)
    names = sorted(e.name for e in entries)
    assert names == ["meta.toml"]


def test_files_excludes_hidden_files(query_paths) -> None:
    """Hidden files like .DS_Store are skipped."""
    (query_paths.opportunities_dir / "2026-05-acme-em" / ".DS_Store").write_text("noise")
    q = OpportunityQuery(query_paths)
    names = {e.name for e in q.files("acme")}
    assert ".DS_Store" not in names


def test_read_file_returns_bytes(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    data = q.read_file("acme", "notes.md")
    assert isinstance(data, bytes)
    assert data == b"notes\n"


def test_read_file_correspondence_subpath(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    data = q.read_file("acme", "correspondence/intro.md")
    assert data == b"hi\n"


def test_read_file_rejects_traversal_dotdot(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    with pytest.raises(ValueError, match="must be inside"):
        q.read_file("acme", "../../../etc/passwd")


def test_read_file_rejects_absolute_path(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    with pytest.raises(ValueError, match="must be inside"):
        q.read_file("acme", "/etc/passwd")


def test_read_file_rejects_symlink_escape(query_paths, tmp_path) -> None:
    """A symlink that points outside the opp dir is rejected even with a plain filename."""
    secret = tmp_path / "secret.txt"
    secret.write_text("nope")
    link = query_paths.opportunities_dir / "2026-05-acme-em" / "evil"
    link.symlink_to(secret)
    q = OpportunityQuery(query_paths)
    with pytest.raises(ValueError, match="must be inside"):
        q.read_file("acme", "evil")
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run:

```bash
uv run pytest tests/application/test_query.py -k "files or read_file" -v
```

Expected: 8 tests fail with `AttributeError: 'OpportunityQuery' object has no attribute 'files'` (or similar).

- [ ] **Step 3: Implement `files` and `read_file` in `query.py`**

Add these imports to the top of `src/jobhound/application/query.py`:

```python
from datetime import datetime, timezone

from jobhound.application.snapshots import FileEntry
```

Add these methods to the `OpportunityQuery` class:

```python
    def files(self, slug: str) -> list[FileEntry]:
        """List every non-hidden file inside the opp dir, recursive. Names are relative."""
        opp_dir, _ = self._resolve_opp_dir(slug)
        entries: list[FileEntry] = []
        for path in sorted(opp_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(opp_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            stat = path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            entries.append(FileEntry(name=rel.as_posix(), size=stat.st_size, mtime=mtime))
        return entries

    def read_file(self, slug: str, filename: str) -> bytes:
        """Read the bytes of `filename` inside the opp dir. Rejects path traversal."""
        opp_dir, _ = self._resolve_opp_dir(slug)
        opp_root = opp_dir.resolve()
        target = (opp_dir / filename).resolve()
        if not target.is_relative_to(opp_root):
            raise ValueError(
                f"filename must be inside the opportunity directory: {filename}",
            )
        return target.read_bytes()
```

Notes:
- `is_file()` returns True for regular files, False for dirs, broken symlinks, etc.
- Hidden files are skipped by checking each path component for a leading `.`. This covers `.DS_Store`, `.git`, etc.
- `read_file`'s traversal check relies on `Path.resolve()` to follow symlinks and normalise `..`. After resolution, the target either lies under `opp_dir.resolve()` (accept) or it doesn't (reject). This catches all three vectors: literal `..`, absolute paths, and symlink escape.

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/application/test_query.py -v
```

Expected: all 20 tests pass (12 from Task 3 + 8 new).

Full suite:

```bash
uv run pytest -q
```

Expected: `167 passed`.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/query.py tests/application/test_query.py
git commit -m "feat(application): add OpportunityQuery.files and .read_file with traversal guard"
```

---

## Task 5: `OpportunityQuery.stats()`

**Goal:** Aggregate counts: funnel per `Status` (every Status present, absent → 0), sources count (`(unspecified)` for None). Filters apply.

**Files:**
- Modify: `src/jobhound/application/query.py`
- Modify: `tests/application/test_query.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/application/test_query.py`:

```python
from jobhound.application.snapshots import Stats


def test_stats_funnel_includes_every_status(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    stats = q.stats()
    assert isinstance(stats, Stats)
    # every Status value must appear in funnel
    assert set(stats.funnel.keys()) == set(Status)
    # acme is APPLIED, beta is SCREEN (gamma is archived, excluded by default)
    assert stats.funnel[Status.APPLIED] == 1
    assert stats.funnel[Status.SCREEN] == 1
    assert stats.funnel[Status.REJECTED] == 0


def test_stats_sources(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    stats = q.stats()
    assert stats.sources == {"LinkedIn": 1, "Referral": 1}


def test_stats_marks_unspecified_source(query_paths) -> None:
    # add a fourth opp with no source field
    new_dir = query_paths.opportunities_dir / "2026-05-no-source"
    new_dir.mkdir()
    (new_dir / "meta.toml").write_text(
        'company = "X"\nrole = "Y"\nslug = "2026-05-no-source"\n'
        'status = "applied"\npriority = "medium"\n',
    )
    q = OpportunityQuery(query_paths)
    stats = q.stats()
    assert stats.sources["(unspecified)"] == 1


def test_stats_respects_filters(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    stats = q.stats(Filters(statuses=frozenset({Status.APPLIED})))
    assert stats.funnel[Status.APPLIED] == 1
    assert stats.funnel[Status.SCREEN] == 0
    assert stats.sources == {"LinkedIn": 1}


def test_stats_include_archived(query_paths) -> None:
    q = OpportunityQuery(query_paths)
    stats = q.stats(Filters(include_archived=True))
    assert stats.funnel[Status.REJECTED] == 1  # gamma
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
uv run pytest tests/application/test_query.py -k stats -v
```

Expected: 5 tests fail with `AttributeError: ... has no attribute 'stats'`.

- [ ] **Step 3: Implement `stats` in `query.py`**

Add to `OpportunityQuery`:

```python
    def stats(self, filters: Filters = Filters()) -> Stats:
        """Aggregate counts over the (filtered) opportunity set."""
        snaps = self.list(filters, today=date.today())
        funnel: dict[Status, int] = {status: 0 for status in Status}
        sources: dict[str, int] = {}
        for snap in snaps:
            funnel[snap.opportunity.status] += 1
            key = snap.opportunity.source or "(unspecified)"
            sources[key] = sources.get(key, 0) + 1
        return Stats(funnel=funnel, sources=sources)
```

Add the import at the top of the file:

```python
from jobhound.application.snapshots import Stats
```

Note: `stats()` uses `date.today()` internally. The derived flags in `Stats` are not exposed (funnel/sources don't need `today`), but `self.list` requires it. A future daemon will likely want to pass `today` explicitly; that's a Phase 3b+ refactor.

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/application/test_query.py -v
```

Expected: all 25 tests pass.

Full suite:

```bash
uv run pytest -q
```

Expected: `172 passed`.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/query.py tests/application/test_query.py
git commit -m "feat(application): add OpportunityQuery.stats with funnel and sources"
```

---

## Task 6: `application/serialization.py` — single-object converters

**Goal:** Three pure functions that turn snapshot dataclasses into JSON-native dicts: `snapshot_to_dict`, `file_entry_to_dict`, `stats_to_dict`. No I/O. No `json.dumps`. Dates/Paths/Enums converted explicitly so the caller doesn't need a `default` hook.

**Files:**
- Create: `src/jobhound/application/serialization.py`
- Create: `tests/application/test_serialization.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/application/test_serialization.py`:

```python
"""Tests for application/serialization.py — JSON-native dict converters."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from jobhound.application.serialization import (
    SCHEMA_VERSION,
    file_entry_to_dict,
    snapshot_to_dict,
    stats_to_dict,
)
from jobhound.application.snapshots import (
    ComputedFlags,
    FileEntry,
    OpportunitySnapshot,
    Stats,
)
from jobhound.domain.contact import Contact
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status


def _snapshot(**opp_overrides: object) -> OpportunitySnapshot:
    base: dict[str, object] = dict(
        slug="2026-05-acme-em",
        company="Acme Corp",
        role="Engineering Manager",
        status=Status.APPLIED,
        priority=Priority.HIGH,
        source="LinkedIn",
        location="Remote, UK",
        comp_range=None,
        first_contact=None,
        applied_on=date(2026, 5, 3),
        last_activity=date(2026, 5, 10),
        next_action="Follow up",
        next_action_due=date(2026, 5, 17),
        tags=("remote", "fintech"),
    )
    base.update(opp_overrides)
    opp = Opportunity(**base)  # type: ignore[arg-type]
    return OpportunitySnapshot(
        opportunity=opp,
        archived=False,
        path=Path("/Users/test/.local/share/jh/opportunities/2026-05-acme-em"),
        computed=ComputedFlags(
            is_active=True, is_stale=False, looks_ghosted=False, days_since_activity=2,
        ),
    )


def test_schema_version_is_one() -> None:
    assert SCHEMA_VERSION == 1


def test_snapshot_to_dict_top_level_shape() -> None:
    snap = _snapshot()
    d = snapshot_to_dict(snap)

    # raw fields
    assert d["slug"] == "2026-05-acme-em"
    assert d["company"] == "Acme Corp"
    assert d["status"] == "applied"
    assert d["priority"] == "high"
    assert d["applied_on"] == "2026-05-03"
    assert d["last_activity"] == "2026-05-10"

    # archived + path
    assert d["archived"] is False
    assert d["path"] == "/Users/test/.local/share/jh/opportunities/2026-05-acme-em"

    # computed namespace
    assert d["computed"] == {
        "is_active": True,
        "is_stale": False,
        "looks_ghosted": False,
        "days_since_activity": 2,
    }


def test_snapshot_to_dict_omits_none_raw_fields() -> None:
    snap = _snapshot(comp_range=None, first_contact=None)
    d = snapshot_to_dict(snap)
    assert "comp_range" not in d
    assert "first_contact" not in d


def test_snapshot_to_dict_preserves_empty_collections() -> None:
    snap = _snapshot(tags=(), contacts=(), links={})
    d = snapshot_to_dict(snap)
    assert d["tags"] == []
    assert d["contacts"] == []
    assert d["links"] == {}


def test_snapshot_to_dict_serialises_contacts() -> None:
    snap = _snapshot(
        contacts=(Contact(name="Jane Doe", role="Recruiter", channel="email"),),
    )
    d = snapshot_to_dict(snap)
    assert d["contacts"] == [
        {"name": "Jane Doe", "role": "Recruiter", "channel": "email"},
    ]


def test_snapshot_to_dict_computed_days_can_be_null() -> None:
    snap = _snapshot()
    # replace computed with no last_activity
    snap = OpportunitySnapshot(
        opportunity=snap.opportunity,
        archived=snap.archived,
        path=snap.path,
        computed=ComputedFlags(
            is_active=True, is_stale=False, looks_ghosted=False, days_since_activity=None,
        ),
    )
    d = snapshot_to_dict(snap)
    assert d["computed"]["days_since_activity"] is None


def test_file_entry_to_dict() -> None:
    entry = FileEntry(
        name="correspondence/2026-05-01-intro.md",
        size=982,
        mtime=datetime(2026, 5, 1, 15, 33, 10, tzinfo=timezone.utc),
    )
    assert file_entry_to_dict(entry) == {
        "name": "correspondence/2026-05-01-intro.md",
        "size": 982,
        "mtime": "2026-05-01T15:33:10Z",
    }


def test_stats_to_dict_funnel_uses_string_keys() -> None:
    stats = Stats(
        funnel={Status.APPLIED: 3, Status.SCREEN: 1, Status.REJECTED: 0,
                Status.PROSPECT: 0, Status.INTERVIEW: 0, Status.OFFER: 0,
                Status.ACCEPTED: 0, Status.DECLINED: 0,
                Status.WITHDRAWN: 0, Status.GHOSTED: 0},
        sources={"LinkedIn": 4, "(unspecified)": 1},
    )
    d = stats_to_dict(stats)
    assert d["funnel"]["applied"] == 3
    assert d["funnel"]["screen"] == 1
    assert d["sources"] == {"LinkedIn": 4, "(unspecified)": 1}


def test_snapshot_to_dict_is_json_dumpable() -> None:
    """The whole point: no `default` hook needed."""
    import json

    snap = _snapshot(
        contacts=(Contact(name="J", role="R", channel="email"),),
        links={"posting": "https://x"},
    )
    text = json.dumps(snapshot_to_dict(snap))
    assert "2026-05-acme-em" in text
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
uv run pytest tests/application/test_serialization.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'jobhound.application.serialization'`.

- [ ] **Step 3: Implement `serialization.py` (converters only)**

Create `src/jobhound/application/serialization.py`:

```python
"""JSON-native dict converters for read-side snapshots.

Functions in this module return only JSON-native types (str, int, bool, None,
list, dict). Dates, datetimes, Path, and StrEnum values are converted
explicitly here so callers can use `json.dumps(...)` without a `default` hook.

This is the single source of truth for the wire shape. The CLI, the future
HTTP daemon, and any future export format share these helpers.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from jobhound.application.snapshots import (
    FileEntry,
    OpportunitySnapshot,
    Stats,
)

SCHEMA_VERSION: int = 1


def _date_or_none(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _datetime_to_z(value: datetime) -> str:
    """Format a tz-aware UTC datetime as ISO 8601 with `Z` suffix."""
    # value.isoformat() returns "+00:00"; replace with "Z" for spec compliance.
    return value.astimezone(tz=value.tzinfo).isoformat().replace("+00:00", "Z")


def snapshot_to_dict(snap: OpportunitySnapshot) -> dict[str, Any]:
    """Serialise an OpportunitySnapshot to JSON-native dict per the spec."""
    opp = snap.opportunity
    # raw fields — omit None, preserve empty collections
    raw: dict[str, Any] = {
        "slug": opp.slug,
        "company": opp.company,
        "role": opp.role,
        "status": opp.status.value,
        "priority": opp.priority.value,
        "source": opp.source,
        "location": opp.location,
        "comp_range": opp.comp_range,
        "first_contact": _date_or_none(opp.first_contact),
        "applied_on": _date_or_none(opp.applied_on),
        "last_activity": _date_or_none(opp.last_activity),
        "next_action": opp.next_action,
        "next_action_due": _date_or_none(opp.next_action_due),
    }
    out: dict[str, Any] = {k: v for k, v in raw.items() if v is not None}

    # empty collections preserved as empty containers
    out["tags"] = list(opp.tags)
    out["contacts"] = [
        {"name": c.name, "role": c.role, "channel": c.channel} for c in opp.contacts
    ]
    out["links"] = dict(opp.links)

    out["archived"] = snap.archived
    out["path"] = str(snap.path)
    out["computed"] = {
        "is_active": snap.computed.is_active,
        "is_stale": snap.computed.is_stale,
        "looks_ghosted": snap.computed.looks_ghosted,
        "days_since_activity": snap.computed.days_since_activity,
    }
    return out


def file_entry_to_dict(entry: FileEntry) -> dict[str, Any]:
    """Serialise a FileEntry to JSON-native dict."""
    return {
        "name": entry.name,
        "size": entry.size,
        "mtime": _datetime_to_z(entry.mtime),
    }


def stats_to_dict(stats: Stats) -> dict[str, Any]:
    """Serialise Stats to JSON-native dict with string status keys."""
    return {
        "funnel": {status.value: count for status, count in stats.funnel.items()},
        "sources": dict(stats.sources),
    }
```

Notes:
- `_datetime_to_z` handles the ISO `+00:00` → `Z` substitution. The spec's example shows `2026-05-12T14:23:45.121Z` — `datetime.isoformat()` produces the microsecond portion automatically if `microsecond != 0`.
- `Contact` is serialised inline (`{name, role, channel}`); we don't call `Contact.to_dict()` because the field order matters less than knowing exactly what's emitted from this module.
- Empty `tags`/`contacts`/`links` are emitted as `[]`/`[]`/`{}` per spec.

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/application/test_serialization.py -v
```

Expected: 9 tests pass.

Full suite:

```bash
uv run pytest -q
```

Expected: `181 passed`.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/serialization.py tests/application/test_serialization.py
git commit -m "feat(application): add JSON converters for snapshots and stats"
```

---

## Task 7: Envelope builders — `list_envelope`, `show_envelope`

**Goal:** Add the `schema_version` / `timestamp` / `db_root` envelope wrappers used by `jh export` and `jh show --json`. Test that the full envelope shape matches the spec exactly.

**Files:**
- Modify: `src/jobhound/application/serialization.py`
- Modify: `tests/application/test_serialization.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/application/test_serialization.py`:

```python
from jobhound.application.serialization import list_envelope, show_envelope


def test_list_envelope_shape() -> None:
    snap = _snapshot()
    ts = datetime(2026, 5, 12, 14, 23, 45, 121000, tzinfo=timezone.utc)
    db_root = Path("/Users/test/.local/share/jh")
    env = list_envelope([snap], timestamp=ts, db_root=db_root)
    assert env["schema_version"] == SCHEMA_VERSION
    assert env["timestamp"] == "2026-05-12T14:23:45.121000Z"
    assert env["db_root"] == "/Users/test/.local/share/jh"
    assert isinstance(env["opportunities"], list)
    assert env["opportunities"][0]["slug"] == "2026-05-acme-em"


def test_list_envelope_empty_opportunities() -> None:
    ts = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)
    env = list_envelope([], timestamp=ts, db_root=Path("/x"))
    assert env["opportunities"] == []


def test_show_envelope_uses_singular_key() -> None:
    snap = _snapshot()
    ts = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)
    env = show_envelope(snap, timestamp=ts, db_root=Path("/x"))
    assert "opportunity" in env
    assert "opportunities" not in env
    assert env["opportunity"]["slug"] == "2026-05-acme-em"


def test_envelopes_are_json_dumpable() -> None:
    import json

    snap = _snapshot()
    ts = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)
    list_text = json.dumps(list_envelope([snap], timestamp=ts, db_root=Path("/x")))
    show_text = json.dumps(show_envelope(snap, timestamp=ts, db_root=Path("/x")))
    assert "2026-05-acme-em" in list_text
    assert "2026-05-acme-em" in show_text
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
uv run pytest tests/application/test_serialization.py -v
```

Expected: 4 envelope tests fail with `ImportError` on `list_envelope` / `show_envelope`.

- [ ] **Step 3: Implement the envelope builders**

Append to `src/jobhound/application/serialization.py`:

```python
from pathlib import Path


def list_envelope(
    snapshots: list[OpportunitySnapshot],
    *,
    timestamp: datetime,
    db_root: Path,
) -> dict[str, Any]:
    """Build the bulk-export envelope (jh export)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": _datetime_to_z(timestamp),
        "db_root": str(db_root),
        "opportunities": [snapshot_to_dict(s) for s in snapshots],
    }


def show_envelope(
    snapshot: OpportunitySnapshot,
    *,
    timestamp: datetime,
    db_root: Path,
) -> dict[str, Any]:
    """Build the single-opportunity envelope (jh show --json)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "timestamp": _datetime_to_z(timestamp),
        "db_root": str(db_root),
        "opportunity": snapshot_to_dict(snapshot),
    }
```

Move the `from pathlib import Path` to the top imports (next to `from typing import Any`) and remove the inline import inside the new code block. This is a small cleanup — the function bodies don't need it because they don't manipulate `Path`, only stringify.

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/application/test_serialization.py -v
```

Expected: 13 tests pass.

Full suite:

```bash
uv run pytest -q
```

Expected: `185 passed`.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/serialization.py tests/application/test_serialization.py
git commit -m "feat(application): add list_envelope and show_envelope builders"
```

---

## Task 8: `jh show <slug> [--json]`

**Goal:** Wire up the first read-API CLI command. Default output: human-readable text. `--json`: pretty-printed envelope on stdout. Slug resolution uses the existing `resolve_slug`. Unknown slug → exit 2 with `jh: no opportunity matches: <query>` on stderr.

**Files:**
- Create: `src/jobhound/commands/show.py`
- Modify: `src/jobhound/cli.py` (register `show`)
- Create: `tests/commands/__init__.py` (empty)
- Create: `tests/commands/test_cmd_show.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/commands/__init__.py` (empty) and `tests/commands/test_cmd_show.py`:

```python
"""Tests for `jh show` (Task 8)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _seed_opp(db_path: Path, slug: str = "2026-05-acme-em") -> Path:
    """Seed one opportunity and return its dir."""
    opp_dir = db_path / "opportunities" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "correspondence").mkdir()
    (opp_dir / "meta.toml").write_text(
        f'company = "Acme"\nrole = "EM"\nslug = "{slug}"\n'
        'status = "applied"\npriority = "high"\nsource = "LinkedIn"\n'
        'applied_on = 2026-05-01\nlast_activity = 2026-05-11\n'
        'tags = ["remote"]\n',
    )
    (opp_dir / "notes.md").write_text("notes\n")
    subprocess.run(
        ["git", "-C", str(db_path), "add", "."], check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "-m", "seed", "--quiet"],
        check=True, capture_output=True,
    )
    return opp_dir


def test_show_human_output_contains_company_status_path(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme"])
    assert result.exit_code == 0
    assert "Acme" in result.output
    assert "EM" in result.output
    assert "applied" in result.output.lower()
    assert "2026-05-acme-em" in result.output


def test_show_human_lists_files(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme"])
    assert "notes.md" in result.output
    assert "meta.toml" in result.output


def test_show_json_output_is_envelope(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme", "--json"])
    assert result.exit_code == 0
    # extract pure JSON from output (capsys may include trailing newline)
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert "timestamp" in payload
    assert payload["db_root"] == str(tmp_jh.db_path)
    assert payload["opportunity"]["slug"] == "2026-05-acme-em"
    assert payload["opportunity"]["computed"]["is_active"] is True


def test_show_unknown_slug_exits_2(tmp_jh, invoke) -> None:
    result = invoke(["show", "nonexistent"])
    assert result.exit_code == 2
    assert "no opportunity matches" in result.output


def test_show_resolves_substring(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path, slug="2026-05-acme-em")
    result = invoke(["show", "acme"])
    assert result.exit_code == 0
    assert "2026-05-acme-em" in result.output
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
uv run pytest tests/commands/test_cmd_show.py -v
```

Expected: 5 tests fail. Either `cyclopts` reports "unknown command 'show'" or imports fail.

- [ ] **Step 3: Implement `commands/show.py`**

Create `src/jobhound/commands/show.py`:

```python
"""`jh show <slug>` — print one opportunity in human text or JSON."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import OpportunityQuery
from jobhound.application.serialization import show_envelope
from jobhound.application.snapshots import FileEntry, OpportunitySnapshot
from jobhound.domain.slug import AmbiguousSlugError, SlugNotFoundError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    slug: str,
    /,
    *,
    json_out: Annotated[bool, Parameter(name=["--json"])] = False,
) -> None:
    """Show one opportunity. Defaults to human text; `--json` for the envelope."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)
    try:
        snap = query.find(slug, today=date.today())
    except SlugNotFoundError:
        print(f"jh: no opportunity matches: {slug}", file=sys.stderr)
        raise SystemExit(2)
    except AmbiguousSlugError as exc:
        print(f"jh: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if json_out:
        envelope = show_envelope(
            snap, timestamp=datetime.now(timezone.utc), db_root=paths.db_root,
        )
        print(json.dumps(envelope, indent=2))
    else:
        _print_human(snap, query.files(snap.opportunity.slug))


def _print_human(snap: OpportunitySnapshot, files: list[FileEntry]) -> None:
    opp = snap.opportunity
    print(f"{opp.company} — {opp.role}  ({opp.slug})")
    print()
    print(f"  Status:        {opp.status.value}")
    print(f"  Priority:      {opp.priority.value}")
    if opp.applied_on is not None:
        print(f"  Applied:       {opp.applied_on.isoformat()}")
    if opp.last_activity is not None:
        print(f"  Last activity: {opp.last_activity.isoformat()}")
    if snap.computed.days_since_activity is not None:
        print(f"  Days quiet:    {snap.computed.days_since_activity}")
    if opp.next_action is not None:
        due = (
            f" (due {opp.next_action_due.isoformat()})"
            if opp.next_action_due is not None else ""
        )
        print(f"  Next action:   {opp.next_action}{due}")
    if opp.tags:
        print(f"  Tags:          {', '.join(opp.tags)}")
    if opp.source is not None:
        print(f"  Source:        {opp.source}")
    if opp.location is not None:
        print(f"  Location:      {opp.location}")
    if opp.comp_range is not None:
        print(f"  Comp:          {opp.comp_range}")
    if opp.contacts:
        print()
        print("  Contacts:")
        for c in opp.contacts:
            line = f"    {c.name}"
            if c.role:
                line += f" ({c.role})"
            if c.channel:
                line += f" — {c.channel}"
            print(line)
    if opp.links:
        print()
        print("  Links:")
        for name, url in opp.links.items():
            print(f"    {name}: {url}")
    if files:
        print()
        print("  Files:")
        for entry in files:
            print(f"    {entry.name}  ({entry.size} bytes)")
    print()
    print(f"  Path: {snap.path}")
```

Register the command in `src/jobhound/cli.py`. Add the import next to the others:

```python
from jobhound.commands import show as cmd_show
```

And after the existing `app.command(...)` lines:

```python
app.command(cmd_show.run, name="show")
```

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/commands/test_cmd_show.py -v
```

Expected: 5 tests pass.

Full suite:

```bash
uv run pytest -q
```

Expected: `190 passed`.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/commands/show.py src/jobhound/cli.py tests/commands/__init__.py tests/commands/test_cmd_show.py
git commit -m "feat(cli): add jh show command with --json output"
```

---

## Task 9: `jh export`

**Goal:** Bulk export a JSON envelope to stdout with filter flags: `--status` (multi), `--priority` (multi), `--slug` (substring), `--active-only`, `--include-archived`. Filters AND across dimensions; values OR within a dimension.

**Files:**
- Create: `src/jobhound/commands/export.py`
- Modify: `src/jobhound/cli.py` (register `export`)
- Create: `tests/commands/test_cmd_export.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/commands/test_cmd_export.py`:

```python
"""Tests for `jh export` (Task 9)."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path


def _seed(db_path: Path, slug: str, *, status: str, priority: str, source: str) -> None:
    opp_dir = db_path / "opportunities" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "correspondence").mkdir()
    (opp_dir / "meta.toml").write_text(
        f'company = "X"\nrole = "Y"\nslug = "{slug}"\n'
        f'status = "{status}"\npriority = "{priority}"\nsource = "{source}"\n'
        f'applied_on = 2026-05-01\nlast_activity = 2026-05-11\n',
    )


def _seed_archived(db_path: Path, slug: str) -> None:
    opp_dir = db_path / "archive" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "meta.toml").write_text(
        f'company = "A"\nrole = "Z"\nslug = "{slug}"\n'
        'status = "rejected"\npriority = "low"\n',
    )


def _seed_all(db_path: Path) -> None:
    _seed(db_path, "2026-05-acme",    status="applied", priority="high",   source="LinkedIn")
    _seed(db_path, "2026-04-beta",    status="screen",  priority="medium", source="Referral")
    _seed(db_path, "2026-05-charlie", status="applied", priority="low",    source="LinkedIn")
    _seed_archived(db_path, "2026-03-delta")
    subprocess.run(["git", "-C", str(db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "-m", "seed", "--quiet"],
        check=True, capture_output=True,
    )


def test_export_default_returns_all_non_archived(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert slugs == ["2026-04-beta", "2026-05-acme", "2026-05-charlie"]


def test_export_envelope_metadata(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export"])
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert "timestamp" in payload
    assert payload["db_root"] == str(tmp_jh.db_path)


def test_export_filter_by_status_comma_separated(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--status", "applied,screen"])
    payload = json.loads(result.output)
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert slugs == ["2026-04-beta", "2026-05-acme", "2026-05-charlie"]


def test_export_filter_by_status_repeated(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--status", "applied", "--status", "screen"])
    payload = json.loads(result.output)
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert slugs == ["2026-04-beta", "2026-05-acme", "2026-05-charlie"]


def test_export_filter_by_priority(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--priority", "high"])
    payload = json.loads(result.output)
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert slugs == ["2026-05-acme"]


def test_export_filter_by_slug_substring(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--slug", "acme"])
    payload = json.loads(result.output)
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert slugs == ["2026-05-acme"]


def test_export_active_only(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--active-only", "--include-archived"])
    payload = json.loads(result.output)
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert "2026-03-delta" not in slugs  # rejected is terminal


def test_export_include_archived(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--include-archived"])
    payload = json.loads(result.output)
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert "2026-03-delta" in slugs
    archived = {o["slug"]: o["archived"] for o in payload["opportunities"]}
    assert archived["2026-03-delta"] is True
    assert archived["2026-05-acme"] is False


def test_export_filters_and_across_dimensions(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    # applied AND high = only acme
    result = invoke(["export", "--status", "applied", "--priority", "high"])
    payload = json.loads(result.output)
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert slugs == ["2026-05-acme"]


def test_export_invalid_status_exits_2(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--status", "bogus"])
    assert result.exit_code == 2


def test_export_empty_result_still_exits_0(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--slug", "no-match"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["opportunities"] == []
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
uv run pytest tests/commands/test_cmd_export.py -v
```

Expected: all 11 tests fail (unknown command).

- [ ] **Step 3: Implement `commands/export.py`**

Create `src/jobhound/commands/export.py`:

```python
"""`jh export` — emit a JSON envelope of opportunities to stdout."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.application.serialization import list_envelope
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    *,
    status: Annotated[list[str], Parameter(name=["--status"])] = [],
    priority: Annotated[list[str], Parameter(name=["--priority"])] = [],
    slug: Annotated[str | None, Parameter(name=["--slug"])] = None,
    active_only: Annotated[bool, Parameter(name=["--active-only"])] = False,
    include_archived: Annotated[bool, Parameter(name=["--include-archived"])] = False,
) -> None:
    """Emit a JSON envelope of all matching opportunities."""
    try:
        statuses = frozenset(Status(s) for s in _split(status))
        priorities = frozenset(Priority(p) for p in _split(priority))
    except ValueError as exc:
        print(f"jh: {exc}", file=sys.stderr)
        raise SystemExit(2)

    filters = Filters(
        statuses=statuses,
        priorities=priorities,
        slug_substring=slug,
        active_only=active_only,
        include_archived=include_archived,
    )
    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)
    snaps = query.list(filters, today=date.today())
    envelope = list_envelope(
        snaps, timestamp=datetime.now(timezone.utc), db_root=paths.db_root,
    )
    print(json.dumps(envelope, indent=2))


def _split(raw: list[str]) -> list[str]:
    """Accept comma-separated OR repeated flags, returning a flat list of values."""
    out: list[str] = []
    for chunk in raw:
        for token in chunk.split(","):
            token = token.strip()
            if token:
                out.append(token)
    return out
```

Register in `src/jobhound/cli.py`:

```python
from jobhound.commands import export as cmd_export
```

And:

```python
app.command(cmd_export.run, name="export")
```

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/commands/test_cmd_export.py -v
```

Expected: 11 tests pass.

Full suite:

```bash
uv run pytest -q
```

Expected: `201 passed`.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/commands/export.py src/jobhound/cli.py tests/commands/test_cmd_export.py
git commit -m "feat(cli): add jh export command with filter flags"
```

---

## Task 10: Drop `PICKUP.md` and update README

**Goal:** Remove the pickup notes (Phase 3a is now in flight; PICKUP.md is obsolete) and add a brief mention of `jh show` and `jh export` in the README's command list.

**Files:**
- Delete: `PICKUP.md`
- Modify: `README.md`

- [ ] **Step 1: Read README to find the command list**

```bash
rg -n "^\s*[#\-*] *(jh |`jh)" README.md
```

Locate the section that lists the existing commands (likely a bullet list under "Usage" or "Commands").

- [ ] **Step 2: Add `jh show` and `jh export` to the README's command list**

Edit `README.md`. After the last existing command entry (probably `jh sync` or `jh delete`), add:

```markdown
- `jh show <slug>` — print one opportunity. `--json` for machine-readable output.
- `jh export` — emit a JSON envelope of all opportunities to stdout. Filter flags: `--status`, `--priority`, `--slug`, `--active-only`, `--include-archived`.
```

Match the surrounding bullet style (some READMEs use `*` or no bullet; preserve the existing convention).

- [ ] **Step 3: Remove `PICKUP.md`**

```bash
git rm PICKUP.md
```

- [ ] **Step 4: Run the full test suite + lint**

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
```

Expected: `201 passed`, zero lint findings.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document jh show + jh export and drop phase 3a pickup notes"
```

---

## After Task 10

- The branch `feat/phase3-read-api-design` contains: the spec commit (already there), the reorg commit, eight feature commits, and the docs commit.
- Open a PR titled `feat(application): phase 3a — read API (jh show + jh export)` against `main`. The PR description should summarise: DDD reorg + library + two CLI commands, stdlib only, X tests added (count the diff).
- Once merged, release-please will propose the next minor bump (likely 0.4.0) on its long-lived Release PR.

## Spec → Task crosswalk

For an at-a-glance check that every spec requirement has a home:

| Spec section | Task |
|---|---|
| DDD subpackage split (§Architecture / DDD layer split) | 1 |
| `Filters` dataclass (§Library API) | 3 |
| `OpportunityQuery.__init__(paths)` no git side-effects (§CQRS) | 3 |
| `OpportunityQuery.list / find` (§Library API) | 3 |
| `OpportunityQuery.files / read_file` + traversal guard (§Library API + §Error handling) | 4 |
| `OpportunityQuery.stats` (§Library API + §JSON shape — stats) | 5 |
| `ComputedFlags`, `OpportunitySnapshot`, `FileEntry`, `Stats` (§snapshots) | 2 |
| `snapshot_to_dict`, `file_entry_to_dict`, `stats_to_dict` (§serialization) | 6 |
| `list_envelope`, `show_envelope` + `SCHEMA_VERSION` (§serialization) | 7 |
| `jh show <slug> [--json]` (§CLI commands) | 8 |
| `jh export` filters (§CLI commands) | 9 |
| Empty collections preserved (§Field rules) | 6 |
| None raw fields omitted (§Field rules) | 6 |
| `computed` block always present (§Field rules) | 2, 6 |
| Path traversal rejection (§Error handling) | 4 |
| Unknown slug exit code 2 (§Error handling) | 8 |
| Invalid status exit code 2 (§Error handling) | 9 |
