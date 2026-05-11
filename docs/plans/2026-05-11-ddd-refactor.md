# DDD Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `jh` around Domain-Driven Design building blocks: introduce an `OpportunityRepository`, push behaviour onto the `Opportunity` aggregate root, and replace stringly-typed primitives (`Status`, `Priority`, `Slug`, `Contact`) with value objects. End state: command handlers are thin shells (parse args → call entity method → save); domain rules and invariants live in `Opportunity` and the value objects.

**Architecture:** Four self-contained phases. Phase 1 introduces `OpportunityRepository` and migrates every command to it (eliminates an 11-fold `resolve_slug → read_meta → mutate → write_meta → commit_change` idiom). Phase 2 adds behaviour methods to `Opportunity` (`apply`, `log_interaction`, `withdraw`, `ghost`, `accept`, `decline`, `touch`, `with_tags`, `with_priority`, `with_contact`, `with_link`) so each command becomes ~12 lines. Phase 3 introduces a `Status` enum and folds the transition rules onto it. Phase 4 introduces `Priority`, `Slug`, and `Contact` value objects. Each phase produces working, fully-tested software and is independently committable; you may stop at any phase boundary.

**Tech stack:** Python 3.13, `cyclopts`, `questionary`, `tomllib` + `tomli-w`, `pytest`, `ruff`, `ty`, `prek`.

**Reference audit:** Conversation on 2026-05-11 — DDD audit of `jh` CLI. See `src/jobhound/opportunities.py`, `src/jobhound/transitions.py`, and the 17 files under `src/jobhound/commands/`.

**On-disk format:** Unchanged. `meta.toml` round-trips identically through every phase. The plan introduces serialization adapters where needed.

**Test discipline:** This is a refactor — the existing test suite (24 test files under `tests/`) is the regression net. Before each phase, run `uv run pytest -q` to establish a green baseline. Add new tests **only** for net-new public APIs (e.g. `Status.is_active`, `Opportunity.apply`). Do not delete existing tests — they validate that behaviour didn't change.

---

## Phase 1 — `OpportunityRepository`

**Goal:** Collapse the duplicated `resolve_slug → read_meta → mutate → write_meta → commit_change` idiom (currently in 11 commands) into one repository class. After Phase 1, every command body shrinks ~30%.

### Task 1: Create `OpportunityRepository`

**Files:**
- Create: `/Users/robin/code/github/yo61/jobhound/src/jobhound/repository.py`
- Create: `/Users/robin/code/github/yo61/jobhound/tests/test_repository.py`

- [ ] **Step 1: Baseline — full suite must be green**

Run: `uv run pytest -q`
Expected: all tests pass. If any fail, fix before proceeding.

- [ ] **Step 2: Write the failing tests for `OpportunityRepository`**

Create `/Users/robin/code/github/yo61/jobhound/tests/test_repository.py`:

```python
"""Tests for OpportunityRepository — the persistence + git-commit surface."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from jobhound.config import Config
from jobhound.opportunities import Opportunity
from jobhound.paths import Paths, paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.slug import SlugNotFoundError


def _make_config(tmp_path: Path) -> Config:
    return Config(db_path=tmp_path / "db", auto_commit=False, editor="")


def _make_opp(slug: str = "2026-05-acme-eng") -> Opportunity:
    return Opportunity(
        slug=slug,
        company="Acme",
        role="Engineer",
        status="prospect",
        priority="medium",
        source=None,
        location=None,
        comp_range=None,
        first_contact=date(2026, 5, 1),
        applied_on=None,
        last_activity=date(2026, 5, 1),
        next_action="follow up",
        next_action_due=date(2026, 5, 8),
    )


def test_create_writes_meta_and_scaffolds_artefacts(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    opp = _make_opp()
    opp_dir = repo.create(opp, message=f"new: {opp.slug}", no_commit=True)

    assert opp_dir.name == opp.slug
    assert (opp_dir / "meta.toml").is_file()
    assert (opp_dir / "notes.md").is_file()
    assert (opp_dir / "research.md").is_file()
    assert (opp_dir / "correspondence").is_dir()


def test_find_returns_opp_and_dir(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)

    opp, opp_dir = repo.find("acme")
    assert opp.company == "Acme"
    assert opp_dir.name == "2026-05-acme-eng"


def test_find_raises_when_missing(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    with pytest.raises(SlugNotFoundError):
        repo.find("nope")


def test_save_persists_changes(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    opp, opp_dir = repo.find("acme")

    updated = replace(opp, priority="high")
    repo.save(updated, opp_dir, message="priority: acme high", no_commit=True)

    reloaded, _ = repo.find("acme")
    assert reloaded.priority == "high"


def test_save_renames_dir_when_slug_changes(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    opp, opp_dir = repo.find("acme")

    renamed = replace(opp, slug="2026-05-acme-senior-eng")
    new_dir = repo.save(renamed, opp_dir, message="edit", no_commit=True)

    assert not opp_dir.exists()
    assert new_dir.name == "2026-05-acme-senior-eng"
    assert (new_dir / "meta.toml").is_file()


def test_save_rejects_rename_collision(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp("2026-05-acme-eng"), message="new", no_commit=True)
    repo.create(_make_opp("2026-05-beta-eng"), message="new", no_commit=True)
    opp, opp_dir = repo.find("acme")

    collision = replace(opp, slug="2026-05-beta-eng")
    with pytest.raises(FileExistsError):
        repo.save(collision, opp_dir, message="edit", no_commit=True)


def test_all_iterates_opportunities(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp("2026-05-acme-eng"), message="new", no_commit=True)
    repo.create(_make_opp("2026-05-beta-eng"), message="new", no_commit=True)

    slugs = sorted(o.slug for o in repo.all())
    assert slugs == ["2026-05-acme-eng", "2026-05-beta-eng"]


def test_archive_moves_dir(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    _, opp_dir = repo.find("acme")

    repo.archive(opp_dir, no_commit=True)
    assert not opp_dir.exists()
    assert (paths.archive_dir / "2026-05-acme-eng" / "meta.toml").is_file()


def test_delete_removes_dir(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new", no_commit=True)
    _, opp_dir = repo.find("acme")

    repo.delete(opp_dir, no_commit=True)
    assert not opp_dir.exists()
```

- [ ] **Step 3: Run tests — expect ModuleNotFoundError**

Run: `uv run pytest tests/test_repository.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'jobhound.repository'`

- [ ] **Step 4: Implement `OpportunityRepository`**

Create `/Users/robin/code/github/yo61/jobhound/src/jobhound/repository.py`:

```python
"""OpportunityRepository — the single persistence + git-commit surface.

Wraps `slug.resolve_slug`, `meta_io.{read,write}_meta`, `git.{ensure_repo,
commit_change}`, plus the on-disk skeleton scaffolding and rename/archive/
delete moves. Every command goes through this class; nothing else should
call meta_io directly.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

from jobhound.config import Config
from jobhound.git import commit_change, ensure_repo
from jobhound.meta_io import read_meta, write_meta
from jobhound.opportunities import Opportunity
from jobhound.paths import Paths
from jobhound.slug import resolve_slug


class OpportunityRepository:
    """Persistence + git-commit surface for `Opportunity` aggregates."""

    def __init__(self, paths: Paths, cfg: Config) -> None:
        self.paths = paths
        self.cfg = cfg
        ensure_repo(self.paths.db_root)

    def find(self, slug_query: str) -> tuple[Opportunity, Path]:
        """Resolve `slug_query` and return (Opportunity, opp_dir)."""
        opp_dir = resolve_slug(slug_query, self.paths.opportunities_dir)
        opp = read_meta(opp_dir / "meta.toml")
        return opp, opp_dir

    def all(self) -> Iterator[Opportunity]:
        """Yield every Opportunity under `opportunities_dir`, sorted by slug."""
        if not self.paths.opportunities_dir.exists():
            return
        for sub in sorted(self.paths.opportunities_dir.iterdir()):
            if not sub.is_dir():
                continue
            yield read_meta(sub / "meta.toml")

    def create(self, opp: Opportunity, *, message: str, no_commit: bool = False) -> Path:
        """Scaffold a new opportunity directory and write `opp`."""
        opp_dir = self.paths.opportunities_dir / opp.slug
        if opp_dir.exists():
            raise FileExistsError(f"opportunity already exists: {opp_dir}")
        opp_dir.mkdir(parents=True)
        (opp_dir / "notes.md").write_text("")
        (opp_dir / "research.md").write_text(
            "# Research\n\n## Company\n\n## Role\n\n## Why apply\n\n## Why not\n"
        )
        (opp_dir / "correspondence").mkdir()
        write_meta(opp, opp_dir / "meta.toml")
        self._commit(message, no_commit=no_commit)
        return opp_dir

    def save(
        self,
        opp: Opportunity,
        opp_dir: Path,
        *,
        message: str,
        no_commit: bool = False,
    ) -> Path:
        """Persist `opp`. Renames the directory if `opp.slug` no longer matches."""
        if opp_dir.name != opp.slug:
            dst = opp_dir.parent / opp.slug
            if dst.exists():
                raise FileExistsError(f"target folder already exists: {dst}")
            opp_dir.rename(dst)
            opp_dir = dst
        write_meta(opp, opp_dir / "meta.toml")
        self._commit(message, no_commit=no_commit)
        return opp_dir

    def archive(self, opp_dir: Path, *, no_commit: bool = False) -> None:
        """Move `opp_dir` from opportunities/ to archive/."""
        dst = self.paths.archive_dir / opp_dir.name
        if dst.exists():
            raise FileExistsError(f"archive target already exists: {dst}")
        self.paths.archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(opp_dir), str(dst))
        self._commit(f"archive: {opp_dir.name}", no_commit=no_commit)

    def delete(self, opp_dir: Path, *, no_commit: bool = False) -> None:
        """Remove `opp_dir` from disk."""
        name = opp_dir.name
        shutil.rmtree(opp_dir)
        self._commit(f"delete: {name}", no_commit=no_commit)

    def _commit(self, message: str, *, no_commit: bool) -> None:
        commit_change(
            self.paths.db_root,
            message,
            enabled=self.cfg.auto_commit and not no_commit,
        )
```

- [ ] **Step 5: Run new tests — expect green**

Run: `uv run pytest tests/test_repository.py -q`
Expected: all 9 tests pass.

- [ ] **Step 6: Run full suite — should still be green**

Run: `uv run pytest -q`
Expected: original tests + 9 new repository tests all pass.

- [ ] **Step 7: Commit**

```bash
git add src/jobhound/repository.py tests/test_repository.py
git commit -m "Add OpportunityRepository"
```

---

### Task 2: Migrate `apply`, `note`, `tag`, `priority`, `link`, `contact` to repo

These six commands share the same exact shape: load → mutate via `replace` → save. Migrate them as one task — each command is a tiny diff.

**Files:**
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/apply.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/note.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/tag.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/priority.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/link.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/contact.py`

- [ ] **Step 1: Migrate `apply.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/apply.py` with:

```python
"""`jh apply` — submitted application, status → applied."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError, require_transition


def run(
    slug_query: str,
    /,
    *,
    on: str | None = None,
    next_action: str,
    next_action_due: str,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Mark the application as submitted."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)

    today_date = date.fromisoformat(today) if today else date.today()
    applied_on = date.fromisoformat(on) if on else today_date
    due = date.fromisoformat(next_action_due)

    opp, opp_dir = repo.find(slug_query)
    try:
        require_transition(opp.status, "applied", verb="apply")
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    updated = replace(
        opp,
        status="applied",
        applied_on=applied_on,
        last_activity=today_date,
        next_action=next_action,
        next_action_due=due,
    )
    repo.save(updated, opp_dir, message=f"apply: {opp.slug}", no_commit=no_commit)
    print(f"applied: {opp.slug}")
```

- [ ] **Step 2: Migrate `note.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/note.py` with:

```python
"""`jh note` — append a timestamped one-liner to notes.md."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    msg: str,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Append a timestamped one-liner to <slug>/notes.md and bump last_activity."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()

    opp, opp_dir = repo.find(slug_query)
    notes = opp_dir / "notes.md"
    existing = notes.read_text() if notes.exists() else ""
    notes.write_text(existing + f"- {today_date.isoformat()} {msg}\n")

    updated = replace(opp, last_activity=today_date)
    repo.save(updated, opp_dir, message=f"note: {opp.slug}", no_commit=no_commit)
    print(f"noted: {opp.slug}")
```

- [ ] **Step 3: Migrate `tag.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/tag.py` with:

```python
"""`jh tag` — add and/or remove tags."""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add and/or remove tags."""
    add_set = set(add or [])
    remove_set = set(remove or [])
    if not add_set and not remove_set:
        print("nothing to do; pass --add and/or --remove", file=sys.stderr)
        raise SystemExit(1)

    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    tags = tuple(sorted((set(opp.tags) | add_set) - remove_set))
    updated = replace(opp, tags=tags)

    summary = " ".join(
        [*(f"+{t}" for t in sorted(add_set)), *(f"-{t}" for t in sorted(remove_set))]
    )
    repo.save(updated, opp_dir, message=f"tag: {opp.slug} {summary}", no_commit=no_commit)
    print(f"tags {opp.slug}: {tags}")
```

- [ ] **Step 4: Migrate `priority.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/priority.py` with:

```python
"""`jh priority` — set priority to high/medium/low."""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository

_VALID = {"high", "medium", "low"}


def run(
    slug_query: str,
    /,
    *,
    to: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Set the priority of an opportunity."""
    if to not in _VALID:
        print(f"--to must be one of {sorted(_VALID)}", file=sys.stderr)
        raise SystemExit(1)
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = replace(opp, priority=to)
    repo.save(updated, opp_dir, message=f"priority: {opp.slug} {to}", no_commit=no_commit)
    print(f"priority {opp.slug}: {to}")
```

- [ ] **Step 5: Migrate `link.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/link.py` with:

```python
"""`jh link` — add or update an entry in the links table."""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    name: str,
    url: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add or update a link."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    links = dict(opp.links)
    links[name] = url
    updated = replace(opp, links=links)
    repo.save(updated, opp_dir, message=f"link: {opp.slug} {name}", no_commit=no_commit)
    print(f"link {opp.slug}: {name} = {url}")
```

- [ ] **Step 6: Migrate `contact.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/contact.py` with:

```python
"""`jh contact` — append a contact entry."""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    name: str,
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add a contact to the contacts list."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    entry: dict[str, str] = {"name": name}
    if role_title is not None:
        entry["role"] = role_title
    if channel is not None:
        entry["channel"] = channel
    if company is not None:
        entry["company"] = company
    if note is not None:
        entry["note"] = note
    updated = replace(opp, contacts=(*opp.contacts, entry))
    repo.save(updated, opp_dir, message=f"contact: {opp.slug} {name}", no_commit=no_commit)
    print(f"contact added: {opp.slug} {name}")
```

- [ ] **Step 7: Run full suite — should still be green**

Run: `uv run pytest -q`
Expected: all tests pass. If a command-level test fails, the migration is wrong — diff the new file against the old one to find the discrepancy.

- [ ] **Step 8: Commit**

```bash
git add src/jobhound/commands/apply.py src/jobhound/commands/note.py src/jobhound/commands/tag.py src/jobhound/commands/priority.py src/jobhound/commands/link.py src/jobhound/commands/contact.py
git commit -m "Migrate apply/note/tag/priority/link/contact to OpportunityRepository"
```

---

### Task 3: Migrate `log` and `_terminal` (covers withdraw/ghost/accept/decline)

**Files:**
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/log.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/_terminal.py`

- [ ] **Step 1: Migrate `log.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/log.py` with:

```python
"""`jh log` — record an interaction; default next status advances one stage."""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError, require_transition

_NAME_SLUG = re.compile(r"[^a-z0-9]+")


def _name_slug(who: str) -> str:
    return _NAME_SLUG.sub("-", who.lower()).strip("-") or "unknown"


def _correspondence_filename(when: date, channel: str, direction: str, who: str) -> str:
    return f"{when.isoformat()}-{channel}-{direction}-{_name_slug(who)}.md"


def run(
    slug_query: str,
    /,
    *,
    channel: str,
    direction: str,
    who: str,
    body: Path,
    next_status: str = "stay",
    next_action: str | None = None,
    next_action_due: str | None = None,
    force: bool = False,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Record an interaction (correspondence) and update status + next action."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()

    if direction not in {"from", "to"}:
        print(f"--direction must be 'from' or 'to', got {direction!r}", file=sys.stderr)
        raise SystemExit(1)
    if not body.is_file():
        print(f"--body file not found: {body}", file=sys.stderr)
        raise SystemExit(1)

    opp, opp_dir = repo.find(slug_query)

    if not force:
        try:
            require_transition(opp.status, next_status, verb="log")
        except InvalidTransitionError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc

    corr_dir = opp_dir / "correspondence"
    corr_dir.mkdir(exist_ok=True)
    corr_path = corr_dir / _correspondence_filename(today_date, channel, direction, who)
    corr_path.write_text(body.read_text())

    new_status = opp.status if next_status == "stay" else next_status
    due = date.fromisoformat(next_action_due) if next_action_due else opp.next_action_due
    action = next_action if next_action is not None else opp.next_action

    updated = replace(
        opp,
        status=new_status,
        last_activity=today_date,
        next_action=action,
        next_action_due=due,
    )
    arrow = f"{opp.status} → {new_status}" if new_status != opp.status else "(no status change)"
    repo.save(updated, opp_dir, message=f"log: {opp.slug} {arrow}", no_commit=no_commit)
    print(f"logged: {opp.slug} {arrow}")
```

- [ ] **Step 2: Migrate `_terminal.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/_terminal.py` with:

```python
"""Shared logic for terminal-status verbs (withdraw, ghost, accept, decline)."""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError, require_transition


def run_transition(
    *,
    slug_query: str,
    verb: str,
    target_status: str,
    today: str | None,
    no_commit: bool,
) -> None:
    """Move an opportunity to `target_status`. Used by withdraw/ghost/accept/decline."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()
    opp, opp_dir = repo.find(slug_query)

    try:
        require_transition(opp.status, target_status, verb=verb)
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    updated = replace(opp, status=target_status, last_activity=today_date)
    repo.save(updated, opp_dir, message=f"{verb}: {opp.slug}", no_commit=no_commit)
    print(f"{verb}: {opp.slug}")
```

- [ ] **Step 3: Run full suite**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/jobhound/commands/log.py src/jobhound/commands/_terminal.py
git commit -m "Migrate log and terminal-status verbs to OpportunityRepository"
```

---

### Task 4: Migrate `new`, `archive`, `delete`, `edit`, `list`

These commands use the special-purpose repo methods (`create`, `archive`, `delete`) or iterate (`all`).

**Files:**
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/new.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/archive.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/delete.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/edit.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/list_.py`

- [ ] **Step 1: Migrate `new.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/new.py` with:

```python
"""`jh new` — scaffold a new opportunity at status `prospect`."""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.opportunities import Opportunity
from jobhound.paths import Paths, paths_from_config
from jobhound.repository import OpportunityRepository

_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_BAD.sub("-", text.lower()).strip("-")
    return s or "untitled"


def _build_slug(today: date, company: str, role: str) -> str:
    return f"{today:%Y-%m}-{_slugify(company)}-{_slugify(role)}"


def run(
    *,
    company: str,
    role: str,
    source: str = "(unspecified)",
    next_action: str = "Initial review of role and company",
    next_action_due: str | None = None,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Create a new opportunity at status `prospect`."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    today_date = date.fromisoformat(today) if today else date.today()
    due = date.fromisoformat(next_action_due) if next_action_due else today_date + timedelta(days=7)
    slug = _build_slug(today_date, company, role)

    opp = Opportunity(
        slug=slug,
        company=company,
        role=role,
        status="prospect",
        priority="medium",
        source=source,
        location=None,
        comp_range=None,
        first_contact=today_date,
        applied_on=None,
        last_activity=today_date,
        next_action=next_action,
        next_action_due=due,
    )
    try:
        opp_dir = repo.create(opp, message=f"new: {slug}", no_commit=no_commit)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Created {opp_dir.relative_to(paths.db_root)}")
```

- [ ] **Step 2: Migrate `archive.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/archive.py` with:

```python
"""`jh archive` — move <slug> from opportunities/ to archive/."""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import Paths, paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Move an opportunity to the archive directory."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    _, opp_dir = repo.find(slug_query)
    try:
        repo.archive(opp_dir, no_commit=no_commit)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"archived: {opp_dir.name}")
```

- [ ] **Step 3: Migrate `delete.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/delete.py` with:

```python
"""`jh delete` — remove an opportunity directory."""

from __future__ import annotations

from typing import Annotated

import questionary
from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    yes: bool = False,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Delete an opportunity directory (e.g. a duplicate scaffold).

    --yes: skip the confirmation prompt.
    """
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    _, opp_dir = repo.find(slug_query)
    if not yes:
        confirm = questionary.confirm(f"Delete {opp_dir.name}?", default=False).ask()
        if not confirm:
            print("aborted")
            raise SystemExit(1)
    name = opp_dir.name
    repo.delete(opp_dir, no_commit=no_commit)
    print(f"deleted: {name}")
```

- [ ] **Step 4: Migrate `edit.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/edit.py` with:

```python
"""`jh edit` — open meta.toml in $EDITOR with validation loop."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.meta_io import ValidationError, read_meta
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository

_ERROR_PREFIX = "# ERROR:"


def _editor_argv(cfg_editor: str) -> list[str]:
    raw = cfg_editor or os.environ.get("EDITOR") or "vi"
    return shlex.split(raw)


def _strip_error_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    idx = 0
    while idx < len(lines) and lines[idx].startswith(_ERROR_PREFIX):
        idx += 1
    if idx == 0:
        return text
    if idx < len(lines) and lines[idx].rstrip() == "#":
        idx += 1
    if idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    return "".join(lines[idx:])


def _prepend_error(path: Path, message: str) -> None:
    body = _strip_error_block(path.read_text())
    block = "".join(f"{_ERROR_PREFIX} {line}\n" for line in message.splitlines())
    path.write_text(f"{block}#\n{body}")


def _open_editor(argv: list[str], path: Path) -> None:
    subprocess.run([*argv, str(path)], check=True)


def run(
    slug_query: str,
    /,
    *,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Open meta.toml in $EDITOR; validate on save; rename on slug change."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    meta = opp_dir / "meta.toml"
    editor_argv = _editor_argv(cfg.editor)

    while True:
        before = meta.read_text()
        _open_editor(editor_argv, meta)
        after = meta.read_text()
        if after == before:
            print("No changes.")
            return
        try:
            opp = read_meta(meta)
        except ValidationError as exc:
            _prepend_error(meta, str(exc))
            continue
        cleaned = _strip_error_block(meta.read_text())
        if cleaned != after:
            meta.write_text(cleaned)
            opp = read_meta(meta)
        final_dir = repo.save(opp, opp_dir, message=f"edit: {opp.slug}", no_commit=no_commit)
        print(f"Updated {final_dir.relative_to(repo.paths.db_root)}")
        return
```

- [ ] **Step 5: Migrate `list_.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/list_.py` with:

```python
"""`jh list` — one-line summary of every opportunity."""

from __future__ import annotations

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run() -> None:
    """List every opportunity as `<slug> <status> <priority>`, sorted by slug."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    for opp in repo.all():
        print(f"{opp.slug:<55} {opp.status:<12} {opp.priority}")
```

- [ ] **Step 6: Run full suite**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/jobhound/commands/new.py src/jobhound/commands/archive.py src/jobhound/commands/delete.py src/jobhound/commands/edit.py src/jobhound/commands/list_.py
git commit -m "Migrate new/archive/delete/edit/list to OpportunityRepository"
```

**Phase 1 complete.** Every command goes through `OpportunityRepository`. `meta_io.read_meta` / `write_meta` are still public but only called from `repository.py`.

---

## Phase 2 — Behaviour methods on `Opportunity`

**Goal:** Push the "what does this verb mean" logic out of CLI handlers and onto the aggregate root. After Phase 2, commands stop calling `dataclasses.replace()` directly; they call `opp.apply(...)`, `opp.withdraw(...)`, etc.

### Task 5: Add transition methods (`apply`, `log_interaction`, `withdraw`, `ghost`, `accept`, `decline`)

**Files:**
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`
- Create: `/Users/robin/code/github/yo61/jobhound/tests/test_opportunity_methods.py`

- [ ] **Step 1: Write failing tests for the entity methods**

Create `/Users/robin/code/github/yo61/jobhound/tests/test_opportunity_methods.py`:

```python
"""Unit tests for behaviour methods on the Opportunity entity."""

from __future__ import annotations

from datetime import date

import pytest

from jobhound.opportunities import Opportunity
from jobhound.transitions import InvalidTransitionError


def _prospect() -> Opportunity:
    return Opportunity(
        slug="2026-05-acme-eng",
        company="Acme",
        role="Engineer",
        status="prospect",
        priority="medium",
        source=None,
        location=None,
        comp_range=None,
        first_contact=date(2026, 5, 1),
        applied_on=None,
        last_activity=date(2026, 5, 1),
        next_action="follow up",
        next_action_due=date(2026, 5, 8),
    )


def test_apply_sets_all_fields_atomically() -> None:
    opp = _prospect()
    after = opp.apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    assert after.status == "applied"
    assert after.applied_on == date(2026, 5, 3)
    assert after.last_activity == date(2026, 5, 3)
    assert after.next_action == "wait"
    assert after.next_action_due == date(2026, 5, 10)


def test_apply_rejects_non_prospect() -> None:
    opp = _prospect().apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    with pytest.raises(InvalidTransitionError):
        opp.apply(
            applied_on=date(2026, 5, 3),
            today=date(2026, 5, 3),
            next_action="x",
            next_action_due=date(2026, 5, 4),
        )


def test_log_interaction_stay() -> None:
    opp = _prospect().apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    after = opp.log_interaction(
        today=date(2026, 5, 5),
        next_status="stay",
        next_action=None,
        next_action_due=None,
        force=False,
    )
    assert after.status == "applied"
    assert after.last_activity == date(2026, 5, 5)
    assert after.next_action == "wait"  # carries over


def test_log_interaction_advances_stage() -> None:
    opp = _prospect().apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    after = opp.log_interaction(
        today=date(2026, 5, 6),
        next_status="screen",
        next_action="prep",
        next_action_due=date(2026, 5, 12),
        force=False,
    )
    assert after.status == "screen"
    assert after.next_action == "prep"


def test_log_interaction_rejects_illegal_jump_without_force() -> None:
    opp = _prospect().apply(
        applied_on=date(2026, 5, 3),
        today=date(2026, 5, 3),
        next_action="wait",
        next_action_due=date(2026, 5, 10),
    )
    with pytest.raises(InvalidTransitionError):
        opp.log_interaction(
            today=date(2026, 5, 6),
            next_status="offer",
            next_action=None,
            next_action_due=None,
            force=False,
        )


def test_log_interaction_force_allows_anything() -> None:
    opp = _prospect()
    after = opp.log_interaction(
        today=date(2026, 5, 6),
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    assert after.status == "offer"


def test_withdraw_from_active() -> None:
    opp = _prospect()
    after = opp.withdraw(today=date(2026, 5, 6))
    assert after.status == "withdrawn"
    assert after.last_activity == date(2026, 5, 6)


def test_withdraw_rejects_terminal() -> None:
    opp = _prospect().withdraw(today=date(2026, 5, 6))
    with pytest.raises(InvalidTransitionError):
        opp.withdraw(today=date(2026, 5, 7))


def test_ghost_from_active() -> None:
    opp = _prospect()
    after = opp.ghost(today=date(2026, 5, 6))
    assert after.status == "ghosted"


def test_accept_requires_offer() -> None:
    opp = _prospect()
    with pytest.raises(InvalidTransitionError):
        opp.accept(today=date(2026, 5, 6))


def test_accept_from_offer() -> None:
    opp = _prospect().log_interaction(
        today=date(2026, 5, 6),
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    after = opp.accept(today=date(2026, 5, 7))
    assert after.status == "accepted"


def test_decline_from_offer() -> None:
    opp = _prospect().log_interaction(
        today=date(2026, 5, 6),
        next_status="offer",
        next_action=None,
        next_action_due=None,
        force=True,
    )
    after = opp.decline(today=date(2026, 5, 7))
    assert after.status == "declined"
```

- [ ] **Step 2: Run tests — expect failure (no such methods)**

Run: `uv run pytest tests/test_opportunity_methods.py -q`
Expected: FAIL — `AttributeError: 'Opportunity' object has no attribute 'apply'`.

- [ ] **Step 3: Add transition methods to `Opportunity`**

Modify `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py` to add the methods. Replace the entire file with:

```python
"""The Opportunity dataclass and its queries.

Ported from the old repo's `opportunities.py`. The TOML layer hands us native
`datetime.date` values, so the old `_coerce_date` helper is gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

ACTIVE_STATUSES: tuple[str, ...] = (
    "prospect",
    "applied",
    "screen",
    "interview",
    "offer",
)
CLOSED_STATUSES: tuple[str, ...] = (
    "accepted",
    "declined",
    "rejected",
    "withdrawn",
    "ghosted",
)
ALL_STATUSES: tuple[str, ...] = ACTIVE_STATUSES + CLOSED_STATUSES

STALE_DAYS: int = 14
GHOSTED_DAYS: int = 21


@dataclass(frozen=True)
class Opportunity:
    """A single opportunity loaded from `<slug>/meta.toml`."""

    slug: str
    company: str
    role: str
    status: str
    priority: str
    source: str | None
    location: str | None
    comp_range: str | None
    first_contact: date | None
    applied_on: date | None
    last_activity: date | None
    next_action: str | None
    next_action_due: date | None
    tags: tuple[str, ...] = field(default_factory=tuple)
    contacts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    links: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def days_since_activity(self, today: date) -> int | None:
        if self.last_activity is None:
            return None
        return (today - self.last_activity).days

    def is_stale(self, today: date) -> bool:
        days = self.days_since_activity(today)
        return self.is_active and days is not None and days >= STALE_DAYS

    def looks_ghosted(self, today: date) -> bool:
        days = self.days_since_activity(today)
        return self.is_active and days is not None and days >= GHOSTED_DAYS

    # ---- behaviour: state transitions --------------------------------------

    def apply(
        self,
        *,
        applied_on: date,
        today: date,
        next_action: str,
        next_action_due: date,
    ) -> Opportunity:
        """Submit the application. Requires status `prospect`."""
        from jobhound.transitions import require_transition

        require_transition(self.status, "applied", verb="apply")
        return replace(
            self,
            status="applied",
            applied_on=applied_on,
            last_activity=today,
            next_action=next_action,
            next_action_due=next_action_due,
        )

    def log_interaction(
        self,
        *,
        today: date,
        next_status: str,
        next_action: str | None,
        next_action_due: date | None,
        force: bool,
    ) -> Opportunity:
        """Record an interaction. `next_status='stay'` keeps the current status."""
        from jobhound.transitions import require_transition

        if not force:
            require_transition(self.status, next_status, verb="log")
        new_status = self.status if next_status == "stay" else next_status
        return replace(
            self,
            status=new_status,
            last_activity=today,
            next_action=next_action if next_action is not None else self.next_action,
            next_action_due=next_action_due if next_action_due is not None else self.next_action_due,
        )

    def withdraw(self, *, today: date) -> Opportunity:
        """Move to status `withdrawn`. Requires an active status."""
        from jobhound.transitions import require_transition

        require_transition(self.status, "withdrawn", verb="withdraw")
        return replace(self, status="withdrawn", last_activity=today)

    def ghost(self, *, today: date) -> Opportunity:
        """Move to status `ghosted`. Requires an active status."""
        from jobhound.transitions import require_transition

        require_transition(self.status, "ghosted", verb="ghost")
        return replace(self, status="ghosted", last_activity=today)

    def accept(self, *, today: date) -> Opportunity:
        """Move to status `accepted`. Requires status `offer`."""
        from jobhound.transitions import require_transition

        require_transition(self.status, "accepted", verb="accept")
        return replace(self, status="accepted", last_activity=today)

    def decline(self, *, today: date) -> Opportunity:
        """Move to status `declined`. Requires status `offer`."""
        from jobhound.transitions import require_transition

        require_transition(self.status, "declined", verb="decline")
        return replace(self, status="declined", last_activity=today)


def opportunity_from_dict(data: dict[str, Any], path: Path | None = None) -> Opportunity:
    """Build an Opportunity from a parsed meta.toml dict."""
    status = data.get("status", "prospect")
    if status not in ALL_STATUSES:
        raise ValueError(f"Unknown status {status!r} in {path}")
    return Opportunity(
        slug=data.get("slug") or (path.parent.name if path else ""),
        company=data["company"],
        role=data["role"],
        status=status,
        priority=data.get("priority", "medium"),
        source=data.get("source"),
        location=data.get("location"),
        comp_range=data.get("comp_range"),
        first_contact=data.get("first_contact"),
        applied_on=data.get("applied_on"),
        last_activity=data.get("last_activity"),
        next_action=data.get("next_action"),
        next_action_due=data.get("next_action_due"),
        tags=tuple(data.get("tags") or ()),
        contacts=tuple(data.get("contacts") or ()),
        links=dict(data.get("links") or {}),
        path=path,
    )
```

Note: imports of `require_transition` are local inside each method to avoid a circular import (transitions.py imports `ACTIVE_STATUSES` from opportunities.py).

- [ ] **Step 4: Run new tests**

Run: `uv run pytest tests/test_opportunity_methods.py -q`
Expected: all 12 tests pass.

Run: `uv run pytest -q`
Expected: full suite still green.

- [ ] **Step 5: Wire `apply.py` and `_terminal.py` to the new methods**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/apply.py`:

```python
"""`jh apply` — submitted application, status → applied."""

from __future__ import annotations

import sys
from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError


def run(
    slug_query: str,
    /,
    *,
    on: str | None = None,
    next_action: str,
    next_action_due: str,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Mark the application as submitted."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)

    today_date = date.fromisoformat(today) if today else date.today()
    applied_on = date.fromisoformat(on) if on else today_date
    due = date.fromisoformat(next_action_due)

    opp, opp_dir = repo.find(slug_query)
    try:
        updated = opp.apply(
            applied_on=applied_on,
            today=today_date,
            next_action=next_action,
            next_action_due=due,
        )
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    repo.save(updated, opp_dir, message=f"apply: {opp.slug}", no_commit=no_commit)
    print(f"applied: {opp.slug}")
```

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/_terminal.py`:

```python
"""Shared logic for terminal-status verbs (withdraw, ghost, accept, decline)."""

from __future__ import annotations

import sys
from datetime import date

from jobhound.config import load_config
from jobhound.opportunities import Opportunity
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError

_METHODS = {
    "withdraw": Opportunity.withdraw,
    "ghost": Opportunity.ghost,
    "accept": Opportunity.accept,
    "decline": Opportunity.decline,
}


def run_transition(
    *,
    slug_query: str,
    verb: str,
    target_status: str,  # kept for backwards compat with callers; unused here
    today: str | None,
    no_commit: bool,
) -> None:
    """Move an opportunity to its terminal status via the entity method."""
    del target_status  # the entity method enforces the target
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()
    opp, opp_dir = repo.find(slug_query)

    method = _METHODS[verb]
    try:
        updated = method(opp, today=today_date)
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    repo.save(updated, opp_dir, message=f"{verb}: {opp.slug}", no_commit=no_commit)
    print(f"{verb}: {opp.slug}")
```

- [ ] **Step 6: Wire `log.py` to `Opportunity.log_interaction`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/log.py`:

```python
"""`jh log` — record an interaction; default next status advances one stage."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository
from jobhound.transitions import InvalidTransitionError

_NAME_SLUG = re.compile(r"[^a-z0-9]+")


def _name_slug(who: str) -> str:
    return _NAME_SLUG.sub("-", who.lower()).strip("-") or "unknown"


def _correspondence_filename(when: date, channel: str, direction: str, who: str) -> str:
    return f"{when.isoformat()}-{channel}-{direction}-{_name_slug(who)}.md"


def run(
    slug_query: str,
    /,
    *,
    channel: str,
    direction: str,
    who: str,
    body: Path,
    next_status: str = "stay",
    next_action: str | None = None,
    next_action_due: str | None = None,
    force: bool = False,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Record an interaction (correspondence) and update status + next action."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()

    if direction not in {"from", "to"}:
        print(f"--direction must be 'from' or 'to', got {direction!r}", file=sys.stderr)
        raise SystemExit(1)
    if not body.is_file():
        print(f"--body file not found: {body}", file=sys.stderr)
        raise SystemExit(1)

    opp, opp_dir = repo.find(slug_query)
    due = date.fromisoformat(next_action_due) if next_action_due else None
    try:
        updated = opp.log_interaction(
            today=today_date,
            next_status=next_status,
            next_action=next_action,
            next_action_due=due,
            force=force,
        )
    except InvalidTransitionError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    corr_dir = opp_dir / "correspondence"
    corr_dir.mkdir(exist_ok=True)
    corr_path = corr_dir / _correspondence_filename(today_date, channel, direction, who)
    corr_path.write_text(body.read_text())

    arrow = (
        f"{opp.status} → {updated.status}" if updated.status != opp.status else "(no status change)"
    )
    repo.save(updated, opp_dir, message=f"log: {opp.slug} {arrow}", no_commit=no_commit)
    print(f"logged: {opp.slug} {arrow}")
```

- [ ] **Step 7: Run full suite**

Run: `uv run pytest -q`
Expected: all tests pass — the entity methods have the same semantics as the old inline `replace(...)` blocks.

- [ ] **Step 8: Commit**

```bash
git add src/jobhound/opportunities.py src/jobhound/commands/apply.py src/jobhound/commands/log.py src/jobhound/commands/_terminal.py tests/test_opportunity_methods.py
git commit -m "Push state-transition behaviour onto Opportunity entity"
```

---

### Task 6: Add `touch`, `with_tags`, `with_priority`, `with_contact`, `with_link` and migrate callers

**Files:**
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/note.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/tag.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/priority.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/contact.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/link.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/tests/test_opportunity_methods.py`

- [ ] **Step 1: Write failing tests for the new methods**

Append to `/Users/robin/code/github/yo61/jobhound/tests/test_opportunity_methods.py`:

```python


def test_touch_bumps_last_activity_only() -> None:
    opp = _prospect()
    after = opp.touch(today=date(2026, 5, 9))
    assert after.last_activity == date(2026, 5, 9)
    assert after.status == opp.status


def test_with_tags_adds_and_removes() -> None:
    opp = _prospect()
    after = opp.with_tags(add={"remote", "uk"}, remove=set())
    assert after.tags == ("remote", "uk")
    after2 = after.with_tags(add=set(), remove={"uk"})
    assert after2.tags == ("remote",)


def test_with_tags_dedupes_and_sorts() -> None:
    opp = _prospect()
    after = opp.with_tags(add={"b", "a", "b"}, remove=set())
    assert after.tags == ("a", "b")


def test_with_priority_rejects_unknown() -> None:
    opp = _prospect()
    with pytest.raises(ValueError):
        opp.with_priority("urgent")


def test_with_priority_sets_value() -> None:
    opp = _prospect()
    after = opp.with_priority("high")
    assert after.priority == "high"


def test_with_contact_appends() -> None:
    opp = _prospect()
    after = opp.with_contact({"name": "Jane", "role": "Recruiter"})
    assert after.contacts == ({"name": "Jane", "role": "Recruiter"},)


def test_with_contact_requires_name() -> None:
    opp = _prospect()
    with pytest.raises(ValueError):
        opp.with_contact({"role": "Recruiter"})


def test_with_link_sets_or_overwrites() -> None:
    opp = _prospect()
    after = opp.with_link(name="jd", url="https://example.com/jd")
    assert after.links == {"jd": "https://example.com/jd"}
    after2 = after.with_link(name="jd", url="https://example.com/jd2")
    assert after2.links == {"jd": "https://example.com/jd2"}
```

- [ ] **Step 2: Run new tests — expect failure**

Run: `uv run pytest tests/test_opportunity_methods.py -q`
Expected: FAIL — `AttributeError` on `touch`, `with_tags`, etc.

- [ ] **Step 3: Add the new methods to `Opportunity`**

In `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`, after the `decline` method, add a module-level `_PRIORITIES` constant and the five methods.

Add right after `GHOSTED_DAYS: int = 21`:

```python
_PRIORITIES: frozenset[str] = frozenset({"high", "medium", "low"})
```

Add after the `decline` method (still inside the class):

```python
    # ---- behaviour: field-shaped operations --------------------------------

    def touch(self, *, today: date) -> Opportunity:
        """Bump `last_activity` without changing status."""
        return replace(self, last_activity=today)

    def with_tags(self, *, add: set[str], remove: set[str]) -> Opportunity:
        """Apply tag add/remove deltas; resulting tag tuple is sorted and deduped."""
        tags = tuple(sorted((set(self.tags) | add) - remove))
        return replace(self, tags=tags)

    def with_priority(self, priority: str) -> Opportunity:
        """Set priority to one of high/medium/low."""
        if priority not in _PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(_PRIORITIES)}, got {priority!r}")
        return replace(self, priority=priority)

    def with_contact(self, contact: dict[str, str]) -> Opportunity:
        """Append a contact entry. `name` is required and non-empty."""
        name = contact.get("name")
        if not name:
            raise ValueError("contact must have a non-empty 'name'")
        return replace(self, contacts=(*self.contacts, dict(contact)))

    def with_link(self, *, name: str, url: str) -> Opportunity:
        """Set or replace a link entry."""
        links = dict(self.links)
        links[name] = url
        return replace(self, links=links)
```

- [ ] **Step 4: Run new tests — expect pass**

Run: `uv run pytest tests/test_opportunity_methods.py -q`
Expected: all tests (12 + 8) pass.

- [ ] **Step 5: Migrate `note.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/note.py`:

```python
"""`jh note` — append a timestamped one-liner to notes.md."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    msg: str,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Append a timestamped one-liner to <slug>/notes.md and bump last_activity."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    today_date = date.fromisoformat(today) if today else date.today()

    opp, opp_dir = repo.find(slug_query)
    notes = opp_dir / "notes.md"
    existing = notes.read_text() if notes.exists() else ""
    notes.write_text(existing + f"- {today_date.isoformat()} {msg}\n")

    repo.save(opp.touch(today=today_date), opp_dir, message=f"note: {opp.slug}", no_commit=no_commit)
    print(f"noted: {opp.slug}")
```

- [ ] **Step 6: Migrate `tag.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/tag.py`:

```python
"""`jh tag` — add and/or remove tags."""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add and/or remove tags."""
    add_set = set(add or [])
    remove_set = set(remove or [])
    if not add_set and not remove_set:
        print("nothing to do; pass --add and/or --remove", file=sys.stderr)
        raise SystemExit(1)

    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = opp.with_tags(add=add_set, remove=remove_set)

    summary = " ".join(
        [*(f"+{t}" for t in sorted(add_set)), *(f"-{t}" for t in sorted(remove_set))]
    )
    repo.save(updated, opp_dir, message=f"tag: {opp.slug} {summary}", no_commit=no_commit)
    print(f"tags {opp.slug}: {updated.tags}")
```

- [ ] **Step 7: Migrate `priority.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/priority.py`:

```python
"""`jh priority` — set priority to high/medium/low."""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    to: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Set the priority of an opportunity."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    try:
        updated = opp.with_priority(to)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    repo.save(updated, opp_dir, message=f"priority: {opp.slug} {to}", no_commit=no_commit)
    print(f"priority {opp.slug}: {to}")
```

- [ ] **Step 8: Migrate `contact.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/contact.py`:

```python
"""`jh contact` — append a contact entry."""

from __future__ import annotations

from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    name: str,
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add a contact to the contacts list."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    entry: dict[str, str] = {"name": name}
    if role_title is not None:
        entry["role"] = role_title
    if channel is not None:
        entry["channel"] = channel
    if company is not None:
        entry["company"] = company
    if note is not None:
        entry["note"] = note
    updated = opp.with_contact(entry)
    repo.save(updated, opp_dir, message=f"contact: {opp.slug} {name}", no_commit=no_commit)
    print(f"contact added: {opp.slug} {name}")
```

- [ ] **Step 9: Migrate `link.py`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/link.py`:

```python
"""`jh link` — add or update an entry in the links table."""

from __future__ import annotations

from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    name: str,
    url: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add or update a link."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = opp.with_link(name=name, url=url)
    repo.save(updated, opp_dir, message=f"link: {opp.slug} {name}", no_commit=no_commit)
    print(f"link {opp.slug}: {name} = {url}")
```

- [ ] **Step 10: Run full suite**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add src/jobhound/opportunities.py src/jobhound/commands/note.py src/jobhound/commands/tag.py src/jobhound/commands/priority.py src/jobhound/commands/contact.py src/jobhound/commands/link.py tests/test_opportunity_methods.py
git commit -m "Push field-shaped behaviour onto Opportunity entity"
```

**Phase 2 complete.** No command calls `dataclasses.replace` on an `Opportunity` directly any more. Every mutation goes through a named method on the entity.

---

## Phase 3 — `Status` value object

**Goal:** Replace the stringly-typed `status` field with a `Status(str, Enum)`. Fold `ACTIVE_STATUSES`/`CLOSED_STATUSES`/`LOG_FORWARD` into `Status`. Move the rules from `transitions.py` onto the type.

### Task 7: Introduce `Status` enum and the transition tables on it

**Files:**
- Create: `/Users/robin/code/github/yo61/jobhound/src/jobhound/status.py`
- Create: `/Users/robin/code/github/yo61/jobhound/tests/test_status.py`

- [ ] **Step 1: Write failing tests for `Status`**

Create `/Users/robin/code/github/yo61/jobhound/tests/test_status.py`:

```python
"""Tests for the Status value object."""

from __future__ import annotations

import pytest

from jobhound.status import STAY, Status


def test_string_equality_holds() -> None:
    assert Status.APPLIED == "applied"
    assert str(Status.APPLIED.value) == "applied"


def test_construct_from_string() -> None:
    assert Status("applied") is Status.APPLIED


def test_construct_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        Status("zombie")


def test_is_active() -> None:
    assert Status.PROSPECT.is_active
    assert Status.OFFER.is_active
    assert not Status.WITHDRAWN.is_active
    assert not Status.ACCEPTED.is_active


def test_is_terminal() -> None:
    assert Status.WITHDRAWN.is_terminal
    assert Status.ACCEPTED.is_terminal
    assert not Status.APPLIED.is_terminal


def test_legal_targets_apply() -> None:
    assert Status.PROSPECT.legal_targets(verb="apply") == frozenset({Status.APPLIED})
    assert Status.APPLIED.legal_targets(verb="apply") == frozenset()


def test_legal_targets_log() -> None:
    # `stay` is excluded — it's a meta-target, not a Status
    assert Status.APPLIED.legal_targets(verb="log") == frozenset({Status.SCREEN, Status.REJECTED})
    assert Status.OFFER.legal_targets(verb="log") == frozenset({Status.REJECTED})
    assert Status.WITHDRAWN.legal_targets(verb="log") == frozenset()


def test_legal_targets_withdraw_ghost() -> None:
    for s in (Status.PROSPECT, Status.APPLIED, Status.SCREEN, Status.INTERVIEW, Status.OFFER):
        assert s.legal_targets(verb="withdraw") == frozenset({Status.WITHDRAWN})
        assert s.legal_targets(verb="ghost") == frozenset({Status.GHOSTED})
    assert Status.ACCEPTED.legal_targets(verb="withdraw") == frozenset()


def test_legal_targets_accept_decline() -> None:
    assert Status.OFFER.legal_targets(verb="accept") == frozenset({Status.ACCEPTED})
    assert Status.OFFER.legal_targets(verb="decline") == frozenset({Status.DECLINED})
    assert Status.APPLIED.legal_targets(verb="accept") == frozenset()


def test_stay_sentinel() -> None:
    assert STAY == "stay"
```

- [ ] **Step 2: Run tests — expect ModuleNotFoundError**

Run: `uv run pytest tests/test_status.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'jobhound.status'`.

- [ ] **Step 3: Implement `Status`**

Create `/Users/robin/code/github/yo61/jobhound/src/jobhound/status.py`:

```python
"""The Status value object for an Opportunity.

`Status` is a `(str, Enum)` so existing string-equality comparisons keep
working while we migrate call sites (`Status.APPLIED == "applied"` is True).
`STAY` is a separate sentinel because `jh log --next-status stay` is a
meta-target — keep current status — not a real Status.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class Status(str, Enum):
    PROSPECT = "prospect"
    APPLIED = "applied"
    SCREEN = "screen"
    INTERVIEW = "interview"
    OFFER = "offer"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    GHOSTED = "ghosted"

    @property
    def is_active(self) -> bool:
        return self in _ACTIVE

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL

    def legal_targets(self, *, verb: str) -> frozenset[Status]:
        """All Status values that `verb` may move `self` to. Empty = illegal."""
        if verb == "apply":
            return frozenset({Status.APPLIED}) if self is Status.PROSPECT else frozenset()
        if verb == "log":
            if not self.is_active:
                return frozenset()
            targets: set[Status] = {Status.REJECTED}
            forward = _LOG_FORWARD.get(self)
            if forward is not None:
                targets.add(forward)
            return frozenset(targets)
        if verb == "withdraw":
            return frozenset({Status.WITHDRAWN}) if self.is_active else frozenset()
        if verb == "ghost":
            return frozenset({Status.GHOSTED}) if self.is_active else frozenset()
        if verb == "accept":
            return frozenset({Status.ACCEPTED}) if self is Status.OFFER else frozenset()
        if verb == "decline":
            return frozenset({Status.DECLINED}) if self is Status.OFFER else frozenset()
        raise ValueError(f"unknown verb {verb!r}")


_ACTIVE: Final[frozenset[Status]] = frozenset({
    Status.PROSPECT,
    Status.APPLIED,
    Status.SCREEN,
    Status.INTERVIEW,
    Status.OFFER,
})
_TERMINAL: Final[frozenset[Status]] = frozenset({
    Status.ACCEPTED,
    Status.DECLINED,
    Status.REJECTED,
    Status.WITHDRAWN,
    Status.GHOSTED,
})
_LOG_FORWARD: Final[dict[Status, Status]] = {
    Status.APPLIED: Status.SCREEN,
    Status.SCREEN: Status.INTERVIEW,
    Status.INTERVIEW: Status.OFFER,
}

STAY: Final[str] = "stay"
"""Meta-target for `jh log --next-status stay` — keep the current status."""
```

- [ ] **Step 4: Run new tests**

Run: `uv run pytest tests/test_status.py -q`
Expected: all 10 tests pass.

- [ ] **Step 5: Run full suite — should still be green (no callers changed)**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/status.py tests/test_status.py
git commit -m "Add Status enum with transition tables"
```

---

### Task 8: Switch `Opportunity.status` and `transitions.require_transition` to use `Status`

**Files:**
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/transitions.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/meta_io.py`

- [ ] **Step 1: Rewrite `transitions.py` as a thin shim**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/transitions.py`:

```python
"""Thin transition-rule layer. The rules themselves live on `Status`."""

from __future__ import annotations

from jobhound.status import STAY, Status


class InvalidTransitionError(Exception):
    """Raised when a verb tries an illegal status change."""


def log_options(current: Status | str) -> list[str]:
    """Return the legal `--next-status` values for `jh log` from `current`.

    Order: forward stage (if any), then `rejected`, then `stay`.
    """
    cur = Status(current) if not isinstance(current, Status) else current
    options: list[str] = []
    targets = cur.legal_targets(verb="log")
    # Forward stage (not rejected) goes first
    forward = next((t.value for t in targets if t is not Status.REJECTED), None)
    if forward is not None:
        options.append(forward)
    if Status.REJECTED in targets:
        options.append(Status.REJECTED.value)
    options.append(STAY)
    return options


def require_transition(current: Status | str, target: Status | str, *, verb: str) -> None:
    """Raise InvalidTransitionError unless `current → target` is legal for `verb`."""
    if verb == "log" and target == STAY:
        return
    cur = Status(current) if not isinstance(current, Status) else current
    try:
        tgt = Status(target) if not isinstance(target, Status) else target
    except ValueError as exc:
        legal = sorted(t.value for t in cur.legal_targets(verb=verb)) + ([STAY] if verb == "log" else [])
        raise InvalidTransitionError(
            f"jh {verb} from {cur.value!r}: {target!r} is not a legal next status (legal: {legal})"
        ) from exc
    if tgt not in cur.legal_targets(verb=verb):
        legal = sorted(t.value for t in cur.legal_targets(verb=verb)) + ([STAY] if verb == "log" else [])
        raise InvalidTransitionError(
            f"jh {verb} from {cur.value!r}: {tgt.value!r} is not a legal next status "
            f"(legal: {legal}). Use --force to override."
            if verb == "log"
            else f"jh {verb} requires status `{cur.value}` → one of {legal} (was {cur.value!r})"
        )
```

- [ ] **Step 2: Switch `Opportunity.status` to `Status`**

Modify `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`. The changes:

1. Replace the `ACTIVE_STATUSES`/`CLOSED_STATUSES`/`ALL_STATUSES` constants with re-exports from `status.py` (so any external import still resolves).
2. Change `status: str` to `status: Status`.
3. Update `is_active` to delegate.
4. Update `opportunity_from_dict` to call `Status(...)`.
5. Update transition methods to pass `Status` enums (the string literals already work because of `(str, Enum)`).

Replace the full file with:

```python
"""The Opportunity dataclass and its queries."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

from jobhound.status import Status

# Backwards-compat re-exports for any external callers (e.g. tests).
ACTIVE_STATUSES: tuple[str, ...] = tuple(s.value for s in (
    Status.PROSPECT, Status.APPLIED, Status.SCREEN, Status.INTERVIEW, Status.OFFER,
))
CLOSED_STATUSES: tuple[str, ...] = tuple(s.value for s in (
    Status.ACCEPTED, Status.DECLINED, Status.REJECTED, Status.WITHDRAWN, Status.GHOSTED,
))
ALL_STATUSES: tuple[str, ...] = ACTIVE_STATUSES + CLOSED_STATUSES

STALE_DAYS: int = 14
GHOSTED_DAYS: int = 21

_PRIORITIES: frozenset[str] = frozenset({"high", "medium", "low"})


@dataclass(frozen=True)
class Opportunity:
    """A single opportunity loaded from `<slug>/meta.toml`."""

    slug: str
    company: str
    role: str
    status: Status
    priority: str
    source: str | None
    location: str | None
    comp_range: str | None
    first_contact: date | None
    applied_on: date | None
    last_activity: date | None
    next_action: str | None
    next_action_due: date | None
    tags: tuple[str, ...] = field(default_factory=tuple)
    contacts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    links: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None

    @property
    def is_active(self) -> bool:
        return self.status.is_active

    def days_since_activity(self, today: date) -> int | None:
        if self.last_activity is None:
            return None
        return (today - self.last_activity).days

    def is_stale(self, today: date) -> bool:
        days = self.days_since_activity(today)
        return self.is_active and days is not None and days >= STALE_DAYS

    def looks_ghosted(self, today: date) -> bool:
        days = self.days_since_activity(today)
        return self.is_active and days is not None and days >= GHOSTED_DAYS

    # ---- behaviour: state transitions --------------------------------------

    def apply(
        self,
        *,
        applied_on: date,
        today: date,
        next_action: str,
        next_action_due: date,
    ) -> Opportunity:
        from jobhound.transitions import require_transition

        require_transition(self.status, Status.APPLIED, verb="apply")
        return replace(
            self,
            status=Status.APPLIED,
            applied_on=applied_on,
            last_activity=today,
            next_action=next_action,
            next_action_due=next_action_due,
        )

    def log_interaction(
        self,
        *,
        today: date,
        next_status: str,
        next_action: str | None,
        next_action_due: date | None,
        force: bool,
    ) -> Opportunity:
        from jobhound.transitions import require_transition

        if not force:
            require_transition(self.status, next_status, verb="log")
        new_status = self.status if next_status == "stay" else Status(next_status)
        return replace(
            self,
            status=new_status,
            last_activity=today,
            next_action=next_action if next_action is not None else self.next_action,
            next_action_due=next_action_due if next_action_due is not None else self.next_action_due,
        )

    def withdraw(self, *, today: date) -> Opportunity:
        from jobhound.transitions import require_transition

        require_transition(self.status, Status.WITHDRAWN, verb="withdraw")
        return replace(self, status=Status.WITHDRAWN, last_activity=today)

    def ghost(self, *, today: date) -> Opportunity:
        from jobhound.transitions import require_transition

        require_transition(self.status, Status.GHOSTED, verb="ghost")
        return replace(self, status=Status.GHOSTED, last_activity=today)

    def accept(self, *, today: date) -> Opportunity:
        from jobhound.transitions import require_transition

        require_transition(self.status, Status.ACCEPTED, verb="accept")
        return replace(self, status=Status.ACCEPTED, last_activity=today)

    def decline(self, *, today: date) -> Opportunity:
        from jobhound.transitions import require_transition

        require_transition(self.status, Status.DECLINED, verb="decline")
        return replace(self, status=Status.DECLINED, last_activity=today)

    # ---- behaviour: field-shaped operations --------------------------------

    def touch(self, *, today: date) -> Opportunity:
        return replace(self, last_activity=today)

    def with_tags(self, *, add: set[str], remove: set[str]) -> Opportunity:
        tags = tuple(sorted((set(self.tags) | add) - remove))
        return replace(self, tags=tags)

    def with_priority(self, priority: str) -> Opportunity:
        if priority not in _PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(_PRIORITIES)}, got {priority!r}")
        return replace(self, priority=priority)

    def with_contact(self, contact: dict[str, str]) -> Opportunity:
        name = contact.get("name")
        if not name:
            raise ValueError("contact must have a non-empty 'name'")
        return replace(self, contacts=(*self.contacts, dict(contact)))

    def with_link(self, *, name: str, url: str) -> Opportunity:
        links = dict(self.links)
        links[name] = url
        return replace(self, links=links)


def opportunity_from_dict(data: dict[str, Any], path: Path | None = None) -> Opportunity:
    """Build an Opportunity from a parsed meta.toml dict."""
    raw_status = data.get("status", "prospect")
    try:
        status = Status(raw_status)
    except ValueError as exc:
        raise ValueError(f"Unknown status {raw_status!r} in {path}") from exc
    return Opportunity(
        slug=data.get("slug") or (path.parent.name if path else ""),
        company=data["company"],
        role=data["role"],
        status=status,
        priority=data.get("priority", "medium"),
        source=data.get("source"),
        location=data.get("location"),
        comp_range=data.get("comp_range"),
        first_contact=data.get("first_contact"),
        applied_on=data.get("applied_on"),
        last_activity=data.get("last_activity"),
        next_action=data.get("next_action"),
        next_action_due=data.get("next_action_due"),
        tags=tuple(data.get("tags") or ()),
        contacts=tuple(data.get("contacts") or ()),
        links=dict(data.get("links") or {}),
        path=path,
    )
```

- [ ] **Step 3: Update `meta_io._as_serializable` to write the enum's value**

Modify `/Users/robin/code/github/yo61/jobhound/src/jobhound/meta_io.py`. Find the `_as_serializable` function and change the `"status": opp.status,` line to:

```python
        "status": opp.status.value,
```

Full updated `_as_serializable`:

```python
def _as_serializable(opp: Opportunity) -> dict[str, Any]:
    """Build the dict that tomli_w will write, in stable field order, dropping None."""
    raw: dict[str, Any] = {
        "company": opp.company,
        "role": opp.role,
        "slug": opp.slug,
        "source": opp.source,
        "status": opp.status.value,
        "priority": opp.priority,
        "first_contact": opp.first_contact,
        "applied_on": opp.applied_on,
        "last_activity": opp.last_activity,
        "next_action": opp.next_action,
        "next_action_due": opp.next_action_due,
        "location": opp.location,
        "comp_range": opp.comp_range,
        "tags": list(opp.tags) if opp.tags else None,
        "contacts": [dict(c) for c in opp.contacts] if opp.contacts else None,
        "links": dict(opp.links) if opp.links else None,
    }
    return {k: raw[k] for k in _FIELD_ORDER if raw.get(k) is not None}
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests pass. The `(str, Enum)` mixin means existing tests that say `status="applied"` and construct `Opportunity(..., status="applied", ...)` keep working — `Status` accepts a string in equality comparisons, but you need to construct via `Status("applied")` when passing positionally. **If tests fail with a TypeError about Status**, the test fixture is constructing the entity with a string for `status`; either update the fixture to use `Status.APPLIED` or wrap with `Status(s)` in `Opportunity.__post_init__`. Prefer updating the fixture.

- [ ] **Step 5: If failures: update test fixtures**

If any tests fail because they pass a `str` where `Status` is now expected (the dataclass won't coerce automatically), update the fixture. Example pattern: in `tests/test_repository.py` and `tests/test_opportunity_methods.py`, replace `status="prospect"` with `status=Status.PROSPECT` and add `from jobhound.status import Status`. Run tests again until green.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/opportunities.py src/jobhound/transitions.py src/jobhound/meta_io.py tests/
git commit -m "Use Status enum for Opportunity.status"
```

**Phase 3 complete.** `Status` is a real value object. `transitions.py` is a thin shim around `Status.legal_targets`. Membership checks (`if status in ACTIVE_STATUSES`) work via the re-exports, but new code should use `status.is_active` / `status.is_terminal`.

---

## Phase 4 — `Priority`, `Slug`, `Contact` value objects

**Goal:** Replace the remaining stringly/dict-typed primitives that carry rules. Skip `Link` — only one place sets links, no field-rich invariants today; promote later if it grows.

### Task 9: `Priority` enum

**Files:**
- Create: `/Users/robin/code/github/yo61/jobhound/src/jobhound/priority.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/meta_io.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/priority.py`

- [ ] **Step 1: Create `Priority`**

Create `/Users/robin/code/github/yo61/jobhound/src/jobhound/priority.py`:

```python
"""The Priority value object for an Opportunity."""

from __future__ import annotations

from enum import Enum


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

- [ ] **Step 2: Replace `_PRIORITIES` and `with_priority` in `opportunities.py`**

In `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`:

1. Add `from jobhound.priority import Priority` near the top.
2. Delete the `_PRIORITIES` constant.
3. Change the `priority` field type from `str` to `Priority`.
4. Update `with_priority` and `opportunity_from_dict`.

Replace the `priority: str` field declaration with:

```python
    priority: Priority
```

Replace the `with_priority` method body with:

```python
    def with_priority(self, priority: Priority | str) -> Opportunity:
        return replace(self, priority=Priority(priority))
```

Replace `priority=data.get("priority", "medium")` inside `opportunity_from_dict` with:

```python
        priority=Priority(data.get("priority", "medium")),
```

- [ ] **Step 3: Update `meta_io._as_serializable` to write the enum's value**

Change `"priority": opp.priority,` to:

```python
        "priority": opp.priority.value,
```

- [ ] **Step 4: Simplify the `priority` command**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/priority.py`:

```python
"""`jh priority` — set priority to high/medium/low."""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.priority import Priority
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    to: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Set the priority of an opportunity."""
    try:
        priority = Priority(to)
    except ValueError:
        print(f"--to must be one of {[p.value for p in Priority]}", file=sys.stderr)
        raise SystemExit(1) from None
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = opp.with_priority(priority)
    repo.save(updated, opp_dir, message=f"priority: {opp.slug} {priority.value}", no_commit=no_commit)
    print(f"priority {opp.slug}: {priority.value}")
```

- [ ] **Step 5: Update test fixtures that construct `Opportunity` with `priority="medium"` etc.**

In `tests/test_repository.py` and `tests/test_opportunity_methods.py`, change `priority="medium"` to `priority=Priority.MEDIUM` and import `from jobhound.priority import Priority`. Strings still work for equality but the dataclass will store them as plain `str` and break the type contract; prefer the enum.

- [ ] **Step 6: Run full suite**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/jobhound/priority.py src/jobhound/opportunities.py src/jobhound/meta_io.py src/jobhound/commands/priority.py tests/
git commit -m "Add Priority enum"
```

---

### Task 10: `Slug` value object

**Files:**
- Create: `/Users/robin/code/github/yo61/jobhound/src/jobhound/slug_value.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/meta_io.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/new.py`
- Create: `/Users/robin/code/github/yo61/jobhound/tests/test_slug_value.py`

Note: a new file `slug_value.py` rather than touching `slug.py` because the existing `slug.py` is a *resolver* (a query against the filesystem) — different concern, keep it separate.

- [ ] **Step 1: Write failing tests for `Slug`**

Create `/Users/robin/code/github/yo61/jobhound/tests/test_slug_value.py`:

```python
"""Tests for the Slug value object."""

from __future__ import annotations

from datetime import date

import pytest

from jobhound.slug_value import Slug


def test_create_accepts_valid() -> None:
    assert Slug.create("2026-05-acme-eng").value == "2026-05-acme-eng"


def test_create_rejects_path_separator() -> None:
    with pytest.raises(ValueError):
        Slug.create("a/b")
    with pytest.raises(ValueError):
        Slug.create("a\\b")


def test_create_rejects_leading_dot() -> None:
    with pytest.raises(ValueError):
        Slug.create(".hidden")


def test_create_rejects_whitespace() -> None:
    with pytest.raises(ValueError):
        Slug.create("a b")
    with pytest.raises(ValueError):
        Slug.create(" leading")
    with pytest.raises(ValueError):
        Slug.create("trailing ")


def test_create_rejects_empty() -> None:
    with pytest.raises(ValueError):
        Slug.create("")


def test_build_formats_year_month_company_role() -> None:
    slug = Slug.build(date(2026, 5, 11), "Acme Corp", "Senior Engineer")
    assert slug.value == "2026-05-acme-corp-senior-engineer"


def test_build_collapses_non_alnum() -> None:
    slug = Slug.build(date(2026, 5, 11), "A!B@C", "x")
    assert slug.value == "2026-05-a-b-c-x"


def test_str_is_value() -> None:
    assert str(Slug.create("x")) == "x"
```

- [ ] **Step 2: Run tests — expect ModuleNotFoundError**

Run: `uv run pytest tests/test_slug_value.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `Slug`**

Create `/Users/robin/code/github/yo61/jobhound/src/jobhound/slug_value.py`:

```python
"""The Slug value object — a validated opportunity identifier."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _NON_ALNUM.sub("-", text.lower()).strip("-")
    return s or "untitled"


@dataclass(frozen=True)
class Slug:
    """An opportunity slug. Construct via `Slug.create()` or `Slug.build()`."""

    value: str

    @classmethod
    def create(cls, raw: str) -> Slug:
        """Validate and wrap an existing slug string."""
        if not raw:
            raise ValueError("slug is empty")
        if raw != raw.strip():
            raise ValueError(f"slug {raw!r} has surrounding whitespace")
        if "/" in raw or "\\" in raw:
            raise ValueError(f"slug {raw!r} contains a path separator")
        if raw.startswith("."):
            raise ValueError(f"slug {raw!r} starts with '.'")
        if any(ch.isspace() for ch in raw):
            raise ValueError(f"slug {raw!r} contains whitespace")
        return cls(value=raw)

    @classmethod
    def build(cls, today: date, company: str, role: str) -> Slug:
        """Construct the canonical `YYYY-MM-company-role` form."""
        return cls(value=f"{today:%Y-%m}-{_slugify(company)}-{_slugify(role)}")

    def __str__(self) -> str:
        return self.value
```

- [ ] **Step 4: Run new tests**

Run: `uv run pytest tests/test_slug_value.py -q`
Expected: 8 tests pass.

- [ ] **Step 5: Route `meta_io._check_slug_safe` through `Slug.create`**

In `/Users/robin/code/github/yo61/jobhound/src/jobhound/meta_io.py`:

1. Add `from jobhound.slug_value import Slug` near the top.
2. Replace the `_check_slug_safe` function body with:

```python
def _check_slug_safe(slug: str) -> None:
    try:
        Slug.create(slug)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
```

- [ ] **Step 6: Route `commands/new.py` through `Slug.build`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/new.py`:

```python
"""`jh new` — scaffold a new opportunity at status `prospect`."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.opportunities import Opportunity
from jobhound.paths import Paths, paths_from_config
from jobhound.priority import Priority
from jobhound.repository import OpportunityRepository
from jobhound.slug_value import Slug
from jobhound.status import Status


def run(
    *,
    company: str,
    role: str,
    source: str = "(unspecified)",
    next_action: str = "Initial review of role and company",
    next_action_due: str | None = None,
    today: Annotated[str | None, Parameter(show=False)] = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Create a new opportunity at status `prospect`."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)

    today_date = date.fromisoformat(today) if today else date.today()
    due = date.fromisoformat(next_action_due) if next_action_due else today_date + timedelta(days=7)
    slug = Slug.build(today_date, company, role)

    opp = Opportunity(
        slug=slug.value,
        company=company,
        role=role,
        status=Status.PROSPECT,
        priority=Priority.MEDIUM,
        source=source,
        location=None,
        comp_range=None,
        first_contact=today_date,
        applied_on=None,
        last_activity=today_date,
        next_action=next_action,
        next_action_due=due,
    )
    try:
        opp_dir = repo.create(opp, message=f"new: {slug.value}", no_commit=no_commit)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Created {opp_dir.relative_to(paths.db_root)}")
```

- [ ] **Step 7: Run full suite**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/jobhound/slug_value.py src/jobhound/meta_io.py src/jobhound/commands/new.py tests/test_slug_value.py
git commit -m "Add Slug value object"
```

---

### Task 11: `Contact` value object

**Files:**
- Create: `/Users/robin/code/github/yo61/jobhound/src/jobhound/contact.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/meta_io.py`
- Modify: `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/contact.py`
- Create: `/Users/robin/code/github/yo61/jobhound/tests/test_contact.py`

- [ ] **Step 1: Write failing tests for `Contact`**

Create `/Users/robin/code/github/yo61/jobhound/tests/test_contact.py`:

```python
"""Tests for the Contact value object."""

from __future__ import annotations

import pytest

from jobhound.contact import Contact


def test_required_name() -> None:
    with pytest.raises(ValueError):
        Contact(name="")


def test_to_dict_drops_none() -> None:
    c = Contact(name="Jane", role="Recruiter", channel=None, company=None, note=None)
    assert c.to_dict() == {"name": "Jane", "role": "Recruiter"}


def test_to_dict_includes_all_set() -> None:
    c = Contact(name="Jane", role="Recruiter", channel="email", company="Acme", note="warm")
    assert c.to_dict() == {
        "name": "Jane",
        "role": "Recruiter",
        "channel": "email",
        "company": "Acme",
        "note": "warm",
    }


def test_from_dict_roundtrip() -> None:
    raw = {"name": "Jane", "role": "Recruiter"}
    assert Contact.from_dict(raw).to_dict() == raw


def test_from_dict_requires_name() -> None:
    with pytest.raises(ValueError):
        Contact.from_dict({"role": "Recruiter"})
```

- [ ] **Step 2: Implement `Contact`**

Create `/Users/robin/code/github/yo61/jobhound/src/jobhound/contact.py`:

```python
"""The Contact value object."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Contact:
    """A single contact attached to an opportunity. `name` is required."""

    name: str
    role: str | None = None
    channel: str | None = None
    company: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Contact.name must be non-empty")

    def to_dict(self) -> dict[str, str]:
        out: dict[str, str] = {"name": self.name}
        if self.role is not None:
            out["role"] = self.role
        if self.channel is not None:
            out["channel"] = self.channel
        if self.company is not None:
            out["company"] = self.company
        if self.note is not None:
            out["note"] = self.note
        return out

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Contact:
        if "name" not in data or not data["name"]:
            raise ValueError("contact dict must have a non-empty 'name'")
        return cls(
            name=data["name"],
            role=data.get("role"),
            channel=data.get("channel"),
            company=data.get("company"),
            note=data.get("note"),
        )
```

- [ ] **Step 3: Run new tests**

Run: `uv run pytest tests/test_contact.py -q`
Expected: 5 tests pass.

- [ ] **Step 4: Switch `Opportunity.contacts` to `tuple[Contact, ...]`**

In `/Users/robin/code/github/yo61/jobhound/src/jobhound/opportunities.py`:

1. Add `from jobhound.contact import Contact` near the top.
2. Change the `contacts` field type:

```python
    contacts: tuple[Contact, ...] = field(default_factory=tuple)
```

3. Replace the `with_contact` method:

```python
    def with_contact(self, contact: Contact) -> Opportunity:
        return replace(self, contacts=(*self.contacts, contact))
```

4. In `opportunity_from_dict`, change the `contacts=...` line:

```python
        contacts=tuple(Contact.from_dict(c) for c in (data.get("contacts") or ())),
```

- [ ] **Step 5: Update `meta_io._as_serializable` to call `.to_dict()`**

In `/Users/robin/code/github/yo61/jobhound/src/jobhound/meta_io.py`, change:

```python
        "contacts": [dict(c) for c in opp.contacts] if opp.contacts else None,
```

to:

```python
        "contacts": [c.to_dict() for c in opp.contacts] if opp.contacts else None,
```

- [ ] **Step 6: Update `commands/contact.py` to build a `Contact`**

Replace `/Users/robin/code/github/yo61/jobhound/src/jobhound/commands/contact.py`:

```python
"""`jh contact` — append a contact entry."""

from __future__ import annotations

from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.contact import Contact
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
    *,
    name: str,
    role_title: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Add a contact to the contacts list."""
    contact = Contact(
        name=name,
        role=role_title,
        channel=channel,
        company=company,
        note=note,
    )
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = opp.with_contact(contact)
    repo.save(updated, opp_dir, message=f"contact: {opp.slug} {name}", no_commit=no_commit)
    print(f"contact added: {opp.slug} {name}")
```

- [ ] **Step 7: Update the existing `with_contact` test**

In `tests/test_opportunity_methods.py`, the `test_with_contact_appends` and `test_with_contact_requires_name` tests now pass a `Contact`, not a `dict`. Replace them:

```python
def test_with_contact_appends() -> None:
    from jobhound.contact import Contact
    opp = _prospect()
    after = opp.with_contact(Contact(name="Jane", role="Recruiter"))
    assert after.contacts == (Contact(name="Jane", role="Recruiter"),)


def test_with_contact_requires_name() -> None:
    from jobhound.contact import Contact
    with pytest.raises(ValueError):
        Contact(name="")
```

- [ ] **Step 8: Run full suite**

Run: `uv run pytest -q`
Expected: all tests pass.

If any test fails because it asserts the old `dict` shape of `opp.contacts`, update the assertion to use `Contact` instances.

- [ ] **Step 9: Commit**

```bash
git add src/jobhound/contact.py src/jobhound/opportunities.py src/jobhound/meta_io.py src/jobhound/commands/contact.py tests/
git commit -m "Add Contact value object"
```

---

## Final verification

After all four phases:

- [ ] **Run the full suite one last time**

Run: `uv run pytest -q`
Expected: all tests green.

- [ ] **Lint and type-check**

Run: `uv run ruff check src tests && uv run ruff format --check src tests`
Run: `uv run ty check src`
Fix anything that fires before moving on.

- [ ] **Manually exercise a representative command against a fresh data root**

```bash
JH_DB_PATH=/tmp/jh-smoke uv run jh new --company "Acme" --role "Engineer" --next-action-due 2026-05-25
uv run jh apply acme --next-action "wait for screen" --next-action-due 2026-05-25
uv run jh log acme --channel email --direction from --who recruiter --body /tmp/email.md --next-status screen --next-action "prep" --next-action-due 2026-05-28
uv run jh list
uv run jh withdraw acme
```

(Note: `JH_DB_PATH` is not currently honored; either temporarily edit your `~/.config/jh/config.toml` or `rm -rf` the test data root after. Verify that meta.toml round-trips and that statuses transition cleanly.)

---

## Notes / deferred

- **Link value object** — not promoted in this plan. Today `Opportunity.links` is `dict[str, str]` (name → url) and only `commands/link.py` writes it. Promote if you add fields (description, added_on) or want URL validation.
- **NextAction value object** pairing `next_action + next_action_due` — defer. The two fields travel together in 4 callers but the join isn't pulling its weight as a type yet.
- **Notes + correspondence inside the aggregate** — defer. The `Opportunity` entity still doesn't model `notes.md` or `correspondence/*.md`. Add only when a rule needs to span them (e.g. "no correspondence after withdrawn").
- **Domain events** — defer. Commit messages are still hand-rolled per command. Worth doing when you add a digest / alerts / external integrations.
- **`Opportunity.path`** — unused field on the entity. Consider removing in a separate cleanup commit.
