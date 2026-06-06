# Short-flag Aliases — Implementation Plan

**Goal:** Add short-flag aliases to existing `Parameter(name=[...])` declarations across six command files.

**Approach:** Mechanical, additive. One commit per command file. Each commit extends `Parameter(name=["--foo"])` → `Parameter(name=["--foo", "-X"])` and adds one short-flag smoke test.

**Spec:** `docs/specs/2026-06-06-short-flags-design.md`

**Branch:** `feat/short-flags` (cut off `main` at `ac8ac97`).

## Verification per task

After each file edit:
1. Run the file's targeted test suite via `uv run --no-sync pytest tests/<test-file>.py -v`.
2. Run a `uv run --no-sync jh --help` (or `jh <subcommand> --help`) to confirm the short flag appears.

Pre-commit hook runs the full suite per commit, which is the integration verification.

## Tasks

### Task 1: `commands/show.py`

Add `-j` short alias to `--json`. Add smoke test in `tests/commands/test_cmd_show.py`.

### Task 2: `commands/list_.py`

Add `-a` to `--all`, `-A` to `--archived`, `-s` to `--status`. Add 3 smoke tests in `tests/test_cmd_list.py`.

### Task 3: `commands/stats.py`

Add `-a`, `-A`, `-s`, `-j` to `--all`, `--archived`, `--status`, `--json`. Add 4 smoke tests in `tests/test_cmd_stats.py`.

### Task 4: `commands/export.py`

Add `-s` to `--status`, `-p` to `--priority`. Add 2 smoke tests in `tests/commands/test_cmd_export.py`.

### Task 5: `commands/file.py`

Add `-o` to `--out` (read), `-n` to `--name` (write), `-c` to `--content` (write+append), `-f` to `--from` (write+append), `-y` to `--yes` (delete). Add smoke tests in `tests/test_cmd_file.py`.

### Task 6: `commands/completion.py`

Add `-d` to `--dest` (install). Add smoke test in `tests/commands/test_cmd_completion.py`.

### Final: PR

Push `feat/short-flags` and open a PR against `main`.

## Constraints

- Do not change any flag semantics. Long forms must still work — existing tests must stay green.
- Smoke tests use the short form and verify the same behavior as an existing long-form test (don't re-verify the underlying domain behavior).
- No new `Parameter` annotations on flags that don't already have them.
- One commit per task. Conventional-commits format: `feat(cli): add short flag -X for --long`.
