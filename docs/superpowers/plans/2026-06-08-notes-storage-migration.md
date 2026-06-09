# Notes Storage Migration Implementation Plan (#102)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-opportunity `notes.md` with per-note files under `<opp>/notes/`, addressed by a stable per-opportunity monotonic sequence number (`<seq>.md` or `<seq>-<slug>.md`) and carrying TOML frontmatter (`+++ ... +++`) with `created` + optional `title`.

**Architecture:** Pure frontmatter helper module → `notes_service` use-case layer → CLI (`commands/note.py`) and MCP (`mcp/tools/ops.py`) thin adapters. Sequence counter `notes_next_seq` lives in `meta.toml` on `Opportunity` and never decrements, so note IDs are stable across deletes. A one-shot migration script ports existing `notes.md` files in chronological order. See `docs/superpowers/specs/2026-06-08-notes-storage-migration-design.md`.

**Tech Stack:** Python 3.13, `uv`, `pytest`, `ruff`, `ty`, `cyclopts`, `mcp` (optional), stdlib `tomllib` (read), `tomli_w` (write), `hypothesis` (one property test).

---

## File map

**Created:**
- `src/jobhound/application/frontmatter.py` — pure parser/serializer
- `src/jobhound/application/notes_service.py` — five use-cases
- `tests/application/test_frontmatter.py`
- `tests/application/test_notes_service.py`
- `tests/commands/test_cmd_note.py`
- `tests/scripts/test_migrate_notes.py`
- `scripts/migrate_notes_to_directory.py`

**Modified:**
- `decisions/2026-06-08-notes-storage-model.md` — Revision section
- `src/jobhound/domain/slug.py` — add `slugify(text)` helper
- `src/jobhound/domain/opportunities.py` — add `notes_next_seq` field + `with_notes_next_seq`
- `src/jobhound/infrastructure/meta_io.py` — field order, serializer, parser
- `src/jobhound/infrastructure/repository.py` — `create` makes `notes/` instead of `notes.md`
- `src/jobhound/application/ops_service.py` — remove `add_note`
- `src/jobhound/commands/note.py` — full rewrite, five verbs
- `src/jobhound/commands/log.py` — use shared `slugify` from `domain/slug.py`
- `src/jobhound/mcp/tools/ops.py` — rewrite `add_note`, add four tools
- `src/jobhound/mcp/errors.py` — translations for new exceptions
- `tests/application/test_ops_service.py` — remove `add_note` tests
- `tests/test_meta_io.py` — `notes_next_seq` round-trip
- `tests/domain/test_opportunities.py` — `notes_next_seq` defaults
- `tests/infrastructure/test_repository.py` — `notes/` directory
- `tests/mcp/test_tools_ops.py` — extend with four new tools
- `tests/storage/in_memory.py` — confirm `list()` enumerates subdirs (or extend if not)
- `docs/commands.md` — replace `add note` section
- `README.md` — replace `notes.md` references
- `CHANGELOG.md` — breaking-change entry (or via release-please footer)

---

## Task 0: Branch + decision-doc amendment

**Files:**
- Modify: `decisions/2026-06-08-notes-storage-model.md`

- [ ] **Step 1: Create branch**

```bash
git checkout -b notes-storage-migration
git status   # should be clean on the new branch
```

- [ ] **Step 2: Append Revision section to decision doc**

Open `decisions/2026-06-08-notes-storage-model.md`. Append the following at end of file (after the existing `## Outcome` section):

```markdown

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
```

- [ ] **Step 3: Commit**

```bash
git add decisions/2026-06-08-notes-storage-model.md
git commit -m "docs: amend notes-storage decision with sequence-id revision"
```

---

## Task 1: Slugify helper in domain/slug.py

**Files:**
- Modify: `src/jobhound/domain/slug.py`
- Test: `tests/domain/test_slug.py` (extend or create)

- [ ] **Step 1: Write failing test**

Open `tests/domain/test_slug.py` (create if absent — `tests/domain/` should already exist per earlier exploration). Add:

```python
import pytest

from jobhound.domain.slug import slugify


def test_slugify_lowercases_and_replaces_runs_of_non_alnum_with_dash():
    assert slugify("Charlotte Eyre Background") == "charlotte-eyre-background"


def test_slugify_strips_leading_trailing_dashes():
    assert slugify("  --hello world!!  ") == "hello-world"


def test_slugify_collapses_consecutive_separators():
    assert slugify("a   b___c") == "a-b-c"


def test_slugify_empty_when_only_separators():
    assert slugify("---") == ""


def test_slugify_keeps_digits():
    assert slugify("Q4 2026 plan") == "q4-2026-plan"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_slug.py -v`
Expected: FAIL — `ImportError: cannot import name 'slugify' from 'jobhound.domain.slug'`.

- [ ] **Step 3: Implement slugify**

Add to `src/jobhound/domain/slug.py` (anywhere at module level, e.g. above `resolve_slug`):

```python
import re

_SLUGIFY_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Lowercase, replace runs of non-alphanumeric with `-`, strip ends.

    Returns "" if no alphanumeric content survives. Used for note title
    suffixes and the legacy correspondence filename builder.
    """
    return _SLUGIFY_PATTERN.sub("-", text.lower()).strip("-")
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/domain/test_slug.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Update `commands/log.py` to use shared helper**

In `src/jobhound/commands/log.py`, replace:

```python
_NAME_SLUG = re.compile(r"[^a-z0-9]+")


def _name_slug(who: str) -> str:
    return _NAME_SLUG.sub("-", who.lower()).strip("-") or "unknown"


def _correspondence_filename(when: datetime, channel: str, direction: str, who: str) -> str:
    return f"{to_local_date(when).isoformat()}-{channel}-{direction}-{_name_slug(who)}.md"
```

with:

```python
from jobhound.domain.slug import slugify


def _correspondence_filename(when: datetime, channel: str, direction: str, who: str) -> str:
    name = slugify(who) or "unknown"
    return f"{to_local_date(when).isoformat()}-{channel}-{direction}-{name}.md"
```

Also remove the now-unused `import re` if it was only used for `_NAME_SLUG`.

- [ ] **Step 6: Verify log.py tests still pass**

Run: `uv run pytest tests/ -k "log" -v`
Expected: PASS (no regressions in `jh log` behavior).

- [ ] **Step 7: Commit**

```bash
git add src/jobhound/domain/slug.py src/jobhound/commands/log.py tests/domain/test_slug.py
git commit -m "feat(domain): extract slugify helper, reuse in commands/log"
```

---

## Task 2: Frontmatter helper module

**Files:**
- Create: `src/jobhound/application/frontmatter.py`
- Create: `tests/application/test_frontmatter.py`

- [ ] **Step 1: Write failing tests (round-trip and validation)**

Create `tests/application/test_frontmatter.py`:

```python
from datetime import UTC, datetime, timedelta, timezone

import pytest
from hypothesis import given, strategies as st

from jobhound.application.frontmatter import (
    Document,
    Frontmatter,
    FrontmatterError,
    parse,
    parse_or_synthesize,
    serialize,
)


def _fm(**kwargs):
    base = {"created": datetime(2026, 6, 8, 14, 23, 5, tzinfo=UTC)}
    return Frontmatter(**(base | kwargs))


def test_serialize_minimal():
    doc = Document(_fm(), body="Hello world.")
    out = serialize(doc)
    assert b"+++\n" in out
    assert b"created = 2026-06-08T14:23:05Z\n" in out
    assert b"title" not in out
    assert out.endswith(b"Hello world.\n")


def test_serialize_with_title():
    doc = Document(_fm(title="Charlotte prep"), body="Body.")
    out = serialize(doc)
    assert b'title = "Charlotte prep"\n' in out


def test_parse_roundtrip_minimal():
    doc = Document(_fm(), body="Hello.")
    assert parse(serialize(doc)) == doc


def test_parse_roundtrip_with_title():
    doc = Document(_fm(title="kickoff"), body="One\nTwo\nThree")
    assert parse(serialize(doc)) == doc


def test_parse_rejects_empty():
    with pytest.raises(FrontmatterError, match="empty"):
        parse(b"")


def test_parse_rejects_unclosed_frontmatter():
    with pytest.raises(FrontmatterError, match="unclosed"):
        parse(b"+++\ncreated = 2026-06-08T14:23:05Z\n\nbody but no closing")


def test_parse_rejects_missing_created():
    with pytest.raises(FrontmatterError, match="created"):
        parse(b'+++\ntitle = "x"\n+++\n\nbody')


def test_parse_rejects_naive_created():
    with pytest.raises(FrontmatterError, match="tz-aware"):
        parse(b"+++\ncreated = 2026-06-08T14:23:05\n+++\n\nbody")


def test_parse_rejects_invalid_toml():
    with pytest.raises(FrontmatterError):
        parse(b"+++\nthis is = = not toml\n+++\n\nbody")


def test_parse_or_synthesize_on_bare_markdown():
    fallback = datetime(2025, 1, 1, tzinfo=UTC)
    doc = parse_or_synthesize(b"Just markdown.\n", fallback)
    assert doc.frontmatter.created == fallback
    assert doc.frontmatter.title is None
    assert doc.body == "Just markdown."


def test_extras_passthrough():
    raw = (
        b"+++\n"
        b"created = 2026-06-08T14:23:05Z\n"
        b'channel = "email"\n'
        b'direction = "to"\n'
        b"+++\n\nbody"
    )
    doc = parse(raw)
    assert doc.frontmatter.extras == {"channel": "email", "direction": "to"}


@given(
    second=st.integers(min_value=0, max_value=59),
    minute=st.integers(min_value=0, max_value=59),
    hour=st.integers(min_value=0, max_value=23),
    title=st.one_of(st.none(), st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126,
                                                              blacklist_characters='"\\'),
                                       min_size=1, max_size=40)),
    body=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126),
                 min_size=1, max_size=400),
)
def test_property_roundtrip(second, minute, hour, title, body):
    created = datetime(2026, 1, 1, hour, minute, second, tzinfo=UTC)
    doc = Document(Frontmatter(created=created, title=title), body=body.strip() or "x")
    assert parse(serialize(doc)) == doc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/application/test_frontmatter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'jobhound.application.frontmatter'`.

- [ ] **Step 3: Implement the module**

Create `src/jobhound/application/frontmatter.py`:

```python
"""TOML-frontmatter parser/serializer for per-item file streams.

Pure module: no FS, no store, no git. Bytes in, dataclass out (and
vice versa). Shared by notes (#102) and correspondence (#105).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import tomli_w

DELIMITER = b"+++"


class FrontmatterError(Exception):
    """Parse or validation failure on a frontmatter block."""


@dataclass(frozen=True)
class Frontmatter:
    """Typed view over the frontmatter table.

    `created` is mandatory and tz-aware UTC. `title` is optional.
    `extras` carries any other top-level keys verbatim (used by
    correspondence for `channel`/`direction`/`who`, and forward-
    compatible with future streams).
    """

    created: datetime
    title: str | None = None
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Document:
    """A parsed file: frontmatter plus the bare-markdown body."""

    frontmatter: Frontmatter
    body: str


def serialize(doc: Document) -> bytes:
    """Render a Document to canonical bytes."""
    fm_dict: dict[str, Any] = {"created": doc.frontmatter.created}
    if doc.frontmatter.title is not None:
        fm_dict["title"] = doc.frontmatter.title
    for k, v in doc.frontmatter.extras.items():
        fm_dict[k] = v
    fm_bytes = tomli_w.dumps(fm_dict).encode("utf-8")
    body = doc.body.rstrip("\n") + "\n"
    return DELIMITER + b"\n" + fm_bytes + DELIMITER + b"\n\n" + body.encode("utf-8")


def parse(content: bytes) -> Document:
    """Parse canonical-shape bytes. Raises FrontmatterError on invalid input."""
    if not content:
        raise FrontmatterError("empty document")
    if not content.startswith(DELIMITER + b"\n"):
        raise FrontmatterError("missing opening +++ delimiter on line 1")
    rest = content[len(DELIMITER) + 1:]
    end_marker = b"\n" + DELIMITER + b"\n"
    idx = rest.find(end_marker)
    if idx < 0:
        # Allow trailing +++ without newline (EOF case)
        eof_marker = b"\n" + DELIMITER
        if rest.endswith(eof_marker):
            idx = len(rest) - len(eof_marker)
            fm_raw = rest[:idx].decode("utf-8")
            body_raw = ""
        else:
            raise FrontmatterError("unclosed frontmatter: no closing +++ found")
    else:
        fm_raw = rest[:idx].decode("utf-8")
        body_raw = rest[idx + len(end_marker):].decode("utf-8")
    try:
        fm_data = tomllib.loads(fm_raw)
    except tomllib.TOMLDecodeError as exc:
        raise FrontmatterError(f"invalid TOML in frontmatter: {exc}") from exc
    if "created" not in fm_data:
        raise FrontmatterError("missing required field: created")
    created = fm_data.pop("created")
    if not isinstance(created, datetime):
        raise FrontmatterError("created must be a TOML datetime, got: " f"{type(created).__name__}")
    if created.tzinfo is None:
        raise FrontmatterError("created must be tz-aware UTC")
    title = fm_data.pop("title", None)
    if title is not None and not isinstance(title, str):
        raise FrontmatterError("title must be a string")
    return Document(
        frontmatter=Frontmatter(created=created, title=title, extras=fm_data),
        body=body_raw.rstrip("\n"),
    )


def parse_or_synthesize(content: bytes, fallback_created: datetime) -> Document:
    """Parse `content`; if it has no frontmatter, treat as bare markdown."""
    if content.startswith(DELIMITER + b"\n"):
        return parse(content)
    return Document(
        frontmatter=Frontmatter(created=fallback_created),
        body=content.decode("utf-8").rstrip("\n"),
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/application/test_frontmatter.py -v`
Expected: PASS (10 example tests + 1 property test).

- [ ] **Step 5: Lint and type-check**

Run: `uv run ruff check src/jobhound/application/frontmatter.py tests/application/test_frontmatter.py && uv run ty check src/jobhound/application/frontmatter.py`
Expected: clean exit. Fix any issues inline before committing.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/application/frontmatter.py tests/application/test_frontmatter.py
git commit -m "feat(application): add TOML frontmatter parser/serializer"
```

---

## Task 3: Opportunity.notes_next_seq + meta_io support

**Files:**
- Modify: `src/jobhound/domain/opportunities.py`
- Modify: `src/jobhound/infrastructure/meta_io.py`
- Test: `tests/domain/test_opportunities.py` (extend)
- Test: `tests/test_meta_io.py` (extend)

- [ ] **Step 1: Write failing test for default value and with_notes_next_seq**

Add to `tests/domain/test_opportunities.py` (top imports may need to be added):

```python
def test_notes_next_seq_defaults_to_1():
    opp = _opp()              # use existing helper if present; otherwise inline minimal Opportunity()
    assert opp.notes_next_seq == 1


def test_with_notes_next_seq_returns_updated_instance():
    opp = _opp()
    updated = opp.with_notes_next_seq(7)
    assert updated.notes_next_seq == 7
    assert opp.notes_next_seq == 1     # original unchanged (frozen dataclass)
```

(If `_opp()` helper does not exist, copy the minimal `Opportunity(...)` constructor call from the existing test file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_opportunities.py -v -k notes_next_seq`
Expected: FAIL — `AttributeError: 'Opportunity' object has no attribute 'notes_next_seq'`.

- [ ] **Step 3: Add field and helper to Opportunity**

In `src/jobhound/domain/opportunities.py`:

(a) Add to the `Opportunity` dataclass (after `links` field, around line 39):

```python
    notes_next_seq: int = 1
```

(b) Add helper method (place alongside other `with_*` methods, e.g. after `with_link`):

```python
    def with_notes_next_seq(self, n: int) -> Opportunity:
        """Return a copy with `notes_next_seq` set to `n`."""
        if n < 1:
            raise ValueError(f"notes_next_seq must be >= 1, got {n}")
        return replace(self, notes_next_seq=n)
```

(c) Update `opportunity_from_dict` (near end of file) to read the field. Find the function and add (placement: where other optional fields are pulled):

```python
    notes_next_seq = data.get("notes_next_seq", 1)
    if not isinstance(notes_next_seq, int) or notes_next_seq < 1:
        raise ValueError(f"notes_next_seq must be a positive int, got {notes_next_seq!r}")
```

Then add `notes_next_seq=notes_next_seq` to the `Opportunity(...)` constructor call inside that function.

- [ ] **Step 4: Run domain tests**

Run: `uv run pytest tests/domain/test_opportunities.py -v -k notes_next_seq`
Expected: PASS.

- [ ] **Step 5: Write failing test for meta_io round-trip**

Add to `tests/test_meta_io.py`:

```python
def test_meta_io_roundtrips_notes_next_seq(tmp_path):
    from jobhound.infrastructure.meta_io import read_meta, write_meta

    opp = _make_opp().with_notes_next_seq(7)   # use existing test helper
    path = tmp_path / "meta.toml"
    write_meta(opp, path)
    loaded = read_meta(path)
    assert loaded.notes_next_seq == 7


def test_meta_io_rejects_notes_next_seq_zero(tmp_path):
    from jobhound.infrastructure.meta_io import ValidationError, read_meta

    path = tmp_path / "meta.toml"
    path.write_text(
        'company = "X"\nrole = "EM"\nslug = "x"\n'
        'status = "prospect"\npriority = "medium"\n'
        "notes_next_seq = 0\n"
    )
    with pytest.raises(ValidationError):
        read_meta(path)


def test_meta_io_defaults_notes_next_seq_to_1_when_absent(tmp_path):
    from jobhound.infrastructure.meta_io import read_meta

    path = tmp_path / "meta.toml"
    path.write_text(
        'company = "X"\nrole = "EM"\nslug = "x"\n'
        'status = "prospect"\npriority = "medium"\n'
    )
    loaded = read_meta(path)
    assert loaded.notes_next_seq == 1
```

(Use the test file's existing helpers; if there's no `_make_opp`, inline a minimal Opportunity constructor.)

- [ ] **Step 6: Run meta_io tests to verify failure**

Run: `uv run pytest tests/test_meta_io.py -v -k notes_next_seq`
Expected: round-trip test FAILS (`notes_next_seq` not in `_FIELD_ORDER`, so it's dropped on write).

- [ ] **Step 7: Update meta_io.py**

In `src/jobhound/infrastructure/meta_io.py`:

(a) Add `"notes_next_seq"` to `_FIELD_ORDER` as the **last** element:

```python
_FIELD_ORDER: tuple[str, ...] = (
    "company",
    "role",
    "slug",
    "source",
    "status",
    "priority",
    "first_contact",
    "applied_on",
    "last_activity",
    "next_action",
    "next_action_due",
    "location",
    "comp_range",
    "tags",
    "contacts",
    "links",
    "notes_next_seq",
)
```

(b) Update `_as_serializable` to include the field:

```python
        "notes_next_seq": opp.notes_next_seq,
```

(placed inside the `raw` dict literal alongside the other entries).

The existing line `return {k: raw[k] for k in _FIELD_ORDER if raw.get(k) is not None}` already drops `None` — `notes_next_seq` is never `None`, so it always writes. Good.

- [ ] **Step 8: Run all tests in tests/test_meta_io.py and tests/domain/**

Run: `uv run pytest tests/test_meta_io.py tests/domain/ -v`
Expected: PASS (including the three new meta_io tests and the two domain tests).

- [ ] **Step 9: Run full suite to catch regressions**

Run: `uv run pytest -q`
Expected: PASS or only failures in `tests/application/test_ops_service.py::test_add_note_*` (those will fail later when we remove `add_note`; ignore for now if they still pass).

- [ ] **Step 10: Commit**

```bash
git add src/jobhound/domain/opportunities.py \
        src/jobhound/infrastructure/meta_io.py \
        tests/domain/test_opportunities.py \
        tests/test_meta_io.py
git commit -m "feat(domain): add notes_next_seq counter on Opportunity"
```

---

## Task 4: notes_service — add_note

**Files:**
- Create: `src/jobhound/application/notes_service.py`
- Create: `tests/application/test_notes_service.py`

- [ ] **Step 1: Write failing test for happy-path add**

Create `tests/application/test_notes_service.py`:

```python
"""Tests for application/notes_service.py."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jobhound.application import notes_service
from jobhound.application.notes_service import (
    EmptyBodyError,
    NoteNotFoundError,
    TitleSlugError,
)
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.priority import Priority
from jobhound.domain.status import Status
from jobhound.infrastructure.config import Config
from jobhound.infrastructure.paths import Paths
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

NOW = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)


def _git_init(db_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(db_root)], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.email", "t@t"], check=True)


def _seeded(tmp_path: Path) -> tuple[OpportunityRepository, Paths, GitLocalFileStore]:
    db_root = tmp_path / "db"
    for d in ("opportunities", "archive", "_shared"):
        (db_root / d).mkdir(parents=True)
    _git_init(db_root)
    paths = Paths(
        db_root=db_root,
        opportunities_dir=db_root / "opportunities",
        archive_dir=db_root / "archive",
        shared_dir=db_root / "_shared",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )
    repo = OpportunityRepository(paths, Config(db_path=db_root, auto_commit=True, editor=""))
    repo.create(
        Opportunity(
            slug="2026-05-acme",
            company="Acme",
            role="EM",
            status=Status.APPLIED,
            priority=Priority.MEDIUM,
            source=None,
            location=None,
            comp_range=None,
            first_contact=None,
            applied_on=None,
            last_activity=None,
            next_action=None,
            next_action_due=None,
        ),
        message="seed",
    )
    store = GitLocalFileStore(paths)
    return repo, paths, store


def test_add_note_writes_seq_1_file(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    result = notes_service.add_note(repo, store, "acme", body="first note", now=NOW)
    assert result.seq == 1
    assert result.filename == "1.md"
    contents = (paths.opportunities_dir / "2026-05-acme" / "notes" / "1.md").read_text()
    assert "created = 2026-05-14T12:00:00Z" in contents
    assert contents.rstrip().endswith("first note")


def test_add_note_with_title_slugifies(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    result = notes_service.add_note(
        repo, store, "acme", body="hi", title="Charlotte Eyre Background", now=NOW
    )
    assert result.filename == "1-charlotte-eyre-background.md"
    assert (paths.opportunities_dir / "2026-05-acme" / "notes" / "1-charlotte-eyre-background.md").exists()


def test_add_note_increments_notes_next_seq(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="one", now=NOW)
    _, opp_dir = repo.find("acme")
    assert (opp_dir / "notes" / "1.md").exists()
    # Re-read meta — counter should be 2 now
    from jobhound.infrastructure.meta_io import read_meta
    opp = read_meta(opp_dir / "meta.toml")
    assert opp.notes_next_seq == 2


def test_add_note_seq_stable_after_delete(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="a", now=NOW)
    notes_service.add_note(repo, store, "acme", body="b", now=NOW)
    notes_service.remove_note(repo, store, "acme", 2, now=NOW)
    r = notes_service.add_note(repo, store, "acme", body="c", now=NOW)
    assert r.seq == 3        # gap at 2 stays; next is 3


def test_add_note_bumps_last_activity(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    _, after, _, _, _ = notes_service.add_note(repo, store, "acme", body="x", now=NOW).__iter__() if False else (
        # AddNoteResult is a dataclass; unpack by fields below
        None, None, None, None, None
    )
    result = notes_service.add_note(repo, store, "acme", body="x", now=NOW)
    assert result.after.last_activity == NOW


def test_add_note_rejects_empty_body(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(EmptyBodyError):
        notes_service.add_note(repo, store, "acme", body="   \n  \n", now=NOW)


def test_add_note_rejects_title_that_slugifies_empty(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(TitleSlugError):
        notes_service.add_note(repo, store, "acme", body="body", title="!!!", now=NOW)
```

(Remove the confused `__iter__` line from the bump test — keep just the bottom two lines:
```python
def test_add_note_bumps_last_activity(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    result = notes_service.add_note(repo, store, "acme", body="x", now=NOW)
    assert result.after.last_activity == NOW
```
)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/application/test_notes_service.py -v`
Expected: FAIL — `ModuleNotFoundError: jobhound.application.notes_service`.

- [ ] **Step 3: Implement notes_service.add_note + helpers**

Create `src/jobhound/application/notes_service.py`:

```python
"""Notes use-cases over a FileStore + OpportunityRepository.

CRUD on per-note files under `<opp>/notes/<seq>[-<title-slug>].md`.
Sequence is held in `opp.notes_next_seq` (meta.toml) and never
decrements — deletes leave permanent gaps so note IDs are stable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jobhound.application import file_service, frontmatter
from jobhound.application.frontmatter import Document, Frontmatter
from jobhound.application.revisions import Revision
from jobhound.domain.opportunities import Opportunity
from jobhound.domain.slug import slugify
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.protocols import FileStore


# ---- Exceptions ---------------------------------------------------------


class NotesServiceError(Exception):
    """Base class for notes_service exceptions."""


class NoteNotFoundError(NotesServiceError):
    def __init__(self, slug: str, seq: int) -> None:
        super().__init__(f"note #{seq} not found in {slug}")
        self.slug = slug
        self.seq = seq


class NoteFilenameError(NotesServiceError):
    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(f"invalid note filename {filename!r}: {reason}")
        self.filename = filename
        self.reason = reason


class EmptyBodyError(NotesServiceError):
    def __init__(self) -> None:
        super().__init__("note body is empty")


class TitleSlugError(NotesServiceError):
    def __init__(self, title: str, reason: str) -> None:
        super().__init__(f"invalid --title {title!r}: {reason}")
        self.title = title
        self.reason = reason


# ---- Data classes -------------------------------------------------------


@dataclass(frozen=True)
class NoteSummary:
    """Metadata only — what `list_notes` returns. No body fetched."""

    seq: int
    filename: str
    created: datetime
    title: str | None


@dataclass(frozen=True)
class Note:
    """Full note — what `read_note` and `edit_note` return."""

    seq: int
    filename: str
    created: datetime
    title: str | None
    body: str
    revision: Revision


@dataclass(frozen=True)
class AddNoteResult:
    before: Opportunity
    after: Opportunity
    opp_dir: Path
    seq: int
    filename: str


# ---- Filename helpers ---------------------------------------------------


_NOTE_FILENAME = re.compile(r"^(\d+)(?:-[a-z0-9-]+)?\.md$")


def _filename(seq: int, title: str | None) -> str:
    if title is None:
        return f"{seq}.md"
    slug = slugify(title)
    if not slug:
        raise TitleSlugError(title, "slugifies to empty")
    return f"{seq}-{slug}.md"


def _parse_filename(name: str) -> int | None:
    m = _NOTE_FILENAME.match(name)
    return int(m.group(1)) if m else None


# ---- Public API ---------------------------------------------------------


def add_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    *,
    body: str,
    title: str | None = None,
    now: datetime,
) -> AddNoteResult:
    """Write a new note. Returns the assigned seq and resulting filename.

    Two commits per call (matches the prior add_note contract): one from
    file_service.write for the new note file, one from repo.save for the
    meta.toml update (last_activity + notes_next_seq).
    """
    if not body.strip():
        raise EmptyBodyError()
    before, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    seq = before.notes_next_seq
    filename = _filename(seq, title)
    doc = Document(
        frontmatter=Frontmatter(created=now, title=title),
        body=body.strip(),
    )
    file_service.write(store, canonical, f"notes/{filename}", frontmatter.serialize(doc))
    after = before.bump(now=now).with_notes_next_seq(seq + 1)
    repo.save(after, opp_dir, message=f"note: {after.slug} #{seq}")
    return AddNoteResult(before=before, after=after, opp_dir=opp_dir, seq=seq, filename=filename)


# list_notes, read_note, edit_note, remove_note added in subsequent tasks.
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/application/test_notes_service.py -v -k add_note`
Expected: 6 PASS (the four `add_note` tests + the title-empty + empty-body tests; `test_add_note_seq_stable_after_delete` will FAIL because `remove_note` isn't implemented yet — temporarily skip or expect that one to fail).

Mark `test_add_note_seq_stable_after_delete` with `@pytest.mark.xfail(reason="remove_note added in Task 6")` for now.

- [ ] **Step 5: Lint/type check**

Run: `uv run ruff check src/jobhound/application/notes_service.py tests/application/test_notes_service.py && uv run ty check src/jobhound/application/notes_service.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/application/notes_service.py tests/application/test_notes_service.py
git commit -m "feat(application): add notes_service.add_note with seq counter"
```

---

## Task 5: notes_service — list_notes + read_note

**Files:**
- Modify: `src/jobhound/application/notes_service.py`
- Modify: `tests/application/test_notes_service.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/application/test_notes_service.py`:

```python
def test_list_notes_empty(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    assert notes_service.list_notes(repo, store, "acme") == []


def test_list_notes_sorted_ascending(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="first", now=NOW)
    notes_service.add_note(repo, store, "acme", body="second", title="kickoff", now=NOW)
    notes_service.add_note(repo, store, "acme", body="third", now=NOW)
    summaries = notes_service.list_notes(repo, store, "acme")
    assert [s.seq for s in summaries] == [1, 2, 3]
    assert summaries[1].title == "kickoff"
    assert summaries[1].filename == "2-kickoff.md"


def test_list_notes_preserves_gaps(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="a", now=NOW)
    notes_service.add_note(repo, store, "acme", body="b", now=NOW)
    notes_service.add_note(repo, store, "acme", body="c", now=NOW)
    notes_service.remove_note(repo, store, "acme", 2, now=NOW)
    summaries = notes_service.list_notes(repo, store, "acme")
    assert [s.seq for s in summaries] == [1, 3]


def test_list_notes_raises_on_corrupt_filename(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    notes_dir = paths.opportunities_dir / "2026-05-acme" / "notes"
    notes_dir.mkdir(exist_ok=True)
    (notes_dir / "garbage.md").write_text("+++\ncreated = 2026-01-01T00:00:00Z\n+++\n\nx")
    from jobhound.application.notes_service import NoteFilenameError
    with pytest.raises(NoteFilenameError):
        notes_service.list_notes(repo, store, "acme")


def test_read_note_returns_full_note(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="hello there", title="greeting", now=NOW)
    note = notes_service.read_note(repo, store, "acme", 1)
    assert note.seq == 1
    assert note.filename == "1-greeting.md"
    assert note.title == "greeting"
    assert note.body == "hello there"
    assert note.created == NOW
    assert note.revision     # any non-empty Revision


def test_read_note_raises_on_missing_seq(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(NoteNotFoundError):
        notes_service.read_note(repo, store, "acme", 42)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/application/test_notes_service.py -v -k "list_notes or read_note"`
Expected: FAIL — `AttributeError: module 'jobhound.application.notes_service' has no attribute 'list_notes'`.

- [ ] **Step 3: Implement list_notes and read_note**

Append to `src/jobhound/application/notes_service.py`:

```python
def _iter_notes_dir(store: FileStore, canonical: str) -> Iterable[tuple[int, str]]:
    """Yield (seq, filename) for every valid note file. Raises on corruption."""
    entries = store.list(canonical)
    for entry in entries:
        if "/" not in entry.name:
            continue
        head, _, name = entry.name.partition("/")
        if head != "notes":
            continue
        if name.startswith("."):
            continue
        seq = _parse_filename(name)
        if seq is None:
            raise NoteFilenameError(name, "does not match <seq>[-<slug>].md")
        yield seq, name


def list_notes(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
) -> list[NoteSummary]:
    """Enumerate notes under `<opp>/notes/`, sorted by seq ascending.

    Only frontmatter is fetched per note; bodies are not read.
    """
    _, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    out: list[NoteSummary] = []
    for seq, name in sorted(_iter_notes_dir(store, canonical), key=lambda t: t[0]):
        content, _ = file_service.read(store, canonical, f"notes/{name}")
        doc = frontmatter.parse(content)
        out.append(
            NoteSummary(
                seq=seq,
                filename=name,
                created=doc.frontmatter.created,
                title=doc.frontmatter.title,
            )
        )
    return out


def read_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    seq: int,
) -> Note:
    """Read one note's full content. Raises NoteNotFoundError if seq absent."""
    _, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    name = None
    for s, n in _iter_notes_dir(store, canonical):
        if s == seq:
            if name is not None:
                raise NoteFilenameError(n, f"multiple files with seq {seq}")
            name = n
    if name is None:
        raise NoteNotFoundError(slug, seq)
    content, revision = file_service.read(store, canonical, f"notes/{name}")
    doc = frontmatter.parse(content)
    return Note(
        seq=seq,
        filename=name,
        created=doc.frontmatter.created,
        title=doc.frontmatter.title,
        body=doc.body,
        revision=revision,
    )
```

- [ ] **Step 4: Verify FileStore.list enumerates subdirectory entries**

`tests/storage/in_memory.py::list` returns `(slug, name) → entry` for all keys matching the slug — names include `notes/1.md` because we wrote them under that path. Good.

For `GitLocalFileStore`, check `src/jobhound/infrastructure/storage/git_local.py::list` to confirm it walks subdirectories. If it doesn't, that's a bug to flag separately (the file API was designed to support subdirectories; investigate with `grep -n "def list" src/jobhound/infrastructure/storage/git_local.py` and the test `tests/infrastructure/storage/test_git_local.py`).

Run: `uv run pytest tests/infrastructure/storage/ -v`
Expected: PASS (no new test required; just confirm baseline).

- [ ] **Step 5: Run notes_service tests**

Run: `uv run pytest tests/application/test_notes_service.py -v`
Expected: all add/list/read tests PASS; the `xfail`-marked `test_add_note_seq_stable_after_delete` still fails (expected).

- [ ] **Step 6: Lint/type-check**

Run: `uv run ruff check src/jobhound/application/notes_service.py && uv run ty check src/jobhound/application/notes_service.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/jobhound/application/notes_service.py tests/application/test_notes_service.py
git commit -m "feat(application): add list_notes and read_note"
```

---

## Task 6: notes_service — edit_note + remove_note

**Files:**
- Modify: `src/jobhound/application/notes_service.py`
- Modify: `tests/application/test_notes_service.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/application/test_notes_service.py`:

```python
def test_edit_note_preserves_created_and_title(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="v1", title="greeting", now=NOW)
    later = datetime(2026, 5, 15, 9, 0, tzinfo=UTC)
    notes_service.edit_note(repo, store, "acme", 1, body="v2", now=later)
    note = notes_service.read_note(repo, store, "acme", 1)
    assert note.body == "v2"
    assert note.title == "greeting"
    assert note.created == NOW


def test_edit_note_bumps_last_activity(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="v1", now=NOW)
    later = datetime(2026, 5, 15, 9, 0, tzinfo=UTC)
    _, after, _ = notes_service.edit_note(repo, store, "acme", 1, body="v2", now=later)
    assert after.last_activity == later


def test_edit_note_raises_on_missing_seq(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(NoteNotFoundError):
        notes_service.edit_note(repo, store, "acme", 99, body="x", now=NOW)


def test_edit_note_rejects_empty_body(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="ok", now=NOW)
    with pytest.raises(EmptyBodyError):
        notes_service.edit_note(repo, store, "acme", 1, body="   ", now=NOW)


def test_remove_note_deletes_file(tmp_path: Path) -> None:
    repo, paths, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="x", now=NOW)
    notes_service.remove_note(repo, store, "acme", 1, now=NOW)
    assert not (paths.opportunities_dir / "2026-05-acme" / "notes" / "1.md").exists()


def test_remove_note_raises_on_missing_seq(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    with pytest.raises(NoteNotFoundError):
        notes_service.remove_note(repo, store, "acme", 5, now=NOW)


def test_remove_note_does_not_decrement_counter(tmp_path: Path) -> None:
    repo, _, store = _seeded(tmp_path)
    notes_service.add_note(repo, store, "acme", body="a", now=NOW)
    notes_service.add_note(repo, store, "acme", body="b", now=NOW)
    notes_service.remove_note(repo, store, "acme", 2, now=NOW)
    _, opp_dir = repo.find("acme")
    from jobhound.infrastructure.meta_io import read_meta
    opp = read_meta(opp_dir / "meta.toml")
    assert opp.notes_next_seq == 3   # was 3 after second add; remove does not decrement
```

Also remove the `xfail` marker from `test_add_note_seq_stable_after_delete`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/application/test_notes_service.py -v -k "edit_note or remove_note"`
Expected: FAIL on `AttributeError` for missing functions.

- [ ] **Step 3: Implement edit_note and remove_note**

Append to `src/jobhound/application/notes_service.py`:

```python
def edit_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    seq: int,
    *,
    body: str,
    base_revision: Revision | None = None,
    now: datetime,
) -> tuple[Opportunity, Opportunity, Note]:
    """Rewrite a note's body, preserving frontmatter (`created`, `title`)."""
    if not body.strip():
        raise EmptyBodyError()
    before, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    note = read_note(repo, store, slug, seq)
    new_doc = Document(
        frontmatter=Frontmatter(created=note.created, title=note.title),
        body=body.strip(),
    )
    file_service.write(
        store,
        canonical,
        f"notes/{note.filename}",
        frontmatter.serialize(new_doc),
        base_revision=base_revision or note.revision,
    )
    after = before.bump(now=now)
    repo.save(after, opp_dir, message=f"note: edit {after.slug} #{seq}")
    refreshed = read_note(repo, store, slug, seq)
    return before, after, refreshed


def remove_note(
    repo: OpportunityRepository,
    store: FileStore,
    slug: str,
    seq: int,
    *,
    now: datetime,
) -> tuple[Opportunity, Opportunity, int]:
    """Delete a note's file. Does NOT decrement notes_next_seq."""
    before, opp_dir = repo.find(slug)
    canonical = opp_dir.name
    note = read_note(repo, store, slug, seq)
    file_service.delete(store, canonical, f"notes/{note.filename}")
    after = before.bump(now=now)
    repo.save(after, opp_dir, message=f"note: remove {after.slug} #{seq}")
    return before, after, seq
```

- [ ] **Step 4: Run all notes_service tests**

Run: `uv run pytest tests/application/test_notes_service.py -v`
Expected: PASS (all tests including `test_add_note_seq_stable_after_delete`).

- [ ] **Step 5: Lint/type-check**

Run: `uv run ruff check src/jobhound/application/notes_service.py && uv run ty check src/jobhound/application/notes_service.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/application/notes_service.py tests/application/test_notes_service.py
git commit -m "feat(application): add edit_note and remove_note"
```

---

## Task 7: Remove ops_service.add_note + update repository.create

**Files:**
- Modify: `src/jobhound/application/ops_service.py`
- Modify: `src/jobhound/infrastructure/repository.py`
- Modify: `tests/application/test_ops_service.py`
- Modify: `tests/infrastructure/test_repository.py`

- [ ] **Step 1: Write failing test for new scaffolding**

In `tests/infrastructure/test_repository.py`, find the test that asserts on `repository.create` output and add (or modify):

```python
def test_create_makes_notes_directory_not_file(tmp_path: Path) -> None:
    repo, paths = _build_repo(tmp_path)   # use existing helper from the test file
    repo.create(_minimal_opp(), message="seed")
    opp_dir = paths.opportunities_dir / "2026-05-x"   # adjust to match _minimal_opp's slug
    assert (opp_dir / "notes").is_dir()
    assert not (opp_dir / "notes.md").exists()


def test_create_persists_notes_next_seq_1(tmp_path: Path) -> None:
    repo, paths = _build_repo(tmp_path)
    repo.create(_minimal_opp(), message="seed")
    from jobhound.infrastructure.meta_io import read_meta
    opp = read_meta(paths.opportunities_dir / "2026-05-x" / "meta.toml")
    assert opp.notes_next_seq == 1
```

(Inspect the existing test file's helpers — `_build_repo` and `_minimal_opp` may have different names. Reuse whatever's there.)

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/infrastructure/test_repository.py -v -k "notes"`
Expected: FAIL — `notes.md` still exists.

- [ ] **Step 3: Update repository.create**

In `src/jobhound/infrastructure/repository.py`, find the `create` method (around line 51) and replace:

```python
        (opp_dir / "notes.md").write_text("")
```

with:

```python
        (opp_dir / "notes").mkdir()
```

- [ ] **Step 4: Run repository tests**

Run: `uv run pytest tests/infrastructure/test_repository.py -v`
Expected: PASS for the new tests. Any pre-existing tests asserting `notes.md` is created must be updated to assert `notes/` directory instead.

- [ ] **Step 5: Remove ops_service.add_note**

In `src/jobhound/application/ops_service.py`:

(a) Delete the `add_note` function (lines ~16-37 — the function and its docstring).
(b) Remove now-unused imports: `from jobhound.application import file_service` and `from jobhound.domain.timekeeping import _format_z_seconds` if they're not used by other functions in the file.

- [ ] **Step 6: Remove add_note tests from test_ops_service.py**

In `tests/application/test_ops_service.py`, delete `test_add_note_appends_dated_entry` and `test_add_note_bumps_last_activity`. Keep the archive/delete/unarchive tests.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -q`
Expected: PASS, except possibly:
- `tests/commands/` — tests that exercise `jh note add` via the old shape will fail; they'll be rewritten in Task 8.
- `tests/mcp/test_tools_ops.py::test_add_note_*` — will be rewritten in Task 9.

Note any failures and proceed; they'll be fixed in subsequent tasks.

- [ ] **Step 8: Commit**

```bash
git add src/jobhound/application/ops_service.py \
        src/jobhound/infrastructure/repository.py \
        tests/application/test_ops_service.py \
        tests/infrastructure/test_repository.py
git commit -m "refactor: remove ops_service.add_note, scaffold notes/ dir"
```

---

## Task 8: CLI — commands/note.py full rewrite

**Files:**
- Modify: `src/jobhound/commands/note.py`
- Create: `tests/commands/test_cmd_note.py`

- [ ] **Step 1: Write failing test for note add (positional body)**

Create `tests/commands/test_cmd_note.py`:

```python
"""End-to-end tests for `jh note` CLI verbs."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest


NOW_ISO = "2026-05-14T12:00:00Z"


def _setup_env(tmp_path: Path) -> dict[str, str]:
    db_root = tmp_path / "db"
    for d in ("opportunities", "archive", "_shared"):
        (db_root / d).mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(db_root)], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_root), "config", "user.email", "t@t"], check=True)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return {
        "JOBHOUND_DB_PATH": str(db_root),
        "JOBHOUND_CACHE_DIR": str(cache_dir),
        "JOBHOUND_STATE_DIR": str(tmp_path / "state"),
        "JOBHOUND_EDITOR": "",
        "PATH": __import__("os").environ["PATH"],
        "HOME": str(tmp_path),
    }


def _run(env: dict[str, str], *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "jh", *args],
        env=env,
        capture_output=True,
        text=True,
        input=stdin,
    )


def _create_opp(env: dict[str, str]) -> None:
    r = _run(env, "new", "--company", "Acme", "--role", "EM", "--now", NOW_ISO)
    assert r.returncode == 0, r.stderr


def test_note_add_positional_body(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    r = _run(env, "note", "add", "acme", "first contact made", "--now", NOW_ISO)
    assert r.returncode == 0, r.stderr
    assert "noted: " in r.stdout
    assert "#1" in r.stdout


def test_note_add_with_title(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    r = _run(env, "note", "add", "acme", "x", "--title", "Charlotte Prep", "--now", NOW_ISO)
    assert r.returncode == 0, r.stderr
    db_root = Path(env["JOBHOUND_DB_PATH"])
    notes_dir = next((db_root / "opportunities").iterdir()) / "notes"
    assert (notes_dir / "1-charlotte-prep.md").exists()


def test_note_add_from_stdin(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    r = _run(env, "note", "add", "acme", "--from", "-", "--now", NOW_ISO, stdin="piped body")
    assert r.returncode == 0, r.stderr


def test_note_add_rejects_both_positional_and_from(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    r = _run(env, "note", "add", "acme", "x", "--from", "-", "--now", NOW_ISO, stdin="y")
    assert r.returncode != 0


def test_note_list_shows_gaps(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    _run(env, "note", "add", "acme", "a", "--now", NOW_ISO)
    _run(env, "note", "add", "acme", "b", "--now", NOW_ISO)
    _run(env, "note", "add", "acme", "c", "--now", NOW_ISO)
    _run(env, "note", "remove", "acme", "2", "--now", NOW_ISO)
    r = _run(env, "note", "list", "acme")
    assert r.returncode == 0
    assert "1" in r.stdout and "3" in r.stdout
    assert "2" not in r.stdout.split("\n", 1)[1]   # 2 not in any data row


def test_note_show_body_only_by_default(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    _run(env, "note", "add", "acme", "hello world", "--now", NOW_ISO)
    r = _run(env, "note", "show", "acme", "1")
    assert r.returncode == 0
    assert r.stdout.strip() == "hello world"


def test_note_show_with_frontmatter(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    _run(env, "note", "add", "acme", "hello", "--now", NOW_ISO)
    r = _run(env, "note", "show", "acme", "1", "--with-frontmatter")
    assert r.returncode == 0
    assert "+++" in r.stdout
    assert "created" in r.stdout


def test_note_edit_from_path(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    _run(env, "note", "add", "acme", "v1", "--now", NOW_ISO)
    new_body = tmp_path / "new.md"
    new_body.write_text("v2")
    r = _run(env, "note", "edit", "acme", "1", "--from", str(new_body), "--now", NOW_ISO)
    assert r.returncode == 0
    r2 = _run(env, "note", "show", "acme", "1")
    assert r2.stdout.strip() == "v2"


def test_note_remove(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    _run(env, "note", "add", "acme", "x", "--now", NOW_ISO)
    r = _run(env, "note", "remove", "acme", "1", "--now", NOW_ISO)
    assert r.returncode == 0
    r2 = _run(env, "note", "list", "acme")
    assert "1" not in r2.stdout.split("\n", 1)[1]


def test_note_remove_missing_seq(tmp_path: Path) -> None:
    env = _setup_env(tmp_path)
    _create_opp(env)
    r = _run(env, "note", "remove", "acme", "99", "--now", NOW_ISO)
    assert r.returncode != 0
    assert "not found" in r.stderr
```

(Inspect existing `tests/commands/` test files to confirm the `_setup_env` / env-var keys are correct for this repo. If the harness uses a different config mechanism — e.g. `JOBHOUND_CONFIG` — adapt accordingly. The pattern that exists today drives the actual implementation.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/commands/test_cmd_note.py -v`
Expected: FAIL — most tests fail because `--msg` is the current flag, positional body isn't accepted, and `list`/`show`/`edit`/`remove` verbs don't exist.

- [ ] **Step 3: Rewrite commands/note.py**

Replace the entire contents of `src/jobhound/commands/note.py` with:

```python
"""`jh note` subgroup — manage notes on an opportunity."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

from jobhound.application import frontmatter, notes_service
from jobhound.application.notes_service import (
    EmptyBodyError,
    NoteFilenameError,
    NoteNotFoundError,
    TitleSlugError,
)
from jobhound.domain.timekeeping import now_utc, to_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository
from jobhound.infrastructure.storage.git_local import GitLocalFileStore

app = App(name="note", help="Manage notes on an opportunity.")


def _repo_and_store() -> tuple[OpportunityRepository, GitLocalFileStore]:
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    return repo, GitLocalFileStore(repo.paths)


def _resolve_body(body: str | None, from_: str | None) -> str:
    if body is not None and from_ is not None:
        print("error: cannot use both positional BODY and --from", file=sys.stderr)
        raise SystemExit(1)
    if body is not None:
        return body
    if from_ is None:
        print("error: must provide either positional BODY or --from PATH|-", file=sys.stderr)
        raise SystemExit(1)
    if from_ == "-":
        return sys.stdin.read()
    return Path(from_).read_text()


def _handle_service_error(exc: Exception, *, verb: str) -> None:
    if isinstance(exc, NoteNotFoundError):
        print(f"{verb}: {exc}", file=sys.stderr)
    elif isinstance(exc, (EmptyBodyError, TitleSlugError, NoteFilenameError)):
        print(f"{verb}: {exc}", file=sys.stderr)
    else:
        raise exc
    raise SystemExit(1)


@app.command(name="add")
def add(
    slug_query: str,
    body: str | None = None,
    /,
    *,
    title: str | None = None,
    from_: Annotated[str | None, Parameter(name=["--from"])] = None,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Write a new note. BODY is positional; use --from PATH|- to read instead."""
    repo, store = _repo_and_store()
    now_obj = to_utc(now) if now else now_utc()
    body_text = _resolve_body(body, from_)
    try:
        result = notes_service.add_note(
            repo, store, slug_query, body=body_text, title=title, now=now_obj
        )
    except Exception as exc:
        _handle_service_error(exc, verb="add")
        return
    suffix = f" ({title})" if title else ""
    print(f"noted: {result.after.slug} #{result.seq}{suffix}")


@app.command(name="list")
def list_(
    slug_query: str,
    /,
    *,
    reverse: bool = False,
) -> None:
    """List notes on an opportunity."""
    repo, store = _repo_and_store()
    try:
        notes = notes_service.list_notes(repo, store, slug_query)
    except Exception as exc:
        _handle_service_error(exc, verb="list")
        return
    if not notes:
        print("(no notes)", file=sys.stderr)
        return
    if reverse:
        notes = list(reversed(notes))
    print(f"{'#':>4}  {'CREATED':<20}  TITLE")
    for n in notes:
        title = n.title if n.title else "—"
        created = n.created.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"{n.seq:>4}  {created:<20}  {title}")


@app.command(name="show")
def show(
    slug_query: str,
    seq: int,
    /,
    *,
    with_frontmatter: bool = False,
) -> None:
    """Print one note's body (default) or full file (--with-frontmatter)."""
    repo, store = _repo_and_store()
    try:
        note = notes_service.read_note(repo, store, slug_query, seq)
    except Exception as exc:
        _handle_service_error(exc, verb="show")
        return
    if with_frontmatter:
        from jobhound.application.frontmatter import Document, Frontmatter
        doc = Document(
            frontmatter=Frontmatter(created=note.created, title=note.title),
            body=note.body,
        )
        sys.stdout.write(frontmatter.serialize(doc).decode("utf-8"))
    else:
        print(note.body)


def _editor_loop(initial_body: str) -> str:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w+", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(initial_body)
        path = tf.name
    try:
        result = subprocess.run([editor, path])
        if result.returncode != 0:
            print("editor exited non-zero, aborting", file=sys.stderr)
            raise SystemExit(1)
        new_body = Path(path).read_text()
    finally:
        Path(path).unlink(missing_ok=True)
    if new_body.strip() == initial_body.strip():
        print("note unchanged, no write", file=sys.stderr)
        raise SystemExit(1)
    return new_body


@app.command(name="edit")
def edit(
    slug_query: str,
    seq: int,
    /,
    *,
    from_: Annotated[str | None, Parameter(name=["--from"])] = None,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Rewrite a note's body. Uses --from PATH|- or opens $EDITOR."""
    repo, store = _repo_and_store()
    now_obj = to_utc(now) if now else now_utc()
    try:
        note = notes_service.read_note(repo, store, slug_query, seq)
    except Exception as exc:
        _handle_service_error(exc, verb="edit")
        return
    if from_ == "-":
        new_body = sys.stdin.read()
    elif from_ is not None:
        new_body = Path(from_).read_text()
    else:
        new_body = _editor_loop(note.body)
    try:
        notes_service.edit_note(
            repo, store, slug_query, seq, body=new_body, now=now_obj
        )
    except Exception as exc:
        _handle_service_error(exc, verb="edit")
        return
    print(f"edited: {slug_query} #{seq}")


@app.command(name="remove")
def remove(
    slug_query: str,
    seq: int,
    /,
    *,
    now: Annotated[datetime | None, Parameter(show=False)] = None,
) -> None:
    """Delete a note. Permanent — the seq stays gone."""
    repo, store = _repo_and_store()
    now_obj = to_utc(now) if now else now_utc()
    try:
        notes_service.remove_note(repo, store, slug_query, seq, now=now_obj)
    except Exception as exc:
        _handle_service_error(exc, verb="remove")
        return
    print(f"removed: {slug_query} #{seq}")
```

- [ ] **Step 4: Run CLI tests**

Run: `uv run pytest tests/commands/test_cmd_note.py -v`
Expected: PASS for all tests. If `cyclopts` doesn't support `Annotated[..., Parameter(name=[...])]` exactly as written, check existing patterns in `commands/file.py` or `commands/set.py` and adapt.

If a test fails because of how `cyclopts` parses positional-optional arguments (`body: str | None = None`), inspect how `commands/log.py` handles its own optional-positional cases and align.

- [ ] **Step 5: Lint/type-check**

Run: `uv run ruff check src/jobhound/commands/note.py tests/commands/test_cmd_note.py && uv run ty check src/jobhound/commands/note.py`
Expected: clean.

- [ ] **Step 6: Run full suite**

Run: `uv run pytest -q`
Expected: PASS, except MCP tests (Task 9 fixes those).

- [ ] **Step 7: Commit**

```bash
git add src/jobhound/commands/note.py tests/commands/test_cmd_note.py
git commit -m "feat!: rewrite jh note as add/list/show/edit/remove group

BREAKING CHANGE: jh note add no longer takes --msg; pass BODY positionally
or via --from PATH|-. New verbs: list, show, edit, remove."
```

---

## Task 9: MCP — rewrite add_note + add four tools

**Files:**
- Modify: `src/jobhound/mcp/tools/ops.py`
- Modify: `src/jobhound/mcp/errors.py`
- Modify: `tests/mcp/test_tools_ops.py`

- [ ] **Step 1: Read existing MCP error translation layer**

```bash
cat src/jobhound/mcp/errors.py
```

Identify the pattern for adding new exception → response translations. Most likely it's a dispatch on `type(exc).__name__` or `isinstance` chain in `exception_to_response`. Match that pattern.

- [ ] **Step 2: Write failing test for new add_note response shape**

In `tests/mcp/test_tools_ops.py`, modify existing `add_note` tests and add new ones (use the patterns already in the file — inspect first):

```python
def test_add_note_returns_seq_and_filename(seeded_repo):
    from jobhound.mcp.tools.ops import add_note
    import json
    raw = add_note(seeded_repo, slug="acme", body="hello")
    payload = json.loads(raw)
    assert payload["note"]["seq"] == 1
    assert payload["note"]["filename"] == "1.md"
    assert "opportunity" in payload


def test_list_notes_empty(seeded_repo):
    from jobhound.mcp.tools.ops import list_notes
    import json
    payload = json.loads(list_notes(seeded_repo, slug="acme"))
    assert payload["notes"] == []


def test_list_notes_after_adds(seeded_repo):
    from jobhound.mcp.tools.ops import add_note, list_notes
    import json
    add_note(seeded_repo, slug="acme", body="a")
    add_note(seeded_repo, slug="acme", body="b", title="kickoff")
    payload = json.loads(list_notes(seeded_repo, slug="acme"))
    assert [n["seq"] for n in payload["notes"]] == [1, 2]
    assert payload["notes"][1]["title"] == "kickoff"


def test_read_note_returns_body_and_revision(seeded_repo):
    from jobhound.mcp.tools.ops import add_note, read_note
    import json
    add_note(seeded_repo, slug="acme", body="hello there")
    payload = json.loads(read_note(seeded_repo, slug="acme", seq=1))
    assert payload["note"]["body"] == "hello there"
    assert payload["note"]["revision"]


def test_edit_note_preserves_metadata(seeded_repo):
    from jobhound.mcp.tools.ops import add_note, edit_note, read_note
    import json
    add_note(seeded_repo, slug="acme", body="v1", title="greeting")
    edit_note(seeded_repo, slug="acme", seq=1, body="v2")
    payload = json.loads(read_note(seeded_repo, slug="acme", seq=1))
    assert payload["note"]["title"] == "greeting"
    assert payload["note"]["body"] == "v2"


def test_remove_note(seeded_repo):
    from jobhound.mcp.tools.ops import add_note, remove_note
    import json
    add_note(seeded_repo, slug="acme", body="x")
    payload = json.loads(remove_note(seeded_repo, slug="acme", seq=1))
    assert payload["removed_seq"] == 1


def test_read_note_missing_seq_returns_error(seeded_repo):
    from jobhound.mcp.tools.ops import read_note
    import json
    payload = json.loads(read_note(seeded_repo, slug="acme", seq=99))
    assert payload["error"] == "note_not_found"
```

(Reuse the `seeded_repo` fixture that should exist in `tests/mcp/conftest.py`; if not, copy the pattern from existing tests in `test_tools_ops.py`.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/mcp/test_tools_ops.py -v`
Expected: most tests fail (the new ones don't have implementations; the old `add_note` ones may fail because it now needs the new shape).

- [ ] **Step 4: Add error translations**

In `src/jobhound/mcp/errors.py`, add cases for the four new exceptions in `exception_to_response` (or whatever dispatch function exists). Follow the existing pattern. Example additions:

```python
from jobhound.application.notes_service import (
    EmptyBodyError,
    NoteFilenameError,
    NoteNotFoundError,
    TitleSlugError,
)

# Inside the dispatch:
if isinstance(exc, NoteNotFoundError):
    return {"error": "note_not_found", "tool": tool, "slug": exc.slug, "seq": exc.seq}
if isinstance(exc, EmptyBodyError):
    return {"error": "empty_body", "tool": tool}
if isinstance(exc, NoteFilenameError):
    return {"error": "note_filename_invalid", "tool": tool,
            "filename": exc.filename, "reason": exc.reason}
if isinstance(exc, TitleSlugError):
    return {"error": "title_slug_invalid", "tool": tool,
            "title": exc.title, "reason": exc.reason}
```

- [ ] **Step 5: Rewrite add_note and add four new tools in mcp/tools/ops.py**

In `src/jobhound/mcp/tools/ops.py`, replace the existing `add_note` function and add four new ones:

```python
def _note_dict(note) -> dict:
    return {
        "seq": note.seq,
        "filename": note.filename,
        "created": note.created.isoformat().replace("+00:00", "Z"),
        "title": note.title,
    }


def add_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    body: str,
    title: str | None = None,
    today: str | None = None,
) -> str:
    from jobhound.application import notes_service
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    now = (
        datetime(*(date.fromisoformat(today).timetuple()[:3]), tzinfo=UTC)
        if today
        else now_utc()
    )
    store = GitLocalFileStore(repo.paths)
    try:
        result = notes_service.add_note(
            repo, store, slug, body=body, title=title, now=now
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="add_note"))
    payload = mutation_response(result.before, result.after, result.opp_dir, now=now)
    payload["note"] = {
        "seq": result.seq,
        "filename": result.filename,
        "created": now.isoformat().replace("+00:00", "Z"),
        "title": title,
    }
    return json.dumps(payload)


def list_notes(repo: OpportunityRepository, *, slug: str) -> str:
    from jobhound.application import notes_service
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    store = GitLocalFileStore(repo.paths)
    try:
        summaries = notes_service.list_notes(repo, store, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="list_notes"))
    return json.dumps({
        "slug": slug,
        "notes": [_note_dict(s) for s in summaries],
    })


def read_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    seq: int,
    with_frontmatter: bool = False,
) -> str:
    from jobhound.application import frontmatter as fm_module
    from jobhound.application import notes_service
    from jobhound.application.frontmatter import Document, Frontmatter
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    store = GitLocalFileStore(repo.paths)
    try:
        note = notes_service.read_note(repo, store, slug, seq)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="read_note"))
    if with_frontmatter:
        doc = Document(
            frontmatter=Frontmatter(created=note.created, title=note.title),
            body=note.body,
        )
        body_out = fm_module.serialize(doc).decode("utf-8")
    else:
        body_out = note.body
    return json.dumps({
        "slug": slug,
        "note": {
            **_note_dict(note),
            "body": body_out,
            "revision": str(note.revision),
        },
    })


def edit_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    seq: int,
    body: str,
    base_revision: str | None = None,
    today: str | None = None,
) -> str:
    from jobhound.application import notes_service
    from jobhound.application.revisions import Revision
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    now = (
        datetime(*(date.fromisoformat(today).timetuple()[:3]), tzinfo=UTC)
        if today
        else now_utc()
    )
    store = GitLocalFileStore(repo.paths)
    rev: Revision | None = Revision(base_revision) if base_revision else None
    try:
        before, after, refreshed = notes_service.edit_note(
            repo, store, slug, seq, body=body, base_revision=rev, now=now
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="edit_note"))
    _, opp_dir = repo.find(slug)
    payload = mutation_response(before, after, opp_dir, now=now)
    payload["note"] = {
        **_note_dict(refreshed),
        "body": refreshed.body,
        "revision": str(refreshed.revision),
    }
    return json.dumps(payload)


def remove_note(
    repo: OpportunityRepository,
    *,
    slug: str,
    seq: int,
    today: str | None = None,
) -> str:
    from jobhound.application import notes_service
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    now = (
        datetime(*(date.fromisoformat(today).timetuple()[:3]), tzinfo=UTC)
        if today
        else now_utc()
    )
    store = GitLocalFileStore(repo.paths)
    try:
        before, after, removed_seq = notes_service.remove_note(
            repo, store, slug, seq, now=now
        )
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="remove_note"))
    _, opp_dir = repo.find(slug)
    payload = mutation_response(before, after, opp_dir, now=now)
    payload["removed_seq"] = removed_seq
    return json.dumps(payload)
```

Also update the `register` function at the bottom of the file to register the four new tools:

```python
def register(app: FastMCP, repo: OpportunityRepository) -> None:
    @app.tool(
        name="add_note",
        description="Write a new note on an opportunity. Returns the assigned seq.",
    )
    def _add(slug: str, body: str, title: str | None = None, today: str | None = None) -> str:
        return add_note(repo, slug=slug, body=body, title=title, today=today)

    @app.tool(
        name="list_notes",
        description="List notes on an opportunity (metadata only, no bodies).",
    )
    def _ln(slug: str) -> str:
        return list_notes(repo, slug=slug)

    @app.tool(
        name="read_note",
        description="Read one note's body and metadata.",
    )
    def _rn(slug: str, seq: int, with_frontmatter: bool = False) -> str:
        return read_note(repo, slug=slug, seq=seq, with_frontmatter=with_frontmatter)

    @app.tool(
        name="edit_note",
        description="Rewrite a note's body. Preserves created and title.",
    )
    def _en(
        slug: str,
        seq: int,
        body: str,
        base_revision: str | None = None,
        today: str | None = None,
    ) -> str:
        return edit_note(repo, slug=slug, seq=seq, body=body,
                         base_revision=base_revision, today=today)

    @app.tool(
        name="remove_note",
        description="Delete a note. Permanent — gap stays in the seq sequence.",
    )
    def _del_note(slug: str, seq: int, today: str | None = None) -> str:
        return remove_note(repo, slug=slug, seq=seq, today=today)

    # (existing archive_opportunity, unarchive_opportunity, delete_opportunity decorators stay)
```

- [ ] **Step 6: Run MCP tests**

Run: `uv run pytest tests/mcp/test_tools_ops.py -v`
Expected: PASS.

- [ ] **Step 7: Lint/type-check**

Run: `uv run ruff check src/jobhound/mcp/ && uv run ty check src/jobhound/mcp/`
Expected: clean.

- [ ] **Step 8: Run full suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/jobhound/mcp/tools/ops.py src/jobhound/mcp/errors.py tests/mcp/test_tools_ops.py
git commit -m "feat(mcp): rewrite add_note, add list/read/edit/remove notes tools"
```

---

## Task 10: Migration script

**Files:**
- Create: `scripts/migrate_notes_to_directory.py`
- Create: `tests/scripts/test_migrate_notes.py`

- [ ] **Step 1: Write failing tests for the parser**

Create `tests/scripts/test_migrate_notes.py`:

```python
"""Tests for scripts/migrate_notes_to_directory.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _load_script():
    """Import the migration script as a module."""
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "migrate_notes_to_directory.py"
    spec = importlib.util.spec_from_file_location("migrate_notes", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["migrate_notes"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_parses_bullet_style():
    m = _load_script()
    notes = m.parse_notes_md(
        "# Acme Running Notes\n"
        "\n"
        "- 2026-05-02T14:11:08Z first contact made\n"
        "- 2026-05-08T09:22:14Z scheduled phone screen\n"
    )
    assert len(notes) == 2
    assert notes[0].created == datetime(2026, 5, 2, 14, 11, 8, tzinfo=UTC)
    assert notes[0].body == "first contact made"
    assert notes[1].body == "scheduled phone screen"


def test_parses_h2_prose_style():
    m = _load_script()
    notes = m.parse_notes_md(
        "## 2026-05-02 — kickoff\n"
        "\n"
        "First call with Sarah. Good vibes.\n"
        "Multi-paragraph body.\n"
        "\n"
        "## 2026-05-08\n"
        "\n"
        "Second call.\n"
    )
    assert len(notes) == 2
    assert notes[0].created == datetime(2026, 5, 2, 0, 0, 0, tzinfo=UTC)
    assert "First call" in notes[0].body
    assert "Second call" in notes[1].body


def test_skips_empty_bodies():
    m = _load_script()
    notes = m.parse_notes_md(
        "## 2026-05-02\n"
        "\n"
        "## 2026-05-08\n"
        "Real content here.\n"
    )
    # First H2 block is empty body → skipped
    assert len(notes) == 1
    assert notes[0].created.day == 8


def test_discards_pre_first_marker_preamble():
    m = _load_script()
    notes = m.parse_notes_md(
        "# Some title\n"
        "Random text.\n"
        "\n"
        "- 2026-05-02T14:11:08Z actual note\n"
    )
    assert len(notes) == 1
    assert notes[0].body == "actual note"


def test_empty_file_yields_nothing():
    m = _load_script()
    assert m.parse_notes_md("") == []
    assert m.parse_notes_md("\n\n   \n") == []


def test_apply_writes_seq_files_and_meta(tmp_path: Path):
    """End-to-end --apply against a synthesized opp dir."""
    m = _load_script()
    # Build a minimal data root with one opp containing notes.md
    db = tmp_path / "db"
    opps = db / "opportunities" / "2026-05-acme"
    opps.mkdir(parents=True)
    (db / "archive").mkdir()
    (opps / "meta.toml").write_text(
        'company = "Acme"\nrole = "EM"\nslug = "2026-05-acme"\n'
        'status = "applied"\npriority = "medium"\n'
    )
    (opps / "notes.md").write_text(
        "- 2026-05-02T14:11:08Z first\n"
        "- 2026-05-08T09:22:14Z second\n"
    )
    subprocess.run(["git", "init", "--quiet", str(db)], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(db), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db), "commit", "-q", "-m", "seed"], check=True)

    m.migrate_one(opps, apply=True)

    assert (opps / "notes" / "1.md").exists()
    assert (opps / "notes" / "2.md").exists()
    assert not (opps / "notes.md").exists()
    from jobhound.infrastructure.meta_io import read_meta
    assert read_meta(opps / "meta.toml").notes_next_seq == 3


def test_idempotent_when_already_migrated(tmp_path: Path):
    m = _load_script()
    opps = tmp_path / "db" / "opportunities" / "2026-05-acme"
    opps.mkdir(parents=True)
    (opps / "notes").mkdir()
    (opps / "meta.toml").write_text(
        'company = "Acme"\nrole = "EM"\nslug = "2026-05-acme"\n'
        'status = "applied"\npriority = "medium"\n'
        "notes_next_seq = 1\n"
    )
    # No notes.md → should be a no-op
    result = m.migrate_one(opps, apply=True)
    assert result.status == "skipped"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/scripts/test_migrate_notes.py -v`
Expected: FAIL — script doesn't exist yet.

- [ ] **Step 3: Implement the migration script**

Create `scripts/migrate_notes_to_directory.py`:

```python
"""One-shot migration: per-opp `notes.md` → per-note files under `notes/`.

Usage:
    uv run scripts/migrate_notes_to_directory.py            # dry-run
    uv run scripts/migrate_notes_to_directory.py --apply
    uv run scripts/migrate_notes_to_directory.py --only acme,menlo
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import tomli_w

from jobhound.application.frontmatter import Document, Frontmatter, serialize
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


DATE_MARKER_H2 = re.compile(r"^## (\d{4}-\d{2}-\d{2})(?: — .*)?$")
DATE_MARKER_BUL = re.compile(r"^- (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) (.*)$")


@dataclass
class MarkerNote:
    created: datetime
    body: str


@dataclass
class MigrateResult:
    status: str             # "migrated" | "skipped" | "error"
    slug: str = ""
    count: int = 0
    detail: str = ""


def parse_notes_md(content: str) -> list[MarkerNote]:
    """Parse a notes.md file into individual notes per the decision grammar."""
    notes: list[MarkerNote] = []
    current_created: datetime | None = None
    current_body_lines: list[str] = []

    def flush() -> None:
        if current_created is None:
            return
        body = "\n".join(current_body_lines).strip()
        if body:
            notes.append(MarkerNote(created=current_created, body=body))

    for line in content.splitlines():
        m_h2 = DATE_MARKER_H2.match(line)
        m_bul = DATE_MARKER_BUL.match(line)
        if m_h2 is not None:
            flush()
            current_created = datetime.strptime(m_h2.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
            current_body_lines = []
        elif m_bul is not None:
            flush()
            current_created = datetime.strptime(m_bul.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            current_body_lines = [m_bul.group(2)]
        else:
            if current_created is not None:
                current_body_lines.append(line)
            # else: pre-first-marker preamble → discard
    flush()
    return notes


def _git_commit(db_root: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(db_root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db_root), "commit", "-q", "-m", message], check=True)


def _read_meta_raw(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _write_meta_raw(path: Path, data: dict) -> None:
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)


def migrate_one(opp_dir: Path, *, apply: bool) -> MigrateResult:
    """Migrate a single opp dir. Returns a result record."""
    slug = opp_dir.name
    notes_md = opp_dir / "notes.md"
    notes_dir = opp_dir / "notes"
    meta_path = opp_dir / "meta.toml"

    if not notes_md.exists():
        if notes_dir.exists():
            return MigrateResult(status="skipped", slug=slug, detail="already migrated")
        # No notes.md and no notes/ — scaffold empty notes/ and set counter
        if apply:
            notes_dir.mkdir(exist_ok=True)
            data = _read_meta_raw(meta_path)
            data.setdefault("notes_next_seq", 1)
            _write_meta_raw(meta_path, data)
        return MigrateResult(status="skipped", slug=slug, detail="no notes.md")

    if notes_dir.exists() and any(notes_dir.iterdir()):
        return MigrateResult(
            status="error", slug=slug,
            detail="notes/ already exists with content; refusing to merge",
        )

    notes = parse_notes_md(notes_md.read_text())
    # Sort by created ascending; assign seq 1..N
    notes.sort(key=lambda n: n.created)

    if not apply:
        return MigrateResult(status="migrated", slug=slug, count=len(notes),
                             detail="dry-run")

    notes_dir.mkdir(exist_ok=True)
    for seq, note in enumerate(notes, start=1):
        doc = Document(
            frontmatter=Frontmatter(created=note.created),
            body=note.body,
        )
        (notes_dir / f"{seq}.md").write_bytes(serialize(doc))

    notes_md.unlink()

    data = _read_meta_raw(meta_path)
    data["notes_next_seq"] = len(notes) + 1
    _write_meta_raw(meta_path, data)

    return MigrateResult(status="migrated", slug=slug, count=len(notes))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run).")
    parser.add_argument("--only", type=str, default="",
                        help="Comma-separated slug substrings to restrict the run.")
    args = parser.parse_args(argv)

    cfg = load_config()
    paths = paths_from_config(cfg)

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    targets: list[Path] = []
    for root in (paths.opportunities_dir, paths.archive_dir):
        if not root.exists():
            continue
        for opp_dir in sorted(root.iterdir()):
            if not opp_dir.is_dir():
                continue
            if only and not any(s in opp_dir.name for s in only):
                continue
            targets.append(opp_dir)

    results: list[MigrateResult] = []
    for opp_dir in targets:
        try:
            r = migrate_one(opp_dir, apply=args.apply)
        except Exception as exc:
            results.append(MigrateResult(status="error", slug=opp_dir.name, detail=str(exc)))
            print(f"=== {opp_dir.name} === ERROR: {exc}", file=sys.stderr)
            continue
        results.append(r)
        if r.status == "migrated":
            print(f"=== {r.slug} ===  {r.count} notes -> notes/{{1..{r.count}}}.md")
        elif r.status == "skipped":
            print(f"=== {r.slug} ===  skipped ({r.detail})")

        if args.apply and r.status == "migrated":
            _git_commit(paths.db_root, f"migrate: notes.md → notes/ for {r.slug}")

    migrated = sum(1 for r in results if r.status == "migrated")
    skipped = sum(1 for r in results if r.status == "skipped")
    errored = sum(1 for r in results if r.status == "error")
    total_notes = sum(r.count for r in results)

    print()
    print("Summary:")
    print(f"  {len(results)} opps scanned")
    print(f"  {migrated} opps migrated ({total_notes} notes)")
    print(f"  {skipped} opps skipped")
    print(f"  {errored} opps errored")
    if not args.apply:
        print()
        print("Dry-run — no files changed. Re-run with --apply to write.")

    return 0 if errored == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run script tests**

Run: `uv run pytest tests/scripts/test_migrate_notes.py -v`
Expected: PASS.

- [ ] **Step 5: Lint/type-check**

Run: `uv run ruff check scripts/migrate_notes_to_directory.py tests/scripts/test_migrate_notes.py && uv run ty check scripts/migrate_notes_to_directory.py`
Expected: clean.

- [ ] **Step 6: Manual smoke test on a fresh data root**

```bash
# Create a tiny temp data root with one opp
mkdir -p /tmp/jh-smoke/db/opportunities/2026-05-x
mkdir -p /tmp/jh-smoke/db/archive
cd /tmp/jh-smoke/db && git init -q && git config user.name t && git config user.email t@t
cat > opportunities/2026-05-x/meta.toml << 'EOF'
company = "X"
role = "EM"
slug = "2026-05-x"
status = "applied"
priority = "medium"
EOF
cat > opportunities/2026-05-x/notes.md << 'EOF'
- 2026-05-02T14:11:08Z first contact
- 2026-05-08T09:22:14Z phone screen scheduled
EOF
git add . && git commit -q -m seed

JOBHOUND_DB_PATH=/tmp/jh-smoke/db uv run scripts/migrate_notes_to_directory.py
JOBHOUND_DB_PATH=/tmp/jh-smoke/db uv run scripts/migrate_notes_to_directory.py --apply
ls /tmp/jh-smoke/db/opportunities/2026-05-x/notes/
cat /tmp/jh-smoke/db/opportunities/2026-05-x/notes/1.md
git -C /tmp/jh-smoke/db log --oneline
rm -rf /tmp/jh-smoke
```

Expected: dry-run prints plan; `--apply` writes `1.md` and `2.md`, commits per-opp. `1.md` contains the frontmatter and body. Note: `JOBHOUND_DB_PATH` may not be the exact env-var name — check `infrastructure/config.py` for the actual variable.

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_notes_to_directory.py tests/scripts/test_migrate_notes.py
git commit -m "feat(scripts): add notes.md -> notes/ migration script"
```

---

## Task 11: Docs + CHANGELOG

**Files:**
- Modify: `docs/commands.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md` (or rely on release-please footer in commit messages)

- [ ] **Step 1: Update docs/commands.md**

Open `docs/commands.md`. Find the existing `jh add note` or `jh note add --msg` section. Replace with:

```markdown
### `jh note add SLUG BODY [--title SLUG] [--from PATH|-]`

Write a new note on an opportunity. `BODY` is positional. Mutually
exclusive with `--from PATH|-`. `--title` is slugified for the
filename suffix.

Examples:

```
jh note add acme "Charlotte mentioned a 4-stage loop"
jh note add acme "x" --title charlotte-prep
jh note add acme --from draft.md
jh note add acme --from -        # read body from stdin
```

Returns the assigned seq: `noted: 2026-05-acme #5`.

### `jh note list SLUG [--reverse]`

List notes for an opportunity, sorted by seq ascending (chronological).
Gaps appear when notes have been removed — they are permanent.

### `jh note show SLUG SEQ [--with-frontmatter]`

Print one note's body to stdout. `--with-frontmatter` prints the file
as stored, including the `+++` block.

### `jh note edit SLUG SEQ [--from PATH|-]`

Rewrite a note's body. With `--from`, reads from a path or stdin.
Without, opens `$EDITOR` (or `$VISUAL`, then `vi`) on a temp file
prefilled with the current body. `created` and `title` are preserved.

### `jh note remove SLUG SEQ`

Delete a note permanently. The seq is NOT reused — the next note added
gets `max(existing seqs) + 1`, preserving stable IDs.
```

(Remove any prior `jh add note` section.)

- [ ] **Step 2: Update README.md**

In `README.md`, search for:
- `jh add note`
- `notes.md`

Replace `jh add note <slug> --msg "..."` examples with `jh note add <slug> "..."`. Replace any reference to "notes.md" with "notes/" or "per-note files under notes/" where contextually appropriate.

- [ ] **Step 3: Verify with grep**

```bash
grep -n "add note\|notes.md\|--msg" README.md docs/commands.md
```

Expected: no remaining references to the old shape (except possibly in CHANGELOG or this design's "Supersedes" notes).

- [ ] **Step 4: CHANGELOG / commit-message-footer**

This project uses release-please. The breaking-change footer goes in the commit messages of Tasks 8 and 9 (already included). Verify by:

```bash
git log --grep="BREAKING" -n
```

Expected: at least the Task 8 commit lists the breaking change.

If `CHANGELOG.md` is hand-maintained in this repo (check existence + structure first), add a top-line entry. Otherwise skip — release-please will handle it.

- [ ] **Step 5: Commit**

```bash
git add docs/commands.md README.md
# Add CHANGELOG.md too if you edited it
git commit -m "docs: update commands.md and README for jh note CRUD verbs"
```

---

## Task 12: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: ALL PASS.

- [ ] **Step 2: Lint and type-check the full project**

Run: `uv run ruff check src/ tests/ scripts/ && uv run ty check src/`
Expected: clean.

- [ ] **Step 3: Verify the working tree**

Run: `git status && git log main..HEAD --oneline`
Expected:
- Clean working tree.
- ~11 commits since branching off main, in the order from the plan.

- [ ] **Step 4: Live-corpus dry-run (PERFORM BEFORE PUSHING)**

```bash
uv run scripts/migrate_notes_to_directory.py
```

Inspect the output for the 6 known files (Menlo × 2, Tailscale, UKHSA, 2 empty). Check:
- Are bullet bodies stripped of the `- <ts>` prefix?
- Are H2 prose blocks captured as multi-line bodies?
- Are the 2 empty files reported as skipped?
- Any unexpected errors?

Spot-check 2-3 planned outputs visually. If anything looks wrong, fix the script (or report what you saw) and re-run dry-run.

- [ ] **Step 5: Apply the migration on the live data root (USER DECIDES TIMING)**

```bash
uv run scripts/migrate_notes_to_directory.py --apply
```

Verify with `git -C <data_root> log --oneline` that one commit per migrated opp was produced.

- [ ] **Step 6: Push and open PR**

```bash
git push -u origin notes-storage-migration
gh pr create --title "feat!: replace notes.md with per-note files under notes/ (#102)" \
             --body "$(cat <<'EOF'
## Summary

Implements #102 per `docs/superpowers/specs/2026-06-08-notes-storage-migration-design.md`.

- Each note is now a file under `<opp>/notes/<seq>.md` (optional title slug suffix).
- TOML frontmatter (`+++ ... +++`) carries `created` and optional `title`.
- Per-opportunity monotonic sequence counter (`notes_next_seq` in `meta.toml`) — note IDs are stable across deletes.
- New CLI verbs: `jh note list/show/edit/remove`. Rewritten `jh note add` takes positional body and `--title` / `--from PATH|-`.
- Matching MCP tools: `list_notes`, `read_note`, `edit_note`, `remove_note`. `add_note` updated.
- One-shot migration script ports existing `notes.md` files in chronological order.

Amends `decisions/2026-06-08-notes-storage-model.md` with a Revision section recording the shift from Unix-ts to sequence-id filenames.

## Test plan

- [x] Unit tests for frontmatter parser/serializer (round-trip + property)
- [x] Service tests for notes_service (add/list/read/edit/remove)
- [x] CLI tests for all five verbs (end-to-end against a temp data root)
- [x] MCP tests for all five tools
- [x] Migration script tests (parser grammar + apply round-trip)
- [x] Live-corpus dry-run reviewed before `--apply`
EOF
)"
```

---

## Self-review (checked by author before handing off)

**Spec coverage:** All eight spec sections have at least one task. Section 1 architecture → Tasks 2-4 boundaries; Section 2 frontmatter → Task 2; Section 3 notes_service → Tasks 4-6; Section 4 CLI → Task 8; Section 5 MCP → Task 9; Section 6 repo scaffolding → Tasks 3, 7; Section 7 migration → Task 10; Section 8 cross-cutting (tests, docs, CHANGELOG, decision amendment) → Tasks 0, 11. The decision-doc amendment is Task 0 (first commit, per spec). Live-corpus dry-run is Step 4 of Task 12, separated from the implementation tasks.

**Placeholder scan:** No "TBD" / "TODO" / "fill in" / "implement appropriately" remain. Two places intentionally direct the implementer to inspect existing code:
- Task 8 Step 1: "Inspect existing `tests/commands/` test files to confirm the `_setup_env` / env-var keys are correct" — necessary because I haven't read every test harness file; the patterns are too thin to copy blindly without verification.
- Task 9 Step 1: "Read existing MCP error translation layer" — `mcp/errors.py` wasn't read during plan-writing; the precise dispatch shape is something the implementer must see firsthand.

Both are bounded reads (one file each), not open-ended exploration.

**Type consistency:** `Note`, `NoteSummary`, `AddNoteResult`, `Frontmatter`, `Document`, `EmptyBodyError`, `NoteNotFoundError`, `NoteFilenameError`, `TitleSlugError`, `notes_next_seq`, `with_notes_next_seq` — used consistently across all tasks. CLI `note add` returns `result.seq` and `result.after.slug`, matching the `AddNoteResult` dataclass defined in Task 4. MCP tools call `notes_service.add_note(repo, store, slug, body=..., title=..., now=...)`, matching the signature in Task 4.
