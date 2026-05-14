# Phase 4 Cleanup — CLI commands → application services

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended for this size of refactor) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `src/jobhound/commands/*.py` to call the new `application/*_service.py` functions instead of inlining the load-mutate-save pattern. CLI tests must remain green throughout — the existing user-visible behavior is the contract.

**Architecture:** Two parts. **(a) Align services to the CLI's existing contract** where they diverge today (notes format + `last_activity` bump, log commit message arrow, contact's extra fields). The Phase 4 spec assumed the services were a clean drop-in; in practice three of them diverge from the existing CLI semantics. Fix the services first, with their tests, so the CLI refactor is mechanical. **(b) Refactor each CLI command** to delegate orchestration to its service while keeping CLI-specific concerns (output text, exit codes, $EDITOR loop, `--yes` prompt, file-side-effects like correspondence/notes writes that don't belong in services) inline.

**Tech Stack:** Python 3.12, existing toolchain. No new deps.

**Spec:** `docs/specs/2026-05-14-phase4-mcp-design.md` §"CLI commands are NOT refactored in Phase 4" — this is the deferred follow-on.

**Branch:** `chore/phase4-cleanup-cli-services` (already created off post-v0.5.0 main).

---

## File Structure

### Application services (modified)

- `src/jobhound/application/ops_service.py` — `add_note` aligned to CLI: accepts `today: date`; writes `- YYYY-MM-DD msg` format; bumps `last_activity` via `Opportunity.touch`.
- `src/jobhound/application/lifecycle_service.py` — `log_interaction` commit message changes from `f"log: {slug} -> {status}"` to CLI's arrow format `f"log: {slug} {arrow}"` where arrow is `"prev → new"` or `"(no status change)"`.
- `src/jobhound/application/relation_service.py` — `add_contact` accepts `company` and `note` kwargs and threads them into `Contact(...)`.

### MCP tool adapters (modified to match new service signatures)

- `src/jobhound/mcp/tools/ops.py` — `add_note` accepts optional `today: str | None` ISO arg.
- `src/jobhound/mcp/tools/relations.py` — `add_contact` accepts optional `company` and `note` kwargs.

### CLI commands (refactored, 11 files)

- `commands/new.py` → `lifecycle_service.create`
- `commands/apply.py` → `lifecycle_service.apply_to`
- `commands/log.py` → `lifecycle_service.log_interaction` (correspondence-file write stays CLI-side; service's `repo.save` picks it up via `git add .`)
- `commands/_terminal.py` → dispatches to `lifecycle_service.{withdraw_from, mark_ghosted, accept_offer, decline_offer}` (one of four by verb)
- `commands/priority.py` → `field_service.set_priority`
- `commands/tag.py` → `relation_service.add_tag` / `.remove_tag` (looped over add/remove sets, then one final save — see Task 11 for the wrinkle)
- `commands/contact.py` → `relation_service.add_contact`
- `commands/link.py` → `relation_service.set_link`
- `commands/note.py` → `ops_service.add_note` (CLI side just parses args + prints result)
- `commands/archive.py` → `ops_service.archive_opportunity`
- `commands/delete.py` → `ops_service.delete_opportunity` (CLI runs its `questionary.confirm` prompt first; passes `confirm=True` to the service only if user agrees)

### Commands NOT refactored (with reasons)

- `commands/edit.py` — interactive `$EDITOR` workflow with validation retry loop. Doesn't fit the load-mutate-save service shape (it's load → edit-externally → validate → save with retry). Stays as-is.
- `commands/sync.py` — CLI-specific preflight (checks for a configured remote and prints a helpful "no remote configured" error) + captures stderr from `git push` for display. The service raises `CalledProcessError` and would lose this UX. Stays as-is.

### Tests

- `tests/application/test_ops_service.py` — update `test_add_note_appends_timestamped_entry` for the new format; add `test_add_note_bumps_last_activity`.
- `tests/application/test_lifecycle_service.py` — add `test_log_interaction_commit_message_format` (snapshots the message via git log).
- `tests/application/test_relation_service.py` — add `test_add_contact_with_company_and_note`.
- `tests/mcp/test_tools_ops.py` — verify `add_note` still works with the new optional `today` arg.
- `tests/mcp/test_tools_relations.py` — verify `add_contact` accepts the new optional kwargs.
- `tests/test_cmd_*.py` — UNCHANGED. The existing 142 CLI tests are the contract; if they break, the refactor is wrong.

---

## Task 1: Align `ops_service.add_note` with CLI

**Goal:** Match `commands/note.py`'s existing behavior exactly: writes `- YYYY-MM-DD msg\n` to `notes.md` (not the `## TIMESTAMP\n\nmsg\n` block format the service currently uses), bumps `last_activity` via `Opportunity.touch(today=...)`. Service gets a new `today: date` keyword arg.

**Files:**
- Modify: `src/jobhound/application/ops_service.py:30-50` (the `add_note` function body)
- Modify: `tests/application/test_ops_service.py` — update `test_add_note_appends_timestamped_entry`; add new test for last_activity bump.

- [ ] **Step 1: Update the test** in `tests/application/test_ops_service.py`. Replace `test_add_note_appends_timestamped_entry` with:

```python
def test_add_note_appends_dated_entry(tmp_path: Path) -> None:
    repo, paths = _seeded(tmp_path)
    today = date(2026, 5, 14)
    ops_service.add_note(repo, "acme", msg="recruiter mentioned hybrid", today=today)
    notes = (paths.opportunities_dir / "2026-05-acme" / "notes.md").read_text()
    assert "- 2026-05-14 recruiter mentioned hybrid" in notes


def test_add_note_bumps_last_activity(tmp_path: Path) -> None:
    repo, _ = _seeded(tmp_path)
    today = date(2026, 5, 14)
    _, after, _ = ops_service.add_note(repo, "acme", msg="x", today=today)
    assert after.last_activity == today
```

Update `test_add_note_no_commit` to pass `today=date.today()`:

```python
def test_add_note_no_commit(tmp_path: Path) -> None:
    repo, _ = _seeded(tmp_path)
    head_before = subprocess.run(
        ["git", "-C", str(repo.paths.db_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    ops_service.add_note(repo, "acme", msg="quiet note", today=date.today(), no_commit=True)
    head_after = subprocess.run(
        ["git", "-C", str(repo.paths.db_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert head_before == head_after
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
uv run pytest tests/application/test_ops_service.py -v
```

Expected: 2 failures (the new tests + the modified one).

- [ ] **Step 3: Update `add_note` in `src/jobhound/application/ops_service.py`**:

```python
def add_note(
    repo: OpportunityRepository,
    slug: str,
    *,
    msg: str,
    today: date,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    """Append `- <today> <msg>\\n` to notes.md and bump last_activity.

    Returns (before, after, opp_dir). `before` is the loaded opp; `after`
    is the touched opp (last_activity updated). The CLI and MCP tool
    both share this contract — same notes.md format, same
    last_activity behavior.
    """
    before, opp_dir = repo.find(slug)
    notes_path = opp_dir / "notes.md"
    existing = notes_path.read_text() if notes_path.exists() else ""
    notes_path.write_text(existing + f"- {today.isoformat()} {msg}\n")
    after = before.touch(today=today)
    repo.save(after, opp_dir, message=f"note: {after.slug}", no_commit=no_commit)
    return before, after, opp_dir
```

Add `from datetime import date` near the top if not already imported.

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
uv run pytest tests/application/test_ops_service.py -v
```

Expected: 7 tests pass (4 unchanged + 2 new + 1 updated).

- [ ] **Step 5: Update the MCP tool** `src/jobhound/mcp/tools/ops.py:add_note` to accept the new `today` kwarg and pass it through. The function signature becomes:

```python
def add_note(
    repo: OpportunityRepository, *, slug: str, msg: str, today: str | None = None,
) -> str:
    today_d = date.fromisoformat(today) if today else date.today()
    try:
        before, after, opp_dir = ops_service.add_note(repo, slug, msg=msg, today=today_d)
    except Exception as exc:
        return json.dumps(exception_to_response(exc, tool="add_note"))
    return json.dumps(mutation_response(before, after, opp_dir, today=today_d))
```

Update the `@app.tool` registration handler in the same file:

```python
@app.tool(...)
def _n(slug: str, msg: str, today: str | None = None) -> str:
    return add_note(repo, slug=slug, msg=msg, today=today)
```

- [ ] **Step 6: Run MCP test for add_note**

```bash
uv run pytest tests/mcp/test_tools_ops.py::test_add_note -v
```

Expected: passes (the existing test doesn't pass `today`, defaults to `date.today()`).

- [ ] **Step 7: Full suite + lint + commit**

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/ops_service.py src/jobhound/mcp/tools/ops.py tests/application/test_ops_service.py
git commit -m "refactor(application): align add_note with CLI (notes format + last_activity)"
```

Expected: 303 → 304 tests passing (one net-new test from this task).

---

## Task 2: Align `lifecycle_service.log_interaction` commit message

**Goal:** Match `commands/log.py`'s commit message: `f"log: {slug} {arrow}"` where arrow is `"prev → new"` for status changes or `"(no status change)"` for stays. The service currently writes `f"log: {slug} -> {new}"` which loses the "stay" affordance and uses ASCII `->`.

**Files:**
- Modify: `src/jobhound/application/lifecycle_service.py` (the `log_interaction` function's `repo.save` call)
- Modify: `tests/application/test_lifecycle_service.py` (add a commit-message-format test)

- [ ] **Step 1: Add the failing test** in `tests/application/test_lifecycle_service.py`:

```python
def test_log_interaction_commit_message_format(tmp_path: Path) -> None:
    """Commit message must match the CLI's existing format."""
    repo, paths = _repo(tmp_path)
    _seed_prospect(repo)
    lifecycle_service.apply_to(
        repo, "acme",
        applied_on=date(2026, 5, 10),
        today=TODAY,
        next_action="x",
        next_action_due=date(2026, 5, 20),
    )
    # Advance status: APPLIED -> SCREEN
    lifecycle_service.log_interaction(
        repo, "acme", next_status="screen",
        next_action=None, next_action_due=None, today=TODAY, force=False,
    )
    msg = subprocess.run(
        ["git", "-C", str(paths.db_root), "log", "-1", "--format=%s"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert msg == "log: 2026-05-acme applied → screen"

    # Stay
    lifecycle_service.log_interaction(
        repo, "acme", next_status="stay",
        next_action=None, next_action_due=None, today=TODAY, force=False,
    )
    msg = subprocess.run(
        ["git", "-C", str(paths.db_root), "log", "-1", "--format=%s"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert msg == "log: 2026-05-acme (no status change)"
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/application/test_lifecycle_service.py::test_log_interaction_commit_message_format -v
```

Expected: assertion failure showing current `"log: 2026-05-acme -> screen"`.

- [ ] **Step 3: Update `log_interaction` in `src/jobhound/application/lifecycle_service.py`**:

```python
def log_interaction(
    repo: OpportunityRepository,
    slug: str,
    *,
    next_status: str,
    next_action: str | None,
    next_action_due: date | None,
    today: date,
    force: bool,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    """Record an interaction. `next_status='stay'` keeps the current status."""
    before, opp_dir = repo.find(slug)
    after = before.log_interaction(
        today=today,
        next_status=next_status,
        next_action=next_action,
        next_action_due=next_action_due,
        force=force,
    )
    arrow = (
        f"{before.status} → {after.status}"
        if after.status != before.status
        else "(no status change)"
    )
    repo.save(
        after, opp_dir,
        message=f"log: {after.slug} {arrow}",
        no_commit=no_commit,
    )
    return before, after, opp_dir
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/application/test_lifecycle_service.py -v
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/lifecycle_service.py tests/application/test_lifecycle_service.py
git commit -m "refactor(application): match CLI's arrow format in log commit message"
```

Expected: 304 → 305 tests passing.

---

## Task 3: Align `relation_service.add_contact` with CLI's contact fields

**Goal:** `commands/contact.py` accepts `company` and `note` parameters in addition to `name`/`role`/`channel`, and threads them into the `Contact` dataclass (which already has these fields). The service currently doesn't expose them.

**Files:**
- Modify: `src/jobhound/application/relation_service.py` (`add_contact` signature)
- Modify: `tests/application/test_relation_service.py` (add coverage for new kwargs)
- Modify: `src/jobhound/mcp/tools/relations.py` (`add_contact` MCP tool)

- [ ] **Step 1: Add the failing test** in `tests/application/test_relation_service.py`:

```python
def test_add_contact_with_company_and_note(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path)
    _, after, _ = relation_service.add_contact(
        repo, "acme",
        name="Jane Doe",
        role="Recruiter",
        channel="email",
        company="Acme HR",
        note="warm intro from referral",
    )
    c = after.contacts[0]
    assert c.name == "Jane Doe"
    assert c.company == "Acme HR"
    assert c.note == "warm intro from referral"
```

- [ ] **Step 2: Run, confirm failure**

```bash
uv run pytest tests/application/test_relation_service.py::test_add_contact_with_company_and_note -v
```

Expected: TypeError or missing-attribute error.

- [ ] **Step 3: Update `add_contact` in `src/jobhound/application/relation_service.py`**:

```python
def add_contact(
    repo: OpportunityRepository,
    slug: str,
    *,
    name: str,
    role: str | None,
    channel: str | None,
    company: str | None = None,
    note: str | None = None,
    no_commit: bool = False,
) -> tuple[Opportunity, Opportunity, Path]:
    before, opp_dir = repo.find(slug)
    after = before.with_contact(Contact(
        name=name, role=role, channel=channel,
        company=company, note=note,
    ))
    repo.save(after, opp_dir, message=f"contact: {after.slug} {name}", no_commit=no_commit)
    return before, after, opp_dir
```

- [ ] **Step 4: Update the MCP `add_contact` tool** in `src/jobhound/mcp/tools/relations.py` to accept and forward the new kwargs:

```python
def add_contact(
    repo: OpportunityRepository,
    *,
    slug: str,
    name: str,
    role: str | None = None,
    channel: str | None = None,
    company: str | None = None,
    note: str | None = None,
) -> str:
    return _wrap(
        "add_contact",
        lambda: relation_service.add_contact(
            repo, slug, name=name, role=role, channel=channel,
            company=company, note=note,
        ),
    )
```

Update the `@app.tool` registration handler to accept the new params.

- [ ] **Step 5: Run + commit**

```bash
uv run pytest tests/application/test_relation_service.py tests/mcp/test_tools_relations.py -v
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run ty check
git add src/jobhound/application/relation_service.py src/jobhound/mcp/tools/relations.py tests/application/test_relation_service.py
git commit -m "refactor(application): expose company and note on add_contact"
```

Expected: 305 → 306 tests passing.

---

## Tasks 4–14: Refactor CLI commands (one per file)

Each task follows the same shape. Doing them as separate commits gives clean git-bisect-ability if a CLI test breaks unexpectedly.

**Per-task template:**

1. Open `src/jobhound/commands/<X>.py`. Identify the load-mutate-save block (typically `repo.find` → domain method → `repo.save`).
2. Replace the block with the matching `application/*_service.<verb>(repo, ...)` call.
3. Keep CLI-specific behavior inline: argument parsing, output `print()` lines, exit codes, error messages, file side effects that don't belong in the service (correspondence files for `log.py`).
4. Remove imports that are no longer needed (e.g., `from jobhound.domain.transitions import InvalidTransitionError` if the CLI no longer catches it directly — but in most cases the CLI still wants to catch and print friendly errors).
5. Run the matching CLI test file: `uv run pytest tests/test_cmd_<X>.py -v`.
6. Run the full suite: `uv run pytest -q`.
7. Lint check: `uv run ruff check . && uv run ruff format --check . && uv run ty check`.
8. Commit: `git commit -m "refactor(commands): <X> delegates to <service>"`.

### Task 4: `commands/new.py` → `lifecycle_service.create`

**Files:** `src/jobhound/commands/new.py`, test: `tests/test_cmd_new.py`.

- [ ] Replace the inlined `repo.create(opp, message=..., no_commit=...)` with `lifecycle_service.create(repo, opp, no_commit=no_commit)`. The service returns `(None, opp, opp_dir)` — destructure to get `opp_dir` for the print line.
- [ ] Keep the `FileExistsError` catch at the CLI level (service propagates it).
- [ ] Run `uv run pytest tests/test_cmd_new.py -v`, full suite, lint, commit.

### Task 5: `commands/apply.py` → `lifecycle_service.apply_to`

**Files:** `src/jobhound/commands/apply.py`, test: `tests/test_cmd_apply.py`.

- [ ] Replace inlined `repo.find` + `opp.apply(...)` + `repo.save(...)` block with:
  ```python
  try:
      opp, _, _ = lifecycle_service.apply_to(
          repo, slug_query,
          applied_on=applied_on,
          today=today_date,
          next_action=next_action,
          next_action_due=due,
          no_commit=no_commit,
      )
  except InvalidTransitionError as exc:
      print(str(exc), file=sys.stderr)
      raise SystemExit(1) from exc
  print(f"applied: {opp.slug}")
  ```
- [ ] Drop the now-unused imports (`from jobhound.infrastructure.repository import OpportunityRepository`, `from jobhound.infrastructure.paths import paths_from_config`, `from jobhound.infrastructure.config import load_config` — wait, those ARE still needed for building `repo`. Keep them. Drop unused ones only.)
- [ ] Run `uv run pytest tests/test_cmd_apply.py -v`, full suite, lint, commit.

### Task 6: `commands/log.py` → `lifecycle_service.log_interaction`

**Files:** `src/jobhound/commands/log.py`, test: `tests/test_cmd_log.py`.

Wrinkle: `log.py` writes a correspondence file (`<slug>/correspondence/<date>-<channel>-<direction>-<who>.md`) in addition to the meta update. The service's `repo.save` does `git add .` which picks up the correspondence write automatically. So:

- [ ] Move correspondence-file write to BEFORE the service call (the service's save commits both).
- [ ] Replace the inlined `repo.find` + `opp.log_interaction(...)` + `repo.save(...)` block with `lifecycle_service.log_interaction(...)`. Capture `(before, after, _)`.
- [ ] Keep the arrow computation for the CLI's `print(f"logged: {opp.slug} {arrow}")` line (the service now computes the same arrow for the commit message; either re-compute in the CLI or extract a helper — re-compute is simpler).
- [ ] Run `uv run pytest tests/test_cmd_log.py -v`, full suite, lint, commit.

### Task 7: `commands/_terminal.py` → `lifecycle_service.{withdraw_from, mark_ghosted, accept_offer, decline_offer}`

**Files:** `src/jobhound/commands/_terminal.py`, tests: `tests/test_cmd_terminal.py` and the four wrapper tests (`test_cmd_simple.py` likely covers these).

- [ ] Replace the `_METHODS` dict-of-domain-methods with a `_SERVICES` dict mapping verb → service function:
  ```python
  _SERVICES = {
      "withdraw": lifecycle_service.withdraw_from,
      "ghost": lifecycle_service.mark_ghosted,
      "accept": lifecycle_service.accept_offer,
      "decline": lifecycle_service.decline_offer,
  }
  ```
- [ ] Update `run_transition` to call `_SERVICES[verb](repo, slug_query, today=today_date, no_commit=no_commit)`. Catch `InvalidTransitionError`, keep the same stderr + exit-1 behavior.
- [ ] Output line stays `print(f"{verb}: {opp.slug}")`. Capture `opp` from the service's return tuple.
- [ ] Run `uv run pytest tests/test_cmd_terminal.py tests/test_cmd_simple.py -v`, full suite, lint, commit.

### Task 8: `commands/priority.py` → `field_service.set_priority`

**Files:** `src/jobhound/commands/priority.py`, test: existing CLI test (search for `test_*priority*`).

- [ ] Replace the inlined `repo.find` + `opp.with_priority(...)` + `repo.save(...)` block with `field_service.set_priority(repo, slug_query, priority, no_commit=no_commit)`.
- [ ] Keep the `Priority(to)` parse + the friendly error message for invalid values at the CLI level.
- [ ] Output line `print(f"priority {opp.slug}: {priority.value}")` — pull `opp` from the service's return tuple.
- [ ] Run the relevant CLI test file, full suite, lint, commit.

### Task 9: `commands/tag.py` → `relation_service.{add_tag, remove_tag}`

**Wrinkle:** `commands/tag.py` accepts `--add` AND `--remove` flags in a single invocation and applies both in one mutation. The services have separate `add_tag(tag)` and `remove_tag(tag)` functions that each take one tag. Calling them in a loop would produce N commits, not one.

Two options:
- **(a)** Leave `tag.py` as-is — it doesn't fit the per-operation service shape. Justify in the plan that batched add+remove is CLI-specific.
- **(b)** Add a new service function `set_tags(repo, slug, *, add: set[str], remove: set[str], no_commit=False)` that does the batched operation in one save. Update `tag.py` to call it. The existing `add_tag`/`remove_tag` services stay (used by the MCP per-tag tools).

**Decision: (b).** The batched form is a real use case (CLI users) and adding the service function is small. The MCP `add_tag`/`remove_tag` keep their per-tag form because that's the AI's expected API.

**Files:** `src/jobhound/application/relation_service.py`, `tests/application/test_relation_service.py`, `src/jobhound/commands/tag.py`, existing tag CLI test.

- [ ] Add `set_tags(repo, slug, *, add, remove, no_commit=False)` to `relation_service.py`:
  ```python
  def set_tags(
      repo: OpportunityRepository,
      slug: str,
      *,
      add: set[str],
      remove: set[str],
      no_commit: bool = False,
  ) -> tuple[Opportunity, Opportunity, Path]:
      before, opp_dir = repo.find(slug)
      after = before.with_tags(add=add, remove=remove)
      summary = " ".join(
          [*(f"+{t}" for t in sorted(add)), *(f"-{t}" for t in sorted(remove))]
      )
      repo.save(after, opp_dir, message=f"tag: {after.slug} {summary}", no_commit=no_commit)
      return before, after, opp_dir
  ```
- [ ] Add a test for `set_tags` exercising both add and remove in one call.
- [ ] Refactor `tag.py` to call `set_tags`. Keep the CLI's "nothing to do" early-exit.
- [ ] Run the tag CLI test, full suite, lint, commit.

### Task 10: `commands/contact.py` → `relation_service.add_contact`

**Files:** `src/jobhound/commands/contact.py`, existing contact CLI test.

- [ ] Replace inlined block with `relation_service.add_contact(repo, slug_query, name=name, role=role_title, channel=channel, company=company, note=note, no_commit=no_commit)`.
- [ ] Keep CLI's print line `print(f"contact added: {opp.slug} {name}")`.
- [ ] Run CLI test, full suite, lint, commit.

### Task 11: `commands/link.py` → `relation_service.set_link`

**Files:** `src/jobhound/commands/link.py`, existing link CLI test.

- [ ] Replace inlined block with `relation_service.set_link(repo, slug_query, name=name, url=url, no_commit=no_commit)`.
- [ ] Keep CLI's print line.
- [ ] Run CLI test, full suite, lint, commit.

### Task 12: `commands/note.py` → `ops_service.add_note`

**Files:** `src/jobhound/commands/note.py`, test: `tests/test_cmd_note.py` (if exists; otherwise included in `test_cmd_simple.py`).

After Task 1, the service writes the exact same `- YYYY-MM-DD msg` format the CLI does. So:

- [ ] Replace the inlined `repo.find` + notes.md write + `opp.touch` + `repo.save` block with `ops_service.add_note(repo, slug_query, msg=msg, today=today_date, no_commit=no_commit)`.
- [ ] Keep the CLI's print line `print(f"noted: {opp.slug}")`.
- [ ] Run note CLI test, full suite, lint, commit.

### Task 13: `commands/archive.py` → `ops_service.archive_opportunity`

**Files:** `src/jobhound/commands/archive.py`, existing archive CLI test.

- [ ] Replace inlined `repo.find` + `repo.archive` block with `ops_service.archive_opportunity(repo, slug_query, no_commit=no_commit)`.
- [ ] Keep the `FileExistsError` catch at the CLI level.
- [ ] Keep CLI's print line.
- [ ] Run archive CLI test, full suite, lint, commit.

### Task 14: `commands/delete.py` → `ops_service.delete_opportunity`

**Wrinkle:** The CLI uses `questionary.confirm` interactively; the service has a `confirm: bool` flag. The right pattern: CLI does its prompt, then if the user agrees, calls `ops_service.delete_opportunity(repo, slug, confirm=True, no_commit=no_commit)`. The service's preview path (`confirm=False`) is for the MCP layer only — CLI never wants a preview.

**Files:** `src/jobhound/commands/delete.py`, existing delete CLI test.

- [ ] Run the `questionary.confirm` prompt as before (unless `--yes`).
- [ ] If confirmed, call `ops_service.delete_opportunity(repo, slug_query, confirm=True, no_commit=no_commit)`. Capture the `DeleteResult` if needed for output (the CLI prints just the slug name).
- [ ] Keep CLI's `aborted` + exit-1 path for user-said-no.
- [ ] Run delete CLI test, full suite, lint, commit.

---

## Task 15: Final sweep + PR-ready check

- [ ] Confirm the 142 original CLI tests are still green: `uv run pytest tests/test_cmd_*.py -q | tail -3`. Count should be exactly the same.
- [ ] Full suite: `uv run pytest -q`. Final count should be ≥306 (303 baseline + 3 net-new tests from Tasks 1-3).
- [ ] Lint: `uv run ruff check . && uv run ruff format --check . && uv run ty check`. Only the pre-existing `yaml` baseline diagnostic should remain.
- [ ] `git log --oneline main..HEAD` — should show ~14 commits, each a single conceptual change.
- [ ] Push branch + open PR.

---

## Spec → Task crosswalk

| Spec section | Task |
|---|---|
| Phase 4 spec §"CLI commands are NOT refactored in Phase 4" — explicit follow-on | All tasks 4–14 |
| Service-CLI alignment (notes format, log arrow, contact fields) | Tasks 1, 2, 3 |
| `edit.py` exception (interactive workflow) | Documented in §File Structure, not refactored |
| `sync.py` exception (CLI-specific preflight) | Documented in §File Structure, not refactored |
| Tag batched add+remove preserved via new `set_tags` service | Task 9 |

## Out of scope

- The minor polish items from PR #11's final review (`sync_data` direction validation, `_require_mcp_sdk` test coverage, helper consolidation across MCP tool modules, thicker relations test coverage). These remain a deferred cleanup pass.
- `edit.py` redesign. The interactive $EDITOR workflow is a separate UX question (the user has noted in passing that they don't love the "edit the toml file directly" approach; replacing it would be its own feature).
