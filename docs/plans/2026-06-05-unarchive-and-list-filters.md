# Unarchive + List Filters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public `unarchive` verb (CLI + MCP) and `--all` / `--archived` / `--status` filters on `jh list` and `jh stats`, mirroring the existing `archive` and `list` surfaces.

**Architecture:** Each layer gets one additive change that mirrors an existing pattern. The repository gains `unarchive(opp_dir)` as the symmetric inverse of `archive(opp_dir)`. The application service gains `unarchive_opportunity(repo, slug)` mirroring `archive_opportunity`. The CLI gains a new `commands/unarchive.py` modeled on `commands/archive.py`, plus filter flags on `list` and `stats` that route through the already-built `OpportunityQuery.list()` / `.stats()` with `Filters`. MCP gains an `unarchive_opportunity(slug)` tool mirroring `archive_opportunity`.

**Tech Stack:** Python 3.12 (uv-managed venv), cyclopts for CLI parameters, FastMCP for MCP tools, pytest + pytest-cov + pytest-asyncio for tests, ruff + ty for lint/types. Run everything through `uv run --no-sync <cmd>`.

**Spec:** `docs/specs/2026-06-05-unarchive-and-list-filters-design.md` is the contract; this plan is the execution.

**Branch:** `feat/unarchive-and-list-filters` (already cut from `main` at commit `667aff8`).

---

## File Structure

### Files created

- `src/jobhound/commands/unarchive.py` — new CLI command (Task 3)
- `tests/test_cmd_unarchive.py` — CLI behavior tests for `jh unarchive` (Tasks 3, 4)

### Files modified

| File | Why |
|---|---|
| `src/jobhound/infrastructure/repository.py` | Add `unarchive(opp_dir)` method (Task 1) |
| `src/jobhound/application/ops_service.py` | Add `unarchive_opportunity(repo, slug)` (Task 2) |
| `src/jobhound/cli.py` | Register `unarchive` command (Task 3) |
| `src/jobhound/commands/_complete.py` | Add `unarchive` to top-level + slug-position tables; add per-command slug-source map so `unarchive` completes from archive dir (Task 3) |
| `src/jobhound/commands/list_.py` | Rewrite `run()` to use `OpportunityQuery`; add `--all` / `--archived` / `--status` flags and trailing `*` marker (Task 5) |
| `src/jobhound/commands/stats.py` | Add same filter flags; route through `OpportunityQuery.stats(Filters(...))` (Task 6) |
| `src/jobhound/mcp/tools/ops.py` | Add `unarchive_opportunity` function + tool registration (Task 7) |
| `src/jobhound/commands/archive.py` | Clean directory names out of module docstring (Task 8) |
| `tests/test_repository.py` | Tests for `unarchive` (Task 1) |
| `tests/application/test_ops_service.py` | Test for `unarchive_opportunity` (Task 2) |
| `tests/commands/test_cmd_complete.py` | Tests for `unarchive` slug-completion (Task 3) |
| `tests/test_cmd_list.py` | Tests for `--all` / `--archived` / `--status` and asterisk marker (Task 5) |
| `tests/test_cmd_stats.py` | Tests for `--all` / `--archived` / `--status` on stats (Task 6) |
| `tests/mcp/test_tools_ops.py` | Round-trip test for `archive_opportunity` → `unarchive_opportunity` (Task 7) |

### Files NOT touched

- `src/jobhound/application/query.py` — `Filters` and `OpportunityQuery.list()` already support `statuses` and `include_archived`.
- `src/jobhound/application/snapshots.py` — `OpportunitySnapshot.archived` already exists.
- `src/jobhound/domain/*.py` — no domain changes; archived stays a storage concept.

---

## Conventions used across all tasks

**Working directory:** `/Users/robin/code/github.com/yo61/jobhound` for every command.

**Test runner:** `uv run --no-sync pytest <args>`. Never `pytest <args>` directly.

**Pre-commit hooks:** ruff-check (with `--fix`), ruff-format, ty, pytest. They run automatically on `git commit`. If they fail, fix the underlying issue and commit a NEW commit; never `--amend` or `--no-verify`.

**Commits per task:** one task = one commit. Use conventional-commits format: `feat(scope): ...`, `test(scope): ...` etc. Subject ≤ 72 chars. Imperative mood. End the commit body with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.

**Adding a Cyclopts named flag whose Python name collides with a builtin:** use `Annotated[T, Parameter(name=["--flag-name"])]` and rename the Python parameter (`all_`, `list_`, etc.). See `commands/show.py:25` for `--json` → `json_out`.

**Reading test failures during TDD:** "Expected: FAIL with X" means the test name should exist and reach the assertion. If pytest reports a collection error (import failure), the test signature/import line is wrong — fix it before continuing.

---

## Task 1: Add `repo.unarchive()` repository method

**Goal:** Add `OpportunityRepository.unarchive(opp_dir)`, mirroring `.archive()`. Pure file-system + git side; no slug resolution at this layer.

**Files:**
- Modify: `src/jobhound/infrastructure/repository.py:85-92` (insert `unarchive` after `archive`)
- Modify: `tests/test_repository.py` (append two new tests)

### Steps

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_repository.py`:

```python
def test_unarchive_moves_dir_back(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new")
    _, opp_dir = repo.find("acme")
    repo.archive(opp_dir)

    archived_dir = paths.archive_dir / "2026-05-acme-eng"
    repo.unarchive(archived_dir)

    assert not archived_dir.exists()
    assert (paths.opportunities_dir / "2026-05-acme-eng" / "meta.toml").is_file()


def test_unarchive_rejects_collision(tmp_path: Path) -> None:
    cfg = _make_config(tmp_path)
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    repo.create(_make_opp(), message="new")
    _, opp_dir = repo.find("acme")
    repo.archive(opp_dir)

    # Re-create an active opportunity with the same slug, then try to unarchive
    # the archived one — target exists.
    repo.create(_make_opp(), message="new")
    archived_dir = paths.archive_dir / "2026-05-acme-eng"

    with pytest.raises(FileExistsError):
        repo.unarchive(archived_dir)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_repository.py::test_unarchive_moves_dir_back tests/test_repository.py::test_unarchive_rejects_collision -v`

Expected: FAIL with `AttributeError: 'OpportunityRepository' object has no attribute 'unarchive'`.

- [ ] **Step 3: Implement `unarchive` on the repository**

In `src/jobhound/infrastructure/repository.py`, immediately after the `archive` method (around line 92), add:

```python
    def unarchive(self, opp_dir: Path) -> None:
        """Move `opp_dir` from archive/ back to opportunities/."""
        dst = self.paths.opportunities_dir / opp_dir.name
        if dst.exists():
            raise FileExistsError(f"target folder already exists: {dst}")
        self.paths.opportunities_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(opp_dir, dst)
        self._commit(f"unarchive: {opp_dir.name}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_repository.py -v`

Expected: All tests in `test_repository.py` PASS, including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/infrastructure/repository.py tests/test_repository.py
git commit -m "$(cat <<'EOF'
feat(repository): add unarchive method as inverse of archive

Mirrors `archive`: refuses if the destination already exists, then
shutil.move's the opp_dir from archive/ back to opportunities/ and
records an `unarchive: <slug>` commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add `ops_service.unarchive_opportunity()`

**Goal:** Application-layer service that takes a slug, finds the archived opp, calls `repo.unarchive`, and returns the standard `(before, after, new_dir)` triple.

**Files:**
- Modify: `src/jobhound/application/ops_service.py` (insert after `archive_opportunity`)
- Modify: `tests/application/test_ops_service.py` (one new test)

### Steps

- [ ] **Step 1: Write the failing test**

Append to `tests/application/test_ops_service.py`:

```python
def test_unarchive_moves_back_to_opportunities(tmp_path: Path) -> None:
    repo, paths, _ = _seeded(tmp_path)
    ops_service.archive_opportunity(repo, "acme")
    assert (paths.archive_dir / "2026-05-acme").exists()

    _, _, new_dir = ops_service.unarchive_opportunity(repo, "acme")

    assert not (paths.archive_dir / "2026-05-acme").exists()
    assert (paths.opportunities_dir / "2026-05-acme").exists()
    assert new_dir == paths.opportunities_dir / "2026-05-acme"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest tests/application/test_ops_service.py::test_unarchive_moves_back_to_opportunities -v`

Expected: FAIL with `AttributeError: module 'jobhound.application.ops_service' has no attribute 'unarchive_opportunity'`.

- [ ] **Step 3: Implement the service function**

In `src/jobhound/application/ops_service.py`, immediately after `archive_opportunity` (around line 51), add:

```python
def unarchive_opportunity(
    repo: OpportunityRepository,
    slug: str,
) -> tuple[Opportunity, Opportunity, Path]:
    """Restore an archived opportunity. Returns (opp, opp, new_dir)."""
    from jobhound.domain.slug import resolve_slug

    opp_dir = resolve_slug(slug, repo.paths.archive_dir)
    opp = read_meta(opp_dir / "meta.toml")
    repo.unarchive(opp_dir)
    new_dir = repo.paths.opportunities_dir / opp_dir.name
    return opp, opp, new_dir
```

And ensure `read_meta` is imported at the top of the file; if not present, add `from jobhound.infrastructure.meta_io import read_meta`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/application/test_ops_service.py -v`

Expected: All ops_service tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/application/ops_service.py tests/application/test_ops_service.py
git commit -m "$(cat <<'EOF'
feat(ops): add unarchive_opportunity service function

Resolves the slug against the archived set (not the active set, since
the slug only makes sense there) and delegates to repo.unarchive.
Mirrors archive_opportunity's shape: returns (opp, opp, new_dir).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add `jh unarchive` CLI command + completion wiring

**Goal:** New top-level `jh unarchive <slug>` command. Registers in `cli.py`. Adds completion: `unarchive` is in the top-level set, takes a slug at position 0, and the slug source is `archive_dir` (not `opportunities_dir`).

The smart-error UX for "slug exists but is active" is added in Task 4.

**Files:**
- Create: `src/jobhound/commands/unarchive.py`
- Create: `tests/test_cmd_unarchive.py`
- Modify: `src/jobhound/cli.py` (register the command)
- Modify: `src/jobhound/commands/_complete.py` (add `unarchive` to tables; add per-command slug-source map)
- Modify: `tests/commands/test_cmd_complete.py` (add completion test)

### Steps

- [ ] **Step 1: Write the failing CLI behavior test**

Create `tests/test_cmd_unarchive.py`:

```python
"""Tests for `jh unarchive`."""

import subprocess


def _seed_archived(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    invoke(["archive", "foo"])


def test_unarchive_moves_folder_back(tmp_jh, invoke) -> None:
    _seed_archived(invoke)
    result = invoke(["unarchive", "foo"])
    assert result.exit_code == 0, result.output
    assert (tmp_jh.db_path / "opportunities" / "2026-05-foo-em").is_dir()
    assert not (tmp_jh.db_path / "archive" / "2026-05-foo-em").exists()
    log = subprocess.check_output(
        ["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True
    )
    assert "unarchive: 2026-05-foo-em" in log


def test_unarchive_prints_slug(tmp_jh, invoke) -> None:
    _seed_archived(invoke)
    result = invoke(["unarchive", "foo"])
    assert "unarchived: 2026-05-foo-em" in result.output


def test_unarchive_missing_slug_errors(tmp_jh, invoke) -> None:
    result = invoke(["unarchive", "nonesuch"])
    assert result.exit_code != 0
    assert "no archived opportunity matches" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_cmd_unarchive.py -v`

Expected: FAIL — `unarchive` is not a registered command, so cyclopts errors.

- [ ] **Step 3: Create the command module**

Create `src/jobhound/commands/unarchive.py`:

```python
"""`jh unarchive` — restore an archived opportunity."""

from __future__ import annotations

import sys

from jobhound.application import ops_service
from jobhound.domain.slug import SlugNotFoundError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import Paths, paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run(
    slug_query: str,
    /,
) -> None:
    """Unarchive an opportunity."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    Paths.ensure(paths)
    repo = OpportunityRepository(paths, cfg)
    try:
        _, _, new_dir = ops_service.unarchive_opportunity(repo, slug_query)
    except SlugNotFoundError:
        print(
            f"jh: no archived opportunity matches {slug_query!r}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"unarchived: {new_dir.name}")
```

- [ ] **Step 4: Register the command in `cli.py`**

In `src/jobhound/cli.py`, add the import (alphabetical, after `from jobhound.commands import set as cmd_set`):

```python
    from jobhound.commands import unarchive as cmd_unarchive
```

And add the registration right after the existing `_cyclopts_app.command(cmd_archive.run, name="archive")` line:

```python
    _cyclopts_app.command(cmd_unarchive.run, name="unarchive")
```

- [ ] **Step 5: Run CLI tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_cmd_unarchive.py -v`

Expected: All three tests PASS.

- [ ] **Step 6: Write the failing completion test**

Append to `tests/commands/test_cmd_complete.py`:

```python
def test_complete_top_level_includes_unarchive(invoke) -> None:
    """`jh __complete zsh jh ""` lists `unarchive`."""
    result = invoke(["__complete", "zsh", "jh", ""])
    out = set(result.output.split())
    assert "unarchive" in out


def test_complete_unarchive_returns_archived_slugs_only(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh unarchive ""` lists slugs from archive_dir, not opportunities."""
    # Seed one active and one archived opportunity, both with deterministic slugs.
    _seed_slug(tmp_jh.db_path, "2026-05-active-em")
    archived = tmp_jh.db_path / "archive" / "2026-05-archived-em"
    archived.mkdir(parents=True)
    (archived / "correspondence").mkdir()
    (archived / "meta.toml").write_text(
        'company = "X"\nrole = "Y"\nslug = "2026-05-archived-em"\n'
        'status = "rejected"\npriority = "high"\nsource = "X"\n'
        "applied_on = 2026-05-01T12:00:00+00:00\n"
        "last_activity = 2026-05-01T12:00:00+00:00\n"
        "tags = []\n",
    )

    result = invoke(["__complete", "zsh", "jh", "unarchive", ""])
    out = set(result.output.split())
    assert "2026-05-archived-em" in out
    assert "2026-05-active-em" not in out
```

- [ ] **Step 7: Run completion tests to verify they fail**

Run: `uv run --no-sync pytest tests/commands/test_cmd_complete.py::test_complete_top_level_includes_unarchive tests/commands/test_cmd_complete.py::test_complete_unarchive_returns_archived_slugs_only -v`

Expected: both FAIL — `unarchive` not in `_TOP_LEVEL_COMMANDS`, and `_complete_slug` only walks `opportunities_dir`.

- [ ] **Step 8: Wire `unarchive` into `_complete.py`**

In `src/jobhound/commands/_complete.py`:

a) Add `("unarchive",)` to `_SLUG_AT_POSITION` (insert alphabetically before `("withdraw",)` near line 36):

```python
        ("show",),
        ("unarchive",),
        ("withdraw",),
```

b) Add `"unarchive"` to `_TOP_LEVEL_COMMANDS` (insert alphabetically between `"stats"` and `"withdraw"` near line 137):

```python
        "show",
        "stats",
        "unarchive",
        "withdraw",
```

c) Refactor `_complete_slug` to take an explicit source directory, and add a per-command source map. Replace the existing `_complete_slug` (around lines 242-258) with:

```python
# cmd_path -> attribute name on `Paths` whose dir holds the slugs to complete.
# Default (when a cmd_path is missing) is `opportunities_dir`.
_SLUG_SOURCE_DIR: dict[tuple[str, ...], str] = {
    ("unarchive",): "archive_dir",
}


def _complete_slug(cmd_path: tuple[str, ...]) -> Iterable[str]:
    """Yield canonical slug names from the relevant directory for `cmd_path`.

    Most commands take active slugs; `unarchive` takes archived ones. Lazy-imports
    config / paths to keep the static-completion path fast.
    """
    from jobhound.infrastructure.config import load_config
    from jobhound.infrastructure.paths import paths_from_config

    cfg = load_config()
    paths = paths_from_config(cfg)
    source_attr = _SLUG_SOURCE_DIR.get(cmd_path, "opportunities_dir")
    source_dir = getattr(paths, source_attr)
    if not source_dir.exists():
        return
    for entry in source_dir.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            yield entry.name
```

d) Update the one caller of `_complete_slug` (near line 324) from `_complete_slug()` to `_complete_slug(cmd_path)`:

```python
    if len(in_positionals) == 0 and cmd_path in _SLUG_AT_POSITION:
        for slug in sorted(_complete_slug(cmd_path)):
            print(slug)
        return
```

- [ ] **Step 9: Run all completion tests to verify they pass**

Run: `uv run --no-sync pytest tests/commands/test_cmd_complete.py -v`

Expected: All completion tests PASS (existing + the two new ones).

- [ ] **Step 10: Run the full suite once before committing**

Run: `uv run --no-sync pytest -q`

Expected: All tests PASS.

- [ ] **Step 11: Commit**

```bash
git add src/jobhound/commands/unarchive.py src/jobhound/cli.py \
        src/jobhound/commands/_complete.py \
        tests/test_cmd_unarchive.py tests/commands/test_cmd_complete.py
git commit -m "$(cat <<'EOF'
feat(cli): add jh unarchive command

`jh unarchive <slug>` restores an archived opportunity. Slug resolution
looks in the archived set only; not-found yields a tailored error.
Wires shell completion so tab-complete after `jh unarchive ` lists
archived slugs (not active ones).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Smart error when slug names an active opportunity

**Goal:** When `jh unarchive <slug>` finds the slug only among active opportunities, the error names the active opportunity instead of saying "no archived opportunity matches".

Example:

```
$ jh unarchive acme
jh: 'acme' matches an active opportunity (2026-05-acme-em); nothing to unarchive
```

**Files:**
- Modify: `src/jobhound/commands/unarchive.py` (add fallback lookup in active dir)
- Modify: `tests/test_cmd_unarchive.py` (one new test)

### Steps

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cmd_unarchive.py`:

```python
def test_unarchive_smart_error_when_slug_is_active(tmp_jh, invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    result = invoke(["unarchive", "foo"])
    assert result.exit_code != 0
    assert "matches an active opportunity" in result.output
    assert "2026-05-foo-em" in result.output
    # Sanity: nothing was moved.
    assert (tmp_jh.db_path / "opportunities" / "2026-05-foo-em").exists()
    assert not (tmp_jh.db_path / "archive" / "2026-05-foo-em").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest tests/test_cmd_unarchive.py::test_unarchive_smart_error_when_slug_is_active -v`

Expected: FAIL — the current error is `"no archived opportunity matches 'foo'"`, not the smart message.

- [ ] **Step 3: Replace the `SlugNotFoundError` branch with the smart fallback**

In `src/jobhound/commands/unarchive.py`, change the `except SlugNotFoundError:` branch to:

```python
    except SlugNotFoundError:
        from jobhound.domain.slug import resolve_slug

        try:
            active_dir = resolve_slug(slug_query, paths.opportunities_dir)
        except SlugNotFoundError:
            print(
                f"jh: no archived opportunity matches {slug_query!r}",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
        print(
            f"jh: {slug_query!r} matches an active opportunity "
            f"({active_dir.name}); nothing to unarchive",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
```

Also handle `AmbiguousSlugError` in the active-dir lookup the same way as `SlugNotFoundError` (treat ambiguous-among-active the same as "no archived match" — the user clearly typed something only sensible against the active set):

```python
    except SlugNotFoundError:
        from jobhound.domain.slug import AmbiguousSlugError, resolve_slug

        try:
            active_dir = resolve_slug(slug_query, paths.opportunities_dir)
        except (SlugNotFoundError, AmbiguousSlugError):
            print(
                f"jh: no archived opportunity matches {slug_query!r}",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
        print(
            f"jh: {slug_query!r} matches an active opportunity "
            f"({active_dir.name}); nothing to unarchive",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
```

- [ ] **Step 4: Run all `unarchive` tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_cmd_unarchive.py -v`

Expected: All four tests PASS (including `test_unarchive_missing_slug_errors` from Task 3, which still hits the no-match branch).

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/commands/unarchive.py tests/test_cmd_unarchive.py
git commit -m "$(cat <<'EOF'
feat(cli): point users at the active slug when unarchive misses

When `jh unarchive <slug>` finds no archived match, fall back to a
lookup in the active set and produce a tailored error if the slug
exists there. Helps users notice the slug is already active.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `jh list` filters + asterisk marker

**Goal:** Replace the `repo.all()` path with `OpportunityQuery.list(Filters(...))`. Add `--all`, `--archived`, `--status` flags. Append a trailing `*` to archived rows when both sets are shown.

Default behavior — `jh list` with no flags — is unchanged (active opportunities only).

**Files:**
- Modify: `src/jobhound/commands/list_.py` (full rewrite of `run`)
- Modify: `tests/test_cmd_list.py` (existing test stays; add filter tests)

### Steps

- [ ] **Step 1: Write the failing tests**

Replace the contents of `tests/test_cmd_list.py` with:

```python
"""Tests for `jh list`."""


def _seed_active(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    invoke(["new", "--company", "Bar", "--role", "IC", "--now", "2026-05-02T12:00:00Z"])


def _seed_active_plus_archived(invoke) -> None:
    _seed_active(invoke)
    invoke(["new", "--company", "Gone", "--role", "Staff", "--now", "2026-05-03T12:00:00Z"])
    invoke(["archive", "gone"])


def test_list_default_shows_active_only(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["list"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output
    assert "2026-05-gone-staff" not in result.output


def test_list_one_line_per_opportunity(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    result = invoke(["list"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output
    assert "prospect" in result.output


def test_list_all_includes_archived_with_asterisk(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["list", "--all"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-gone-staff" in result.output
    # archived row ends with a trailing asterisk
    for line in result.output.splitlines():
        if "2026-05-gone-staff" in line:
            assert line.rstrip().endswith("*")
        elif line.strip() and not line.startswith(" "):
            assert not line.rstrip().endswith("*")


def test_list_archived_shows_only_archived(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["list", "--archived"])
    assert result.exit_code == 0, result.output
    assert "2026-05-gone-staff" in result.output
    assert "2026-05-foo-em" not in result.output
    assert "2026-05-bar-ic" not in result.output


def test_list_all_and_archived_are_mutually_exclusive(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    result = invoke(["list", "--all", "--archived"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_list_status_filter_single(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    invoke(["set", "status", "foo", "applied"])
    result = invoke(["list", "--status", "applied"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" not in result.output


def test_list_status_filter_repeated(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    invoke(["set", "status", "foo", "applied"])
    result = invoke(["list", "--status", "applied", "--status", "prospect"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output


def test_list_status_filter_comma_separated(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    invoke(["set", "status", "foo", "applied"])
    result = invoke(["list", "--status", "applied,prospect"])
    assert result.exit_code == 0, result.output
    assert "2026-05-foo-em" in result.output
    assert "2026-05-bar-ic" in result.output


def test_list_status_filter_unknown_value_errors(tmp_jh, invoke) -> None:
    _seed_active(invoke)
    result = invoke(["list", "--status", "made-up"])
    assert result.exit_code != 0
    assert "unknown status" in result.output


def test_list_all_status_filter_composes(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    # "gone" was archived as prospect. Filter by prospect across both sets.
    result = invoke(["list", "--all", "--status", "prospect"])
    assert result.exit_code == 0, result.output
    assert "2026-05-gone-staff" in result.output
    assert "2026-05-foo-em" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_cmd_list.py -v`

Expected: The `default_shows_active_only` test now should pass (today's `repo.all()` already only sees active). Most others FAIL — flags don't exist.

- [ ] **Step 3: Rewrite `commands/list_.py`**

Replace the contents of `src/jobhound/commands/list_.py` with:

```python
"""`jh list` — one-line summary of opportunities, optionally filtered."""

from __future__ import annotations

import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.domain.status import Status
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    *,
    all_: Annotated[bool, Parameter(name=["--all"])] = False,
    archived: Annotated[bool, Parameter(name=["--archived"])] = False,
    status: Annotated[list[str] | None, Parameter(name=["--status"])] = None,
) -> None:
    """List opportunities."""
    if all_ and archived:
        print("jh: --all and --archived are mutually exclusive", file=sys.stderr)
        raise SystemExit(2)

    statuses = _parse_statuses(status)

    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)
    filters = Filters(statuses=statuses, include_archived=(all_ or archived))
    snaps = query.list(filters, now=now_utc())
    if archived:
        snaps = [s for s in snaps if s.archived]

    for snap in snaps:
        opp = snap.opportunity
        mark = " *" if snap.archived else ""
        print(f"{opp.slug:<55} {opp.status:<12} {opp.priority:<8}{mark}".rstrip())


def _parse_statuses(raw: list[str] | None) -> frozenset[Status]:
    """Accept repeated `--status` and comma-separated values."""
    if not raw:
        return frozenset()
    tokens = [t.strip() for chunk in raw for t in chunk.split(",") if t.strip()]
    try:
        return frozenset(Status(t) for t in tokens)
    except ValueError as exc:
        print(f"jh: unknown status: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_cmd_list.py -v`

Expected: All ten tests PASS.

- [ ] **Step 5: Sanity-check the full suite**

Run: `uv run --no-sync pytest -q`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/commands/list_.py tests/test_cmd_list.py
git commit -m "$(cat <<'EOF'
feat(cli): add list filters and archived-row marker

`jh list` accepts `--all`, `--archived` (mutually exclusive), and
`--status` (repeatable, accepts comma-separated values). Default
behavior is unchanged. Archived rows in mixed output end with a
trailing `*`.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `jh stats` filters

**Goal:** Same `--all` / `--archived` / `--status` flags on `jh stats`. `Filters` already supported by `OpportunityQuery.stats()`; the CLI command just needs the flags and the same parsing.

**Files:**
- Modify: `src/jobhound/commands/stats.py` (add filters)
- Modify: `tests/test_cmd_stats.py` (add filter tests)

### Steps

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cmd_stats.py`:

```python
def _seed_active_plus_archived(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    invoke(["new", "--company", "Gone", "--role", "Staff", "--now", "2026-05-02T12:00:00Z"])
    invoke(["archive", "gone"])


def test_stats_default_excludes_archived(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # both seeded as prospect; default = active only -> exactly 1 prospect
    assert payload["funnel"]["prospect"] == 1


def test_stats_all_includes_archived(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--all", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["funnel"]["prospect"] == 2


def test_stats_archived_only(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--archived", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["funnel"]["prospect"] == 1


def test_stats_status_filter(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    invoke(["set", "status", "foo", "applied"])
    result = invoke(["stats", "--status", "applied", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["funnel"]["applied"] == 1
    assert payload["funnel"]["prospect"] == 0


def test_stats_all_and_archived_are_mutually_exclusive(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--all", "--archived"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_stats_unknown_status_errors(tmp_jh, invoke) -> None:
    _seed_active_plus_archived(invoke)
    result = invoke(["stats", "--status", "made-up"])
    assert result.exit_code != 0
    assert "unknown status" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_cmd_stats.py -v`

Expected: The new tests FAIL (flags don't exist; today's `query.stats()` is called with no filters).

- [ ] **Step 3: Rewrite `commands/stats.py`**

Replace `src/jobhound/commands/stats.py` with:

```python
"""`jh stats` — show aggregate funnel and source counts."""

from __future__ import annotations

import json
import sys
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import Filters, OpportunityQuery
from jobhound.application.serialization import stats_to_dict
from jobhound.application.snapshots import Stats
from jobhound.domain.status import Status
from jobhound.domain.timekeeping import now_utc
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    *,
    json_out: Annotated[bool, Parameter(name=["--json"])] = False,
    all_: Annotated[bool, Parameter(name=["--all"])] = False,
    archived: Annotated[bool, Parameter(name=["--archived"])] = False,
    status: Annotated[list[str] | None, Parameter(name=["--status"])] = None,
) -> None:
    """Show pipeline stats."""
    if all_ and archived:
        print("jh: --all and --archived are mutually exclusive", file=sys.stderr)
        raise SystemExit(2)

    statuses = _parse_statuses(status)

    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)

    if archived:
        # Active+archived then drop active rows. Filters has no archived-only mode;
        # this keeps the read API unchanged.
        snaps = [
            s
            for s in query.list(
                Filters(statuses=statuses, include_archived=True),
                now=now_utc(),
            )
            if s.archived
        ]
        stats = _aggregate(snaps)
    else:
        stats = query.stats(
            Filters(statuses=statuses, include_archived=all_),
        )

    if json_out:
        print(json.dumps(stats_to_dict(stats), indent=2))
    else:
        _print_human(stats_to_dict(stats))


def _parse_statuses(raw: list[str] | None) -> frozenset[Status]:
    """Accept repeated `--status` and comma-separated values."""
    if not raw:
        return frozenset()
    tokens = [t.strip() for chunk in raw for t in chunk.split(",") if t.strip()]
    try:
        return frozenset(Status(t) for t in tokens)
    except ValueError as exc:
        print(f"jh: unknown status: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


def _aggregate(snaps: list) -> Stats:
    """Build a Stats aggregate from a snapshot list (used for --archived only)."""
    funnel: dict[Status, int] = dict.fromkeys(Status, 0)
    sources: dict[str, int] = {}
    for snap in snaps:
        funnel[snap.opportunity.status] += 1
        key = snap.opportunity.source or "(unspecified)"
        sources[key] = sources.get(key, 0) + 1
    return Stats(funnel=funnel, sources=sources)


def _print_human(data: dict) -> None:
    print("Funnel:")
    for status, count in data.get("funnel", {}).items():
        if count:
            print(f"  {status:<20s} {count}")
    sources = data.get("sources", {})
    if sources:
        print()
        print("Sources:")
        for source, count in sorted(sources.items()):
            print(f"  {source:<20s} {count}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_cmd_stats.py -v`

Expected: All tests PASS, including the existing `test_stats_prints_funnel`, `test_stats_json_flag`, and `test_stats_empty_db_succeeds`.

- [ ] **Step 5: Run the full suite**

Run: `uv run --no-sync pytest -q`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/jobhound/commands/stats.py tests/test_cmd_stats.py
git commit -m "$(cat <<'EOF'
feat(cli): add stats filters mirroring list

`jh stats` accepts the same `--all`, `--archived`, and `--status`
flags as `jh list`. Default behavior is unchanged. Composes with
the existing `--json` flag.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: MCP `unarchive_opportunity` tool

**Goal:** Add a `unarchive_opportunity(slug)` MCP tool mirroring `archive_opportunity`. Returns a mutation envelope; the snapshot's `archived` flag is `False`.

**Files:**
- Modify: `src/jobhound/mcp/tools/ops.py`
- Modify: `tests/mcp/test_tools_ops.py`

### Steps

- [ ] **Step 1: Write the failing test**

Append to `tests/mcp/test_tools_ops.py`:

```python
from jobhound.mcp.tools.ops import unarchive_opportunity  # noqa: E402


def test_unarchive_round_trips_archive(
    repo: OpportunityRepository,
    mcp_paths: Paths,
) -> None:
    archive_payload = json.loads(archive_opportunity(repo, slug="acme"))
    assert archive_payload["opportunity"]["archived"] is True

    unarchive_payload = json.loads(unarchive_opportunity(repo, slug="acme"))
    assert unarchive_payload["opportunity"]["archived"] is False
    assert (mcp_paths.opportunities_dir / "2026-05-acme-em").exists()
    assert not (mcp_paths.archive_dir / "2026-05-acme-em").exists()
```

Move the new import alongside the existing `from jobhound.mcp.tools.ops import (...)` block at the top of the file instead of inline — make the import block:

```python
from jobhound.mcp.tools.ops import (
    add_note,
    archive_opportunity,
    delete_opportunity,
    unarchive_opportunity,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --no-sync pytest tests/mcp/test_tools_ops.py::test_unarchive_round_trips_archive -v`

Expected: FAIL — `ImportError: cannot import name 'unarchive_opportunity' from 'jobhound.mcp.tools.ops'`.

- [ ] **Step 3: Add the function and tool registration**

In `src/jobhound/mcp/tools/ops.py`, immediately after the existing `archive_opportunity` function (around line 53), add:

```python
def unarchive_opportunity(repo: OpportunityRepository, *, slug: str) -> str:
    try:
        before, after, new_dir = ops_service.unarchive_opportunity(repo, slug)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="unarchive_opportunity"))
    return json.dumps(
        mutation_response(
            before,
            after,
            new_dir,
            now=now_utc(),
            archived=False,
        )
    )
```

In the `register` function, immediately after the `archive_opportunity` registration block (the `@app.tool(name="archive_opportunity", ...)` followed by `def _a(...)`), add:

```python
    @app.tool(
        name="unarchive_opportunity",
        description="Restore an archived opportunity.",
    )
    def _u(slug: str) -> str:
        return unarchive_opportunity(repo, slug=slug)
```

- [ ] **Step 4: Run MCP tests to verify they pass**

Run: `uv run --no-sync pytest tests/mcp/ -v`

Expected: All MCP tests PASS, including the new round-trip test.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/mcp/tools/ops.py tests/mcp/test_tools_ops.py
git commit -m "$(cat <<'EOF'
feat(mcp): add unarchive_opportunity tool

Mirrors archive_opportunity. Returns the standard mutation envelope
with archived=False on the resulting snapshot.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Clean directory names out of public-facing module docstrings

**Goal:** Module-level docstrings on the public command files mention `opportunities/` / `archive/`, leaking storage layout. Replace with state-language equivalents. Only touches the headers; internal repository docstrings keep naming the directories (that is their domain).

**Files:**
- Modify: `src/jobhound/commands/archive.py` (one-line module docstring)
- Modify: `src/jobhound/commands/list_.py` already rewritten in Task 5 — verify the module docstring is leak-free (it is: "one-line summary of opportunities, optionally filtered").

### Steps

- [ ] **Step 1: Edit `commands/archive.py`'s module docstring**

In `src/jobhound/commands/archive.py`, replace line 1:

```python
"""`jh archive` — move <slug> from opportunities/ to archive/."""
```

with:

```python
"""`jh archive` — move an opportunity to the archived state."""
```

- [ ] **Step 2: Run the full suite to make sure nothing breaks**

Run: `uv run --no-sync pytest -q`

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/jobhound/commands/archive.py
git commit -m "$(cat <<'EOF'
docs(commands): describe archive in state terms, not storage

Module-level docstring no longer names the on-disk directory layout.
Keeps the public surface free of backend leakage, matching the
unarchive command added in this branch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

After Task 8, run the whole suite and a lint pass once more before opening a PR:

- [ ] `uv run --no-sync pytest -q` — all green
- [ ] `uv run --no-sync ruff check src tests` — no warnings
- [ ] `uv run --no-sync ruff format --check src tests` — no diffs
- [ ] `uv run --no-sync ty check src` — no errors
- [ ] `git log --oneline main..HEAD` — 8 commits, one per task

If any pre-commit hook fails during a per-task commit, fix the underlying issue in the working tree and create a NEW commit (never `--amend`, never `--no-verify`). Then re-run the per-task verification.

Open the PR with:

```bash
gh pr create --title "feat: add jh unarchive and list/stats filters" --body "$(cat <<'EOF'
## Summary
- New `jh unarchive <slug>` command (CLI + MCP) restores an archived opportunity.
- `jh list` and `jh stats` accept `--all` / `--archived` / `--status` filters; defaults unchanged.
- Archived rows in `jh list --all` end with a trailing `*`.

Spec: `docs/specs/2026-06-05-unarchive-and-list-filters-design.md`
Plan: `docs/plans/2026-06-05-unarchive-and-list-filters.md`

## Test plan
- [ ] `uv run --no-sync pytest -q` green locally
- [ ] `jh archive foo && jh unarchive foo` round-trips
- [ ] `jh list`, `jh list --all`, `jh list --archived`, `jh list --status applied,screen` behave as specified
- [ ] `jh stats` mirrors `jh list` filtering
- [ ] Tab completion: `jh unarchive <TAB>` lists archived slugs only

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
