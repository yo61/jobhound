# Pickup notes — Phase 3a (post-restart)

Temporary checkpoint. Delete this file once Phase 3a is underway.

## Where we left off (2026-05-13)

- **Branch:** `feat/phase3-read-api-design` (off `main` at `65fc516`).
- **Last commit:** `01ee19b docs: spec phase 3a read API + DDD reorganisation`.
- **Spec:** `docs/specs/2026-05-12-jh-read-api-design.md` (687 lines).
- **Working tree:** clean.

Phase 3a is fully designed and the spec is committed. No implementation
code yet. Memory at `project_jh_cli.md` has the full strategic context.

## Steps to resume

### 1. Sanity-check git state

```bash
cd ~/code/github/yo61/jobhound
git branch --show-current        # should show feat/phase3-read-api-design
git status                       # should be clean
git log --oneline -3             # tip should be 01ee19b
```

### 2. Review the spec

Open `docs/specs/2026-05-12-jh-read-api-design.md` and read it end to end.
Decisions already captured: subpackage DDD layout, HTML dashboard ships by
default, PDF/web behind optional extras, sub-phase plan (3a/3b/3c/3d),
all filter flags, JSON envelope shape, error handling table.

If anything needs to change, tell Claude — the spec is a single commit
that can be amended or follow-up'd freely; nothing depends on it yet.

### 3. (Optional, can defer) Phase 3d prerequisite check

Verify the iCloud-hosted Job Hunting 2026-04 repo has no live writes
since the 2026-05-12 migration. Sandbox-blocked from doing this last
session; run it yourself when convenient:

```bash
cd "$HOME/Documents/Projects/Job Hunting 2026-04"
git log --since=2026-05-12 --oneline                        # expect empty
git status                                                   # expect clean
find opportunities archive _shared -newer Taskfile.yml -type f 2>/dev/null
diff -rq opportunities/ "$HOME/.local/share/jh/opportunities/" 2>&1 | head
```

Expected: no commits, clean status, no recent files, diff shows only the
YAML↔TOML format difference (`meta.yaml` vs `meta.toml`).

This is a Phase 3d prerequisite, not a 3a blocker. Skip if you want to
get straight into 3a implementation planning.

### 4. Tell Claude to draft the implementation plan

In a fresh Claude session, from this repo directory:

> Pick up Phase 3a from where we left off. Read `PICKUP.md`, then the
> spec at `docs/specs/2026-05-12-jh-read-api-design.md`, then invoke
> the `superpowers:writing-plans` skill to draft the implementation
> plan. The plan should start with the mechanical DDD reorganisation
> commit (move existing flat modules into `domain/`, `infrastructure/`
> subpackages, rewrite imports, 142-test suite green) before any new
> code.

Claude should:

1. Read this file + the spec.
2. Read `~/.claude/projects/-Users-robin-code-github-yo61-jobhound/memory/project_jh_cli.md` for the full decisions list.
3. Invoke `superpowers:writing-plans` to produce an implementation plan
   broken into discrete tasks (DDD reorg → `OpportunityQuery` →
   snapshots → serialisation → `jh show` → `jh export` → docs).
4. Save the plan to `docs/plans/2026-05-13-phase3a-read-api.md`.
5. Get your approval before any code is written.

### 5. After plan approval, execute

Use the `superpowers:executing-plans` skill or work through the plan
manually. The brainstorming/design work is done; this is implementation.

## Decisions reference (one-line summary)

If you'd rather skim than re-read the spec:

- `jh show <slug>` — human text default, `--json` for machines.
- `jh export` — JSON envelope to stdout. Filters: `--status`,
  `--priority`, `--slug` (substring), `--active-only`,
  `--include-archived` (off by default).
- JSON envelope: `{schema_version, timestamp, db_root, opportunities[]}`.
  Per-opp: raw fields + `archived` + absolute `path` + `computed`
  namespace.
- Library architecture: `OpportunityQuery` is a sibling of
  `OpportunityRepository` (CQRS-shaped read/write split). No git side
  effects on construction. `today: date` is a required kwarg on
  `list`/`find`.
- DDD subpackages: `domain/` / `infrastructure/` / `application/` /
  `commands/`. `cli.py` and `prompts.py` stay at package root.
- Reorg is the first commit of 3a — mechanical only, 142 tests must
  pass before any new code lands.
- Optional extras: `[reports]` for `reportlab`+`mistune` (PDF in 3c),
  `[web]` for Starlette/Jinja2 (future daemon).
- Manual rebuild only — no auto-rebuild on mutations.

## Sub-phase plan (full)

- **3a** *(this spec)*: library + `jh show` + `jh export` + DDD reorg.
- **3b**: `jh dashboard` + `jh today` + `jh ics` (stdlib only).
- **3c**: `jh cv` + `jh pdf` (behind `[reports]` extra).
- **3d**: archive `Job Hunting 2026-04` (rename, `chflags -R uchg`).
- *(later)* HTTP daemon + web UI (behind `[web]` extra).

## Cleanup

When Phase 3a implementation begins, delete this file:

```bash
git rm PICKUP.md && git commit -m "chore: drop phase 3a pickup notes"
```
